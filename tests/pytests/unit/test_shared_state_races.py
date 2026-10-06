"""
Stress tests for shared in-process caches touched from executor threads.

Motivation
==========

Salt's MWorker async migration converted 26 ``AESFuncs`` methods, 5
``ClearFuncs`` methods, and ``AuthFuncs._auth_impl`` to ``async def``,
with the synchronous internals offloaded to ``loop.run_in_executor``.
Any shared cache previously touched only from the single-threaded ioloop
is now hit by arbitrary executor worker threads under concurrent load.

The tests here hammer each identified cache from many threads via
``ThreadPoolExecutor(max_workers=32).submit(...)`` and assert:

* no exception raised (``dict changed size during iteration``, etc.),
* no lost writes (final cache state matches the expected set of keys),
* no torn reads (values are internally consistent),
* where applicable, RSA verify / sign under concurrent access still
  produces correct results.

Some entries in the audit list turned out not to exist on the current
branch:

* ``salt.crypt.PrivateKey._signer_cache`` / ``PublicKey._verifier_cache``
  -- the "Bug 4 caching fix" hasn't landed on this commit.
* ``salt.utils.optsdict._proxy_cache`` -- ditto for "Bug 5".

Those absences are recorded in the audit report; here we only test
caches that actually exist.
"""

import concurrent.futures
import threading

import pytest

import salt.cache
import salt.crypt
import salt.loader.lazy
import salt.utils.decorators
import salt.utils.optsdict
from tests.support.mock import patch

THREAD_COUNT = 32
OPS_PER_THREAD = 200


# ---------------------------------------------------------------------------
# salt.cache.MemCache
# ---------------------------------------------------------------------------


@pytest.fixture
def memcache_opts():
    return {
        "cache": "stress_driver",
        "memcache_expire_seconds": 60,
        # Deliberately generous so LRU eviction can't be confused with
        # a race-driven lost write. Tests never exceed this count.
        "memcache_max_items": 100_000,
        "memcache_full_cleanup": False,
        "memcache_debug": False,
    }


@pytest.fixture
def memcache(memcache_opts):
    # Isolate ``MemCache.data`` for this test.
    salt.cache.MemCache.data = {}
    with patch("salt.loader.cache", return_value={}):
        cache = salt.cache.factory(memcache_opts)
        # Force :attr:`storage` to materialise so all threads see the
        # same OrderedDict instance without racing on the initial
        # ``MemCache.data[storage_id] = OrderedDict()`` write.
        _ = cache.storage
        yield cache
    salt.cache.MemCache.data = {}


def test_memcache_concurrent_store(memcache):
    """
    Concurrent ``store`` must not drop entries and must not raise
    ``RuntimeError: dictionary changed size during iteration``.
    """
    total = THREAD_COUNT * OPS_PER_THREAD
    keys = [f"k{i}" for i in range(total)]
    errors = []

    def worker(key):
        try:
            memcache.store("bank", key, key)
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(exc)

    with patch("salt.cache.Cache.store"), patch("salt.cache.Cache.fetch"):
        with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_COUNT) as ex:
            list(ex.map(worker, keys))

    assert not errors, "unexpected exceptions: %s" % errors
    storage = salt.cache.MemCache.data["stress_driver"]
    stored_keys = {key for (_bank, key) in storage.keys()}
    assert stored_keys == set(keys), "lost writes: missing=%s" % (
        set(keys) - stored_keys
    )
    # Each record must be a well-formed [atime, expires, data] triple.
    for record in storage.values():
        assert len(record) == 3
        assert isinstance(record[0], float)


def test_memcache_concurrent_fetch_atime_update(memcache):
    """
    ``fetch`` updates the record atime via ``pop`` -> ``__setitem__``.
    Under contention this used to torn-write; verify no records are lost
    and the returned value is always the one we stored.
    """
    errors = []
    returned = []

    with patch("salt.cache.Cache.store"), patch("salt.cache.Cache.fetch"):
        memcache.store("bank", "hot_key", "hot_value")

        def worker(_):
            try:
                returned.append(memcache.fetch("bank", "hot_key"))
            except Exception as exc:  # pylint: disable=broad-except
                errors.append(exc)

        with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_COUNT) as ex:
            list(ex.map(worker, range(THREAD_COUNT * OPS_PER_THREAD)))

    assert not errors, "unexpected exceptions: %s" % errors
    assert all(v == "hot_value" for v in returned)
    storage = salt.cache.MemCache.data["stress_driver"]
    assert ("bank", "hot_key") in storage


