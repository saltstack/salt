"""
Unit tests for the sender-side handshake gate and decrypt-failure log
helpers in :mod:`salt.cache._cluster_replicator`.

The sender-side gate consults the publish daemon's ``_discover_replies``
/ ``peer_keys`` state and filters the ``pushers`` list before firing a
``cluster_aes``-encrypted replication event.  Peers that have not
completed the cluster discover/join handshake cannot decrypt the
payload; skipping them converts the silent-loss failure mode into a
WARN on the sender side.  The fan-out catch-up happens through the
state-sync stream initiated by the join-reply handler, backed by the
sender-side pending-replication queue that replays live writes a peer
missed during its join window.

The decrypt-failure log helper emits a correlatable, rate-limited
log on the receiver side when ``cluster_aes`` decrypt fails.
"""

import asyncio
import hashlib
import logging
import time

import pytest

import salt.cache._cluster_replicator as _crep

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _FakePusher:
    """Minimal duck-typed Pusher stand-in for the gate (pull_host only)."""

    def __init__(self, pull_host):
        self.pull_host = pull_host

    def __repr__(self):
        return f"_FakePusher({self.pull_host!r})"


@pytest.fixture
def opts():
    return {
        "id": "master-1",
        "cluster_id": "cluster-A",
        "cluster_cache_replicate_require_joined": True,
    }


@pytest.fixture(autouse=True)
def _reset_skip_log_state():
    """Reset coalescing counters so tests don't bleed into each other."""
    _crep._SKIP_LOG_LAST.clear()
    _crep._DECRYPT_LOG_LAST.clear()
    _crep._reset_pending_state()
    yield
    _crep._SKIP_LOG_LAST.clear()
    _crep._DECRYPT_LOG_LAST.clear()
    _crep._reset_pending_state()


class _FakeAsyncPusher:
    """Pusher stand-in whose ``publish`` is an awaitable that records payloads."""

    def __init__(self, pull_host, fail_at=None):
        self.pull_host = pull_host
        self.published = []
        self.fail_at = fail_at  # index at which to raise (one-shot)

    async def publish(self, event):
        if self.fail_at is not None and len(self.published) == self.fail_at:
            self.fail_at = None
            raise RuntimeError("simulated publish error")
        self.published.append(event)


# ---------------------------------------------------------------------------
# peer_is_joined
# ---------------------------------------------------------------------------


def test_peer_is_joined_from_discover_replies():
    # Primary signal: the peer sent us a discover-reply.
    assert _crep.peer_is_joined({"peer-a"}, {}, "peer-a") is True


def test_peer_is_joined_from_peer_keys():
    # Secondary signal: the peer's session key is installed; this is
    # a strictly-later-but-equivalent handshake indicator.
    assert _crep.peer_is_joined(set(), {"peer-a": b"key"}, "peer-a") is True


def test_peer_is_not_joined_when_unknown():
    assert _crep.peer_is_joined({"peer-a"}, {}, "peer-b") is False


def test_peer_is_not_joined_on_empty_host():
    assert _crep.peer_is_joined({"peer-a"}, {}, None) is False
    assert _crep.peer_is_joined({"peer-a"}, {}, "") is False


def test_peer_is_joined_matches_bare_host_when_port_suffix_present():
    # Operators list peers as "host:port"; the handshake handlers key
    # on the bare host.  The gate must accept either form.
    assert _crep.peer_is_joined({"peer-a"}, {}, "peer-a:4506") is True


def test_peer_is_joined_tolerates_none_inputs():
    # Early-bootstrap: the publish daemon may not yet have initialised
    # the sets.  Must not crash; just return False.
    assert _crep.peer_is_joined(None, None, "peer-a") is False


# ---------------------------------------------------------------------------
# filter_joined_pushers
# ---------------------------------------------------------------------------


def test_filter_joined_pushers_all_joined(opts):
    """3 peers, all joined: fan-out retains all three (regression)."""
    pushers = [_FakePusher("a"), _FakePusher("b"), _FakePusher("c")]
    kept, skipped = _crep.filter_joined_pushers(
        pushers, {"a", "b", "c"}, {}, opts, context="test"
    )
    assert [p.pull_host for p in kept] == ["a", "b", "c"]
    assert skipped == []


