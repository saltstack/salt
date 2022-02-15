"""
    :codeauthor: Thomas Jackson <jacksontj.89@gmail.com>
"""

import hashlib
import logging
import os

import pytest
import salt.config
import salt.crypt
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
from tests.support.mock import MagicMock, call, patch

try:
    from M2Crypto import RSA

    HAS_M2 = True
except ImportError:
    HAS_M2 = False
    try:
        from Cryptodome.Cipher import PKCS1_OAEP
    except ImportError:
        from Crypto.Cipher import PKCS1_OAEP  # nosec

log = logging.getLogger(__name__)

MASTER_PRIV_KEY = """
-----BEGIN RSA PRIVATE KEY-----
MIIEogIBAAKCAQEAoAsMPt+4kuIG6vKyw9r3+OuZrVBee/2vDdVetW+Js5dTlgrJ
aghWWn3doGmKlEjqh7E4UTa+t2Jd6w8RSLnyHNJ/HpVhMG0M07MF6FMfILtDrrt8
ZX7eDVt8sx5gCEpYI+XG8Y07Ga9i3Hiczt+fu6HYwu96HggmG2pqkOrn3iGfqBvV
YVFJzSZYe7e4c1PeEs0xYcrA4k+apyGsMtpef8vRUrNicRLc7dAcvfhtgt2DXEZ2
d72t/CR4ygtUvPXzisaTPW0G7OWAheCloqvTIIPQIjR8htFxGTz02STVXfnhnJ0Z
k8KhqKF2v1SQvIYxsZU7jaDgl5i3zpeh58cYOwIDAQABAoIBABZUJEO7Y91+UnfC
H6XKrZEZkcnH7j6/UIaOD9YhdyVKxhsnax1zh1S9vceNIgv5NltzIsfV6vrb6v2K
Dx/F7Z0O0zR5o+MlO8ZncjoNKskex10gBEWG00Uqz/WPlddiQ/TSMJTv3uCBAzp+
S2Zjdb4wYPUlgzSgb2ygxrhsRahMcSMG9PoX6klxMXFKMD1JxiY8QfAHahPzQXy9
F7COZ0fCVo6BE+MqNuQ8tZeIxu8mOULQCCkLFwXmkz1FpfK/kNRmhIyhxwvCS+z4
JuErW3uXfE64RLERiLp1bSxlDdpvRO2R41HAoNELTsKXJOEt4JANRHm/CeyA5wsh
NpscufUCgYEAxhgPfcMDy2v3nL6KtkgYjdcOyRvsAF50QRbEa8ldO+87IoMDD/Oe
osFERJ5hhyyEO78QnaLVegnykiw5DWEF02RKMhD/4XU+1UYVhY0wJjKQIBadsufB
2dnaKjvwzUhPh5BrBqNHl/FXwNCRDiYqXa79eWCPC9OFbZcUWWq70s8CgYEAztOI
61zRfmXJ7f70GgYbHg+GA7IrsAcsGRITsFR82Ho0lqdFFCxz7oK8QfL6bwMCGKyk
nzk+twh6hhj5UNp18KN8wktlo02zTgzgemHwaLa2cd6xKgmAyuPiTgcgnzt5LVNG
FOjIWkLwSlpkDTl7ZzY2QSy7t+mq5d750fpIrtUCgYBWXZUbcpPL88WgDB7z/Bjg
dlvW6JqLSqMK4b8/cyp4AARbNp12LfQC55o5BIhm48y/M70tzRmfvIiKnEc/gwaE
NJx4mZrGFFURrR2i/Xx5mt/lbZbRsmN89JM+iKWjCpzJ8PgIi9Wh9DIbOZOUhKVB
9RJEAgo70LvCnPTdS0CaVwKBgDJW3BllAvw/rBFIH4OB/vGnF5gosmdqp3oGo1Ik
jipmPAx6895AH4tquIVYrUl9svHsezjhxvjnkGK5C115foEuWXw0u60uiTiy+6Pt
2IS0C93VNMulenpnUrppE7CN2iWFAiaura0CY9fE/lsVpYpucHAWgi32Kok+ZxGL
WEttAoGAN9Ehsz4LeQxEj3x8wVeEMHF6OsznpwYsI2oVh6VxpS4AjgKYqeLVcnNi
TlZFsuQcqgod8OgzA91tdB+Rp86NygmWD5WzeKXpCOg9uA+y/YL+0sgZZHsuvbK6
PllUgXdYxqClk/hdBFB7v9AQoaj7K9Ga22v32msftYDQRJ94xOI=
-----END RSA PRIVATE KEY-----
"""


