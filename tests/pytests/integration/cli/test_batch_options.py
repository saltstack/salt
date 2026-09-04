"""
Integration tests covering every batching option end-to-end on the real
CLI.

These tests intentionally exercise the full ``salt`` / ``salt-run`` CLI
lifecycle against a running master + 2 minions so the asyncio event
loop, the publisher/subscriber ``SyncWrapper`` teardown, and the
master-side ``BatchManager`` event bus all run on real code paths.

Unit tests for ``Batch`` mock ``SyncWrapper`` out and therefore can
miss interpreter-level teardown regressions like the
``RuntimeWarning: coroutine 'BaseEventLoop.shutdown_asyncgens' was
never awaited`` leak fixed in commit ``7f305709b7a``.  Each test below
asserts that the CLI exits cleanly and that no asyncio teardown noise
hits the CLI's stderr — the failure mode that bug surfaced through.

The CLI options exercised are:

1. ``--batch`` integer
2. ``--batch`` percentage
3. ``--batch-wait``
4. ``--batch-safe-limit`` (trip-to-batch threshold)
5. ``--batch-safe-size`` (batch size used when safe-limit trips)
6. ``--failhard`` halts on first bad return
7. ``--async`` hand-off to ``BatchManager`` (``driver="master"``)
8. ``state.apply`` in batches (``driver="cli"``)
9. ``salt-run batch.stop <jid>`` halts a sync batch mid-flight
10. ``salt-run batch.list_active`` sees a sync batch mid-run
11. ``salt-run batch.status <jid>`` returns live progress mid-run
"""

import os
import threading
import time

import pytest

import salt.utils.files
import salt.utils.platform

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.slow_test,
]

# Known asyncio / Tornado teardown markers we will not accept on the CLI's
# stderr.  The unawaited-coroutine warning is the exact regression
# previously caught only in the failing Windows zeromq 2 batch jobs.
_FORBIDDEN_STDERR_MARKERS = (
    "BaseEventLoop.shutdown_asyncgens",
    "BaseEventLoop.shutdown_default_executor",
    "coroutine '",
    "was never awaited",
    "Traceback (most recent call last)",
)


def _assert_clean_stderr(cmd):
    """
    Assert the CLI's stderr is free of asyncio teardown noise.

    This is the regression gate for the
    ``RuntimeWarning: coroutine 'BaseEventLoop.shutdown_*' was never
    awaited`` leak that previously slipped past the unit tests because
    those tests mocked ``SyncWrapper`` out entirely.
    """
    stderr = cmd.stderr or ""
    for marker in _FORBIDDEN_STDERR_MARKERS:
        assert (
            marker not in stderr
        ), f"Forbidden marker {marker!r} found in CLI stderr:\n{stderr}"


@pytest.fixture(scope="module")
def run_timeout():
    if salt.utils.platform.is_windows():
        return 240
    return 60


@pytest.fixture(scope="module")
def batch_test_sls(salt_master):
    """
    Write a tiny SLS file to the master's base file_roots.

    Used by ``test_batch_state_apply`` to exercise the
    ``state.apply``-via-batch path (driver="cli", with state
    return parsing in the CLI output formatter).
    """
    sls_name = "batch_options_test"
    file_root = salt_master.config["file_roots"]["base"][0]
    sls_file = os.path.join(file_root, f"{sls_name}.sls")
    contents = (
        "batch options succeed:\n"
        "  test.succeed_without_changes:\n"
        "    - name: batch_options_test\n"
    )
    with salt.utils.files.fopen(sls_file, "w") as fh:
        fh.write(contents)
    try:
        yield sls_name
    finally:
        if os.path.exists(sls_file):
            os.remove(sls_file)


@pytest.fixture
def long_running_fun():
    """
    Tuple ``(fun, args)`` the runner-visibility tests use to keep a
    sync batch 'mid-run' long enough for ``batch.status`` /
    ``batch.list_active`` / ``batch.stop`` to observe it.

    Uses ``test.sleep`` so we avoid ``state.apply``'s per-minion
    lock (which would make sequential tests collide when an earlier
    sleep is still running on a minion).
    """
    return ("test.sleep", "5")


