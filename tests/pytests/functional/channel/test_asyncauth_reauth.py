"""
Functional regression tests for AsyncAuth's forced re-auth contract
(saltstack/salt issue #70642 / PR #70772 review).

Scenario under test
-------------------
A caller hits :exc:`salt.crypt.AuthenticationError` because the master
rotated its AES key and the cached session key no longer decrypts.  The
caller then calls :meth:`AsyncAuth.authenticate` to force a fresh
sign-in while ``authenticated`` still reports True.  Other callers on
the same minion gate on the ``if not self.auth.authenticated: await
self.auth.authenticate()`` pattern in ``channel/client.py``; they must
observe ``authenticated=False`` for the duration of the forced re-auth
and join the in-flight sign-in task as waiters -- otherwise they skip
the gate, send with the stale key, hit their own
``AuthenticationError`` and bounce into a redundant re-auth
(one wasted master roundtrip per sibling).

These tests drive the contract against the real ZeroMQ transport, a
real :class:`ReqServerChannel` + :class:`AuthFuncs` on the master side,
and a real :class:`AsyncAuth` / :class:`AsyncReqChannel` on the minion
side -- no ``sign_in`` monkey-patching, no simulated
``AuthenticationError``.  The unit-test counterpart that uses a mocked
``sign_in`` lives at
``tests/pytests/unit/test_crypt.py::test_authenticate_forced_reauth_flips_authenticated_to_false``.
"""

import asyncio
import ctypes
import logging
import multiprocessing
import pathlib
import shutil

import pytest
import pytestshellutils.utils.ports

import salt.channel.client
import salt.channel.server
import salt.config
import salt.crypt
import salt.daemons.masterapi
import salt.exceptions
import salt.master
import salt.utils.event
import salt.utils.files
import salt.utils.platform
import salt.utils.process
import salt.utils.stringutils
from tests.conftest import FIPS_TESTRUN

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.skip_on_spawning_platform(
        reason=(
            "SMaster.secrets requires a fork-friendly multiprocessing.Array; "
            "the spawning platforms (Windows, macOS default) break the inline "
            "post_fork path used here."
        ),
    ),
    pytest.mark.timeout_unless_on_windows(120),
]


# ---- fixtures ---------------------------------------------------------------


@pytest.fixture
def reauth_minion_id():
    return "test-asyncauth-reauth-minion"


@pytest.fixture
def ret_port():
    return pytestshellutils.utils.ports.get_unused_localhost_port()


@pytest.fixture
def pki_root(tmp_path):
    """Create the PKI tree used by both master and minion."""
    if salt.utils.platform.is_darwin():
        # Avoid 'OSError: AF_UNIX path too long' on darwin.
        root = pathlib.Path("/tmp").resolve() / tmp_path.name
    else:
        root = tmp_path

    master_pki = root / "master_pki"
    minion_pki = root / "minion_pki"
    master_pki.mkdir(parents=True, exist_ok=True)
    minion_pki.mkdir(parents=True, exist_ok=True)
    (master_pki / "minions").mkdir(exist_ok=True)
    (master_pki / "minions_pre").mkdir(exist_ok=True)
    (master_pki / "minions_rejected").mkdir(exist_ok=True)
    (master_pki / "minions_denied").mkdir(exist_ok=True)
    (root / "sock").mkdir(exist_ok=True)
    (root / "cache").mkdir(exist_ok=True)
    (root / "cache" / "sessions").mkdir(exist_ok=True)
    (root / "extmods").mkdir(exist_ok=True)

    master_priv, master_pub = salt.crypt.gen_keys(4096)
    (master_pki / "master.pem").write_text(master_priv)
    (master_pki / "master.pub").write_text(master_pub)

    minion_priv, minion_pub = salt.crypt.gen_keys(4096)
    (minion_pki / "minion.pem").write_text(minion_priv)
    (minion_pki / "minion.pub").write_text(minion_pub)

    yield root

    if salt.utils.platform.is_darwin():
        shutil.rmtree(str(root), ignore_errors=True)


