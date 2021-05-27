import pytest
import salt.ext.tornado.iostream
import salt.transport.ipc
import salt.utils.asynchronous


def test_ipc_connect_in_async_methods():
    "The connect method is in IPCMessageSubscriber's async_methods property"
    assert "connect" in salt.transport.ipc.IPCMessageSubscriber.async_methods


def test_ipc_connect_sync_wrapped():
    """
    Ensure IPCMessageSubscriber.connect gets wrapped by
    salt.utils.asynchronous.SyncWrapper.
    """
    puburi = "/tmp/noexist.ipc"
    subscriber = salt.utils.asynchronous.SyncWrapper(
        salt.transport.ipc.IPCMessageSubscriber, args=(puburi,), loop_kwarg="io_loop",
    )
    with pytest.raises(salt.ext.tornado.iostream.StreamClosedError):
        subscriber.connect()
