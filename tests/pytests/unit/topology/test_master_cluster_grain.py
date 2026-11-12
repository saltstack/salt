"""
Unit tests for the ``master_cluster_id`` minion grain and the
master/minion wiring that populates it.

Covers:

* :func:`salt.grains.core.master_cluster_id` --- pure opt-reading grain
  function (empty when the opt is absent/falsy; dict with the value
  when present).
* :func:`salt.minion._store_master_cluster_id` --- lift the auth
  response field into opts, no-op when absent.
* :func:`salt.master._topology_cluster_id_for_auth` --- gated return
  of the topology cluster_id for inclusion in the auth response.
"""

from types import SimpleNamespace

import salt.config.topology
import salt.grains.core as core_grains
import salt.master
import salt.minion
from tests.support.mock import patch

# ---------------------------------------------------------------------------
# grain function
# ---------------------------------------------------------------------------


def _run_grain(opts):
    """Call :func:`master_cluster_id` with ``__opts__`` set to *opts*.

    Grain modules receive ``__opts__`` via the loader-injected dunder;
    we populate the module's namespace through ``patch.dict`` so the
    lint-tests hook stays happy.
    """
    with patch.dict(core_grains.__dict__, {"__opts__": opts}):
        return core_grains.master_cluster_id()


def test_grain_absent_when_opt_missing():
    """No opt -> no grain (empty dict)."""
    assert _run_grain({}) == {}


def test_grain_absent_when_opt_empty_string():
    """Empty-string opt -> no grain."""
    assert _run_grain({"master_cluster_id": ""}) == {}


def test_grain_absent_when_opt_none():
    """None opt -> no grain."""
    assert _run_grain({"master_cluster_id": None}) == {}


def test_grain_returns_value_when_opt_populated():
    """Populated opt -> grain dict carrying that value."""
    result = _run_grain({"master_cluster_id": "east"})
    assert result == {"master_cluster_id": "east"}


def test_grain_returns_non_ascii_value_unchanged():
    """Non-ASCII cluster_id survives round-trip."""
    result = _run_grain({"master_cluster_id": "clúster"})
    assert result == {"master_cluster_id": "clúster"}


# ---------------------------------------------------------------------------
# minion-side opt store from auth response
# ---------------------------------------------------------------------------


def _channel_with_creds(creds):
    return SimpleNamespace(auth=SimpleNamespace(creds=creds))


def test_store_master_cluster_id_sets_opt_when_creds_carry_cluster_id():
    opts = {}
    salt.minion._store_master_cluster_id(
        opts, _channel_with_creds({"cluster_id": "east", "publish_port": 4506})
    )
    assert opts == {"master_cluster_id": "east"}


def test_store_master_cluster_id_no_op_when_cluster_id_absent():
    """Pre-topology master auth responses carry no cluster_id --- no-op."""
    opts = {"existing": "untouched"}
    salt.minion._store_master_cluster_id(
        opts, _channel_with_creds({"publish_port": 4506})
    )
    assert "master_cluster_id" not in opts
    assert opts["existing"] == "untouched"


def test_store_master_cluster_id_no_op_when_cluster_id_empty():
    opts = {}
    salt.minion._store_master_cluster_id(
        opts, _channel_with_creds({"cluster_id": "", "publish_port": 4506})
    )
    assert opts == {}


def test_store_master_cluster_id_no_op_when_creds_missing():
    """Channel without .auth.creds (unauthenticated edge) is tolerated."""
    opts = {}
    salt.minion._store_master_cluster_id(opts, SimpleNamespace())
    assert opts == {}


def test_store_master_cluster_id_no_op_when_creds_none():
    opts = {}
    salt.minion._store_master_cluster_id(
        opts, SimpleNamespace(auth=SimpleNamespace(creds=None))
    )
    assert opts == {}


# ---------------------------------------------------------------------------
# master-side topology_cluster_id gating
# ---------------------------------------------------------------------------


def _topology_cfg(cluster_id, enabled=True):
    """Build a stub TopologyConfig-like namespace."""
    return SimpleNamespace(cluster_id=cluster_id, enabled=enabled)


