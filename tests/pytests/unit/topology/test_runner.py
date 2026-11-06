"""
Unit tests for :mod:`salt.runners.topology`.

Covers invariants that do not require a running master or the full
functional harness:

* ``__virtual__`` opts matrix (enabled, disabled, missing key).
* ``graph('dot')`` output is syntactically well-formed DOT.
* ``trust`` with an invalid action returns an error dict.
* ``find`` with ``timeout=0`` short-circuits to ``{}``.
* ``graph`` with an invalid format returns an error dict.
"""

import pytest

import salt.runners.topology as topology_runner


@pytest.fixture
def pki_dir(tmp_path):
    pki = tmp_path / "pki"
    (pki / "master").mkdir(parents=True)
    return pki


@pytest.fixture
def enabled_opts(pki_dir):
    return {
        "topology_enabled": True,
        "topology_link_port": 4530,
        "topology_peers": [],
        "pki_dir": str(pki_dir),
        "cluster_id": "unit-test",
        "__role": "master",
    }


@pytest.fixture
def disabled_opts(pki_dir):
    return {
        "topology_enabled": False,
        "pki_dir": str(pki_dir),
    }


@pytest.fixture
def configure_loader_modules(enabled_opts):
    return {topology_runner: {"__opts__": enabled_opts}}


# ---------------------------------------------------------------------------
# __virtual__
# ---------------------------------------------------------------------------


def test_virtual_enabled_returns_name(enabled_opts, monkeypatch):
    monkeypatch.setattr(topology_runner, "__opts__", enabled_opts, raising=False)
    assert topology_runner.__virtual__() == "topology"


def test_virtual_disabled_returns_false_with_reason(disabled_opts, monkeypatch):
    monkeypatch.setattr(topology_runner, "__opts__", disabled_opts, raising=False)
    result = topology_runner.__virtual__()
    assert isinstance(result, tuple)
    assert result[0] is False
    assert "topology_enabled" in result[1]


def test_virtual_missing_opt_returns_false(monkeypatch):
    """A master opts dict with no topology key at all is "disabled"."""
    monkeypatch.setattr(topology_runner, "__opts__", {}, raising=False)
    result = topology_runner.__virtual__()
    assert isinstance(result, tuple)
    assert result[0] is False


# ---------------------------------------------------------------------------
# graph('dot') --- syntactic validity
# ---------------------------------------------------------------------------


def test_graph_dot_balanced_and_names_cluster(enabled_opts, pki_dir, monkeypatch):
    """DOT output is well-formed: digraph header + balanced braces."""
    monkeypatch.setattr(topology_runner, "__opts__", enabled_opts, raising=False)
    # Add two accepted peers on disk so edges show up.
    masters = pki_dir / "masters"
    masters.mkdir(parents=True, exist_ok=True)
    (masters / "east.pub").write_bytes(b"fake pub east")
    (masters / "west.pub").write_bytes(b"fake pub west")

    out = topology_runner.graph(fmt="dot")
    assert isinstance(out, str)
    assert out.lstrip().startswith("digraph")
    # Balanced braces.
    assert out.count("{") == out.count("}") >= 1
    # The local cluster node is drawn as a doublecircle.
    assert "doublecircle" in out
    # Both peers appear as edge targets.
    assert '"east"' in out
    assert '"west"' in out
    # Edges originate from the local cluster.
    assert '"unit-test" -> "east"' in out
    assert '"unit-test" -> "west"' in out


def test_graph_dot_no_peers_still_valid(enabled_opts, monkeypatch):
    """Even with no peers DOT output is syntactically valid."""
    monkeypatch.setattr(topology_runner, "__opts__", enabled_opts, raising=False)
    out = topology_runner.graph(fmt="dot")
    assert out.lstrip().startswith("digraph")
    assert out.count("{") == out.count("}") == 1


# ---------------------------------------------------------------------------
# graph(fmt=invalid)
# ---------------------------------------------------------------------------


