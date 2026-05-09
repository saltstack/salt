"""
Unit tests for the ``cluster`` runner — currently the read-only
``ring_info`` query and the explicit ``NotImplementedError`` from
``ring_set``.

The proposal path is deferred (see ``GAPS.md``); these tests pin
the contract that operators see today so a follow-up that lights up
the propose path can update them in lockstep.
"""

import pytest

from salt.cluster import ring_membership
from salt.runners import cluster as cluster_runner


@pytest.fixture(autouse=True)
def _isolate_ring():
    """Each test gets a fresh empty ring; cleanup also resets it."""
    ring_membership.reset()
    yield
    ring_membership.reset()


def test_ring_info_default_state():
    """
    A runner subprocess has never received a rebuild — the ring is
    empty.  ``is_clustered`` is False, ``node_count`` is 0, the nodes
    list is empty.  Stable shape so the docs / runbook never lie.
    """
    info = cluster_runner.ring_info()
    assert info["is_clustered"] is False
    assert info["node_count"] == 0
    assert info["nodes"] == []
    # ``vnodes`` is computed from the token table; an empty ring has 0
    # tokens so the answer is 0 rather than the default-150 constant.
    assert info["vnodes"] == 0


def test_ring_info_after_rebuild():
    """
    A populated ring round-trips through ``ring_info`` cleanly.  This
    is the shape stage 2 will see once the runner's ring is sourced
    from the same SM the publish daemon's ring is.
    """
    ring_membership.rebuild(["m1", "m2", "m3"])
    info = cluster_runner.ring_info()
    assert info["is_clustered"] is True
    assert info["node_count"] == 3
    assert info["nodes"] == ["m1", "m2", "m3"]
    assert info["vnodes"] >= 1


def test_ring_set_raises_until_propose_path_lands():
    """
    Operators who try to commit a new policy through the runner today
    must see a loud failure rather than a silent no-op.  ``ring_set``
    raises :class:`NotImplementedError` until the runner-to-master
    IPC arrives.
    """
    with pytest.raises(NotImplementedError):
        cluster_runner.ring_set(members="voters", replicas=2)


def test_ring_set_raises_with_no_args_too():
    """``ring_set`` raises before validating arguments."""
    with pytest.raises(NotImplementedError):
        cluster_runner.ring_set()
