"""
Functional tests for :class:`salt.crypt.AsyncAuth` concurrency semantics.

These tests exercise the real zmq transport + real
:class:`salt.channel.server.ReqServerChannel` + real
:meth:`salt.crypt.AsyncAuth.sign_in` path.  No ``sign_in`` monkey-patching,
no ``asyncio.Event`` gating -- the goal is to prove the per-caller-future
contract (issue #70642) under honest timing against the honest wire format.

The three properties under test:

1. Distinct per-caller Futures, but exactly one master-side AUTH roundtrip
   for N concurrent waiters against a cold ``creds_map``.
2. No ``asyncio.exceptions.InvalidStateError`` under burst load even when
   the master-side AUTH handler is artificially slowed.
3. Exceptions in the sign-in task fan out to every registered waiter
   (previously, an ``OSError`` or other unexpected exception escaped as an
   unhandled task exception and left waiters hanging).
"""

import asyncio
import ctypes
import logging
import multiprocessing
import os
import pathlib
import shutil

import pytest
from saltfactories.utils import random_string

import salt.channel.server
import salt.config
import salt.crypt
import salt.master
import salt.transport.base
import salt.utils.platform
import salt.utils.process
import salt.utils.stringutils
from tests.conftest import FIPS_TESTRUN

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.skip_on_spawning_platform(
        reason="These tests are currently broken on spawning platforms. Need to be rewritten.",
    ),
    pytest.mark.timeout_unless_on_windows(120),
]


@pytest.fixture
def channel_minion_id():
    return random_string("concurrent-auth-minion-")


@pytest.fixture
def root_dir(tmp_path):
    if salt.utils.platform.is_darwin():
        # To avoid 'OSError: AF_UNIX path too long'
        _root_dir = pathlib.Path("/tmp").resolve() / tmp_path.name
    else:
        _root_dir = tmp_path
    try:
        yield _root_dir
    finally:
        shutil.rmtree(str(_root_dir), ignore_errors=True)


@pytest.fixture
def master_config(master_opts, root_dir):
    master_opts.update(
        transport="zeromq",
        id="master",
        interface="127.0.0.1",
        fips_mode=FIPS_TESTRUN,
        publish_signing_algorithm=(
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
        root_dir=str(root_dir),
        worker_pools_enabled=False,
        auto_accept=True,
        open_mode=False,
        auth_events=False,
    )
    priv, pub = salt.crypt.gen_keys(4096)
    path = pathlib.Path(master_opts["pki_dir"], "master")
    path.with_suffix(".pem").write_text(priv, encoding="utf-8")
    path.with_suffix(".pub").write_text(pub, encoding="utf-8")
    yield master_opts


@pytest.fixture
def minion_config(minion_opts, master_config, channel_minion_id):
    minion_opts.update(
        transport=master_config["transport"],
        root_dir=master_config["root_dir"],
        id=channel_minion_id,
        cachedir=master_config["cachedir"],
        sock_dir=master_config["sock_dir"],
        ret_port=master_config["ret_port"],
        interface="127.0.0.1",
        pki_dir=os.path.join(master_config["root_dir"], f"pki_{channel_minion_id}"),
        master_port=master_config["ret_port"],
        master_ip="127.0.0.1",
        master_uri="tcp://127.0.0.1:{}".format(master_config["ret_port"]),
        fips_mode=FIPS_TESTRUN,
        encryption_algorithm="OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        signing_algorithm="PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        auth_timeout=5,
        auth_tries=1,
        acceptance_wait_time=0,
        acceptance_wait_time_max=0,
        rejected_retry=False,
        auth_events=False,
    )
    os.makedirs(minion_opts["pki_dir"], exist_ok=True)
    salt.crypt.AsyncAuth(minion_opts).get_keys()  # generate minion.pem/pub
    yield minion_opts


def _pre_accept(minion_config, master_config):
    minion_pub = os.path.join(minion_config["pki_dir"], "minion.pub")
    master_minions = pathlib.Path(master_config["pki_dir"]) / "minions"
    master_minions.mkdir(exist_ok=True)
    shutil.copyfile(minion_pub, master_minions / minion_config["id"])


def _reject(minion_config, master_config):
    minion_pub = os.path.join(minion_config["pki_dir"], "minion.pub")
    master_rejected = pathlib.Path(master_config["pki_dir"]) / "minions_rejected"
    master_rejected.mkdir(exist_ok=True)
    shutil.copyfile(minion_pub, master_rejected / minion_config["id"])


@pytest.fixture
def master_secrets():
    """
    Populate ``SMaster.secrets['aes']`` the same way the real master does on
    startup.  Required for ``ReqServerChannel.post_fork`` -> crypticle.
    """
    old = salt.master.SMaster.secrets.get("aes")
    salt.master.SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        ),
        "serial": multiprocessing.Value(ctypes.c_longlong, lock=False),
        "reload": salt.crypt.Crypticle.generate_key_string,
    }
    try:
        yield
    finally:
        if old is None:
            salt.master.SMaster.secrets.pop("aes", None)
        else:
            salt.master.SMaster.secrets["aes"] = old


