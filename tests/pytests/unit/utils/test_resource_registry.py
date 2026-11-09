"""
Unit tests for :mod:`salt.utils.resource_registry`.
"""

import contextlib
import threading

import pytest

import salt.utils.resource_registry as rr

# Production default mmap is ~256 MiB (2**21 slots × 128 B). Unit tests only
# need a tiny table; keeping this small avoids multi‑GiB churn across many
# tests (and false CI failures from /tmp exhaustion).
_TEST_PRIMARY_CAPACITY = 4096
_TEST_PRIMARY_SLOT_SIZE = 128


class _FakeCache:
    """In-memory stand-in for ``salt.cache.factory`` output."""

    def __init__(self):
        self.banks = {}

    def fetch(self, bank, key):
        return self.banks.get(bank, {}).get(key)

    def store(self, bank, key, value):
        self.banks.setdefault(bank, {})[key] = value


@pytest.fixture
def registry(tmp_path):
    opts = {
        "cachedir": str(tmp_path),
        "resource_index_primary_capacity": _TEST_PRIMARY_CAPACITY,
        "resource_index_primary_slot_size": _TEST_PRIMARY_SLOT_SIZE,
    }
    cache = _FakeCache()
    reg = rr.ResourceRegistry(opts, cache=cache)
    try:
        yield reg
    finally:
        reg.close()


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "expr, expected",
    [
        ("vcf_host", {"type": "vcf_host", "id": None}),
        ("vcf_host:esxi-01", {"type": "vcf_host", "id": "esxi-01"}),
        ("", {"type": None, "id": None}),
        (None, {"type": None, "id": None}),
        (":orphan", {"type": None, "id": "orphan"}),
        ("type_only:", {"type": "type_only", "id": None}),
    ],
)
def test_parse_srn(expr, expected):
    assert rr.parse_srn(expr) == expected


def test_resource_index_srn_key():
    assert rr.resource_index_srn_key("ssh", "web-01") == "ssh:web-01"


def test_encode_decode_by_id_roundtrip():
    blob = rr._encode_by_id_value("vcenter-1", "vcf_host")
    out = rr._decode_by_id_value(blob)
    assert out == {"minion": "vcenter-1", "type": "vcf_host"}


def test_decode_by_id_handles_garbage():
    assert rr._decode_by_id_value(None) is None
    assert rr._decode_by_id_value(True) is None
    assert rr._decode_by_id_value("not-json") is None
    assert rr._decode_by_id_value("[1,2]") is None


# ---------------------------------------------------------------------------
# Registry end-to-end
# ---------------------------------------------------------------------------


def test_register_minion_and_read_back(registry):
    registry.register_minion(
        "vcenter-1",
        {
            "vcf_host": ["esxi-01", "esxi-02"],
            "vm": ["vm-a"],
        },
    )

    assert registry.has_resource("vcenter-1", "vcf_host", "esxi-01") is True
    assert registry.has_resource("vcenter-1", "vcf_host", "nope") is False
    assert registry.has_resource_type("vcenter-1", "vm") is True
    assert registry.has_resource_type("vcenter-1", "bogus") is False

    rs = registry.get_resources_for_minion("vcenter-1")
    assert set(rs.keys()) == {"vcf_host", "vm"}
    assert sorted(rs["vcf_host"]) == ["esxi-01", "esxi-02"]

    assert registry.get_managing_minions_for_srn("vcf_host", "esxi-01") == ["vcenter-1"]
    assert registry.get_managing_minions_for_srn("vcf_host", "nope") == []


def test_register_minion_diff_removes_stale(registry):
    registry.register_minion("m1", {"ssh": ["a", "b", "c"], "vm": ["v1"]})
    # Now a smaller inventory: drop "b" and all vms.
    registry.register_minion("m1", {"ssh": ["a", "c"]})

    rs = registry.get_resources_for_minion("m1")
    assert sorted(rs["ssh"]) == ["a", "c"]
    assert "vm" not in rs
    assert registry.has_resource("m1", "ssh", "b") is False
    assert registry.has_resource("m1", "vm", "v1") is False


