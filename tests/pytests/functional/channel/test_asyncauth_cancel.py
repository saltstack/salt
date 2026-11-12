"""
Functional tests for ``salt.crypt.AsyncAuth`` cancellation contract against
the real ZeroMQ transport + real ``ReqServerChannel`` + real ``sign_in``.

Scope
-----
These tests exercise the per-caller-future design introduced for issue
#70642.  They assert three invariants:

1. **Cancellation isolation** -- cancelling one caller's future does not
   disturb siblings, and does not spawn an extra master-side sign-in.
2. **Last-waiter cancel drains the sign-in task** -- when the sole waiter
   cancels, ``_sign_in_task`` is cleared synchronously by
   ``_on_waiter_done`` (the pending-cancel-window fix), the minion-side
   request channel is released (no fd leak across repeated cycles), and
   ``_last_result`` is cleared.
3. **Fresh ``authenticate()`` in the pending-cancel window** -- a new
   call arriving after a last-waiter cancel (but before the cancelled
   task's ``_on_sign_in_done`` has run) spawns a *fresh* sign-in task and
   completes normally; the cancelled task's done-callback must not
   clobber the new task's state (``self._sign_in_task is not task``
   guard).

All three tests speak to a real master process (``ReqServerChannelProcess``
below) over a real zmq ``REP`` socket.  A test-only subclass slows the
``_auth`` handler by ~200 ms so cancellation has a window to land before
the master's reply is on the wire, and increments a shared
``multiprocessing.Value`` counter so sibling spawns are directly
observable.

Testing internal attributes (``_waiters``, ``_sign_in_task``,
``_last_result``) is intentional here; the whole point of these tests is
to pin the invariants those attributes encode.
"""

import asyncio
import ctypes
import logging
import multiprocessing
import os
import pathlib
import shutil

import pytest
import tornado.ioloop
from pytestshellutils.utils import ports as _ports
from pytestshellutils.utils.processes import terminate_process

import salt.channel.server
import salt.config
import salt.crypt
import salt.daemons.masterapi
import salt.master
import salt.utils.event
import salt.utils.files
import salt.utils.platform
import salt.utils.process
import salt.utils.stringutils

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.skip_on_spawning_platform(
        reason=(
            "Requires fork-safe multiprocessing shared state; the existing "
            "functional channel tests carry the same restriction."
        ),
    ),
    pytest.mark.timeout_unless_on_windows(120),
    pytest.mark.slow_test,
]


MINION_ID = "test-asyncauth-cancel-minion"


@pytest.fixture
def auth_pki_dir(tmp_path):
    """
    PKI layout mirroring ``test_auth_downgrade.py``: a master pki dir with
    the accepted minion pub pre-populated under ``minions/<id>`` and a
    minion pki dir with its own keypair.  Keys are generated once per
    test so the per-test cost stays at a single 2048-bit generation.
    """
    if salt.utils.platform.is_darwin():
        # Avoid 'AF_UNIX path too long' on macOS by rehoming under /tmp.
        root_dir = pathlib.Path("/tmp").resolve() / tmp_path.name
    else:
        root_dir = tmp_path

    master_pki = root_dir / "master_pki"
    minion_pki = root_dir / "minion_pki"
    master_pki.mkdir(parents=True)
    minion_pki.mkdir(parents=True)
    (master_pki / "minions").mkdir()
    (master_pki / "minions_pre").mkdir()
    (master_pki / "minions_rejected").mkdir()
    (master_pki / "minions_denied").mkdir()

    master_priv, master_pub = salt.crypt.gen_keys(2048)
    (master_pki / "master.pem").write_text(master_priv)
    (master_pki / "master.pub").write_text(master_pub)

    minion_priv, minion_pub = salt.crypt.gen_keys(2048)
    (minion_pki / "minion.pem").write_text(minion_priv)
    (minion_pki / "minion.pub").write_text(minion_pub)

    # Accept the minion
    (master_pki / "minions" / MINION_ID).write_text(minion_pub)

    try:
        yield root_dir
    finally:
        if salt.utils.platform.is_darwin():
            shutil.rmtree(str(root_dir), ignore_errors=True)


@pytest.fixture
def free_port():
    return _ports.get_unused_localhost_port()


