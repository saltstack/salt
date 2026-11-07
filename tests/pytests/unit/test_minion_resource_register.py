"""
Deeper unit coverage for minion-side resource register chunking and the
opt-in grain-cache retention. Complements ``test_minion_resources.py``
(which already covers the baseline chunked-send + cache-retention cases)
by exercising edge cases, static-helper correctness, and
concurrent-registration isolation.

The target code lives on PR ``dwoz/fix/minion-register-scale``
(saltstack/salt#70720): see ``Minion._plan_register_chunks``,
``Minion._register_resources_with_master``, and the master-side
per-chunk upsert + ``_return``-triggered sweep in
``salt.utils.resource_registry.ResourceRegistry``.
"""

import asyncio

import salt.loader.context
import salt.master
import salt.minion
import salt.utils.resource_registry
from tests.support.mock import MagicMock
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
        ``resource_grains`` bank sees them in the chunk-store path.
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
        inline stale-entry sweep (legacy single-chunk path) runs. Wire
        format must be unchunked (no ``_register_jid`` / ``_chunk_*``
        fields) so the empty-clear path is zero-coupling for old masters.
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
        for key in (
            "_register_jid",
            "_chunk_seq",
            "_chunk_total",
            "_chunk_is_last",
        ):
            assert (
                key not in load
            ), f"{key} must be omitted on empty-pillar single-chunk payloads"

    def test_concurrent_registrations_use_distinct_jids(self, minion_opts):
        """
        Two overlapping ``_register_resources_with_master`` coroutines
        running on the same Minion instance must produce distinct jids.
        A shared jid would make the master's terminal-chunk sweep
        delete either call's partial writes when the other call's
        terminal chunk arrives.
        """
        m = _mk_minion(minion_opts, 25, resource_register_chunk_size=10)
        jids_per_call = {"a": set(), "b": set()}
        current = {"name": "a"}

        async def capture(load, timeout=None):
            jids_per_call[current["name"]].add(load.get("_register_jid"))
            await asyncio.sleep(0)

        async def run_both():
            with mock_patch.object(m, "_send_req_async_main", side_effect=capture):

                async def _call(name):
                    current["name"] = name
                    await m._register_resources_with_master()

                await _call("a")
                await _call("b")

        asyncio.run(run_both())
        jids_a = jids_per_call["a"] - {None}
        jids_b = jids_per_call["b"] - {None}
        assert len(jids_a) == 1, f"call 'a' must share one jid; got {jids_a}"
        assert len(jids_b) == 1
        assert jids_a.isdisjoint(
            jids_b
        ), "two registrations on the same minion must use distinct jids"

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
        for key in (
            "_register_jid",
            "_chunk_seq",
            "_chunk_total",
            "_chunk_is_last",
        ):
            assert key not in delivered[0]

    def test_register_two_chunks_at_boundary_plus_one(self, minion_opts):
        """
        ``chunk_size + 1`` resources -> exactly 2 chunks sharing one jid;
        the final chunk carries ``_chunk_is_last=True`` to signal the
        master to run the stale-entry sweep.
        """
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
        jids = {d["_register_jid"] for d in delivered}
        assert len(jids) == 1, "all chunks must share one jid"


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
        inline stale-entry sweep (legacy single-chunk wire path) runs.
        Wire format must be unchunked (no chunking fields) so old
        masters stay compatible. Matches the behaviour of
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
        for key in ("_register_jid", "_chunk_seq"):
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
# Master-side chunk-upsert + ``_return``-triggered sweep
# ---------------------------------------------------------------------------


