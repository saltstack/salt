import pytest
from pytestshellutils.utils import ports

import salt.ext.tornado.iostream
import salt.transport.ipc
import salt.utils.asynchronous
import salt.utils.platform

pytestmark = [
    pytest.mark.core_test,
]


def test_ipc_connect_in_async_methods():
    "The connect method is in IPCMessageSubscriber's async_methods property"
    assert "connect" in salt.transport.ipc.IPCMessageSubscriber.async_methods


async def test_ipc_connect_sync_wrapped(io_loop, tmp_path):
    """
    Ensure IPCMessageSubscriber.connect gets wrapped by
    salt.utils.asynchronous.SyncWrapper.
    """
    if salt.utils.platform.is_windows():
        socket_path = ports.get_unused_localhost_port()
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


async def test_ipc_client_connect_after_close_no_attribute_error(io_loop, tmp_path):
    """
    Regression for #68993.

    When IPCClient.close() runs while _connect() is still pending, the
    coroutine eventually resumes and used to call set_result/set_exception
    on self._connecting_future after close() had cleared it to None,
    raising AttributeError. _connect() must tolerate a cleared
    _connecting_future.
    """
    if salt.utils.platform.is_windows():
        socket_path = ports.get_unused_localhost_port()
    else:
        socket_path = str(tmp_path / "noexist.ipc")
    client = salt.transport.ipc.IPCClient(socket_path, io_loop=io_loop)
    # Simulate the race: _connecting_future has already been cleared by
    # close() by the time _connect() reaches its set_result/set_exception
    # call sites. timeout=0 forces the failure branch on the first attempt.
    client._connecting_future = None
    await client._connect(timeout=0)