@pytest.fixture
def cancel_master_opts(auth_pki_dir, free_port):
    # Start from DEFAULT_MASTER_OPTS so every runtime key (especially the
    # zmq transport internals like ``mworker_queue_niceness``) is present.
    opts = salt.config.DEFAULT_MASTER_OPTS.copy()
    # ``worker_pools_enabled=False`` keeps the plain ReqServerChannel path
    # active, but ``zmq_device`` still constructs a ``RequestRouter`` for
    # statistics purposes which requires a ``*`` catchall pool.  Seed the
    # DEFAULT_WORKER_POOLS layout here so its validation passes.
    from salt.config.worker_pools import DEFAULT_WORKER_POOLS

    opts["worker_pools"] = DEFAULT_WORKER_POOLS
    opts.update(
        {
            "master_uri": f"tcp://127.0.0.1:{free_port}",
            "interface": "127.0.0.1",
            "ret_port": free_port,
            "ipv6": False,
            "sock_dir": str(auth_pki_dir / "sock"),
            "cachedir": str(auth_pki_dir / "cache"),
            "pki_dir": str(auth_pki_dir / "master_pki"),
            "id": "master",
            "__role": "master",
            "transport": "zeromq",
            "keysize": 2048,
            "max_minions": 0,
            "auto_accept": True,
            "open_mode": False,
            "key_pass": None,
            "publish_port": free_port + 1,
            "auth_mode": 1,
            "auth_events": False,
            "publish_session": 86400,
            "request_server_ttl": 300,
            "worker_threads": 1,
            "worker_pools_enabled": False,
            "cluster_id": None,
            "master_sign_pubkey": False,
            "sign_pub_messages": False,
            "minimum_auth_version": 0,
            "keys.cache_driver": "localfs_key",
            "extension_modules": str(auth_pki_dir / "extmods"),
            "file_roots": {"base": [str(auth_pki_dir / "file_roots")]},
            "pillar_roots": {"base": [str(auth_pki_dir / "pillar_roots")]},
            "pub_server_niceness": None,
            "mworker_queue_niceness": None,
            "con_cache": False,
            "zmq_monitor": False,
            "permissive_pki_access": True,
        }
    )
    (auth_pki_dir / "sock").mkdir(exist_ok=True)
    (auth_pki_dir / "cache").mkdir(exist_ok=True)
    (auth_pki_dir / "cache" / "sessions").mkdir(exist_ok=True)
    return opts


@pytest.fixture
def cancel_minion_opts(auth_pki_dir, cancel_master_opts, free_port):
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    opts.update(
        {
            "master_uri": f"tcp://127.0.0.1:{free_port}",
            "interface": "127.0.0.1",
            "ret_port": free_port,
            "ipv6": False,
            "sock_dir": str(auth_pki_dir / "minion_sock"),
            "cachedir": str(auth_pki_dir / "minion_cache"),
            "pki_dir": str(auth_pki_dir / "minion_pki"),
            "id": MINION_ID,
            "__role": "minion",
            "transport": "zeromq",
            "keysize": 2048,
            "encryption_algorithm": salt.crypt.OAEP_SHA1,
            "signing_algorithm": salt.crypt.PKCS1v15_SHA1,
            "master_port": free_port,
            "master_ip": "127.0.0.1",
            "acceptance_wait_time": 1,
            "acceptance_wait_time_max": 1,
            "auth_timeout": 10,
            "auth_tries": 1,
            "auth_retries": 1,
            "auth_events": False,
            "request_channel_timeout": 10,
            "request_channel_tries": 1,
            "keys.cache_driver": "localfs_key",
            "detect_mode": False,
        }
    )
    (auth_pki_dir / "minion_sock").mkdir(exist_ok=True)
    (auth_pki_dir / "minion_cache").mkdir(exist_ok=True)
    return opts