@pytest.fixture
def reauth_master_opts(pki_root, reauth_minion_id, ret_port):
    opts = salt.config.DEFAULT_MASTER_OPTS.copy()
    opts.update(
        {
            "master_uri": f"tcp://127.0.0.1:{ret_port}",
            "interface": "127.0.0.1",
            "ret_port": ret_port,
            "ipv6": False,
            "sock_dir": str(pki_root / "sock"),
            "cachedir": str(pki_root / "cache"),
            "pki_dir": str(pki_root / "master_pki"),
            "id": "master",
            "__role": "master",
            "transport": "zeromq",
            "keysize": 4096,
            "max_minions": 0,
            "auto_accept": True,
            "open_mode": False,
            "key_pass": None,
            "publish_port": ret_port + 1,
            "auth_mode": 1,
            # Auth events require an event bus; a plain filesystem one is fine.
            "auth_events": False,
            "publish_session": 86400,
            "request_server_ttl": 300,
            "worker_threads": 1,
            "worker_pools_enabled": False,
            # ``RequestRouter`` still runs inside the ``MWorkerQueue``
            # helper process even in non-pooled mode and validates the
            # worker_pools layout -- an empty one (the config default)
            # trips the "must have exactly one pool with catchall"
            # assertion.  Provide the stock single-pool layout.
            "worker_pools": {
                "default": {"worker_count": 1, "commands": ["*"]},
            },
            "cluster_id": None,
            "master_sign_pubkey": False,
            "sign_pub_messages": False,
            "minimum_auth_version": 0,
            "keys.cache_driver": "localfs_key",
            "extension_modules": str(pki_root / "extmods"),
            "file_roots": {"base": [str(pki_root / "file_roots")]},
            "pillar_roots": {"base": [str(pki_root / "pillar_roots")]},
            "con_cache": False,
            "pub_server_niceness": None,
            "zmq_monitor": False,
            "master_stats": False,
            "ping_on_rotate": False,
            "fips_mode": FIPS_TESTRUN,
            "publish_signing_algorithm": (
                "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
            ),
        }
    )
    # Pre-accept the minion key.
    minion_pub = pki_root / "minion_pki" / "minion.pub"
    master_minions = pki_root / "master_pki" / "minions" / reauth_minion_id
    if minion_pub.exists():
        master_minions.write_text(minion_pub.read_text())
    return opts


@pytest.fixture
def reauth_minion_opts(pki_root, reauth_master_opts, reauth_minion_id, ret_port):
    return {
        "master_uri": f"tcp://127.0.0.1:{ret_port}",
        "interface": "127.0.0.1",
        "ret_port": ret_port,
        "ipv6": False,
        "sock_dir": reauth_master_opts["sock_dir"],
        "pki_dir": str(pki_root / "minion_pki"),
        "cachedir": str(pki_root / "cache"),
        "id": reauth_minion_id,
        "__role": "minion",
        "transport": "zeromq",
        "keysize": 4096,
        "encryption_algorithm": ("OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1"),
        "signing_algorithm": ("PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"),
        "fips_mode": FIPS_TESTRUN,
        "master_port": ret_port,
        "master_ip": "127.0.0.1",
        "verify_master_pubkey_sign": False,
        "always_verify_signature": False,
        "master_sign_key_name": "master_sign",
        "master_finger": "",
        "syndic_finger": "",
        "acceptance_wait_time": 0,
        "acceptance_wait_time_max": 0,
        "auth_timeout": 10,
        "auth_tries": 1,
        "auth_safemode": False,
        "auth_events": False,
        "keys.cache_driver": "localfs_key",
        "detect_mode": False,
        "minion_sign_messages": False,
        "request_channel_timeout": 10,
        "request_channel_tries": 1,
        "open_mode": False,
        "rejected_retry": False,
    }


@pytest.fixture
def smaster_secrets():
    """
    Install a real ``SMaster.secrets['aes']`` keyed by a
    ``multiprocessing.Array`` so the master worker sees the parent's
    rotations and the minion/master share a key.
    """
    old = salt.master.SMaster.secrets.pop("aes", None)
    salt.master.SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        ),
        "serial": multiprocessing.Value(ctypes.c_longlong, lock=False),
        "reload": salt.crypt.Crypticle.generate_key_string,
    }
    try:
        yield salt.master.SMaster.secrets["aes"]
    finally:
        salt.master.SMaster.secrets.pop("aes", None)
        if old is not None:
            salt.master.SMaster.secrets["aes"] = old


