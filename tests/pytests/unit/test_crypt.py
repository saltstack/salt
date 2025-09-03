import os

import pytest

import salt.crypt as crypt
from tests.support.mock import patch


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


@pytest.fixture
def minion_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "etc").mkdir()
    (root / "etc" / "salt").mkdir()
    (root / "etc" / "salt" / "pki").mkdir()
    yield root


@pytest.mark.parametrize("linesep", ["\r\n", "\r", "\n"])
def test__clean_key(key_data, linesep):
    tst_key = linesep.join(key_data)
    chk_key = "\n".join(key_data)
    assert crypt.clean_key(tst_key) == crypt.clean_key(chk_key)


@pytest.mark.parametrize("linesep", ["\r\n", "\r", "\n"])
def test__clean_key_mismatch(key_data, linesep):
    tst_key = linesep.join(key_data)
    tst_key = tst_key.replace("5", "4")
    chk_key = "\n".join(key_data)
    assert crypt.clean_key(tst_key) != crypt.clean_key(chk_key)


async def test_auth_aes_key_rotation(minion_root, io_loop):
    pki_dir = minion_root / "etc" / "salt" / "pki"
    os.makedirs(str(pki_dir), exist_ok=True)
    opts = {
        "id": "minion",
        "__role": "minion",
        "pki_dir": str(pki_dir),
        "master_uri": "tcp://127.0.0.1:4505",
        "keysize": 4096,
        "acceptance_wait_time": 60,
        "keys.cache_driver": "localfs_key",
        "acceptance_wait_time_max": 60,
    }
    priv, pub = crypt.gen_keys(opts["keysize"])
    keypath = pki_dir / "minion"
    keypath.with_suffix(".pem").write_text(priv)
    keypath.with_suffix(".pub").write_text(pub)
    credskey = (
        opts["pki_dir"],  # where the keys are stored
        opts["id"],  # minion ID
        opts["master_uri"],  # master ID
        str(os.path.getmtime(os.path.join(opts["pki_dir"], "minion.pem"))),
    )
    aes = crypt.Crypticle.generate_key_string()
    session = crypt.Crypticle.generate_key_string()

    auth = crypt.AsyncAuth(opts, io_loop)

    async def mock_sign_in(*args, **kwargs):
        return mock_sign_in.response

    mock_sign_in.response = {
        "enc": "pub",
        "aes": aes,
        "session": session,
    }
    auth.sign_in = mock_sign_in

    assert credskey not in auth.creds_map

    await auth.authenticate()

    assert credskey in auth.creds_map
    assert auth.creds_map[credskey]["aes"] == aes
    assert auth.creds_map[credskey]["session"] == session

    aes1 = crypt.Crypticle.generate_key_string()

    mock_sign_in.response = {
        "enc": "pub",
        "aes": aes1,
        "session": session,
    }

    await auth.authenticate()

    assert credskey in auth.creds_map
    assert auth.creds_map[credskey]["aes"] == aes1
    assert auth.creds_map[credskey]["session"] == session

    session1 = crypt.Crypticle.generate_key_string()
    mock_sign_in.response = {
        "enc": "pub",
        "aes": aes1,
        "session": session1,
    }

    await auth.authenticate()

    assert credskey in auth.creds_map
    assert auth.creds_map[credskey]["aes"] == aes1
    assert auth.creds_map[credskey]["session"] == session1


def test_sauth_aes_key_rotation(minion_root, io_loop):

    pki_dir = minion_root / "etc" / "salt" / "pki"
    opts = {
        "id": "minion",
        "__role": "minion",
        "pki_dir": str(pki_dir),
        "master_uri": "tcp://127.0.0.1:4505",
        "keysize": 4096,
        "acceptance_wait_time": 60,
        "acceptance_wait_time_max": 60,
        "keys.cache_driver": "localfs_key",
    }
    credskey = (
        opts["pki_dir"],  # where the keys are stored
        opts["id"],  # minion ID
        opts["master_uri"],  # master ID
    )
    priv, pub = crypt.gen_keys(opts["keysize"])
    keypath = pki_dir / "minion"
    keypath.with_suffix(".pem").write_text(priv)
    keypath.with_suffix(".pub").write_text(pub)

    aes = crypt.Crypticle.generate_key_string()
    session = crypt.Crypticle.generate_key_string()

    auth = crypt.SAuth(opts, io_loop)

    def mock_sign_in(*args, **kwargs):
        return mock_sign_in.response

    mock_sign_in.response = {
        "enc": "pub",
        "aes": aes,
        "session": session,
    }
    auth.sign_in = mock_sign_in

    assert auth._creds is None

    auth.authenticate()

    assert isinstance(auth._creds, dict)
    assert auth._creds["aes"] == aes
    assert auth._creds["session"] == session

    aes1 = crypt.Crypticle.generate_key_string()

    mock_sign_in.response = {
        "enc": "pub",
        "aes": aes1,
        "session": session,
    }

    auth.authenticate()

    assert isinstance(auth._creds, dict)
    assert auth._creds["aes"] == aes1
    assert auth._creds["session"] == session

    session1 = crypt.Crypticle.generate_key_string()
    mock_sign_in.response = {
        "enc": "pub",
        "aes": aes1,
        "session": session1,
    }

    auth.authenticate()

    assert isinstance(auth._creds, dict)
    assert auth._creds["aes"] == aes1
    assert auth._creds["session"] == session1


def test_async_auth_cache_private_key(minion_root, io_loop):
    pki_dir = minion_root / "etc" / "salt" / "pki"
    cache_dir = minion_root / "var" / "salt" / "cache"
    os.makedirs(str(cache_dir), exist_ok=True)
    opts = {
        "id": "minion",
        "__role": "minion",
        "pki_dir": str(pki_dir),
        "master_uri": "tcp://127.0.0.1:4505",
        "keysize": 4096,
        "acceptance_wait_time": 60,
        "acceptance_wait_time_max": 60,
        "keys.cache_driver": "localfs_key",
        "cache_dir": str(cache_dir),
        "optimization_order": [0, 1, 2],
        "permissive_pki_access": True,
    }

    auth = crypt.AsyncAuth(opts, io_loop)

    # The private key is cached.
    assert isinstance(auth._private_key, crypt.PrivateKey)

    # get_keys returns the cached instance
    _id = id(auth._private_key)
    assert _id == id(auth.get_keys())


def test_async_auth_cache_token(minion_root, io_loop):
    pki_dir = minion_root / "etc" / "salt" / "pki"
    cache_dir = minion_root / "var" / "salt" / "cache"
    os.makedirs(str(cache_dir), exist_ok=True)
    opts = {
        "id": "minion",
        "__role": "minion",
        "pki_dir": str(pki_dir),
        "master_uri": "tcp://127.0.0.1:4505",
        "keysize": 4096,
        "acceptance_wait_time": 60,
        "acceptance_wait_time_max": 60,
        "keys.cache_driver": "localfs_key",
        "cache_dir": str(cache_dir),
        "optimization_order": [0, 1, 2],
        "permissive_pki_access": True,
    }

    auth = crypt.AsyncAuth(opts, io_loop)

    with patch("salt.crypt.PrivateKey.encrypt") as moc:
        auth.gen_token("salt")
        auth.gen_token("salt")
        moc.assert_called_once()
