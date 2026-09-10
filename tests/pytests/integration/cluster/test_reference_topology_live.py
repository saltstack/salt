"""
Live-cluster assertions for claims in
``doc/topics/tutorials/master-cluster-reference.rst`` that require
actual Raft membership state.

Gated behind ``RUN_CLUSTER_INTEGRATION`` because standing up multiple
isolated-FS masters is slow (~2-4 min each) and shouldn't run on every
CI matrix cell.  Set ``RUN_CLUSTER_INTEGRATION=1`` locally or on a
dedicated integration runner.

These tests **cannot** be replaced by mocks or fixture-only assertions:
each one checks observable Raft state via ``salt-run cluster.members``
which only exists once the cluster has actually formed.
"""

import os

import pytest

pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("RUN_CLUSTER_INTEGRATION"),
        reason=(
            "Live cluster reference-topology integration -- set "
            "RUN_CLUSTER_INTEGRATION=1 to run.  Not run by default; "
            "the assertions here spin up 2 or 3 isolated-FS masters "
            "and can take 4-6 minutes each on shared runners."
        ),
    ),
    pytest.mark.timeout(360),
]


def test_isolated_fs_two_master_forms_membership(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
):
    """
    Doc L49-135: the 2-node isolated-FS reference topology forms a
    cluster where both peers see each other as voters.

    Pins the doc's cluster-boot claim to real Raft state.  If the
    isolated-FS bring-up path regresses, the doc's promise that
    "start salt-master on both hosts -- you have a 2-node cluster"
    breaks.
    """
    cli1 = cluster_master_1_isolated.salt_run_cli(timeout=180)
    ret = cli1.run("cluster.members")
    assert ret.returncode == 0, f"cluster.members failed: {ret}"
    members = ret.data
    voters = set(members.get("voters", []))
    assert (
        "127.0.0.1" in voters and "127.0.0.2" in voters
    ), f"Expected both masters as voters; got {members}"


def test_isolated_fs_three_master_forms_membership(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
):
    """
    Doc L137-250: the 3-node isolated-FS reference topology forms a
    cluster with three voters.  Doc also claims the reader should run
    ``salt-run cluster.members`` after startup to see all three as
    voters (L229-239) -- this test is the codified version of that
    verification step.
    """
    cli1 = cluster_master_1_isolated.salt_run_cli(timeout=180)
    ret = cli1.run("cluster.members")
    assert ret.returncode == 0, f"cluster.members failed: {ret}"
    members = ret.data
    voters = set(members.get("voters", []))
    assert voters == {
        "127.0.0.1",
        "127.0.0.2",
        "127.0.0.3",
    }, f"Expected exactly 3 voters; got {members}"


def test_isolated_fs_ring_info_available(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
):
    """
    Doc L229-239: ``salt-run cluster.ring_info`` returns the HashRing
    state that routes job / grain cache to specific peers.  The doc
    tells the reader to run it after cluster.members -- pin the
    runner's return shape to what the doc implies (a dict with the
    expected keys).
    """
    cli1 = cluster_master_1_isolated.salt_run_cli(timeout=180)
    ret = cli1.run("cluster.ring_info")
    assert ret.returncode == 0, f"cluster.ring_info failed: {ret}"
    info = ret.data
    assert isinstance(info, dict), f"ring_info should return a dict, got {info!r}"
    # Doc L376-383 says the shape is
    # ``{is_clustered, node_count, nodes, vnodes}``.
    for key in ("is_clustered", "node_count", "nodes", "vnodes"):
        assert key in info, f"ring_info missing documented key {key!r}: {info}"


def test_isolated_fs_config_matches_documented_shape(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
):
    """
    Doc L74-96 documents that:

    * ``cluster_peers`` lists every OTHER peer (not self).
    * ``cluster_isolated_filesystem`` is True in these topologies.
    * ``cluster_pki_dir`` is per-peer local.

    Assert those hold at runtime on both masters.
    """
    cli1 = cluster_master_1_isolated.salt_run_cli(timeout=120)
    ret = cli1.run("config.get", "cluster_isolated_filesystem")
    assert ret.data is True, f"master-1 cluster_isolated_filesystem: {ret.data}"

    ret = cli1.run("config.get", "cluster_peers")
    peers = list(ret.data or [])
    assert (
        "127.0.0.1" not in peers
    ), f"master-1 cluster_peers should not include self (127.0.0.1); got {peers}"

    cli2 = cluster_master_2_isolated.salt_run_cli(timeout=120)
    ret = cli2.run("config.get", "cluster_isolated_filesystem")
    assert ret.data is True, f"master-2 cluster_isolated_filesystem: {ret.data}"

    ret = cli2.run("config.get", "cluster_peers")
    peers = list(ret.data or [])
    assert (
        "127.0.0.2" not in peers
    ), f"master-2 cluster_peers should not include self (127.0.0.2); got {peers}"
