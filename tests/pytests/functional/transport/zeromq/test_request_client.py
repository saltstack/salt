import logging

import pytest
import pytestshellutils.utils.ports
import zmq
import zmq.eventloop.zmqstream

import salt.exceptions
import salt.ext.tornado.gen
import salt.ext.tornado.locks
import salt.transport.zeromq

log = logging.getLogger(__name__)

_REQ_DRAIN_TIMEOUT_S = 10
_REQ_POLL_S = 0.01

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def _blocking_teardown_req_message_client(cli):
    """
    When ``close_future`` cannot finish, release ZMQ resources.

    ``AsyncReqMessageClient.close()`` is a no-op if ``close_future()`` already
    started teardown but ``finalize()`` never ran (stuck loop, half-finished
    ``_send_recv``, etc.). ``_close_zmq_only`` matches the resource release in
    ``finalize`` without re-entering ``_initiate_async_req_close``.
    """
    try:
        mc = cli.message_client
        if getattr(mc, "socket", None) is not None:
            try:
                mc.close()
            except Exception:  # pylint: disable=broad-except
                log.debug(
                    "REQ MessageClient synchronous close failed during cleanup",
                    exc_info=True,
                )
        if getattr(mc, "socket", None) is not None:
            mc._close_zmq_only()
        mc._mark_teardown_finished()
    except Exception:  # pylint: disable=broad-except
        log.debug(
            "REQ MessageClient synchronous teardown fallback failed during cleanup",
            exc_info=True,
        )
    finally:
        # ``Transport.__del__`` warns unless ``_closing`` is set; when the owning
        # ``IOLoop`` is stopped we never yield ``cli.close_future()`` (#68637).
        setattr(cli, "_closing", True)


def _sync_yield_req_client_close_future(cli, io_loop):
    """
    Block until zeromq RequestClient asynchronous teardown completes (#68637).

    Uses ``RequestClient.close_future()``—same completion contract as
    ``AsyncReqChannel.close_async`` / ``Minion.destroy_async``—rather than polling
    ``message_client.socket is None``. If the loop is stopped or ``run_sync`` fails,
    fall back to synchronous ``AsyncReqMessageClient.close()`` (covers tests that stop
    the ``IOLoop`` before teardown).
    """

    @salt.ext.tornado.gen.coroutine
    def _wait():
        fut = cli.close_future()
        yield fut

    ok = False
    try:
        if getattr(io_loop, "_running", False):
            io_loop.run_sync(_wait, timeout=_REQ_DRAIN_TIMEOUT_S)
            ok = True
    except Exception:  # pylint: disable=broad-except
        log.debug(
            "REQ client close_future waiter aborted during cleanup", exc_info=True
        )
    if not ok or getattr(cli.message_client, "socket", None) is not None:
        _blocking_teardown_req_message_client(cli)


def _sync_finalize_req_client(cli, io_loop):
    """Explicit teardown for fixtures (wait on ``close_future``)."""
    _sync_yield_req_client_close_future(cli, io_loop)


async def async_finalize_req_client(cli):
    """
    Async cleanup: spin the I/O loop via ``gen.sleep`` until ``close_future`` completes.

    Plain ``await`` on a Tornado ``Future`` does not drive ``cli.io_loop`` in this
    test harness (#68637).
    """
    await _async_wait_close_future(cli, "fixture REQ close_future did not finish")


async def _await_req_teardown_after_close(cli):
    """After ``RequestClient.close()`` in-test, wait for deferred teardown."""
    await _async_wait_close_future(
        cli, "REQ message client did not finish teardown after RequestClient.close()"
    )


async def _async_wait_close_future(cli, fail_msg):
    fut = cli.close_future()
    n = max(1, int(_REQ_DRAIN_TIMEOUT_S / _REQ_POLL_S))
    for _ in range(n):
        if fut.done():
            fut.result()
            return
        await salt.ext.tornado.gen.sleep(_REQ_POLL_S)
    _blocking_teardown_req_message_client(cli)
    if getattr(cli.message_client, "socket", None) is not None:
        pytest.fail(fail_msg)


def _zmq_teardown_rep(stream=None, rep_socket=None, ctx=None):
    """Close REP ``ZMQStream`` / socket, optionally ``Context.term()`` (reduces pyzmq ``__del__`` noise)."""
    if stream is not None:
        try:
            if not stream.closed():
                stream.close()
        except Exception:  # pylint: disable=broad-except
            pass
    if rep_socket is not None:
        try:
            if not rep_socket.closed:
                rep_socket.close(0)
        except Exception:  # pylint: disable=broad-except
            pass
    if ctx is not None:
        try:
            ctx.term()
        except Exception:  # pylint: disable=broad-except
            pass


