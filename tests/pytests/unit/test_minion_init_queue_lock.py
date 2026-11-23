"""
Regression tests for the Minion.__init__ queue.lock stomp on multiprocessing
spawn-start platforms.

Context: ``salt.minion.Minion.__init__`` used to run an unconditional
``os.remove(queue.lock)`` + orphaned-running-file cleanup at every
instantiation. On any multiprocessing spawn-start platform (Windows
always, Linux when configured for spawn), each per-job subprocess
re-enters ``__init__`` via the ``instance=None`` branch in
``_invoke_execution`` (salt/minion.py:3216-3226) and deletes queue.lock
while a sibling job holds it. Siblings then each "acquire" a lock that
is already held; the original holder dies with ``FileNotFoundError`` on
release.

Fix: the cleanup lives on the CLI daemon entry points
(``salt.cli.daemons.Minion.prepare`` and ``ProxyMinion.prepare``) where
it fires exactly once per daemon process, before any ``Minion`` instance
is constructed. The utility functions
``salt.utils.state.cleanup_stale_queue_lock`` and
``salt.utils.state.cleanup_orphaned_queue_files`` do the work.
"""

import inspect
import multiprocessing
import os

import pytest

import salt.cli.daemons
import salt.minion
import salt.utils.files
import salt.utils.state


@pytest.fixture
def opts(tmp_path):
    return {"cachedir": str(tmp_path), "master": "regression-test-master"}


def test_minion_init_does_not_reference_queue_lock_cleanup():
    """
    ``Minion.__init__`` must not invoke the queue.lock cleanup directly.

    The cleanup was moved to ``salt.cli.daemons.Minion.prepare`` so it
    fires exactly once per daemon process. Invoking it from
    ``Minion.__init__`` would re-fire inside every per-job spawn
    subprocess on Windows, stomping locks held by siblings.
    """
    src = inspect.getsource(salt.minion.Minion.__init__)
    assert "queue_lock_path" not in src, (
        "Minion.__init__ references queue_lock_path. The cleanup must live "
        "in salt.cli.daemons.Minion.prepare() so it does not run inside "
        "per-job spawn subprocesses (issue #70580 side-effect)."
    )
    assert (
        "cleanup_stale_queue_lock" not in src
    ), "Minion.__init__ calls cleanup_stale_queue_lock. Same reason."
    assert (
        "_cleanup_orphaned_queue_files" not in src
    ), "Minion.__init__ calls the orphaned-running-file cleanup. Same reason."
    assert (
        "cleanup_orphaned_queue_files" not in src
    ), "Minion.__init__ calls the orphaned-running-file cleanup. Same reason."


def test_daemon_prepare_wires_queue_cleanup_calls():
    """
    Companion invariant: ``salt.cli.daemons.Minion.prepare`` and
    ``ProxyMinion.prepare`` must both invoke the queue cleanup wrapper.
    Catches an accidental revert that leaves the stale cleanup orphaned.
    """
    for cls_name in ("Minion", "ProxyMinion"):
        cls = getattr(salt.cli.daemons, cls_name)
        src = inspect.getsource(cls.prepare)
        assert "cleanup_queue_state" in src, (
            f"{cls_name}.prepare does not call cleanup_queue_state; "
            "daemons started under this class will not recover from a "
            "SIGKILLed prior minion that leaked queue.lock, and will "
            "not fan out cleanup across a multimaster master list."
        )


def _child_minion_init(lock_path, minion_opts):
    """
    Construct ``salt.minion.Minion`` in a spawn-start child process,
    bypassing the parent-class init (which needs a live event loop and
    master connection).

    This exercises exactly the body of ``Minion.__init__`` and nothing
    else; the test asserts that running that body does not touch
    ``queue.lock``.
    """
    import salt.minion
    from tests.support.mock import patch

    def _bare_super(self, opts):
        self.opts = opts

    with patch.object(salt.minion.MinionBase, "__init__", _bare_super):
        try:
            salt.minion.Minion(minion_opts, load_grains=False)
        except Exception:  # pylint: disable=broad-except
            # Minion.__init__ does a lot after the (now-removed) cleanup
            # block -- loader setup, subprocess list, periodic callbacks,
            # etc. -- and most of that trips in the stripped-down child.
            # The cleanup, if present, would have fired at the TOP of
            # __init__ before any of that failed, so a later exception
            # here does not weaken the regression check.
            pass