class TestMasterRegisterChunkUpsert:
    """
    Direct coverage of the registry primitives the chunked-register
    handler uses: :meth:`ResourceRegistry.upsert_minion_chunk` and
    :meth:`ResourceRegistry.sweep_minion_stale_jids`.

    These replace the old ``_RegisterChunkStage`` + ``_register_chunk_apply``
    coverage. The new design has no master-side staging dict — each chunk
    writes directly to the primary index, and a trailing ``_return`` RPC
    (``fun="resource.register"``) triggers the stale-jid sweep. Entries
    from prior registrations are preserved mid-stream and only collapsed
    on return.
    """

    @staticmethod
    def _registry(tmp_path):
        """Build a fresh :class:`ResourceRegistry` rooted at ``tmp_path``."""
        opts = {"cachedir": str(tmp_path)}
        salt.utils.resource_registry.reset_registry()
        return salt.utils.resource_registry.get_registry(opts)

    def test_upsert_streams_each_chunk_to_registry(self, tmp_path):
        """
        Each ``upsert_minion_chunk`` call writes immediately — no
        staging, no accumulation. After three chunks the registry
        contains the union of all three chunks' SRNs, stamped with the
        shared jid.
        """
        registry = self._registry(tmp_path)
        jid = "20260101000000000001"
        for seq, rids in enumerate((["a1", "a2"], ["b1"], ["c1", "c2"])):
            n_put = registry.upsert_minion_chunk("m", {"dummy": rids}, jid)
            assert n_put == len(rids)
        # Every rid from every chunk must be present.
        by_minion = registry.get_resources_for_minion("m")
        assert sorted(by_minion["dummy"]) == ["a1", "a2", "b1", "c1", "c2"]
        # And every entry must carry the jid in its value.
        srn_jids = registry._store.srn_jids_by_minion("m")
        for srn, stored in srn_jids.items():
            assert stored == jid, f"entry {srn} must carry jid {jid}; got {stored!r}"

    def test_upsert_is_idempotent(self, tmp_path):
        """
        Replaying a chunk (same minion, same jid, same SRNs) leaves the
        registry unchanged — the master can safely tolerate chunk
        retries without duplicating or deleting entries.
        """
        registry = self._registry(tmp_path)
        jid = "20260101000000000002"
        registry.upsert_minion_chunk("m", {"dummy": ["a1", "a2"]}, jid)
        by_minion_1 = registry.get_resources_for_minion("m")
        registry.upsert_minion_chunk("m", {"dummy": ["a1", "a2"]}, jid)
        by_minion_2 = registry.get_resources_for_minion("m")
        assert by_minion_1 == by_minion_2
        assert sorted(by_minion_2["dummy"]) == ["a1", "a2"]

    def test_sweep_removes_only_older_jids(self, tmp_path):
        """
        After a newer register writes entries stamped with jid=B > jid=A,
        the sweep for jid=B tombstones the A-stamped entries and preserves
        the B-stamped ones. Idempotent: running the sweep twice is a no-op.
        """
        registry = self._registry(tmp_path)
        jid_a = "20260101000000000010"
        jid_b = "20260101000000000020"
        # Register A — entries a1, a2 stamped jid_a.
        registry.upsert_minion_chunk("m", {"dummy": ["a1", "a2"]}, jid_a)
        # Register B begins — overwrites a1 (same SRN) with jid_b, adds b1.
        registry.upsert_minion_chunk("m", {"dummy": ["a1", "b1"]}, jid_b)
        # Pre-sweep: all three entries present.
        pre = registry.get_resources_for_minion("m")
        assert sorted(pre["dummy"]) == ["a1", "a2", "b1"]
        n_del = registry.sweep_minion_stale_jids("m", jid_b)
        # a2 (jid_a < jid_b) tombstoned; a1 (now jid_b after overwrite)
        # and b1 preserved.
        assert n_del == 1
        post = registry.get_resources_for_minion("m")
        assert sorted(post["dummy"]) == ["a1", "b1"]
        # Idempotent: a second sweep is a no-op.
        assert registry.sweep_minion_stale_jids("m", jid_b) == 0

    def test_sweep_preserves_newer_concurrent_register(self, tmp_path):
        """
        If register B is still in flight when register A's return
        arrives, A's sweep must NOT delete B's entries (B has jid > A).
        Strict ``<`` on the jid comparison is the safety net.
        """
        registry = self._registry(tmp_path)
        jid_a = "20260101000000000030"
        jid_b = "20260101000000000040"
        # A writes a1.
        registry.upsert_minion_chunk("m", {"dummy": ["a1"]}, jid_a)
        # B writes b1 (concurrent, newer).
        registry.upsert_minion_chunk("m", {"dummy": ["b1"]}, jid_b)
        # A's return arrives — sweep for jid_a.
        n_del = registry.sweep_minion_stale_jids("m", jid_a)
        # A's own entries are at jid_a, which is NOT strictly less than
        # jid_a; B's entries are at jid_b > jid_a. So nothing is deleted.
        assert n_del == 0
        remaining = registry.get_resources_for_minion("m")
        assert sorted(remaining["dummy"]) == ["a1", "b1"]

    def test_sweep_skips_legacy_entries_without_jid(self, tmp_path):
        """
        Entries written before the schema-3 ``j`` field exists decode
        with ``jid=None`` and must never be deleted by the sweep — we
        can't know if they predate or follow the current register.
        """
        registry = self._registry(tmp_path)
        # Write a legacy entry (no jid) by going through the lower-level
        # store ``put`` with ``jid=None``.
        registry._store.put("dummy:legacy-1", "m", "dummy", jid=None)
        # Stamped entry at some jid.
        registry.upsert_minion_chunk("m", {"dummy": ["new-1"]}, "20260101000000000100")
        # Sweep at a jid newer than the stamped one — would delete it if
        # strict ``<`` held. The legacy entry (no jid) is skipped.
        assert registry.sweep_minion_stale_jids("m", "20260101000000000200") == 1
        remaining = registry.get_resources_for_minion("m")
        # Legacy entry preserved; new-1 (jid < sweep jid) deleted.
        assert "legacy-1" in remaining["dummy"]
        assert "new-1" not in remaining["dummy"]

    def test_upsert_then_sweep_matches_legacy_register_semantics(self, tmp_path):
        """
        An upsert followed by an immediate sweep equals the pre-PR
        ``register_minion`` replacement semantics: entries not in the
        new payload are gone, entries in the new payload are present.
        """
        registry = self._registry(tmp_path)
        jid_a = "20260101000000000300"
        jid_b = "20260101000000000400"
        registry.upsert_minion_chunk("m", {"dummy": ["old-1", "old-2"]}, jid_a)
        # Sweep for jid_a cleans up nothing yet (no older entries).
        registry.sweep_minion_stale_jids("m", jid_a)
        # New registration replaces the set.
        registry.upsert_minion_chunk("m", {"dummy": ["new-1"]}, jid_b)
        registry.sweep_minion_stale_jids("m", jid_b)
        remaining = registry.get_resources_for_minion("m")
        assert remaining["dummy"] == ["new-1"]

    def test_register_minion_stamps_jid(self, tmp_path):
        """
        The legacy :meth:`register_minion` entry point stamps every
        entry with a generated jid so a subsequent chunked register's
        sweep can still identify them as stale.
        """
        registry = self._registry(tmp_path)
        registry.register_minion("m", {"dummy": ["a1"]})
        srn_jids = registry._store.srn_jids_by_minion("m")
        assert srn_jids
        for srn, stored in srn_jids.items():
            assert (
                stored is not None
            ), f"legacy register must stamp a jid; got None for {srn}"


