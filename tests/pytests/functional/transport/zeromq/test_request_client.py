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

        @salt.ext.tornado.gen.coroutine
        def req_handler(stream, msg):
            stream.send(msg[0])

        stream.on_recv_stream(req_handler)

        rep = await request_client.send(b"foo")
        req_socket = request_client.message_client.socket
        rep = await request_client.send(b"foo")
        assert req_socket is request_client.message_client.socket
        request_client.close()
        assert request_client.message_client.socket is None

    finally:
        stream.close()


async def test_request_channel_issue_65265(io_loop, request_client, minion_opts, port):

    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"

    ctx = zmq.Context()
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
        stream.close()

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
        stream.close()


async def test_request_client_send_recv_socket_closed(
    io_loop, request_client, minion_opts, port, caplog
):
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    ctx = zmq.Context()
    socket = ctx.socket(zmq.REP)
    socket.bind(minion_opts["master_uri"])
    stream = zmq.eventloop.zmqstream.ZMQStream(socket, io_loop=io_loop)

    request_client.connect()
    socket = request_client.message_client.socket
    with caplog.at_level(logging.TRACE):
        request_client.close()
        await salt.ext.tornado.gen.sleep(0.5)
        assert "Send socket closed while polling." in caplog.messages
        assert f"Send and receive coroutine ending {socket}" in caplog.messages


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
                request_client.close()
                serve_socket.close()


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
                request_client.close()
                serve_socket.close()


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
        with pytest.raises(zmq.eventloop.future.CancelledError):
            try:
                await request_client.send("meh")
                await salt.ext.tornado.gen.sleep(0.3)
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
                request_client.close()
                serve_socket.close()
                ctx.term()
