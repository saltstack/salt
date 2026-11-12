"""
Unit tests for :meth:`salt.cluster.consensus.raft.topology.TopologyStateMachine.next_hop`
leader-only semantics (RFC implementation-follow-up item 5).

The RFC decision: routing queries are leader-only.  Followers (any
process that does not own the :mod:`salt.topology.link_manager`
state) must raise :class:`NotLeaderError` rather than return
``None`` --- ``None`` is reserved for the unambiguous "no route
exists" case, so returning ``None`` on a follower would be
indistinguishable from "I can tell there is no route".
"""

import os

import pytest

import salt.topology.link_manager as link_manager
from salt.cluster.consensus.raft.topology import NotLeaderError, TopologyStateMachine

pytestmark = [
    pytest.mark.skip_on_windows,
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def opts(tmp_path):
    master_dir = tmp_path / "master"
    master_dir.mkdir(parents=True, exist_ok=True)
    return {
        "pki_dir": str(tmp_path),
        "topology_registry_cache_size": 1024,
        "topology_registry_cache_key_size": 64,
        "keysize": 2048,
        "hash_type": "sha256",
    }


@pytest.fixture
def sm(opts):
    machine = TopologyStateMachine(opts)
    try:
        yield machine
    finally:
        try:
            machine.registry.close()
        except Exception:  # pylint: disable=broad-except
            pass


@pytest.fixture
def patch_link_manager(monkeypatch):
    """Return a helper that patches link_manager module globals via
    monkeypatch so attribute restoration happens in teardown (and the
    pylint ``unmocked-patch`` rule is satisfied)."""

    def _patch(owner_pid=None, links=None, inbound=None):
        monkeypatch.setattr(link_manager, "_OWNER_PID", owner_pid)
        monkeypatch.setattr(link_manager, "_LINKS", dict(links or {}))
        monkeypatch.setattr(link_manager, "_INBOUND", dict(inbound or {}))

    return _patch


# ---------------------------------------------------------------------------
# Follower (non-owner) raises NotLeaderError
# ---------------------------------------------------------------------------


def test_next_hop_follower_raises_not_leader(sm, patch_link_manager):
    """When link_manager has no owner, next_hop raises NotLeaderError."""
    patch_link_manager(owner_pid=None)
    with pytest.raises(NotLeaderError):
        sm.next_hop("east")


def test_next_hop_wrong_pid_owner_raises_not_leader(sm, patch_link_manager):
    """Owner PID set to a different process -> follower treatment."""
    patch_link_manager(owner_pid=os.getpid() + 1_000_000)
    with pytest.raises(NotLeaderError):
        sm.next_hop("east")


def test_not_leader_error_message_names_cause(sm, patch_link_manager):
    """The error message is specific enough for an operator to diagnose."""
    patch_link_manager(owner_pid=None)
    with pytest.raises(NotLeaderError) as exc_info:
        sm.next_hop("east")
    msg = str(exc_info.value)
    assert "leader-only" in msg
    assert "link_manager" in msg


# ---------------------------------------------------------------------------
# Leader returns the correct next hop
# ---------------------------------------------------------------------------


class _StubLink:
    """Minimal link stand-in; only ``peer_cluster_id`` is read."""

    def __init__(self, peer_cluster_id):
        self.peer_cluster_id = peer_cluster_id


def test_next_hop_leader_direct_link(sm, patch_link_manager):
    """Leader with a direct link returns that peer's cluster_id."""
    patch_link_manager(owner_pid=os.getpid(), links={"east": _StubLink("east")})
    assert sm.next_hop("east") == "east"


def test_next_hop_leader_inbound_link(sm, patch_link_manager):
    """A direct link registered on the inbound side is also a valid next hop."""
    patch_link_manager(owner_pid=os.getpid(), inbound={"south": _StubLink("south")})
    assert sm.next_hop("south") == "south"


def test_next_hop_leader_unknown_target_returns_none(sm, patch_link_manager):
    """Leader with no route for the target returns ``None`` (unambiguous)."""
    patch_link_manager(owner_pid=os.getpid(), links={"east": _StubLink("east")})
    assert sm.next_hop("mars") is None


def test_next_hop_leader_provisional_link_returns_none(sm, patch_link_manager):
    """A pre-handshake (peer_cluster_id=None) link is not a usable route."""
    patch_link_manager(owner_pid=os.getpid(), links={"pending": _StubLink(None)})
    # get_link("pending") returns the stub, which has peer_cluster_id=None.
    assert sm.next_hop("pending") is None


# ---------------------------------------------------------------------------
# Documented behavior appears in the docstring
# ---------------------------------------------------------------------------


def test_next_hop_docstring_mentions_leader_only(sm):
    """The method docstring documents the leader-only contract."""
    doc = sm.next_hop.__doc__ or ""
    assert "leader" in doc.lower()
    assert "NotLeaderError" in doc


def test_not_leader_error_is_runtime_error(sm):
    """NotLeaderError is a RuntimeError subclass (catchable by generic handlers)."""
    assert issubclass(NotLeaderError, RuntimeError)