def test_filter_joined_pushers_partial(opts, caplog):
    """3 peers, 2 joined, 1 not-joined: fan-out skips the unjoined peer."""
    pushers = [_FakePusher("a"), _FakePusher("b"), _FakePusher("c")]
    with caplog.at_level(logging.WARNING, logger="salt.cache._cluster_replicator"):
        kept, skipped = _crep.filter_joined_pushers(
            pushers, {"a", "b"}, {}, opts, context="test"
        )
    assert [p.pull_host for p in kept] == ["a", "b"]
    assert [p.pull_host for p in skipped] == ["c"]
    # Operator signal: a WARN names the skipped peer.
    assert any(
        "skipping" in record.message and "c" in record.message
        for record in caplog.records
    )


def test_filter_joined_pushers_none_joined(opts, caplog):
    """No peer is joined: nothing fans out; WARN fires for every skip."""
    pushers = [_FakePusher("a"), _FakePusher("b"), _FakePusher("c")]
    with caplog.at_level(logging.WARNING, logger="salt.cache._cluster_replicator"):
        kept, skipped = _crep.filter_joined_pushers(
            pushers, set(), {}, opts, context="test"
        )
    assert kept == []
    assert [p.pull_host for p in skipped] == ["a", "b", "c"]
    warn_hosts = sorted(
        host
        for host in ("a", "b", "c")
        if any(host in r.message and "skipping" in r.message for r in caplog.records)
    )
    assert warn_hosts == ["a", "b", "c"]


def test_filter_joined_pushers_transition_to_joined(opts):
    """
    Peer not-joined on write-1, joined on write-2 (handshake landed
    between the two calls): the gate sees the state transition on
    its next invocation and includes the peer.
    """
    pushers = [_FakePusher("a"), _FakePusher("b")]
    # First write: only 'a' joined.
    discover_replies = {"a"}
    kept, skipped = _crep.filter_joined_pushers(
        pushers, discover_replies, {}, opts, context="write-1"
    )
    assert [p.pull_host for p in kept] == ["a"]
    assert [p.pull_host for p in skipped] == ["b"]
    # 'b' finishes the handshake.
    discover_replies.add("b")
    # Second write: both joined.
    kept2, skipped2 = _crep.filter_joined_pushers(
        pushers, discover_replies, {}, opts, context="write-2"
    )
    assert [p.pull_host for p in kept2] == ["a", "b"]
    assert skipped2 == []


def test_filter_joined_pushers_disabled_by_opt(opts):
    """
    ``cluster_cache_replicate_require_joined: False`` restores the
    pre-gate always-fan-out behaviour.  Useful for operators who need
    to diagnose a stuck handshake.
    """
    opts["cluster_cache_replicate_require_joined"] = False
    pushers = [_FakePusher("a"), _FakePusher("b")]
    kept, skipped = _crep.filter_joined_pushers(
        pushers, set(), {}, opts, context="test"
    )
    # Every pusher kept despite nobody being joined.
    assert [p.pull_host for p in kept] == ["a", "b"]
    assert skipped == []


def test_filter_joined_pushers_default_on_when_opt_missing():
    """Opt absent from opts: gate is active (safer default)."""
    opts = {"id": "master-1", "cluster_id": "cluster-A"}
    pushers = [_FakePusher("a")]
    kept, skipped = _crep.filter_joined_pushers(
        pushers, set(), {}, opts, context="test"
    )
    assert kept == []
    assert len(skipped) == 1


def test_filter_joined_pushers_empty_list(opts):
    kept, skipped = _crep.filter_joined_pushers([], set(), {}, opts)
    assert kept == []
    assert skipped == []


def test_filter_joined_pushers_bare_host_match_with_port_suffix(opts):
    """
    _discover_replies keys on bare host; cluster_peers / pushers may
    carry ``:port``.  The gate must bridge both forms.
    """
    pushers = [_FakePusher("peer-a:4506")]
    kept, _ = _crep.filter_joined_pushers(pushers, {"peer-a"}, {}, opts)
    assert [p.pull_host for p in kept] == ["peer-a:4506"]


def test_filter_joined_pushers_skip_log_coalesces(opts, caplog):
    """
    Spam-case: many writes to the same un-joined peer should NOT
    flood the log.  The first skip logs; subsequent skips in the
    same window are counted.
    """
    pushers = [_FakePusher("a")]
    with caplog.at_level(logging.WARNING, logger="salt.cache._cluster_replicator"):
        for _ in range(10):
            _crep.filter_joined_pushers(pushers, set(), {}, opts, context="burst")
    # Exactly one WARN emitted; the rest are coalesced.
    skip_warns = [
        r for r in caplog.records if "skipping" in r.message and "a" in r.message
    ]
    assert len(skip_warns) == 1