def test_spawn_child_minion_init_does_not_stomp_held_queue_lock(opts):
    """
    End-to-end: spawn three subprocesses that each construct a
    ``salt.minion.Minion`` and assert the parent-held ``queue.lock`` is
    still present when they finish.

    Before the fix (cleanup in ``Minion.__init__``): each spawn-start
    child deletes ``queue.lock``. The parent observes its lock file
    vanish.

    After the fix (cleanup relocated to ``prepare()``): ``Minion.__init__``
    does not touch ``queue.lock``, and the parent-held lock survives.
    """
    lock_path = salt.utils.state.queue_lock_path(opts)
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        ctx = multiprocessing.get_context("spawn")
        procs = [
            ctx.Process(target=_child_minion_init, args=(lock_path, opts))
            for _ in range(3)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=60)
            assert p.exitcode == 0, (
                f"child exited with {p.exitcode}; subprocess crashed "
                "before completing Minion.__init__"
            )
        assert os.path.exists(lock_path), (
            "queue.lock was removed by a spawn-start Minion.__init__. "
            "The cleanup must live in salt.cli.daemons.Minion.prepare(), "
            "not in Minion.__init__ (issue #70580 side-effect)."
        )
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
        if os.path.exists(lock_path):
            os.remove(lock_path)


def test_cleanup_helpers_still_work_when_called_from_daemon_context(opts):
    """
    Sanity: the SIGKILL-recovery behavior must still work. When
    ``cleanup_stale_queue_lock`` and ``cleanup_orphaned_queue_files`` are
    invoked from the CLI daemon layer, they must actually remove the
    leftover artifacts.
    """
    import time

    lock_path = salt.utils.state.queue_lock_path(opts)
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    # Write a dead PID; the cleanup path requires either a dead PID or
    # an expired empty-file grace to proceed.
    with salt.utils.files.fopen(lock_path, "w", encoding="utf-8") as fp:
        fp.write(str(2**31 - 1))
    assert os.path.exists(lock_path)
    salt.utils.state.cleanup_stale_queue_lock(opts)
    assert not os.path.exists(lock_path), (
        "cleanup_stale_queue_lock failed to remove a lock whose PID is "
        "dead. SIGKILL recovery is broken."
    )

    state_queue_dir = salt.utils.state.state_queue_dir(opts)
    os.makedirs(state_queue_dir, exist_ok=True)
    orphan = os.path.join(state_queue_dir, "running_12345.p")
    with salt.utils.files.fopen(orphan, "w", encoding="utf-8"):
        pass
    old_mtime = time.time() - 600  # 10 minutes ago
    os.utime(orphan, (old_mtime, old_mtime))
    assert os.path.exists(orphan)
    salt.utils.state.cleanup_orphaned_queue_files(opts)
    assert not os.path.exists(
        orphan
    ), "cleanup_orphaned_queue_files failed to remove an aged orphan."


def test_cleanup_helpers_do_not_remove_fresh_orphans(opts):
    """
    Companion: ``running_*.p`` files younger than the 5-minute threshold
    must be preserved -- a live job may legitimately own them.
    """
    state_queue_dir = salt.utils.state.state_queue_dir(opts)
    os.makedirs(state_queue_dir, exist_ok=True)
    fresh = os.path.join(state_queue_dir, "running_67890.p")
    with salt.utils.files.fopen(fresh, "w", encoding="utf-8"):
        pass
    salt.utils.state.cleanup_orphaned_queue_files(opts)
    assert os.path.exists(fresh), (
        "cleanup_orphaned_queue_files removed a fresh running_*.p file, "
        "which could belong to a live job."
    )