@pytest.fixture
def port():
    return pytestshellutils.utils.ports.get_unused_localhost_port()


@pytest.fixture
def request_client(io_loop, minion_opts, port):
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    client = salt.transport.zeromq.RequestClient(minion_opts, io_loop)
    try:
        yield client
    finally:
        _sync_finalize_req_client(client, io_loop)


async def test_request_channel_issue_64627(io_loop, request_client, minion_opts, port):
    """
    Validate socket is preserved until request channel is explicitly closed.

    When ``AsyncReqMessageClient.close()`` runs on an active ``IOLoop``, teardown is
    scheduled on the loop (#68637); yield ``close_future`` before asserting the socket is gone.
    """
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"

    ctx = zmq.Context()
    socket = ctx.socket(zmq.REP)
    socket.bind(minion_opts["master_uri"])
    stream = zmq.eventloop.zmqstream.ZMQStream(socket, io_loop=io_loop)
    try:

        @salt.ext.tornado.gen.coroutine
        def req_handler(stream, msg):
            stream.send(msg[0])

        stream.on_recv_stream(req_handler)

        rep = await request_client.send(b"foo")
        req_socket = request_client.message_client.socket
        rep = await request_client.send(b"foo")
        assert req_socket is request_client.message_client.socket
        request_client.close()
        await _await_req_teardown_after_close(request_client)
        assert request_client.message_client.socket is None

    finally:
        await async_finalize_req_client(request_client)
        _zmq_teardown_rep(stream=stream, rep_socket=socket, ctx=ctx)


async def test_request_channel_issue_65265(io_loop, request_client, minion_opts, port):

    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"

    ctx = zmq.Context()
    try:
        socket = ctx.socket(zmq.REP)
        socket.bind(minion_opts["master_uri"])
        stream = zmq.eventloop.zmqstream.ZMQStream(socket, io_loop=io_loop)

        try:
            send_complete = salt.ext.tornado.locks.Event()

            @salt.ext.tornado.gen.coroutine
            def no_handler(stream, msg):
                """
                The server never responds.
                """
                stream.close()

            stream.on_recv_stream(no_handler)

            @salt.ext.tornado.gen.coroutine
            def send_request():
                """
                The request will timeout becuse the server does not respond.
                """
                ret = None
                with pytest.raises(salt.exceptions.SaltReqTimeoutError):
                    yield request_client.send("foo", timeout=3)
                send_complete.set()
                return ret

            io_loop.spawn_callback(send_request)

            await send_complete.wait()

        finally:
            await async_finalize_req_client(request_client)
            _zmq_teardown_rep(stream=stream, rep_socket=socket)

        # Create a new server, the old socket has been closed.

        @salt.ext.tornado.gen.coroutine
        def req_handler(stream, msg):
            """
            The server responds
            """
            stream.send(salt.payload.dumps("bar"))

        socket = ctx.socket(zmq.REP)
        socket.bind(minion_opts["master_uri"])
        stream = zmq.eventloop.zmqstream.ZMQStream(socket, io_loop=io_loop)
        try:
            stream.on_recv_stream(req_handler)
            await salt.ext.tornado.gen.sleep(1)

            ret = await request_client.send("foo", timeout=1)
            assert ret == "bar"
        finally:
            await async_finalize_req_client(request_client)
            _zmq_teardown_rep(stream=stream, rep_socket=socket)
    finally:
        _zmq_teardown_rep(ctx=ctx)


async def test_request_client_send_recv_socket_closed(
    io_loop, request_client, minion_opts, port, caplog
):
    """
    REQ shutdown records coroutine teardown while the socket repr shows closed.

    Graceful teardown (#68637) delivers a queue sentinel so ``_send_recv`` often
    exits without hitting the periodic ``socket.poll(0, POLLOUT)`` path—the
    trace line ``Send socket closed while polling.`` is not guaranteed. Assert
    the stable ``Send and receive coroutine ending`` message instead.
    """
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    ctx = zmq.Context()
    socket = ctx.socket(zmq.REP)
    socket.bind(minion_opts["master_uri"])
    stream = zmq.eventloop.zmqstream.ZMQStream(socket, io_loop=io_loop)

    try:
        request_client.connect()

        with caplog.at_level(logging.TRACE):
            request_client.close()
            await _await_req_teardown_after_close(request_client)

            assert any(
                "Send and receive coroutine ending" in msg and "closed" in msg
                for msg in caplog.messages
            ), caplog.messages
    finally:
        await async_finalize_req_client(request_client)
        _zmq_teardown_rep(stream=stream, rep_socket=socket, ctx=ctx)


