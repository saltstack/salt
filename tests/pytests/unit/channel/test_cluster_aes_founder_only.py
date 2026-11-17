"""
Unit tests for the founder-only ``cluster_aes`` gate in the
``cluster/peer/join-reply`` path.

Background
----------

Each master in a bootstrapping cluster runs ``read_or_generate_key()``
and lands a locally-generated random ``cluster_aes`` in its own
``cluster_pki_dir/.aes``.  Only the master designated as the
founder (the lowest-id member of ``{self, *cluster_peers}``) holds
the authoritative cluster-wide ``cluster_aes``; non-founders overwrite
their bootstrap value when they receive the founder's join-reply.

The sender-side responder to ``cluster/peer/join`` previously
attached ``SMaster.secrets["cluster_aes"]["secret"].value`` to every
``cluster/peer/join-reply`` regardless of founder identity.  A
non-founder that received a ``cluster/peer/discover`` from a third
master during its own bootstrap window would reply with its
locally-generated bootstrap ``cluster_aes``; if that reply landed on
the receiver AFTER the founder's reply, the receiver would overwrite
the founder's authoritative value with the non-founder's bootstrap
value.  In the three-master topology this produces a persistent
``m1 != m2 == m3`` disagreement; writes from m1 then decrypt-fail on
m2/m3.  Agent #148 traced this timeline in CI run 43983101731
(arm64 integration-3).

Fix
---

Two-layer defence:

1. Sender-side gate in the ``cluster/peer/join`` handler: only the
   founder attaches ``cluster_aes`` to ``inner_payload``.
   Tested here indirectly via ``is_designated_cluster_founder``
   -- the guard the handler calls to decide whether to attach.

2. Receiver-side filter at the ``cluster/peer/join-reply`` install
   site: ``filter_non_founder_cluster_aes_from_join_reply`` drops
   the attached field if the sender isn't the designated founder.
"""

import pytest

from salt.channel.server import (
    _cluster_bootstrap_founder_id,
    filter_non_founder_cluster_aes_from_join_reply,
    is_designated_cluster_founder,
)

# ---------------------------------------------------------------------------
# Founder predicate
# ---------------------------------------------------------------------------


def test_lowest_id_master_is_founder():
    """
    Three-master bootstrap: ``id`` lexicographically lowest is the
    founder.  ``127.0.0.1`` (our master) is lower than ``127.0.0.2``
    and ``127.0.0.3`` so this master is the founder.
    """
    opts = {
        "id": "127.0.0.1",
        "cluster_id": "cluster-A",
        "cluster_peers": ["127.0.0.2", "127.0.0.3"],
    }
    assert _cluster_bootstrap_founder_id(opts) == "127.0.0.1"
    assert is_designated_cluster_founder(opts) is True


def test_non_lowest_id_master_is_not_founder():
    """
    Mid-id master: founder is the lowest-id peer, not this one.
    """
    opts = {
        "id": "127.0.0.2",
        "cluster_id": "cluster-A",
        "cluster_peers": ["127.0.0.1", "127.0.0.3"],
    }
    assert _cluster_bootstrap_founder_id(opts) == "127.0.0.1"
    assert is_designated_cluster_founder(opts) is False


def test_highest_id_master_is_not_founder():
    """
    Highest-id master: founder is the lowest-id peer, not this one.
    """
    opts = {
        "id": "127.0.0.3",
        "cluster_id": "cluster-A",
        "cluster_peers": ["127.0.0.1", "127.0.0.2"],
    }
    assert _cluster_bootstrap_founder_id(opts) == "127.0.0.1"
    assert is_designated_cluster_founder(opts) is False


def test_founder_predicate_matches_bootstrap_decision():
    """
    The founder predicate used by the join-reply sender MUST match
    the bootstrap decision used by ``_publish_daemon``.  Both sort
    ``{self_id, *cluster_peers}`` and pick the first element.  This
    test pins that the two paths agree for a four-master cluster
    with non-trivial id ordering.
    """
    peers = ["master-c", "master-a", "master-d"]
    # Each master sees the same bootstrap pool (sorted) and the same
    # founder -- the designated bootstrap voter.
    for self_id, expected_is_founder in [
        ("master-a", True),  # lowest id wins
        ("master-b", False),
        ("master-c", False),
        ("master-d", False),
    ]:
        opts = {
            "id": self_id,
            "cluster_id": "cluster-X",
            "cluster_peers": [p for p in peers + ["master-b"] if p != self_id],
        }
        assert is_designated_cluster_founder(opts) is expected_is_founder


