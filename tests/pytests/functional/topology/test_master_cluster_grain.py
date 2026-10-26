"""
Functional tests for the ``master_cluster_id`` minion grain.

The grain is populated from the master's auth response, gated on
``topology_enabled`` + ``topology_push_cluster_grain`` on the master
(the latter defaults to True per RFC).  On topology-enabled masters
the field ``cluster_id`` is added to the auth response payload; the
minion lifts it into ``self.opts["master_cluster_id"]`` and the
``master_cluster_id`` grain function returns ``{"master_cluster_id":
<value>}``.  When absent, the grain is simply not present (empty
dict return).

Coverage:
* topology-enabled master pushes grain to attached minion
* non-topology master does NOT publish the grain
* ``grains.items`` carries the grain through full grain compilation
  (not stripped at serialization)
* ``top.sls`` pillar matcher targets the grain
"""

import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows,
]


# ---------------------------------------------------------------------------
# Positive: topology-enabled master -> minion sees master_cluster_id grain
# ---------------------------------------------------------------------------


def test_grain_present_on_topology_minion(single_master, attach_minion):
    """A minion attached to a topology-enabled master gets the grain."""
    cluster = single_master(cluster_id="east")
    minion = attach_minion(cluster)
    ret = minion.salt_call_cli().run("grains.get", "master_cluster_id")
    assert ret.returncode == 0, ret
    assert ret.data == "east"


def test_grain_survives_grains_items(single_master, attach_minion):
    """The grain survives full ``grains.items`` compilation."""
    cluster = single_master(cluster_id="west")
    minion = attach_minion(cluster)
    ret = minion.salt_call_cli().run("grains.items")
    assert ret.returncode == 0, ret
    assert isinstance(ret.data, dict), ret.data
    assert ret.data.get("master_cluster_id") == "west"


# ---------------------------------------------------------------------------
# Negative: non-topology master -> grain not present
# ---------------------------------------------------------------------------


def test_grain_absent_without_topology(single_master, attach_minion):
    """A minion attached to a non-topology master has no grain."""
    cluster = single_master(
        opts_overrides={"topology_enabled": False},
        cluster_id="plain",
    )
    minion = attach_minion(cluster)
    ret = minion.salt_call_cli().run("grains.get", "master_cluster_id")
    assert ret.returncode == 0, ret
    # grains.get for a missing key returns "" by default.
    assert ret.data in ("", {}, None), ret.data
    ret_items = minion.salt_call_cli().run("grains.items")
    assert ret_items.returncode == 0, ret_items
    assert "master_cluster_id" not in ret_items.data


def test_grain_absent_when_push_opt_disabled(single_master, attach_minion):
    """
    Topology-enabled master with ``topology_push_cluster_grain: False``
    does not publish the grain --- opt-out is honoured.
    """
    cluster = single_master(
        opts_overrides={"topology_push_cluster_grain": False},
        cluster_id="silent",
    )
    minion = attach_minion(cluster)
    ret = minion.salt_call_cli().run("grains.items")
    assert ret.returncode == 0, ret
    assert "master_cluster_id" not in ret.data


# ---------------------------------------------------------------------------
# Targeting: pillar top matches on master_cluster_id grain
# ---------------------------------------------------------------------------


def test_grain_matcher_targets_master_cluster_id(single_master, attach_minion):
    """
    The grain matcher accepts ``master_cluster_id:east`` as a target --- i.e.
    the grain is visible to Salt's targeting machinery, which is the primary
    use case for ``top.sls`` grain targeting (``- match: grain`` /
    ``- match: compound``).
    """
    cluster = single_master(cluster_id="east")
    minion = attach_minion(cluster)
    ret = minion.salt_call_cli().run("match.grain", "master_cluster_id:east")
    assert ret.returncode == 0, ret
    assert ret.data is True, ret.data
    # Non-matching cluster_id returns False, not an error.
    ret = minion.salt_call_cli().run("match.grain", "master_cluster_id:west")
    assert ret.returncode == 0, ret
    assert ret.data is False, ret.data
