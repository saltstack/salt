import socket

import pytest
from pytestshellutils.utils import ports

import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.ext.tornado.iostream
import salt.transport.frame
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


async def test_ipc_publisher_drops_non_consuming_client_68114(io_loop, tmp_path):
    """
    Regression for #68114.

    A subscriber that connects to ``IPCMessagePublisher`` but never reads
    from the socket used to make ``IPCMessagePublisher._write`` block on
    ``stream.write()`` forever -- ``publish()`` kept queueing more
    ``spawn_callback(self._write, ...)`` coroutines per message, all of
    which awaited a write that would never complete. The pending writes
    (plus their referenced payloads) accumulated in the publisher's event
    loop, causing the master event publisher's RSS to grow without bound
    against a non-consuming IPC client.

    With the fix, ``_write`` applies a configurable ``ipc_write_timeout``.
    When a write to a slow/non-consuming subscriber does not complete in
    time, the stream is closed and removed from ``self.streams`` so the
    publisher reclaims memory and stops spawning new writers for that
    client.
    """
    if salt.utils.platform.is_windows():
        pytest.skip("IPCMessagePublisher uses unix sockets only on this path")

    socket_path = str(tmp_path / "pub_68114.ipc")
    opts = {
        # Default in real deployments is 0 (unbounded write buffer); that is
        # exactly the case where a non-consuming subscriber leaks memory in
        # the publisher because tornado's IOStream never raises
        # StreamBufferFullError and the pending writes accumulate.
        "ipc_write_buffer": 0,
        # Tight timeout so the test does not have to wait long for the drop.
        "ipc_write_timeout": 1,
    }

    publisher = salt.transport.ipc.IPCMessagePublisher(
        opts, socket_path, io_loop=io_loop
    )
    publisher.start()
    try:
        # Non-consuming subscriber: a raw blocking UNIX socket that never reads.
        slow = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        slow.setblocking(False)
        try:
            slow.connect(socket_path)
        except BlockingIOError:
            pass

        # Let the publisher's accept handler register the new stream.
        for _ in range(20):
            await salt.ext.tornado.gen.sleep(0.05)
            if publisher.streams:
                break
        assert publisher.streams, "publisher never registered the slow subscriber"

        # Publish enough oversized payloads that the unix-socket send buffer
        # is guaranteed to back up; with ipc_write_buffer=0 tornado's
        # IOStream will never raise StreamBufferFullError, so before the fix
        # the _write coroutines for the slow client awaited stream.write()
        # forever and accumulated in the event loop.
        big_payload = "x" * (256 * 1024)
        for _ in range(64):
            publisher.publish(big_payload)

        # Wait for the publisher's write timeout to fire and drop the slow
        # stream. ipc_write_timeout=1 so a few seconds is plenty.
        for _ in range(60):
            await salt.ext.tornado.gen.sleep(0.1)
            if not publisher.streams:
                break

        assert not publisher.streams, (
            "publisher did not drop a non-consuming subscriber after"
            " ipc_write_timeout elapsed"
        )

        try:
            slow.close()
        except OSError:
            pass
    finally:
        publisher.close()


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
