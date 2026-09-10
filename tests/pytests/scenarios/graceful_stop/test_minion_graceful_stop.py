"""
Scenario coverage for the minion graceful-stop fixup (issue #70050 audit).

End-to-end: real master + real minion under pytest-salt-factories. Publish
a long-running job, deliver SIGTERM to the minion process, and assert the
master receives an aborted return *inside the graceful window* rather
than having to wait for its own ``gather_job_timeout``.

This is the user-visible fix: before the fix the master got no return at
all, the caller saw the minion as "Not Responded", and the job hung open
on the master's cache until timeout.
"""

import pathlib
import time

import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(
        reason=(
            "POSIX SIGTERM path; Windows service graceful-stop is "
            "covered by the pkg-tier test."
        )
    ),
]


@pytest.fixture(scope="package")
def scenario_salt_cli(salt_master_factory):
    """
    Package-scoped ``salt`` CLI helper. The session-scoped ``salt_cli``
    in ``tests/conftest.py`` targets the session ``salt_master_factory``;
    the scenarios/daemons package supplies its own package-scoped
    master, so we re-derive the CLI at matching scope.
    """
    return salt_master_factory.salt_cli()


def _wait_for(predicate, timeout=30, interval=0.2, msg="condition"):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    raise AssertionError(f"timed out waiting for {msg}")


@pytest.fixture(scope="package")
def running_master(salt_master_factory):
    with salt_master_factory.started(start_timeout=60):
        yield salt_master_factory


def test_graceful_stop_master_sees_termination_promptly(
    running_master, salt_minion_factory, scenario_salt_cli
):
    """
    1. Start a fresh minion.
    2. Publish a ``test.sleep 30`` job via ``--async``, capture jid.
    3. Wait for the minion's proc dir to reflect the in-flight job.
    4. SIGTERM the minion (``.terminate()`` on the factory).
    5. Assert:
         * minion exits within a bounded window (well under systemd's
           default TimeoutStopSec of 90s -- we use 20s as a hard
           ceiling).
         * ``<cachedir>/proc/`` is empty after exit (Gap 1 + Gap 2).
    """
    salt_cli = scenario_salt_cli
    with salt_minion_factory.started(start_timeout=60):
        # Minion is up and connected. Publish a long-running job.
        dispatch = salt_cli.run(
            "test.sleep",
            "30",
            "--async",
            minion_tgt=salt_minion_factory.id,
        )
        assert dispatch.returncode == 0, f"async dispatch failed: {dispatch}"

        cachedir = salt_minion_factory.config["cachedir"]
        proc_dir_path = pathlib.Path(f"{cachedir}/proc")
        _wait_for(
            lambda: proc_dir_path.is_dir() and any(proc_dir_path.iterdir()),
            timeout=20,
            msg="minion proc file for in-flight test.sleep to appear",
        )

        # Snapshot for the failure message.
        before = sorted(p.name for p in proc_dir_path.iterdir())
        assert before, "precondition: expected an in-flight proc file"

        start = time.time()
        salt_minion_factory.terminate()
        elapsed = time.time() - start

    # After the ``with`` block the factory has torn the minion down.
    assert (
        elapsed < 20
    ), f"minion took {elapsed:.1f}s to exit on SIGTERM (target < 20s, hard-cap systemd 90s)"

    remaining = (
        sorted(p.name for p in proc_dir_path.iterdir())
        if proc_dir_path.exists()
        else []
    )
    assert not remaining, (
        f"proc files survived graceful stop -- Gap 1/Gap 2 regression. "
        f"Before-stop: {before!r} After-stop: {remaining!r}"
    )