def test_request_client_send_recv_loop_closed(minion_opts, port, caplog):
    io_loop = salt.ext.tornado.ioloop.IOLoop()
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    ctx = zmq.Context()
    serve_socket = ctx.socket(zmq.REP)
    serve_socket.bind(minion_opts["master_uri"])
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    request_client = salt.transport.zeromq.RequestClient(minion_opts, io_loop)

    request_client.connect()

    def poll(*args, **kwargs):
        """
        Mock this error because it is incredibly hard to time this.
        """
        raise zmq.eventloop.future.CancelledError()

    socket = request_client.message_client.socket
    socket.poll = poll

    with caplog.at_level(logging.TRACE):

        @salt.ext.tornado.gen.coroutine
        def testit():
            yield salt.ext.tornado.gen.sleep(0.5)
            io_loop.stop()

        io_loop.add_callback(testit)
        io_loop.start()

        try:
            assert "Loop closed while polling send socket." in caplog.messages
            assert f"Send and receive coroutine ending {socket}" in caplog.messages
        finally:
            _sync_finalize_req_client(request_client, io_loop)
            _zmq_teardown_rep(rep_socket=serve_socket, ctx=ctx)


@pytest.mark.parametrize(
    "errno", [zmq.ETERM, zmq.ENOTSOCK, zmq.error.EINTR, zmq.EFSM, 321]
)
async def test_request_client_send_msg_socket_closed(
    io_loop, request_client, minion_opts, port, caplog, errno
):
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    ctx = zmq.Context()
    serve_socket = ctx.socket(zmq.REP)
    serve_socket.bind(minion_opts["master_uri"])

    request_client.connect()

    @salt.ext.tornado.gen.coroutine
    def send(*args, **kwargs):
        """
        Mock this error because it is incredibly hard to time this.
        """
        raise zmq.ZMQError(errno=errno)

    socket = request_client.message_client.socket
    socket.send = send
    with caplog.at_level(logging.TRACE):
        with pytest.raises(zmq.ZMQError):
            try:
                await request_client.send("meh")
                await salt.ext.tornado.gen.sleep(0.3)
                if errno == zmq.EFSM:
                    assert "Socket was found in invalid state." in caplog.messages
                elif errno != 321:
                    assert "Recieve socket closed while polling." in caplog.messages
                else:
                    assert (
                        "Unhandled Zeromq error durring send/receive: Unknown error 321"
                        in caplog.messages
                    )
                assert (
                    "The request timed out or ended with an error before sending completed. reconnecting."
                    in caplog.messages
                )
                assert f"Send and receive coroutine ending {socket}" in caplog.messages
            finally:
                await async_finalize_req_client(request_client)
                _zmq_teardown_rep(rep_socket=serve_socket, ctx=ctx)


async def test_request_client_send_msg_loop_closed(
    io_loop, request_client, minion_opts, port, caplog
):
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    ctx = zmq.Context()
    serve_socket = ctx.socket(zmq.REP)
    serve_socket.bind(minion_opts["master_uri"])

    request_client.connect()

    @salt.ext.tornado.gen.coroutine
    def send(*args, **kwargs):
        """
        Mock this error because it is incredibly hard to time this.
        """
        raise zmq.eventloop.future.CancelledError()

    socket = request_client.message_client.socket
    socket.send = send
    with caplog.at_level(logging.TRACE):
        with pytest.raises(zmq.eventloop.future.CancelledError):
            try:
                await request_client.send("meh")
                await salt.ext.tornado.gen.sleep(0.3)
                assert "Loop closed while sending." in caplog.messages
                assert f"Send and receive coroutine ending {socket}" in caplog.messages
            finally:
                await async_finalize_req_client(request_client)
                _zmq_teardown_rep(rep_socket=serve_socket, ctx=ctx)