def test_cleanup_queue_state_fans_out_across_multimaster_list(tmp_path):
    """
    Regression: on a multimaster config, ``opts["master"]`` is a list.
    Each ``Minion`` instance that ``MinionManager`` spawns gets its own
    per-master ``queue_lock_path`` keyed on the single master name. The
    daemon-level cleanup must fan out across the list so each per-master
    lock path is cleaned.

    Pre-fix behavior: ``cleanup_stale_queue_lock(self.config)`` was called
    with the top-level opts whose ``master`` value was the list itself.
    ``_sanitize_master_id`` joined the list (``"m1,m2"``) and cleanup
    targeted ``queues/m1,m2/queue.lock``. The real per-master locks at
    ``queues/m1/queue.lock`` and ``queues/m2/queue.lock`` survived,
    silently losing SIGKILL recovery under multimaster.
    """
    opts = {
        "cachedir": str(tmp_path),
        "master": ["master-one", "master-two", "master-three"],
    }
    # Create a leftover lock under each per-master path. Write a
    # known-dead PID so the grace window doesn't protect them -- these
    # represent genuinely-abandoned locks from SIGKILLed prior daemons.
    per_master_locks = []
    for master in opts["master"]:
        per_master_opts = dict(opts)
        per_master_opts["master"] = master
        lock_path = salt.utils.state.queue_lock_path(per_master_opts)
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        with salt.utils.files.fopen(lock_path, "w", encoding="utf-8") as fp:
            fp.write(str(2**31 - 1))
        per_master_locks.append(lock_path)
        assert os.path.exists(lock_path)

    salt.utils.state.cleanup_queue_state(opts)

    for lock_path in per_master_locks:
        assert not os.path.exists(lock_path), (
            f"cleanup_queue_state did not remove the per-master lock "
            f"{lock_path!r}. Multimaster SIGKILL recovery is broken; the "
            "wrapper must iterate opts['master'] when it is a list."
        )


def test_cleanup_queue_state_scalar_master_still_works(tmp_path):
    """
    Companion: single-master configs (``opts["master"]`` is a string) must
    continue to route cleanup to the correct single lock path.
    """
    opts = {"cachedir": str(tmp_path), "master": "single-master"}
    lock_path = salt.utils.state.queue_lock_path(opts)
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    with salt.utils.files.fopen(lock_path, "w", encoding="utf-8") as fp:
        fp.write(str(2**31 - 1))
    salt.utils.state.cleanup_queue_state(opts)
    assert not os.path.exists(lock_path)


def test_queue_base_dir_namespaces_by_proxyid(tmp_path):
    """
    Regression: ``salt-proxy --proxyid A/B`` daemons share a default
    cachedir. Without a proxyid component in the queue path, two proxies
    against the same master collide on ``queue.lock``.

    See salt/utils/state.py:queue_base_dir -- when ``opts["proxyid"]``
    is set, it must appear in the path.
    """
    base = {"cachedir": str(tmp_path), "master": "same-master"}
    plain = salt.utils.state.queue_base_dir(base)
    with_proxy_a = salt.utils.state.queue_base_dir({**base, "proxyid": "proxy-a"})
    with_proxy_b = salt.utils.state.queue_base_dir({**base, "proxyid": "proxy-b"})
    assert with_proxy_a != with_proxy_b, (
        "queue_base_dir produced identical paths for two proxies on the "
        "same master; a cleanup from proxy-b would stomp proxy-a's lock."
    )
    assert with_proxy_a != plain, (
        "queue_base_dir for a proxy must differ from the master-only form "
        "so proxies cannot collide with a direct salt-minion on the same "
        "cachedir+master."
    )
    assert "proxy-a" in with_proxy_a
    assert "proxy-b" in with_proxy_b


def test_cleanup_stale_queue_lock_skips_live_holder(tmp_path):
    """
    Regression for SALT_KEEPALIVE respawn stomp (and any scenario where a
    cleanup fires while a live process still holds ``queue.lock``).

    The holder is identified by the PID recorded in the lock file AND
    its process start time (the process must have been running when the
    lock was written). Cleanup must skip removal when that pair matches.
    """
    opts = {"cachedir": str(tmp_path), "master": "liveness-test"}
    lock_path = salt.utils.state.queue_lock_path(opts)
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    with salt.utils.files.fopen(lock_path, "w", encoding="utf-8") as fp:
        fp.write(str(os.getpid()))  # our own PID -- guaranteed alive

    salt.utils.state.cleanup_stale_queue_lock(opts)

    assert os.path.exists(lock_path), (
        "cleanup_stale_queue_lock removed a lock whose recorded PID is "
        "alive and whose mtime is after our start time. Concurrent "
        "holders can lose their lock."
    )


