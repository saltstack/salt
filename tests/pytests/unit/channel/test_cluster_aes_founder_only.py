"""
Unit tests for the founder-predicate helpers and the deprecated
``filter_non_founder_cluster_aes_from_join_reply`` shim.

Background
----------

Each master in a bootstrapping cluster runs ``read_or_generate_key()``
and lands a locally-generated random ``cluster_aes`` in its own
``cluster_pki_dir/.aes``.  Only the master designated as the
founder (the lowest-id member of ``{self, *cluster_peers}``) holds
the authoritative cluster-wide ``cluster_aes``; non-founders overwrite
their bootstrap value when they receive the founder's join-reply.

Historical two-layer defence (commit ``6acb1653613``):

1. Sender-side gate in the ``cluster/peer/join`` handler: only the
   founder attached ``cluster_aes`` to ``inner_payload``.

2. Receiver-side filter at the ``cluster/peer/join-reply`` install
   site: ``filter_non_founder_cluster_aes_from_join_reply`` dropped
   the attached field if the sender wasn't the designated founder.

That identity-based pair permanently broke late-joiner propagation:
once the founder died, a surviving non-founder could not deliver
``cluster_aes`` to a brand-new master joining through it.

Current design (unified cluster-key propagation primitive)
----------------------------------------------------------

The sender ships ``cluster_aes`` unconditionally; the receiver
installs or rejects based on its own per-key bootstrap-vs-committed
state machine with a founder-wait window during bootstrap.  Identity
is consulted only by the receiver (to decide whether to honour the
first-arriving install or wait for the founder's reply).

``is_designated_cluster_founder`` / ``_cluster_bootstrap_founder_id``
remain in use by the receiver's founder-wait window.
``filter_non_founder_cluster_aes_from_join_reply`` is kept as a
deprecated no-op shim so cross-fork integrators who pulled the
original commit continue to build.
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
# Deprecated receiver-side filter shim
# ---------------------------------------------------------------------------
#
# Behaviour after deprecation: ``filter_non_founder_cluster_aes_from_join_reply``
# unconditionally returns ``(inner, False)`` and emits a one-shot
# DeprecationWarning-style log line per process.  The tests here lock
# that contract so cross-fork integrators who pulled commit 6 as a
# backport candidate get a predictable no-op.


@pytest.fixture
def opts_as_joiner():
    """
    A joiner (non-founder) that previously relied on the filter to
    reject cluster_aes from any peer other than the designated
    founder.  The filter is now a no-op shim.
    """
    return {
        "id": "m2",
        "cluster_id": "cluster-A",
        "cluster_peers": ["m1", "m3"],
    }


@pytest.fixture(autouse=True)
def _reset_filter_deprecation_warned_flag(monkeypatch):
    """
    The deprecation WARN is emitted at most once per process via a
    module-level flag.  Reset it between tests so each test can
    independently assert its emission (or absence).
    """
    import salt.channel.server as _ch

    monkeypatch.setattr(_ch, "_FILTER_DEPRECATION_WARNED", False)
    yield
    monkeypatch.setattr(_ch, "_FILTER_DEPRECATION_WARNED", False)


def test_filter_is_noop_for_founder_sourced_reply(opts_as_joiner):
    """
    Founder-sourced join-reply: the shim still returns the input
    unchanged with ``was_filtered=False``.
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
    assert filtered is inner
    assert filtered["cluster_aes"] == b"<founder-ciphertext>"


def test_filter_is_noop_for_non_founder_sourced_reply(opts_as_joiner):
    """
    Non-founder join-reply with ``cluster_aes``: the shim NO LONGER
    drops the field (the receiver state machine gates the install
    instead).  Return value is the original dict unchanged.
    """
    inner = {
        "peer_id": "m3",  # NOT the founder
        "cluster_aes": b"<bootstrap-ciphertext>",
        "cluster_pem": b"<pem>",
        "return_token": b"tok",
    }
    filtered, was_filtered = filter_non_founder_cluster_aes_from_join_reply(
        inner, opts_as_joiner
    )
    assert was_filtered is False
    # No copy, no field removed -- state machine handles it later.
    assert filtered is inner
    assert filtered["cluster_aes"] == b"<bootstrap-ciphertext>"
    assert filtered["cluster_pem"] == b"<pem>"


def test_filter_passthrough_when_no_cluster_aes_present(opts_as_joiner):
    """
    Reply without ``cluster_aes``: still a no-op.
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
    assert filtered is inner


def test_filter_handles_non_dict_input_gracefully():
    """
    Defensive: a malformed payload (non-dict) still passes through
    unchanged under the shim.
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


def test_filter_emits_one_shot_deprecation_warning(opts_as_joiner, caplog):
    """
    The shim emits a deprecation WARN exactly once per process on
    first call; subsequent calls are silent.
    """
    import logging as _logging

    caplog.set_level(_logging.WARNING, logger="salt.channel.server")
    inner = {"peer_id": "m1", "cluster_aes": b"<x>"}
    filter_non_founder_cluster_aes_from_join_reply(inner, opts_as_joiner)
    filter_non_founder_cluster_aes_from_join_reply(inner, opts_as_joiner)
    deprecation_records = [
        r
        for r in caplog.records
        if "deprecated" in r.getMessage()
        and "filter_non_founder_cluster_aes_from_join_reply" in r.getMessage()
    ]
    assert len(deprecation_records) == 1, (
        "Expected the deprecation WARN exactly once; got " f"{len(deprecation_records)}"
    )