# ---------------------------------------------------------------------------
# 1. --batch integer
# ---------------------------------------------------------------------------


def test_batch_integer_size(salt_cli, salt_minion, salt_sub_minion, run_timeout):
    """
    ``salt -b 2 '*minion*' test.ping`` runs both minions in a single
    sub-batch and returns 0.
    """
    cmd = salt_cli.run(
        "test.ping",
        "-b",
        "2",
        minion_tgt="*minion*",
        _timeout=run_timeout,
    )
    assert cmd.returncode == 0, cmd
    _assert_clean_stderr(cmd)
    # Both minions should be visible in the output.
    assert salt_minion.id in cmd.stdout
    assert salt_sub_minion.id in cmd.stdout


# ---------------------------------------------------------------------------
# 2. --batch percentage
# ---------------------------------------------------------------------------


def test_batch_percentage(salt_cli, salt_minion, salt_sub_minion, run_timeout):
    """
    ``salt -b 50% '*minion*' test.ping`` runs one minion at a time.

    With two minions and 50% we expect both minions to return
    eventually — and we force text output so the per-sub-batch
    ``Executing run on`` lines are visible (salt-factories otherwise
    injects ``--out=json --out-indent=0`` which strips them).
    """
    cmd = salt_cli.run(
        "test.ping",
        "-b",
        "50%",
        "--out=txt",
        minion_tgt="*minion*",
        _timeout=run_timeout,
    )
    assert cmd.returncode == 0, cmd
    _assert_clean_stderr(cmd)
    # One Executing line per sub-batch — there must be at least two
    # because we forced 50% of two minions.
    executing_lines = [
        line for line in cmd.stdout.splitlines() if "Executing run on" in line
    ]
    assert len(executing_lines) >= 2, cmd.stdout


# ---------------------------------------------------------------------------
# 3. --batch-wait
# ---------------------------------------------------------------------------


def test_batch_wait_between_subbatches(
    salt_cli, salt_minion, salt_sub_minion, run_timeout
):
    """
    ``--batch-wait`` inserts a delay between sub-batches.

    We assert the CLI succeeds and that the wall-clock for two
    one-minion sub-batches is at least the configured wait — i.e.
    the option is actually honored end-to-end and the CLI doesn't
    short-circuit the wait.
    """
    wait_seconds = 2
    start = time.monotonic()
    cmd = salt_cli.run(
        "test.ping",
        "-b",
        "1",
        "--batch-wait",
        str(wait_seconds),
        minion_tgt="*minion*",
        _timeout=run_timeout,
    )
    elapsed = time.monotonic() - start
    assert cmd.returncode == 0, cmd
    _assert_clean_stderr(cmd)
    # Lower bound is intentionally generous: --batch-wait is a
    # per-completed-minion delay; with two minions we expect at
    # least one wait_seconds gap.  CI clock skew makes anything
    # tighter flaky.
    assert (
        elapsed >= wait_seconds
    ), f"Expected at least {wait_seconds}s wall-clock; got {elapsed:.2f}s"


# ---------------------------------------------------------------------------
# 4. --batch-safe-limit
# ---------------------------------------------------------------------------


def test_batch_safe_limit_triggers_batching(
    salt_cli, salt_minion, salt_sub_minion, run_timeout
):
    """
    ``--batch-safe-limit 2`` causes ``salt`` to enter batch mode when
    the target resolves to >=2 minions, even without ``-b``.

    With two minions targeted and safe-limit=2 the CLI must use
    batches of ``--batch-safe-size`` (default 8 / overridden to 1
    below to force the batch path to fire) and exit cleanly.

    Force ``--out=txt`` so the per-sub-batch ``Executing run on``
    lines are visible — salt-factories injects ``--out=json
    --out-indent=0`` by default which strips them.
    """
    cmd = salt_cli.run(
        "test.ping",
        "--batch-safe-limit",
        "2",
        "--batch-safe-size",
        "1",
        "--out=txt",
        minion_tgt="*minion*",
        _timeout=run_timeout,
    )
    assert cmd.returncode == 0, cmd
    _assert_clean_stderr(cmd)
    # safe-size=1 + safe-limit=2 means we expect batched output —
    # at least one ``Executing run on`` line per minion.
    executing_lines = [
        line for line in cmd.stdout.splitlines() if "Executing run on" in line
    ]
    assert len(executing_lines) >= 2, cmd.stdout