class TestMinionResourceRegisterCompletionEvent:
    """
    The minion fires :data:`salt.defaults.events.MINION_RESOURCE_REFRESH_COMPLETE`
    on the local bus at the end of ``_register_resources_with_master``,
    success or failure. CLI callers using
    ``saltutil.refresh_resources(wait=True)`` block on this event.
    """

    @staticmethod
    def _fake_event_bus(capture):
        """Return a context manager mimicking ``salt.utils.event.get_event``."""

        class _FakeEvent:
            def fire_event(self, payload, tag):
                capture.append((tag, payload))

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def _factory(*args, **kwargs):
            return _FakeEvent()

        return _factory

    def test_chunked_register_fires_complete_event_on_success(self, minion_opts):
        """
        On success the completion event payload reports
        ``complete=True`` + accurate ``chunks_sent`` / ``chunks_total``
        and no ``error`` field.
        """
        m = _mk_minion(minion_opts, 30, resource_register_chunk_size=10)
        events = []

        async def capture(load, timeout=None):
            pass

        factory = self._fake_event_bus(events)
        with mock_patch.object(
            m, "_send_req_async_main", side_effect=capture
        ), mock_patch("salt.utils.event.get_event", side_effect=factory):
            asyncio.run(m._register_resources_with_master())
        refresh_events = [
            e for e in events if e[0] == "/salt/minion/minion_resource_refresh_complete"
        ]
        assert len(refresh_events) == 1
        tag, payload = refresh_events[0]
        assert payload["complete"] is True
        assert payload["chunks_sent"] == 3
        assert payload["chunks_total"] == 3
        assert payload["jid"] is not None
        assert "error" not in payload

    def test_single_chunk_register_fires_complete_event(self, minion_opts):
        """
        The legacy single-chunk wire path still fires the completion
        event so ``wait=True`` works even when there's no jid.
        """
        m = _mk_minion(minion_opts, 5, resource_register_chunk_size=10)
        events = []

        async def capture(load, timeout=None):
            pass

        factory = self._fake_event_bus(events)
        with mock_patch.object(
            m, "_send_req_async_main", side_effect=capture
        ), mock_patch("salt.utils.event.get_event", side_effect=factory):
            asyncio.run(m._register_resources_with_master())
        refresh_events = [
            e for e in events if e[0] == "/salt/minion/minion_resource_refresh_complete"
        ]
        assert len(refresh_events) == 1
        _, payload = refresh_events[0]
        assert payload["complete"] is True
        assert payload["chunks_sent"] == 1
        assert payload["chunks_total"] == 1
        # Single-chunk legacy path has no minion-side jid.
        assert payload["jid"] is None

    def test_abort_mid_chunks_fires_complete_event_with_error(self, minion_opts):
        """
        Partial-progress abort (retry budget exhausted mid-stream)
        still fires the completion event, with ``complete=False``,
        ``chunks_sent < chunks_total``, and an ``error`` string.
        """
        m = _mk_minion(minion_opts, 30, resource_register_chunk_size=10)
        m.opts["resource_register_chunk_retries"] = 0
        events = []

        async def flaky(load, timeout=None):
            if load.get("_chunk_seq") == 1:
                raise RuntimeError("simulated chunk-1 failure")

        factory = self._fake_event_bus(events)
        with mock_patch.object(
            m, "_send_req_async_main", side_effect=flaky
        ), mock_patch("salt.utils.event.get_event", side_effect=factory):
            asyncio.run(m._register_resources_with_master())
        refresh_events = [
            e for e in events if e[0] == "/salt/minion/minion_resource_refresh_complete"
        ]
        assert len(refresh_events) == 1
        _, payload = refresh_events[0]
        assert payload["complete"] is False
        assert payload["chunks_sent"] == 1
        assert payload["chunks_total"] == 3
        assert "error" in payload
        assert "chunk 2/3" in payload["error"]