class _Server:
    """Container for the server plumbing so tests can inspect state."""

    def __init__(self):
        self.channel = None
        self.process_manager = None
        # ``auth_received`` ticks the moment the ``_auth`` payload
        # arrives on the master side (before the optional gate).
        # ``auth_count`` ticks when ``AuthFuncs._auth`` actually runs
        # (after the gate releases).
        self.auth_received = 0
        self.auth_count = 0
        self.auth_gate = None  # optional asyncio.Event


@pytest.fixture
def req_server(reauth_master_opts, smaster_secrets, io_loop):
    """
    Spin up a real non-pooled ``ReqServerChannel`` bound to a real
    ZeroMQ ROUTER on ``ret_port``.  The MWorkerQueue device runs in a
    forked helper process (via ``ProcessManager``) and the REP-side
    worker runs inline on ``io_loop`` -- so the test can observe and
    instrument the handler.
    """
    import tornado.ioloop

    tornado.ioloop.IOLoop.current(instance=True)
    server = _Server()

    # pre_fork spawns the zmq_device helper process.
    server.process_manager = salt.utils.process.ProcessManager(
        name="asyncauth-reauth-PM"
    )
    channel = salt.channel.server.ReqServerChannel.factory(reauth_master_opts)
    channel.pre_fork(server.process_manager)
    channel.post_fork(_noop_payload_handler, io_loop=io_loop)

    # Instrument ``_auth`` on the channel so tests can count forced
    # re-auth roundtrips and (optionally) await a gate before replying.
    orig_auth = channel._auth

    def counting_auth(load, sign_messages=False, version=0):
        server.auth_count += 1
        return orig_auth(load, sign_messages, version)

    channel._auth = counting_auth

    # Wrap the whole ``handle_message`` to inject an async gate around
    # ``_auth`` calls; this lets tests observe mid-flight state.
    orig_handle = channel.handle_message

    async def gated_handle_message(payload):
        is_auth = (
            isinstance(payload, dict)
            and payload.get("enc") == "clear"
            and isinstance(payload.get("load"), dict)
            and payload["load"].get("cmd") == "_auth"
        )
        if is_auth:
            server.auth_received += 1
            if server.auth_gate is not None:
                await server.auth_gate.wait()
        return await orig_handle(payload)

    channel.handle_message = gated_handle_message
    # The transport already captured the original ``handle_message`` as
    # its ``message_handler`` inside ``post_fork``.  Replace that too so
    # the gate actually runs.
    channel.transport.message_handler = gated_handle_message

    server.channel = channel
    try:
        yield server
    finally:
        try:
            channel.close()
        except Exception:  # pylint: disable=broad-except
            pass
        try:
            server.process_manager.terminate()
        except Exception:  # pylint: disable=broad-except
            pass


async def _noop_payload_handler(payload):
    """
    Payload handler used for non-``_auth`` requests.  Echoes the load
    back inside a crypted response so a successful ``AsyncReqChannel``
    send returns.  ``_auth`` requests never reach this handler -- they
    are short-circuited inside ``ReqServerChannel.handle_message``.
    """
    return payload, {"fun": "send"}


async def _wait_for_master_ready(minion_opts, deadline=10.0):
    """
    Spin a sign-in with a fresh ``AsyncAuth`` until the master is
    reachable and auto-accept has completed.  Returns the authenticated
    ``AsyncAuth``.  The MWorkerQueue device can take a moment to bind
    after pre_fork.
    """
    import tornado.ioloop

    io_loop = tornado.ioloop.IOLoop.current()
    start = asyncio.get_event_loop().time()
    last_exc = None
    while asyncio.get_event_loop().time() - start < deadline:
        auth = salt.crypt.AsyncAuth(minion_opts, io_loop=io_loop)
        try:
            ok = await auth.authenticate()
            if ok is True and auth.authenticated:
                return auth
        except Exception as exc:  # pylint: disable=broad-except
            last_exc = exc
            log.debug("auth not ready yet: %s", exc)
        # Clear any cached failure state and retry.
        salt.crypt.AsyncAuth.creds_map.pop(
            salt.crypt._auth_singleton_key(minion_opts), None
        )
        await asyncio.sleep(0.2)
    raise AssertionError(
        f"master never became auth-ready within {deadline}s; last exc={last_exc!r}"
    )


# ---- tests ------------------------------------------------------------------


