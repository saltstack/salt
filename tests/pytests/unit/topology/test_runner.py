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