def test_graph_invalid_fmt(enabled_opts, monkeypatch):
    monkeypatch.setattr(topology_runner, "__opts__", enabled_opts, raising=False)
    out = topology_runner.graph(fmt="svg")
    assert isinstance(out, dict)
    assert "error" in out


# ---------------------------------------------------------------------------
# trust(invalid action / invalid cluster_id)
# ---------------------------------------------------------------------------


def test_trust_invalid_action(enabled_opts, monkeypatch):
    monkeypatch.setattr(topology_runner, "__opts__", enabled_opts, raising=False)
    out = topology_runner.trust("east", "frobnicate")
    assert isinstance(out, dict)
    assert "error" in out
    assert "frobnicate" in out["error"]


def test_trust_empty_cluster_id(enabled_opts, monkeypatch):
    monkeypatch.setattr(topology_runner, "__opts__", enabled_opts, raising=False)
    out = topology_runner.trust("", "accept")
    assert "error" in out


def test_trust_missing_key_for_accept(enabled_opts, monkeypatch):
    """``accept`` on a cluster with no pending key is an error."""
    monkeypatch.setattr(topology_runner, "__opts__", enabled_opts, raising=False)
    out = topology_runner.trust("ghost", "accept")
    assert "error" in out


def test_trust_fingerprint_missing_key(enabled_opts, monkeypatch):
    monkeypatch.setattr(topology_runner, "__opts__", enabled_opts, raising=False)
    out = topology_runner.trust("ghost", "fingerprint")
    assert "error" in out


# ---------------------------------------------------------------------------
# find() short-circuits
# ---------------------------------------------------------------------------


def test_find_timeout_zero(enabled_opts, monkeypatch):
    monkeypatch.setattr(topology_runner, "__opts__", enabled_opts, raising=False)
    assert topology_runner.find("anywhere", timeout=0) == {}


def test_find_negative_timeout(enabled_opts, monkeypatch):
    monkeypatch.setattr(topology_runner, "__opts__", enabled_opts, raising=False)
    assert topology_runner.find("anywhere", timeout=-5) == {}


def test_find_empty_minion_id(enabled_opts, monkeypatch):
    monkeypatch.setattr(topology_runner, "__opts__", enabled_opts, raising=False)
    assert topology_runner.find("", timeout=10) == {}


def test_find_bad_timeout_type(enabled_opts, monkeypatch):
    monkeypatch.setattr(topology_runner, "__opts__", enabled_opts, raising=False)
    assert topology_runner.find("x", timeout="forever") == {}


# ---------------------------------------------------------------------------
# peers() on bare opts (no pki tree) --- defensive degradation
# ---------------------------------------------------------------------------


def test_peers_empty_without_pki(enabled_opts, monkeypatch, tmp_path):
    opts = dict(enabled_opts)
    opts["pki_dir"] = str(tmp_path / "nonexistent")
    monkeypatch.setattr(topology_runner, "__opts__", opts, raising=False)
    out = topology_runner.peers()
    assert out == []


# ---------------------------------------------------------------------------
# links() health labelling
# ---------------------------------------------------------------------------


def _write_accepted(pki_dir, cluster_id, pubkey=b"-----BEGIN FAKE-----\n"):
    """Drop a .pub into ``pki/masters/`` to simulate acceptance.

    Matches ``_masters_dir(opts, 'masters') = pki_dir / 'masters'``
    in :mod:`salt.runners.topology`.
    """
    import pathlib

    masters = pathlib.Path(pki_dir) / "masters"
    masters.mkdir(parents=True, exist_ok=True)
    (masters / f"{cluster_id}.pub").write_bytes(pubkey)


