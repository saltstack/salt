import asyncio
import logging

import pytest
import pytestshellutils.utils.ports
import zmq
import zmq.eventloop.zmqstream

import salt.exceptions
import salt.ext.tornado.gen
import salt.ext.tornado.locks
import salt.ext.tornado.platform.asyncio
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
    import time

    import salt.ext.tornado.platform

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
                yield request_client.send("foo", timeout=1)
            send_complete.set()
            return ret

        start = time.monotonic()
        io_loop.spawn_callback(send_request)

        await send_complete.wait()

        # Ensure the lock was released when the request timed out.

        locked = request_client.message_client.lock._block._value
        assert locked == 0
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
        send_complete = asyncio.Event()

        ret = await request_client.send("foo", timeout=1)
        assert ret == "bar"
    finally:
        stream.close()