class TestPillarRefreshDoesNotTouchResources:
    """
    ``Minion.pillar_refresh`` must refresh pillar only — resource
    rediscovery and master register are decoupled. Operators who need
    the resource registry refreshed explicitly run
    ``saltutil.refresh_resources``.
    """

    def test_pillar_refresh_does_not_call_register_resources(self, minion_opts):
        """
        Patch ``_discover_resources`` and ``_register_resources_with_master``
        to loud mocks and assert ``pillar_refresh`` doesn't call them.
        """
        m = _mk_minion(minion_opts, 5, resource_register_chunk_size=10)
        # ``pillar_refresh`` body touches a lot of infra we don't need to
        # fully exercise; stub what it calls so the body is traversable.
        m.matchers_refresh = MagicMock()
        m.beacons_refresh = MagicMock()
        discover = MagicMock()
        register = MagicMock()
        with mock_patch.object(
            m, "_discover_resources", side_effect=discover
        ), mock_patch.object(
            m, "_register_resources_with_master", side_effect=register
        ), mock_patch(
            "salt.pillar.get_async_pillar"
        ) as get_pillar:
            fake = MagicMock()

            async def _compile_pillar():
                return {"ok": True}

            fake.compile_pillar = _compile_pillar

            async def _aclose():
                pass

            fake.aclose = _aclose
            get_pillar.return_value = fake
            try:
                asyncio.run(m.pillar_refresh())
            except Exception:  # pylint: disable=broad-except
                # Any deeper infra failure is irrelevant — we only care
                # that the two resource-side callables were not invoked.
                pass
        discover.assert_not_called()
        register.assert_not_called()
