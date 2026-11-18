"""
Unit tests for the NEW-10 collect-from-peers gate: ``filter_joined_pushers``
is consulted before sizing ``expected_peers`` on the collect sentinel so
the sentinel threshold matches the kept set.

Reviewer correction #2 is also exercised here: ``peers_eofed`` is a
per-peer set, not a monotonic counter.  A skipped peer whose cluster_aes
install races the fan-out and emits an eof cannot push the threshold
past the kept-count via counter arithmetic -- the correctness check is
"every kept peer has eof'd every channel", which can only be answered
with per-peer identity on each eof.

See ``salt/channel/server.py:_run_collect_from_peers``,
``_init_collect_sentinel``, ``_record_collect_chunk`` and the
``source_peer`` attribution in ``_handle_collect_request`` +
``_begin_root_sync_session``.
"""

import json
import os

import pytest

import salt.cache._cluster_replicator as _crep
import salt.utils.files
from salt.channel.server import MasterPubServerChannel


class _FakePusher:
    """Minimal duck-typed Pusher stand-in for the gate (pull_host only)."""

    def __init__(self, pull_host):
        self.pull_host = pull_host
        self.published = []

    async def publish(self, event):
        self.published.append(event)

    def __repr__(self):
        return f"_FakePusher({self.pull_host!r})"


def _collect_stub(cachedir):
    """
    Build a bare object that exposes only the attributes the
    production ``_init_collect_sentinel`` / ``_record_collect_chunk`` /
    ``_write_collect_sentinel`` implementations rely on.
    """
    stub = MasterPubServerChannel.__new__(MasterPubServerChannel)
    stub.opts = {"cachedir": str(cachedir)}
    stub._collect_status = None
    return stub


@pytest.fixture
def opts():
    return {
        "id": "master-requester",
        "cluster_id": "cluster-A",
        "cluster_cache_replicate_require_joined": True,
    }


@pytest.fixture(autouse=True)
def _reset_pending():
    _crep._reset_pending_state()
    yield
    _crep._reset_pending_state()


def test_gate_sizes_expected_peers_from_kept(tmp_path, opts):
    """
    Three pushers, two joined.  ``filter_joined_pushers`` keeps the two
    and ``expected_peers`` is sized from them, not the raw pushers
    list.  Threshold reaches ``complete=True`` after both kept peers
    eof every channel.
    """
    pushers = [_FakePusher("peer-A"), _FakePusher("peer-B"), _FakePusher("peer-C")]
    discover_replies = {"peer-A", "peer-B"}  # peer-C un-joined
    kept, skipped = _crep.filter_joined_pushers(
        pushers, discover_replies, {}, opts, context="collect-from-peers"
    )
    assert [p.pull_host for p in kept] == ["peer-A", "peer-B"]
    assert [p.pull_host for p in skipped] == ["peer-C"]
    expected_peers = [p.pull_host for p in kept]

    stub = _collect_stub(tmp_path)
    MasterPubServerChannel._init_collect_sentinel(
        stub, ["keys"], expected_peers, "master-requester", skipped_peers=["peer-C"]
    )
    assert stub._collect_status["expected_peers"] == ["peer-A", "peer-B"]
    assert stub._collect_status["skipped_peers"] == ["peer-C"]
    assert stub._collect_status["complete"] is False

    # One peer eofs -> not complete yet.
    MasterPubServerChannel._record_collect_chunk(
        stub, "keys", 1, eof=True, source_peer="peer-A"
    )
    assert stub._collect_status["complete"] is False
    # Second peer eofs -> complete.
    MasterPubServerChannel._record_collect_chunk(
        stub, "keys", 1, eof=True, source_peer="peer-B"
    )
    assert stub._collect_status["complete"] is True


