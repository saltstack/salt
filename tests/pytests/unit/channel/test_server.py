import pytest

import salt.channel.server as server
from tests.support.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def key_data():
    return [
        "-----BEGIN PUBLIC KEY-----",
        "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAoe5QSDYRWKyknbVyRrIj",
        "rm1ht5HgKzAVUber0x54+b/UgxTd1cqI6I+eDlx53LqZSH3G8Rd5cUh8LHoGedSa",
        "E62vEiLAjgXa+RdgcGiQpYS8+Z2RvQJ8oIcZgO+2AzgBRHboNWHTYRRmJXCd3dKs",
        "9tcwK6wxChR06HzGqaOTixAuQlegWbOTU+X4dXIbW7AnuQBt9MCib7SxHlscrqcS",
        "cBrRvq51YP6cxPm/rZJdBqZhVrlghBvIpa45NApP5PherGi4AbEGYte4l+gC+fOA",
        "osEBis1V27djPpIyQS4qk3XAPQg6CYQMDltHqA4Fdo0Nt7SMScxJhfH0r6zmBFAe",
        "BQIDAQAB",
        "-----END PUBLIC KEY-----",
    ]


@pytest.mark.parametrize("linesep", ["\r\n", "\r", "\n"])
def test_compare_keys(key_data, linesep):
    src_key = linesep.join(key_data)
    tgt_key = "\n".join(key_data)
    assert server.ReqServerChannel.compare_keys(src_key, tgt_key) is True


@pytest.mark.parametrize("linesep", ["\r\n", "\r", "\n"])
def test_compare_keys_newline_src(key_data, linesep):
    src_key = linesep.join(key_data) + linesep
    tgt_key = "\n".join(key_data)
    assert src_key.endswith(linesep)
    assert not tgt_key.endswith("\n")
    assert server.ReqServerChannel.compare_keys(src_key, tgt_key) is True


@pytest.mark.parametrize("linesep", ["\r\n", "\r", "\n"])
def test_compare_keys_newline_tgt(key_data, linesep):
    src_key = linesep.join(key_data)
    tgt_key = "\n".join(key_data) + "\n"
    assert not src_key.endswith(linesep)
    assert tgt_key.endswith("\n")
    assert server.ReqServerChannel.compare_keys(src_key, tgt_key) is True


@pytest.fixture
def root_dir(tmp_path):
    (tmp_path / "var").mkdir()
    (tmp_path / "var" / "cache").mkdir()
    (tmp_path / "var" / "run").mkdir()
    (tmp_path / "etc").mkdir()
    (tmp_path / "etc" / "salt").mkdir()
    (tmp_path / "etc" / "salt" / "pki").mkdir()
    (tmp_path / "etc" / "salt" / "pki" / "minions").mkdir()
    yield tmp_path


def test_req_server_validate_token_removes_token(root_dir):
    opts = {
        "id": "minion",
        "__role": "minion",
        "master_uri": "tcp://127.0.0.1:4505",
        "cachedir": str(root_dir / "var" / "cache"),
        "pki_dir": str(root_dir / "etc" / "salt" / "pki"),
        "sock_dir": str(root_dir / "var" / "run"),
        "key_pass": "",
        "keysize": 2048,
        "master_sign_pubkey": False,
        "keys.cache_driver": "localfs_key",
        "optimization_order": (0, 1, 2),
        "permissive_pki_access": False,
        "cluster_id": "",
    }
    reqsrv = server.ReqServerChannel.factory(opts)
    payload = {
        "load": {
            "id": "minion",
            "tok": "asdf",
        }
    }
    assert reqsrv.validate_token(payload) is False
    assert "tok" not in payload["load"]


def test_req_server_validate_token_removes_token_id_traversal(root_dir):
    opts = {
        "id": "minion",
        "__role": "minion",
        "master_uri": "tcp://127.0.0.1:4505",
        "cachedir": str(root_dir / "var" / "cache"),
        "pki_dir": str(root_dir / "etc" / "salt" / "pki"),
        "sock_dir": str(root_dir / "var" / "run"),
        "key_pass": "",
        "keysize": 2048,
        "master_sign_pubkey": False,
        "keys.cache_driver": "localfs_key",
        "optimization_order": (0, 1, 2),
        "permissive_pki_access": False,
        "cluster_id": "",
    }
    reqsrv = server.ReqServerChannel.factory(opts)
    payload = {
        "load": {
            "id": "minion/../../foo",
            "tok": "asdf",
        }
    }
    assert reqsrv.validate_token(payload) is False
    assert "tok" not in payload["load"]