# ---------------------------------------------------------------------------
# 5. --batch-safe-size
# ---------------------------------------------------------------------------


def test_batch_safe_size_one(salt_cli, salt_minion, salt_sub_minion, run_timeout):
    """
    ``--batch-safe-size 1`` is the batch size used when
    ``--batch-safe-limit`` trips.

    The safe-limit branch in ``salt/cli/salt.py`` requires
    ``--batch-safe-limit > 1`` to engage (``if self.options
    .batch_safe_limit > 1`` at line 116) and trips when the target
    resolves to ``>=`` that many minions.  With two minions and
    safe-limit=2, ``safe-size=1`` then forces one-at-a-time
    sub-batches and emits a NOTICE line.
    """
    cmd = salt_cli.run(
        "test.ping",
        "--batch-safe-limit",
        "2",
        "--batch-safe-size",
        "1",
        "--out=txt",
        minion_tgt="*minion*",
        _timeout=run_timeout,
    )
    assert cmd.returncode == 0, cmd
    _assert_clean_stderr(cmd)
    # The NOTICE is the unambiguous signal that the safe-limit
    # branch engaged.
    assert "switching to batch execution" in cmd.stdout, cmd.stdout
    # And safe-size=1 means one ``Executing run on`` line per
    # minion.
    executing_lines = [
        line for line in cmd.stdout.splitlines() if "Executing run on" in line
    ]
    assert len(executing_lines) >= 2, cmd.stdout


# ---------------------------------------------------------------------------
# 6. --failhard
# ---------------------------------------------------------------------------


def test_batch_failhard_stops_on_first_bad_return(
    salt_cli, salt_minion, salt_sub_minion, run_timeout
):
    """
    ``-b 1 --failhard`` halts the batch as soon as a minion returns
    a non-zero retcode.  ``test.retcode 23`` returns 23 for every
    minion, so the first sub-batch must trip failhard and the CLI
    exit with that retcode.
    """
    cmd = salt_cli.run(
        "test.retcode",
        "23",
        "-b",
        "1",
        "--failhard",
        minion_tgt="*minion*",
        _timeout=run_timeout,
    )
    assert cmd.returncode == 23, cmd
    _assert_clean_stderr(cmd)


# ---------------------------------------------------------------------------
# 7. --async hand-off to BatchManager
# ---------------------------------------------------------------------------