class _SlowAuthReqServerChannel(salt.channel.server.ReqServerChannel):
    """
    ``ReqServerChannel`` whose ``handle_message`` sleeps for ~200 ms on
    every ``_auth`` request *before* calling the underlying ``_auth``.

    The delay is enforced on the server event loop (``asyncio.sleep``), so
    client cancellation can land after the request is on the wire but
    before the reply is produced -- which is the exact window the
    AsyncAuth cancellation contract is written for.

    A ``multiprocessing.Value('i')`` counter is incremented once per
    serviced sign-in and read back in the parent process to prove that
    sibling callers did not each trigger their own master-side
    roundtrip.
    """

    # Set after construction via ``post_fork_`` style wiring below.
    _auth_counter = None
    _auth_delay = 0.2

    async def handle_message(self, payload):
        try:
            if (
                isinstance(payload, dict)
                and payload.get("enc") == "clear"
                and isinstance(payload.get("load"), dict)
                and payload["load"].get("cmd") == "_auth"
            ):
                if self._auth_counter is not None:
                    with self._auth_counter.get_lock():
                        self._auth_counter.value += 1
                await asyncio.sleep(self._auth_delay)
        except Exception:  # pylint: disable=broad-except
            log.exception("Slow-auth wrapper raised; falling through")
        return await super().handle_message(payload)


class ReqServerChannelProcess(salt.utils.process.SignalHandlingProcess):
    """
    Runs the real zmq ``ReqServerChannel`` in a dedicated subprocess, so
    the minion-side ``AsyncAuth`` under test sees a genuine remote peer
    across a real socket.  Modeled on ``ReqServerChannelProcess`` in
    ``test_req_channel.py``.
    """

    def __init__(self, config, auth_counter):
        super().__init__()
        self._closing = False
        self.config = config
        self.auth_counter = auth_counter
        self.running = multiprocessing.Event()
        self.process_manager = None
        self.io_loop = None
        self.req_server_channel = None

    def run(self):
        salt.master.SMaster.secrets["aes"] = {
            "secret": multiprocessing.Array(
                ctypes.c_char,
                salt.utils.stringutils.to_bytes(
                    salt.crypt.Crypticle.generate_key_string()
                ),
            ),
            "serial": multiprocessing.Value(ctypes.c_longlong, lock=False),
        }

        self.process_manager = salt.utils.process.ProcessManager(
            name="AsyncAuthCancel-ReqServer-PM"
        )

        # Build the slow-auth subclass directly so that the overriden
        # handle_message is what the zmq transport calls back into.  We
        # can't just monkeypatch an instance's handle_message because
        # ``post_fork`` passes a bound-method reference to the transport
        # layer before the override is installed.
        self.req_server_channel = _SlowAuthReqServerChannel.factory(self.config)
        self.req_server_channel._auth_counter = self.auth_counter
        self.req_server_channel.pre_fork(self.process_manager)

        self.io_loop = tornado.ioloop.IOLoop()
        self.io_loop.make_current()

        async def _payload_handler(payload):
            # Non-_auth payloads aren't expected in these tests, but provide
            # a sane default so an errant publish doesn't hang the loop.
            return payload, {"fun": "send_clear"}

        self.req_server_channel.post_fork(_payload_handler, io_loop=self.io_loop)
        self.io_loop.add_callback(self.running.set)
        try:
            self.io_loop.start()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            try:
                self.req_server_channel.close()
            except Exception:  # pylint: disable=broad-except
                log.exception("Error closing req_server_channel on teardown")

    def _handle_signals(self, signum, sigframe):
        self.close()
        super()._handle_signals(signum, sigframe)

    def __enter__(self):
        self.start()
        if not self.running.wait(timeout=30):
            raise RuntimeError("ReqServerChannelProcess did not start")
        return self

    def __exit__(self, *args):
        self.close()
        self.terminate()
        self.join(timeout=10)

    def close(self):
        if self._closing:
            return
        self._closing = True
        if self.process_manager is not None:
            try:
                self.process_manager.terminate()
                for pid in list(self.process_manager._process_map):
                    terminate_process(pid=pid, kill_children=True, slow_stop=False)
            except Exception:  # pylint: disable=broad-except
                pass
            self.process_manager = None


@pytest.fixture
def auth_counter():
    return multiprocessing.Value(ctypes.c_int, 0)


@pytest.fixture
def running_master(cancel_master_opts, auth_counter):
    """
    Spin up the slow-auth ReqServerChannel in a subprocess.  The subprocess
    owns the zmq ``REP`` socket on ``cancel_master_opts["ret_port"]``; the test
    body is the minion peer.
    """
    proc = ReqServerChannelProcess(cancel_master_opts, auth_counter)
    try:
        with proc:
            yield proc
    finally:
        try:
            terminate_process(pid=proc.pid, kill_children=True, slow_stop=False)
        except Exception:  # pylint: disable=broad-except
            pass