# ---------------------------------------------------------------------------
# Chunked-register correctness: regression tests for the
# multi-chunk-prune-cascade bug fixed in the pre-Phase-3 fixer pass.
# Precedent: a 200K register fired as 20 x 10K chunks was persisting
# only 10K entries because every chunk's receipt was running the
# diff-against-previous delete pass, pruning every earlier chunk of
# the same window.
# ---------------------------------------------------------------------------


def test_register_minion_chunk_multi_chunk_persists_all_chunks(registry):
    """Three non-final chunks + one final chunk all persist, nothing pruned."""
    # Chunk 1: additive put, no delete
    n_put, n_del = registry.register_minion_chunk(
        "m1", {"dummy": ["d1", "d2"]}, chunk_final=False, chunk_scope="dummy"
    )
    assert (n_put, n_del) == (2, 0)
    assert sorted(registry.get_resources_for_minion("m1").get("dummy", [])) == [
        "d1",
        "d2",
    ]

    # Chunk 2: additive put, STILL no delete -- the previous chunk's
    # entries must survive.
    n_put, n_del = registry.register_minion_chunk(
        "m1", {"dummy": ["d3", "d4"]}, chunk_final=False, chunk_scope="dummy"
    )
    assert (n_put, n_del) == (2, 0)
    assert sorted(registry.get_resources_for_minion("m1").get("dummy", [])) == [
        "d1",
        "d2",
        "d3",
        "d4",
    ]

    # Chunk 3 (terminal): put + delete pass.  Union of chunks 1+2+3
    # is {d1..d5} and nothing else; no prior inventory to prune, so
    # n_del must be 0 and ALL five entries must land.
    n_put, n_del = registry.register_minion_chunk(
        "m1", {"dummy": ["d5"]}, chunk_final=True, chunk_scope="dummy"
    )
    assert (n_put, n_del) == (1, 0)
    assert sorted(registry.get_resources_for_minion("m1").get("dummy", [])) == [
        "d1",
        "d2",
        "d3",
        "d4",
        "d5",
    ]


def test_register_minion_chunk_terminal_prunes_removed_srns(registry):
    """Terminal chunk correctly prunes SRNs no longer in the new window."""
    # Prime with 3 SRNs via single-shot register.
    registry.register_minion("m1", {"dummy": ["d1", "d2", "d3"]})
    # Chunked re-register with a smaller set spread across two chunks.
    registry.register_minion_chunk(
        "m1", {"dummy": ["d1"]}, chunk_final=False, chunk_scope="dummy"
    )
    # Mid-stream: d2 and d3 are STILL present (not pruned yet).
    assert sorted(registry.get_resources_for_minion("m1").get("dummy", [])) == [
        "d1",
        "d2",
        "d3",
    ]
    # Terminal chunk commits the new window; d2 + d3 are now stale.
    n_put, n_del = registry.register_minion_chunk(
        "m1", {"dummy": ["d4"]}, chunk_final=True, chunk_scope="dummy"
    )
    assert n_put == 1
    assert n_del == 2
    assert sorted(registry.get_resources_for_minion("m1").get("dummy", [])) == [
        "d1",
        "d4",
    ]


def test_register_minion_chunk_scope_does_not_prune_other_types(registry):
    """A per-type chunked window must not wipe the minion's other types."""
    registry.register_minion("m1", {"dummy": ["d1"], "ssh": ["host-1", "host-2"]})
    # Re-register the ssh type only, via a single terminal chunk.
    n_put, n_del = registry.register_minion_chunk(
        "m1", {"ssh": ["host-1"]}, chunk_final=True, chunk_scope="ssh"
    )
    # ssh:host-2 pruned (stale within scope), dummy:d1 untouched.
    assert n_del == 1
    rs = registry.get_resources_for_minion("m1")
    assert sorted(rs.get("ssh", [])) == ["host-1"]
    assert sorted(rs.get("dummy", [])) == ["d1"]


