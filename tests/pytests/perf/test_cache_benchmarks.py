"""
Performance benchmarks: mmap_cache vs localfs.

Run with::

    pytest tests/pytests/perf/test_cache_benchmarks.py -v \
        --benchmark-columns=mean,stddev,median,ops,rounds \
        --benchmark-sort=name

These tests are *not* collected by the regular test suite (``tests/`` root is
scanned only for ``unit/``, ``functional/``, etc.).  They must be invoked
explicitly.

Benchmark matrix
----------------
Each operation (store, fetch, updated, flush-key, list) is benchmarked against
both backends with a realistic payload (a dict that mimics a minion grain
record, ~1 KB serialised).  A second "large payload" variant (~64 KB) tests
the heap-append path that only mmap_cache exercises.

The ``--benchmark-compare`` flag can be used across runs to track regressions.
"""

import os
import shutil
import tempfile

import pytest

import salt.cache.localfs as localfs
import salt.cache.mmap_cache as mmap_cache

# ---------------------------------------------------------------------------
# Shared fixtures and helpers
# ---------------------------------------------------------------------------

# Realistic grain-like payload (~1 KB serialised)
_SMALL_PAYLOAD = {
    "os": "Ubuntu",
    "os_family": "Debian",
    "osrelease": "22.04",
    "oscodename": "jammy",
    "kernel": "Linux",
    "kernelrelease": "5.15.0-91-generic",
    "cpuarch": "x86_64",
    "num_cpus": 8,
    "mem_total": 32768,
    "ip_interfaces": {"eth0": ["10.0.0.1"], "lo": ["127.0.0.1"]},
    "fqdn": "minion-001.example.com",
    "id": "minion-001",
    "saltversion": "3009.0",
    "pythonversion": [3, 11, 0, "final", 0],
    "grains_cache_enabled": True,
    "roles": ["web", "cache", "worker"],
}

# Large payload (~64 KB) — stresses heap-append vs file-per-key
_LARGE_PAYLOAD = {
    "big_data": "x" * 65_000,
    "id": "minion-big",
}

_BANK = "minions"
_KEY = "grains"
_N_KEYS = 200  # number of distinct keys for list / bulk tests

_OPTS = {
    # Size is set to _N_KEYS * 10 (~10 % fill factor).  In production it
    # would be tuned to the expected bank cardinality; keeping it proportional
    # here ensures list/scan benchmarks reflect realistic index utilisation
    # rather than an artificially sparse table.
    "mmap_cache_size": _N_KEYS * 10,
    "mmap_cache_slot_size": 96,
    "mmap_cache_key_size": 64,
}


@pytest.fixture
def configure_loader_modules():
    return {
        localfs: {},
        mmap_cache: {"__opts__": _OPTS},
    }


@pytest.fixture
def localfs_dir(tmp_path):
    d = str(tmp_path / "localfs")
    os.makedirs(d)
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def mmap_dir(tmp_path):
    d = str(tmp_path / "mmap")
    os.makedirs(d)
    mmap_cache._caches.clear()
    yield d
    mmap_cache._caches.clear()
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def localfs_populated(localfs_dir):
    """localfs cache pre-populated with _N_KEYS entries."""
    for i in range(_N_KEYS):
        localfs.store(_BANK, f"key_{i:04d}", _SMALL_PAYLOAD, cachedir=localfs_dir)
    return localfs_dir


@pytest.fixture
def mmap_populated(mmap_dir):
    """mmap_cache pre-populated with _N_KEYS entries."""
    for i in range(_N_KEYS):
        mmap_cache.store(_BANK, f"key_{i:04d}", _SMALL_PAYLOAD, cachedir=mmap_dir)
    return mmap_dir


# ---------------------------------------------------------------------------
# store — small payload
# ---------------------------------------------------------------------------


def test_localfs_store_small(benchmark, localfs_dir):
    benchmark(localfs.store, _BANK, _KEY, _SMALL_PAYLOAD, cachedir=localfs_dir)


def test_mmap_store_small(benchmark, mmap_dir):
    benchmark(mmap_cache.store, _BANK, _KEY, _SMALL_PAYLOAD, cachedir=mmap_dir)


# ---------------------------------------------------------------------------
# store — large payload
# ---------------------------------------------------------------------------


def test_localfs_store_large(benchmark, localfs_dir):
    benchmark(localfs.store, _BANK, _KEY, _LARGE_PAYLOAD, cachedir=localfs_dir)


def test_mmap_store_large(benchmark, mmap_dir):
    benchmark(mmap_cache.store, _BANK, _KEY, _LARGE_PAYLOAD, cachedir=mmap_dir)


# ---------------------------------------------------------------------------
# fetch (cache warm — repeated reads of same key)
# ---------------------------------------------------------------------------


def test_localfs_fetch_warm(benchmark, localfs_dir):
    localfs.store(_BANK, _KEY, _SMALL_PAYLOAD, cachedir=localfs_dir)
    benchmark(localfs.fetch, _BANK, _KEY, cachedir=localfs_dir)


