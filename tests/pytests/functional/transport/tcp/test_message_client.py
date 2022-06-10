import logging

import salt.transport.tcp
import salt.utils.msgpack
from tornado import gen
from tornado.iostream import StreamClosedError
from tornado.tcpserver import TCPServer

log = logging.getLogger(__name__)


async def test_message_client_reconnect(io_loop):
    """
    Verify that the tcp MessageClient class re-sets it's unpacker after a
    stream disconnect.
    """
    config = {
        "master_ip": "127.0.0.1",
        "publish_port": 5679,
    }

    class TestServer(TCPServer):
        send = []
        stop = False

        async def handle_stream(self, stream, address):
            while self.stop is False:
                for msg in self.send[:]:
                    msg = self.send.pop(0)
                    try:
                        await stream.write(msg)
                    except StreamClosedError:
                        break
                else:
                    await gen.sleep(1)
            stream.close()

    received = []
    server = TestServer()
    server.listen(config["publish_port"])

    client = salt.transport.tcp.TCPPubClient(config.copy(), io_loop)
    await client.connect(config["publish_port"])

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
        await gen.sleep(1)
    assert received == [msg]

    # The message client has unpacked one msg and there is a partial msg left in
    # the unpacker. Closing the stream now leaves the unpacker in a bad state
    # since the rest of the partil message will never be received.
    server.stop = True
    await gen.sleep(1)
    server.stop = False
    received = []

    # Prior to the fix for #60831, the unpacker would be left in a broken state
    # resulting in either a TypeError or BufferFull error from msgpack. The
    # rest of this test would fail.
    server.send.append(pmsg)
    while not received:
        await gen.sleep(1)
    assert received == [msg, msg]
    server.stop = True