def test_links_accepted_without_registry_reports_attached(
    enabled_opts, pki_dir, monkeypatch
):
    """Peer with key in masters/ but no registry entry → ``attached``.

    Matches the ``peers()`` label and mirrors the "handshake
    accepted, no summary gossip yet" state.
    """
    _write_accepted(pki_dir, "east-sub")
    _write_accepted(pki_dir, "west")
    monkeypatch.setattr(topology_runner, "__opts__", enabled_opts, raising=False)
    # Stub registry/breadcrumbs readers to simulate an empty mmap.
    monkeypatch.setattr(topology_runner, "_open_registry_reader", lambda opts: None)
    monkeypatch.setattr(topology_runner, "_open_breadcrumbs_reader", lambda opts: None)
    monkeypatch.setattr(topology_runner, "_registry_peer_ids", lambda reader: [])
    monkeypatch.setattr(topology_runner, "_breadcrumbs_count", lambda bread: 0)
    monkeypatch.setattr(topology_runner, "_live_link_by_cluster", lambda cid: None)

    out = topology_runner.links()

    by_id = {entry["peer_cluster_id"]: entry for entry in out}
    assert set(by_id) == {"east-sub", "west"}
    for entry in by_id.values():
        assert entry["health"] == "attached"


def test_links_registry_entry_reports_connected(enabled_opts, pki_dir, monkeypatch):
    """Peer present in the registry (summary gossip received) → ``connected``.

    Strongest from-disk confirmation the subprocess runner can
    make; last_summary_at reflects the gossip timestamp.
    """
    _write_accepted(pki_dir, "east")
    monkeypatch.setattr(topology_runner, "__opts__", enabled_opts, raising=False)
    monkeypatch.setattr(topology_runner, "_open_registry_reader", lambda opts: None)
    monkeypatch.setattr(topology_runner, "_open_breadcrumbs_reader", lambda opts: None)
    monkeypatch.setattr(topology_runner, "_registry_peer_ids", lambda reader: ["east"])
    monkeypatch.setattr(
        topology_runner,
        "_registry_peer_state",
        lambda reader, cid: {"attached_at": 123.0, "endpoints": []},
    )
    monkeypatch.setattr(topology_runner, "_breadcrumbs_count", lambda bread: 0)
    monkeypatch.setattr(topology_runner, "_live_link_by_cluster", lambda cid: None)

    out = topology_runner.links()

    assert len(out) == 1
    assert out[0]["peer_cluster_id"] == "east"
    assert out[0]["health"] == "connected"
    assert out[0]["last_summary_at"] == 123.0


def test_links_rejected_key_absent(enabled_opts, pki_dir, monkeypatch):
    """A key only in masters_rejected/ must not surface in links()."""
    import pathlib

    rejected = pathlib.Path(pki_dir) / "masters_rejected"
    rejected.mkdir(parents=True, exist_ok=True)
    (rejected / "bad-peer.pub").write_bytes(b"-----BEGIN FAKE-----\n")
    monkeypatch.setattr(topology_runner, "__opts__", enabled_opts, raising=False)
    monkeypatch.setattr(topology_runner, "_open_registry_reader", lambda opts: None)
    monkeypatch.setattr(topology_runner, "_open_breadcrumbs_reader", lambda opts: None)
    monkeypatch.setattr(topology_runner, "_registry_peer_ids", lambda reader: [])
    monkeypatch.setattr(topology_runner, "_breadcrumbs_count", lambda bread: 0)
    monkeypatch.setattr(topology_runner, "_live_link_by_cluster", lambda cid: None)

    out = topology_runner.links()

    assert out == []


# ---------------------------------------------------------------------------
# peers() surfaces health snapshot regression
# ---------------------------------------------------------------------------


def _write_health_snapshot(pki_dir, cluster_id, payload):
    """Persist a sidecar health snapshot the way the publish daemon does.

    Mirrors the writer in
    :meth:`salt.topology.link.PeerMasterLink._write_health_snapshot`.
    """
    import json
    import pathlib

    directory = pathlib.Path(pki_dir) / "topology_link_health"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{cluster_id}.json").write_text(json.dumps(payload))