async def test_request_client_recv_poll_loop_closed(
    io_loop, request_client, minion_opts, port, caplog
):
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    ctx = zmq.Context()
    serve_socket = ctx.socket(zmq.REP)
    serve_socket.bind(minion_opts["master_uri"])

    request_client.connect()

    socket = request_client.message_client.socket

    def poll(*args, **kwargs):
        """
        Mock this error because it is incredibly hard to time this.
        """
        if args[1] == zmq.POLLIN:
            raise zmq.eventloop.future.CancelledError()
        else:
            return socket.poll(*args, **kwargs)

    socket.poll = poll
    with caplog.at_level(logging.TRACE):
        try:
            await request_client.send("meh")
            await salt.ext.tornado.gen.sleep(0.3)
            assert "Loop closed while polling receive socket." in caplog.messages
            assert f"Send and receive coroutine ending {socket}" in caplog.messages
        finally:
            await async_finalize_req_client(request_client)
            _zmq_teardown_rep(rep_socket=serve_socket, ctx=ctx)


async def test_request_client_recv_poll_socket_closed(
    io_loop, request_client, minion_opts, port, caplog
):
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    ctx = zmq.Context()
    serve_socket = ctx.socket(zmq.REP)
    serve_socket.bind(minion_opts["master_uri"])

    request_client.connect()

    socket = request_client.message_client.socket

    def poll(*args, **kwargs):
        """
        Mock this error because it is incredibly hard to time this.
        """
        if args[1] == zmq.POLLIN:
            raise zmq.ZMQError()
        else:
            return socket.poll(*args, **kwargs)

    socket.poll = poll
    with caplog.at_level(logging.TRACE):
        with pytest.raises(zmq.ZMQError):
            try:
                await request_client.send("meh")
                await salt.ext.tornado.gen.sleep(0.3)
                assert "Receive socket closed while polling." in caplog.messages
                assert f"Send and receive coroutine ending {socket}" in caplog.messages
            finally:
                await async_finalize_req_client(request_client)
                _zmq_teardown_rep(rep_socket=serve_socket, ctx=ctx)


async def test_request_client_recv_loop_closed(
    io_loop, request_client, minion_opts, port, caplog
):
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    ctx = zmq.Context()
    serve_socket = ctx.socket(zmq.REP)
    serve_socket.bind(minion_opts["master_uri"])
    stream = zmq.eventloop.zmqstream.ZMQStream(serve_socket, io_loop=io_loop)

    @salt.ext.tornado.gen.coroutine
    def req_handler(stream, msg):
        stream.send(msg[0])

    stream.on_recv_stream(req_handler)

    request_client.connect()

    socket = request_client.message_client.socket

    @salt.ext.tornado.gen.coroutine
    def recv(*args, **kwargs):
        """
        Mock this error because it is incredibly hard to time this.
        """
        raise zmq.eventloop.future.CancelledError()

    socket.recv = recv

    with caplog.at_level(logging.TRACE):
        with pytest.raises(zmq.eventloop.future.CancelledError):
            try:
                await request_client.send("meh")
                await salt.ext.tornado.gen.sleep(0.3)
                assert "Loop closed while receiving." in caplog.messages
                assert f"Send and receive coroutine ending {socket}" in caplog.messages
            finally:
                await async_finalize_req_client(request_client)
                _zmq_teardown_rep(stream=stream, rep_socket=serve_socket, ctx=ctx)


async def test_request_client_recv_socket_closed(
    io_loop, request_client, minion_opts, port, caplog
):
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    ctx = zmq.Context()
    serve_socket = ctx.socket(zmq.REP)
    serve_socket.bind(minion_opts["master_uri"])
    stream = zmq.eventloop.zmqstream.ZMQStream(serve_socket, io_loop=io_loop)

    @salt.ext.tornado.gen.coroutine
    def req_handler(stream, msg):
        stream.send(msg[0])

    stream.on_recv_stream(req_handler)

    request_client.connect()

    socket = request_client.message_client.socket

    @salt.ext.tornado.gen.coroutine
    def recv(*args, **kwargs):
        """
        Mock this error because it is incredibly hard to time this.
        """
        raise zmq.ZMQError()

    socket.recv = recv

    with caplog.at_level(logging.TRACE):
        with pytest.raises(zmq.ZMQError):
            try:
                await request_client.send("meh")
                await salt.ext.tornado.gen.sleep(0.3)
                assert "Receive socket closed while receiving." in caplog.messages
                assert f"Send and receive coroutine ending {socket}" in caplog.messages
            finally:
                await async_finalize_req_client(request_client)
                _zmq_teardown_rep(stream=stream, rep_socket=serve_socket, ctx=ctx)