# ---------------------------------------------------------------------------
# secret_fingerprint
# ---------------------------------------------------------------------------


def test_secret_fingerprint_bytes():
    secret = b"\x00" * 32
    fp = _crep.secret_fingerprint(secret)
    assert fp == hashlib.sha256(secret).hexdigest()[:8]
    assert len(fp) == 8


def test_secret_fingerprint_str():
    fp = _crep.secret_fingerprint("abc")
    assert fp == hashlib.sha256(b"abc").hexdigest()[:8]


def test_secret_fingerprint_none():
    assert _crep.secret_fingerprint(None) == "<unavailable>"


def test_secret_fingerprint_never_leaks_full_secret():
    """Load-bearing: the log sanitiser must not emit the full key."""
    secret = b"very-secret-" + b"\xff" * 32
    fp = _crep.secret_fingerprint(secret)
    assert fp != secret.hex()
    assert "very-secret" not in fp


# ---------------------------------------------------------------------------
# log_decrypt_failure
# ---------------------------------------------------------------------------


def test_log_decrypt_failure_emits_structured_log(caplog):
    opts = {"cluster_id": "cluster-A", "id": "master-1"}
    secret = b"\x00" * 32
    try:
        raise ValueError("boom")
    except ValueError:
        with caplog.at_level(logging.ERROR, logger="salt.cache._cluster_replicator"):
            _crep.log_decrypt_failure(
                "cluster/peer/delegate-cache-write",
                opts,
                secret,
                source_peer="peer-x",
                extra={"handler": "delegate-cache-write"},
            )
    msgs = [r.getMessage() for r in caplog.records]
    assert any("cluster-decrypt-failed" in m for m in msgs)
    joined = "\n".join(msgs)
    assert "cluster/peer/delegate-cache-write" in joined
    assert "'cluster-A'" in joined
    assert "peer-x" in joined
    # Fingerprint, never the raw key.
    assert hashlib.sha256(secret).hexdigest()[:8] in joined
    assert "handler" in joined


def test_log_decrypt_failure_rate_limits(caplog):
    """Many failures on the same (tag, peer) within the window => one log."""
    opts = {"cluster_id": "cluster-A"}
    try:
        raise ValueError("boom")
    except ValueError:
        with caplog.at_level(logging.ERROR, logger="salt.cache._cluster_replicator"):
            for _ in range(10):
                _crep.log_decrypt_failure(
                    "cluster/peer/delegate-cache-write",
                    opts,
                    b"x" * 32,
                    source_peer="peer-x",
                )
    err_records = [r for r in caplog.records if "cluster-decrypt-failed" in r.message]
    assert len(err_records) == 1


def test_log_decrypt_failure_distinct_tags_not_coalesced(caplog):
    """Different (tag, peer) tuples have independent windows."""
    opts = {"cluster_id": "cluster-A"}
    try:
        raise ValueError("boom")
    except ValueError:
        with caplog.at_level(logging.ERROR, logger="salt.cache._cluster_replicator"):
            _crep.log_decrypt_failure(
                "cluster/peer/delegate-cache-write",
                opts,
                b"x" * 32,
                source_peer="peer-x",
            )
            _crep.log_decrypt_failure(
                "cluster/peer/delegate-resource-register-write",
                opts,
                b"x" * 32,
                source_peer="peer-x",
            )
    err_records = [r for r in caplog.records if "cluster-decrypt-failed" in r.message]
    assert len(err_records) == 2


def test_log_decrypt_failure_handles_missing_secret(caplog):
    """A null secret must not crash the log path."""
    opts = {"cluster_id": "cluster-A"}
    try:
        raise ValueError("boom")
    except ValueError:
        with caplog.at_level(logging.ERROR, logger="salt.cache._cluster_replicator"):
            _crep.log_decrypt_failure(
                "cluster/peer/delegate-cache-write",
                opts,
                None,
            )
    err_records = [r for r in caplog.records if "cluster-decrypt-failed" in r.message]
    assert len(err_records) == 1
    assert "<unavailable>" in err_records[0].getMessage()


# ---------------------------------------------------------------------------
# Pending-queue (enqueue / drain / flush)
# ---------------------------------------------------------------------------


def _make_event(event=b"evt", tag="cluster/peer/delegate-cache-write", **kw):
    return _crep.PendingEvent(
        kind=kw.pop("kind", "cache"),
        event=event,
        tag=tag,
        bank=kw.pop("bank", "grains"),
        key=kw.pop("key", "minion-1"),
        minion_id=kw.pop("minion_id", None),
    )


