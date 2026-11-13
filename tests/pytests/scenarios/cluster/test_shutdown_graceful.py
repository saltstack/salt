"""
Scenario regression: SIGTERM on the Raft leader must not flood its
peer followers' logs with ``SaltPeer: failed to send ...`` ``[ERROR]``
tracebacks (pre-request-vote, request-vote, or append-entries).

PR #70733 (``Clean up async cancellation + Raft peer-gone ERRORs on
cluster shutdown``) demoted expected unreachable-peer exceptions
(``ConnectionError`` / ``OSError`` / ``StreamClosedError``) in
``SaltPeer._send`` from ``log.exception`` (ERROR + traceback) to
``log.debug``, and also invalidated the cached ``_TCPPubServerPublisher``
after a send failure so subsequent heartbeats reconnect instead of
firing repeatedly against a dead stream.

Companion to ``test_peer_departure_quiet.py``: that sibling test stops
a FOLLOWER and audits the LEADER's log; this one stops the LEADER and
audits the FOLLOWERS' logs.  Together they cover both sides of the
peer-going-away ERROR demotion.

Pre-fix the follower logs floods dozens of ``SaltPeer: failed to send``
ERROR lines/sec while the stepped-down leader is unreachable; post-fix
these are DEBUG.
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


# Any ``SaltPeer: failed to send`` ERROR -- append-entries, request-vote,
# pre-request-vote etc.  Pre-fix ``log.exception`` emitted one of these
# per heartbeat tick per unreachable peer; post-fix they are DEBUG.
_SALTPEER_ERROR_RE = re.compile(
    r"\[ERROR\s*\].*SaltPeer:\s*failed to send",
    re.IGNORECASE,
)
_LEADER_RE = re.compile(r"BECOMING LEADER")


def _find_leader(masters):
    """Return the master whose log has a ``BECOMING LEADER`` entry."""
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


def test_leader_sigterm_does_not_flood_followers_with_saltpeer_errors(
    cluster_master_1, cluster_master_2, cluster_master_3
):
    """
    Wait for a leader, SIGTERM it, and confirm the remaining
    followers do not emit ``SaltPeer: failed to send`` ``[ERROR]``
    lines for the departed leader.

    Pre-fix: followers log one ERROR + traceback per heartbeat tick
    for the unreachable leader.  Post-fix: DEBUG.  Threshold: at most
    3 across all followers combined.
    """
    masters = (cluster_master_1, cluster_master_2, cluster_master_3)

    # Let a leader emerge.
    leader = None
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        leader = _find_leader(masters)
        if leader is not None:
            break
        time.sleep(1)
    assert leader is not None, "No Raft leader elected in 30 s"

    # Capture the followers' current log offsets so we only count
    # ERRORs that appear after the leader SIGTERM.
    followers = [m for m in masters if m is not leader]
    start_offsets = {}
    log_paths = {}
    for follower in followers:
        log_path = pathlib.Path(follower.config["log_file"])
        log_paths[follower.config["id"]] = log_path
        start_offsets[follower.config["id"]] = (
            log_path.stat().st_size if log_path.exists() else 0
        )

    # SIGTERM the leader.
    leader.terminate()

    # Observation window -- must cover a handful of heartbeat ticks
    # so pre-fix would have logged dozens of ERRORs.
    observation_s = 15
    time.sleep(observation_s)

    hits_by_follower = {}
    total_hits = 0
    for follower in followers:
        name = follower.config["id"]
        with salt.utils.files.fopen(log_paths[name], "r") as fp:
            fp.seek(start_offsets[name])
            tail = fp.read()
        hits = _SALTPEER_ERROR_RE.findall(tail)
        hits_by_follower[name] = hits
        total_hits += len(hits)

    assert total_hits <= 3, (
        f"Followers collectively logged {total_hits} "
        f"``SaltPeer: failed to send`` ERROR line(s) in {observation_s} s "
        f"after the leader SIGTERM.  Threshold: <= 3.  "
        f"Regression of PR #70733 -- expected peer-unreachable "
        f"exceptions should be DEBUG on the heartbeat path.\n\n"
        + "\n".join(
            f"{name}: {len(hits)} hit(s)\n" + "\n".join(f"  {h}" for h in hits[:3])
            for name, hits in hits_by_follower.items()
        )
    )