class CountingReqServerChannel(salt.channel.server.ReqServerChannel):
    """
    ReqServerChannel subclass that counts ``_auth`` dispatches and lets a
    test slow the handler down to widen the race window that this file is
    trying to prove is closed.
    """

    # Set by the test before pre_fork.
    auth_counter = None  # type: ignore[assignment]
    auth_delay = 0.0

    # pylint: disable=invalid-overridden-method
    def _auth(self, load, sign_messages=False, version=0):
        if self.auth_counter is not None:
            self.auth_counter[0] += 1
        if self.auth_delay:
            # Synchronous sleep -- the real master _auth is synchronous too
            # (it blocks the io_loop for the duration of key crypto).  This
            # widens the window during which concurrent AsyncAuth waiters
            # could race on a shared future, which is exactly what we want
            # to stress.
            import time as _time

            _time.sleep(self.auth_delay)
        return super()._auth(load, sign_messages=sign_messages, version=version)


@pytest.fixture
def _reset_asyncauth_singletons():
    """
    Each test starts with a clean ``AsyncAuth.instance_map`` and
    ``creds_map`` so the ``is None`` cold-start branch in ``authenticate``
    actually runs.  The real app only has one of these per process; tests
    stacked in one worker share class state and must scrub it.
    """
    import weakref

    old_instance_map = salt.crypt.AsyncAuth.instance_map
    old_creds_map = dict(salt.crypt.AsyncAuth.creds_map)
    salt.crypt.AsyncAuth.instance_map = weakref.WeakKeyDictionary()
    salt.crypt.AsyncAuth.creds_map = {}
    try:
        yield
    finally:
        salt.crypt.AsyncAuth.instance_map = old_instance_map
        salt.crypt.AsyncAuth.creds_map = old_creds_map


async def _run_server(master_config, counter, delay, io_loop):
    """
    Stand up a counting ReqServerChannel on ``io_loop`` and return it.  The
    caller is responsible for ``close()``.
    """
    CountingReqServerChannel.auth_counter = counter
    CountingReqServerChannel.auth_delay = delay
    pm = salt.utils.process.ProcessManager()
    transport = salt.transport.base.request_server(master_config)
    server = CountingReqServerChannel(master_config, transport)
    server.pre_fork(pm)

    async def _noop_payload_handler(payload):
        return payload, {"fun": "send"}

    server.post_fork(_noop_payload_handler, io_loop=io_loop)
    # Give the zmq transport a beat to actually bind.
    await asyncio.sleep(0.2)
    return server, pm


async def test_distinct_futures_and_one_signin(
    master_config,
    minion_config,
    master_secrets,
    _reset_asyncauth_singletons,
    io_loop,
):
    """
    Property (1): N=3 concurrent ``authenticate()`` callers against a cold
    ``creds_map`` get three distinct Future objects, all resolve ``True``,
    and the master services exactly one ``_auth`` roundtrip.
    """
    _pre_accept(minion_config, master_config)
    counter = [0]
    server, pm = await _run_server(master_config, counter, 0.0, io_loop)
    try:
        auth = salt.crypt.AsyncAuth(minion_config, io_loop=io_loop)
        # Cold start: no cached creds for this key.
        key = salt.crypt._auth_singleton_key(minion_config)
        assert key not in salt.crypt.AsyncAuth.creds_map

        f1 = auth.authenticate()
        f2 = auth.authenticate()
        f3 = auth.authenticate()

        # Each caller got its own Future object (issue #70642 contract).
        assert f1 is not f2
        assert f2 is not f3
        assert f1 is not f3

        results = await asyncio.gather(f1, f2, f3)
        assert results == [True, True, True]

        # Exactly one master-side AUTH was serviced for the three callers.
        assert counter[0] == 1, f"expected 1 _auth, got {counter[0]}"

        # And the creds landed in the shared map exactly once.
        assert key in salt.crypt.AsyncAuth.creds_map
        assert auth.authenticated is True
        assert auth._sign_in_task is None
    finally:
        server.close()
        pm.terminate()


