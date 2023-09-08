import ctypes
import multiprocessing

import msgpack
import pytest

import salt.config
import salt.transport.zeromq
from salt.master import SMaster
from tests.support.mock import MagicMock


async def test_req_server_garbage_request(io_loop):
    """
    Validate invalid msgpack messages will not raise exceptions in the
    RequestServers's message handler.
    """
    opts = salt.config.master_config("")
    request_server = salt.transport.zeromq.RequestServer(opts)

    def message_handler(payload):
        return payload

    request_server.post_fork(message_handler, io_loop)

    byts = msgpack.dumps({"foo": "bar"})
    badbyts = byts[:3] + b"^M" + byts[3:]

    try:
        ret = await request_server.handle_message(None, badbyts)
    except Exception as exc:  # pylint: disable=broad-except
        pytest.fail(f"Exception was raised {exc}")
    finally:
        request_server.close()

    assert ret == {"msg": "bad load"}


async def test_req_chan_bad_payload_to_decode(pki_dir, io_loop):
    opts = {
        "master_uri": "tcp://127.0.0.1:4506",
        "interface": "127.0.0.1",
        "ret_port": 4506,
        "ipv6": False,
        "sock_dir": ".",
        "pki_dir": str(pki_dir.joinpath("minion")),
        "id": "minion",
        "__role": "minion",
        "keysize": 4096,
        "max_minions": 0,
        "auto_accept": False,
        "open_mode": False,
        "key_pass": None,
        "publish_port": 4505,
        "auth_mode": 1,
        "acceptance_wait_time": 3,
        "acceptance_wait_time_max": 3,
    }
    SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        ),
        "reload": salt.crypt.Crypticle.generate_key_string,
    }
    master_opts = dict(opts, pki_dir=str(pki_dir.joinpath("master")))
    master_opts["master_sign_pubkey"] = False
    server = salt.channel.server.ReqServerChannel.factory(master_opts)

    with pytest.raises(salt.exceptions.SaltDeserializationError):
        server._decode_payload(None)
    with pytest.raises(salt.exceptions.SaltDeserializationError):
        server._decode_payload({})
    with pytest.raises(salt.exceptions.SaltDeserializationError):
        server._decode_payload(12345)


async def test_client_timeout_msg(minion_opts):
    client = salt.transport.zeromq.AsyncReqMessageClient(
        minion_opts, "tcp://127.0.0.1:4506"
    )
    assert hasattr(client, "_future")
    assert client._future is None
    future = salt.ext.tornado.concurrent.Future()
    client._future = future
    client.timeout_message(future)
    with pytest.raises(salt.exceptions.SaltReqTimeoutError):
        await future
    assert client._future is None

    future_a = salt.ext.tornado.concurrent.Future()
    future_b = salt.ext.tornado.concurrent.Future()
    future_b.set_exception = MagicMock()
    client._future = future_a
    client.timeout_message(future_b)

    assert client._future == future_a
    future_b.set_exception.assert_not_called()