MASTER_PUB_KEY = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAoAsMPt+4kuIG6vKyw9r3
+OuZrVBee/2vDdVetW+Js5dTlgrJaghWWn3doGmKlEjqh7E4UTa+t2Jd6w8RSLny
HNJ/HpVhMG0M07MF6FMfILtDrrt8ZX7eDVt8sx5gCEpYI+XG8Y07Ga9i3Hiczt+f
u6HYwu96HggmG2pqkOrn3iGfqBvVYVFJzSZYe7e4c1PeEs0xYcrA4k+apyGsMtpe
f8vRUrNicRLc7dAcvfhtgt2DXEZ2d72t/CR4ygtUvPXzisaTPW0G7OWAheCloqvT
IIPQIjR8htFxGTz02STVXfnhnJ0Zk8KhqKF2v1SQvIYxsZU7jaDgl5i3zpeh58cY
OwIDAQAB
-----END PUBLIC KEY-----
"""


MINION_PRIV_KEY = """
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAsT6TwnlI0L7urjXu6D5E11tFJ/NglQ45jW/WN9tAUNvphq6Q
cjJCd/aWmdqlqe7ix8y9M/8rgwghRQsnPXblVBvPwFcUEXhMRnOGzqbq/0zyQX01
KecT0plBhlDt2lTyCLU6E4XCqyLbPfOxgXzsVqM0/TnzRtpVvGNy+5N4eFGylrjb
cJhPxKt2G9TDOCM/hYacDs5RVIYQQmcYb8LJq7G3++FfWpYRDaxdKoHNFDspEynd
jzr67hgThnwzc388OKNJx/7B2atwPTunPb3YBjgwDyRO/01OKK4gUHdw5KoctFgp
kDCDjwjemlyXV+MYODRTIdtOlAP83ZkntEuLoQIDAQABAoIBAAJOKNtvFGfF2l9H
S4CXZSUGU0a+JaCkR+wmnjsPwPn/dXDpAe8nGpidpNicPWqRm6WABjeQHaxda+fB
lpSrRtEdo3zoi2957xQJ5wddDtI1pmXJQrdbm0H/K39oIg/Xtv/IZT769TM6OtVg
paUxG/aftmeGXDtGfIL8w1jkuPABRBLOakWQA9uVdeG19KTU0Ag8ilpJdEX64uFJ
W75bpVjT+KO/6aV1inuCntQSP097aYvUWajRwuiYVJOxoBZHme3IObcE6mdnYXeQ
wblyWBpJUHrOS4MP4HCODV2pHKZ2rr7Nwhh8lMNw/eY9OP0ifz2AcAqe3sUMQOKP
T0qRC6ECgYEAyeU5JvUPOpxXvvChYh6gJ8pYTIh1ueDP0O5e4t3vhz6lfy9DKtRN
ROJLUorHvw/yVXMR72nT07a0z2VswcrUSw8ov3sI53F0NkLGEafQ35lVhTGs4vTl
CFoQCuAKPsxeUl4AIbfbpkDsLGQqzW1diFArK7YeQkpGuGaGodXl480CgYEA4L40
x5cUXnAhTPsybo7sbcpiwFHoGblmdkvpYvHA2QxtNSi2iHHdqGo8qP1YsZjKQn58
371NhtqidrJ6i/8EBFP1dy+y/jr9qYlZNNGcQeBi+lshrEOIf1ct56KePG79s8lm
DmD1OY8tO2R37+Py46Nq1n6viT/ST4NjLQI3GyUCgYEAiOswSDA3ZLs0cqRD/gPg
/zsliLmehTFmHj4aEWcLkz+0Ar3tojUaNdX12QOPFQ7efH6uMhwl8NVeZ6xUBlTk
hgbAzqLE1hjGBCpiowSZDZqyOcMHiV8ll/VkHcv0hsQYT2m6UyOaDXTH9g70TB6Y
KOKddGZsvO4cad/1+/jQkB0CgYAzDEEkzLY9tS57M9uCrUgasAu6L2CO50PUvu1m
Ig9xvZbYqkS7vVFhva/FmrYYsOHQNLbcgz0m0mZwm52mSuh4qzFoPxdjE7cmWSJA
ExRxCiyxPR3q6PQKKJ0urgtPIs7RlX9u6KsKxfC6OtnbTWWQO0A7NE9e13ZHxUoz
oPsvWQKBgCa0+Fb2lzUeiQz9bV1CBkWneDZUXuZHmabAZomokX+h/bq+GcJFzZjW
3kAHwYkIy9IAy3SyO/6CP0V3vAye1p+XbotiwsQ/XZnr0pflSQL3J1l1CyN3aopg
Niv7k/zBn15B72aK73R/CpUSk9W/eJGqk1NcNwf8hJHsboRYx6BR
-----END RSA PRIVATE KEY-----
"""


MINION_PUB_KEY = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAsT6TwnlI0L7urjXu6D5E
11tFJ/NglQ45jW/WN9tAUNvphq6QcjJCd/aWmdqlqe7ix8y9M/8rgwghRQsnPXbl
VBvPwFcUEXhMRnOGzqbq/0zyQX01KecT0plBhlDt2lTyCLU6E4XCqyLbPfOxgXzs
VqM0/TnzRtpVvGNy+5N4eFGylrjbcJhPxKt2G9TDOCM/hYacDs5RVIYQQmcYb8LJ
q7G3++FfWpYRDaxdKoHNFDspEyndjzr67hgThnwzc388OKNJx/7B2atwPTunPb3Y
BjgwDyRO/01OKK4gUHdw5KoctFgpkDCDjwjemlyXV+MYODRTIdtOlAP83ZkntEuL
oQIDAQAB
-----END PUBLIC KEY-----
"""

