"""
Deeper unit coverage for minion-side resource register chunking and the
opt-in grain-cache retention. Complements ``test_minion_resources.py``
(which already covers the baseline chunked-send + cache-retention cases)
by exercising edge cases, static-helper correctness, master-side staging
TTL/LRU, and concurrent-registration isolation.

The target code lives on PR ``dwoz/fix/minion-register-scale``
(saltstack/salt#70720): see ``Minion._plan_register_chunks``,
``Minion._register_resources_with_master``, and
``salt.master._RegisterChunkStage`` + ``_register_chunk_apply``.
"""

import asyncio
import threading
import time

import salt.loader.context
import salt.master
import salt.minion
from tests.support.mock import patch as mock_patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_pillar(n_resources, rtype="dummy"):
    """Return a minimal ``{rtype: [res-0, …, res-n-1]}`` resources dict."""
    return {rtype: [f"res-{i:06d}" for i in range(n_resources)]}


def _install_grains_fn(minion):
    """Patch the minion loader so ``_collect_resource_grains`` yields dicts."""

    def grains_fn():
        target = salt.loader.context.resource_ctxvar.get()
        # Deterministic env grain that lets grain-target tests match a
        # predictable subset without needing a saltfactories pillar roundtrip.
        idx = int(target["id"].rsplit("-", 1)[-1])
        return {"env": "prod" if idx % 2 == 0 else "staging", "id": target["id"]}

    minion.resource_funcs = {"dummy.grains": grains_fn}


def _mk_minion(minion_opts, n_resources, **opt_overrides):
    """Build a Minion with a loaded resources pillar and no real master link."""
    minion_opts["resources"] = _build_pillar(n_resources)
    minion_opts["multiprocessing"] = False
    for k, v in opt_overrides.items():
        minion_opts[k] = v
    with mock_patch("salt.minion.Minion.gen_modules"), mock_patch(
        "salt.minion.Minion.connect_master"
    ):
        m = salt.minion.Minion(minion_opts, load_grains=False)
    _install_grains_fn(m)
    m.tok = b"tok"
    return m


# ---------------------------------------------------------------------------
# Static ``_plan_register_chunks`` helper tests
# ---------------------------------------------------------------------------


