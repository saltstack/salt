import logging
import os

import pytest

import salt.crypt as crypt
import salt.exceptions
from tests.support.mock import mock_open, patch


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


async def test_auth_aes_key_rotation(minion_root, io_loop, caplog):
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

    with caplog.at_level(logging.DEBUG):
        await auth.authenticate()

    assert "Got new master aes key" in caplog.text
    assert credskey in auth.creds_map
    assert auth.creds_map[credskey]["aes"] == aes
    assert auth.creds_map[credskey]["session"] == session

    aes1 = crypt.Crypticle.generate_key_string()

    mock_sign_in.response = {
        "enc": "pub",
        "aes": aes1,
        "session": session,
    }

    with caplog.at_level(logging.DEBUG):
        await auth.authenticate()

    assert "The master's aes key has changed" in caplog.text
    assert credskey in auth.creds_map
    assert auth.creds_map[credskey]["aes"] == aes1
    assert auth.creds_map[credskey]["session"] == session

    session1 = crypt.Crypticle.generate_key_string()
    mock_sign_in.response = {
        "enc": "pub",
        "aes": aes1,
        "session": session1,
    }

    with caplog.at_level(logging.DEBUG):
        await auth.authenticate()

    assert "The master's session key has changed" in caplog.text
    assert credskey in auth.creds_map
    assert auth.creds_map[credskey]["aes"] == aes1
    assert auth.creds_map[credskey]["session"] == session1


def test_sauth_aes_key_rotation(minion_root, io_loop, caplog):

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

    with caplog.at_level(logging.DEBUG):
        auth.authenticate()

    assert "Got new master aes key" in caplog.text
    assert isinstance(auth._creds, dict)
    assert auth._creds["aes"] == aes
    assert auth._creds["session"] == session

    aes1 = crypt.Crypticle.generate_key_string()

    mock_sign_in.response = {
        "enc": "pub",
        "aes": aes1,
        "session": session,
    }

    with caplog.at_level(logging.DEBUG):
        auth.authenticate()

    assert "The master's aes key has changed" in caplog.text
    assert isinstance(auth._creds, dict)
    assert auth._creds["aes"] == aes1
    assert auth._creds["session"] == session

    session1 = crypt.Crypticle.generate_key_string()
    mock_sign_in.response = {
        "enc": "pub",
        "aes": aes1,
        "session": session1,
    }

    with caplog.at_level(logging.DEBUG):
        auth.authenticate()

    assert "The master's session key has changed" in caplog.text
    assert isinstance(auth._creds, dict)
    assert auth._creds["aes"] == aes1
    assert auth._creds["session"] == session1


def test_get_key_with_evict_bad_key(tmp_path):
    key_path = tmp_path / "key"
    key_path.write_text("asdfasoiasdofaoiu0923jnoiausbd98sb9")
    with pytest.raises(salt.exceptions.InvalidKeyError):
        crypt._get_key_with_evict(str(key_path), 1, None)


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


def test_verify_master_accepts_cached_key_with_whitespace_drift(
    minion_root, io_loop, key_data
):
    """
    Regression test for https://github.com/saltstack/salt/issues/68493

    A master that does not ``clean_key()`` its outgoing ``pub_key`` (e.g. an
    older 3006.0 master) sends a payload whose ``pub_key`` carries a trailing
    newline. ``verify_master`` writes that raw payload to ``minion_master.pub``
    on first contact, but on every subsequent restart it reads the cached file
    through ``clean_key()`` (which strips trailing whitespace) and then
    compares the normalized cache against the raw payload. The two strings
    only differ in trailing whitespace, but the comparison fails and the
    minion rejects the master with "Invalid master key" forever (until the
    cache file is deleted).

    The fix normalizes both sides of the comparison through ``clean_key()``.
    """
    pki_dir = minion_root / "etc" / "salt" / "pki"
    opts = {
        "id": "minion",
        "__role": "minion",
        "pki_dir": str(pki_dir),
        "master_uri": "tcp://127.0.0.1:4505",
        "keysize": 4096,
        "acceptance_wait_time": 60,
        "acceptance_wait_time_max": 60,
        "open_mode": False,
        "verify_master_pubkey_sign": False,
        "always_verify_signature": False,
    }
    crypt.gen_keys(pki_dir, "minion", opts["keysize"])

    auth = crypt.AsyncAuth(opts, io_loop)

    raw_pub_key = "\n".join(key_data) + "\n"
    cached_pub_key = crypt.clean_key(raw_pub_key)
    assert raw_pub_key != cached_pub_key, "fixture must exercise the drift"

    # Simulate the on-disk cache that the minion would build up after talking
    # to a master whose outgoing pub_key has been normalized by clean_key().
    m_pub_fn = pki_dir / auth.mpub
    m_pub_fn.write_text(cached_pub_key)

    payload = {
        "enc": "pub",
        "pub_key": raw_pub_key,
        "aes": "ignored-by-extract-aes-mock",
    }

    with patch.object(auth, "extract_aes", return_value="aes-key") as extract:
        result = auth.verify_master(payload)

    assert result == "aes-key"
    extract.assert_called_once()


