import logging
import os

import pytest
import tornado.gen

import salt.crypt as crypt
import salt.exceptions
from tests.conftest import FIPS_TESTRUN
from tests.support.mock import mock_open, patch


def _fips_safe_sig_algorithm():
    return crypt.PKCS1v15_SHA224 if FIPS_TESTRUN else crypt.PKCS1v15_SHA1


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


async def test_authenticate_missing_creds_attribute_67947(minion_root, io_loop, caplog):
    """
    Regression test for https://github.com/saltstack/salt/issues/67947

    ``AsyncAuth.__singleton_init__`` only assigned ``self._creds`` when the
    minion's ``creds_map`` already contained the key for this auth instance.
    In the not-in-cache branch it fell through to ``self.authenticate()`` and
    left ``_creds`` unset.

    ``_authenticate`` then runs on the io_loop and checks ``if key not in
    AsyncAuth.creds_map:`` after the round-trip to the master. If a *sibling*
    ``AsyncAuth`` instance for the same key (same pki_dir + id + master_uri +
    key-mtime tuple) completed its own sign_in between our construction and
    our ``_authenticate`` running, ``creds_map`` now contains the key and the
    check goes into the ``else`` branch that dereferences ``self._creds``.
    That raises ``AttributeError: 'AsyncAuth' object has no attribute
    '_creds'`` on the reporter's Windows minion, aborts the authenticate
    coroutine, and silently disconnects the minion until manual restart.

    The fix initializes ``self._creds = None`` in the constructor (matching
    the sibling ``SAuth`` class) and updates the else-branch to treat
    ``self._creds is None`` as the first-time case rather than the
    key-changed case.
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
    }
    priv, pub = crypt.gen_keys(opts["keysize"])
    keypath = pki_dir / "minion"
    keypath.with_suffix(".pem").write_text(priv)
    keypath.with_suffix(".pub").write_text(pub)
    credskey = (
        opts["pki_dir"],
        opts["id"],
        opts["master_uri"],
        str(os.path.getmtime(os.path.join(opts["pki_dir"], "minion.pem"))),
    )

    # Make sure any leftover mapping from prior tests in this session does not
    # mask the bug: the constructor's short-circuit branch would otherwise set
    # ``_creds`` for us.
    crypt.AsyncAuth.creds_map.pop(credskey, None)

    auth = crypt.AsyncAuth(opts, io_loop)

    aes = crypt.Crypticle.generate_key_string()
    session = crypt.Crypticle.generate_key_string()

    async def mock_sign_in(*args, **kwargs):
        # Simulate a sibling ``AsyncAuth`` for the same key winning the race
        # and populating ``creds_map`` after our constructor ran but before
        # our ``_authenticate`` reaches the ``key not in creds_map`` check.
        crypt.AsyncAuth.creds_map[credskey] = {
            "aes": aes,
            "session": session,
        }
        return {"enc": "pub", "aes": aes, "session": session}

    auth.sign_in = mock_sign_in

    try:
        with caplog.at_level(logging.DEBUG):
            await auth.authenticate()
    finally:
        crypt.AsyncAuth.creds_map.pop(credskey, None)

    # Before the fix, ``_authenticate`` raised ``AttributeError: 'AsyncAuth'
    # object has no attribute '_creds'`` from the else branch that compared
    # ``self._creds["aes"]`` against the freshly signed-in creds. After the
    # fix, the constructor initializes ``_creds`` to ``None`` and the else
    # branch treats that as the first-authentication case.
    assert isinstance(auth._creds, dict)
    assert auth._creds["aes"] == aes
    assert auth._creds["session"] == session


async def test_authenticate_future_set_exception_guarded_against_double_set(
    minion_root, io_loop, caplog
):
    """
    Regression test for the ``InvalidStateError`` wedge described in
    ``agents/bugs/2026-11-01-asyncauth-invalid-state.md``.

    ``AsyncAuth._authenticate()`` finishes its retry loop by calling either
    ``_authenticate_future.set_exception(error)`` (failure branch at
    ``crypt.py:1449``) or ``_authenticate_future.set_result(True)``
    (success branch).  A stale coroutine racing against a sibling
    ``authenticate()`` call that already resolved the future (or against
    another instance of ``_authenticate()`` scheduled after
    ``invalidate()`` dropped the attribute) would hit a done future and
    raise ``asyncio.exceptions.InvalidStateError: invalid state`` out of
    the coroutine task, leaving the minion wedged in an un-authenticated
    state with no further auth attempts.

    This test simulates the race by pre-resolving
    ``_authenticate_future`` before the loop reaches ``set_exception``,
    then awaits the ``_authenticate`` task itself to observe its final
    exit state.  Before the guard, the task raises
    ``InvalidStateError`` from its tail; with the guard, the task
    completes cleanly and a subsequent ``authenticate()`` schedules a
    fresh retry task with a brand-new future.
    """
    import asyncio as _asyncio

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
    }
    priv, pub = crypt.gen_keys(opts["keysize"])
    keypath = pki_dir / "minion"
    keypath.with_suffix(".pem").write_text(priv)
    keypath.with_suffix(".pub").write_text(pub)
    credskey = (
        opts["pki_dir"],
        opts["id"],
        opts["master_uri"],
        str(os.path.getmtime(os.path.join(opts["pki_dir"], "minion.pem"))),
    )
    crypt.AsyncAuth.creds_map.pop(credskey, None)

    auth = crypt.AsyncAuth(opts, io_loop)

    # Capture the _authenticate task so we can inspect its final state
    # after authenticate() returns.  Without this, the task runs on the
    # same loop in the background and its unhandled InvalidStateError
    # would only surface as an "asyncio: Task exception was never
    # retrieved" warning on the stderr --- which is exactly the wedge
    # observed on the live minions but not detectable via pytest.raises
    # on the outer future.
    captured_task = {}
    original_create_task = auth.io_loop.create_task

    def tracked_create_task(coro):
        task = original_create_task(coro)
        captured_task["task"] = task
        return task

    auth.io_loop.create_task = tracked_create_task

    # Simulate the race: have ``sign_in`` resolve ``_authenticate_future``
    # from under the running coroutine before returning the
    # ``"bad enc algo"`` sentinel that routes the loop to the failure
    # branch at ``_authenticate()``'s tail.  Without the guard, the tail
    # call to ``set_exception`` would then raise ``InvalidStateError``.
    pre_resolve_error = salt.exceptions.SaltClientError(
        "pre-resolved by a sibling coroutine"
    )

    async def mock_sign_in(*args, **kwargs):
        if not auth._authenticate_future.done():
            auth._authenticate_future.set_exception(pre_resolve_error)
        return "bad enc algo"

    auth.sign_in = mock_sign_in

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(salt.exceptions.SaltClientError) as exc_info:
            await auth.authenticate()
        # The awaiter sees the pre-resolved exception --- the correct
        # user-facing behavior.
        assert exc_info.value is pre_resolve_error
        # Drain the _authenticate task: before the guard this re-raises
        # InvalidStateError; with the guard it completes cleanly.
        task = captured_task["task"]
        try:
            await task
        except _asyncio.InvalidStateError:
            pytest.fail(
                "AsyncAuth._authenticate raised InvalidStateError when "
                "its _authenticate_future was already resolved; the "
                "set_exception call at the tail of _authenticate must "
                "be guarded with ``if not done()`` so the coroutine does "
                "not die with an unhandled exception and wedge the "
                "minion in a non-authenticated state."
            )
        assert task.done()
        # The guard logs a DEBUG line when it drops the redundant set.
        assert any("already resolved" in rec.getMessage() for rec in caplog.records)

    assert auth._authenticate_future.done()

    # A subsequent ``authenticate()`` must be able to schedule a fresh
    # retry: the previous future is done, so ``authenticate()`` takes
    # the else-branch, allocates a new future, and schedules a new
    # ``_authenticate`` task.  This is the retry wiring that would be
    # dead if ``InvalidStateError`` had leaked out of the first attempt
    # as an "unhandled task exception".
    previous_future = auth._authenticate_future

    async def mock_sign_in_retry(*args, **kwargs):
        return "bad enc algo"

    auth.sign_in = mock_sign_in_retry
    with pytest.raises(salt.exceptions.SaltClientError):
        await auth.authenticate()

    assert auth._authenticate_future is not previous_future
    assert auth._authenticate_future.done()


# --- PublicKey / PrivateKey caching regression tests --------------------------


@pytest.fixture
def _clear_pub_key_cache():
    """
    Clear the module-level public-key cache before and after each test so
    tests can make hard assertions about cache membership and identity.
    """
    crypt._pub_key_cache.clear()
    crypt._pub_key_cache_path_index.clear()
    yield
    crypt._pub_key_cache.clear()
    crypt._pub_key_cache_path_index.clear()


@pytest.fixture
def _rsa_keypair(tmp_path):
    """
    Generate an RSA keypair once per test and write both halves to disk so
    tests exercise ``PublicKey.from_file`` / ``PrivateKey.from_file``.
    """
    priv_pem, pub_pem = crypt.gen_keys(2048)
    priv_path = tmp_path / "test.pem"
    pub_path = tmp_path / "test.pub"
    priv_path.write_text(priv_pem)
    pub_path.write_text(pub_pem)
    return {
        "priv_pem": priv_pem,
        "pub_pem": pub_pem,
        "priv_path": str(priv_path),
        "pub_path": str(pub_path),
    }


def _count_class_init(cls):
    """
    Return a context-manager-like helper that instruments ``cls.__init__`` to
    count the number of calls it receives.  Returns a ``dict`` whose ``count``
    key holds the running total; caller is responsible for restoring the
    original ``__init__`` when done.
    """
    counter = {"count": 0, "original": cls.__init__}

    def wrapper(self, *args, **kwargs):
        counter["count"] += 1
        return counter["original"](self, *args, **kwargs)

    cls.__init__ = wrapper
    return counter


def test_publickey_verifier_cached_across_decrypts(_rsa_keypair):
    """
    Repeated ``PublicKey.decrypt`` calls on a single instance must build the
    underlying ``RSAX931Verifier`` exactly once.  Pre-fix behavior was one
    verifier per decrypt() call.
    """
    import salt.utils.rsax931

    priv = crypt.PrivateKey.from_str(_rsa_keypair["priv_pem"])
    pub = crypt.PublicKey.from_str(_rsa_keypair["pub_pem"])
    signed = priv.encrypt(b"salt")

    counter = _count_class_init(salt.utils.rsax931.RSAX931Verifier)
    try:
        for _ in range(50):
            assert pub.decrypt(signed) == b"salt"
    finally:
        salt.utils.rsax931.RSAX931Verifier.__init__ = counter["original"]

    assert counter["count"] == 1, (
        "PublicKey.decrypt should reuse a single RSAX931Verifier per "
        f"instance; got {counter['count']} verifier constructions"
    )


def test_privatekey_signer_cached_across_encrypts(_rsa_keypair):
    """
    Repeated ``PrivateKey.encrypt`` calls on a single instance must build the
    underlying ``RSAX931Signer`` exactly once.  Pre-fix behavior was one
    signer per encrypt() call.
    """
    import salt.utils.rsax931

    priv = crypt.PrivateKey.from_str(_rsa_keypair["priv_pem"])

    counter = _count_class_init(salt.utils.rsax931.RSAX931Signer)
    try:
        for _ in range(50):
            priv.encrypt(b"salt")
    finally:
        salt.utils.rsax931.RSAX931Signer.__init__ = counter["original"]

    assert counter["count"] == 1, (
        "PrivateKey.encrypt should reuse a single RSAX931Signer per "
        f"instance; got {counter['count']} signer constructions"
    )


def test_pubkey_from_file_returns_cached_instance(_rsa_keypair, _clear_pub_key_cache):
    """
    ``PublicKey.from_file`` returns the *same* instance for repeated loads of
    the same on-disk file, so downstream libcrypto state (verifiers) is
    reused across the entire process.
    """
    first = crypt.PublicKey.from_file(_rsa_keypair["pub_path"])
    second = crypt.PublicKey.from_file(_rsa_keypair["pub_path"])
    assert first is second


def test_pubkey_from_file_mtime_evicts(_rsa_keypair, _clear_pub_key_cache):
    """
    A change to the file's mtime invalidates the cache entry and forces a
    fresh ``PublicKey`` instance on the next load.
    """
    pub_path = _rsa_keypair["pub_path"]
    first = crypt.PublicKey.from_file(pub_path)
    # Bump mtime one second into the future.  Using an explicit stamp avoids
    # relying on filesystem timestamp resolution.
    old_mtime = os.path.getmtime(pub_path)
    os.utime(pub_path, (old_mtime + 5, old_mtime + 5))
    second = crypt.PublicKey.from_file(pub_path)
    assert first is not second
    # Same key material -> same underlying cryptography public numbers.
    from cryptography.hazmat.primitives.asymmetric import rsa

    assert isinstance(first.key, rsa.RSAPublicKey)
    assert isinstance(second.key, rsa.RSAPublicKey)
    assert first.key.public_numbers() == second.key.public_numbers()


def test_verify_retries_after_rotation_without_mtime_bump(
    tmp_path, _clear_pub_key_cache
):
    """
    Simulate an on-disk key rotation that preserves mtime (cp -p / NFS mtime
    cache / atomic rename).  ``PublicKey.verify`` must detect the mismatch,
    evict the stale cache entry, and retry once with a freshly loaded key.
    """
    stale_priv_pem, stale_pub_pem = crypt.gen_keys(2048)
    fresh_priv_pem, fresh_pub_pem = crypt.gen_keys(2048)

    pub_path = tmp_path / "rotated.pub"
    pub_path.write_text(stale_pub_pem)
    mtime = os.path.getmtime(str(pub_path))

    # Warm the cache with the stale key.
    cached = crypt.PublicKey.from_file(str(pub_path))
    assert (str(pub_path), str(mtime)) in crypt._pub_key_cache

    # Rotate on disk without bumping mtime.  A signature produced by the
    # fresh key must NOT validate against the cached stale key on the first
    # try, but the retry-on-fail path reloads and succeeds.
    pub_path.write_text(fresh_pub_pem)
    os.utime(str(pub_path), (mtime, mtime))

    # Use a FIPS-compatible signing algorithm so this test exercises the
    # retry path under FIPS as well.  PKCS1v15-SHA1 (the pre-cache default)
    # is rejected at the salt boundary in FIPS mode.
    algorithm = _fips_safe_sig_algorithm()
    fresh_priv = crypt.PrivateKey.from_str(fresh_priv_pem)
    message = b"rotation-safety-check"
    signature = fresh_priv.sign(message, algorithm=algorithm)

    assert cached.verify(message, signature, algorithm=algorithm) is True
    # The retry evicts the stale entry and reinstalls a fresh instance for
    # the same (path, mtime) key.
    assert crypt._pub_key_cache[(str(pub_path), str(mtime))] is not cached


def test_decrypt_retries_after_rotation_without_mtime_bump(
    tmp_path, _clear_pub_key_cache
):
    """
    Mirror of the verify retry, but for ``PublicKey.decrypt`` which drives the
    X9.31 padding code path used by AsyncAuth.  A payload signed by the
    freshly rotated private key must decrypt successfully even though the
    cache initially holds the stale public key.
    """
    stale_priv_pem, stale_pub_pem = crypt.gen_keys(2048)
    fresh_priv_pem, fresh_pub_pem = crypt.gen_keys(2048)

    pub_path = tmp_path / "rotated.pub"
    pub_path.write_text(stale_pub_pem)
    mtime = os.path.getmtime(str(pub_path))

    cached = crypt.PublicKey.from_file(str(pub_path))

    pub_path.write_text(fresh_pub_pem)
    os.utime(str(pub_path), (mtime, mtime))

    fresh_priv = crypt.PrivateKey.from_str(fresh_priv_pem)
    signed = fresh_priv.encrypt(b"salt")

    assert cached.decrypt(signed) == b"salt"


def test_verify_genuine_bad_sig_returns_false_after_retry(
    _rsa_keypair, _clear_pub_key_cache
):
    """
    A genuinely invalid signature must still return ``False`` even though the
    retry-on-fail path will attempt to reload the key from disk.  The retry
    is bounded (one extra attempt) and never papers over real failures.
    """
    pub = crypt.PublicKey.from_file(_rsa_keypair["pub_path"])
    forged = b"\x00" * 256
    assert pub.verify(b"any message", forged) is False


def test_decrypt_genuine_bad_payload_raises_after_retry(
    _rsa_keypair, _clear_pub_key_cache
):
    """
    ``PublicKey.decrypt`` re-raises the underlying ``ValueError`` for genuine
    decryption failures after exactly one retry.  This preserves the
    pre-cache contract callers rely on.
    """
    pub = crypt.PublicKey.from_file(_rsa_keypair["pub_path"])
    with pytest.raises(ValueError):
        pub.decrypt(b"\x00" * 256)