AES_KEY = "8wxWlOaMMQ4d3yT74LL4+hGrGTf65w8VgrcNjLJeLRQ2Q6zMa8ItY2EQUgMKKDb7JY+RnPUxbB0="


@pytest.fixture
def pki_dir(tmpdir):
    madir = tmpdir.mkdir("master")
    mapriv = madir.join("master.pem")
    mapriv.write(MASTER_PRIV_KEY.strip())
    mapub = madir.join("master.pub")
    mapub.write(MASTER_PUB_KEY.strip())
    mipub = madir.mkdir("minions").join("minion")
    mipub.write(MINION_PUB_KEY.strip())
    midir = tmpdir.mkdir("minion")
    mipub = midir.join("minion.pub")
    mipub.write(MINION_PUB_KEY.strip())
    mipriv = midir.join("minion.pem")
    mipriv.write(MINION_PRIV_KEY.strip())
    mimapriv = midir.join("minion_master.pub")
    mimapriv.write(MASTER_PUB_KEY.strip())
    try:
        yield tmpdir
    finally:
        tmpdir.remove()


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


def test_force_close_all_instances():
    zmq1 = MagicMock()
    zmq2 = MagicMock()
    zmq3 = MagicMock()
    zmq_objects = {"zmq": {"1": zmq1, "2": zmq2}, "other_zmq": {"3": zmq3}}

    with patch("salt.transport.zeromq.AsyncZeroMQReqChannel.instance_map", zmq_objects):
        salt.transport.zeromq.AsyncZeroMQReqChannel.force_close_all_instances()

        assert zmq1.mock_calls == [call.close()]
        assert zmq2.mock_calls == [call.close()]
        assert zmq3.mock_calls == [call.close()]

        # check if instance map changed
        assert zmq_objects is salt.transport.zeromq.AsyncZeroMQReqChannel.instance_map


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


