"""
Cluster integration tests for failure conditions not otherwise covered.

These tests exercise paths that fan out from a working cluster into a
degraded or recovering state:

  * **Storage loss recovery** — a master's local cache (Raft log + key
    cache) is wiped while it is offline; on restart it must reconverge
    through the join handshake's bulk state-sync rather than diverging
    or refusing to start.
  * **Unreachable peers diagnosis** — a master configured with
    ``cluster_isolated_filesystem=True`` but whose peers are all
    unreachable should not hang silently; it should self-elect as a
    founding voter (because it has no way to learn otherwise) and
    surface that fact in its log.
  * **Lease / clock-skew defense (placeholder)** — the disruption
    defense (pre-vote + lease) is unit-tested but not yet integration-
    tested at real-process granularity; left as a marked skip until
    Raft timing becomes config-driven.

Companion unit/functional tests live in
``tests/pytests/unit/cluster/consensus/`` and
``tests/pytests/functional/cluster/consensus/``.
"""

import pathlib
import shutil
import time

import pytest

import salt.cache

pytestmark = [
    pytest.mark.slow_test,
]


def _fetch_minion_key(master, minion_id):
    """Read an accepted minion key from the master's keys cache."""
    cache = salt.cache.Cache(master.config, driver=master.config["keys.cache_driver"])
    return cache.fetch("keys", minion_id)


def _wait_for_log_line(master, needle, timeout=30):
    """Poll the master's log file for *needle*; return True when found."""
    log_file = master.config.get("log_file")
    if not log_file:
        return False
    log_path = pathlib.Path(log_file)
    if not log_path.is_absolute():
        log_path = pathlib.Path(master.config.get("root_dir", "")) / log_file
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if log_path.is_file():
            try:
                if needle in log_path.read_text(encoding="utf-8", errors="replace"):
                    return True
            except OSError:
                pass
        time.sleep(0.5)
    return False