class TestPlanRegisterChunks:
    """
    ``Minion._plan_register_chunks`` is the static splitter driving the
    minion's chunked RPC. These tests pin the output shape so a regression
    (e.g. chunking by grains-count instead of resources-count) is caught
    without needing to stand up a minion.
    """

    def test_below_threshold_returns_single_chunk(self):
        resources = {"dummy": [f"r-{i}" for i in range(5)]}
        grains = {f"dummy:r-{i}": {"k": i} for i in range(5)}
        chunks = salt.minion.Minion._plan_register_chunks(resources, grains, 10)
        assert len(chunks) == 1
        assert chunks[0][0] == resources
        assert chunks[0][1] == grains

    def test_chunk_size_zero_returns_single_chunk(self):
        """``chunk_size <= 0`` disables chunking (the config knob guard)."""
        resources = {"dummy": [f"r-{i}" for i in range(100)]}
        chunks = salt.minion.Minion._plan_register_chunks(resources, {}, 0)
        assert len(chunks) == 1
        resources2 = {"dummy": [f"r-{i}" for i in range(100)]}
        chunks2 = salt.minion.Minion._plan_register_chunks(resources2, {}, -5)
        assert len(chunks2) == 1

    def test_distributes_resources_evenly_in_chunks(self):
        """25 resources with chunk_size=10 -> 10+10+5 split."""
        resources = {"dummy": [f"r-{i:03d}" for i in range(25)]}
        grains = {f"dummy:r-{i:03d}": {"i": i} for i in range(25)}
        chunks = salt.minion.Minion._plan_register_chunks(resources, grains, 10)
        assert len(chunks) == 3
        sizes = [sum(len(v) for v in c[0].values()) for c in chunks]
        assert sizes == [10, 10, 5]
        # No resource lost or duplicated.
        seen = []
        for chunk_res, _ in chunks:
            seen.extend(chunk_res["dummy"])
        assert sorted(seen) == sorted(resources["dummy"])

    def test_grain_dicts_follow_owning_resource_into_chunk(self):
        """A grain dict for res-N must land in the same chunk as res-N."""
        resources = {"dummy": [f"r-{i:03d}" for i in range(25)]}
        grains = {f"dummy:r-{i:03d}": {"i": i} for i in range(25)}
        chunks = salt.minion.Minion._plan_register_chunks(resources, grains, 10)
        for chunk_res, chunk_grains in chunks:
            for rid in chunk_res["dummy"]:
                srn = f"dummy:{rid}"
                assert (
                    srn in chunk_grains
                ), f"grain for {srn} must ride with its owning resource"

    def test_orphan_grains_ride_last_chunk(self):
        """
        Grain entries whose SRN doesn't map to any currently-managed
        resource must be delivered on the final chunk so the master's
        stale-flush path (gated on ``_chunk_is_last=True``) sees them.
        Defensive case: ``resource_grains`` is built from a live loader
        that may report keys slightly out of sync with the pillar.
        """
        resources = {"dummy": [f"r-{i:03d}" for i in range(25)]}
        grains = {f"dummy:r-{i:03d}": {"i": i} for i in range(25)}
        # Orphans: valid SRN shape but no matching resource.
        grains["dummy:ghost-1"] = {"zombie": True}
        grains["dummy:ghost-2"] = {"zombie": True}
        chunks = salt.minion.Minion._plan_register_chunks(resources, grains, 10)
        last_grains = chunks[-1][1]
        assert "dummy:ghost-1" in last_grains
        assert "dummy:ghost-2" in last_grains
        # Earlier chunks must NOT carry the orphans.
        for chunk_res, chunk_grains in chunks[:-1]:
            assert "dummy:ghost-1" not in chunk_grains
            assert "dummy:ghost-2" not in chunk_grains

    def test_empty_input_still_returns_one_chunk(self):
        """
        Empty inventory still produces a (single) chunk so the master's
        stale-entry flush can run on reconnect after a resource type is
        removed from the pillar.
        """
        chunks = salt.minion.Minion._plan_register_chunks({}, {}, 10)
        assert len(chunks) == 1
        assert chunks[0] == ({}, {})

    def test_multi_type_split_preserves_type_grouping(self):
        """Resources of multiple types still slice cleanly."""
        resources = {
            "dummy": [f"d-{i}" for i in range(12)],
            "ssh": [f"s-{i}" for i in range(8)],
        }
        chunks = salt.minion.Minion._plan_register_chunks(resources, {}, 10)
        # 20 total pairs, chunk_size=10 -> 2 chunks.
        assert len(chunks) == 2
        combined = {"dummy": [], "ssh": []}
        for chunk_res, _ in chunks:
            for t, ids in chunk_res.items():
                combined[t].extend(ids)
        assert sorted(combined["dummy"]) == sorted(resources["dummy"])
        assert sorted(combined["ssh"]) == sorted(resources["ssh"])


# ---------------------------------------------------------------------------
# Full ``_register_resources_with_master`` flow — edge cases
# ---------------------------------------------------------------------------