def test_zeromq_async_pub_channel_filtering_decode_message_no_match(temp_salt_master,):
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


def test_req_server_chan_encrypt_v2(pki_dir):
    loop = salt.ext.tornado.ioloop.IOLoop.current()
    opts = {
        "worker_threads": 1,
        "master_uri": "tcp://127.0.0.1:4506",
        "interface": "127.0.0.1",
        "ret_port": 4506,
        "ipv6": False,
        "zmq_monitor": False,
        "mworker_queue_niceness": False,
        "sock_dir": ".",
        "pki_dir": str(pki_dir.join("master")),
        "id": "minion",
        "__role": "minion",
        "keysize": 4096,
    }
    server = salt.transport.zeromq.ZeroMQReqServerChannel(opts)
    dictkey = "pillar"
    nonce = "abcdefg"
    pillar_data = {"pillar1": "meh"}
    ret = server._encrypt_private(pillar_data, dictkey, "minion", nonce)
    assert "key" in ret
    assert dictkey in ret

    key = salt.crypt.get_rsa_key(str(pki_dir.join("minion", "minion.pem")), None)
    if HAS_M2:
        aes = key.private_decrypt(ret["key"], RSA.pkcs1_oaep_padding)
    else:
        cipher = PKCS1_OAEP.new(key)
        aes = cipher.decrypt(ret["key"])
    pcrypt = salt.crypt.Crypticle(opts, aes)
    signed_msg = pcrypt.loads(ret[dictkey])

    assert "sig" in signed_msg
    assert "data" in signed_msg
    data = salt.payload.Serial({}).loads(signed_msg["data"])
    assert "key" in data
    assert data["key"] == ret["key"]
    assert "key" in data
    assert data["nonce"] == nonce
    assert "pillar" in data
    assert data["pillar"] == pillar_data


def test_req_server_chan_encrypt_v1(pki_dir):
    loop = salt.ext.tornado.ioloop.IOLoop.current()
    opts = {
        "worker_threads": 1,
        "master_uri": "tcp://127.0.0.1:4506",
        "interface": "127.0.0.1",
        "ret_port": 4506,
        "ipv6": False,
        "zmq_monitor": False,
        "mworker_queue_niceness": False,
        "sock_dir": ".",
        "pki_dir": str(pki_dir.join("master")),
        "id": "minion",
        "__role": "minion",
        "keysize": 4096,
    }
    server = salt.transport.zeromq.ZeroMQReqServerChannel(opts)
    dictkey = "pillar"
    nonce = "abcdefg"
    pillar_data = {"pillar1": "meh"}
    ret = server._encrypt_private(pillar_data, dictkey, "minion", sign_messages=False)

    assert "key" in ret
    assert dictkey in ret

    key = salt.crypt.get_rsa_key(str(pki_dir.join("minion", "minion.pem")), None)
    if HAS_M2:
        aes = key.private_decrypt(ret["key"], RSA.pkcs1_oaep_padding)
    else:
        cipher = PKCS1_OAEP.new(key)
        aes = cipher.decrypt(ret["key"])
    pcrypt = salt.crypt.Crypticle(opts, aes)
    data = pcrypt.loads(ret[dictkey])
    assert data == pillar_data


