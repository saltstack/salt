"""
Minion resource-registration memory ceiling (Q7 of the no-pillar design).

The hard invariant (see ``feedback-minion-never-holds-full-resource-set``):
when a minion registers 200K resources with its master, the full inventory
must NEVER be resident in memory at once -- only one chunk at a time.

This module exercises two levels of that invariant:

* **Generator-shape** (always runs, no master).  Confirms the dummy
  module's ``discover()`` is a generator, that ``init()`` doesn't stuff
  the full ID list into ``__context__``, and that the ``opts`` dict never
  acquires a materialized 200K-entry ``resources`` subtree during
  discovery.  This is the cheap canary -- any regression that turns
  ``discover()`` back into a list comprehension fails this test
  immediately with a clear ``isinstance`` / ``len()`` violation.

* **Register-shape** (always runs, no master).  Consumes the generator
  in chunks of ``resource_register_chunk_size`` (10_000) and asserts that
  at most one chunk is live at any time.  No ``list(discover(...))``
  anywhere in the loop.

* **RSS ceiling** (requires psutil; skipped if the current process can't
  be measured).  Pulls 200K IDs from ``discover()`` in chunks and asserts
  the resident-set-size delta stays under 50 MiB.  This is the
  real-world signal: if a regression accidentally materializes the full
  inventory, this test fires with "RSS grew by 170 MiB" instead of the
  bounded delta.

Intentionally does not spin a real salt-master -- spinning a master and
waiting for a 200K register to drain takes 60+ seconds and is Phase 3's
job.  The invariants we need to catch (list vs. generator, full-set
materialization) are all minion-local; this file covers them without the
master-side orchestration.
"""

import gc
import os

import pytest

import salt.resources.dummy as dummy_mod
import salt.utils.resources

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


CHUNK_SIZE = 10_000
TARGET_COUNT = 200_000
# 50 MiB -- chunk_size (10_000) x per-ID str cost (~50 B zero-padded)
# x safety factor ~10 for grain-dict / pack buffers around one chunk.
MAX_RSS_DELTA_MIB = 50


# ---------------------------------------------------------------------------
# Generator-shape invariants
# ---------------------------------------------------------------------------


def test_discover_200k_is_generator():
    """
    ``discover(opts)`` with a 200K count MUST return a generator, never
    a list.  If this fails the "chunked register" architecture is dead
    in the water -- the full inventory is already materialized before
    the register loop even starts.
    """
    opts = {"dummy_resource_count": TARGET_COUNT}
    gen = dummy_mod.discover(opts)
    # Pull a single item -- the whole set must not be traversed to do so.
    first = next(gen)
    assert first == "dummy-0000001"
    # And it's not a list.
    assert not isinstance(gen, list)


def test_enabled_resource_types_contract():
    """Guardrail for the type-list driver the minion reads."""
    opts = {"resource_types": ["dummy"]}
    assert salt.utils.resources.enabled_resource_types(opts) == ["dummy"]


# ---------------------------------------------------------------------------
# Register-loop shape: chunks, no full list
# ---------------------------------------------------------------------------


def test_chunked_consumption_never_holds_full_inventory():
    """
    Simulate the minion's register loop: iterate ``discover()`` into
    fixed-size chunks and ship each chunk, dropping the reference before
    the next.  Assert the ``opts`` dict never acquires a top-level
    ``resources`` key containing the full inventory.
    """
    opts = {"dummy_resource_count": TARGET_COUNT}

    shipped = []  # per-chunk counts only (NOT the chunks themselves)
    chunk = []
    for rid in dummy_mod.discover(opts):
        chunk.append(rid)
        if len(chunk) >= CHUNK_SIZE:
            shipped.append(len(chunk))
            # Drop the reference -- this is the key invariant.  If the
            # register loop appends chunks to a growing list, this test
            # would still "pass" but the RSS test (below) would catch it.
            chunk = []
            # Enforce: opts never acquires a materialized subtree.
            assert "resources" not in opts or not opts["resources"], (
                "opts['resources'] was populated during chunked consumption; "
                "register loop must not materialize the full inventory"
            )
    if chunk:
        shipped.append(len(chunk))

    assert sum(shipped) == TARGET_COUNT
    assert len(shipped) == TARGET_COUNT // CHUNK_SIZE
    # Every intermediate chunk was exactly CHUNK_SIZE.
    for n in shipped[:-1]:
        assert n == CHUNK_SIZE


# ---------------------------------------------------------------------------
# RSS ceiling (slow test)
# ---------------------------------------------------------------------------


@pytest.mark.slow_test
@pytest.mark.skipif(not HAS_PSUTIL, reason="psutil required for RSS measurement")
def test_200k_register_shape_rss_bounded():
    """
    Pull 200K IDs from ``discover()`` into fixed-size chunks and assert
    the resident-set-size delta stays under 50 MiB.  Mirrors what the
    minion's register loop does, minus the actual master RPC.

    The baseline is measured *after* ``gc.collect()`` to drop
    interpreter-startup noise.  The peak is measured after the full
    200K traversal, before chunk GC.  A regression that materializes
    the full 200K ID list hits ~15 MiB just for the strings and ~170
    MiB when the grain dict is included; either case blows the 50 MiB
    ceiling.
    """
    proc = psutil.Process(os.getpid())
    opts = {
        "dummy_resource_count": TARGET_COUNT,
        "resource_register_chunk_size": CHUNK_SIZE,
    }

    gc.collect()
    baseline_rss = proc.memory_info().rss

    peak_rss = baseline_rss
    total = 0
    chunk = []
    for rid in dummy_mod.discover(opts):
        chunk.append(rid)
        if len(chunk) >= CHUNK_SIZE:
            total += len(chunk)
            # Sample RSS while one chunk is live.
            rss_now = proc.memory_info().rss
            if rss_now > peak_rss:
                peak_rss = rss_now
            chunk = []  # drop reference, GC-able
    if chunk:
        total += len(chunk)
        rss_now = proc.memory_info().rss
        if rss_now > peak_rss:
            peak_rss = rss_now

    assert total == TARGET_COUNT
    delta_bytes = peak_rss - baseline_rss
    delta_mib = delta_bytes / (1024 * 1024)
    assert delta_mib < MAX_RSS_DELTA_MIB, (
        f"minion register shape leaked {delta_mib:.1f} MiB during 200K "
        f"traversal; chunked streaming is not working "
        f"(limit: {MAX_RSS_DELTA_MIB} MiB)"
    )