class TestRegisterResourcesEdgeCases:
    def test_empty_pillar_sends_single_unchunked_clearing_load(self, minion_opts):
        """
        An empty pillar still fires exactly one RPC so the master's
        stale-entry flush runs. Wire format must be unchunked (no
        ``_register_token`` / ``_chunk_*`` fields) so the empty-clear
        path is zero-coupling for old masters.
        """
        minion_opts["resources"] = {}
        minion_opts["multiprocessing"] = False
        with mock_patch("salt.minion.Minion.gen_modules"), mock_patch(
            "salt.minion.Minion.connect_master"
        ):
            m = salt.minion.Minion(minion_opts, load_grains=False)
        m.tok = b"tok"
        delivered = []

        async def capture(load, timeout=None):
            delivered.append(load)

        with mock_patch.object(m, "_send_req_async_main", side_effect=capture):
            asyncio.run(m._register_resources_with_master())
        assert len(delivered) == 1
        load = delivered[0]
        assert load["resources"] == {}
        assert load["resource_grains"] == {}
        for key in ("_register_token", "_chunk_seq", "_chunk_total", "_chunk_is_last"):
            assert (
                key not in load
            ), f"{key} must be omitted on empty-pillar single-chunk payloads"

    def test_concurrent_registrations_use_distinct_tokens(self, minion_opts):
        """
        Two overlapping ``_register_resources_with_master`` coroutines
        running on the same Minion instance must produce distinct tokens.
        A shared token would let the master conflate chunks across
        registrations — e.g. cancel chunk 1 of call A because chunk 0 of
        call B arrived under the same key.
        """
        m = _mk_minion(minion_opts, 25, resource_register_chunk_size=10)
        # A gate the capturer flips once per call so we can interleave
        # two in-flight registrations under one event loop.
        send_order = []
        tokens_per_call = {"a": set(), "b": set()}
        current = {"name": "a"}

        async def capture(load, timeout=None):
            # Record which call this is for by reading the sentinel map.
            tokens_per_call[current["name"]].add(load.get("_register_token"))
            send_order.append((current["name"], load["_chunk_seq"]))
            # Brief yield to let the paired task progress.
            await asyncio.sleep(0)

        async def run_both():
            with mock_patch.object(m, "_send_req_async_main", side_effect=capture):
                # Each call owns a distinct 'name' so we can group tokens.
                async def _call(name):
                    current["name"] = name
                    await m._register_resources_with_master()

                # Serialise the two calls through the loop so each gets
                # its own token-generation pass; concurrent event-loop
                # scheduling here would still reach the same assertion
                # (distinct tokens per call) but be flaky on 'current'.
                await _call("a")
                await _call("b")

        asyncio.run(run_both())
        tokens_a = tokens_per_call["a"] - {None}
        tokens_b = tokens_per_call["b"] - {None}
        assert len(tokens_a) == 1, f"call 'a' must share one token; got {tokens_a}"
        assert len(tokens_b) == 1
        assert tokens_a.isdisjoint(
            tokens_b
        ), "two registrations on the same minion must use distinct tokens"

    def test_resolve_opt_in_cache_populated_once_then_reused(self, minion_opts):
        """
        With ``resource_grains_cache_in_memory: True`` the resolve path
        populates ``_resource_grains_cache`` on first grain-target call and
        serves subsequent calls from it without re-rendering. Catches a
        regression where the opt-in branch forgets to persist.
        """
        m = _mk_minion(minion_opts, 5, resource_grains_cache_in_memory=True)
        m._resource_grains_cache = None
        n_calls = {"collect": 0}

        orig = m._collect_resource_grains_for

        def counting_collect(srns):
            n_calls["collect"] += 1
            return orig(srns)

        with mock_patch.object(
            m, "_collect_resource_grains_for", side_effect=counting_collect
        ):
            load = {
                "tgt": "env:prod",
                "tgt_type": "grain",
                "fun": "test.ping",
            }
            r1 = m._resolve_resource_targets(load)
            r2 = m._resolve_resource_targets(load)
        assert r1 == r2
        assert (
            n_calls["collect"] == 1
        ), f"opt-in retention must render once, got {n_calls['collect']}"
        assert m._resource_grains_cache is not None

    def test_resolve_opt_out_renders_every_call(self, minion_opts):
        """
        Default (opt-out) must re-render on every grain-target call. This
        is the explicit tradeoff: no resident grain map, but target-time
        render cost per call. After the streaming refactor on the same
        PR, the renderer is called per-SRN rather than once per resolve;
        the invariant is that the second resolve ADDS render calls (if
        the opt-out path accidentally cached, the second resolve would
        skip the renderer entirely and the count would stay flat).
        """
        m = _mk_minion(minion_opts, 5, resource_grains_cache_in_memory=False)
        m._resource_grains_cache = None
        n_calls = {"collect": 0}
        orig = m._collect_resource_grains_for

        def counting_collect(srns):
            n_calls["collect"] += 1
            return orig(srns)

        with mock_patch.object(
            m, "_collect_resource_grains_for", side_effect=counting_collect
        ):
            load = {
                "tgt": "env:prod",
                "tgt_type": "grain",
                "fun": "test.ping",
            }
            m._resolve_resource_targets(load)
            first_round = n_calls["collect"]
            assert (
                first_round > 0
            ), "opt-out resolve must drive the renderer at least once"
            m._resolve_resource_targets(load)
        assert n_calls["collect"] > first_round, (
            "opt-out must re-render on every resolve; second resolve added no "
            f"renders (first_round={first_round}, total={n_calls['collect']})"
        )
        # And must NOT populate the persistent cache.
        assert m._resource_grains_cache is None

    def test_register_single_chunk_at_exact_boundary(self, minion_opts):
        """
        Exactly ``chunk_size`` resources -> still one chunk (boundary
        condition on ``len(pairs) <= chunk_size`` in the planner).
        """
        m = _mk_minion(minion_opts, 10, resource_register_chunk_size=10)
        delivered = []

        async def capture(load, timeout=None):
            delivered.append(load)

        with mock_patch.object(m, "_send_req_async_main", side_effect=capture):
            asyncio.run(m._register_resources_with_master())
        assert len(delivered) == 1
        for key in ("_register_token", "_chunk_seq", "_chunk_total", "_chunk_is_last"):
            assert key not in delivered[0]

    def test_register_two_chunks_at_boundary_plus_one(self, minion_opts):
        """``chunk_size + 1`` resources -> exactly 2 chunks."""
        m = _mk_minion(minion_opts, 11, resource_register_chunk_size=10)
        delivered = []

        async def capture(load, timeout=None):
            delivered.append(load)

        with mock_patch.object(m, "_send_req_async_main", side_effect=capture):
            asyncio.run(m._register_resources_with_master())
        assert len(delivered) == 2
        assert [d["_chunk_seq"] for d in delivered] == [0, 1]
        assert [d["_chunk_total"] for d in delivered] == [2, 2]
        assert [d["_chunk_is_last"] for d in delivered] == [False, True]


