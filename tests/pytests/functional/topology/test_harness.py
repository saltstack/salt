"""
Harness-correctness tests for the master-topology functional test
infrastructure.

These tests exercise the *fixture* --- not topology behavior.  They
assert that:

* ``single_master`` brings up one standalone master with
  ``topology_enabled: True`` and a ``topology.conf`` on disk.
* ``single_cluster`` brings up an N-peer 3008.x master cluster
  reusing the existing ``cluster_*`` primitives.
* ``two_cluster_fixture`` and ``three_cluster_fixture`` deliver
  distinct clusters with distinct ``topology_link_port`` and
  non-overlapping ``cluster_id`` values.
* ``accept_peer`` / ``revoke_peer`` manipulate
  ``<pki_dir>/master/masters/<cluster_id>.pub``.
* ``config_peer`` edits ``topology.conf`` under the master's
  ``config_dir``.
* ``inspect_registry`` / ``inspect_breadcrumbs`` return harness
  state that per-file teams can later swap for real-cache reads.
* ``attach_minion`` yields a minion whose ``master`` opt points at
  the chosen cluster's master.
* Teardown leaks no processes and no listening ports.

Behavior tests (handshake, publish forwarding, breadcrumbs,
summary propagation) are added by the per-file implementation
teams --- NOT here.
"""

import socket

import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


# ---------------------------------------------------------------------------
# single_master
# ---------------------------------------------------------------------------


def test_single_master_starts_and_opts_wired(single_master):
    """A standalone master comes up with topology opts in place."""
    cluster = single_master()
    assert cluster.is_running()
    master = cluster.masters[0]
    assert master.config["topology_enabled"] is True
    assert master.config["topology_link_port"] > 0
    assert master.config["cluster_id"] == cluster.cluster_id
    assert list(master.config.get("topology_peers") or []) == []


def test_single_master_cluster_id_wired(single_master):
    """``cluster_id`` from the fixture argument makes it into master opts."""
    cluster = single_master(cluster_id="solo")
    master = cluster.masters[0]
    assert master.config["cluster_id"] == "solo"


def test_single_master_distinct_ports(single_master):
    """Two calls to single_master get distinct ret_port + topology_link_port."""
    a = single_master(cluster_id="a")
    b = single_master(cluster_id="b")
    assert a.masters[0].config["ret_port"] != b.masters[0].config["ret_port"]
    assert (
        a.masters[0].config["topology_link_port"]
        != b.masters[0].config["topology_link_port"]
    )


def test_single_master_topology_disabled_opt(single_master):
    """Caller can request topology_enabled=False for backward-compat tests."""
    cluster = single_master(opts_overrides={"topology_enabled": False})
    master = cluster.masters[0]
    assert master.config["topology_enabled"] is False


# ---------------------------------------------------------------------------
# single_cluster
# ---------------------------------------------------------------------------


def test_single_cluster_single_peer(single_cluster):
    """``peer_count=1`` falls back to a standalone master (no cluster_peers)."""
    cluster = single_cluster("east", peer_count=1)
    assert len(cluster.masters) == 1
    assert cluster.cluster_id == "east"


def test_single_cluster_multi_peer(single_cluster):
    """``peer_count=3`` spawns a 3-member 3008.x cluster."""
    cluster = single_cluster("west", peer_count=3)
    assert len(cluster.masters) == 3
    # One ``cluster_id`` serves both features; every peer in the
    # Raft cluster carries the same topology-graph identity.
    cluster_ids = {m.config.get("cluster_id") for m in cluster.masters}
    assert cluster_ids == {"west"}


# ---------------------------------------------------------------------------
# two_cluster_fixture / three_cluster_fixture
# ---------------------------------------------------------------------------


def test_two_cluster_fixture_distinct(two_cluster_fixture):
    """Two independent clusters with distinct topology cluster_ids + ports."""
    east, west = two_cluster_fixture
    assert east.cluster_id != west.cluster_id
    east_port = east.masters[0].config["topology_link_port"]
    west_port = west.masters[0].config["topology_link_port"]
    assert east_port != west_port


