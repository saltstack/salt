import asyncio
import logging

import pytest
import tornado.gen
import tornado.iostream
import tornado.tcpserver

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
    class TestServer(tornado.tcpserver.TCPServer):
        send = []
        disconnect = False

        async def handle_stream(self, stream, address):
            try:
                log.error("Got stream %r", self.disconnect)
                while self.disconnect is False:
                    for msg in self.send[:]:
                        msg = self.send.pop(0)
                        try:
                            log.error("Write %r", msg)
                            await stream.write(msg)
                        except tornado.iostream.StreamClosedError:
                            log.error("Stream Closed Error From Test Server")
                            break
                    else:
                        log.error("SLEEP")
                        await asyncio.sleep(1)
                log.error("Close stream")
            finally:
                stream.close()
                log.error("After close stream")

    server = TestServer()
    try:
        yield server
    finally:
        server.disconnect = True
        server.stop()


@pytest.fixture
def client(io_loop, config):
    client = salt.transport.tcp.TCPPubClient(
        config.copy(), io_loop, host=config["master_ip"], port=config["publish_port"]
    )
    try:
        yield client
    finally:
        client.close()


async def test_message_client_reconnect(config, client, server):
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
    await asyncio.sleep(0.03)
    # Prepare two packed messages
    msg = salt.utils.msgpack.dumps({"test": "test1"})
    pmsg = salt.utils.msgpack.dumps({"head": {}, "body": msg})
    assert len(pmsg) == 26
    pmsg += salt.utils.msgpack.dumps({"head": {}, "body": msg})

    # Send one full and one partial msg to the client.
    partial = pmsg[:40]
    log.error("Send partial %r", partial)
    server.send.append(partial)

    while not received:
        log.error("wait received")
        await asyncio.sleep(1)
    log.error("assert received")
    assert received == [msg]
    # log.error("sleep")
    # await asyncio.sleep(1)

    # The message client has unpacked one msg and there is a partial msg left in
    # the unpacker. Closing the stream now leaves the unpacker in a bad state
    # since the rest of the partil message will never be received.
    log.error("disconnect")
    server.disconnect = True
    log.error("sleep")
    await asyncio.sleep(1)
    log.error("after sleep")
    log.error("disconnect false")
    server.disconnect = False
    log.error("sleep")
    await asyncio.sleep(1)
    log.error("after sleep")
    log.error("Disconnect False")
    received = []

    # Prior to the fix for #60831, the unpacker would be left in a broken state
    # resulting in either a TypeError or BufferFull error from msgpack. The
    # rest of this test would fail.
    log.error("Send pmsg %r", pmsg)
    server.send.append(pmsg)
    log.error("After - Send pmsg %r", pmsg)
    while not received:
        await tornado.gen.sleep(1)
    log.error("received %r", received)
    assert received == [msg, msg]
    server.disconnect = True

    # Close the client
    client.close()
    # Provide time for the on_recv task to complete
    await tornado.gen.sleep(1)
