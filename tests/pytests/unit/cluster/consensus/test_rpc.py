"""Tests for ``salt.cluster.consensus.rpc`` wire helpers."""

import pytest

import salt.utils.event
from salt.cluster.consensus import rpc


def test_all_tags_start_with_cluster_raft():
    for tag in rpc.ALL_TAGS:
        assert tag.startswith("cluster/raft/")


def test_is_raft_tag_true():
    for tag in rpc.ALL_TAGS:
        assert rpc.is_raft_tag(tag) is True


def test_is_raft_tag_false():
    assert rpc.is_raft_tag("cluster/peer/foo") is False
    assert rpc.is_raft_tag("cluster/event/master1/blah") is False
    assert rpc.is_raft_tag("") is False


def test_pack_unpack_roundtrip():
    payload = {"term": 3, "granted": True}
    raw = rpc.pack(rpc.REQUEST_VOTE_REPLY, "node-a", "corr-123", payload)
    assert isinstance(raw, bytes)

    tag, src, rpc_id, raft_group_id, out = rpc.unpack(raw)
    assert tag == rpc.REQUEST_VOTE_REPLY
    assert src == "node-a"
    assert rpc_id == "corr-123"
    # Default group is the main cluster Raft log.
    assert raft_group_id == "cluster"
    assert out == payload


def test_pack_unpack_all_kinds():
    for tag in rpc.ALL_TAGS:
        raw = rpc.pack(tag, "src-node", "rid-1", {"x": 1})
        out_tag, out_src, out_rid, out_group, out_payload = rpc.unpack(raw)
        assert out_tag == tag
        assert out_src == "src-node"
        assert out_rid == "rid-1"
        assert out_group == "cluster"
        assert out_payload == {"x": 1}


def test_pack_unpack_carries_raft_group_id():
    """
    A non-default ``raft_group_id`` round-trips through the envelope.
    Multi-ring support depends on the field reaching the receiver
    intact so the dispatcher can pick the correct local ``Node``.
    """
    raw = rpc.pack(rpc.APPEND_ENTRIES, "src", "rid", {"x": 1}, raft_group_id="jobs")
    _, _, _, group, _ = rpc.unpack(raw)
    assert group == "jobs"


def test_unpack_pre_multi_ring_envelope_defaults_to_cluster():
    """
    Envelopes packed before multi-ring support omit
    ``raft_group_id``; ``unpack`` must default the field to
    ``"cluster"`` so old senders are still routed to the main cluster
    Raft group.
    """
    raw = salt.utils.event.SaltEvent.pack(
        rpc.REQUEST_VOTE,
        {"src": "n1", "rpc_id": "r1", "payload": {"term": 0}},
    )
    tag, src, rpc_id, group, payload = rpc.unpack(raw)
    assert tag == rpc.REQUEST_VOTE
    assert src == "n1"
    assert rpc_id == "r1"
    assert group == "cluster"
    assert payload == {"term": 0}


def test_unpack_malformed_envelope():
    # Pack with raw SaltEvent but missing required keys
    raw = salt.utils.event.SaltEvent.pack("cluster/raft/request-vote", {"bad": "data"})
    with pytest.raises(ValueError, match="Malformed Raft RPC envelope"):
        rpc.unpack(raw)
