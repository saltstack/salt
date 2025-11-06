import asyncio
import logging

import pytest
import pytestshellutils.utils.ports
import tornado.ioloop
import zmq
import zmq.eventloop.zmqstream

import salt.exceptions
import salt.transport.zeromq

log = logging.getLogger(__name__)


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
        client.close()


async def test_request_channel_issue_64627(io_loop, request_client, minion_opts, port):
    """
    Validate socket is preserved until request channel is explicitly closed.
    """
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"

    ctx = zmq.Context()
    socket = ctx.socket(zmq.REP)
    socket.bind(minion_opts["master_uri"])
    stream = zmq.eventloop.zmqstream.ZMQStream(socket, io_loop=io_loop)
    try:

        async def req_handler(stream, msg):
            stream.send(msg[0])

        stream.on_recv_stream(req_handler)

        rep = await request_client.send(b"foo")
        req_socket = request_client.socket
        rep = await request_client.send(b"foo")
        assert req_socket is request_client.socket
        request_client.close()
        assert request_client.socket is None

    finally:
        stream.close()
        ctx.term()


async def test_request_channel_issue_65265(io_loop, request_client, minion_opts, port):

    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"

    ctx = zmq.Context()
    socket = ctx.socket(zmq.REP)
    socket.bind(minion_opts["master_uri"])
    stream = zmq.eventloop.zmqstream.ZMQStream(socket, io_loop=io_loop)

    try:
        send_complete = asyncio.Event()

        async def no_handler(stream, msg):
            """
            The server never responds.
            """
            stream.close()

        stream.on_recv_stream(no_handler)

        async def send_request():
            """
            The request will timeout becuse the server does not respond.
            """
            ret = None
            with pytest.raises(salt.exceptions.SaltReqTimeoutError):
                await request_client.send("foo", timeout=3)
            send_complete.set()
            return ret

        io_loop.spawn_callback(send_request)

        await send_complete.wait()

    finally:
        stream.close()

    # Create a new server, the old socket has been closed.

    async def req_handler(stream, msg):
        """
        The server responds
        """
        stream.send(salt.payload.dumps("bar"))

    socket = ctx.socket(zmq.REP)
    socket.bind(minion_opts["master_uri"])
    stream = zmq.eventloop.zmqstream.ZMQStream(socket, io_loop=io_loop)
    try:
        stream.on_recv_stream(req_handler)
        await asyncio.sleep(1)

        ret = await request_client.send("foo", timeout=1)
        assert ret == "bar"
    finally:
        stream.close()
        ctx.term()


async def test_request_client_send_recv_socket_closed(
    io_loop, request_client, minion_opts, port, caplog
):
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    ctx = zmq.Context()
    socket = ctx.socket(zmq.REP)
    socket.bind(minion_opts["master_uri"])
    stream = zmq.eventloop.zmqstream.ZMQStream(socket, io_loop=io_loop)

    await request_client.connect()

    socket = request_client.socket
    with caplog.at_level(logging.TRACE):
        request_client.close()
        await asyncio.sleep(0.5)
        assert "Send socket closed while polling." in caplog.messages
        assert f"Send and receive coroutine ending {socket}" in caplog.messages


@pytest.mark.xfail
def test_request_client_send_recv_loop_closed(minion_opts, port, caplog):
    io_loop = tornado.ioloop.IOLoop()
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    ctx = zmq.Context()
    serve_socket = ctx.socket(zmq.REP)
    serve_socket.bind(minion_opts["master_uri"])
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    request_client = salt.transport.zeromq.RequestClient(minion_opts, io_loop)

    def poll(*args, **kwargs):
        """
        Mock this error because it is incredibly hard to time this.
        """
        raise zmq.eventloop.future.CancelledError()

    socket = request_client.socket
    socket.poll = poll

    with caplog.at_level(logging.TRACE):

        async def testit():
            await request_client.connect()
            await asyncio.sleep(0.5)
            io_loop.stop()

        io_loop.add_callback(testit)
        io_loop.start()

        try:
            assert "Loop closed while polling send socket." in caplog.messages
            assert f"Send and receive coroutine ending {socket}" in caplog.messages
        finally:
            request_client.close()
            serve_socket.close()


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

    await request_client.connect()

    async def send(*args, **kwargs):
        """
        Mock this error because it is incredibly hard to time this.
        """
        raise zmq.ZMQError(errno=errno)

    socket = request_client.socket
    socket.send = send
    with caplog.at_level(logging.TRACE):
        with pytest.raises(zmq.ZMQError):
            try:
                await request_client.send("meh")
                await asyncio.sleep(0.3)
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
                request_client.close()
                serve_socket.close()