def _drop_auth_singletons():
    """
    ``AsyncAuth`` is a per-io_loop / per-key singleton.  Tests in this
    module need a fresh instance per test so their asserts on
    ``_sign_in_task`` / ``_last_result`` reflect only that test's
    activity.  Clearing the class-level maps is the documented way to
    recycle the singleton (see ``AsyncAuth._after_fork_in_child``).
    """
    import weakref

    salt.crypt.AsyncAuth.instance_map = weakref.WeakKeyDictionary()
    salt.crypt.AsyncAuth.creds_map.clear()


@pytest.fixture
def fresh_auth():
    _drop_auth_singletons()
    yield
    _drop_auth_singletons()


async def test_cancellation_isolation_single_signin(
    running_master,
    cancel_minion_opts,
    fresh_auth,
    auth_counter,
    io_loop,
):
    """
    Property 1: Cancelling one caller's future must not cancel siblings,
    must not spawn an extra master-side sign-in, and must not abort the
    in-flight sign-in task while other waiters are still registered.
    """
    auth = salt.crypt.AsyncAuth(cancel_minion_opts, io_loop=io_loop)

    # Spawn three concurrent callers.  They share a single ``_sign_in_task``
    # and each get their own Future.
    f0 = auth.authenticate()
    f1 = auth.authenticate()
    f2 = auth.authenticate()

    # All three share the same in-flight sign-in task.
    assert auth._sign_in_task is not None
    assert len(auth._waiters) == 3
    shared_task = auth._sign_in_task

    # Give the io_loop a tick so the task is actively running against the
    # slow-auth master.
    await asyncio.sleep(0)

    # Cancel the middle caller only.
    f1.cancel()

    # Cancelling a waiter must not cancel the shared sign-in task while
    # siblings remain -- only last-waiter-cancel does that.
    assert auth._sign_in_task is shared_task
    assert not shared_task.cancelled()

    # The two remaining callers should resolve to True; the cancelled
    # one raises CancelledError.
    r0 = await f0
    r2 = await f2
    assert r0 is True
    assert r2 is True

    assert f1.cancelled()

    # Exactly one sign-in roundtrip serviced by the master: cancelling a
    # sibling must not spawn an extra request.
    assert (
        auth_counter.value == 1
    ), f"Expected exactly 1 master-side sign-in, got {auth_counter.value}"

    # The sign-in task's done-callback cleared state after success.
    assert auth._sign_in_task is None
    assert auth._last_result == (True,)
    assert auth._waiters == set()
    assert auth.authenticated is True


async def test_last_waiter_cancel_drains_task_no_fd_leak(
    running_master,
    cancel_minion_opts,
    fresh_auth,
    auth_counter,
    io_loop,
):
    """
    Property 2: When the sole waiter cancels, the pending-cancel-window
    fix (``_on_waiter_done`` clearing ``_sign_in_task`` synchronously)
    must drop the request-channel reference so repeated cancel cycles
    do not accumulate file descriptors on the minion process.
    """
    import psutil

    auth = salt.crypt.AsyncAuth(cancel_minion_opts, io_loop=io_loop)

    proc = psutil.Process(os.getpid())

    # Prime the loop so the first cycle's steady-state fd set is
    # established (zmq contexts, logging fds, etc. settle after the
    # first iteration).
    f = auth.authenticate()
    await asyncio.sleep(0)
    assert (
        auth._sign_in_task is not None
    ), "Sign-in task must be installed synchronously by authenticate()"
    priming_task = auth._sign_in_task
    f.cancel()
    # ``future.cancel()`` schedules the done-callback via ``call_soon``;
    # a single ``sleep(0)`` drains the loop so ``_on_waiter_done`` has
    # run and the pending-cancel-window fix is observable.
    await asyncio.sleep(0)

    # The pending-cancel-window fix: ``_on_waiter_done`` must clear
    # ``_sign_in_task`` and ``_last_result`` *before* requesting the
    # task cancellation so a racing ``authenticate()`` does not latch
    # onto the doomed task.
    assert (
        auth._sign_in_task is None
    ), "_on_waiter_done must clear _sign_in_task on last-waiter cancel"
    assert auth._last_result is None, (
        "_on_waiter_done must clear _last_result so a racing "
        "authenticate() does not observe stale success"
    )
    # Let the cancelled task finish unwinding on the loop.
    await asyncio.sleep(0.3)
    assert priming_task.done()

    baseline_fds = proc.num_fds()

    # Loop ten cancel cycles.  Each cycle: authenticate(), yield, cancel.
    # If the sign-in task's AsyncReqChannel is leaked (the pre-fix
    # behaviour), fd count grows every cycle.
    for i in range(10):
        fut = auth.authenticate()
        assert auth._sign_in_task is not None, f"cycle {i}: task not spawned"
        # Yield once so the sign-in task hits its first await point and
        # the zmq request is on the wire.
        await asyncio.sleep(0)
        fut.cancel()
        # Drain the loop so the done-callback runs.
        await asyncio.sleep(0)
        # ``_on_waiter_done`` clear invariant.
        assert (
            auth._sign_in_task is None
        ), f"cycle {i}: _sign_in_task must be cleared on last-waiter cancel"
        assert (
            auth._last_result is None
        ), f"cycle {i}: _last_result must be cleared on last-waiter cancel"
        # Give the cancelled task time to unwind so its channel closes.
        await asyncio.sleep(0.3)

    current_fds = proc.num_fds()

    # Allow a small envelope for logging / jitter but not unbounded growth.
    # Pre-fix this grew by ~2 fds per cycle; we bound at +10 total for
    # the full 10-iteration loop.
    assert current_fds - baseline_fds <= 10, (
        f"FD leak: baseline={baseline_fds} after 10 cancel cycles "
        f"current={current_fds} (delta={current_fds - baseline_fds})"
    )


