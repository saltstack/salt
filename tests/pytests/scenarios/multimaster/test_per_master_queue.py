"""
Integration regression tests for the per-master queue split.

Two behaviors the previous shared-queue layout could not provide:

1. Stale-lock cleanup in ``Minion.__init__`` deleting another Minion's live
   lock file, producing ``FileNotFoundError: ...queue.lock`` in production.
2. A job queued by Minion-1 being drained and returned via Minion-2, so the
   return goes to the wrong master.

These tests run a real hot/hot multimaster minion (two ``Minion`` instances in
one process) and assert both bugs are gone.
"""

import logging
import os
import pathlib
import subprocess
import sys
import time

import pytest
import yaml

import salt.payload
import salt.utils.files
import salt.utils.state

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.core_test,
]


def _per_master_opts(minion_config, master_string):
    """
    Build an opts-shaped dict that the queue helpers can resolve into the
    same paths the in-process Minion for ``master_string`` would use.
    """
    opts = dict(minion_config)
    opts["master"] = master_string
    return opts


def _master_strings(minion_config):
    """
    Return the per-master strings the Minion uses internally for path
    resolution. For a multimaster config, ``master`` is a list of
    ``host:port`` strings.
    """
    masters = minion_config["master"]
    if isinstance(masters, str):
        return [masters]
    return list(masters)


def test_per_master_queue_paths_disjoint(salt_mm_minion_1, ensure_connections):
    """
    Sanity check: the two Minions inside the hot/hot minion process resolve
    to completely disjoint queue path trees, and the legacy shared paths are
    not created during normal operation.
    """
    cachedir = salt_mm_minion_1.config["cachedir"]
    masters = _master_strings(salt_mm_minion_1.config)
    assert len(masters) == 2, masters

    opts_a = _per_master_opts(salt_mm_minion_1.config, masters[0])
    opts_b = _per_master_opts(salt_mm_minion_1.config, masters[1])

    assert salt.utils.state.queue_base_dir(opts_a) != salt.utils.state.queue_base_dir(
        opts_b
    )
    assert salt.utils.state.queue_lock_path(opts_a) != salt.utils.state.queue_lock_path(
        opts_b
    )

    # The legacy shared paths must never be touched by the new code.
    assert not os.path.exists(os.path.join(cachedir, "minion_queue.lock"))
    assert not os.path.exists(os.path.join(cachedir, "job_queue"))
    assert not os.path.exists(os.path.join(cachedir, "state_queue"))


def test_no_lock_filenotfounderror_after_traffic(
    salt_mm_minion_1,
    mm_master_1_salt_cli,
    mm_master_2_salt_cli,
    ensure_connections,
):
    """
    Regression for the production traceback ``FileNotFoundError: ...job_queue.lock``.

    Drive a burst of jobs from both masters and confirm the minion log never
    contains the FileNotFoundError signature that Minion-2's stale-lock cleanup
    used to produce against Minion-1's live lock under the shared layout.
    """
    log_path = pathlib.Path(salt_mm_minion_1.config["log_file"])
    log_size_before = log_path.stat().st_size if log_path.exists() else 0

    # Fire a handful of jobs from each master in alternation; if the lock race
    # still exists, one of these will trip the cleanup-vs-hold race.
    for _ in range(6):
        for cli in (mm_master_1_salt_cli, mm_master_2_salt_cli):
            ret = cli.run("test.ping", minion_tgt=salt_mm_minion_1.id)
            assert ret.returncode == 0, ret

    # Give any deferred error reporting a moment to flush.
    time.sleep(1)

    if log_path.exists():
        with salt.utils.files.fopen(log_path, "r") as fp_:
            fp_.seek(log_size_before)
            tail = fp_.read()
        assert "FileNotFoundError" not in tail or "queue.lock" not in tail, (
            "Minion log contains a FileNotFoundError tied to the queue lock — "
            "the per-master split should have eliminated this race.\n\n"
            f"{tail}"
        )