def test_register_minion_chunk_all_scope_prunes_everything_not_in_window(
    registry,
):
    """``chunk_scope='__all__'`` matches legacy single-shot full-replace."""
    registry.register_minion("m1", {"dummy": ["d1"], "ssh": ["h1"]})
    # One-shot terminal chunk replacing entire inventory.
    n_put, n_del = registry.register_minion_chunk(
        "m1", {"dummy": ["d2"]}, chunk_final=True, chunk_scope="__all__"
    )
    # ssh:h1 and dummy:d1 both pruned.
    assert n_del == 2
    rs = registry.get_resources_for_minion("m1")
    assert sorted(rs.get("dummy", [])) == ["d2"]
    assert "ssh" not in rs


def test_register_minion_chunk_pending_state_cleared_after_terminal(registry):
    """The accumulator doesn't leak minion state across windows."""
    registry.register_minion_chunk(
        "m1", {"dummy": ["d1"]}, chunk_final=False, chunk_scope="dummy"
    )
    registry.register_minion_chunk(
        "m1", {"dummy": ["d2"]}, chunk_final=True, chunk_scope="dummy"
    )
    # After terminal commit, ``_pending_registers`` for m1 must be empty
    # (or the key gone entirely).
    pending = registry._pending_registers.get("m1")
    assert not pending, f"terminal chunk must clear its window; got {pending!r}"


def test_register_minion_chunk_many_chunks_simulating_200k_shape(registry):
    """
    Simulate the exact failure mode the production bug hit: a large
    inventory split into N chunks must persist (sum of chunks) entries,
    not just the last chunk.
    """
    chunk_size = 50
    total = 500  # 10 chunks of 50 each
    rids = [f"d{i:04d}" for i in range(total)]
    for idx in range(0, total, chunk_size):
        slice_ = rids[idx : idx + chunk_size]
        is_final = idx + chunk_size >= total
        registry.register_minion_chunk(
            "m1",
            {"dummy": slice_},
            chunk_final=is_final,
            chunk_scope="dummy",
        )
    got = sorted(registry.get_resources_for_minion("m1").get("dummy", []))
    assert len(got) == total, (
        f"{total} entries sent across chunks but only {len(got)} persisted; "
        "multi-chunk aggregation is broken"
    )
    assert got[0] == "d0000"
    assert got[-1] == f"d{total - 1:04d}"