def test_enqueue_pending_round_trip(opts):
    """Enqueued events stay in FIFO order and reappear on drain."""
    evt1 = _make_event(event=b"e1")
    evt2 = _make_event(event=b"e2")
    _crep.enqueue_pending("peer-x", evt1, opts=opts)
    _crep.enqueue_pending("peer-x", evt2, opts=opts)
    assert _crep.pending_queue_depth("peer-x") == 2
    drained = _crep.drain_pending_for_peer("peer-x", opts=opts)
    assert [e.event for e in drained] == [b"e1", b"e2"]
    # After draining the queue is empty.
    assert _crep.pending_queue_depth("peer-x") == 0


def test_enqueue_pending_ignores_empty_peer_host(opts):
    """Falsy peer_host: enqueue is a no-op (defensive)."""
    assert _crep.enqueue_pending(None, _make_event(), opts=opts) == 0
    assert _crep.enqueue_pending("", _make_event(), opts=opts) == 0
    assert _crep.pending_queue_depth() == 0


def test_enqueue_pending_per_peer_isolation(opts):
    """Each peer gets its own queue; drain of one leaves the other."""
    _crep.enqueue_pending("peer-x", _make_event(event=b"x"), opts=opts)
    _crep.enqueue_pending("peer-y", _make_event(event=b"y"), opts=opts)
    assert _crep.pending_queue_depth("peer-x") == 1
    assert _crep.pending_queue_depth("peer-y") == 1
    _crep.drain_pending_for_peer("peer-x", opts=opts)
    assert _crep.pending_queue_depth("peer-x") == 0
    assert _crep.pending_queue_depth("peer-y") == 1


def test_enqueue_pending_enforces_cap(opts, caplog):
    """A per-peer queue above the cap drops its OLDEST entry."""
    opts = {**opts, "cluster_cache_replicate_pending_max_events": 3}
    with caplog.at_level(logging.WARNING, logger="salt.cache._cluster_replicator"):
        for i in range(5):
            _crep.enqueue_pending(
                "peer-x", _make_event(event=f"e{i}".encode()), opts=opts
            )
    drained = _crep.drain_pending_for_peer("peer-x", opts=opts)
    # Oldest two dropped; survivors are e2..e4 in FIFO order.
    assert [e.event for e in drained] == [b"e2", b"e3", b"e4"]
    # Operator signal: an overflow WARN was emitted.
    assert any("dropped" in r.message and "peer-x" in r.message for r in caplog.records)


def test_enqueue_pending_ttl_expiry(opts):
    """Expired entries are dropped before the new entry is appended."""
    opts = {**opts, "cluster_cache_replicate_pending_ttl": 0.05}
    _crep.enqueue_pending("peer-x", _make_event(event=b"old"), opts=opts)
    time.sleep(0.1)
    _crep.enqueue_pending("peer-x", _make_event(event=b"fresh"), opts=opts)
    drained = _crep.drain_pending_for_peer("peer-x", opts=opts)
    # ``old`` was popped at the second enqueue.
    assert [e.event for e in drained] == [b"fresh"]


def test_drain_pending_filters_ttl_expired(opts):
    """``drain_pending_for_peer`` filters expired entries without touching others."""
    opts = {**opts, "cluster_cache_replicate_pending_ttl": 0.05}
    _crep.enqueue_pending("peer-x", _make_event(event=b"e1"), opts=opts)
    time.sleep(0.1)
    # TTL check inside drain; the (now stale) e1 is filtered.
    drained = _crep.drain_pending_for_peer("peer-x", opts=opts)
    assert drained == []
    assert _crep.pending_queue_depth("peer-x") == 0


def test_drop_pending_for_peer_empties_queue(opts):
    """``drop_pending_for_peer`` removes every entry for the peer."""
    _crep.enqueue_pending("peer-x", _make_event(event=b"e1"), opts=opts)
    _crep.enqueue_pending("peer-x", _make_event(event=b"e2"), opts=opts)
    assert _crep.drop_pending_for_peer("peer-x") == 2
    assert _crep.pending_queue_depth("peer-x") == 0


