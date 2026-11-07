"""
Functional tests for :mod:`salt.utils.resource_registry`.

Exercises the real on-disk primary mmap through the registry API with
concurrent processes, covering the sub-chunk-flock-yielding behaviour of
``put_many`` under contention.
"""

import multiprocessing
import time

import pytest

import salt.utils.resource_registry as rr

# Smaller than production (which is 2**21 slots) but large enough for
# 3×8K = 24K entries at a reasonable load factor without compaction
# kicking in during the test window.
_PRIMARY_CAPACITY = 65536
_PRIMARY_SLOT_SIZE = 128

pytestmark = [
    pytest.mark.slow_test,
]


def _mk_resources(n, minion_id, rtype="host"):
    """Return ``{rtype: [rid_0, rid_1, ...]}`` with ``n`` unique ids.

    IDs are namespaced by minion so concurrent registrations on the same
    cache dir don't collide on SRN keys — each key maps to exactly one
    minion, which is the registry's contract.
    """
    return {rtype: [f"{minion_id}-rid-{i:05d}" for i in range(n)]}


def _worker_register(
    cachedir,
    minion_id,
    n_entries,
    result_queue,
    yield_every=1024,
):
    """Open its own ResourceRegistry on ``cachedir`` and register ``n_entries``
    resources for ``minion_id``. Report (ok, elapsed) or an error."""
    try:
        opts = {
            "cachedir": cachedir,
            "resource_index_primary_capacity": _PRIMARY_CAPACITY,
            "resource_index_primary_slot_size": _PRIMARY_SLOT_SIZE,
            "resource_registry_put_many_yield": yield_every,
        }
        reg = rr.ResourceRegistry(opts)
        try:
            resources = _mk_resources(n_entries, minion_id)
            t0 = time.monotonic()
            n_put, n_del = reg.register_minion(minion_id, resources)
            elapsed = time.monotonic() - t0
        finally:
            reg.close()
        result_queue.put(("ok", minion_id, int(n_put), int(n_del), elapsed))
    except Exception as exc:  # pylint: disable=broad-except
        result_queue.put(("err", minion_id, repr(exc)))


def test_concurrent_register_minions_progresses_with_yield(tmp_path):
    """Three concurrent register_minion calls into *separate* cache dirs
    all finish successfully with yield_every enabled.

    This is a regression guard: today the three cache files are
    independent on disk so there is no cross-master contention, but we
    want to prove the yielding code path is exercised correctly when it
    is enabled in opts.
    """
    n_entries = 8000
    procs = []
    q = multiprocessing.Queue()
    for i in range(3):
        d = tmp_path / f"m{i}"
        d.mkdir()
        p = multiprocessing.Process(
            target=_worker_register,
            args=(str(d), f"minion-{i}", n_entries, q, 512),
        )
        procs.append(p)

    t0 = time.monotonic()
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=120)
    total = time.monotonic() - t0

    results = [q.get(timeout=5) for _ in range(len(procs))]
    errors = [r for r in results if r[0] == "err"]
    assert not errors, errors
    for ok, _mid, n_put, n_del, _elapsed in results:
        assert ok == "ok"
        assert n_put == n_entries
        assert n_del == 0

    # Hard upper bound: three isolated 8K registers should finish well
    # inside 60 s even on a loaded host. Primarily this is a
    # "does not deadlock / does not OOM" guard.
    assert total < 60, f"concurrent isolated registers took {total:.2f}s"


def test_concurrent_register_same_cache_dir_progresses(tmp_path):
    """Three concurrent register_minion calls on the *same* cache dir
    (i.e. same primary mmap file) all finish; this is the hot path that
    the A' yield behaviour is designed to improve under contention.

    We don't assert an exact speedup because micro-timings are flaky;
    we do assert all three complete in under 60s and no entries are
    lost.
    """
    cachedir = str(tmp_path)
    n_entries = 8000
    q = multiprocessing.Queue()
    procs = [
        multiprocessing.Process(
            target=_worker_register,
            args=(cachedir, f"minion-{i}", n_entries, q, 512),
        )
        for i in range(3)
    ]

    t0 = time.monotonic()
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=120)
    total = time.monotonic() - t0

    results = [q.get(timeout=5) for _ in range(len(procs))]
    errors = [r for r in results if r[0] == "err"]
    assert not errors, errors
    for ok, _mid, n_put, n_del, _elapsed in results:
        assert ok == "ok"
        assert n_put == n_entries
        assert n_del == 0

    assert total < 60, f"concurrent same-cachedir registers took {total:.2f}s"

    # Verify every registered pair is actually present in the final
    # cache. Open a reader registry and spot-check each minion.
    opts = {
        "cachedir": cachedir,
        "resource_index_primary_capacity": _PRIMARY_CAPACITY,
        "resource_index_primary_slot_size": _PRIMARY_SLOT_SIZE,
    }
    reg = rr.ResourceRegistry(opts)
    try:
        for i in range(3):
            got = reg.get_resources_for_minion(f"minion-{i}")
            # register_minion stores {rtype: [rid, ...]}.
            assert "host" in got, (i, got)
            assert len(got["host"]) == n_entries, (i, len(got["host"]))
    finally:
        reg.close()