def test_req_chan_decode_data_dict_entry_v1(pki_dir):
    mockloop = MagicMock()
    opts = {
        "master_uri": "tcp://127.0.0.1:4506",
        "interface": "127.0.0.1",
        "ret_port": 4506,
        "ipv6": False,
        "sock_dir": ".",
        "pki_dir": str(pki_dir.join("minion")),
        "id": "minion",
        "__role": "minion",
        "keysize": 4096,
    }
    master_opts = dict(opts, pki_dir=str(pki_dir.join("master")))
    server = salt.transport.zeromq.ZeroMQReqServerChannel(master_opts)
    client = salt.transport.zeromq.AsyncZeroMQReqChannel(opts, io_loop=mockloop)
    dictkey = "pillar"
    target = "minion"
    pillar_data = {"pillar1": "meh"}
    ret = server._encrypt_private(pillar_data, dictkey, target, sign_messages=False)
    key = client.auth.get_keys()
    if HAS_M2:
        aes = key.private_decrypt(ret["key"], RSA.pkcs1_oaep_padding)
    else:
        cipher = PKCS1_OAEP.new(key)
        aes = cipher.decrypt(ret["key"])
    pcrypt = salt.crypt.Crypticle(client.opts, aes)
    ret_pillar_data = pcrypt.loads(ret[dictkey])
    assert ret_pillar_data == pillar_data


async def test_req_chan_decode_data_dict_entry_v2(pki_dir):
    mockloop = MagicMock()
    opts = {
        "master_uri": "tcp://127.0.0.1:4506",
        "interface": "127.0.0.1",
        "ret_port": 4506,
        "ipv6": False,
        "sock_dir": ".",
        "pki_dir": str(pki_dir.join("minion")),
        "id": "minion",
        "__role": "minion",
        "keysize": 4096,
    }
    master_opts = dict(opts, pki_dir=str(pki_dir.join("master")))
    server = salt.transport.zeromq.ZeroMQReqServerChannel(master_opts)
    client = salt.transport.zeromq.AsyncZeroMQReqChannel(opts, io_loop=mockloop)

    dictkey = "pillar"
    target = "minion"
    pillar_data = {"pillar1": "meh"}

    # Mock auth and message client.
    auth = client.auth
    auth._crypticle = salt.crypt.Crypticle(opts, AES_KEY)
    client.auth = MagicMock()
    client.auth.authenticated = True
    client.auth.get_keys = auth.get_keys
    client.auth.crypticle.dumps = auth.crypticle.dumps
    client.auth.crypticle.loads = auth.crypticle.loads
    client.message_client = MagicMock()

    @salt.ext.tornado.gen.coroutine
    def mocksend(msg, timeout=60, tries=3):
        client.message_client.msg = msg
        load = client.auth.crypticle.loads(msg["load"])
        ret = server._encrypt_private(
            pillar_data, dictkey, target, nonce=load["nonce"], sign_messages=True
        )
        raise salt.ext.tornado.gen.Return(ret)

    client.message_client.send = mocksend

    # Note the 'ver' value in 'load' does not represent the the 'version' sent
    # in the top level of the transport's message.
    load = {
        "id": target,
        "grains": {},
        "saltenv": "base",
        "pillarenv": "base",
        "pillar_override": True,
        "extra_minion_data": {},
        "ver": "2",
        "cmd": "_pillar",
    }
    ret = await client.crypted_transfer_decode_dictentry(load, dictkey="pillar",)
    assert "version" in client.message_client.msg
    assert client.message_client.msg["version"] == 2
    assert ret == {"pillar1": "meh"}