def test_verify_master_caches_clean_key_on_first_contact(
    minion_root, io_loop, key_data
):
    """
    Regression test for https://github.com/saltstack/salt/issues/68493

    When ``verify_master`` accepts a master's pub_key for the first time it
    must cache the ``clean_key()``-normalized form to ``minion_master.pub``.
    Caching the raw payload causes the next call (which reads through
    ``clean_key()``) to compare a normalized cache against a raw payload and
    spuriously reject the master.
    """
    pki_dir = minion_root / "etc" / "salt" / "pki"
    opts = {
        "id": "minion",
        "__role": "minion",
        "pki_dir": str(pki_dir),
        "master_uri": "tcp://127.0.0.1:4505",
        "keysize": 4096,
        "acceptance_wait_time": 60,
        "acceptance_wait_time_max": 60,
        "open_mode": False,
        "verify_master_pubkey_sign": False,
        "always_verify_signature": False,
    }
    crypt.gen_keys(pki_dir, "minion", opts["keysize"])

    auth = crypt.AsyncAuth(opts, io_loop)

    raw_pub_key = "\n".join(key_data) + "\n"
    cached_pub_key = crypt.clean_key(raw_pub_key)

    m_pub_fn = pki_dir / auth.mpub
    assert not m_pub_fn.exists()

    payload = {
        "enc": "pub",
        "pub_key": raw_pub_key,
        "aes": "ignored-by-extract-aes-mock",
    }

    with patch.object(auth, "extract_aes", return_value="aes-key"):
        # First contact: master_pub=False because the minion hadn't seen a
        # pubkey yet when it sent the auth request.
        result = auth.verify_master(payload, master_pub=False)

    assert result == "aes-key"
    assert m_pub_fn.read_text() == cached_pub_key


@pytest.mark.parametrize("linesep", ["\r\n", "\r", "\n"])
def test_gen_signature_signs_clean_key(key_data, linesep):
    """
    Regression test for https://github.com/saltstack/salt/issues/68930

    gen_signature() must apply clean_key() before signing so the signed
    content matches what get_pub_str() sends to minions.
    """
    raw_pub_on_disk = linesep.join(key_data)
    expected = crypt.clean_key(raw_pub_on_disk)

    with (
        patch("salt.utils.files.fopen", mock_open(read_data=raw_pub_on_disk)),
        patch("os.path.isfile", return_value=False),
        patch("salt.crypt.sign_message", return_value=b"fakesig") as mock_sign,
    ):
        crypt.gen_signature("priv_path", "pub_path", "sig_path")

    _, signed_content, _ = mock_sign.call_args[0]
    assert signed_content == expected


@pytest.mark.parametrize("linesep", ["\r\n", "\r", "\n"])
def test_gen_signature_signs_clean_key_trailing_newline(key_data, linesep):
    """
    Same as above but with a trailing newline, which is the common case
    because the cryptography library writes PEM files with one.
    """
    raw_pub_on_disk = linesep.join(key_data) + linesep
    expected = crypt.clean_key(raw_pub_on_disk)

    assert raw_pub_on_disk != expected

    with (
        patch("salt.utils.files.fopen", mock_open(read_data=raw_pub_on_disk)),
        patch("os.path.isfile", return_value=False),
        patch("salt.crypt.sign_message", return_value=b"fakesig") as mock_sign,
    ):
        crypt.gen_signature("priv_path", "pub_path", "sig_path")

    _, signed_content, _ = mock_sign.call_args[0]
    assert signed_content == expected