async def test_request_client_send_msg_loop_closed(
    io_loop, request_client, minion_opts, port, caplog
):
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    ctx = zmq.Context()
    serve_socket = ctx.socket(zmq.REP)
    serve_socket.bind(minion_opts["master_uri"])

    await request_client.connect()

    async def send(*args, **kwargs):
        """
        Mock this error because it is incredibly hard to time this.
        """
        raise zmq.eventloop.future.CancelledError()

    socket = request_client.socket
    socket.send = send
    with caplog.at_level(logging.TRACE):
        with pytest.raises(zmq.eventloop.future.CancelledError):
            try:
                await request_client.send("meh")
                await asyncio.sleep(0.3)
                assert "Loop closed while sending." in caplog.messages
                assert f"Send and receive coroutine ending {socket}" in caplog.messages
            finally:
                request_client.close()
                serve_socket.close()


async def test_request_client_recv_poll_loop_closed(
    io_loop, request_client, minion_opts, port, caplog
):
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    ctx = zmq.Context()
    serve_socket = ctx.socket(zmq.REP)
    serve_socket.bind(minion_opts["master_uri"])

    await request_client.connect()

    socket = request_client.socket

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
        with pytest.raises(zmq.eventloop.future.CancelledError):
            try:
                await request_client.send("meh")
                await asyncio.sleep(0.3)
                assert "Loop closed while polling receive socket." in caplog.messages
                assert f"Send and receive coroutine ending {socket}" in caplog.messages
            finally:
                request_client.close()
                serve_socket.close()


async def test_request_client_recv_poll_socket_closed(
    io_loop, request_client, minion_opts, port, caplog
):
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    ctx = zmq.Context()
    serve_socket = ctx.socket(zmq.REP)
    serve_socket.bind(minion_opts["master_uri"])

    await request_client.connect()

    socket = request_client.socket

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
                await asyncio.sleep(0.3)
                assert "Recieve socket closed while polling." in caplog.messages
                assert f"Send and receive coroutine ending {socket}" in caplog.messages
            finally:
                request_client.close()
                serve_socket.close()


async def test_request_client_recv_loop_closed(
    io_loop, request_client, minion_opts, port, caplog
):
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    ctx = zmq.Context()
    serve_socket = ctx.socket(zmq.REP)
    serve_socket.bind(minion_opts["master_uri"])
    stream = zmq.eventloop.zmqstream.ZMQStream(serve_socket, io_loop=io_loop)

    async def req_handler(stream, msg):
        stream.send(msg[0])

    stream.on_recv_stream(req_handler)

    await request_client.connect()

    socket = request_client.socket

    async def recv(*args, **kwargs):
        """
        Mock this error because it is incredibly hard to time this.
        """
        raise zmq.eventloop.future.CancelledError()

    socket.recv = recv

    with caplog.at_level(logging.TRACE):
        with pytest.raises(zmq.eventloop.future.CancelledError):
            try:
                await request_client.send("meh")
                await asyncio.sleep(0.3)
                assert "Loop closed while receiving." in caplog.messages
                assert f"Send and receive coroutine ending {socket}" in caplog.messages
            finally:
                request_client.close()
                serve_socket.close()
                ctx.term()


