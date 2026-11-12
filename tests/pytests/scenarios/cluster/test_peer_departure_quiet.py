"""
Scenario regression: stopping one cluster master must not flood the
Raft leader's log with ``SaltPeer: failed to send cluster/raft/append-
entries`` ``[ERROR]`` tracebacks.

PR #70733 demoted expected ``ConnectionError`` / ``OSError`` /
``StreamClosedError`` from the ``SaltPeer._send`` heartbeat path from
``log.exception`` (ERROR + traceback) to ``log.debug``.  It also
invalidated the cached ``_TCPPubServerPublisher`` so the next heartbeat
reconnects instead of firing against the same dead stream forever.

Pre-fix, during a peer departure (either a planned ``docker compose
down`` or a crash), the leader produced dozens of ERROR lines per
second for every heartbeat tick.

This scenario asserts the count stays very low (``<= 3``) during a
~15 s window after one master is stopped.  A real transport bug (that
should stay at ERROR) still trips it.
"""

import pathlib
import re
import time

import pytest

import salt.utils.files

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.no_subprocess_coverage,
]


# ``log.exception(...)`` emits one ERROR line with the formatted
# message plus the traceback on subsequent lines.  Matching the
# message-level line only is sufficient and robust against the
# trailing traceback shape.
_ERROR_RE = re.compile(
    r"\[ERROR\s*\].*SaltPeer: failed to send.*append-entries", re.IGNORECASE
)
_LEADER_RE = re.compile(r"BECOMING LEADER")


def _find_leader(masters):
    """
    Return the master whose log file contains a ``BECOMING LEADER``
    entry.  If more than one has (a re-election happened), return the
    most-recently-promoted one.  If none has yet, return None.
    """
    best = None
    best_mtime = -1
    for master in masters:
        log_path = pathlib.Path(master.config["log_file"])
        if not log_path.exists():
            continue
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _LEADER_RE.search(text):
            mtime = log_path.stat().st_mtime
            if mtime > best_mtime:
                best_mtime = mtime
                best = master
    return best


def test_peer_departure_does_not_flood_leader_with_errors(
    cluster_master_1, cluster_master_2, cluster_master_3
):
    """
    Wait for a Raft leader to emerge, stop a follower, observe the
    leader's log for 15 s, and assert the ``SaltPeer: failed to send
    ...append-entries`` ERROR count is low.
    """
    masters = (cluster_master_1, cluster_master_2, cluster_master_3)

    # Let the cluster settle and a leader appear.  Up to 30 s is a
    # generous bound -- usually sub-5 s in CI.
    leader = None
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        leader = _find_leader(masters)
        if leader is not None:
            break
        time.sleep(1)
    assert leader is not None, "No Raft leader elected in 30 s"

    # Pick a follower to stop (any non-leader).
    follower = next(m for m in masters if m is not leader)
    leader_log = pathlib.Path(leader.config["log_file"])
    start_offset = leader_log.stat().st_size if leader_log.exists() else 0

    # Trigger peer departure.  ``slow_stop=True`` (default on the
    # saltfactories daemon) translates to SIGTERM.
    follower.terminate()

    # Observation window.  Pre-fix the leader's error rate was
    # dozens/sec; 15 s is plenty to differentiate signal from slack.
    observation_s = 15
    time.sleep(observation_s)

    with salt.utils.files.fopen(leader_log, "r") as fp:
        fp.seek(start_offset)
        tail = fp.read()

    hits = _ERROR_RE.findall(tail)
    assert len(hits) <= 3, (
        f"Leader logged {len(hits)} ``SaltPeer: failed to send ... "
        f"append-entries`` ERROR line(s) in {observation_s} s after "
        f"one follower stopped.  Threshold: <= 3.  Expected peer-"
        f"unreachable exceptions should be DEBUG post-PR #70733.\n\n"
        f"First offending lines:\n" + "\n".join(hits[:5])
    )
