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
    with pytest.raises(salt.ext.tornado.iostream.StreamClosedError):
        # Don't `await subscriber.connect()`, that's the purpose of the SyncWrapper
        subscriber.connect()


@pytest.fixture
def opts():
    yield {"ipc_write_buffer": 0}


@pytest.fixture
def socket_path():
    yield os.path.join(RUNTIME_VARS.TMP, "ipc_test.ipc")


@pytest.fixture
def pub_channel(opts, socket_path):
    channel = salt.transport.ipc.IPCMessagePublisher(
        opts,
        socket_path,
    )
    channel.start()
    yield channel
    channel.close()


async def test_sync_reading(pub_channel, opts, socket_path):
    # To be completely fair let's create 2 clients.
    client1 = salt.transport.ipc.IPCMessageSubscriber(
        opts,
        socket_path,
    )
    client2 = salt.transport.ipc.IPCMessageSubscriber(
        opts,
        socket_path,
    )
    await client1.connect()
    await client2.connect()
    call_cnt = []
    # Now let both waiting data at once
    pub_channel.publish("TEST")
    ret1 = client1.read_sync()
    ret2 = client2.read_sync()
    assert ret1 == "TEST"
    assert ret2 == "TEST"


async def test_multi_client_reading(pub_channel, opts, socket_path):
    # To be completely fair let's create 2 clients.
    client1 = salt.transport.ipc.IPCMessageSubscriber(
        opts,
        socket_path,
    )
    client2 = salt.transport.ipc.IPCMessageSubscriber(
        opts,
        socket_path,
    )
    await client1.connect()
    await client2.connect()
    call_cnt = []

    # Create a watchdog to be safe from hanging in sync loops (what old code did)
    evt = threading.Event()

    # Runs in ioloop thread so we're safe from race conditions here
    def handler(raw):
        call_cnt.append(raw)

    # Now let both waiting data at once
    await client1.read_async(handler)
    await client2.read_async(handler)
    pub_channel.publish("TEST")
    assert len(call_cnt) == 2
    assert call_cnt[0] == "TEST"
    assert call_cnt[1] == "TEST"


if sys.version_info > (3, 5):

    @pytest.fixture
    async def sub_channel(opts, socket_path):
        channel = salt.transport.ipc.IPCMessageSubscriber(
            opts,
            socket_path,
        )
        await channel.connect()
        try:
            yield channel
        finally:
            channel.close()

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

        try:
            ret1 = await client1.read_async(handler)
        except salt.ext.tornado.iostream.StreamClosedError as ex:
            assert False, "StreamClosedError was raised inside the Future"