def test_mmap_fetch_warm(benchmark, mmap_dir):
    mmap_cache.store(_BANK, _KEY, _SMALL_PAYLOAD, cachedir=mmap_dir)
    benchmark(mmap_cache.fetch, _BANK, _KEY, cachedir=mmap_dir)


# ---------------------------------------------------------------------------
# fetch — large payload
# ---------------------------------------------------------------------------


def test_localfs_fetch_large(benchmark, localfs_dir):
    localfs.store(_BANK, _KEY, _LARGE_PAYLOAD, cachedir=localfs_dir)
    benchmark(localfs.fetch, _BANK, _KEY, cachedir=localfs_dir)


def test_mmap_fetch_large(benchmark, mmap_dir):
    mmap_cache.store(_BANK, _KEY, _LARGE_PAYLOAD, cachedir=mmap_dir)
    benchmark(mmap_cache.fetch, _BANK, _KEY, cachedir=mmap_dir)


# ---------------------------------------------------------------------------
# updated (mtime lookup — mmap reads index only, no heap)
# ---------------------------------------------------------------------------


def test_localfs_updated(benchmark, localfs_dir):
    localfs.store(_BANK, _KEY, _SMALL_PAYLOAD, cachedir=localfs_dir)
    benchmark(localfs.updated, _BANK, _KEY, cachedir=localfs_dir)


def test_mmap_updated(benchmark, mmap_dir):
    mmap_cache.store(_BANK, _KEY, _SMALL_PAYLOAD, cachedir=mmap_dir)
    benchmark(mmap_cache.updated, _BANK, _KEY, cachedir=mmap_dir)


# ---------------------------------------------------------------------------
# list — N keys already stored
# ---------------------------------------------------------------------------


def test_localfs_list(benchmark, localfs_populated):
    benchmark(localfs.list_, _BANK, cachedir=localfs_populated)


def test_mmap_list(benchmark, mmap_populated):
    benchmark(mmap_cache.list_, _BANK, cachedir=mmap_populated)


# ---------------------------------------------------------------------------
# flush (delete a single key)
# ---------------------------------------------------------------------------


def test_localfs_flush_key(benchmark, localfs_dir):
    def setup():
        localfs.store(_BANK, _KEY, _SMALL_PAYLOAD, cachedir=localfs_dir)

    def run():
        localfs.flush(_BANK, key=_KEY, cachedir=localfs_dir)

    benchmark.pedantic(run, setup=setup, rounds=200, warmup_rounds=5)


def test_mmap_flush_key(benchmark, mmap_dir):
    def setup():
        mmap_cache.store(_BANK, _KEY, _SMALL_PAYLOAD, cachedir=mmap_dir)

    def run():
        mmap_cache.flush_(_BANK, key=_KEY, cachedir=mmap_dir)

    benchmark.pedantic(run, setup=setup, rounds=200, warmup_rounds=5)


# ---------------------------------------------------------------------------
# sequential append (Raft hot-path simulation)
#
# Appends N entries to a log bank in sequence.  This is the primary use-case
# where mmap_cache should show the largest advantage: each append is a single
# heap write + index slot update, with no directory entry creation.
# ---------------------------------------------------------------------------


def test_localfs_sequential_append(benchmark, localfs_dir):
    counter = [0]

    def append_one():
        k = f"{counter[0]:08d}"
        counter[0] += 1
        localfs.store(
            "cluster/raft/log", k, {"term": 1, "entry": k}, cachedir=localfs_dir
        )

    benchmark.pedantic(append_one, rounds=500, warmup_rounds=10)


def test_mmap_sequential_append(benchmark, mmap_dir):
    counter = [0]

    def append_one():
        k = f"{counter[0]:08d}"
        counter[0] += 1
        mmap_cache.store(
            "cluster/raft/log", k, {"term": 1, "entry": k}, cachedir=mmap_dir
        )

    benchmark.pedantic(append_one, rounds=500, warmup_rounds=10)


# ---------------------------------------------------------------------------
# bulk store + full scan (simulates startup log recovery)
# ---------------------------------------------------------------------------


def test_localfs_bulk_store_and_scan(benchmark, localfs_dir):
    def run():
        d = tempfile.mkdtemp(dir=localfs_dir)
        try:
            for i in range(50):
                localfs.store("log", f"{i:04d}", {"i": i}, cachedir=d)
            return localfs.list_("log", cachedir=d)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    benchmark(run)


def test_mmap_bulk_store_and_scan(benchmark, tmp_path):
    def run():
        d = str(tmp_path / f"mmap_bulk_{run.counter}")
        run.counter += 1
        os.makedirs(d, exist_ok=True)
        mmap_cache._caches.clear()
        for i in range(50):
            mmap_cache.store("log", f"{i:04d}", {"i": i}, cachedir=d)
        return mmap_cache.list_("log", cachedir=d)

    run.counter = 0
    benchmark(run)