async def test_burst_no_invalid_state_error(
    master_config,
    minion_config,
    master_secrets,
    _reset_asyncauth_singletons,
    io_loop,
):
    """
    Property (2): 20 concurrent ``authenticate()`` callers with the
    master-side AUTH handler slowed by 50ms.  None should see
    ``InvalidStateError``; all should resolve ``True``; ``creds_map`` has
    exactly one entry; and exactly one AUTH roundtrip was serviced.

    The pre-70642 ``_authenticate_future`` design would, under this timing,
    occasionally let a tail-reaching waiter ``set_exception`` on an
    already-resolved future -- that is the bug this property guards.
    """
    _pre_accept(minion_config, master_config)
    counter = [0]
    server, pm = await _run_server(master_config, counter, 0.05, io_loop)
    try:
        auth = salt.crypt.AsyncAuth(minion_config, io_loop=io_loop)
        key = salt.crypt._auth_singleton_key(minion_config)
        assert key not in salt.crypt.AsyncAuth.creds_map

        futures = [auth.authenticate() for _ in range(20)]
        # All futures are distinct -- the per-caller invariant must hold
        # even when 20 callers pile onto the same in-flight sign-in.
        assert len({id(f) for f in futures}) == 20

        # gather with return_exceptions=True so a single InvalidStateError
        # does not short-circuit the others; we want to inspect them all.
        results = await asyncio.gather(*futures, return_exceptions=True)
        for i, r in enumerate(results):
            assert r is True, f"waiter {i} got {r!r} instead of True"

        assert counter[0] == 1, f"expected 1 _auth under burst, got {counter[0]}"
        assert key in salt.crypt.AsyncAuth.creds_map
        assert auth.authenticated is True
        assert auth._sign_in_task is None
        assert auth._waiters == set()
    finally:
        server.close()
        pm.terminate()


async def test_exception_fans_out_to_all_waiters(
    master_config,
    minion_config,
    master_secrets,
    _reset_asyncauth_singletons,
    io_loop,
):
    """
    Property (3): when sign-in fails for N=5 concurrent waiters, every
    waiter raises on await; the authenticator is left in a clean
    unauthenticated state (``authenticated is False``, ``_sign_in_task is
    None``) so a subsequent ``authenticate()`` call can retry fresh.

    Failure is induced through the real wire path: the minion's key is
    placed in ``minions_rejected/`` on the master.  The master's
    ``AuthFuncs._auth`` returns ``ret: False``; with ``rejected_retry=False``
    the minion's ``handle_signin_response`` would normally call
    ``sys.exit()`` -- which we must avoid in a test -- so we instead set
    ``rejected_retry=True`` + ``auth_retries=1`` in a minimal override
    below.  That path makes ``_authenticate`` exit the retry loop after one
    master roundtrip with ``SaltClientError``, which is the exception
    ``_on_sign_in_done`` must fan out.
    """
    _reject(minion_config, master_config)
    minion_config["rejected_retry"] = True
    minion_config["auth_retries"] = 1

    counter = [0]
    server, pm = await _run_server(master_config, counter, 0.0, io_loop)
    try:
        auth = salt.crypt.AsyncAuth(minion_config, io_loop=io_loop)
        key = salt.crypt._auth_singleton_key(minion_config)
        assert key not in salt.crypt.AsyncAuth.creds_map

        futures = [auth.authenticate() for _ in range(5)]
        assert len({id(f) for f in futures}) == 5

        results = await asyncio.gather(*futures, return_exceptions=True)
        # Every single waiter must have received the exception; none may
        # hang, and none may receive True.
        from salt.exceptions import SaltClientError

        for i, r in enumerate(results):
            assert isinstance(
                r, SaltClientError
            ), f"waiter {i}: expected SaltClientError, got {r!r}"

        # Post-conditions: authenticator is cleaned up for a retry.
        assert auth.authenticated is False
        assert auth._sign_in_task is None
        assert auth._waiters == set()
        assert key not in salt.crypt.AsyncAuth.creds_map
    finally:
        server.close()
        pm.terminate()