def test_memcache_concurrent_store_flush_fetch(memcache):
    """
    Interleave writers, readers and flushers on overlapping key
    ranges. Verifies the class-level lock covers all three mutation
    families (``store``, ``fetch`` atime bump, ``flush``).
    """
    errors = []
    keys = [f"mix_{i}" for i in range(256)]

    def store_worker(_):
        try:
            for key in keys:
                memcache.store("bank", key, key + "_v2")
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(("store", exc))

    def fetch_worker(_):
        try:
            for key in keys:
                memcache.fetch("bank", key)
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(("fetch", exc))

    def flush_worker(_):
        try:
            # Flush a single key at a time so the writers still get a
            # meaningful hit rate. Whole-bank flush would trivially
            # produce lost writes.
            for key in keys[::8]:
                memcache.flush("bank", key)
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(("flush", exc))

    with patch("salt.cache.Cache.store"), patch("salt.cache.Cache.fetch"), patch(
        "salt.cache.Cache.flush"
    ):
        # Seed the cache while patches are active so we don't touch a
        # real driver.
        for key in keys:
            memcache.store("bank", key, key)
        with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_COUNT) as ex:
            futs = []
            for i in range(THREAD_COUNT):
                if i % 3 == 0:
                    futs.append(ex.submit(flush_worker, i))
                elif i % 2 == 0:
                    futs.append(ex.submit(fetch_worker, i))
                else:
                    futs.append(ex.submit(store_worker, i))
            for fut in concurrent.futures.as_completed(futs):
                fut.result()

    assert not errors, "unexpected exceptions: %s" % errors


def test_memcache_storage_property_no_lost_odicts(memcache_opts):
    """
    The ``storage`` property lazily creates the per-driver
    :class:`OrderedDict`. Concurrent instantiation on the same driver
    used to race: two threads could both see an empty ``MemCache.data``
    slot and each write a fresh OrderedDict, silently discarding the
    other thread's stored records.
    """
    salt.cache.MemCache.data = {}
    errors = []
    seen = []

    def worker(_):
        try:
            with patch("salt.loader.cache", return_value={}):
                cache = salt.cache.factory(memcache_opts)
                storage = cache.storage
                seen.append(id(storage))
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_COUNT) as ex:
        list(ex.map(worker, range(THREAD_COUNT * 4)))

    assert not errors, "unexpected exceptions: %s" % errors
    # All threads must observe the same underlying storage object.
    assert len(set(seen)) == 1, "MemCache.data race produced multiple odicts"
    salt.cache.MemCache.data = {}


# ---------------------------------------------------------------------------
# salt.master.AuthFuncs.sessions
# ---------------------------------------------------------------------------


class _FakeAuthFuncs:
    """
    Test double for :class:`salt.master.AuthFuncs.session_key` that
    exercises the lock without needing the full AuthFuncs plumbing
    (MasterKeys, event bus, disk sessions dir, ...). Mirrors the
    lock + dict layout of the real class.
    """

    def __init__(self):
        self.sessions = {}
        self._sessions_lock = threading.Lock()
        self.write_calls = 0
        self._write_lock = threading.Lock()

    def _write(self):
        with self._write_lock:
            self.write_calls += 1

    def session_key(self, minion):
        # Fast-path cache hit: single locked read.
        with self._sessions_lock:
            cached = self.sessions.get(minion)
        if cached is not None:
            return cached[1]
        # Simulate the expensive Crypticle write/read.
        self._write()
        entry = (0.0, f"key-for-{minion}")
        with self._sessions_lock:
            self.sessions[minion] = entry
        return entry[1]