# ---------------------------------------------------------------------------
# Per-chunk grain rendering — bounds minion peak transient allocation
# ---------------------------------------------------------------------------


class TestRegisterPerChunkGrainRender:
    """
    ``_register_resources_with_master`` must render each chunk's grain
    dict inside the send loop (default mode) so peak transient allocation
    is bounded by ``resource_register_chunk_size`` instead of the full
    managed-resource grain map.

    Regression guard: live retest at 200K resources showed minion RSS at
    267 MB (baseline 72 MB) when the grain map was rendered upfront and
    held for the full chunk-send loop. These tests pin the fix: render
    per chunk, drop the dict at end of iteration, keep opt-in retention
    behaviour unchanged.
    """

    def test_grains_rendered_per_chunk_not_upfront(self, minion_opts):
        """
        25K-resource pillar with ``chunk_size=10000`` → 3 chunks.
        ``_collect_resource_grains_for`` must be called exactly 3 times
        (once per chunk), each call's SRN list must be <= chunk_size, and
        ``_collect_resource_grains`` (the unbounded "render everything"
        entry point) must NOT be called in default mode.
        """
        m = _mk_minion(minion_opts, 25000, resource_register_chunk_size=10000)
        m.opts["resource_grains_cache_in_memory"] = False

        per_chunk_sizes = []
        orig_for = m._collect_resource_grains_for

        def counting_for(srns):
            srns_list = list(srns) if srns is not None else None
            per_chunk_sizes.append(len(srns_list) if srns_list is not None else -1)
            return orig_for(srns_list)

        unbounded_called = {"n": 0}

        def should_not_run():
            unbounded_called["n"] += 1
            return orig_for(None)

        async def noop(load, timeout=None):
            return None

        with mock_patch.object(
            m, "_collect_resource_grains_for", side_effect=counting_for
        ), mock_patch.object(
            m, "_collect_resource_grains", side_effect=should_not_run
        ), mock_patch.object(
            m, "_send_req_async_main", side_effect=noop
        ):
            asyncio.run(m._register_resources_with_master())

        assert len(per_chunk_sizes) == 3, (
            f"expected 3 per-chunk render calls (one per chunk); got "
            f"{len(per_chunk_sizes)}: {per_chunk_sizes}"
        )
        assert max(per_chunk_sizes) <= 10000, (
            f"per-chunk render saw a batch larger than chunk_size=10000: "
            f"{per_chunk_sizes}"
        )
        assert sum(per_chunk_sizes) == 25000, (
            f"union of per-chunk SRN lists must cover every managed resource "
            f"exactly once; got total {sum(per_chunk_sizes)} (expected 25000)"
        )
        assert unbounded_called["n"] == 0, (
            "default-mode register must not call the unbounded "
            "_collect_resource_grains() entry point — that re-introduces the "
            "upfront full-grain-map allocation this fix removes"
        )

    def test_opt_in_mode_renders_full_map_once_and_projects_per_chunk(
        self, minion_opts
    ):
        """
        With ``resource_grains_cache_in_memory: True``, operator asked for
        retention. We render the full grain map ONCE (so the cache is
        populated) and project per-chunk slices from it via pure dict
        access — no per-chunk ``_collect_resource_grains_for`` calls in
        the send loop.
        """
        m = _mk_minion(
            minion_opts,
            25000,
            resource_register_chunk_size=10000,
            resource_grains_cache_in_memory=True,
        )

        n_full = {"n": 0}
        # ``_collect_resource_grains`` is a thin wrapper that calls
        # ``_collect_resource_grains_for(None)`` — distinguish by the
        # ``srns`` arg: ``None`` means "render everything" (the full
        # render); a list means a per-chunk call.
        for_calls = []
        orig_full = m._collect_resource_grains
        orig_for = m._collect_resource_grains_for

        def counting_full():
            n_full["n"] += 1
            return orig_full()

        def counting_for(srns):
            for_calls.append(None if srns is None else list(srns))
            return orig_for(srns)

        async def noop(load, timeout=None):
            return None

        with mock_patch.object(
            m, "_collect_resource_grains", side_effect=counting_full
        ), mock_patch.object(
            m, "_collect_resource_grains_for", side_effect=counting_for
        ), mock_patch.object(
            m, "_send_req_async_main", side_effect=noop
        ):
            asyncio.run(m._register_resources_with_master())

        assert n_full["n"] == 1, (
            f"opt-in retention must render the full grain map exactly once; "
            f"got {n_full['n']} calls"
        )
        bounded_for_calls = [c for c in for_calls if c is not None]
        assert bounded_for_calls == [], (
            f"opt-in retention projects chunks from the cached full map "
            f"via dict access, not by re-invoking the per-chunk renderer; "
            f"got {len(bounded_for_calls)} per-chunk calls with lengths "
            f"{[len(c) for c in bounded_for_calls]}"
        )
        assert m._resource_grains_cache is not None
        assert len(m._resource_grains_cache) == 25000, (
            f"opt-in cache must contain every managed resource after "
            f"register; got {len(m._resource_grains_cache)}"
        )

    def test_default_mode_does_not_populate_cache(self, minion_opts):
        """
        Default mode (opt-out) must NOT leave ``_resource_grains_cache``
        populated after register — the whole point of the per-chunk
        render is that no full-map dict is held between calls.
        """
        m = _mk_minion(minion_opts, 2500, resource_register_chunk_size=1000)
        m.opts["resource_grains_cache_in_memory"] = False

        async def noop(load, timeout=None):
            return None

        with mock_patch.object(m, "_send_req_async_main", side_effect=noop):
            asyncio.run(m._register_resources_with_master())

        assert m._resource_grains_cache is None, (
            "default mode must not populate _resource_grains_cache; a "
            "populated cache here means the fix silently retained the "
            "full grain map after register"
        )

    def test_empty_resources_still_sends_one_chunk(self, minion_opts):
        """
        An empty pillar still sends exactly one RPC so the master's
        stale-entry flush (``_chunk_is_last=True`` path) runs. Wire
        format must be unchunked (no chunking fields) so old masters
        stay compatible. Matches the behaviour of
        :class:`TestRegisterResourcesEdgeCases` but also asserts the
        per-chunk render path didn't inject stray calls into the
        empty-load codepath.
        """
        minion_opts["resources"] = {}
        minion_opts["multiprocessing"] = False
        with mock_patch("salt.minion.Minion.gen_modules"), mock_patch(
            "salt.minion.Minion.connect_master"
        ):
            m = salt.minion.Minion(minion_opts, load_grains=False)
        m.tok = b"tok"
        _install_grains_fn(m)

        delivered = []
        n_for = {"n": 0}
        n_full = {"n": 0}
        orig_for = m._collect_resource_grains_for
        orig_full = m._collect_resource_grains

        async def capture(load, timeout=None):
            delivered.append(load)

        def counting_for(srns):
            n_for["n"] += 1
            return orig_for(srns)

        def counting_full():
            n_full["n"] += 1
            return orig_full()

        with mock_patch.object(
            m, "_send_req_async_main", side_effect=capture
        ), mock_patch.object(
            m, "_collect_resource_grains_for", side_effect=counting_for
        ), mock_patch.object(
            m, "_collect_resource_grains", side_effect=counting_full
        ):
            asyncio.run(m._register_resources_with_master())

        assert len(delivered) == 1, (
            f"empty pillar must still send exactly one clearing RPC; got "
            f"{len(delivered)}"
        )
        load = delivered[0]
        assert load["resources"] == {}
        assert load["resource_grains"] == {}
        for key in ("_register_token", "_chunk_seq", "_chunk_total", "_chunk_is_last"):
            assert (
                key not in load
            ), f"{key} must be omitted on single-chunk empty-clearing payload"
        assert n_for["n"] == 0, (
            "empty pillar must not drive the per-chunk renderer — nothing "
            f"to render; got {n_for['n']} calls"
        )
        assert n_full["n"] == 0, (
            "empty pillar in default mode must not drive the full renderer "
            f"either; got {n_full['n']} calls"
        )

    def test_chunk_render_failure_logs_and_aborts(self, minion_opts):
        """
        If per-chunk rendering raises mid-stream, the enclosing
        ``_register_resources_with_master`` try/except logs and the rest
        of the registration aborts. Earlier chunks already on the wire
        remain staged on the master (pre-existing partial-registration
        behaviour; not this fix's concern).
        """
        m = _mk_minion(minion_opts, 25, resource_register_chunk_size=10)
        m.opts["resource_grains_cache_in_memory"] = False

        delivered = []
        orig_for = m._collect_resource_grains_for
        call_idx = {"n": 0}

        def flaky(srns):
            call_idx["n"] += 1
            if call_idx["n"] == 2:
                raise RuntimeError("simulated render failure on chunk 2")
            return orig_for(srns)

        async def capture(load, timeout=None):
            delivered.append(load)

        with mock_patch.object(
            m, "_collect_resource_grains_for", side_effect=flaky
        ), mock_patch.object(m, "_send_req_async_main", side_effect=capture):
            asyncio.run(m._register_resources_with_master())

        # Chunk 0 sent successfully (render call 1 succeeded).
        # Chunk 1's render raised — nothing was queued, nothing sent for
        # chunk 1 or chunk 2.
        seqs = [d.get("_chunk_seq") for d in delivered]
        assert seqs == [0], (
            f"a render failure mid-stream must abort the loop after the "
            f"last successfully sent chunk; got seqs {seqs}"
        )

    def test_peak_srn_count_per_render_bounded_at_chunk_size(self, minion_opts):
        """
        Hard invariant: no single ``_collect_resource_grains_for`` call
        inside a register may see more SRNs than ``chunk_size``. This is
        the memory-ceiling contract — whatever the chunking shape, peak
        transient allocation stays O(chunk_size).
        """
        m = _mk_minion(minion_opts, 25000, resource_register_chunk_size=10000)
        m.opts["resource_grains_cache_in_memory"] = False

        peak = {"n": 0}
        orig_for = m._collect_resource_grains_for

        def peek(srns):
            n = len(list(srns)) if srns is not None else -1
            if n > peak["n"]:
                peak["n"] = n
            return orig_for(srns)

        async def noop(load, timeout=None):
            return None

        with mock_patch.object(
            m, "_collect_resource_grains_for", side_effect=peek
        ), mock_patch.object(m, "_send_req_async_main", side_effect=noop):
            asyncio.run(m._register_resources_with_master())

        assert 0 < peak["n"] <= 10000, (
            f"peak per-call SRN count must be in (0, chunk_size=10000]; "
            f"got {peak['n']}"
        )


