"""Native event sessions exchange real IPC messages and drain their readers."""

import asyncio
from types import SimpleNamespace

import pytest

import salt.minion
import salt.transport.tcp
import salt.utils.asynchronous
import salt.utils.event
from tests.support.mock import patch


@pytest.fixture
def event_broker(master_opts, io_loop):
    loop = salt.utils.asynchronous.aioloop(io_loop)
    opts = dict(master_opts)
    opts.update(ipc_mode="tcp", transport="tcp", ipv6=False)
    broker = salt.transport.tcp.PublishServer(
        opts, pub_host="127.0.0.1", pub_port=0, pull_host="127.0.0.1", pull_port=0
    )

    async def start():
        await broker.publisher(broker.publish_payload, io_loop=loop)
        pub_socket = next(iter(broker.pub_server._sockets.values()))
        opts["tcp_master_pub_port"] = pub_socket.getsockname()[1]
        opts["tcp_master_pull_port"] = broker.pull_sock.sock.getsockname()[1]

    async def close():
        broker.close()
        pending = [
            task for task in asyncio.all_tasks() if task is not asyncio.current_task()
        ]
        if pending:
            await asyncio.wait_for(asyncio.gather(*pending, return_exceptions=True), 2)

    loop.run_until_complete(start())
    yield opts
    loop.run_until_complete(close())


def native_event(opts, listen):
    return salt.utils.event.get_event(
        "master", opts=opts, listen=listen, io_loop=asyncio.get_running_loop()
    )


async def test_native_event_exchange_and_cleanup_without_syncwrapper(event_broker):
    unrelated = asyncio.create_task(asyncio.Event().wait())
    try:
        with patch(
            "salt.utils.asynchronous.SyncWrapper",
            side_effect=AssertionError("unexpected wrapper"),
        ):
            async with native_event(event_broker, True) as listener:
                subscriber = listener.subscriber
                async with native_event(event_broker, False) as sender:
                    await sender.fire_event_async({"value": False}, "test/native")
                    result = await listener.get_event_async(
                        tag="test/native", full=True
                    )
                    pusher = sender.pusher
                    assert result["tag"] == "test/native"
                    assert result["data"]["value"] is False
                assert pusher._closing
            assert subscriber._closed
        assert not unrelated.done()
        assert not asyncio.get_running_loop().is_closed()
    finally:
        await salt.utils.asynchronous.cancel_tasks(unrelated)


async def test_real_read_timeout_preserves_subscriber(event_broker):
    async with native_event(event_broker, True) as listener:
        subscriber = listener.subscriber
        assert await listener.get_event_async(wait=0.01) is None
        async with native_event(event_broker, False) as sender:
            await sender.fire_event_async({"sequence": 1}, "test/after-timeout")
            assert (await listener.get_event_async(tag="test/after-timeout"))[
                "sequence"
            ] == 1
        assert listener.subscriber is subscriber


@pytest.mark.parametrize("cancel_reader", [False, True])
async def test_interrupted_startup_read_can_receive_over_same_real_connection(
    event_broker, cancel_reader
):
    started, release = asyncio.Event(), asyncio.Event()
    connect = salt.transport.tcp.PublishClient.connect

    async def delayed_connect(client, *args, **kwargs):
        started.set()
        await release.wait()
        return await connect(client, *args, **kwargs)

    with patch.object(salt.transport.tcp.PublishClient, "connect", delayed_connect):
        listener = native_event(event_broker, True)
        read = asyncio.create_task(
            listener.get_event_async(wait=0 if cancel_reader else 0.01)
        )
        try:
            await started.wait()
            if cancel_reader:
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                read.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await read
            else:
                assert await read is None
            connection = listener._connect_task
            assert not connection.done()
            release.set()
            async with listener, native_event(event_broker, False) as sender:
                await sender.fire_event_async({"value": False}, "test/startup")
                assert (await listener.get_event_async(tag="test/startup"))[
                    "value"
                ] is False
                assert listener._connect_task is connection
        finally:
            release.set()
            await salt.utils.asynchronous.cancel_tasks(read)
            await listener.destroy_async()


async def test_destroy_drains_real_infinite_read(event_broker):
    async with native_event(event_broker, True) as listener:
        subscriber = listener.subscriber
        read = asyncio.create_task(listener.get_event_async(wait=0))
        await asyncio.sleep(0)
        await listener.destroy_async()
        with pytest.raises(asyncio.CancelledError):
            await read
        assert not listener._event_read_tasks
        assert subscriber._closed
        assert subscriber._read_task is None


async def test_syndic_request_awaits_matching_native_event_response(event_broker):
    opts = dict(
        event_broker,
        master="master",
        tcp_pub_port=event_broker["tcp_master_pub_port"],
        tcp_pull_port=event_broker["tcp_master_pull_port"],
    )
    with patch(
        "salt.utils.asynchronous.SyncWrapper",
        side_effect=AssertionError("unexpected wrapper"),
    ):
        async with salt.utils.event.get_event(
            "minion", opts=opts, io_loop=asyncio.get_running_loop()
        ) as peer:
            request = asyncio.create_task(
                salt.minion.Minion._send_req_async(
                    SimpleNamespace(opts=opts), {"request": True}, 5
                )
            )
            try:
                message = await peer.get_event_async(
                    tag="__master_req_channel_payload/", full=True
                )
                assert message["data"]["request"] is True
                request_id = message["tag"].split("/")[1]
                await peer.fire_event_async(
                    {"ret": "unrelated"}, "__master_req_channel_return/other"
                )
                await peer.fire_event_async(
                    {"ret": {"success": True}},
                    f"__master_req_channel_return/{request_id}",
                )
                assert await request == {"success": True}
            finally:
                await salt.utils.asynchronous.cancel_tasks(request)
