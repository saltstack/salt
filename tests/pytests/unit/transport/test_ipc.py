import asyncio
import time
import logging
import os
import sys
import threading

import pytest
import salt.ext.tornado.iostream
import salt.transport.ipc
import salt.utils.asynchronous
import salt.utils.platform
from saltfactories.utils.ports import get_unused_localhost_port
from tests.support.runtests import RUNTIME_VARS

pytestmark = [
    pytest.mark.skip_on_darwin,
    pytest.mark.skip_on_freebsd,
    pytest.mark.skip_on_windows,
]

log = logging.getLogger(__name__)


def test_ipc_connect_in_async_methods():
    "The connect method is in IPCMessageSubscriber's async_methods property"
    assert "connect" in salt.transport.ipc.IPCMessageSubscriber.async_methods


async def test_ipc_connect_sync_wrapped(io_loop, tmp_path):
    """
    Ensure IPCMessageSubscriber.connect gets wrapped by
    salt.utils.asynchronous.SyncWrapper.
    """
    if salt.utils.platform.is_windows():
        socket_path = get_unused_localhost_port()
    else:
        socket_path = str(tmp_path / "noexist.ipc")
    subscriber = salt.utils.asynchronous.SyncWrapper(
        salt.transport.ipc.IPCMessageSubscriber,
        args=(socket_path,),
        kwargs={"io_loop": io_loop},
        loop_kwarg="io_loop",
    )
    # with pytest.raises(salt.ext.tornado.iostream.StreamClosedError):
    with pytest.raises(FileNotFoundError):
        # Don't `await subscriber.connect()`, that's the purpose of the SyncWrapper
        subscriber.connect()


@pytest.fixture
def opts():
    yield {"ipc_write_buffer": 0}


@pytest.fixture
def socket_path():
    remove = False
    if not os.path.exists(RUNTIME_VARS.TMP):
        os.mkdir(RUNTIME_VARS.TMP)
        remove = True
    try:
        yield os.path.join(RUNTIME_VARS.TMP, "ipc_test.ipc")
    finally:
        if remove:
            os.remove(RUNTIME_VARS.TMP)


@pytest.fixture
async def pub_channel(opts, socket_path):
    channel = salt.transport.ipc.IPCMessagePublisher(
        opts,
        socket_path,
    )
    await channel.start()
    try:
        yield channel
    finally:
        channel.close()


async def test_sync_reading(pub_channel, opts, socket_path):
    # To be completely fair let's create 2 clients.
    client1 = salt.transport.ipc.IPCMessageSubscriber(
        socket_path,
    )
    client2 = salt.transport.ipc.IPCMessageSubscriber(
        socket_path,
    )
    await client1.connect()
    await client2.connect()
    call_cnt = []
    await asyncio.sleep(0.01)
    # Now let both waiting data at once
    pub_channel.publish("TEST")
    ret1 = await client1.read()
    ret2 = await client2.read()
    assert ret1 == "TEST"
    assert ret2 == "TEST"


async def test_multi_client_reading(pub_channel, opts, socket_path, event_loop):
    # To be completely fair let's create 2 clients.
    client1 = salt.transport.ipc.IPCMessageSubscriber(
        socket_path,
    )
    client2 = salt.transport.ipc.IPCMessageSubscriber(
        socket_path,
    )

    await client1.connect()
    log.error("WTF 3")
    await client2.connect()
    call_cnt = []
    await asyncio.sleep(0.1)

    # Runs in ioloop thread so we're safe from race conditions here
    def handler(raw):
        log.error("CALLED")
        call_cnt.append(raw)

    # Now let both waiting data at once
    task1 = event_loop.create_task(client1.read_async(handler))
    task2 = event_loop.create_task(client2.read_async(handler))

    pub_channel.publish("TEST")
    start = time.time()
    timeout = 60

    while True:
        if len(call_cnt) == 2 or time.time() - start >= timeout:
            task1.cancel()
            task2.cancel()
            break
        await asyncio.sleep(.3)

    await asyncio.gather(task1, task2, return_exceptions=True)

    assert len(call_cnt) == 2
    assert call_cnt[0] == "TEST"
    assert call_cnt[1] == "TEST"


if sys.version_info > (3, 6):

    @pytest.fixture
    async def sub_channel(opts, socket_path):
        channel = salt.transport.ipc.IPCMessageSubscriber(
            socket_path,
        )
        await channel.connect()
        try:
            yield channel
        finally:
            channel.close()

    @pytest.mark.skip("This need a refactor")
    async def test_async_reading_streamclosederror(sub_channel):
        client1 = sub_channel
        call_cnt = []

        # Create a watchdog to be safe from hanging in sync loops (what old code did)
        evt = threading.Event()

        def close_server():
            if evt.wait(0.001):
                return
            client1.close()

        watchdog = threading.Thread(target=close_server)
        watchdog.start()

        # Runs in ioloop thread so we're safe from race conditions here
        def handler(raw):
            pass

        with pytest.raises(ConnectionRefusedError):
            ret1 = await client1.read_async(handler)
        # try:
        #    ret1 = await client1.read_async(handler)
        # except salt.ext.tornado.iostream.StreamClosedError as ex:
        #    assert False, "StreamClosedError was raised inside the Future"