async def test_req_chan_decode_data_dict_entry_v2_bad_nonce(pki_dir):
    mockloop = MagicMock()
    opts = {
        "master_uri": "tcp://127.0.0.1:4506",
        "interface": "127.0.0.1",
        "ret_port": 4506,
        "ipv6": False,
        "sock_dir": ".",
        "pki_dir": str(pki_dir.join("minion")),
        "id": "minion",
        "__role": "minion",
        "keysize": 4096,
    }
    master_opts = dict(opts, pki_dir=str(pki_dir.join("master")))
    server = salt.transport.zeromq.ZeroMQReqServerChannel(master_opts)
    client = salt.transport.zeromq.AsyncZeroMQReqChannel(opts, io_loop=mockloop)

    dictkey = "pillar"
    badnonce = "abcdefg"
    target = "minion"
    pillar_data = {"pillar1": "meh"}

    # Mock auth and message client.
    auth = client.auth
    auth._crypticle = salt.crypt.Crypticle(opts, AES_KEY)
    client.auth = MagicMock()
    client.auth.authenticated = True
    client.auth.get_keys = auth.get_keys
    client.auth.crypticle.dumps = auth.crypticle.dumps
    client.auth.crypticle.loads = auth.crypticle.loads
    client.message_client = MagicMock()
    ret = server._encrypt_private(
        pillar_data, dictkey, target, nonce=badnonce, sign_messages=True
    )

    @salt.ext.tornado.gen.coroutine
    def mocksend(msg, timeout=60, tries=3):
        client.message_client.msg = msg
        raise salt.ext.tornado.gen.Return(ret)

    client.message_client.send = mocksend

    # Note the 'ver' value in 'load' does not represent the the 'version' sent
    # in the top level of the transport's message.
    load = {
        "id": target,
        "grains": {},
        "saltenv": "base",
        "pillarenv": "base",
        "pillar_override": True,
        "extra_minion_data": {},
        "ver": "2",
        "cmd": "_pillar",
    }

    with pytest.raises(salt.crypt.AuthenticationError) as excinfo:
        ret = await client.crypted_transfer_decode_dictentry(load, dictkey="pillar",)
    assert "Pillar nonce verification failed." == excinfo.value.message


async def test_req_chan_decode_data_dict_entry_v2_bad_signature(pki_dir):
    mockloop = MagicMock()
    opts = {
        "master_uri": "tcp://127.0.0.1:4506",
        "interface": "127.0.0.1",
        "ret_port": 4506,
        "ipv6": False,
        "sock_dir": ".",
        "pki_dir": str(pki_dir.join("minion")),
        "id": "minion",
        "__role": "minion",
        "keysize": 4096,
    }
    master_opts = dict(opts, pki_dir=str(pki_dir.join("master")))
    server = salt.transport.zeromq.ZeroMQReqServerChannel(master_opts)
    client = salt.transport.zeromq.AsyncZeroMQReqChannel(opts, io_loop=mockloop)

    dictkey = "pillar"
    badnonce = "abcdefg"
    target = "minion"
    pillar_data = {"pillar1": "meh"}

    # Mock auth and message client.
    auth = client.auth
    auth._crypticle = salt.crypt.Crypticle(opts, AES_KEY)
    client.auth = MagicMock()
    client.auth.authenticated = True
    client.auth.get_keys = auth.get_keys
    client.auth.crypticle.dumps = auth.crypticle.dumps
    client.auth.crypticle.loads = auth.crypticle.loads
    client.message_client = MagicMock()

    @salt.ext.tornado.gen.coroutine
    def mocksend(msg, timeout=60, tries=3):
        client.message_client.msg = msg
        load = client.auth.crypticle.loads(msg["load"])
        ret = server._encrypt_private(
            pillar_data, dictkey, target, nonce=load["nonce"], sign_messages=True
        )

        key = client.auth.get_keys()
        if HAS_M2:
            aes = key.private_decrypt(ret["key"], RSA.pkcs1_oaep_padding)
        else:
            cipher = PKCS1_OAEP.new(key)
            aes = cipher.decrypt(ret["key"])
        pcrypt = salt.crypt.Crypticle(client.opts, aes)
        signed_msg = pcrypt.loads(ret[dictkey])
        # Changing the pillar data will cause the signature verification to
        # fail.
        data = salt.payload.Serial({}).loads(signed_msg["data"])
        data["pillar"] = {"pillar1": "bar"}
        signed_msg["data"] = salt.payload.Serial({}).dumps(data)
        ret[dictkey] = pcrypt.dumps(signed_msg)
        raise salt.ext.tornado.gen.Return(ret)

    client.message_client.send = mocksend

    # Note the 'ver' value in 'load' does not represent the the 'version' sent
    # in the top level of the transport's message.
    load = {
        "id": target,
        "grains": {},
        "saltenv": "base",
        "pillarenv": "base",
        "pillar_override": True,
        "extra_minion_data": {},
        "ver": "2",
        "cmd": "_pillar",
    }

    with pytest.raises(salt.crypt.AuthenticationError) as excinfo:
        ret = await client.crypted_transfer_decode_dictentry(load, dictkey="pillar",)
    assert "Pillar payload signature failed to validate." == excinfo.value.message


