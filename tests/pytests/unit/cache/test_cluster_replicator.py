"""
Unit tests for the sender-side handshake gate and decrypt-failure log
helpers in :mod:`salt.cache._cluster_replicator`.

The sender-side gate consults the publish daemon's ``_discover_replies``
/ ``peer_keys`` state and filters the ``pushers`` list before firing a
``cluster_aes``-encrypted replication event.  Peers that have not
completed the cluster discover/join handshake cannot decrypt the
payload; skipping them converts the silent-loss failure mode into a
WARN on the sender side.  The fan-out catch-up happens through the
state-sync stream initiated by the join-reply handler.

The decrypt-failure log helper emits a correlatable, rate-limited
log on the receiver side when ``cluster_aes`` decrypt fails.
"""

import hashlib
import logging

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
    yield
    _crep._SKIP_LOG_LAST.clear()
    _crep._DECRYPT_LOG_LAST.clear()


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