def test_gate_straddler_peer_does_not_satisfy_threshold(tmp_path, opts):
    """
    Reviewer correction #2: a SKIPPED peer that somehow emits an eof
    (its cluster_aes install races the fan-out gate) must NOT count
    towards ``complete=True``.  With a monotonic counter the stray
    eof + the kept peer's eof would hit the threshold of 2 (==
    len(kept)); with per-peer set tracking, the stray peer is NOT in
    ``expected_peers`` so the subset check still requires every kept
    peer to be in ``peers_eofed``.
    """
    stub = _collect_stub(tmp_path)
    MasterPubServerChannel._init_collect_sentinel(
        stub,
        ["keys"],
        ["peer-A", "peer-B"],
        "master-requester",
        skipped_peers=["peer-C"],
    )

    # Stray eof from the skipped peer first.
    MasterPubServerChannel._record_collect_chunk(
        stub, "keys", 1, eof=True, source_peer="peer-C"
    )
    assert stub._collect_status["complete"] is False

    # Then one of the two expected peers eofs.
    MasterPubServerChannel._record_collect_chunk(
        stub, "keys", 1, eof=True, source_peer="peer-A"
    )
    # Threshold NOT reached: we need peer-A AND peer-B.  With a
    # monotonic counter this would have flipped to True (2 >= 2).
    assert stub._collect_status["complete"] is False
    assert stub._collect_status["per_channel"]["keys"]["eofs_seen"] == 2

    # Finally the second expected peer eofs.
    MasterPubServerChannel._record_collect_chunk(
        stub, "keys", 1, eof=True, source_peer="peer-B"
    )
    assert stub._collect_status["complete"] is True


def test_sentinel_tracks_per_peer_not_counter(tmp_path, opts):
    """
    The sentinel's per-channel state carries a ``peers_eofed`` list,
    sorted for JSON-serialisable stability, in addition to the
    monotonic ``eofs_seen`` back-compat counter.
    """
    stub = _collect_stub(tmp_path)
    MasterPubServerChannel._init_collect_sentinel(
        stub,
        ["keys", "bank:jobs/loads"],
        ["peer-A", "peer-B"],
        "master-requester",
    )

    MasterPubServerChannel._record_collect_chunk(
        stub, "keys", 0, eof=False, source_peer="peer-B"
    )
    MasterPubServerChannel._record_collect_chunk(
        stub, "keys", 2, eof=True, source_peer="peer-B"
    )
    MasterPubServerChannel._record_collect_chunk(
        stub, "keys", 3, eof=True, source_peer="peer-A"
    )

    per_ch = stub._collect_status["per_channel"]["keys"]
    assert per_ch["peers_eofed"] == ["peer-A", "peer-B"]
    assert per_ch["eofs_seen"] == 2  # back-compat counter

    # Other channel has nothing yet, so NOT complete.
    assert stub._collect_status["complete"] is False
    MasterPubServerChannel._record_collect_chunk(
        stub, "bank:jobs/loads", 1, eof=True, source_peer="peer-A"
    )
    assert stub._collect_status["complete"] is False
    MasterPubServerChannel._record_collect_chunk(
        stub, "bank:jobs/loads", 1, eof=True, source_peer="peer-B"
    )
    assert stub._collect_status["complete"] is True


def test_sentinel_written_on_disk_is_json_serialisable(tmp_path):
    """
    Guard against a regression where the per-peer set is stored as a
    Python ``set()`` and the JSON writer fails.  Reviewer flagged
    this explicitly as the one-line JSON-serialisation complication.
    """
    stub = _collect_stub(tmp_path)
    MasterPubServerChannel._init_collect_sentinel(
        stub, ["keys"], ["peer-A"], "master-requester", skipped_peers=["peer-B"]
    )
    MasterPubServerChannel._record_collect_chunk(
        stub, "keys", 1, eof=True, source_peer="peer-A"
    )

    # The atomicfile writer persists to disk; reload and compare.
    path = os.path.join(str(tmp_path), "cluster-collect-status.json")
    with salt.utils.files.fopen(path) as fp:
        doc = json.load(fp)
    assert doc["complete"] is True
    assert doc["skipped_peers"] == ["peer-B"]
    assert doc["per_channel"]["keys"]["peers_eofed"] == ["peer-A"]
    assert doc["per_channel"]["keys"]["eofs_seen"] == 1


def test_gate_aborts_when_no_peers_joined(opts):
    """
    Every pusher un-joined -> ``filter_joined_pushers`` returns an
    empty ``kept``.  The caller is expected to still write a sentinel
    so operators see a deterministic result, but NOT emit any
    collect-requests.
    """
    pushers = [_FakePusher("peer-A"), _FakePusher("peer-B")]
    kept, skipped = _crep.filter_joined_pushers(
        pushers, set(), {}, opts, context="collect-from-peers"
    )
    assert kept == []
    assert sorted(p.pull_host for p in skipped) == ["peer-A", "peer-B"]
