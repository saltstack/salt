"""
Functional tests for :mod:`salt.runners.topology`.

Drives the real runner module against the shared harness fixtures
in ``conftest.py``.  The master processes brought up by the
harness carry ``topology_enabled: True`` and a ``topology.conf``
on disk but do not currently run ``link_manager.start``; the
runner is designed to degrade gracefully to on-disk state in that
case (same shape as a running system that has not yet seen a
successful handshake).

The runner is loaded in-process by instantiating a
:func:`salt.loader.runner` LazyLoader onto the harness master's
opts dict so each test asserts the real public callable, not a
monkey-patched proxy.
"""

import logging
import pathlib

import pytest

import salt.loader
import salt.utils.files

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _runner(cluster):
    """Return the loaded ``topology.*`` LazyLoader for *cluster*'s master.

    Uses :meth:`TopologyCluster.master_opts` so any :meth:`config_peer`
    writes to the master config file are picked up (``master.config``
    is an immutable snapshot taken at startup).
    """
    master = cluster.masters[0]
    opts = dict(master.config)
    opts.update(cluster.master_opts())
    loader = salt.loader.runner(opts)
    return loader, opts


def _call(loader, name, *args, **kwargs):
    """Invoke ``topology.<name>`` on the loader."""
    func = loader[f"topology.{name}"]
    return func(*args, **kwargs)


def _write_pending(cluster, peer_cluster_id, pubkey=b"peer pub"):
    """Simulate a peer whose key is in masters_pre/ (pending accept)."""
    master = cluster.masters[0]
    pki_dir = pathlib.Path(master.config["pki_dir"])
    pending_dir = pki_dir / "masters_pre"
    pending_dir.mkdir(parents=True, exist_ok=True)
    target = pending_dir / f"{peer_cluster_id}.pub"
    target.write_bytes(pubkey)
    return target


# ---------------------------------------------------------------------------
# __virtual__
# ---------------------------------------------------------------------------


def test_virtual_available_when_topology_enabled(single_master):
    """``__virtual__`` returns ``topology`` when the opt is True."""
    cluster = single_master(cluster_id="solo")
    loader, _opts = _runner(cluster)
    assert "topology.status" in loader


def test_virtual_false_when_topology_disabled(single_master):
    """``__virtual__`` returns False with a reason when disabled."""
    cluster = single_master(opts_overrides={"topology_enabled": False})
    loader, _opts = _runner(cluster)
    # Loader hides the virtualname when False is returned; the func
    # should not be callable via its short name.
    assert "topology.status" not in loader


# ---------------------------------------------------------------------------
# status()
# ---------------------------------------------------------------------------


def test_status_shape_solo(single_master):
    """``status()`` returns a dict with cluster_id, counts, peers."""
    cluster = single_master(cluster_id="solo")
    loader, _opts = _runner(cluster)
    ret = _call(loader, "status")
    assert isinstance(ret, dict)
    assert ret["cluster_id"] == "solo"
    assert "minion_count" in ret
    assert "up_count" in ret
    assert isinstance(ret["peers"], list)
    assert ret["peers"] == []


def test_status_includes_accepted_peer(two_cluster_fixture):
    """After accept, the peer appears in ``status()['peers']``."""
    east, west = two_cluster_fixture
    east.accept_peer(west)
    loader, _opts = _runner(east)
    ret = _call(loader, "status")
    assert ret["cluster_id"] == "east"
    peer_ids = {p["cluster_id"] for p in ret["peers"]}
    assert "west" in peer_ids


# ---------------------------------------------------------------------------
# links()
# ---------------------------------------------------------------------------


def test_links_empty_without_peers(single_master):
    """``links()`` returns an empty list on a fresh solo master."""
    cluster = single_master(cluster_id="solo")
    loader, _opts = _runner(cluster)
    ret = _call(loader, "links")
    assert isinstance(ret, list)
    assert ret == []


def test_links_reports_accepted_peer(two_cluster_fixture):
    """Each accepted peer gets a link entry with expected keys."""
    east, west = two_cluster_fixture
    east.accept_peer(west)
    east.config_peer(west)
    loader, _opts = _runner(east)
    ret = _call(loader, "links")
    assert isinstance(ret, list)
    assert len(ret) >= 1
    entry = next(e for e in ret if e["peer_cluster_id"] == "west")
    assert "health" in entry
    assert "endpoints" in entry
    assert "last_summary_at" in entry
    assert "breadcrumbs_active" in entry


# ---------------------------------------------------------------------------
# peers()
# ---------------------------------------------------------------------------


def test_peers_empty_on_fresh_master(single_master):
    """No configured, no pending, no accepted -> empty list."""
    cluster = single_master(cluster_id="solo")
    loader, _opts = _runner(cluster)
    ret = _call(loader, "peers")
    assert isinstance(ret, list)
    assert ret == []


def test_peers_pending_then_attached(two_cluster_fixture):
    """A peer in masters_pre/ shows pending; after accept, attached."""
    east, west = two_cluster_fixture
    _write_pending(east, "west")
    loader, _opts = _runner(east)
    ret = _call(loader, "peers")
    west_entry = next(p for p in ret if p["cluster_id"] == "west")
    assert west_entry["state"] == "pending"

    # Now accept and re-call.
    east.accept_peer(west)
    ret2 = _call(loader, "peers")
    west_entry2 = next(p for p in ret2 if p["cluster_id"] == "west")
    assert west_entry2["state"] == "attached"


