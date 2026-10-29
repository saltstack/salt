"""Batch channel cleanup with real SaltEvent and TCP IPC subscribers."""

import asyncio
import logging

import pytest
from pytestshellutils.utils import ports
from saltfactories.utils import random_string

import salt.transport.tcp
from salt.cli.batch_async import SharedEventsChannel
from salt.utils.asynchronous import aioloop, cancel_tasks

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.windows_whitelisted,
]


@pytest.fixture
def event_channel(salt_factories, io_loop):
    # Leave the daemon stopped so real connections to its event port are refused.
    master = salt_factories.salt_master_daemon(
        random_string("batch-event-channel-"),
        overrides={
            "ipc_mode": "tcp",
            "tcp_master_pub_port": ports.get_unused_localhost_port(),
            "tcp_reconnect_backoff": 0.1,
        },
    )
    loop = aioloop(io_loop)
    channel = SharedEventsChannel(master.config, loop)
    subscriber = channel.master_event.subscriber
    initial = channel.master_event._connect_task
    assert isinstance(subscriber, salt.transport.tcp.PublishClient)
    try:
        yield channel
    finally:
        loop.run_until_complete(cancel_tasks(channel._reconnect_task, initial))
        channel._used_by.clear()
        loop.run_until_complete(channel.destroy_unused())


async def _wait_for_connection_failure(channel, task, caplog):
    async def wait():
        while not any(
            record.name == "salt.transport.tcp"
            and record.args
            and record.args[0] is channel.master_event.subscriber
            and "will reconnect" in record.msg
            for record in caplog.records
        ):
            if task.done():
                await task
                pytest.fail("Subscription finished without attempting a connection")
            await asyncio.sleep(0)

    await asyncio.wait_for(wait(), timeout=5)


async def test_destroy_unused_drains_initial_connection(event_channel, caplog):
    caplog.set_level(logging.DEBUG, logger="salt.transport.tcp")

    async def handler(*args):
        pass

    initial = event_channel.master_event._connect_task
    pending = asyncio.create_task(event_channel.subscribe("123", "return", 1, handler))
    try:
        await _wait_for_connection_failure(event_channel, pending, caplog)
        assert await event_channel.destroy_unused() is True
        assert pending.done()
        assert pending.cancelled()
        assert initial.done()
        assert event_channel.master_event is None
        assert event_channel.local_client is None
    finally:
        await cancel_tasks(pending)


async def test_destroy_unused_cancels_reconnect_after_initial_waiter_leaves(
    event_channel, caplog
):
    caplog.set_level(logging.DEBUG, logger="salt.transport.tcp")

    async def handler(*args):
        pass

    event_channel.use(1)
    event_channel.use(2)
    initial = event_channel.master_event._connect_task
    first = asyncio.create_task(event_channel.subscribe("123", "return", 1, handler))
    pending = None
    try:
        await _wait_for_connection_failure(event_channel, first, caplog)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert initial.cancelled()
        event_channel.unsubscribe(None, None, 1)
        event_channel.unuse(1)
        assert await event_channel.destroy_unused() is False

        caplog.clear()
        pending = asyncio.create_task(
            event_channel.subscribe("456", "return", 2, handler)
        )
        await _wait_for_connection_failure(event_channel, pending, caplog)
        assert event_channel._reconnect_task is pending
        event_channel.unsubscribe(None, None, 2)
        event_channel.unuse(2)
        assert await event_channel.destroy_unused() is True
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(pending, timeout=5)
        assert event_channel.master_event is None
        assert event_channel.local_client is None
    finally:
        await cancel_tasks(first, pending)