def test_three_cluster_fixture_distinct(three_cluster_fixture):
    """Three independent clusters with pairwise distinct ids + link ports."""
    a, b, c = three_cluster_fixture
    ids = {a.cluster_id, b.cluster_id, c.cluster_id}
    assert len(ids) == 3
    ports = {
        a.masters[0].config["topology_link_port"],
        b.masters[0].config["topology_link_port"],
        c.masters[0].config["topology_link_port"],
    }
    assert len(ports) == 3


def test_two_cluster_fixture_not_peered(two_cluster_fixture):
    """No peering happens by default --- tests opt in explicitly."""
    east, west = two_cluster_fixture
    assert east.inspect_registry()["peers"] == []
    assert west.inspect_registry()["peers"] == []


# ---------------------------------------------------------------------------
# accept_peer / revoke_peer
# ---------------------------------------------------------------------------


def test_accept_peer_writes_key(two_cluster_fixture):
    """``accept_peer`` drops a ``.pub`` into the master's ``pki_dir/masters``."""
    east, west = two_cluster_fixture
    east.accept_peer(west)
    masters_dir = east.masters_pki_dir
    assert (masters_dir / f"{west.cluster_id}.pub").is_file()


def test_revoke_peer_removes_key(two_cluster_fixture):
    """``revoke_peer`` undoes ``accept_peer``."""
    east, west = two_cluster_fixture
    east.accept_peer(west)
    east.revoke_peer(west)
    masters_dir = east.masters_pki_dir
    assert not (masters_dir / f"{west.cluster_id}.pub").is_file()


def test_revoke_peer_idempotent(two_cluster_fixture):
    """Revoking a never-accepted peer is a no-op, not an error."""
    east, west = two_cluster_fixture
    east.revoke_peer(west)  # must not raise


# ---------------------------------------------------------------------------
# config_peer
# ---------------------------------------------------------------------------


def test_config_peer_adds_to_topology_peers(two_cluster_fixture):
    """``config_peer`` appends to this master's ``topology_peers`` opt
    on disk; ``master.config`` is an immutable snapshot taken at
    startup, so we read the fresh on-disk state via
    :meth:`TopologyCluster.master_opts` (which re-reads the file)."""
    east, west = two_cluster_fixture
    east.config_peer(west)
    peers = list(east.master_opts()["topology_peers"])
    west_port = west.masters[0].config["topology_link_port"]
    assert any(entry["port"] == west_port for entry in peers), peers


# ---------------------------------------------------------------------------
# inspect_* harness APIs
# ---------------------------------------------------------------------------


def test_inspect_registry_shape(single_master):
    """``inspect_registry`` returns a dict with ``identity`` and ``peers``."""
    cluster = single_master(cluster_id="solo")
    state = cluster.inspect_registry()
    assert "identity" in state
    assert "peers" in state
    assert isinstance(state["peers"], list)


def test_inspect_breadcrumbs_shape(single_master):
    """``inspect_breadcrumbs`` returns a (possibly empty) list of dicts."""
    cluster = single_master(cluster_id="solo")
    crumbs = cluster.inspect_breadcrumbs()
    assert isinstance(crumbs, list)


# ---------------------------------------------------------------------------
# attach_minion
# ---------------------------------------------------------------------------


def test_attach_minion(attach_minion, single_master):
    """A minion attached to a cluster has that cluster's ret_port in opts."""
    cluster = single_master(cluster_id="solo")
    minion = attach_minion(cluster)
    assert minion.is_running()
    master_ret_port = cluster.masters[0].config["ret_port"]
    assert str(master_ret_port) in str(minion.config["master"])


# ---------------------------------------------------------------------------
# Teardown invariants
# ---------------------------------------------------------------------------


def _port_listening(port, host="127.0.0.1"):
    """Return True iff *port* is accepting connections on *host*."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def test_teardown_releases_ports(single_master):
    """After the fixture exits, the master's ports are no longer listening."""
    cluster = single_master(cluster_id="teardown")
    ret_port = cluster.masters[0].config["ret_port"]
    link_port = cluster.masters[0].config["topology_link_port"]
    assert cluster.is_running()
    cluster.terminate()
    assert not cluster.is_running()
    assert not _port_listening(ret_port)
    # ``topology_link_port`` is harness-reserved but never bound by the
    # (empty-stub) topology code; the assertion is still useful because
    # when teams wire up ``link_manager.pre_fork``, this test will catch
    # a leaked listener.
    assert not _port_listening(link_port)