def test_peers_configured_only(two_cluster_fixture):
    """A peer in topology.conf but not yet in any pki dir shows configured."""
    east, west = two_cluster_fixture
    east.config_peer(west)
    loader, _opts = _runner(east)
    ret = _call(loader, "peers")
    states = {p["cluster_id"]: p["state"] for p in ret}
    # The configured peer has host/port in topology.conf but no key yet.
    # Its id is derived from the host:port tuple, not a cluster_id, so it
    # appears under its endpoint identity until the first handshake.
    assert any(s == "configured" for s in states.values())


# ---------------------------------------------------------------------------
# trust()
# ---------------------------------------------------------------------------


def test_trust_accept_moves_key(two_cluster_fixture):
    """``trust('<id>', 'accept')`` moves masters_pre/ -> masters/."""
    east, west = two_cluster_fixture
    _write_pending(east, "west")
    loader, _opts = _runner(east)
    ret = _call(loader, "trust", "west", "accept")
    assert ret["state"] == "accepted"
    master = east.masters[0]
    pki_dir = pathlib.Path(master.config["pki_dir"])
    assert (pki_dir / "masters" / "west.pub").is_file()
    assert not (pki_dir / "masters_pre" / "west.pub").is_file()


def test_trust_reject_moves_to_rejected(two_cluster_fixture):
    """``trust('<id>', 'reject')`` moves the key to masters_rejected/."""
    east, _west = two_cluster_fixture
    _write_pending(east, "west")
    loader, _opts = _runner(east)
    ret = _call(loader, "trust", "west", "reject")
    assert ret["state"] == "rejected"
    master = east.masters[0]
    pki_dir = pathlib.Path(master.config["pki_dir"])
    assert (pki_dir / "masters_rejected" / "west.pub").is_file()


def test_trust_fingerprint_returns_string(two_cluster_fixture):
    """``trust('<id>', 'fingerprint')`` returns a non-empty string."""
    east, _west = two_cluster_fixture
    _write_pending(east, "west", pubkey=b"fake-west-pub\n")
    loader, _opts = _runner(east)
    ret = _call(loader, "trust", "west", "fingerprint")
    assert isinstance(ret, dict)
    assert "fingerprint" in ret
    assert isinstance(ret["fingerprint"], str)
    assert len(ret["fingerprint"]) > 0


def test_trust_delete_removes_key(two_cluster_fixture):
    """``trust('<id>', 'delete')`` removes an accepted key."""
    east, west = two_cluster_fixture
    east.accept_peer(west)
    loader, _opts = _runner(east)
    ret = _call(loader, "trust", "west", "delete")
    assert ret["state"] == "deleted"
    master = east.masters[0]
    pki_dir = pathlib.Path(master.config["pki_dir"])
    assert not (pki_dir / "masters" / "west.pub").is_file()


def test_trust_invalid_action_returns_error(single_master):
    """An unknown action yields an error dict."""
    cluster = single_master(cluster_id="solo")
    loader, _opts = _runner(cluster)
    ret = _call(loader, "trust", "west", "frob")
    assert isinstance(ret, dict)
    assert "error" in ret


# ---------------------------------------------------------------------------
# find()
# ---------------------------------------------------------------------------


def test_find_empty_when_no_match(single_master):
    """``find()`` returns an empty dict when nothing matches."""
    cluster = single_master(cluster_id="solo")
    loader, _opts = _runner(cluster)
    ret = _call(loader, "find", "nowhere-minion", timeout=1)
    assert isinstance(ret, dict)
    assert ret == {}


def test_find_timeout_zero_returns_empty(single_master):
    """``timeout=0`` short-circuits with an empty dict."""
    cluster = single_master(cluster_id="solo")
    loader, _opts = _runner(cluster)
    ret = _call(loader, "find", "any-minion", timeout=0)
    assert ret == {}


# ---------------------------------------------------------------------------
# graph()
# ---------------------------------------------------------------------------


def test_graph_text_contains_cluster(two_cluster_fixture):
    """``graph('text')`` is a string with this cluster's id in it."""
    east, west = two_cluster_fixture
    east.accept_peer(west)
    loader, _opts = _runner(east)
    out = _call(loader, "graph", "text")
    assert isinstance(out, str)
    assert "east" in out
    assert "west" in out


def test_graph_dot_is_valid_dot(two_cluster_fixture):
    """``graph('dot')`` returns syntactically balanced DOT source."""
    east, west = two_cluster_fixture
    east.accept_peer(west)
    loader, _opts = _runner(east)
    out = _call(loader, "graph", "dot")
    assert isinstance(out, str)
    assert out.lstrip().startswith(("digraph", "graph"))
    assert out.count("{") == out.count("}")
    assert out.count("{") >= 1
    assert "east" in out
    assert "west" in out


def test_graph_json_structure(two_cluster_fixture):
    """``graph('json')`` returns ``{"nodes": [...], "edges": [...]}``."""
    east, west = two_cluster_fixture
    east.accept_peer(west)
    loader, _opts = _runner(east)
    out = _call(loader, "graph", "json")
    assert isinstance(out, dict)
    assert "nodes" in out
    assert "edges" in out
    assert isinstance(out["nodes"], list)
    assert isinstance(out["edges"], list)
    assert any(n.get("id") == "east" for n in out["nodes"])
    assert any(n.get("id") == "west" for n in out["nodes"])


def test_graph_invalid_fmt_errors(single_master):
    """Unknown ``fmt`` yields an error dict."""
    cluster = single_master(cluster_id="solo")
    loader, _opts = _runner(cluster)
    out = _call(loader, "graph", "yaml")
    assert isinstance(out, dict)
    assert "error" in out