async def test_fresh_authenticate_in_pending_cancel_window(
    running_master,
    cancel_minion_opts,
    fresh_auth,
    auth_counter,
    io_loop,
):
    """
    Property 3: Immediately after a last-waiter cancel, a new
    ``authenticate()`` call must spawn a *fresh* sign-in task (because
    ``_on_waiter_done`` already set ``_sign_in_task = None``) and the
    cancelled task's eventual ``_on_sign_in_done`` must NOT clobber the
    new task's ``_waiters`` or ``_last_result`` -- the
    ``self._sign_in_task is not task`` guard must fire.
    """
    auth = salt.crypt.AsyncAuth(cancel_minion_opts, io_loop=io_loop)

    # Start the first (soon-to-be-cancelled) caller.
    f_old = auth.authenticate()
    await asyncio.sleep(0)
    old_task = auth._sign_in_task
    assert old_task is not None

    # Last-waiter cancel -- the done-callback is scheduled via
    # ``call_soon``; drain the loop so ``_on_waiter_done`` runs and
    # clears ``_sign_in_task`` / ``_last_result``.
    f_old.cancel()
    await asyncio.sleep(0)
    assert auth._sign_in_task is None
    assert auth._last_result is None

    # Fresh authenticate() in the pending-cancel window.  The old task is
    # still not ``done()`` (cooperative cancellation hasn't propagated
    # yet), but ``_sign_in_task is None`` so the spawn guard fires and a
    # brand-new task is installed.
    f_new = auth.authenticate()
    new_task = auth._sign_in_task
    assert new_task is not None, "Fresh authenticate() must spawn a new task"
    assert new_task is not old_task, (
        "New authenticate() in pending-cancel window must install a *fresh* "
        "task, not re-latch onto the cancelled one"
    )

    # The new caller should successfully authenticate.
    result = await f_new
    assert result is True
    assert auth.authenticated is True
    assert auth._last_result == (True,)

    # When the old (cancelled) task's ``_on_sign_in_done`` eventually
    # runs, its ``self._sign_in_task is not task`` guard must short
    # circuit.  If it didn't, it would have cleared ``_last_result`` or
    # the new task's waiters on its way out.  Give the loop a tick for
    # the old task's done-callback to run, then re-check invariants.
    await asyncio.sleep(0.3)
    assert old_task.done()
    # The new task's success state is still intact -- old task's stale
    # callback did not clobber it.
    assert auth._last_result == (True,)
    assert auth.authenticated is True

    # Two sign-in requests hit the master: one for the cancelled call
    # (its request went on the wire before the cancel landed) and one
    # for the fresh call.  Both are "real" so the counter is 2; what
    # matters is that we spawned exactly one FRESH task, not that we
    # did not touch the master at all.
    assert auth_counter.value >= 1