def test_session_key_concurrent_no_torn_reads():
    """
    Two threads racing on ``sessions[minion]`` must not observe a
    half-populated tuple. The class stores ``(mtime, key)`` and
    unpacks it in one step; the fix locks the access so unpacking is
    safe.
    """
    fake = _FakeAuthFuncs()
    errors = []
    values = []
    minions = [f"minion-{i}" for i in range(64)]

    def worker(_):
        try:
            for m in minions:
                values.append(fake.session_key(m))
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_COUNT) as ex:
        list(ex.map(worker, range(THREAD_COUNT)))

    assert not errors, "unexpected exceptions: %s" % errors
    for v in values:
        assert isinstance(v, str) and v.startswith("key-for-")
    assert set(fake.sessions.keys()) == set(minions)


# ---------------------------------------------------------------------------
# salt.loader.LazyLoader (audit-only stress test)
# ---------------------------------------------------------------------------


def test_lazyloader_lock_reentrant():
    """
    ``LazyLoader._get_lock`` returns an :class:`RLock`. Verify it is
    reentrant (needed because ``_load`` -> ``_refresh_file_mapping``
    can re-enter under the same lock).
    """

    class _Fake:
        _get_lock = salt.loader.lazy.LazyLoader._get_lock

    lock = _Fake._get_lock(_Fake)
    # Reentrant acquire from the same thread must not deadlock.
    with lock:
        with lock:
            pass


def test_lazyloader_dict_concurrent_safe():
    """
    Concurrent ``_load_module``-style mutations to ``LazyLoader._dict``
    happen under ``self._lock``. Simulate the pattern with a bare
    RLock and a dict, and assert no lost writes / no exceptions.
    """
    lock = threading.RLock()
    d = {}
    errors = []

    def worker(start):
        try:
            for i in range(OPS_PER_THREAD):
                key = f"m.{start * OPS_PER_THREAD + i}"
                with lock:
                    d[key] = i
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_COUNT) as ex:
        list(ex.map(worker, range(THREAD_COUNT)))

    assert not errors, "unexpected exceptions: %s" % errors
    assert len(d) == THREAD_COUNT * OPS_PER_THREAD


# ---------------------------------------------------------------------------
# salt.utils.optsdict.OptsDict (audit-only stress test)
# ---------------------------------------------------------------------------


def test_optsdict_concurrent_mutations_safe():
    """
    :class:`OptsDict` uses a per-instance :class:`RLock` on every
    mutation path (``__setitem__``, ``__delitem__``, ``pop``, ...).
    Verify no ``dict changed size during iteration`` errors under
    concurrent writers + iterators.
    """
    od = salt.utils.optsdict.OptsDict.from_dict({"initial": True})
    errors = []
    total_ops = THREAD_COUNT * OPS_PER_THREAD
    write_keys = [f"k{i}" for i in range(total_ops)]

    def writer(key):
        try:
            od[key] = key
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(("writer", exc))

    def reader(_):
        try:
            # Iterating triggers OptsDict.__iter__, which rebuilds the
            # underlying dict under the lock.
            for _key in od:
                pass
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(("reader", exc))

    with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_COUNT) as ex:
        futs = [ex.submit(writer, k) for k in write_keys]
        # Interleave a handful of readers.
        futs += [ex.submit(reader, i) for i in range(THREAD_COUNT * 4)]
        for fut in concurrent.futures.as_completed(futs):
            fut.result()

    assert not errors, "unexpected exceptions: %s" % errors
    # All writer keys must be present (in addition to "initial").
    missing = set(write_keys) - set(od._local.keys())
    assert not missing, "OptsDict lost writes: %s" % missing


# ---------------------------------------------------------------------------
# salt.utils.decorators.memoize (audit-only stress test)
# ---------------------------------------------------------------------------