def test_register_minion_chunk_out_of_order_final_defers_prune(registry):
    """
    Regression for the peer-side chunk reordering race (Phase-3 reviewer
    finding #14): the publish daemon dispatches each incoming
    ``cluster/peer/delegate-resource-register-write`` event into the
    default ThreadPoolExecutor via ``run_in_executor(None, ...)``.  The
    executor is NOT FIFO, so a fast ``chunk_final=True`` can land before
    earlier non-final chunks finish.  Pre-fix, the terminal prune ran
    against the incomplete pending window and wiped the valid SRNs the
    slow non-final chunk was about to re-insert.

    This test feeds the chunks to the registry in reverse order
    (3-final, 2, 1, 0) and asserts:

    1. The terminal chunk does NOT run the prune immediately -- it
       detects the gap via ``chunk_index`` and buffers.
    2. The missing non-final chunks land and accumulate normally.
    3. When the final gap closes (chunk 0 arrives), the deferred prune
       fires and all SRNs from every chunk survive.

    Pre-fix behavior: the 3-final chunk would call ``delete_many`` on
    every SRN in the registry (because the window's "committed" set
    only contained its own 1 SRN) and the later chunks would still
    insert but the prune cascade would have wiped prior state.
    """
    # Seed with 2 previously-registered SRNs that must survive the
    # chunked re-register (they belong to a type outside the scope).
    registry.register_minion("m1", {"ssh": ["h-old"], "dummy": ["d-old"]})

    # Build the window: 4 chunks total (indexes 0..3) carrying d0..d3.
    # Scope == "dummy" so the prune at the end should remove d-old but
    # NOT h-old.
    chunks = [
        (0, {"dummy": ["d0"]}, False),
        (1, {"dummy": ["d1"]}, False),
        (2, {"dummy": ["d2"]}, False),
        (3, {"dummy": ["d3"]}, True),
    ]

    # Deliver out-of-order: final first, then 2, then 1, then 0.
    arrival_order = [3, 2, 1, 0]
    delivered_by_index = {idx: payload for idx, payload, final in chunks}
    final_by_index = {idx: final for idx, _payload, final in chunks}

    # First delivery: the terminal chunk (index 3).  Pre-fix would have
    # pruned d-old AND all 4 dummy-SRNs (no d0/d1/d2 in the committed
    # set because they haven't arrived).  Post-fix: the gap check sees
    # seen_indexes={3} but needs {0,1,2,3}, so no prune runs.
    n_put, n_del = registry.register_minion_chunk(
        "m1",
        delivered_by_index[3],
        chunk_final=final_by_index[3],
        chunk_scope="dummy",
        chunk_index=3,
    )
    assert n_put == 1
    assert n_del == 0, (
        "Out-of-order terminal must NOT prune -- the window's earlier "
        "chunks have not arrived yet (seen_indexes={3}, need {0,1,2,3})"
    )
    # d-old must still be present because the prune was deferred.
    assert "d-old" in registry.get_resources_for_minion("m1").get("dummy", [])
    # Pending state is still live; the registry remembers the deferred
    # final so a later arrival of the missing indices can promote it.
    pending = registry._pending_registers.get("m1", {}).get("dummy")
    assert pending is not None, "pending window must survive the deferred final"
    assert pending["final_pending"] == 3

    # Deliver the remaining chunks in reverse (2, 1, 0).  None of them
    # is final; the gap check on arrival of chunk 0 (closing the
    # sequence) promotes the deferred final into a prune pass.
    for idx in (2, 1):
        n_put, n_del = registry.register_minion_chunk(
            "m1",
            delivered_by_index[idx],
            chunk_final=final_by_index[idx],
            chunk_scope="dummy",
            chunk_index=idx,
        )
        assert n_put == 1
        assert n_del == 0, (
            f"intermediate chunk index={idx} must not fire the prune "
            "while the window still has a gap"
        )

    # Final gap-closing chunk (index 0).  The gap check now sees
    # {0,1,2,3} == expected, so the deferred prune fires.  d-old was
    # not in the committed set (it's old scope=dummy state), so it is
    # the only thing pruned; d0..d3 all survive; h-old is outside the
    # scope and is untouched.
    n_put, n_del = registry.register_minion_chunk(
        "m1",
        delivered_by_index[0],
        chunk_final=final_by_index[0],
        chunk_scope="dummy",
        chunk_index=0,
    )
    assert n_put == 1
    assert n_del == 1, f"deferred prune should remove exactly d-old; got n_del={n_del}"

    # Final state: d0..d3 all present, d-old pruned, h-old preserved.
    final_state = registry.get_resources_for_minion("m1")
    assert sorted(final_state.get("dummy", [])) == ["d0", "d1", "d2", "d3"]
    assert sorted(final_state.get("ssh", [])) == ["h-old"]
    # Pending window must be fully cleared.
    assert "m1" not in registry._pending_registers


def test_register_minion_chunk_final_prune_runs_once(registry):
    """
    Once the deferred prune fires it must NOT re-fire on duplicate
    terminal deliveries (bus bounce-back shape).  The pending state is
    cleared when the prune commits so a second terminal arrival only
    runs an additive put (and any new gap check is self-contained to
    the new post-commit window).
    """
    registry.register_minion("m1", {"dummy": ["d-stale"]})
    registry.register_minion_chunk(
        "m1",
        {"dummy": ["d0"]},
        chunk_final=False,
        chunk_scope="dummy",
        chunk_index=0,
    )
    n_put, n_del = registry.register_minion_chunk(
        "m1",
        {"dummy": ["d1"]},
        chunk_final=True,
        chunk_scope="dummy",
        chunk_index=1,
    )
    assert n_del == 1  # d-stale pruned
    assert sorted(registry.get_resources_for_minion("m1").get("dummy", [])) == [
        "d0",
        "d1",
    ]
    # Duplicate final -- pending window was cleared by the commit above;
    # the duplicate opens a fresh single-chunk window with
    # ``seen_indexes={1}`` but ``final_index=1`` requires ``{0,1}``, so
    # the deferred-prune gap check defers (no spurious delete of d0).
    # The additive ``put_many`` still runs (idempotent re-insert of d1).
    n_put, n_del = registry.register_minion_chunk(
        "m1",
        {"dummy": ["d1"]},
        chunk_final=True,
        chunk_scope="dummy",
        chunk_index=1,
    )
    assert n_del == 0, (
        "duplicate terminal arrival must not spuriously prune through "
        "a gap check -- the window is fresh and incomplete"
    )
    # d0 and d1 both remain -- no spurious prune cascaded through the
    # duplicate.
    assert sorted(registry.get_resources_for_minion("m1").get("dummy", [])) == [
        "d0",
        "d1",
    ]