async def test_rotated_master_aes_triggers_real_authentication_error(
    reauth_minion_opts, req_server, io_loop, smaster_secrets
):
    """
    Property (1): a real crypted roundtrip against a stale AES key must
    raise :class:`salt.crypt.AuthenticationError` on the client when
    the auto-retry inside ``_crypted_transfer`` is bypassed.

    We drive this by signing in once (populating ``creds_map`` with the
    master's current ``aes``/``session``), then overwriting the
    minion-side cached ``session`` key with a stale value.  The next
    low-level ``_do_transfer`` call encrypts with the stale key, the
    master fails to decrypt in ``_decode_payload`` (v3 path uses the
    per-minion session key cache that still holds the original value),
    and the master returns the literal string ``"bad load"``.  The
    minion's reply-decrypt then raises ``AuthenticationError`` on HMAC
    verification.
    """
    auth = await _wait_for_master_ready(reauth_minion_opts)
    assert auth.authenticated

    channel = salt.channel.client.AsyncReqChannel.factory(
        reauth_minion_opts, io_loop=io_loop, crypt="aes"
    )
    try:
        # Baseline: a crypted send round-trips cleanly.
        resp = await channel.send({"cmd": "_test_ok"}, timeout=5, tries=1)
        assert isinstance(resp, dict)

        # Now stash a stale session key on the minion side.  The master
        # still has the original in ``server.sessions[minion]`` so the
        # mismatch forces a decrypt failure on the master, which returns
        # ``"bad load"`` -- and the minion's attempt to decrypt that
        # literal via ``session_crypticle.loads`` raises
        # ``AuthenticationError`` on HMAC verify.
        stale = salt.crypt.Crypticle.generate_key_string()
        auth._session_crypticle = salt.crypt.Crypticle(auth.opts, stale)

        # Drive the inner ``_do_transfer`` directly so the retry wrapper
        # inside ``_crypted_transfer`` does not swallow the first
        # ``AuthenticationError``.  We assert the raw contract that a
        # stale key produces that exception on the real stack.
        import uuid

        nonce = uuid.uuid4().hex
        packaged = channel._package_load(
            {"cmd": "_test_stale"}, nonce, session_crypticle=auth.session_crypticle
        )
        data = await channel.transport.send(packaged, timeout=5)
        assert data, "master should return a (bad load) payload"
        with pytest.raises(salt.exceptions.AuthenticationError):
            auth.session_crypticle.loads(data, False, nonce=nonce)
    finally:
        channel.close()


async def test_forced_reauth_flips_authenticated_to_false_mid_flight(
    reauth_minion_opts, req_server, io_loop, smaster_secrets
):
    """
    Property (2): while a forced re-auth is in flight,
    ``auth.authenticated`` must be False, ``auth._last_result`` must be
    None, and ``auth._sign_in_task`` must be a pending task.  After
    completion ``authenticated`` flips back to True, ``_last_result`` is
    ``(True,)``, and ``creds_map`` holds the newly-rotated AES key.
    """
    auth = await _wait_for_master_ready(reauth_minion_opts)
    assert auth.authenticated
    assert auth._last_result == (True,)
    aes_old = auth._creds["aes"]
    credskey = salt.crypt._auth_singleton_key(reauth_minion_opts)
    assert salt.master.SMaster.secrets["aes"]["secret"].value.decode() == aes_old

    # Rotate the master's AES key.  A fresh sign-in now must return a
    # different ``aes`` than ``aes_old``.
    salt.master.SMaster.rotate_secrets(
        master_opts_for_rotation(req_server), use_lock=True
    )
    aes_rotated = salt.master.SMaster.secrets["aes"]["secret"].value.decode()
    assert aes_rotated != aes_old

    # Reset counters after the warm-up sign-in and gate the master's
    # ``_auth`` so we can observe the intermediate state.
    req_server.auth_received = 0
    req_server.auth_count = 0
    req_server.auth_gate = asyncio.Event()

    try:
        forced = auth.authenticate()
        # Yield once so ``authenticate`` attaches the waiter, spawns
        # ``_sign_in_task``, and starts awaiting the (gated) sign-in.
        for _ in range(20):
            await asyncio.sleep(0)
            if (
                auth._sign_in_task is not None
                and not auth._sign_in_task.done()
                and auth._last_result is None
            ):
                break
        # Drive the task until it actually reaches the gate on the
        # master side (the ``_auth`` reply), not just sitting pre-send.
        # Spin for a short while waiting for the gate to see the
        # ``_auth`` payload arrive on the master.
        start = asyncio.get_event_loop().time()
        while (
            req_server.auth_received == 0
            and asyncio.get_event_loop().time() - start < 5
        ):
            await asyncio.sleep(0.05)
        assert req_server.auth_received >= 1
        # The ``_auth`` handler itself is parked on the gate, so
        # ``auth_count`` is still 0 until we release.
        assert req_server.auth_count == 0

        assert auth._sign_in_task is not None, "forced re-auth should spawn a task"
        assert (
            not auth._sign_in_task.done()
        ), "task must still be pending while master is gated"
        assert (
            auth._last_result is None
        ), "_last_result must be cleared while re-auth is in flight"
        assert auth.authenticated is False, (
            "authenticated must be False mid-flight so sibling callers "
            "wait on the new sign-in instead of sending with the stale key"
        )

        # Release the gate -- the sign-in completes, ``authenticated``
        # goes back to True, and ``creds_map`` holds the NEW aes.
        req_server.auth_gate.set()
        ok = await asyncio.wait_for(forced, timeout=10)
        assert ok is True
        assert auth.authenticated
        assert auth._last_result == (True,)
        assert salt.crypt.AsyncAuth.creds_map[credskey]["aes"] == aes_rotated
        assert salt.crypt.AsyncAuth.creds_map[credskey]["aes"] != aes_old
    finally:
        req_server.auth_gate = None


