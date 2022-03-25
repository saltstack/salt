"""
    :codeauthor: Thomas Jackson <jacksontj.89@gmail.com>
"""

import asyncio
import hashlib
import logging

import pytest
import salt.channel.client
import salt.config
import salt.exceptions
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.log.setup
import salt.transport.zeromq
import salt.utils.platform
import salt.utils.process
import salt.utils.stringutils
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


def test_master_uri():
    """
    test _get_master_uri method
    """

    m_ip = "127.0.0.1"
    m_port = 4505
    s_ip = "111.1.0.1"
    s_port = 4058

    m_ip6 = "1234:5678::9abc"
    s_ip6 = "1234:5678::1:9abc"

    with patch("salt.transport.zeromq.LIBZMQ_VERSION_INFO", (4, 1, 6)), patch(
        "salt.transport.zeromq.ZMQ_VERSION_INFO", (16, 0, 1)
    ):
        # pass in both source_ip and source_port
        assert salt.transport.zeromq._get_master_uri(
            master_ip=m_ip, master_port=m_port, source_ip=s_ip, source_port=s_port
        ) == "tcp://{}:{};{}:{}".format(s_ip, s_port, m_ip, m_port)

        assert salt.transport.zeromq._get_master_uri(
            master_ip=m_ip6, master_port=m_port, source_ip=s_ip6, source_port=s_port
        ) == "tcp://[{}]:{};[{}]:{}".format(s_ip6, s_port, m_ip6, m_port)

        # source ip and source_port empty
        assert salt.transport.zeromq._get_master_uri(
            master_ip=m_ip, master_port=m_port
        ) == "tcp://{}:{}".format(m_ip, m_port)

        assert salt.transport.zeromq._get_master_uri(
            master_ip=m_ip6, master_port=m_port
        ) == "tcp://[{}]:{}".format(m_ip6, m_port)

        # pass in only source_ip
        assert salt.transport.zeromq._get_master_uri(
            master_ip=m_ip, master_port=m_port, source_ip=s_ip
        ) == "tcp://{}:0;{}:{}".format(s_ip, m_ip, m_port)

        assert salt.transport.zeromq._get_master_uri(
            master_ip=m_ip6, master_port=m_port, source_ip=s_ip6
        ) == "tcp://[{}]:0;[{}]:{}".format(s_ip6, m_ip6, m_port)

        # pass in only source_port
        assert salt.transport.zeromq._get_master_uri(
            master_ip=m_ip, master_port=m_port, source_port=s_port
        ) == "tcp://0.0.0.0:{};{}:{}".format(s_port, m_ip, m_port)


def test_clear_req_channel_master_uri_override(temp_salt_minion, temp_salt_master):
    """
    ensure master_uri kwarg is respected
    """
    opts = temp_salt_minion.config.copy()
    # minion_config should be 127.0.0.1, we want a different uri that still connects
    opts.update(
        {
            "id": "root",
            "transport": "zeromq",
            "auth_tries": 1,
            "auth_timeout": 5,
            "master_ip": "127.0.0.1",
            "master_port": temp_salt_master.config["ret_port"],
            "master_uri": "tcp://127.0.0.1:{}".format(
                temp_salt_master.config["ret_port"]
            ),
        }
    )
    master_uri = "tcp://{master_ip}:{master_port}".format(
        master_ip="localhost", master_port=opts["master_port"]
    )
    with salt.channel.client.ReqChannel.factory(opts, master_uri=master_uri) as channel:
        assert "127.0.0.1" in channel.transport.message_client.addr


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
    ioloop = asyncio.get_event_loop()
    transport = salt.transport.zeromq.PublishClient(opts, ioloop)
    with transport:
        patch_socket = MagicMock(return_value=True)
        patch_auth = MagicMock(return_value=True)
        with patch.object(transport, "_socket", patch_socket):
            await transport.connect(455505)
    assert str(opts["publish_port"]) in patch_socket.mock_calls[0][1][0]