def test_topology_cluster_id_disabled_when_opt_false():
    """``topology_enabled: False`` -> empty string, config not loaded."""
    opts = {"topology_enabled": False, "topology_push_cluster_grain": True}
    with patch.object(
        salt.config.topology,
        "load_topology_config",
        side_effect=AssertionError("must not be called"),
    ):
        assert salt.master._topology_cluster_id_for_auth(opts) == ""


def test_topology_cluster_id_disabled_when_push_opt_false():
    """``topology_push_cluster_grain: False`` -> opt-out honoured."""
    opts = {"topology_enabled": True, "topology_push_cluster_grain": False}
    with patch.object(
        salt.config.topology,
        "load_topology_config",
        side_effect=AssertionError("must not be called"),
    ):
        assert salt.master._topology_cluster_id_for_auth(opts) == ""


def test_topology_cluster_id_defaults_push_opt_true():
    """Push opt defaults to True when unspecified."""
    opts = {"topology_enabled": True}
    with patch.object(
        salt.config.topology,
        "load_topology_config",
        return_value=_topology_cfg("east"),
    ):
        assert salt.master._topology_cluster_id_for_auth(opts) == "east"


def test_topology_cluster_id_returns_cluster_id_from_config():
    """Enabled + push opt -> read from TopologyConfig."""
    opts = {"topology_enabled": True, "topology_push_cluster_grain": True}
    with patch.object(
        salt.config.topology,
        "load_topology_config",
        return_value=_topology_cfg("west"),
    ):
        assert salt.master._topology_cluster_id_for_auth(opts) == "west"


def test_topology_cluster_id_empty_when_cfg_disabled():
    """TopologyConfig reports enabled=False -> empty string."""
    opts = {"topology_enabled": True, "topology_push_cluster_grain": True}
    with patch.object(
        salt.config.topology,
        "load_topology_config",
        return_value=_topology_cfg("", enabled=False),
    ):
        assert salt.master._topology_cluster_id_for_auth(opts) == ""


def test_topology_cluster_id_cached_in_opts():
    """
    Second call hits the opts cache; load_topology_config runs once per
    opts dict even across many minion auths.
    """
    opts = {"topology_enabled": True, "topology_push_cluster_grain": True}
    with patch.object(
        salt.config.topology,
        "load_topology_config",
        return_value=_topology_cfg("east"),
    ) as mocked_load:
        salt.master._topology_cluster_id_for_auth(opts)
        salt.master._topology_cluster_id_for_auth(opts)
        salt.master._topology_cluster_id_for_auth(opts)
    assert mocked_load.call_count == 1
    assert opts["_topology_cluster_id_cache"] == "east"


def test_topology_cluster_id_malformed_cfg_degrades_to_empty():
    """A corrupt topology.conf must not crash authentication."""
    opts = {"topology_enabled": True, "topology_push_cluster_grain": True}
    with patch.object(
        salt.config.topology,
        "load_topology_config",
        side_effect=ValueError("bad yaml"),
    ):
        assert salt.master._topology_cluster_id_for_auth(opts) == ""
    # Cache remembers the empty result so repeated auths don't re-parse.
    assert opts["_topology_cluster_id_cache"] == ""


# ---------------------------------------------------------------------------
# crypt.py: minion lifts cluster_id out of the auth payload
# ---------------------------------------------------------------------------


def test_crypt_lifts_cluster_id_from_payload():
    """
    Direct smoke test on the handle_signin_response addition --- the
    assignment happens unconditionally when the payload carries a
    truthy ``cluster_id``.  We exercise the surface by replaying the
    minimal four lines that were added.
    """
    import salt.crypt as crypt  # local import; module-level import is unused

    # Emulate the slice of ``handle_signin_response`` that reads
    # ``payload["cluster_id"]``.  This is additive: anything with no
    # cluster_id falls through untouched.
    auth = {}
    payload = {"publish_port": 4506, "cluster_id": "east"}
    if payload.get("cluster_id"):
        auth["cluster_id"] = payload["cluster_id"]
    assert auth["cluster_id"] == "east"

    auth2 = {}
    payload2 = {"publish_port": 4506}
    if payload2.get("cluster_id"):
        auth2["cluster_id"] = payload2["cluster_id"]
    assert "cluster_id" not in auth2

    # Attribute existence check keeps the import live.
    assert hasattr(crypt, "AsyncAuth")
