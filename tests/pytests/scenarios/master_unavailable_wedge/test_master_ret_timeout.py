"""
Scenario reproducing the salt-minion pyzmq ``Context.__del__`` finalizer
wedge that appears in the wild when a salt-minion loses its master's
ReqServer while background events keep firing.  Log sequence and shape
observed on VCF Ops mgmt-vc / sddc-manager / ops / ops-collector:

    ERROR salt.minion: Minion unable to successfully connect to a Salt Master.
    ERROR salt.transport.zeromq: Request timed out while waiting for a response. reconnecting.
    ERROR salt.transport.zeromq: Request timed out while waiting for a response. reconnecting.
    ... (repeating, ~1/minute)
    WARNING salt.transport.tcp: unclosed publish server <salt.transport.tcp.PublishServer object at 0x...>
    WARNING salt.utils.asynchronous: unclosed SyncWrapper for cls=<class 'salt.transport.tcp._TCPPubServerPublisher'>; call ``close()`` or use as a context manager
    WARNING salt.transport.tcp: unclosed publisher client <salt.transport.tcp._TCPPubServerPublisher object at 0x...>
    ... (repeating)
    ERROR salt.minion: Error dispatching event. Message timed out
    <silence -- MainThread wedged in libzmq zmq_ctx_term()>

Test flow:
    1. Bring up a real salt-master + salt-minion via saltfactories
       (master started by the module-scope fixture, minion started
       inside the test body).
    2. Baseline test.ping to confirm auth + connectivity.
    3. Terminate the master.  Minion's REQ channel starts timing out.
    4. Under the aggressive ``mine_interval`` / ``grains_refresh_every``
       set in the conftest, the minion fires enough REQ churn to
       eventually leak a ``zmq.Context`` inside an asyncio callback.
       That callback GC-triggers ``Context.__del__`` -> ``destroy()`` ->
       ``socket.close()`` -> libzmq ``zmq_ctx_term()`` and freezes
       MainThread.
    5. Detect the wedge by polling ``/proc/<pid>/status`` for
       ``voluntary_ctxt_switches``.  If the counter does not advance
       for several seconds while the minion is supposedly running,
       MainThread is in an uninterruptable C blocking call -- the
       wedge signature.

Marked ``slow_test`` because the wedge is timing-dependent; the test
waits up to ``WEDGE_TIMEOUT_S`` for the freeze to fire.  On the current
salt + pyzmq 27.1.0 codebase the wedge is expected to fire; the test is
marked ``xfail(strict=True)`` so it flips red when the transport fix
lands.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import pytest

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skipif(
        sys.platform != "linux",
        reason="Wedge detection uses /proc/<pid>/status; Linux-only.",
    ),
]

# Total time the test will wait for the wedge to fire after the master
# is terminated.  In the wild it can take 30+ minutes on a quiet
# appliance; the aggressive mine_interval + short request_channel_timeout
# in conftest.py bring it down to a few minutes.
WEDGE_TIMEOUT_S = 6 * 60

# Polling cadence for the wedge detector.
POLL_INTERVAL_S = 5

# Number of consecutive POLL_INTERVAL_S windows with zero
# voluntary_ctxt_switches to confirm the wedge (guards against transient
# scheduler quiescence).
WEDGE_CONFIRM_WINDOWS = 3


def _voluntary_ctxt_switches(pid: int) -> int:
    """Read the voluntary_ctxt_switches counter from /proc/<pid>/status.

    A healthy salt-minion issues 50-150 voluntary context switches per
    second (each blocking syscall counts as one).  A minion wedged
    inside ``zmq_ctx_term()`` issues zero -- MainThread is in an
    uninterruptable C call.
    """
    for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
        if line.startswith("voluntary_ctxt_switches:"):
            return int(line.split()[1])
    raise RuntimeError(f"voluntary_ctxt_switches not found for pid {pid}")


def _find_mpm_pid(minion_parent_pid: int) -> int:
    """Given the salt-minion parent PID (from saltfactories), find the
    MultiMinionProcessManager child that runs the ioloop.  That child
    is the one that wedges.

    Falls back to the parent PID if no matching child is found (single-
    process minion configs).
    """
    proc_children = Path(f"/proc/{minion_parent_pid}/task/{minion_parent_pid}/children")
    if proc_children.exists():
        for tok in proc_children.read_text(encoding="utf-8").split():
            try:
                child_pid = int(tok)
            except ValueError:
                continue
            cmdline_path = Path(f"/proc/{child_pid}/cmdline")
            if not cmdline_path.exists():
                continue
            cmdline = (
                cmdline_path.read_bytes()
                .replace(b"\x00", b" ")
                .decode(errors="replace")
            )
            if "MinionProcessManager" in cmdline:
                return child_pid
    return minion_parent_pid


def _wait_for_wedge(mpm_pid: int, deadline: float) -> tuple[bool, str]:
    """Poll voluntary_ctxt_switches until either it stops advancing
    (wedge fired) or the deadline expires.

    Returns (wedged, reason).
    """
    zero_windows = 0
    last_count = _voluntary_ctxt_switches(mpm_pid)
    while time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL_S)
        try:
            current = _voluntary_ctxt_switches(mpm_pid)
        except FileNotFoundError:
            return False, f"minion pid {mpm_pid} disappeared (process died)"
        delta = current - last_count
        log.info(
            "wedge probe: voluntary_ctxt_switches delta = %d over %ds (mpm=%d)",
            delta,
            POLL_INTERVAL_S,
            mpm_pid,
        )
        if delta == 0:
            zero_windows += 1
            if zero_windows >= WEDGE_CONFIRM_WINDOWS:
                return True, (
                    f"voluntary_ctxt_switches did not advance for "
                    f"{WEDGE_CONFIRM_WINDOWS * POLL_INTERVAL_S}s -- "
                    f"MainThread is in an uninterruptable C blocking "
                    f"call (zmq_ctx_term)."
                )
        else:
            zero_windows = 0
        last_count = current
    return False, f"deadline reached after {WEDGE_TIMEOUT_S}s without wedge"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Reproducer of the field-observed salt-minion wedge: when the "
        "master's ReqServer is unreachable and the minion's scheduled "
        "REQ churn keeps firing, a leaked ``zmq.Context`` in an asyncio "
        "callback triggers ``Context.__del__ -> destroy() -> "
        "socket.close()`` which blocks in libzmq ``zmq_ctx_term()``.  "
        "When the caller-side fix (explicit "
        "``context.destroy(linger=0)`` on every close path, and "
        "``channel.close()`` before drop) is in place, this test flips "
        "to passing and ``strict=True`` fails it to signal the "
        "maintainer to remove the marker."
    ),
)
@pytest.mark.timeout(WEDGE_TIMEOUT_S + 120)
def test_master_terminated_minion_wedges_in_zmq_ctx_term(
    salt_master, salt_minion, caplog
):
    """Full-scenario reproducer: real master+minion, terminate the
    master mid-run, wait for the minion to wedge."""
    with salt_minion.started(start_timeout=180):
        # ------------------------------------------------------------
        # Step 1: baseline -- prove the pair is healthy before we start
        # breaking things.
        # ------------------------------------------------------------
        cli = salt_master.salt_cli(timeout=60)
        ret = cli.run("test.ping", minion_tgt=salt_minion.id)
        assert (
            ret.returncode == 0
        ), f"baseline test.ping failed before master termination: {ret}"
        assert ret.data is True

        minion_parent_pid = salt_minion.impl._terminal.pid  # noqa: SLF001
        mpm_pid = _find_mpm_pid(minion_parent_pid)
        log.info(
            "baseline healthy: master pid=%s minion parent pid=%s mpm pid=%s",
            salt_master.impl._terminal.pid,  # noqa: SLF001
            minion_parent_pid,
            mpm_pid,
        )

        baseline_ctxt = _voluntary_ctxt_switches(mpm_pid)
        time.sleep(2)
        healthy_ctxt = _voluntary_ctxt_switches(mpm_pid)
        healthy_delta = healthy_ctxt - baseline_ctxt
        log.info(
            "baseline voluntary_ctxt_switches delta over 2s = %d "
            "(healthy expected: >5)",
            healthy_delta,
        )
        assert healthy_delta > 5, (
            f"minion appears unhealthy even before we terminated the "
            f"master: voluntary_ctxt_switches delta = {healthy_delta} "
            f"over 2s.  Something is wrong with the test setup, not "
            f"the code under test."
        )

        # ------------------------------------------------------------
        # Step 2: terminate the master.  The salt_master fixture wraps
        # its own started() context, but calling terminate() here
        # stops the daemon process immediately; the fixture's exit
        # will be a no-op.
        # ------------------------------------------------------------
        log.info("terminating master to force REQ timeouts on the minion")
        salt_master.terminate()

        # ------------------------------------------------------------
        # Step 3: watch the minion for the wedge.
        # ------------------------------------------------------------
        deadline = time.monotonic() + WEDGE_TIMEOUT_S
        with caplog.at_level(logging.WARNING, logger="salt"):
            wedged, reason = _wait_for_wedge(mpm_pid, deadline)

        # ------------------------------------------------------------
        # Step 4: confirm the pre-wedge log sequence appeared while we
        # waited.  These are the exact substrings from the wild.
        # ------------------------------------------------------------
        log_text = caplog.text
        expected_substrings = [
            "Request timed out while waiting for a response. reconnecting.",
            "unclosed SyncWrapper for cls=<class "
            "'salt.transport.tcp._TCPPubServerPublisher'>",
        ]
        missing = [s for s in expected_substrings if s not in log_text]
        assert not missing, (
            f"pre-wedge log sequence incomplete -- missing: {missing!r}. "
            f"Detector reported ({wedged}, {reason}) without emitting "
            f"all expected precursor log lines.  Either the log-line "
            f"wording changed or the minion took a different code path "
            f"than the field-observed sequence."
        )

        assert wedged, (
            f"minion did not wedge within {WEDGE_TIMEOUT_S}s of master "
            f"termination: {reason}.  This test's xfail(strict=True) "
            f"marker will convert this pass into a test failure -- the "
            f"transport fix has landed and the marker should be "
            f"removed."
        )
        pytest.fail(f"minion wedged as expected: {reason}")