async def test_zeromq_async_pub_channel_filtering_decode_message_no_match(
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

    ioloop = asyncio.get_event_loop()
    channel = salt.transport.zeromq.PublishClient(opts, ioloop)
    with channel:
        with patch(
            "salt.crypt.AsyncAuth.crypticle",
            MagicMock(return_value={"tgt_type": "glob", "tgt": "*", "jid": 1}),
        ):
            res = await channel._decode_messages(message)
    assert res is None


async def test_zeromq_async_pub_channel_filtering_decode_message(
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

    ioloop = asyncio.get_event_loop()
    channel = salt.transport.zeromq.PublishClient(opts, ioloop)
    with channel:
        with patch(
            "salt.crypt.AsyncAuth.crypticle",
            MagicMock(return_value={"tgt_type": "glob", "tgt": "*", "jid": 1}),
        ) as mock_test:
            res = await channel._decode_messages(message)

    assert res["enc"] == "aes"
import zmq

async def test_zeromq_req_channel(temp_salt_master, temp_salt_minion, event_loop):
    event_loop.set_debug(False)

    async def monitorclient(server_url="tcp://127.0.0.1:9999"):
        try:
            context = zmq.asyncio.Context()
            socket = context.socket(zmq.SUB)
            socket.connect(server_url)
            socket.setsockopt(zmq.SUBSCRIBE, b"")
            log.error( "started monitoring client")

            while True:
                res = await socket.recv_multipart()
                log.error("MON GOT %r", res)
        except Exception as exc:
            log.exception("mon")

    #task = event_loop.create_task(monitorclient())
    log.error("WTF %r", event_loop)
    opts = dict(
        temp_salt_master.config.copy(),
        id=temp_salt_minion.id,
        ipc_mode="ipc",
        pub_hwm=10,
        zmq_filtering=True,
        recon_randomize=False,
        recon_default=1,
        recon_max=2,
        master_ip="127.0.0.1",
        acceptance_wait_time=5,
        acceptance_wait_time_max=5,
        sign_pub_messages=False,
    )
    opts["master_uri"] = "tcp://{interface}:{ret_port}".format(**opts)
    # for k in opts:
    #    log.error("%s=%r", k, opts[k])
    req_server = salt.transport.zeromq.RequestServer(opts)
    process_manager = salt.utils.process.ProcessManager(name="ReqServer-ProcessManager")
    req_server.pre_fork(process_manager)
    await asyncio.sleep(2)
    event = asyncio.Event()

    async def handle_payload(payload):
        return payload
    req_server.post_fork(handle_payload, event_loop)


    req_client = salt.transport.zeromq.RequestClient(opts, event_loop)
    log.error("SEND 1")
    resp = await req_client.send({"wtf": "meh"}, timeout=3)
    assert resp == {"wtf": "meh"}

    event.set()

    process_manager.terminate()
    req_server.close()
    await req_server.task

    assert req_client.message_client.socket
    with pytest.raises(salt.transport.zeromq.SaltReqTimeoutError):
        log.error("SEND 2")
        resp = await req_client.send({"wtf": "meh"}, timeout=3)


    #assert req_client.message_client.socket.closed
    #req_client.message_client.context.destroy()

    req_server = salt.transport.zeromq.RequestServer(opts)
    process_manager = salt.utils.process.ProcessManager(name="ReqServer-ProcessManager")
    req_server.pre_fork(process_manager)
    await asyncio.sleep(2)

    req_server.post_fork(handle_payload, event_loop)

    await asyncio.sleep(2)

    log.error("SEND 3")
    # req_client = salt.transport.zeromq.RequestClient(opts, io_loop)
    resp = await req_client.send({"wtf": "meh"}, timeout=10)
    assert resp == {"wtf": "meh"}
    process_manager.terminate()
    req_server.close()
