import logging
import os

import pytest
import tornado.gen

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
        "keys.cache_driver": "localfs_key",
        "open_mode": False,
        "verify_master_pubkey_sign": False,
        "always_verify_signature": False,
    }
    crypt.write_keys(str(pki_dir), "minion", opts["keysize"])

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
        "keys.cache_driver": "localfs_key",
        "open_mode": False,
        "verify_master_pubkey_sign": False,
        "always_verify_signature": False,
    }
    crypt.write_keys(str(pki_dir), "minion", opts["keysize"])

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


@pytest.mark.skipif(
    not hasattr(crypt, "gen_signature"),
    reason=(
        "salt.crypt.gen_signature is a MasterKeys method on 3007.x. "
        "The refactored code path signs pub.public_bytes() from a key "
        "object rather than raw file content, so the #68930 whitespace-"
        "drift bug does not apply."
    ),
)
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


@pytest.mark.skipif(
    not hasattr(crypt, "gen_signature"),
    reason=(
        "salt.crypt.gen_signature is a MasterKeys method on 3007.x. "
        "The refactored code path signs pub.public_bytes() from a key "
        "object rather than raw file content, so the #68930 whitespace-"
        "drift bug does not apply."
    ),
)
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


async def test_authenticate_caps_retry_loop_with_auth_retries_69442(
    minion_root, io_loop
):
    """
    Regression test for https://github.com/saltstack/salt/issues/69442

    When ``sign_in()`` keeps returning ``"retry"`` (for example because the
    master has not yet accepted the minion key, the master AES key is in
    flux, or the master is reachable but rejecting auth), the outer
    ``AsyncAuth._authenticate()`` loop must bail out after ``auth_retries``
    attempts with a ``SaltClientError`` whose message names the attempt
    count.

    On 3006.x/3007.x the loop had no outer-attempts cap and the minion
    spun forever with exponential backoff up to ``acceptance_wait_time_max``
    with no operator-visible error log. This test asserts the
    backported cap: with ``auth_retries=3`` and ``sign_in`` returning
    ``"retry"`` on every call, the loop runs exactly 3 attempts and the
    future resolves to a ``SaltClientError`` carrying the
    ``"Failed to authenticate with the master after 3 attempts"`` message.
    """
    pki_dir = minion_root / "etc" / "salt" / "pki"
    opts = {
        "id": "minion",
        "__role": "minion",
        "pki_dir": str(pki_dir),
        "master_uri": "tcp://127.0.0.1:4505",
        "keysize": 4096,
        # Zero out the inter-attempt sleep so the test doesn't actually
        # wait ``acceptance_wait_time * attempts`` seconds before
        # observing the cap.
        "acceptance_wait_time": 0,
        "acceptance_wait_time_max": 0,
        "keys.cache_driver": "localfs_key",
        "auth_retries": 3,
    }
    crypt.write_keys(str(pki_dir), "minion", opts["keysize"])

    auth = crypt.AsyncAuth(opts, io_loop)

    call_count = 0

    @tornado.gen.coroutine
    def mock_sign_in(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return "retry"

    auth.sign_in = mock_sign_in

    with pytest.raises(salt.exceptions.SaltClientError) as exc_info:
        await auth.authenticate()

    assert call_count == 3
    assert "Failed to authenticate with the master after 3 attempts" in str(
        exc_info.value
    )


async def test_authenticate_default_does_not_cap_retry_loop_69442(minion_root, io_loop):
    """
    Regression test for https://github.com/saltstack/salt/issues/69442

    The outer ``AsyncAuth._authenticate()`` retry cap is opt-in on the
    3006.x LTS branch: the default ``auth_retries=0`` must preserve the
    pre-3006.26 behavior of retrying ``sign_in()`` forever when it keeps
    returning ``"retry"``.  Operators who upgrade without setting the
    new option should see no behavior change.

    This test drives the loop without ``auth_retries`` set (so the
    default applies) and asserts that the loop keeps calling ``sign_in``
    well past any small finite cap (the historical ``auth_tries``
    default of 7, the canonical ``master_tries`` default of 1, etc.).
    After ``call_limit`` ``"retry"`` returns the mock returns the
    distinct ``"bad enc algo"`` sentinel to break the otherwise-infinite
    loop cleanly via the existing ``elif`` branch.  The test passes if
    and only if the loop reached ``call_limit`` and the resulting error
    is the generic "Attempt to authenticate ... failed" message rather
    than the cap-specific "...after N attempts" message.
    """
    pki_dir = minion_root / "etc" / "salt" / "pki"
    opts = {
        "id": "minion",
        "__role": "minion",
        "pki_dir": str(pki_dir),
        "master_uri": "tcp://127.0.0.1:4505",
        "keysize": 4096,
        "acceptance_wait_time": 0,
        "acceptance_wait_time_max": 0,
        "keys.cache_driver": "localfs_key",
        # Intentionally do not set ``auth_retries`` -- the default
        # (0 == unlimited) is what we're asserting here.
    }
    crypt.write_keys(str(pki_dir), "minion", opts["keysize"])

    auth = crypt.AsyncAuth(opts, io_loop)

    # Sanity-check the default before driving the loop.
    assert auth.opts.get("auth_retries", 0) == 0

    call_count = 0
    # Comfortably past the historical ``auth_tries`` default of 7 and
    # any other plausible small cap a regression might introduce.
    call_limit = 25

    @tornado.gen.coroutine
    def mock_sign_in(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count >= call_limit:
            # Break the otherwise-infinite loop via the existing
            # ``"bad enc algo"`` sentinel branch in ``_authenticate``.
            return "bad enc algo"
        return "retry"

    auth.sign_in = mock_sign_in

    with pytest.raises(salt.exceptions.SaltClientError) as exc_info:
        await auth.authenticate()

    # The loop ran every plausible small finite cap's worth of attempts
    # without bailing out with the cap error, proving the default is
    # uncapped.
    assert call_count == call_limit
    assert "after" not in str(exc_info.value).lower() or "attempts" not in str(
        exc_info.value
    )
    assert "Attempt to authenticate with the salt master failed" in str(exc_info.value)
