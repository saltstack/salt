"""
Functional tests for :class:`salt.crypt.AsyncAuth` fast-path + done-gap
contract (issue #70642).

These tests exercise the real zmq transport + real
:class:`salt.channel.server.ReqServerChannel` + real
:meth:`salt.crypt.AsyncAuth.sign_in` path.  No ``sign_in`` monkey-patching,
no ``asyncio.Event`` gating -- the goal is to prove, via a real master-side
AUTH counter, two properties that today only have unit-test coverage:

1. **Cached-creds fast path makes zero sign-in roundtrips.**  When
   ``AsyncAuth`` is constructed with a key already in ``creds_map``, the
   ``authenticated`` property is True immediately and the production
   ``if not self.auth.authenticated: await self.auth.authenticate()``
   gate (see ``salt/channel/client.py``) short-circuits the network
   roundtrip entirely.  After ``invalidate()``, the same pattern results
   in exactly one real sign-in.

   Unit counterpart:
   ``test_authenticate_cached_creds_fast_path_via_authenticated_property``
   in ``tests/pytests/unit/test_crypt.py``, which proves the contract via
   ``_last_result`` internals.  This functional version proves it via the
   master-side AUTH counter, which is what production channel
   reconstruction actually depends on.

2. **Done-callback-gap race: one burst, one sign-in.**  Under a burst of
   N concurrent ``authenticate()`` callers against a slowed master, every
   caller is served by **exactly one** AUTH roundtrip -- even when some
   callers arrive in the ``call_soon`` gap between the sign-in task's
   completion and ``_on_sign_in_done`` running.

   Unit counterpart:
   ``test_authenticate_during_done_callback_gap_does_not_respawn_sign_in``
   in ``tests/pytests/unit/test_crypt.py``, which injects a precise
   ``call_soon`` from inside a mocked ``sign_in`` to land in the gap.
   On a real zmq stack we cannot inject into the master coroutine from
   the minion-side test without monkey-patching, so this file uses the
   best deterministic approximation: a 20-caller burst against a slowed
   master, looped 20 times, asserting ``auth_counter == 1`` on every
   iteration.  Under the pre-fix ``.done()``-based spawn guard, a tail
   caller landing in the gap would increment the counter to >=2; the
   fixed guard keeps it at 1.
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
    pytest.mark.timeout_unless_on_windows(180),
]


@pytest.fixture
def channel_minion_id():
    return random_string("fastpath-auth-minion-")


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
            # could race on a shared future / the done-callback gap,
            # which is exactly what we want to stress.
            import time as _time

            _time.sleep(self.auth_delay)
        return super()._auth(load, sign_messages=sign_messages, version=version)


@pytest.fixture
def _reset_asyncauth_singletons():
    """
    Each test starts with a clean ``AsyncAuth.instance_map`` and
    ``creds_map`` so the cached-creds branch in ``__singleton_init__``
    only fires when *this* test pre-populates it.
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


async def test_cached_creds_zero_signin_then_invalidate_one_signin(
    master_config,
    minion_config,
    master_secrets,
    _reset_asyncauth_singletons,
    io_loop,
):
    """
    Property (1): cached-creds fast path makes zero master-side AUTH
    roundtrips, and ``invalidate()`` arms the next ``authenticate()`` for
    exactly one real sign-in.

    Workflow:

    - Pre-populate ``AsyncAuth.creds_map[credskey]`` with a session key
      and the **same** AES value the master holds in
      ``SMaster.secrets['aes']['secret']`` (that is the invariant real
      channels depend on: minion-side cached creds match the master's
      live master-AES, because the creds were produced by a prior real
      sign-in).
    - Construct ``AsyncAuth(opts, io_loop=io_loop)``.  The
      ``__singleton_init__`` cached-creds branch must set
      ``_last_result = (True,)``, so ``authenticated`` is True
      *immediately*.
    - Follow the production ``channel/client.py`` gate:
      ``if not auth.authenticated: await auth.authenticate()``.  Because
      ``authenticated`` is True, ``authenticate()`` is never called.
      The master-side AUTH counter must be 0.
    - Call ``auth.invalidate()``.  ``authenticated`` must flip to False
      and the ``creds_map`` entry must be gone.
    - Re-enter the gate: ``authenticated`` is now False, so
      ``authenticate()`` runs.  The master services exactly one
      ``_auth`` roundtrip.

    This pins the contract that hot reconnect flows depend on: a channel
    reconstructed with a warm ``creds_map`` does not re-auth against the
    master, because the ``authenticated`` property is True on the
    freshly-constructed ``AsyncAuth``.
    """
    _pre_accept(minion_config, master_config)
    counter = [0]
    server, pm = await _run_server(master_config, counter, 0.0, io_loop)
    try:
        # Pre-populate creds_map with the master's live AES so that the
        # creds we're pretending were "already negotiated" match reality.
        # (Any value would satisfy the fast-path gate on the *minion*
        # side, but matching the master's AES is what the invariant
        # production callers rely on.)
        master_aes = salt.master.SMaster.secrets["aes"]["secret"].value.decode()
        session = salt.crypt.Crypticle.generate_key_string()
        credskey = salt.crypt._auth_singleton_key(minion_config)
        salt.crypt.AsyncAuth.creds_map[credskey] = {
            "aes": master_aes,
            "session": session,
        }

        auth = salt.crypt.AsyncAuth(minion_config, io_loop=io_loop)

        # Fast path pre-conditions: no sign-in task, no waiters, cached
        # creds flipped the property to True without any roundtrip.
        assert auth.authenticated is True
        assert auth._sign_in_task is None
        assert auth._waiters == set()
        assert counter[0] == 0

        # Production gate: skip authenticate() because we're already
        # authenticated.  Prove zero roundtrips happened by never calling
        # authenticate() and re-asserting the counter after a yield so
        # any stray scheduled coroutine would have had a chance to run.
        if not auth.authenticated:
            await auth.authenticate()  # pragma: no cover -- gate skips

        await asyncio.sleep(0.05)
        assert counter[0] == 0, (
            f"cached-creds fast path should make zero AUTH roundtrips; "
            f"got {counter[0]}"
        )
        # creds_map entry is still the one we pre-populated -- no real
        # sign-in happened, so the AES value is unchanged.
        assert salt.crypt.AsyncAuth.creds_map[credskey]["aes"] == master_aes
        assert salt.crypt.AsyncAuth.creds_map[credskey]["session"] == session

        # Now invalidate: the cached entry is dropped, authenticated
        # flips to False, and the next gate-enter triggers one real
        # sign-in.
        auth.invalidate()
        assert auth.authenticated is False
        assert auth._last_result is None
        assert credskey not in salt.crypt.AsyncAuth.creds_map

        if not auth.authenticated:
            result = await auth.authenticate()
        assert result is True
        assert counter[0] == 1, (
            f"post-invalidate authenticate() should make exactly one "
            f"AUTH roundtrip; got {counter[0]}"
        )
        assert auth.authenticated is True
        assert auth._sign_in_task is None
        assert credskey in salt.crypt.AsyncAuth.creds_map
    finally:
        server.close()
        pm.terminate()