async def test_sibling_waits_on_in_flight_forced_reauth(
    reauth_minion_opts, req_server, io_loop, smaster_secrets
):
    """
    Property (3): a sibling caller arriving during the forced re-auth
    window must observe ``authenticated=False``, join the in-flight
    sign-in as a waiter (not spawn a second task), and both callers
    must resolve to True from the single master roundtrip.
    """
    auth = await _wait_for_master_ready(reauth_minion_opts)
    assert auth.authenticated

    salt.master.SMaster.rotate_secrets(
        master_opts_for_rotation(req_server), use_lock=True
    )
    # Reset master-side counters after the warm-up sign-in.
    req_server.auth_received = 0
    req_server.auth_count = 0
    req_server.auth_gate = asyncio.Event()

    try:
        forced = auth.authenticate()
        # Spin until the gated _auth payload is actually received on
        # the master side (the handler is parked on the gate).
        start = asyncio.get_event_loop().time()
        while (
            req_server.auth_received == 0
            and asyncio.get_event_loop().time() - start < 5
        ):
            await asyncio.sleep(0.05)
        assert (
            req_server.auth_received == 1
        ), "forced re-auth should drive exactly one master _auth roundtrip"

        assert auth.authenticated is False
        # Sibling arrives now and must observe ``authenticated=False``,
        # join the in-flight sign-in task as a waiter, and not spawn a
        # second master roundtrip.  ``authenticate()`` returns a
        # tornado/asyncio Future directly, not a coroutine.
        sibling = auth.authenticate()
        for _ in range(20):
            await asyncio.sleep(0)
            if len(auth._waiters) >= 2:
                break
        assert (
            len(auth._waiters) >= 2
        ), "sibling must register as a waiter on the in-flight sign-in"
        # Give any racing spawn a moment to show up.
        await asyncio.sleep(0.2)
        assert req_server.auth_received == 1, (
            "sibling must join the in-flight sign-in, not drive a second "
            "master roundtrip"
        )

        req_server.auth_gate.set()
        results = await asyncio.wait_for(asyncio.gather(forced, sibling), timeout=10)
        assert results == [True, True]
        assert (
            req_server.auth_received == 1
        ), "after completion still exactly one roundtrip serviced both callers"
        assert (
            req_server.auth_count == 1
        ), "exactly one AuthFuncs._auth call ran for both callers"
        assert auth.authenticated
        assert auth._last_result == (True,)
    finally:
        req_server.auth_gate = None


# ---- helpers ----------------------------------------------------------------


def master_opts_for_rotation(req_server):
    """
    ``rotate_secrets`` reads a handful of keys off ``opts`` to decide
    whether to fire a ping / event.  Use the live channel's opts to
    keep behavior consistent.
    """
    return req_server.channel.opts