def test_cleanup_stale_queue_lock_detects_pid_reuse(tmp_path):
    """
    Regression for BrianHa94's PR-review finding #3: after a SIGKILL +
    restart, the recorded PID can be reclaimed by an unrelated process.
    Pure liveness probing (``os.kill(pid, 0)``) would see the new owner
    as alive and leave the stale lock in place; the next ``wait_lock``
    would then sit on the 24 h timeout.

    Cleanup must compare the process's start time against the lock
    file's mtime: if the process started AFTER the lock was written,
    the PID has been reused and the lock is stale.
    """
    psutil = pytest.importorskip("psutil")

    opts = {"cachedir": str(tmp_path), "master": "pid-reuse-test"}
    lock_path = salt.utils.state.queue_lock_path(opts)
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    # Use our own (alive) PID so the liveness probe succeeds.
    with salt.utils.files.fopen(lock_path, "w", encoding="utf-8") as fp:
        fp.write(str(os.getpid()))
    # Backdate the lock mtime to 60 s before this process was started.
    # The PID is alive but cannot be the holder that wrote the file.
    create_time = psutil.Process(os.getpid()).create_time()
    old = create_time - 60
    os.utime(lock_path, (old, old))

    salt.utils.state.cleanup_stale_queue_lock(opts)

    assert not os.path.exists(lock_path), (
        "cleanup_stale_queue_lock treated a PID-reused holder as live. "
        "After a reboot or PID-wrap scenario the next wait_lock acquire "
        "would block up to 24 h."
    )


def test_wait_lock_survives_concurrent_removal(tmp_path):
    """
    Regression for BrianHa94's PR-review finding #2: if a concurrent
    cleanup removes the lock file while a legitimate holder has it,
    ``wait_lock``'s ``finally`` used to raise ``FileNotFoundError``,
    turning a successful state run into a traceback.

    The ``finally`` must catch ``FileNotFoundError`` and log a warning
    instead.
    """
    import threading

    lock = str(tmp_path / "concurrent.lock")
    acquired = threading.Event()
    proceed = threading.Event()
    result = []

    def hold():
        try:
            with salt.utils.files.wait_lock(lock, lock_fn=lock, timeout=10):
                acquired.set()
                proceed.wait(timeout=5)
            result.append("clean")
        except Exception as exc:  # pylint: disable=broad-except
            result.append(f"crash:{type(exc).__name__}")

    t = threading.Thread(target=hold)
    t.start()
    assert acquired.wait(timeout=5), "holder never acquired the lock"
    # Simulate a concurrent stale-lock cleanup removing the lock file
    # out from under us.
    os.remove(lock)
    proceed.set()
    t.join(timeout=5)
    assert result == [
        "clean"
    ], f"wait_lock holder crashed instead of logging and continuing: {result}"


def test_cleanup_stale_queue_lock_removes_dead_pid(tmp_path):
    """
    Companion: once the holder dies, the stale lock must get removed so
    the next acquire does not block on a ghost.
    """
    opts = {"cachedir": str(tmp_path), "master": "liveness-test"}
    lock_path = salt.utils.state.queue_lock_path(opts)
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    # PID 2^31 - 1 is above the standard pid_max on Linux; it will not
    # be a real running process on this system.
    with salt.utils.files.fopen(lock_path, "w", encoding="utf-8") as fp:
        fp.write(str(2**31 - 1))

    salt.utils.state.cleanup_stale_queue_lock(opts)

    assert not os.path.exists(lock_path), (
        "cleanup_stale_queue_lock left a lock whose recorded PID is "
        "dead. SIGKILL-recovery is broken; the next acquire will "
        "block for up to 24h on wait_lock's timeout."
    )


def test_cleanup_stale_queue_lock_grace_protects_fresh_empty_lock(tmp_path):
    """
    Microsecond-race protection: ``wait_lock`` creates the file via
    ``O_CREAT|O_EXCL`` and then writes the PID in a second syscall. A
    concurrent cleanup reading the file between those steps sees empty
    content. Treating empty as "dead, remove" would stomp the live
    acquirer -- the red-team round-2 PoC.

    Cleanup must apply ``_EMPTY_LOCK_GRACE_SECONDS`` to empty files so a
    legitimate acquirer has time to complete its PID write.
    """
    opts = {"cachedir": str(tmp_path), "master": "liveness-test"}
    lock_path = salt.utils.state.queue_lock_path(opts)
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    with salt.utils.files.fopen(lock_path, "w", encoding="utf-8"):
        pass  # fresh empty file, mtime == now

    salt.utils.state.cleanup_stale_queue_lock(opts)

    assert os.path.exists(lock_path), (
        "cleanup_stale_queue_lock removed a fresh empty lock. This is the "
        "O_EXCL-vs-PID-write race and would let two concurrent acquires "
        "both think they hold the lock."
    )


