"""
    :codeauthor: Thomas Jackson <jacksontj.89@gmail.com>
"""

import asyncio
import hashlib
import logging
import socket
import time

import aiohttp
import pytest
import tornado.ioloop

import salt.crypt
import salt.transport.tcp
import salt.transport.ws
import salt.transport.zeromq
import salt.utils.stringutils
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.core_test,
]


def transport_ids(value):
    return f"Transport({value})"


@pytest.fixture(
    params=(
        "zeromq",
        "tcp",
        "ws",
    ),
    ids=transport_ids,
)
def transport(request):
    return request.param


async def test_zeromq_async_pub_channel_publish_port(temp_salt_master):
    """
    test when connecting that we use the publish_port set in opts when its not 4506
    """
    opts = dict(
        temp_salt_master.config.copy(),
        ipc_mode="ipc",
        pub_hwm=0,
        recon_randomize=False,
        publish_port=455505,
        recon_default=1,
        recon_max=2,
        master_ip="127.0.0.1",
        acceptance_wait_time=5,
        acceptance_wait_time_max=5,
        sign_pub_messages=False,
    )
    opts["master_uri"] = "tcp://{interface}:{publish_port}".format(**opts)
    ioloop = tornado.ioloop.IOLoop()
    # Transport will connect to port given to connect method.
    transport = salt.transport.zeromq.PublishClient(
        opts, ioloop, host=opts["master_ip"], port=121212
    )
    with transport:
        patch_socket = MagicMock(return_value=True)
        patch_auth = MagicMock(return_value=True)
        with patch.object(transport, "_socket", patch_socket):
            await transport.connect(opts["publish_port"])
    assert str(opts["publish_port"]) in patch_socket.mock_calls[0][1][0]


def test_zeromq_async_pub_channel_filtering_decode_message_no_match(
    temp_salt_master,
):
    """
    test zeromq PublishClient _decode_messages when
    zmq_filtering enabled and minion does not match
    """
    message = [
        b"4f26aeafdb2367620a393c973eddbe8f8b846eb",
        b"\x82\xa3enc\xa3aes\xa4load\xda\x00`\xeeR\xcf"
        b"\x0eaI#V\x17if\xcf\xae\x05\xa7\xb3bN\xf7\xb2\xe2"
        b'\xd0sF\xd1\xd4\xecB\xe8\xaf"/*ml\x80Q3\xdb\xaexg'
        b"\x8e\x8a\x8c\xd3l\x03\\,J\xa7\x01i\xd1:]\xe3\x8d"
        b"\xf4\x03\x88K\x84\n`\xe8\x9a\xad\xad\xc6\x8ea\x15>"
        b"\x92m\x9e\xc7aM\x11?\x18;\xbd\x04c\x07\x85\x99\xa3\xea[\x00D",
    ]

    opts = dict(
        temp_salt_master.config.copy(),
        ipc_mode="ipc",
        pub_hwm=0,
        zmq_filtering=True,
        recon_randomize=False,
        recon_default=1,
        recon_max=2,
        master_ip="127.0.0.1",
        acceptance_wait_time=5,
        acceptance_wait_time_max=5,
        sign_pub_messages=False,
    )
    opts["master_uri"] = "tcp://{interface}:{publish_port}".format(**opts)

    ioloop = tornado.ioloop.IOLoop()
    transport = salt.transport.zeromq.PublishClient(
        opts, ioloop, host=opts["master_ip"], port=121212
    )
    with transport:
        with patch(
            "salt.crypt.AsyncAuth.crypticle",
            MagicMock(return_value={"tgt_type": "glob", "tgt": "*", "jid": 1}),
        ):
            res = transport._decode_messages(message)
    assert res is None


def test_zeromq_async_pub_channel_filtering_decode_message(
    temp_salt_master, temp_salt_minion
):
    """
    test AsyncZeroMQPublishClient _decode_messages when zmq_filtered enabled
    """
    minion_hexid = salt.utils.stringutils.to_bytes(
        hashlib.sha1(salt.utils.stringutils.to_bytes(temp_salt_minion.id)).hexdigest()
    )

    message = [
        minion_hexid,
        b"\x82\xa3enc\xa3aes\xa4load\xda\x00`\xeeR\xcf"
        b"\x0eaI#V\x17if\xcf\xae\x05\xa7\xb3bN\xf7\xb2\xe2"
        b'\xd0sF\xd1\xd4\xecB\xe8\xaf"/*ml\x80Q3\xdb\xaexg'
        b"\x8e\x8a\x8c\xd3l\x03\\,J\xa7\x01i\xd1:]\xe3\x8d"
        b"\xf4\x03\x88K\x84\n`\xe8\x9a\xad\xad\xc6\x8ea\x15>"
        b"\x92m\x9e\xc7aM\x11?\x18;\xbd\x04c\x07\x85\x99\xa3\xea[\x00D",
    ]

    opts = dict(
        temp_salt_master.config.copy(),
        id=temp_salt_minion.id,
        ipc_mode="ipc",
        pub_hwm=0,
        zmq_filtering=True,
        recon_randomize=False,
        recon_default=1,
        recon_max=2,
        master_ip="127.0.0.1",
        acceptance_wait_time=5,
        acceptance_wait_time_max=5,
        sign_pub_messages=False,
    )
    opts["master_uri"] = "tcp://{interface}:{publish_port}".format(**opts)

    ioloop = tornado.ioloop.IOLoop()
    transport = salt.transport.zeromq.PublishClient(
        opts, ioloop, host=opts["master_ip"], port=121212
    )
    with transport:
        with patch(
            "salt.crypt.AsyncAuth.crypticle",
            MagicMock(return_value={"tgt_type": "glob", "tgt": "*", "jid": 1}),
        ) as mock_test:
            res = transport._decode_messages(message)

    assert res["enc"] == "aes"