# ---------------------------------------------------------------------------
# Master-side ``_RegisterChunkStage`` + ``_register_chunk_apply``
# ---------------------------------------------------------------------------


class TestMasterRegisterChunkStage:
    """
    Direct coverage of the master staging store the chunked RPC lands in.
    Separate from ``test_master.py`` which exercises the end-to-end
    ``AESFuncs._register_resources`` path; here we pin the invariants of
    the staging data structure itself so a refactor (e.g. swapping to
    ``threading.RLock`` or an LRU cache lib) that still passes the e2e
    tests can't silently drop entries.
    """

    def _make_stage(self, maxsize=None, ttl=None):
        kwargs = {}
        if maxsize is not None:
            kwargs["maxsize"] = maxsize
        if ttl is not None:
            kwargs["ttl"] = ttl
        return salt.master._RegisterChunkStage(**kwargs)

    def test_record_and_finalise_simple_roundtrip(self):
        stage = self._make_stage()
        stage.record("m1", "t1", {"dummy": ["a"]}, {"dummy:a": {"k": 1}})
        resources, grains = stage.finalise(
            "m1", "t1", {"dummy": ["b"]}, {"dummy:b": {"k": 2}}
        )
        assert sorted(resources["dummy"]) == ["a", "b"]
        assert grains == {"dummy:a": {"k": 1}, "dummy:b": {"k": 2}}
        # Finalise must drop the entry so a fresh registration can use the
        # same token without inheriting stale state (protects against a
        # rogue minion that reuses a token).
        assert stage.pending_count() == 0

    def test_finalise_without_prior_chunks_is_passthrough(self):
        """
        If no non-final chunks were recorded first (e.g. a single-chunk
        registration that happens to carry a token), finalise returns the
        final-chunk payload verbatim. Ensures single-chunk-with-token
        payloads still commit.
        """
        stage = self._make_stage()
        resources, grains = stage.finalise(
            "m1", "t-solo", {"dummy": ["x"]}, {"dummy:x": {"k": 9}}
        )
        assert resources == {"dummy": ["x"]}
        assert grains == {"dummy:x": {"k": 9}}

    def test_concurrent_minions_isolated_by_minion_id(self):
        """
        Two minions each mid-registration with distinct tokens: each gets
        its own staged state and finalise for one doesn't bleed into the
        other.
        """
        stage = self._make_stage()
        stage.record("m-A", "tA", {"dummy": ["a1"]}, {"dummy:a1": {"m": "A"}})
        stage.record("m-B", "tB", {"dummy": ["b1"]}, {"dummy:b1": {"m": "B"}})
        stage.record("m-A", "tA", {"dummy": ["a2"]}, {"dummy:a2": {"m": "A"}})
        assert stage.pending_count() == 2
        r_a, g_a = stage.finalise(
            "m-A", "tA", {"dummy": ["a3"]}, {"dummy:a3": {"m": "A"}}
        )
        assert sorted(r_a["dummy"]) == ["a1", "a2", "a3"]
        # No B entries leak into A's commit.
        for srn in g_a:
            assert g_a[srn]["m"] == "A"
        # B's entry still present until finalised.
        assert stage.pending_count() == 1
        r_b, g_b = stage.finalise(
            "m-B", "tB", {"dummy": ["b2"]}, {"dummy:b2": {"m": "B"}}
        )
        assert sorted(r_b["dummy"]) == ["b1", "b2"]
        for srn in g_b:
            assert g_b[srn]["m"] == "B"
        assert stage.pending_count() == 0

    def test_same_minion_distinct_tokens_do_not_conflate(self):
        """
        One minion issuing two overlapping registrations with distinct
        tokens must have each kept separate. Regression against a bug
        where staging keyed only on ``minion_id`` conflated concurrent
        registrations.
        """
        stage = self._make_stage()
        stage.record("m", "tA", {"dummy": ["a1"]}, {})
        stage.record("m", "tB", {"dummy": ["b1"]}, {})
        assert stage.pending_count() == 2
        rA, _ = stage.finalise("m", "tA", {"dummy": ["a2"]}, {})
        assert sorted(rA["dummy"]) == ["a1", "a2"]
        rB, _ = stage.finalise("m", "tB", {"dummy": ["b2"]}, {})
        assert sorted(rB["dummy"]) == ["b1", "b2"]

    def test_ttl_evicts_abandoned_registration(self):
        """
        A registration whose final chunk never arrives is evicted after
        ``ttl`` seconds so the staging store doesn't grow unbounded when
        minions die mid-stream.
        """
        stage = self._make_stage(ttl=0.05)
        stage.record("m", "t", {"dummy": ["x"]}, {})
        assert stage.pending_count() == 1
        time.sleep(0.15)
        # Trigger lazy eviction with any staging-touching call.
        stage.record("m-other", "t-other", {"dummy": ["y"]}, {})
        assert ("m", "t") not in getattr(stage, "_entries", {})
        # The new entry is still present.
        assert stage.pending_count() == 1

    def test_lru_evicts_oldest_when_maxsize_exceeded(self):
        """
        When the entry cap is exceeded, the oldest insertion is dropped.
        Bounds the staging store under a hostile / buggy minion fleet
        producing many partial registrations.
        """
        stage = self._make_stage(maxsize=3, ttl=3600)
        stage.record("m1", "t1", {"dummy": ["a"]}, {})
        stage.record("m2", "t2", {"dummy": ["b"]}, {})
        stage.record("m3", "t3", {"dummy": ["c"]}, {})
        assert stage.pending_count() == 3
        stage.record("m4", "t4", {"dummy": ["d"]}, {})
        # m1 (oldest) must be evicted.
        assert ("m1", "t1") not in getattr(stage, "_entries", {})
        assert stage.pending_count() == 3

    def test_register_chunk_apply_unchunked_passthrough(self):
        """
        ``_register_chunk_apply`` returns the (resources, grains) tuple
        directly for loads with no ``_register_token`` — i.e. legacy /
        single-chunk-no-token wire format is unchanged.
        """
        stage = self._make_stage()
        load = {
            "id": "m",
            "resources": {"dummy": ["x"]},
            "resource_grains": {"dummy:x": {"k": 1}},
        }
        result = salt.master._register_chunk_apply(load, stage)
        assert result == ({"dummy": ["x"]}, {"dummy:x": {"k": 1}})
        assert stage.pending_count() == 0

    def test_register_chunk_apply_non_final_returns_none(self):
        """Non-final chunk returns ``None`` so caller doesn't commit."""
        stage = self._make_stage()
        load = {
            "id": "m",
            "resources": {"dummy": ["x"]},
            "resource_grains": {"dummy:x": {"k": 1}},
            "_register_token": "tok",
            "_chunk_seq": 0,
            "_chunk_total": 2,
            "_chunk_is_last": False,
        }
        assert salt.master._register_chunk_apply(load, stage) is None
        assert stage.pending_count() == 1

    def test_register_chunk_apply_final_merges_and_returns(self):
        """Final chunk returns the full merged payload."""
        stage = self._make_stage()
        chunk0 = {
            "id": "m",
            "resources": {"dummy": ["a"]},
            "resource_grains": {"dummy:a": {"k": 1}},
            "_register_token": "tok",
            "_chunk_seq": 0,
            "_chunk_total": 2,
            "_chunk_is_last": False,
        }
        chunk1 = {
            "id": "m",
            "resources": {"dummy": ["b"]},
            "resource_grains": {"dummy:b": {"k": 2}},
            "_register_token": "tok",
            "_chunk_seq": 1,
            "_chunk_total": 2,
            "_chunk_is_last": True,
        }
        assert salt.master._register_chunk_apply(chunk0, stage) is None
        resources, grains = salt.master._register_chunk_apply(chunk1, stage)
        assert sorted(resources["dummy"]) == ["a", "b"]
        assert grains == {"dummy:a": {"k": 1}, "dummy:b": {"k": 2}}
        assert stage.pending_count() == 0

    def test_stage_is_thread_safe_against_concurrent_record(self):
        """
        Hammer ``record`` from several threads to catch a regression
        where the LRU bookkeeping drops the internal lock. Deterministic
        assertion: every key put in is retrievable.
        """
        stage = self._make_stage(maxsize=10000, ttl=60)
        n_threads = 8
        per_thread = 200
        errors = []

        def worker(tid):
            try:
                for i in range(per_thread):
                    stage.record(
                        f"m-{tid}",
                        f"tok-{tid}-{i}",
                        {"dummy": [f"r-{tid}-{i}"]},
                        {f"dummy:r-{tid}-{i}": {"tid": tid, "i": i}},
                    )
            except Exception as exc:  # pylint: disable=broad-except
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(tid,)) for tid in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, errors
        assert stage.pending_count() == n_threads * per_thread