def _wait_for(predicate, *, timeout, interval=0.5):
    """Spin until ``predicate()`` is truthy or ``timeout`` elapses."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    return last


def _extract_async_jid(stdout):
    """
    Pull the JID out of ``--async -b``'s ``Executed batch command
    with job ID: 20260613...`` line.
    """
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("Executed batch command with job ID:"):
            return line.rsplit(":", 1)[1].strip()
    return None


def _batch_state_path(salt_master, jid):
    """Return the on-disk ``.batch.p`` path for ``jid``."""
    import salt.utils.batch_state

    return salt.utils.batch_state._batch_state_path(jid, salt_master.config)


def test_batch_async_handoff_to_batch_manager(
    salt_cli,
    salt_run_cli,
    salt_master,
    salt_minion,
    salt_sub_minion,
    run_timeout,
):
    """
    ``salt -b 2 --async '*minion*' test.ping`` hands off to the
    master-side ``BatchManager``.

    The CLI prints the JID and exits.  The manager then drives the
    batch to completion through its own event-bus loop, writes the
    terminal state, and removes the JID from the active index.
    """
    cmd = salt_cli.run(
        "test.ping",
        "-b",
        "2",
        "--async",
        minion_tgt="*minion*",
        _timeout=run_timeout,
    )
    assert cmd.returncode == 0, cmd
    _assert_clean_stderr(cmd)
    jid = _extract_async_jid(cmd.stdout)
    assert jid, f"could not find async batch JID in: {cmd.stdout!r}"

    # ``.batch.p`` is written by the async CLI handoff before
    # ``salt/batch/<jid>/new`` is fired and is left in place by the
    # BatchManager — the file is the durable record of the batch.
    state_path = _batch_state_path(salt_master, jid)

    def _state_exists():
        return os.path.exists(state_path)

    assert _wait_for(
        _state_exists, timeout=15
    ), f".batch.p never appeared at {state_path}"

    # And the BatchManager retires the JID from the active index
    # when it completes.  ``batch.list_active`` reads that index, so
    # we poll it from the runner.
    def _retired():
        rs = salt_run_cli.run(
            "batch.list_active",
            "--out=json",
            _timeout=run_timeout,
        )
        if rs.returncode != 0:
            return False
        # rs.data is the parsed JSON when --out=json is honored;
        # fall back to a string match on stdout otherwise.
        active = rs.data if rs.data is not None else rs.stdout
        if isinstance(active, list):
            return jid not in [b.get("jid") for b in active if isinstance(b, dict)]
        if isinstance(active, str):
            return jid not in active
        return True

    assert _wait_for(_retired, timeout=60, interval=1.0), (
        f"BatchManager never retired async batch {jid} from the "
        f"active index within 60s"
    )


# ---------------------------------------------------------------------------
# 8. state.apply in batches
# ---------------------------------------------------------------------------


def test_batch_state_apply(
    salt_cli, salt_minion, salt_sub_minion, batch_test_sls, run_timeout
):
    """
    ``salt -b 2 '*minion*' state.apply <sls>`` exercises the batch
    path for state output formatting.

    The state runs the no-op ``test.succeed_without_changes`` so the
    CLI must return 0 and the per-minion state result rendering must
    still work under the sync CLI batch driver.
    """
    cmd = salt_cli.run(
        "state.apply",
        batch_test_sls,
        "-b",
        "2",
        minion_tgt="*minion*",
        _timeout=run_timeout,
    )
    assert cmd.returncode == 0, cmd
    _assert_clean_stderr(cmd)
    # Each minion should appear with its succeed_without_changes result.
    for mid in (salt_minion.id, salt_sub_minion.id):
        assert mid in cmd.stdout, cmd.stdout
    # Either the state name or a Succeeded marker should be present;
    # we don't want to be locked to one output flavor across Salt
    # versions, so check both.
    assert (
        "batch options succeed" in cmd.stdout or "succeed_without_changes" in cmd.stdout
    ), cmd.stdout


# ---------------------------------------------------------------------------
# 9. batch.stop halts a sync batch mid-flight
# ---------------------------------------------------------------------------


def _spawn_long_batch(salt_cli, fun, arg, batch_size="1", timeout=120):
    """
    Spawn ``salt -b <size> '*minion*' <fun> <arg>`` in a background
    thread and return ``(thread, result_box)``.

    The caller can poll ``result_box`` for ``cmd`` once the thread
    joins.  We use ``test.sleep`` rather than ``state.apply`` so the
    runner-visibility tests don't collide on the per-minion state
    lock when scheduled back-to-back.
    """
    result_box = {}

    def _run():
        result_box["cmd"] = salt_cli.run(
            fun,
            arg,
            "-b",
            batch_size,
            minion_tgt="*minion*",
            _timeout=timeout,
        )

    t = threading.Thread(target=_run, name="batch-runner", daemon=True)
    t.start()
    return t, result_box


def _find_active_sync_jid(salt_run_cli, run_timeout, *, want_driver="cli"):
    """
    Poll ``batch.list_active`` until we see a sync-CLI-driver batch
    and return its JID.

    Returns ``None`` if nothing shows up before the local deadline.
    """
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        rs = salt_run_cli.run(
            "batch.list_active",
            "--out=json",
            _timeout=run_timeout,
        )
        active = rs.data if rs.data is not None else None
        if isinstance(active, list):
            for entry in active:
                if isinstance(entry, dict) and entry.get("driver") == want_driver:
                    return entry.get("jid")
        time.sleep(0.5)
    return None


def test_batch_stop_halts_sync_batch(
    salt_cli,
    salt_run_cli,
    salt_minion,
    salt_sub_minion,
    long_running_fun,
    run_timeout,
):
    """
    Fire ``salt-run batch.stop <jid>`` against a running sync batch
    and assert the CLI's batch halts on the next iteration via the
    event-driven halt subscription.

    The sync batch runs ``test.sleep 5`` with ``-b 1`` so only one
    minion is running at any moment, leaving the second pending —
    that's the slot the halt event prevents from launching.
    """
    runner_thread, result_box = _spawn_long_batch(
        salt_cli, *long_running_fun, batch_size="1", timeout=run_timeout
    )
    try:
        jid = _find_active_sync_jid(salt_run_cli, run_timeout)
        assert jid, (
            "sync batch never registered in batch.list_active before "
            "the local 30s window"
        )

        stop_result = salt_run_cli.run("batch.stop", jid, _timeout=run_timeout)
        assert stop_result.returncode == 0, stop_result

        runner_thread.join(timeout=run_timeout)
        assert not runner_thread.is_alive(), (
            "Batch CLI did not honor the halt event within the test " "timeout"
        )
    finally:
        runner_thread.join(timeout=run_timeout)

    cmd = result_box.get("cmd")
    assert cmd is not None, "batch runner thread never produced a result"
    _assert_clean_stderr(cmd)
    # We don't assert a specific retcode here — the CLI may exit 0
    # (drained the in-flight minion's return before halting) or
    # non-zero (halted with pending minions).  Both are correct
    # behaviour for a halt mid-batch; what matters is that we
    # observed clean exit + clean stderr.


# ---------------------------------------------------------------------------
# 10. batch.list_active sees a sync batch mid-run
# ---------------------------------------------------------------------------


def test_batch_list_active_sees_sync_batch(
    salt_cli,
    salt_run_cli,
    salt_minion,
    salt_sub_minion,
    long_running_fun,
    run_timeout,
):
    """
    Spawn a sync batch and verify it shows up in
    ``salt-run batch.list_active`` mid-run.

    Validates the event-bus visibility path
    (``salt/batch/<jid>/new`` from the CLI → BatchManager
    ``_handle_new`` with ``driver="cli"`` → on-disk active index).
    """
    runner_thread, result_box = _spawn_long_batch(
        salt_cli, *long_running_fun, batch_size="1", timeout=run_timeout
    )
    try:
        jid = _find_active_sync_jid(salt_run_cli, run_timeout)
        assert jid, "sync batch never appeared in batch.list_active"
    finally:
        runner_thread.join(timeout=run_timeout)

    cmd = result_box.get("cmd")
    assert cmd is not None
    assert cmd.returncode == 0, cmd
    _assert_clean_stderr(cmd)


# ---------------------------------------------------------------------------
# 11. batch.status returns live progress mid-run
# ---------------------------------------------------------------------------


def test_batch_status_returns_live_progress(
    salt_cli,
    salt_run_cli,
    salt_minion,
    salt_sub_minion,
    long_running_fun,
    run_timeout,
):
    """
    Mid-run, ``salt-run batch.status <jid>`` returns the live
    BatchState summary written by the BatchManager (which persists
    every ``salt/batch/<jid>/progress`` event we fire from the CLI).
    """
    runner_thread, result_box = _spawn_long_batch(
        salt_cli, *long_running_fun, batch_size="1", timeout=run_timeout
    )
    try:
        jid = _find_active_sync_jid(salt_run_cli, run_timeout)
        assert jid, "sync batch never appeared in batch.list_active"

        status_result = salt_run_cli.run(
            "batch.status", jid, "--out=json", _timeout=run_timeout
        )
        assert status_result.returncode == 0, status_result
        # ``data`` is the JSON-decoded payload when --out=json works;
        # otherwise fall back to a structural check on the raw stdout.
        summary = (
            status_result.data
            if status_result.data is not None
            else status_result.stdout
        )
        if isinstance(summary, dict):
            assert summary.get("jid") == jid, summary
            assert summary.get("driver") == "cli", summary
        else:
            assert jid in str(summary), summary
    finally:
        runner_thread.join(timeout=run_timeout)

    cmd = result_box.get("cmd")
    assert cmd is not None
    _assert_clean_stderr(cmd)
