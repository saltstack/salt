import logging

import pytest

import salt.ext.tornado.gen
import salt.ext.tornado.iostream
import salt.ext.tornado.tcpserver
import salt.transport.tcp
import salt.utils.msgpack

log = logging.getLogger(__name__)


@pytest.fixture
def config():
    yield {
        "master_ip": "127.0.0.1",
        "publish_port": 5679,
    }


@pytest.fixture
def server(config):
    class TestServer(salt.ext.tornado.tcpserver.TCPServer):
        send = []
        disconnect = False

        async def handle_stream(  # pylint: disable=invalid-overridden-method
            self, stream, address
        ):
            while self.disconnect is False:
                for msg in self.send[:]:
                    msg = self.send.pop(0)
                    try:
                        await stream.write(msg)
                    except salt.ext.tornado.iostream.StreamClosedError:
                        break
                else:
                    await salt.ext.tornado.gen.sleep(1)
            stream.close()

    server = TestServer()
    try:
        yield server
    finally:
        server.disconnect = True
        server.stop()


@pytest.fixture
def client(io_loop, config):
    client = salt.transport.tcp.TCPPubClient(config.copy(), io_loop)
    try:
        yield client
    finally:
        client.close()


async def test_message_client_reconnect(io_loop, config, client, server):
    """
    Verify that the tcp MessageClient class re-sets it's unpacker after a
    stream disconnect.
    """

    server.listen(config["publish_port"])
    await client.connect(config["publish_port"])

    received = []

    def handler(msg):
        received.append(msg)

    client.on_recv(handler)

    # Prepare two packed messages
    msg = salt.utils.msgpack.dumps({"test": "test1"})
    pmsg = salt.utils.msgpack.dumps({"head": {}, "body": msg})
    assert len(pmsg) == 26
    pmsg += salt.utils.msgpack.dumps({"head": {}, "body": msg})

    # Send one full and one partial msg to the client.
    partial = pmsg[:40]
    server.send.append(partial)

    while not received:
        await salt.ext.tornado.gen.sleep(1)
    assert received == [msg]

    # The message client has unpacked one msg and there is a partial msg left in
    # the unpacker. Closing the stream now leaves the unpacker in a bad state
    # since the rest of the partil message will never be received.
    server.disconnect = True
    await salt.ext.tornado.gen.sleep(1)
    server.disconnect = False
    received = []

    # Prior to the fix for #60831, the unpacker would be left in a broken state
    # resulting in either a TypeError or BufferFull error from msgpack. The
    # rest of this test would fail.
    server.send.append(pmsg)
    while not received:
        await salt.ext.tornado.gen.sleep(1)
    assert received == [msg, msg]