def test_register_minion_chunk_concurrent_apply_no_srn_loss(registry):
    """
    Thread-contention regression: multiple threads applying chunks for
    the same ``(minion_id, scope)`` must not race the ``_pending_registers``
    mutation + prune.  Pre-fix (no lock), concurrent threads could
    interleave a terminal-prune against another thread's half-committed
    pending set and drop valid SRNs.
    """
    total_chunks = 8
    chunk_size = 20
    all_rids = set()
    for ci in range(total_chunks):
        for ri in range(chunk_size):
            all_rids.add(f"c{ci:02d}-r{ri:02d}")

    def apply_chunk(ci):
        rids = [f"c{ci:02d}-r{ri:02d}" for ri in range(chunk_size)]
        registry.register_minion_chunk(
            "m1",
            {"dummy": rids},
            chunk_final=(ci == total_chunks - 1),
            chunk_scope="dummy",
            chunk_index=ci,
        )

    # Fan the chunks out across threads in reverse order so the final
    # (highest-index) chunk is highly likely to try to prune before
    # all non-final chunks finish.
    threads = []
    for ci in reversed(range(total_chunks)):
        t = threading.Thread(target=apply_chunk, args=(ci,))
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    got = set(registry.get_resources_for_minion("m1").get("dummy", []))
    missing = all_rids - got
    assert not missing, (
        f"Concurrent out-of-order register dropped {len(missing)} SRNs "
        f"(sample: {sorted(missing)[:5]})"
    )


def test_cross_type_collisions_are_not_ambiguous(registry):
    """Composite SRN keys: same bare id on different types resolves distinctly."""
    registry.register_minion("m1", {"ssh": ["web-01"]})
    registry.register_minion("m2", {"vm": ["web-01"]})

    assert registry.get_managing_minions_for_srn("ssh", "web-01") == ["m1"]
    assert registry.get_managing_minions_for_srn("vm", "web-01") == ["m2"]


def test_managing_minions_by_type(registry):
    registry.register_minion("m1", {"ssh": ["a"]})
    registry.register_minion("m2", {"ssh": ["b"], "vm": ["v"]})
    registry.register_minion("m3", {"vm": ["v2"]})

    got = registry.get_managing_minions_by_type("ssh")
    assert got == {"minions": ["m1", "m2"], "missing": []}

    got = registry.get_managing_minions_by_type("vm")
    assert got == {"minions": ["m2", "m3"], "missing": []}

    got = registry.get_managing_minions_by_type("bogus")
    assert got == {"minions": [], "missing": []}


def test_unregister_minion(registry):
    registry.register_minion("m1", {"ssh": ["a", "b"]})
    registry.register_minion("m2", {"ssh": ["c"]})

    n = registry.unregister_minion("m1")
    assert n == 2

    assert registry.get_resources_for_minion("m1") == {}
    assert registry.get_managing_minions_by_type("ssh") == {
        "minions": ["m2"],
        "missing": [],
    }