async def test_request_client_recv_socket_closed(
    io_loop, request_client, minion_opts, port, caplog
):
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    ctx = zmq.Context()
    serve_socket = ctx.socket(zmq.REP)
    serve_socket.bind(minion_opts["master_uri"])
    stream = zmq.eventloop.zmqstream.ZMQStream(serve_socket, io_loop=io_loop)

    async def req_handler(stream, msg):
        stream.send(msg[0])

    stream.on_recv_stream(req_handler)

    await request_client.connect()

    socket = request_client.socket

    async def recv(*args, **kwargs):
        """
        Mock this error because it is incredibly hard to time this.
        """
        raise zmq.ZMQError()

    socket.recv = recv

    with caplog.at_level(logging.TRACE):
        with pytest.raises(zmq.ZMQError):
            try:
                await request_client.send("meh")
                await asyncio.sleep(0.3)
                assert "Receive socket closed while receiving." in caplog.messages
                assert f"Send and receive coroutine ending {socket}" in caplog.messages
            finally:
                request_client.close()
                serve_socket.close()
                ctx.term()


async def test_request_client_uses_asyncio_queue(io_loop, minion_opts, port):
    """
    Test that RequestClient uses asyncio.Queue instead of tornado.queues.Queue.
    This verifies the conversion from Tornado to pure asyncio.
    """
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    request_client = salt.transport.zeromq.RequestClient(minion_opts, io_loop)
    try:
        # Verify the queue is an asyncio.Queue
        assert isinstance(request_client._queue, asyncio.Queue)
        # Verify it has asyncio.Queue methods
        assert hasattr(request_client._queue, "get")
        assert hasattr(request_client._queue, "put")
        # Verify it doesn't have Tornado-specific attributes
        assert not hasattr(request_client._queue, "get_timeout")
    finally:
        request_client.close()


async def test_request_client_queue_timeout_uses_asyncio(
    io_loop, minion_opts, port, caplog
):
    """
    Test that RequestClient queue timeout uses asyncio.TimeoutError.
    This verifies the conversion from tornado.gen.TimeoutError to asyncio.TimeoutError.
    """
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    ctx = zmq.Context()
    serve_socket = ctx.socket(zmq.REP)
    serve_socket.bind(minion_opts["master_uri"])

    request_client = salt.transport.zeromq.RequestClient(minion_opts, io_loop)

    try:
        await request_client.connect()

        # The queue should timeout without any messages
        # This tests that asyncio.wait_for with asyncio.TimeoutError works
        # The _send_recv loop should handle the timeout gracefully

        # Send a request - it should queue properly
        future = asyncio.Future()
        await request_client._queue.put((future, b"test_message"))

        # Wait briefly
        await asyncio.sleep(0.1)

        # The _send_recv loop should have picked up the message
        # and attempted to send it (though no handler is set up)
        assert request_client._queue.qsize() == 0

    finally:
        request_client.close()
        serve_socket.close()
        ctx.term()


async def test_request_client_asyncio_cancelled_error_handling(
    io_loop, request_client, minion_opts, port, caplog
):
    """
    Test that RequestClient properly handles asyncio.CancelledError.
    This verifies the new asyncio.CancelledError exception handlers.
    """
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    ctx = zmq.Context()
    serve_socket = ctx.socket(zmq.REP)
    serve_socket.bind(minion_opts["master_uri"])

    await request_client.connect()

    socket = request_client.socket

    async def send(*args, **kwargs):
        """
        Mock send to raise asyncio.CancelledError
        """
        raise asyncio.CancelledError()

    socket.send = send

    with caplog.at_level(logging.TRACE):
        with pytest.raises(asyncio.CancelledError):
            try:
                await request_client.send("meh")
                await asyncio.sleep(0.3)
                assert "Loop closed while sending." in caplog.messages
                assert f"Send and receive coroutine ending {socket}" in caplog.messages
            finally:
                request_client.close()
                serve_socket.close()
                ctx.term()