def test_filter_joined_pushers_enqueues_skipped_when_event_present(opts):
    """
    ``filter_joined_pushers(pending_event=...)`` enqueues the event
    to every skipped peer's pending queue.
    """
    pushers = [_FakePusher("a"), _FakePusher("b"), _FakePusher("c")]
    evt = _make_event(event=b"payload")
    _crep.filter_joined_pushers(
        pushers,
        {"a"},
        {},
        opts,
        context="delegate-cache-write",
        pending_event=evt,
    )
    assert _crep.pending_queue_depth("a") == 0  # joined -> no enqueue
    assert _crep.pending_queue_depth("b") == 1
    assert _crep.pending_queue_depth("c") == 1


def test_filter_joined_pushers_no_enqueue_without_event(opts):
    """
    Omitting ``pending_event`` preserves the legacy "skip + warn"
    behaviour (no queue side-effect).  Protects unit-test paths that
    exercise the gate without a payload.
    """
    pushers = [_FakePusher("a"), _FakePusher("b")]
    _crep.filter_joined_pushers(
        pushers, set(), {}, opts, context="delegate-cache-write"
    )
    assert _crep.pending_queue_depth() == 0


def test_flush_pending_publishes_in_fifo_order(opts):
    """FIFO: drain + publish preserves enqueue order."""
    evt1 = _make_event(event=b"e1")
    evt2 = _make_event(event=b"e2")
    evt3 = _make_event(event=b"e3")
    _crep.enqueue_pending("peer-x", evt1, opts=opts)
    _crep.enqueue_pending("peer-x", evt2, opts=opts)
    _crep.enqueue_pending("peer-x", evt3, opts=opts)
    target = _FakeAsyncPusher("peer-x")

    async def _run():
        return await _crep.flush_pending_for_peer("peer-x", [target], opts=opts)

    flushed = asyncio.new_event_loop().run_until_complete(_run())
    assert flushed == 3
    assert target.published == [b"e1", b"e2", b"e3"]
    assert _crep.pending_queue_depth("peer-x") == 0


def test_flush_pending_matches_bare_host_pusher(opts):
    """Pusher carries ``host:port``; peer_host is bare -- match succeeds."""
    _crep.enqueue_pending("peer-x", _make_event(event=b"payload"), opts=opts)
    target = _FakeAsyncPusher("peer-x:4506")

    async def _run():
        return await _crep.flush_pending_for_peer("peer-x", [target], opts=opts)

    flushed = asyncio.new_event_loop().run_until_complete(_run())
    assert flushed == 1
    assert target.published == [b"payload"]


def test_flush_pending_no_pusher_leaves_queue(opts):
    """Missing pusher: entries stay queued for a later flush."""
    _crep.enqueue_pending("peer-x", _make_event(event=b"payload"), opts=opts)

    async def _run():
        return await _crep.flush_pending_for_peer("peer-x", [], opts=opts)

    flushed = asyncio.new_event_loop().run_until_complete(_run())
    assert flushed == 0
    # Not drained -- a later flush with the right pusher will deliver.
    assert _crep.pending_queue_depth("peer-x") == 1


def test_flush_pending_requeues_on_publish_error(opts, caplog):
    """
    An exception from ``pusher.publish`` re-queues the failing entry
    plus every entry after it, preserving FIFO order.
    """
    _crep.enqueue_pending("peer-x", _make_event(event=b"e1"), opts=opts)
    _crep.enqueue_pending("peer-x", _make_event(event=b"e2"), opts=opts)
    _crep.enqueue_pending("peer-x", _make_event(event=b"e3"), opts=opts)
    target = _FakeAsyncPusher("peer-x", fail_at=1)  # fail on the 2nd publish

    async def _run():
        return await _crep.flush_pending_for_peer("peer-x", [target], opts=opts)

    with caplog.at_level(logging.ERROR, logger="salt.cache._cluster_replicator"):
        flushed = asyncio.new_event_loop().run_until_complete(_run())
    # e1 shipped; e2 raised; e2 + e3 re-enqueued in order.
    assert flushed == 1
    assert target.published == [b"e1"]
    survivors = _crep.drain_pending_for_peer("peer-x", opts=opts)
    assert [e.event for e in survivors] == [b"e2", b"e3"]
    assert any("pending-flush publish failed" in r.message for r in caplog.records)


def test_flush_pending_empty_queue_is_noop(opts):
    """Flushing an empty queue returns 0; no publish; no exception."""
    target = _FakeAsyncPusher("peer-x")

    async def _run():
        return await _crep.flush_pending_for_peer("peer-x", [target], opts=opts)

    flushed = asyncio.new_event_loop().run_until_complete(_run())
    assert flushed == 0
    assert target.published == []