async def test_handle_message_exceptions(temp_salt_master):
    """
    test exceptions are handled cleanly in handle_message
    """
    opts = dict(temp_salt_master.config.copy())
    req = server.ReqServerChannel(opts, None)

    with patch(
        "salt.channel.server.ReqServerChannel._decode_payload",
        MagicMock(side_effect=OSError()),
    ):
        ret = await req.handle_message({})
        assert ret == "bad load"

    with patch(
        "salt.channel.server.ReqServerChannel._decode_payload",
        MagicMock(return_value="foobar"),
    ):
        ret = await req.handle_message({})
        assert ret == "bad load"

    with patch(
        "salt.channel.server.ReqServerChannel._decode_payload",
        MagicMock(return_value={"load": {"id": "foo\0"}}),
    ):
        ret = await req.handle_message({"enc": "clear", "load": {}})
        assert ret == "bad load: id contains a null byte"

    with patch(
        "salt.channel.server.ReqServerChannel._decode_payload",
        MagicMock(return_value={"load": {"id": None}}),
    ):
        ret = await req.handle_message({"enc": "clear", "load": {}})
        assert ret == "bad load: id None is not a string"

    with patch(
        "salt.channel.server.ReqServerChannel._decode_payload",
        MagicMock(return_value={"enc": "clear", "load": {"cmd": "_auth"}}),
    ):
        with patch(
            "salt.channel.server.ReqServerChannel._auth",
            MagicMock(side_effect=OSError()),
        ):
            ret = await req.handle_message({"enc": "clear", "load": {}})
            assert ret == "Some exception handling minion payload"

    with patch(
        "salt.channel.server.ReqServerChannel._decode_payload",
        MagicMock(return_value={"enc": "clear", "load": {"cmd": "not_auth"}}),
    ):
        with patch(
            "salt.channel.server.ReqServerChannel.payload_handler",
            MagicMock(side_effect=OSError()),
            create=True,
        ):
            ret = await req.handle_message({"enc": "clear", "load": {}})
            assert ret == "Some exception handling minion payload"

    with patch(
        "salt.channel.server.ReqServerChannel._decode_payload",
        MagicMock(return_value={"enc": "clear", "load": {"cmd": "not_auth"}}),
    ):
        with patch(
            "salt.channel.server.ReqServerChannel.payload_handler",
            AsyncMock(return_value=(None, {"fun": "send"})),
            create=True,
        ):
            crypticle = MagicMock()
            with patch.object(req, "crypticle", crypticle, create=True):
                crypticle.dumps = MagicMock(side_effect=OSError())
                ret = await req.handle_message({"enc": "clear", "load": {}})
                assert ret == "Some exception handling minion payload"

    with patch(
        "salt.channel.server.ReqServerChannel._decode_payload",
        MagicMock(return_value={"enc": "clear", "load": {"cmd": "not_auth"}}),
    ):
        with patch(
            "salt.channel.server.ReqServerChannel.payload_handler",
            AsyncMock(
                return_value=(None, {"fun": "send_private", "key": None, "tgt": None})
            ),
            create=True,
        ):
            with patch.object(
                req, "_encrypt_private", MagicMock(side_effect=OSError()), create=True
            ):
                ret = await req.handle_message({"enc": "clear", "load": {}})
                assert ret == "Some exception handling minion payload"

    with patch(
        "salt.channel.server.ReqServerChannel._decode_payload",
        MagicMock(return_value={"enc": "clear", "load": {"cmd": "not_auth"}}),
    ):
        with patch(
            "salt.channel.server.ReqServerChannel.payload_handler",
            AsyncMock(return_value=(None, {"fun": "foobar", "key": None, "tgt": None})),
            create=True,
        ):
            with patch.object(
                req, "_encrypt_private", MagicMock(side_effect=OSError()), create=True
            ):
                ret = await req.handle_message({"enc": "clear", "load": {}})
                assert ret == "Server-side exception handling payload"