async def test_req_chan_decode_data_dict_entry_v2_bad_key(pki_dir):
    mockloop = MagicMock()
    opts = {
        "master_uri": "tcp://127.0.0.1:4506",
        "interface": "127.0.0.1",
        "ret_port": 4506,
        "ipv6": False,
        "sock_dir": ".",
        "pki_dir": str(pki_dir.join("minion")),
        "id": "minion",
        "__role": "minion",
        "keysize": 4096,
    }
    master_opts = dict(opts, pki_dir=str(pki_dir.join("master")))
    server = salt.transport.zeromq.ZeroMQReqServerChannel(master_opts)
    client = salt.transport.zeromq.AsyncZeroMQReqChannel(opts, io_loop=mockloop)

    dictkey = "pillar"
    badnonce = "abcdefg"
    target = "minion"
    pillar_data = {"pillar1": "meh"}

    # Mock auth and message client.
    auth = client.auth
    auth._crypticle = salt.crypt.Crypticle(opts, AES_KEY)
    client.auth = MagicMock()
    client.auth.authenticated = True
    client.auth.get_keys = auth.get_keys
    client.auth.crypticle.dumps = auth.crypticle.dumps
    client.auth.crypticle.loads = auth.crypticle.loads
    client.message_client = MagicMock()

    @salt.ext.tornado.gen.coroutine
    def mocksend(msg, timeout=60, tries=3):
        client.message_client.msg = msg
        load = client.auth.crypticle.loads(msg["load"])
        ret = server._encrypt_private(
            pillar_data, dictkey, target, nonce=load["nonce"], sign_messages=True
        )

        key = client.auth.get_keys()
        if HAS_M2:
            aes = key.private_decrypt(ret["key"], RSA.pkcs1_oaep_padding)
        else:
            cipher = PKCS1_OAEP.new(key)
            aes = cipher.decrypt(ret["key"])
        pcrypt = salt.crypt.Crypticle(client.opts, aes)
        signed_msg = pcrypt.loads(ret[dictkey])

        # Now encrypt with a different key
        key = salt.crypt.Crypticle.generate_key_string()
        pcrypt = salt.crypt.Crypticle(opts, key)
        pubfn = os.path.join(master_opts["pki_dir"], "minions", "minion")
        pub = salt.crypt.get_rsa_pub_key(pubfn)
        ret[dictkey] = pcrypt.dumps(signed_msg)
        key = salt.utils.stringutils.to_bytes(key)
        if HAS_M2:
            ret["key"] = pub.public_encrypt(key, RSA.pkcs1_oaep_padding)
        else:
            cipher = PKCS1_OAEP.new(pub)
            ret["key"] = cipher.encrypt(key)
        raise salt.ext.tornado.gen.Return(ret)

    client.message_client.send = mocksend

    # Note the 'ver' value in 'load' does not represent the the 'version' sent
    # in the top level of the transport's message.
    load = {
        "id": target,
        "grains": {},
        "saltenv": "base",
        "pillarenv": "base",
        "pillar_override": True,
        "extra_minion_data": {},
        "ver": "2",
        "cmd": "_pillar",
    }

    with pytest.raises(salt.crypt.AuthenticationError) as excinfo:
        ret = await client.crypted_transfer_decode_dictentry(load, dictkey="pillar",)
    assert "Key verification failed." == excinfo.value.message