async def test_publish_client_connect_server_down(transport, io_loop):
    opts = {"master_ip": "127.0.0.1"}
    host = "127.0.0.1"
    port = 111222
    if transport == "zeromq":
        client = salt.transport.zeromq.PublishClient(
            opts, io_loop, host=host, port=port
        )
        await client.connect()
        assert client._socket
    elif transport == "tcp":
        client = salt.transport.tcp.PublishClient(opts, io_loop, host=host, port=port)
        io_loop.spawn_callback(client.connect)
        assert client._stream is None
    elif transport == "ws":
        client = salt.transport.ws.PublishClient(opts, io_loop, host=host, port=port)
        io_loop.spawn_callback(client.connect)
        assert client._ws is None
        assert client._session is None
    client.close()
    await asyncio.sleep(0.03)


async def test_publish_client_connect_server_comes_up(transport, io_loop):
    opts = {"master_ip": "127.0.0.1"}
    host = "127.0.0.1"
    port = 11122
    msg = salt.payload.dumps({"meh": 123})
    if transport == "zeromq":
        import zmq

        ctx = zmq.asyncio.Context()
        uri = f"tcp://{opts['master_ip']}:{port}"
        log.debug("TEST - Senging %r", msg)
        client = salt.transport.zeromq.PublishClient(
            opts, io_loop, host=host, port=port
        )
        await client.connect()
        assert client._socket

        sock = ctx.socket(zmq.PUB)
        sock.setsockopt(zmq.BACKLOG, 1000)
        sock.setsockopt(zmq.LINGER, -1)
        sock.setsockopt(zmq.SNDHWM, 1000)
        sock.bind(uri)
        await asyncio.sleep(20)

        async def recv():
            return await client.recv(timeout=1)

        task = asyncio.create_task(recv())
        # Sleep to allow zmq to do it's thing.
        await sock.send(msg)
        await asyncio.sleep(0.03)
        await task
        response = task.result()
        assert response
        client.close()
        sock.close()
        await asyncio.sleep(0.03)
        ctx.term()
    elif transport == "tcp":

        client = salt.transport.tcp.PublishClient(opts, io_loop, host=host, port=port)
        # XXX: This is an implimentation detail of the tcp transport.
        # await client.connect(port)
        io_loop.spawn_callback(client.connect)
        assert client._stream is None
        await asyncio.sleep(2)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(0)
        sock.bind((opts["master_ip"], port))
        sock.listen(128)
        await asyncio.sleep(0.03)

        msg = salt.payload.dumps({"meh": 123})
        _msg = salt.transport.frame.frame_msg(msg, header=None)

        # This loop and timeout is needed to reliably run this test on windows.
        start = time.monotonic()
        while True:
            try:
                conn, addr = sock.accept()
            except BlockingIOError:
                await asyncio.sleep(0.3)
                if time.monotonic() - start > 30:
                    raise TimeoutError("No connection after 30 seconds")
            else:
                break

        conn.send(_msg)
        response = await client.recv()
        assert msg == response
    elif transport == "ws":
        client = salt.transport.ws.PublishClient(opts, io_loop, host=host, port=port)
        io_loop.spawn_callback(client.connect)
        assert client._ws is None
        assert client._session is None
        await asyncio.sleep(2)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(0)
        sock.bind((opts["master_ip"], port))
        sock.listen(128)

        async def handler(request):
            ws = aiohttp.web.WebSocketResponse()
            await ws.prepare(request)
            data = salt.payload.dumps(msg)
            await ws.send_bytes(data)

        server = aiohttp.web.Server(handler)
        runner = aiohttp.web.ServerRunner(server)
        await runner.setup()
        site = aiohttp.web.SockSite(runner, sock)
        await site.start()

        await asyncio.sleep(0.03)
        response = await client.recv()
        assert msg == response
    else:
        raise Exception(f"Unknown transport {transport}")
    client.close()
    await asyncio.sleep(0.03)