def test_pending_queue_depth_aggregates(opts):
    """``pending_queue_depth()`` with no arg returns the total depth."""
    _crep.enqueue_pending("peer-x", _make_event(event=b"e1"), opts=opts)
    _crep.enqueue_pending("peer-x", _make_event(event=b"e2"), opts=opts)
    _crep.enqueue_pending("peer-y", _make_event(event=b"e3"), opts=opts)
    assert _crep.pending_queue_depth() == 3
    assert _crep.pending_queue_depth("peer-x") == 2
    assert _crep.pending_queue_depth("peer-y") == 1


def test_flush_pending_after_enqueue_covers_integration_semantics(opts):
    """
    End-to-end seam: a write fires through ``filter_joined_pushers``
    while the peer is un-joined; it lands in the pending queue; a
    subsequent handshake-complete event triggers a flush; the peer
    receives the exact bytes.
    """
    pushers = [_FakePusher("peer-x")]
    evt = _make_event(event=b"delta")
    # Write-time: gate finds 'peer-x' un-joined -> enqueue.
    kept, skipped = _crep.filter_joined_pushers(
        pushers,
        set(),  # empty discover_replies
        {},  # empty peer_keys
        opts,
        context="delegate-cache-write",
        pending_event=evt,
    )
    assert kept == []
    assert len(skipped) == 1
    assert _crep.pending_queue_depth("peer-x") == 1

    # Handshake completes.  The publish daemon normally hands us an
    # async pusher; swap in the async stand-in.
    target = _FakeAsyncPusher("peer-x")

    async def _run():
        return await _crep.flush_pending_for_peer("peer-x", [target], opts=opts)

    flushed = asyncio.new_event_loop().run_until_complete(_run())
    assert flushed == 1
    assert target.published == [b"delta"]
    assert _crep.pending_queue_depth("peer-x") == 0


def test_staggered_join_regression_fifo_across_multiple_writes(opts):
    """
    Regression for the Arm64 bootstrap-race failures documented in
    PR #70773 (``test_grain_targeting_works_from_any_backend``,
    ``test_resource_registry_replicates``).

    Three writes land on master_1 while master_2 is still mid-
    handshake (not in ``_discover_replies``, not in ``peer_keys``).
    Each is enqueued.  Then the handshake completes and master_2 sees
    every write in submission order.

    Covers the exact scenario: live writes between the state-sync
    snapshot and the ``cluster/peer/discover-reply`` arrival.
    """
    peer2 = _FakePusher("127.0.0.2")
    writes = [
        _make_event(event=b"grains-write-1", bank="grains", key="minion-a"),
        _make_event(
            event=b"resource-write",
            kind="resource",
            bank=None,
            key=None,
            tag="cluster/peer/delegate-resource-register-write",
            minion_id="minion-a",
        ),
        _make_event(event=b"grains-write-2", bank="grains", key="minion-b"),
    ]
    # Three sender-side calls during the join window: each enqueues
    # because master_2 is un-joined.
    for evt in writes:
        kept, skipped = _crep.filter_joined_pushers(
            [peer2],
            set(),
            {},
            opts,
            context=evt.tag,
            pending_event=evt,
        )
        assert kept == []
        assert len(skipped) == 1
    assert _crep.pending_queue_depth("127.0.0.2") == 3

    # Handshake completes.  Flush in one call.
    target = _FakeAsyncPusher("127.0.0.2")

    async def _run():
        return await _crep.flush_pending_for_peer("127.0.0.2", [target], opts=opts)

    flushed = asyncio.new_event_loop().run_until_complete(_run())
    assert flushed == 3
    # FIFO: writes delivered in submission order.
    assert target.published == [
        b"grains-write-1",
        b"resource-write",
        b"grains-write-2",
    ]
    assert _crep.pending_queue_depth("127.0.0.2") == 0


def test_double_flush_is_idempotent(opts):
    """
    Two flush triggers (``discover-reply`` + ``peer-keys``-broadcast)
    for the same peer must not double-deliver.  The second flush sees
    an empty queue.
    """
    _crep.enqueue_pending("peer-x", _make_event(event=b"once"), opts=opts)
    target = _FakeAsyncPusher("peer-x")

    async def _run():
        return await _crep.flush_pending_for_peer("peer-x", [target], opts=opts)

    loop = asyncio.new_event_loop()
    first = loop.run_until_complete(_run())
    second = loop.run_until_complete(_run())
    assert first == 1
    assert second == 0
    assert target.published == [b"once"]