def test_compact_preserves_contents(registry):
    registry.register_minion("m1", {"ssh": [f"h{i}" for i in range(50)]})
    registry.register_minion("m2", {"vm": ["v1", "v2"]})

    stats_before = registry.stats()["primary"]
    assert stats_before["occupied"] == 52

    before, after = registry.compact()
    assert before == after == 52

    # Reads still work after swap.
    assert registry.has_resource("m1", "ssh", "h7") is True
    assert registry.get_managing_minions_for_srn("vm", "v2") == ["m2"]


def test_compact_reclaims_tombstones(registry):
    registry.register_minion("m1", {"ssh": [f"h{i}" for i in range(40)]})
    registry.register_minion("m1", {"ssh": [f"h{i}" for i in range(0, 40, 2)]})

    stats_before = registry.stats()["primary"]
    # 40 originals - 20 survivors = 20 deletions; 20 occupied + 20 deleted.
    assert stats_before["occupied"] == 20
    assert stats_before["deleted"] == 20

    before, after = registry.compact()
    assert before == after == 20

    stats_after = registry.stats()["primary"]
    assert stats_after["occupied"] == 20
    assert stats_after["deleted"] == 0


def test_get_resource_uses_resources_bank(registry):
    # The ResourceRegistry uses the fake cache we injected; seed the bank.
    fake_cache = registry._cache
    fake_cache.store(rr.RESOURCE_BANK, "esxi-01", {"managing_minions": ["vcenter-1"]})
    assert registry.get_resource("esxi-01") == {"managing_minions": ["vcenter-1"]}
    assert registry.get_resource("missing") is None


def test_get_managing_minions_for_id_legacy(registry):
    registry._cache.store(
        rr.RESOURCE_BANK, "shared-id", {"managing_minions": ["m1", "m2"]}
    )
    assert registry.get_managing_minions_for_id("shared-id") == ["m1", "m2"]
    assert registry.get_managing_minions_for_id("missing") == []


def test_stats_shape(registry):
    registry.register_minion("m1", {"ssh": ["a"]})
    s = registry.stats()
    assert "primary" in s
    assert "derived_version" in s
    assert "derived_by_type_count" in s
    assert "derived_by_minion_count" in s
    assert "path" in s
    assert s["primary"]["occupied"] == 1


def test_missing_cachedir_raises():
    with pytest.raises(ValueError):
        rr.ResourceRegistry({}, cache=_FakeCache())


def test_get_registry_without_cachedir_is_inert():
    """Master helpers may construct CkMinions with partial opts (no cache dir)."""
    reg = rr.get_registry({})
    assert reg.has_srn("ssh", "x") is False
    assert reg.get_resources_for_minion("m") == {}
    assert reg.register_minion("m", {"ssh": ["a"]}) == (0, 0)


# ---------------------------------------------------------------------------
# maybe_compact — policy-driven automatic compaction
# ---------------------------------------------------------------------------


def _make_registry(tmp_path, **overrides):
    opts = {
        "cachedir": str(tmp_path),
        "resource_index_primary_capacity": _TEST_PRIMARY_CAPACITY,
        "resource_index_primary_slot_size": _TEST_PRIMARY_SLOT_SIZE,
    }
    opts.update(overrides)
    return rr.ResourceRegistry(opts, cache=_FakeCache())


@contextlib.contextmanager
def _registry_session(tmp_path, **overrides):
    """Construct a registry and always ``close()`` so mmap FDs are released."""
    reg = _make_registry(tmp_path, **overrides)
    try:
        yield reg
    finally:
        reg.close()


def test_maybe_compact_throttled_by_default(tmp_path):
    with _registry_session(tmp_path) as reg:
        # No writes yet, no file either. First call goes through the throttle
        # (because _last_compact_check starts at 0). Second should be throttled.
        first, _ = reg.maybe_compact()
        second, _ = reg.maybe_compact()
        assert first is False  # no file / nothing above threshold
        assert second is False  # throttled


def test_maybe_compact_force_check_bypasses_throttle(tmp_path):
    with _registry_session(tmp_path) as reg:
        reg.register_minion("m1", {"ssh": ["a", "b", "c"]})
        # Force two back-to-back reads; both should run (no side-effect since
        # nothing is above threshold, but the stats read happens).
        _, s1 = reg.maybe_compact(force_check=True)
        _, s2 = reg.maybe_compact(force_check=True)
        assert s1 is not None
        assert s2 is not None


