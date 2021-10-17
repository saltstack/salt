"""
    :codeauthor: Thomas Jackson <jacksontj.89@gmail.com>
"""

import hashlib

import salt.config
import salt.exceptions
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.log.setup
import salt.transport.client
import salt.transport.server
import salt.utils.platform
import salt.utils.process
import salt.utils.stringutils
from salt.transport.zeromq import AsyncReqMessageClientPool
from tests.support.mock import MagicMock, patch


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


def test_async_req_message_client_pool_send():
    sock_pool_size = 5
    with patch(
        "salt.transport.zeromq.AsyncReqMessageClient.__init__",
        MagicMock(return_value=None),
    ):
        message_client_pool = AsyncReqMessageClientPool(
            {"sock_pool_size": sock_pool_size}, args=({}, "")
        )
        message_client_pool.message_clients = [
            MagicMock() for _ in range(sock_pool_size)
        ]
        for message_client_mock in message_client_pool.message_clients:
            message_client_mock.send_queue = [0, 0, 0]
            message_client_mock.send.return_value = []

        with message_client_pool:
            assert message_client_pool.send() == []

            message_client_pool.message_clients[2].send_queue = [0]
            message_client_pool.message_clients[2].send.return_value = [1]
            assert message_client_pool.send() == [1]


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
    with salt.transport.client.ReqChannel.factory(
        opts, master_uri=master_uri
    ) as channel:
        assert "localhost" in channel.master_uri


def test_zeromq_async_pub_channel_publish_port(temp_salt_master):
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

    channel = salt.transport.zeromq.AsyncZeroMQPubChannel(opts)
    with channel:
        patch_socket = MagicMock(return_value=True)
        patch_auth = MagicMock(return_value=True)
        with patch.object(channel, "_socket", patch_socket), patch.object(
            channel, "auth", patch_auth
        ):
            channel.connect()
    assert str(opts["publish_port"]) in patch_socket.mock_calls[0][1][0]


def test_zeromq_async_pub_channel_filtering_decode_message_no_match(
    temp_salt_master,
):
    """
    test AsyncZeroMQPubChannel _decode_messages when
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

    channel = salt.transport.zeromq.AsyncZeroMQPubChannel(opts)
    with channel:
        with patch(
            "salt.crypt.AsyncAuth.crypticle",
            MagicMock(return_value={"tgt_type": "glob", "tgt": "*", "jid": 1}),
        ):
            res = channel._decode_messages(message)
    assert res.result() is None


def test_zeromq_async_pub_channel_filtering_decode_message(
    temp_salt_master, temp_salt_minion
):
    """
    test AsyncZeroMQPubChannel _decode_messages when zmq_filtered enabled
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

    channel = salt.transport.zeromq.AsyncZeroMQPubChannel(opts)
    with channel:
        with patch(
            "salt.crypt.AsyncAuth.crypticle",
            MagicMock(return_value={"tgt_type": "glob", "tgt": "*", "jid": 1}),
        ) as mock_test:
            res = channel._decode_messages(message)

    assert res.result()["enc"] == "aes"