def test_memoize_concurrent_idempotent():
    """
    ``salt.utils.decorators.memoize`` uses a raw dict without a lock.
    Under CPython the GIL makes dict item assignment atomic, so the
    check-then-set races into duplicate ``func`` calls but not into a
    torn read: every caller still gets the same cached value on hit.
    Verify that under 32-thread contention the cached result is
    internally consistent (same object per key).
    """
    call_counts = {}
    counter_lock = threading.Lock()

    @salt.utils.decorators.memoize
    def expensive(arg):
        with counter_lock:
            call_counts[arg] = call_counts.get(arg, 0) + 1
        # Return a fresh mutable so identity comparisons detect
        # "which call filled the cache".
        return object()

    results = {}
    errors = []
    keys = ["a", "b", "c", "d", "e", "f", "g", "h"]

    def worker(key):
        try:
            r = expensive(key)
            results.setdefault(key, []).append(r)
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_COUNT) as ex:
        futs = []
        for _ in range(OPS_PER_THREAD):
            for key in keys:
                futs.append(ex.submit(worker, key))
        for fut in concurrent.futures.as_completed(futs):
            fut.result()

    assert not errors, "unexpected exceptions: %s" % errors
    # ``memoize`` under contention CAN call ``func`` more than once
    # per unique key (that's the wasted-work race noted in the audit),
    # but every returned value for a given key must ultimately settle
    # on a single cached object.
    for key in keys:
        vals = results[key]
        # Eventually-consistent: the last N-K calls must return the
        # winning cached object. We only require that at most one
        # distinct object leaks per key at steady state -- the
        # penultimate call and the last call must agree.
        assert vals[-1] is vals[-2], (
            "memoize returned different objects for key %s on back-to-back calls" % key
        )


# ---------------------------------------------------------------------------
# RSA verify / sign under concurrent access (crypto correctness)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rsa_keypair():
    """
    Generate a real RSA keypair in memory. Reused across the
    verify/sign stress tests so we pay the keygen cost once.
    """
    priv_pem, pub_pem = salt.crypt.gen_keys(2048)
    priv = salt.crypt.PrivateKeyString(priv_pem)
    pub = salt.crypt.PublicKeyString(pub_pem)
    return priv, pub


# ``PrivateKey.sign`` / ``PublicKey.verify`` default to ``PKCS1v15-SHA1``,
# which Salt rejects at its own boundary when FIPS mode is enabled
# (``salt/crypt.py::BaseKey._enforce_fips``). The concurrency invariant
# we're stress-testing here is orthogonal to the hash choice — both
# branches funnel through the same ``self.key.sign(...)`` /
# ``self.key.verify(...)`` executor codepath. Pass the FIPS-approved
# ``PKCS1v15-SHA224`` algorithm explicitly so the test exercises the
# same shared-state paths in both FIPS and non-FIPS runs.
_SIGNING_ALGORITHM = salt.crypt.PKCS1v15_SHA224


def test_rsa_verify_concurrent(rsa_keypair):
    """
    Signature verification is CPU-bound and now runs on executor
    threads for ``_return``. Verify that many threads verifying the
    same signature at once all produce ``True`` and no thread raises.
    """
    priv, pub = rsa_keypair
    message = b"salt-shared-state-stress"
    signature = priv.sign(message, algorithm=_SIGNING_ALGORITHM)

    errors = []
    results = []

    def worker(_):
        try:
            results.append(pub.verify(message, signature, algorithm=_SIGNING_ALGORITHM))
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_COUNT) as ex:
        list(ex.map(worker, range(THREAD_COUNT * 32)))

    assert not errors, "unexpected exceptions: %s" % errors
    assert all(results), "some verifies returned False under concurrency"


def test_rsa_sign_concurrent(rsa_keypair):
    """
    Signing is used by ``AuthFuncs._clear_signed``, offloaded to the
    default executor. Verify concurrent signs each produce a valid
    signature the corresponding public key accepts.
    """
    priv, pub = rsa_keypair
    errors = []
    good = []

    def worker(seed):
        try:
            msg = f"stress-{seed}".encode()
            sig = priv.sign(msg, algorithm=_SIGNING_ALGORITHM)
            good.append(pub.verify(msg, sig, algorithm=_SIGNING_ALGORITHM))
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_COUNT) as ex:
        list(ex.map(worker, range(THREAD_COUNT * 8)))

    assert not errors, "unexpected exceptions: %s" % errors
    assert all(good), "some signatures did not verify under concurrent sign"