def test_single_master_is_trivially_founder():
    """
    Single-master cluster (empty peers): the master is trivially
    the founder -- its own id is the only id in the pool.
    """
    opts = {"id": "solo", "cluster_id": "cluster-S", "cluster_peers": []}
    assert _cluster_bootstrap_founder_id(opts) == "solo"
    assert is_designated_cluster_founder(opts) is True


# ---------------------------------------------------------------------------
# Receiver-side filter
# ---------------------------------------------------------------------------


@pytest.fixture
def opts_as_joiner():
    """
    A joiner (non-founder) that expects founder ``m1`` to respond
    with cluster_aes and rejects cluster_aes from any other peer.
    """
    return {
        "id": "m2",
        "cluster_id": "cluster-A",
        "cluster_peers": ["m1", "m3"],
    }


def test_receiver_accepts_cluster_aes_from_founder(opts_as_joiner):
    """
    Founder-sourced join-reply is accepted unchanged: filter returns
    the input dict and ``was_filtered=False``.
    """
    inner = {
        "peer_id": "m1",  # founder
        "cluster_aes": b"<founder-ciphertext>",
        "return_token": b"tok",
    }
    filtered, was_filtered = filter_non_founder_cluster_aes_from_join_reply(
        inner, opts_as_joiner
    )
    assert was_filtered is False
    assert "cluster_aes" in filtered
    assert filtered["cluster_aes"] == b"<founder-ciphertext>"


def test_receiver_drops_cluster_aes_from_non_founder(opts_as_joiner):
    """
    A non-founder's join-reply with cluster_aes is filtered: the
    returned dict is a NEW dict (original is not mutated) with
    ``cluster_aes`` removed, and ``was_filtered=True``.
    """
    inner = {
        "peer_id": "m3",  # NOT the founder (m1 is)
        "cluster_aes": b"<bootstrap-ciphertext>",
        "cluster_pem": b"<pem>",
        "return_token": b"tok",
    }
    filtered, was_filtered = filter_non_founder_cluster_aes_from_join_reply(
        inner, opts_as_joiner
    )
    assert was_filtered is True
    assert "cluster_aes" not in filtered
    # Other fields preserved -- static per-cluster material still
    # installed from non-founder replies.
    assert filtered["cluster_pem"] == b"<pem>"
    assert filtered["return_token"] == b"tok"
    # Original dict not mutated -- defence against caller re-use.
    assert "cluster_aes" in inner


def test_receiver_passthrough_when_no_cluster_aes_present(opts_as_joiner):
    """
    A reply without ``cluster_aes`` (e.g. from a non-founder that
    already honours the sender-side gate) passes through unmodified
    and ``was_filtered=False``.
    """
    inner = {
        "peer_id": "m3",
        "cluster_pem": b"<pem>",
        "return_token": b"tok",
    }
    filtered, was_filtered = filter_non_founder_cluster_aes_from_join_reply(
        inner, opts_as_joiner
    )
    assert was_filtered is False
    assert filtered is inner  # no-copy fast path


def test_receiver_drops_cluster_aes_when_sender_id_missing(opts_as_joiner):
    """
    A reply with ``cluster_aes`` but no ``peer_id`` field (malformed
    or forged) MUST be filtered -- we cannot verify the sender is
    the founder.
    """
    inner = {
        "cluster_aes": b"<unknown-source-ciphertext>",
    }
    filtered, was_filtered = filter_non_founder_cluster_aes_from_join_reply(
        inner, opts_as_joiner
    )
    assert was_filtered is True
    assert "cluster_aes" not in filtered


def test_founder_receiver_accepts_cluster_aes_from_itself_identity():
    """
    Edge case: a founder re-processes its own join-reply (should not
    happen in practice -- a master doesn't send discover to itself --
    but the filter must not corrupt the identity case).  When
    ``peer_id`` equals the founder id, the field is kept.
    """
    opts = {
        "id": "m1",
        "cluster_id": "cluster-A",
        "cluster_peers": ["m2", "m3"],
    }
    inner = {
        "peer_id": "m1",  # founder sending to itself
        "cluster_aes": b"<founder-ciphertext>",
    }
    filtered, was_filtered = filter_non_founder_cluster_aes_from_join_reply(inner, opts)
    assert was_filtered is False
    assert filtered["cluster_aes"] == b"<founder-ciphertext>"


def test_receiver_filter_handles_non_dict_input_gracefully():
    """
    Defensive: a malformed payload (non-dict) passes through
    unchanged.  The caller will almost certainly crash downstream
    but the filter must not raise on its own.
    """
    opts = {
        "id": "m2",
        "cluster_id": "cluster-A",
        "cluster_peers": ["m1", "m3"],
    }
    filtered, was_filtered = filter_non_founder_cluster_aes_from_join_reply(
        "not-a-dict", opts
    )
    assert was_filtered is False
    assert filtered == "not-a-dict"