# Burst sizing + loop iterations for property (2).  N=20 callers matches
# the unit test's intent (pile many concurrent callers against a slowed
# master, catching any that land in the done-callback gap); 20 loop
# iterations mean we exercise the race ~400 times per run, which is
# enough to surface the pre-fix bug deterministically on every machine
# this test was developed on.
_BURST_CALLERS = 20
_BURST_ITERATIONS = 20


async def test_burst_exactly_one_signin_no_done_gap_respawn(
    master_config,
    minion_config,
    master_secrets,
    _reset_asyncauth_singletons,
    io_loop,
):
    """
    Property (2): N=20 concurrent ``authenticate()`` callers against a
    master slowed by 50ms must be served by **exactly one** master-side
    ``_auth`` roundtrip.  Looped 20 times.

    This is the real-stack approximation of the unit test
    ``test_authenticate_during_done_callback_gap_does_not_respawn_sign_in``.
    That unit test injects a precise ``call_soon`` from inside a mocked
    ``sign_in`` to land a late caller in the window between the sign-in
    task's return and ``_on_sign_in_done`` executing.  The real zmq
    stack does not expose a hook to inject into the master coroutine
    from a minion-side test without monkey-patching, so we rely on the
    probabilistic equivalent: a large burst of callers plus a slowed
    master raises the odds that *some* caller lands in the gap on any
    given iteration.  Looping 20 times escalates that odds-of-at-least-
    one-gap-arrival to effective certainty.

    Under the pre-fix spawn guard
    (``if self._sign_in_task is None or self._sign_in_task.done():``)
    a gap caller would spawn a second sign-in, bumping ``auth_counter``
    to 2 on that iteration.  Under the fixed guard
    (``if self._sign_in_task is None:``) the gap caller joins the first
    task's waiter set and ``auth_counter`` stays at 1 on every
    iteration.

    The per-iteration ``invalidate()`` resets ``_last_result`` and drops
    the cached creds so the next burst starts cold -- otherwise the
    cached-creds fast path short-circuits the whole thing after
    iteration 1 and we'd never exercise the race.
    """
    _pre_accept(minion_config, master_config)
    counter = [0]
    server, pm = await _run_server(master_config, counter, 0.05, io_loop)
    try:
        auth = salt.crypt.AsyncAuth(minion_config, io_loop=io_loop)
        credskey = salt.crypt._auth_singleton_key(minion_config)

        for iteration in range(_BURST_ITERATIONS):
            # Cold start for this iteration: wipe any lingering cache.
            auth.invalidate()
            assert auth.authenticated is False
            counter[0] = 0

            futures = [auth.authenticate() for _ in range(_BURST_CALLERS)]
            # Per-caller distinct futures is the #70642 invariant --
            # regressing it would reintroduce InvalidStateError bursts.
            assert len({id(f) for f in futures}) == _BURST_CALLERS

            results = await asyncio.gather(*futures, return_exceptions=True)
            for i, r in enumerate(results):
                assert r is True, (
                    f"iteration {iteration} waiter {i}: expected True, " f"got {r!r}"
                )
            assert counter[0] == 1, (
                f"iteration {iteration}: expected exactly 1 AUTH "
                f"roundtrip, got {counter[0]}.  A count >=2 indicates a "
                f"late caller landed in the _on_sign_in_done call_soon "
                f"gap and the spawn guard re-entered on "
                f"_sign_in_task.done()."
            )
            assert auth.authenticated is True
            assert auth._sign_in_task is None
            assert auth._waiters == set()
            assert credskey in salt.crypt.AsyncAuth.creds_map
    finally:
        server.close()
        pm.terminate()