def test_peers_surfaces_degraded_health_from_snapshot(
    enabled_opts, pki_dir, monkeypatch
):
    """``peers()`` MUST merge the publish daemon's sidecar health
    snapshot so operators see ``attached-degraded`` rather than the
    on-disk-key ``attached`` label when the outbound REQ channel has
    been torn down.

    Without this merge the runner returns ``attached`` for any peer
    whose key is on disk, regardless of whether the sender is still
    able to forward frames to that peer — a "topology.peers is a liar"
    shape that hides real degradation from operators.
    """
    _write_accepted(pki_dir, "west-sub-sub-1")
    _write_health_snapshot(
        pki_dir,
        "west-sub-sub-1",
        {
            "peer_cluster_id": "west-sub-sub-1",
            "health": "degraded",
            "session_generation": 2,
            "send_fault_count": 7,
            "last_send_fault_at": 1000.0,
            "last_send_success_at": 900.0,
            "updated_at": 1000.5,
        },
    )
    monkeypatch.setattr(topology_runner, "__opts__", enabled_opts, raising=False)

    out = topology_runner.peers()
    by_id = {entry["cluster_id"]: entry for entry in out}
    entry = by_id["west-sub-sub-1"]
    assert entry["state"] == "attached-degraded"
    assert entry["send_fault_count"] == 7
    assert entry["session_generation"] == 2
    assert entry["last_send_fault_at"] == 1000.0
    assert entry["last_send_success_at"] == 900.0


def test_peers_surfaces_wedged_when_fault_newer_than_success(
    enabled_opts, pki_dir, monkeypatch
):
    """When the snapshot says the link is CONNECTED but the most recent
    fault wallclock is newer than the most recent success, the composite
    state is ``attached-wedged``: the sender's view of the link is
    healthy but it hasn't delivered a frame since the last fault.

    This is the asymmetry operators care about -- key material and
    REQ-health both look fine but forwards are still failing.
    """
    _write_accepted(pki_dir, "east")
    _write_health_snapshot(
        pki_dir,
        "east",
        {
            "peer_cluster_id": "east",
            "health": "connected",
            "session_generation": 3,
            "send_fault_count": 2,
            "last_send_fault_at": 2000.0,
            "last_send_success_at": 1000.0,
        },
    )
    monkeypatch.setattr(topology_runner, "__opts__", enabled_opts, raising=False)

    out = topology_runner.peers()
    entry = next(e for e in out if e["cluster_id"] == "east")
    assert entry["state"] == "attached-wedged"
    assert entry["send_fault_count"] == 2


def test_peers_without_snapshot_falls_back_to_plain_attached(
    enabled_opts, pki_dir, monkeypatch
):
    """A peer accepted on disk but with no sidecar snapshot (publish
    daemon has never written one -- e.g. link never faulted or runner
    on a freshly started master) MUST return the plain ``attached``
    label without fault fields.
    """
    _write_accepted(pki_dir, "south")
    monkeypatch.setattr(topology_runner, "__opts__", enabled_opts, raising=False)

    out = topology_runner.peers()
    entry = next(e for e in out if e["cluster_id"] == "south")
    assert entry["state"] == "attached"
    for field in (
        "session_generation",
        "send_fault_count",
        "last_send_fault_at",
        "last_send_success_at",
    ):
        assert field not in entry


def test_peers_tolerates_malformed_snapshot(enabled_opts, pki_dir, monkeypatch):
    """A corrupt sidecar JSON must not raise -- fall back to plain
    ``attached``.  The snapshot is observability, not a correctness
    primitive; a disk hiccup must not break the runner.
    """
    import pathlib

    _write_accepted(pki_dir, "north")
    directory = pathlib.Path(pki_dir) / "topology_link_health"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "north.json").write_text("not json {{{")
    monkeypatch.setattr(topology_runner, "__opts__", enabled_opts, raising=False)

    out = topology_runner.peers()
    entry = next(e for e in out if e["cluster_id"] == "north")
    assert entry["state"] == "attached"