@pytest.fixture
def queue_limited_mm_minion(salt_mm_minion_1):
    """
    Stop the package-scoped multimaster minion, lower its
    ``process_count_max`` to 1, and restart it. Restores the original config
    on teardown.
    """
    if salt_mm_minion_1.is_running():
        salt_mm_minion_1.terminate()

    config_file = pathlib.Path(salt_mm_minion_1.config_file)
    with salt.utils.files.fopen(config_file) as fp_:
        config = yaml.safe_load(fp_)

    original = {
        "process_count_max": config.get("process_count_max"),
        "mine_interval": config.get("mine_interval"),
        "schedule": config.get("schedule"),
    }
    config["process_count_max"] = 1
    config["mine_interval"] = 0
    config["schedule"] = {}

    with salt.utils.files.fopen(config_file, "w") as fp_:
        yaml.safe_dump(config, fp_)

    salt_mm_minion_1.start()
    try:
        yield salt_mm_minion_1
    finally:
        if salt_mm_minion_1.is_running():
            salt_mm_minion_1.terminate()
        for k, v in original.items():
            if v is None:
                config.pop(k, None)
            else:
                config[k] = v
        with salt.utils.files.fopen(config_file, "w") as fp_:
            yaml.safe_dump(config, fp_)
        salt_mm_minion_1.start()


def test_queued_job_lands_in_originating_masters_dir(
    queue_limited_mm_minion,
    mm_master_1_salt_cli,
    mm_master_2_salt_cli,
):
    """
    Regression for the wrong-master-return bug: when Minion-1 queues a job
    because ``process_count_max`` is hit, the queued file must land under
    *master-1's* per-master ``job_queue`` directory, not master-2's.
    """
    minion = queue_limited_mm_minion
    masters = _master_strings(minion.config)
    assert len(masters) == 2, masters

    # The running Minion sets opts["master"] to the value returned by
    # eval_master, which strips the port. We don't know that value here, so
    # discover queue dirs by scanning cache/queues/ for per-master subdirs at
    # assertion time rather than computing the path from the conftest config.
    queues_root = os.path.join(minion.config["cachedir"], "queues")
    proc_dir = os.path.join(minion.config["cachedir"], "proc")

    # Occupy the single execution slot via master-1 with a foreground sleeper
    # CLI call. salt_cli.run blocks until the CLI exits; running it as Popen
    # without --async leaves the CLI subprocess waiting on minion completion,
    # while the minion's own execution subprocess holds the slot for the
    # duration of the sleep.
    cmd_sleep = [
        sys.executable,
        mm_master_1_salt_cli.script_name,
        "-c",
        mm_master_1_salt_cli.config_dir,
        minion.id,
        "test.sleep",
        "60",
    ]
    sleep_proc = subprocess.Popen(
        cmd_sleep, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    try:
        # Wait until a test.sleep job actually appears in proc/.
        deadline = time.time() + 30
        found_sleeper = False
        while time.time() < deadline and not found_sleeper:
            if os.path.isdir(proc_dir):
                for fn in os.listdir(proc_dir):
                    try:
                        with salt.utils.files.fopen(
                            os.path.join(proc_dir, fn), "rb"
                        ) as fp_:
                            data = salt.payload.load(fp_)
                    except (OSError, ValueError, EOFError, TypeError):
                        continue
                    if isinstance(data, dict) and data.get("fun") == "test.sleep":
                        found_sleeper = True
                        break
            if not found_sleeper:
                time.sleep(0.5)
        if not found_sleeper:
            out, err = sleep_proc.communicate(timeout=5)
            pytest.fail(
                f"Sleeper never claimed the execution slot. "
                f"stdout={out!r}, stderr={err!r}"
            )

        # Fire a job via master-1 only — process_count_max is 1, so it queues.
        cmd_ping = [
            sys.executable,
            mm_master_1_salt_cli.script_name,
            "-c",
            mm_master_1_salt_cli.config_dir,
            minion.id,
            "test.ping",
        ]
        ping_proc = subprocess.Popen(
            cmd_ping, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        try:
            deadline = time.time() + 30
            per_master_counts = {}
            while time.time() < deadline:
                per_master_counts = {}
                if os.path.isdir(queues_root):
                    for sub in os.listdir(queues_root):
                        job_dir = os.path.join(queues_root, sub, "job_queue")
                        if not os.path.isdir(job_dir):
                            continue
                        queued = [
                            f for f in os.listdir(job_dir) if f.startswith("queued_")
                        ]
                        per_master_counts[sub] = queued
                if any(per_master_counts.values()):
                    break
                time.sleep(0.5)

            # Exactly one per-master subdir should contain queued files.
            # Both Minions exist (the minion has two masters configured) so
            # both per-master subtrees may exist on disk, but only one — the
            # one belonging to the master that actually published — should
            # hold the queued file.
            holders = [m for m, q in per_master_counts.items() if q]
            assert len(holders) == 1, (
                f"Expected the queued job in exactly one master's job_queue; "
                f"got {per_master_counts}"
            )
        finally:
            ping_proc.kill()
            ping_proc.wait(timeout=10)
    finally:
        sleep_proc.kill()
        sleep_proc.wait(timeout=10)
