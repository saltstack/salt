import pytest
import pytestshellutils.utils.ports
import zmq
import zmq.eventloop.zmqstream

import salt.ext.tornado.gen
import salt.transport.zeromq


@pytest.fixture
def port():
    return pytestshellutils.utils.ports.get_unused_localhost_port()


async def test_request_channel_issue_64627(io_loop, minion_opts, port):
    """
    Validate socket is preserved until request channel is explicitly closed.
    """
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"

    ctx = zmq.Context()
    socket = ctx.socket(zmq.REP)
    socket.bind(minion_opts["master_uri"])
    stream = zmq.eventloop.zmqstream.ZMQStream(socket, io_loop=io_loop)

    @salt.ext.tornado.gen.coroutine
    def req_handler(stream, msg):
        yield stream.send(msg[0])

    stream.on_recv_stream(req_handler)

    request_client = salt.transport.zeromq.RequestClient(minion_opts, io_loop)

    rep = await request_client.send(b"foo")
    req_socket = request_client.message_client.stream.socket
    rep = await request_client.send(b"foo")
    assert req_socket is request_client.message_client.stream.socket
    request_client.close()
    assert request_client.message_client.stream is None