def test_cleanup_stale_queue_lock_removes_empty_legacy_lock_after_grace(tmp_path):
    """
    Pre-PID-write-era holders (or crashed acquirers that never wrote a
    PID) left empty lock files. After the grace window expires, those
    leftovers must get recovered or the next acquire blocks for 24h.
    """
    import time as _time

    opts = {"cachedir": str(tmp_path), "master": "liveness-test"}
    lock_path = salt.utils.state.queue_lock_path(opts)
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    with salt.utils.files.fopen(lock_path, "w", encoding="utf-8"):
        pass  # empty file

    # Backdate mtime past the grace window.
    old = _time.time() - salt.utils.state._EMPTY_LOCK_GRACE_SECONDS - 10
    os.utime(lock_path, (old, old))

    salt.utils.state.cleanup_stale_queue_lock(opts)

    assert not os.path.exists(lock_path)


def test_pid_is_alive_uses_psutil_wrapper():
    """
    On Windows, Python's ``os.kill(pid, 0)`` is **destructive** (it calls
    ``TerminateProcess``). Salt's cross-platform liveness probe is
    ``salt.utils.process.os_is_running`` (psutil-backed where
    available). ``_pid_is_alive`` must delegate to it.

    Behavioral check: the function must return True for the current
    process's PID (guaranteed alive) and False for a PID that cannot
    exist (above ``pid_max``). Both outcomes would be WRONG on Windows
    if the implementation called ``os.kill`` directly: the first would
    still work but the second would terminate whatever process happened
    to recycle the PID.
    """
    src = inspect.getsource(salt.utils.state._pid_is_alive)
    assert "os_is_running" in src, (
        "_pid_is_alive does not route through salt.utils.process.os_is_running. "
        "On Windows that helper must be used because Python's os.kill(pid, 0) "
        "terminates the target process."
    )
    assert salt.utils.state._pid_is_alive(os.getpid()) is True
    assert salt.utils.state._pid_is_alive(2**31 - 1) is False


def test_wait_lock_writes_pid(tmp_path):
    """
    Companion invariant for the liveness-check design:
    ``salt.utils.files.wait_lock`` must write the holder's PID so
    cleanup can probe it.
    """
    import salt.utils.files

    lock_path = str(tmp_path / "test.lock")
    with salt.utils.files.wait_lock(lock_path, lock_fn=lock_path, timeout=5):
        with salt.utils.files.fopen(lock_path, encoding="utf-8") as fp:
            content = fp.read().strip()
    assert content == str(os.getpid()), (
        f"wait_lock did not record the holder's PID (read {content!r}). "
        "Stale-lock liveness probes depend on this."
    )


def test_caller_init_invokes_queue_cleanup(tmp_path, monkeypatch):
    """
    Regression: ``salt.cli.caller.BaseCaller.__init__`` must invoke
    ``cleanup_queue_state`` so salt-call users get SIGKILL recovery.
    Without this hook, a SIGKILLed salt-call leaves ``queue.lock``
    behind and every subsequent salt-call with ``queue=<int>`` blocks
    for up to 24h on ``wait_lock``.
    """
    called = []

    def _spy(opts):
        called.append(opts.get("cachedir"))

    import salt.cli.caller
    import salt.minion

    monkeypatch.setattr(salt.utils.state, "cleanup_queue_state", _spy)
    monkeypatch.setattr(
        salt.minion, "SMinion", lambda opts: type("StubMinion", (), {})()
    )

    salt.cli.caller.BaseCaller({"cachedir": str(tmp_path), "master": "salt-call-test"})
    assert called == [str(tmp_path)], (
        "BaseCaller.__init__ did not call cleanup_queue_state. "
        "salt-call masterless has no SIGKILL recovery path."
    )