def test_master_recovers_after_cache_dir_loss(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
    cluster_minion_1_isolated,
):
    """
    A master whose ``cache_dir`` is wiped while offline must rejoin the
    cluster cleanly on restart by re-running the discover/join handshake
    and pulling state via the bulk state-sync embedded in
    ``cluster/peer/join-reply``.

    Sequence:
      1. Three isolated-FS masters bootstrap; minion_1 connects to
         master_1 and is auto-accepted.  Cluster events replicate the
         accepted key to masters 2 and 3.
      2. master_2 is stopped.  Its ``cache_dir`` (which holds the Raft
         log persisted via ``salt.cache`` and the keys cache) is
         removed entirely, simulating disk loss / replacement.
      3. master_2 restarts.  It cannot find its prior join sentinel or
         keys cache, so it re-runs discover + join against masters 1
         and 3, receives a fresh ``cluster_aes`` / ``cluster.pem`` /
         minion-key dump, and lands back in the cluster.
      4. Within 30 s the recovered master_2 has the accepted minion
         key in its keys cache.

    This catches a class of bugs where a master that loses storage
    silently rejects the rejoin (e.g. because of a stale sentinel
    written to a different filesystem location) or keeps a partial
    state from before the wipe.
    """
    minion_id = cluster_minion_1_isolated.id
    master_2 = cluster_master_2_isolated

    # Sanity: master_2 has the minion key before we wipe.  Use a short
    # poll window so a slow event-replication round doesn't trip the
    # test before we even get to the failure injection.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        entry = _fetch_minion_key(master_2, minion_id)
        if entry and entry.get("state") == "accepted":
            break
        time.sleep(0.5)
    assert entry and entry.get("state") == "accepted", (
        f"Pre-condition failed: master_2 never received minion {minion_id!r} "
        f"key in the first place (last entry: {entry!r})"
    )

    cache_dir = pathlib.Path(master_2.config["cache_dir"])
    pki_dir = pathlib.Path(master_2.config["cluster_pki_dir"])

    # Stop master_2 — terminate() returns when the process is reaped.
    master_2.terminate()

    # Wipe master_2's cache_dir entirely.  We leave its cluster_pki_dir
    # alone (peer pubs etc.) but blow away the join sentinel, the keys
    # cache, and the Raft log storage.  This is the "lost the disk"
    # scenario.
    shutil.rmtree(cache_dir, ignore_errors=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Also drop the cluster_aes file so we exercise the over-the-wire
    # delivery path on rejoin (rather than master_2 reading its prior
    # value from disk).
    (pki_dir / ".aes").unlink(missing_ok=True)

    # Restart master_2.  The factory's started() context manager is
    # already exited at this point (the fixture's `yield`), so we need
    # to start the daemon directly via the salt-factories API.
    with master_2.started(start_timeout=120):
        # Wait for the rejoin to land the minion key back in master_2's
        # cache.
        deadline = time.monotonic() + 60
        entry = None
        while time.monotonic() < deadline:
            entry = _fetch_minion_key(master_2, minion_id)
            if entry and entry.get("state") == "accepted":
                break
            time.sleep(0.5)
        assert entry and entry.get("state") == "accepted", (
            f"After cache_dir loss + restart, master_2 never received "
            f"minion {minion_id!r} key via state-sync (last entry: {entry!r})"
        )

        # And the cluster_aes must have been re-delivered over the wire
        # (we deleted the local copy before restart).
        aes_path = pki_dir / ".aes"
        assert aes_path.is_file(), (
            "master_2 did not re-acquire cluster_aes from peers after "
            "cache_dir loss; expected over-the-wire delivery via join-reply"
        )


def test_isolated_master_with_unreachable_peers_self_elects(
    request, salt_factories, tmp_path
):
    """
    A master configured with ``cluster_isolated_filesystem=True`` and
    ``cluster_peers`` pointing at addresses where no master is listening
    should not hang during startup.  After ``cluster_join_timeout``
    elapses with no join-reply, it self-elects as a founding voter.

    This is the "first master in a brand-new cluster" path applied to a
    misconfigured deployment: if a sysadmin starts a master with peers
    that are typo'd or down, we want to see ``Raft consensus service
    started as founding voter`` in the log and the master fully
    operational rather than silently waiting forever.

    Tests the cluster_aes/cluster.pem replication-failure category by
    proving that the *absence* of replication (no peer reachable) is a
    handled, diagnosed condition rather than a hang.
    """
    pki = tmp_path / "pki"
    pki.mkdir()
    (pki / "peers").mkdir()
    cache = tmp_path / "cache"
    cache.mkdir()

    config_overrides = {
        "interface": "127.0.0.1",
        "cluster_id": "lonely_cluster",
        # 127.0.0.50/.51 are loopback addresses where no daemon is
        # bound; the kernel returns ECONNREFUSED *immediately* rather
        # than waiting on the TCP connect timeout.  RFC 5737 TEST-NET
        # addresses look attractive but black-hole packets, so the
        # master would hang for the full SYN retry budget (>= 120s)
        # instead of bouncing fast and falling through to the
        # founding-voter timer.
        "cluster_peers": ["127.0.0.50", "127.0.0.51"],
        "cluster_pki_dir": str(pki),
        "cache_dir": str(cache),
        "cluster_isolated_filesystem": True,
        "cluster_join_timeout": 5,
        "log_granular_levels": {
            "salt": "info",
            "salt.channel": "debug",
        },
    }
    factory = salt_factories.salt_master_daemon(
        "lonely-master",
        defaults={
            "open_mode": True,
            "transport": request.config.getoption("--transport"),
        },
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=60):
        # Within a few seconds of cluster_join_timeout we should see the
        # founding-voter message — proves the master diagnosed the
        # missing peers and proceeded rather than hanging on the
        # discover/join handshake forever.
        assert _wait_for_log_line(
            factory,
            "Raft consensus service started as founding voter",
            timeout=30,
        ), (
            "Master with unreachable cluster_peers did not log "
            "'started as founding voter' within 30s; expected the "
            "cluster_join_timeout fallback to fire"
        )


@pytest.mark.skip(
    reason=(
        "Real-process lease/clock-skew defense test requires Raft "
        "follower_timeout / heartbeat_interval to be config-driven. "
        "Currently hardcoded in salt/cluster/consensus/raft/node.py "
        "via util.gettimeout(_min, _max). Pre-vote + lease enforcement "
        "is covered at the unit level by "
        "tests/pytests/unit/cluster/consensus/test_raft_node_safety.py "
        "(test_prevote_denied_by_lease, test_prevote_phase). Once the "
        "raft scheduler accepts an opt-driven override for the "
        "follower-timeout window, write a real-process test that "
        "spawns a 4th master with an aggressively short timeout and "
        "asserts the healthy 3-master leader does not lose its term."
    )
)
def test_disruptive_candidate_blocked_by_lease():
    """Placeholder for a real-process pre-vote / lease defense test."""