def test_maybe_compact_triggers_on_tombstone_ratio(tmp_path):
    # Very large interval during setup so register_minion's in-line
    # maybe_compact is suppressed; we drive compaction explicitly.
    with _registry_session(
        tmp_path,
        resource_registry_compact_min_interval=3600,
        resource_registry_compact_tombstone_ratio=0.1,
    ) as reg:
        reg.register_minion("m1", {"ssh": [f"h{i}" for i in range(20)]})
        reg.register_minion("m1", {"ssh": [f"h{i}" for i in range(0, 20, 4)]})

        stats_pre = reg.stats()["primary"]
        assert stats_pre["deleted"] > 0

        compacted, _ = reg.maybe_compact(force_check=True)
        assert compacted is True

        stats_post = reg.stats()["primary"]
        assert stats_post["deleted"] == 0
        assert reg.has_resource("m1", "ssh", "h0") is True
        assert reg.has_resource("m1", "ssh", "h3") is False


def test_maybe_compact_triggers_on_load_factor(tmp_path):
    with _registry_session(
        tmp_path,
        resource_index_primary_capacity=128,
        resource_registry_compact_load_factor=0.1,
        # Suppress the in-line compact so the test sees an un-compacted file.
        resource_registry_compact_min_interval=3600,
    ) as reg:
        reg.register_minion("m1", {"ssh": [f"h{i}" for i in range(20)]})
        compacted, stats = reg.maybe_compact(force_check=True)
        # Occupied/total = 20/128 = 0.156 which exceeds 0.1.
        assert compacted is True


def test_maybe_compact_no_trigger_when_healthy(tmp_path):
    with _registry_session(
        tmp_path,
        resource_registry_compact_min_interval=0,
    ) as reg:
        reg.register_minion("m1", {"ssh": ["a", "b"]})
        compacted, stats = reg.maybe_compact(force_check=True)
        assert compacted is False
        assert stats["occupied"] == 2
        assert stats["deleted"] == 0


def test_register_minion_triggers_auto_compact(tmp_path):
    """register_minion invokes maybe_compact inline; when thresholds are met
    on the second call, the tombstones from the delta must be reclaimed."""
    with _registry_session(
        tmp_path,
        resource_registry_compact_min_interval=0,
        resource_registry_compact_tombstone_ratio=0.1,
    ) as reg:
        reg.register_minion("m1", {"ssh": [f"h{i}" for i in range(20)]})
        # The second register_minion deletes 15 entries, tombstone_ratio
        # becomes 15/5 = 3.0 >> 0.1, and the inline maybe_compact reclaims.
        reg.register_minion("m1", {"ssh": [f"h{i}" for i in range(0, 20, 4)]})
        stats = reg.stats()["primary"]
        assert stats["deleted"] == 0
        assert stats["occupied"] == 5


def test_concurrent_register_minion_and_mmap_derived_reads(registry):
    """
    Writers (:meth:`register_minion`) and readers (derived views / bare-id
    resolution) run concurrently on the mmap primary — must stay crash-free.
    """
    errs = []
    lock = threading.Lock()

    def writer():
        try:
            for i in range(60):
                registry.register_minion(f"w{i % 6}", {"dummy": [f"id-{i}", "anchor"]})
        except Exception as exc:  # pylint: disable=broad-except
            with lock:
                errs.append(exc)

    def reader():
        try:
            for _ in range(120):
                registry.resolve_bare_resource_id("anchor")
                registry.get_resource_ids_by_type("dummy")
                registry.get_resources_for_minion("w0")
        except Exception as exc:  # pylint: disable=broad-except
            with lock:
                errs.append(exc)

    tw = threading.Thread(target=writer)
    tr = threading.Thread(target=reader)
    tw.start()
    tr.start()
    tw.join()
    tr.join()
    assert not errs, errs
    assert registry.resolve_bare_resource_id("anchor")
