"""
Regression tests for issue #70567.

Unit tests for :func:`salt.cluster.node_id` -- the single cluster-wide
identity for a master.
"""

import pytest

import salt.cluster


@pytest.mark.parametrize(
    "configured_id,expected",
    [
        # ``apply_master_config`` returns this when ``id`` is not ste explicitly
        ("salt-master-1_master", "salt-master-1"),
        # An explicitly configured id is already the bare name.
        ("salt-master-1", "salt-master-1"),
        # Only a trailing suffix is removed, and only one.
        ("salt_master_pool_master", "salt_master_pool"),
        ("master", "master"),
        ("_master", ""),
        ("master-of-none", "master-of-none"),
    ],
)
def test_node_id_strips_only_the_trailing_master_suffix(configured_id, expected):
    assert salt.cluster.node_id({"id": configured_id}) == expected


def test_node_id_ignores_interface():
    """
    ``opts["interface"]`` must not contribute to the identity.
    """
    opts = {"id": "salt-master-1_master", "interface": "0.0.0.0"}
    assert salt.cluster.node_id(opts) == "salt-master-1"
    opts["interface"] = "[::]"
    assert salt.cluster.node_id(opts) == "salt-master-1"


@pytest.mark.parametrize(
    "my_id,peers,expect_founder",
    [
        # Sorting first in the pool makes this master the founder.
        ("salt-master-1_master", ["salt-master-2", "salt-master-3"], True),
        # Sorting later does not.
        ("salt-master-2_master", ["salt-master-1", "salt-master-3"], False),
        ("salt-master-3_master", ["salt-master-1", "salt-master-2"], False),
        # A single-master cluster founds itself.
        ("salt-master-1_master", [], True),
    ],
)
def test_founding_voter_election_is_decidable(my_id, peers, expect_founder):
    """
    Exactly one master must see itself as the designated founder.
    """
    node_id = salt.cluster.node_id({"id": my_id, "interface": "0.0.0.0"})
    bootstrap_pool = sorted({node_id, *peers})
    is_founder = bool(bootstrap_pool) and bootstrap_pool[0] == node_id
    assert is_founder is expect_founder


def test_founding_voter_election_elects_exactly_one():
    """
    Run the election from every master's point of view at once.
    """
    names = ["salt-master-1", "salt-master-2", "salt-master-3"]
    founders = []
    for name in names:
        opts = {"id": f"{name}_master", "interface": "0.0.0.0"}
        node_id = salt.cluster.node_id(opts)
        peers = [n for n in names if n != name]
        bootstrap_pool = sorted({node_id, *peers})
        if bootstrap_pool[0] == node_id:
            founders.append(name)
    assert founders == ["salt-master-1"], (
        "exactly one master may found the cluster; with the identity split "
        f"this returned {founders!r}"
    )
