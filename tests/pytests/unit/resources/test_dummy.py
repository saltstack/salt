"""
Unit tests for the ``salt.resources.dummy`` test fixture's state store.

The dummy resource module is the primary fixture for the resource subsystem
test suites.  It has two distinct modes:

* **Default (on-disk)** — each per-resource ``_save_state`` / ``_load_state``
  call round-trips through ``<cachedir>/dummy-resource-<id>.cache`` and is
  what the correctness/lifecycle tests rely on.

* **Scale-mode (in-memory)** — opted into via the minion opt
  ``dummy_resource_persist_state = False``, state lives in a bounded
  OrderedDict with LRU eviction, and no cache files are written.  This
  mode exists for benchmark / chunked-register scale tests where the
  per-resource I/O is the bottleneck, not the thing under test.

These tests pin both the default-mode behavior and the scale-mode semantics
(opt gate, file absence, in-memory round-trip, LRU bound, log level).
"""

import glob
import logging
import os

import pytest

import salt.resources.dummy as dummy_mod


@pytest.fixture(autouse=True)
def _reset_memory_store():
    """Keep tests order-independent: the module-level store is process-wide."""
    dummy_mod._memory_store_reset()
    yield
    dummy_mod._memory_store_reset()


@pytest.fixture
def cachedir(tmp_path):
    return str(tmp_path)


@pytest.fixture
def persist_opts(cachedir):
    """Default on-disk persistence (``dummy_resource_persist_state`` unset == True)."""
    return {"cachedir": cachedir}


@pytest.fixture
def scale_opts(cachedir):
    """Scale-mode: in-memory, generous cap."""
    return {
        "cachedir": cachedir,
        "dummy_resource_persist_state": False,
        "dummy_resource_state_max_entries": 100000,
    }


def _cachefile(cachedir, resource_id):
    return os.path.join(cachedir, f"dummy-resource-{resource_id}.cache")


def _count_cachefiles(cachedir):
    return len(glob.glob(os.path.join(cachedir, "dummy-resource-*.cache")))


# ---------------------------------------------------------------------------
# Default behavior — must be preserved exactly
# ---------------------------------------------------------------------------


def test_dummy_persist_state_default_writes_cache_file(persist_opts, cachedir):
    """
    With the opt at its default (True), ``_save_state`` must write a cache
    file and ``_load_state`` must round-trip the same dict back from disk.
    """
    resource_id = "dummy-01"
    details = {
        "id": resource_id,
        "services": {"apache": "running"},
        "packages": {"coreutils": "1.0"},
    }

    dummy_mod._save_state(persist_opts, resource_id, details)

    assert os.path.exists(_cachefile(cachedir, resource_id))
    assert _count_cachefiles(cachedir) == 1

    loaded = dummy_mod._load_state(persist_opts, resource_id)
    assert loaded == details


# ---------------------------------------------------------------------------
# Scale-mode — opt=False
# ---------------------------------------------------------------------------


def test_dummy_persist_state_disabled_no_file_written(scale_opts, cachedir):
    """
    With the opt set to False, a thousand save/load calls must not leave a
    single cache file behind in ``cachedir``.  This is the whole point of
    scale-mode: eliminate the per-resource filesystem churn.
    """
    for i in range(1000):
        resource_id = f"dummy-{i:05d}"
        dummy_mod._save_state(
            scale_opts,
            resource_id,
            {
                "id": resource_id,
                "services": {"apache": "running"},
                "packages": {"coreutils": "1.0"},
            },
        )
        # Also hit the load path, which is the one that fires during grain
        # collection — this is where _initial_state would otherwise
        # cascade back into _save_state.
        dummy_mod._load_state(scale_opts, resource_id)

    assert _count_cachefiles(cachedir) == 0, (
        "dummy_resource_persist_state=False must not write any cache files; "
        f"found {_count_cachefiles(cachedir)} under {cachedir}"
    )


def test_dummy_persist_state_disabled_round_trips_in_memory(scale_opts):
    """
    Save state A, load state A, assert identical.  Then save state B, load
    state B, assert identical — proving the in-memory store is keyed by
    resource_id and not just a single-slot cache.
    """
    state_a = {
        "id": "dummy-A",
        "services": {"apache": "running"},
        "packages": {"coreutils": "1.0", "apache": "2.4"},
    }
    state_b = {
        "id": "dummy-B",
        "services": {"apache": "stopped"},
        "packages": {"coreutils": "2.0"},
    }

    dummy_mod._save_state(scale_opts, "dummy-A", state_a)
    assert dummy_mod._load_state(scale_opts, "dummy-A") == state_a

    dummy_mod._save_state(scale_opts, "dummy-B", state_b)
    assert dummy_mod._load_state(scale_opts, "dummy-B") == state_b
    # Re-load A to confirm B's save didn't stomp it.
    assert dummy_mod._load_state(scale_opts, "dummy-A") == state_a


def test_dummy_persist_state_disabled_load_initializes_missing(scale_opts, cachedir):
    """
    A ``_load_state`` call for a resource that has never been saved must
    still return a sensible initial state (so the ``_loaded_state`` context
    manager works) without touching disk.
    """
    loaded = dummy_mod._load_state(scale_opts, "never-seen-before")
    assert loaded["id"] == "never-seen-before"
    assert "services" in loaded
    assert "packages" in loaded
    assert _count_cachefiles(cachedir) == 0


def test_dummy_persist_state_disabled_load_returns_copy(scale_opts):
    """
    The in-memory store must return a copy; mutating the loaded dict must
    not retroactively edit the stored state.
    """
    dummy_mod._save_state(
        scale_opts,
        "dummy-C",
        {"id": "dummy-C", "services": {}, "packages": {"redbull": "999.99"}},
    )
    loaded = dummy_mod._load_state(scale_opts, "dummy-C")
    loaded["packages"]["redbull"] = "999999"
    reloaded = dummy_mod._load_state(scale_opts, "dummy-C")
    assert reloaded["packages"]["redbull"] == "999.99"


# ---------------------------------------------------------------------------
# Scale-mode — bounded store (LRU)
# ---------------------------------------------------------------------------


def test_dummy_persist_state_bounded_memory(cachedir):
    """
    With ``dummy_resource_state_max_entries = 10`` perform 20 saves.  The
    first ten resource_ids must have been evicted (LRU) — a subsequent
    load for one of them re-initializes rather than returning the saved
    payload.
    """
    opts = {
        "cachedir": cachedir,
        "dummy_resource_persist_state": False,
        "dummy_resource_state_max_entries": 10,
    }

    for i in range(20):
        dummy_mod._save_state(
            opts,
            f"dummy-{i:02d}",
            {
                "id": f"dummy-{i:02d}",
                "services": {},
                "packages": {"sentinel": str(i)},
            },
        )

    assert len(dummy_mod._memory_state) == 10

    # The ten most recent must still be present with their sentinel.
    for i in range(10, 20):
        loaded = dummy_mod._load_state(opts, f"dummy-{i:02d}")
        assert loaded["packages"]["sentinel"] == str(i)

    # One of the evicted entries re-initializes from scratch — the sentinel
    # that proves state round-tripped must be gone.
    revived = dummy_mod._load_state(opts, "dummy-00")
    assert "sentinel" not in revived["packages"]

    # And still no files on disk.
    assert _count_cachefiles(cachedir) == 0


def test_dummy_persist_state_bounded_lru_touch_on_load(cachedir):
    """
    A load must promote the entry to most-recently-used so a cold entry
    isn't evicted just because it hasn't been *written* lately.
    """
    opts = {
        "cachedir": cachedir,
        "dummy_resource_persist_state": False,
        "dummy_resource_state_max_entries": 3,
    }

    for name in ("a", "b", "c"):
        dummy_mod._save_state(
            opts,
            name,
            {"id": name, "services": {}, "packages": {"sentinel": name}},
        )
    # Touch "a" so it becomes most-recently-used; "b" should be the next
    # eviction candidate when a fourth key arrives.
    dummy_mod._load_state(opts, "a")
    dummy_mod._save_state(
        opts, "d", {"id": "d", "services": {}, "packages": {"sentinel": "d"}}
    )

    # "a" survived, "b" is gone.
    assert "a" in dummy_mod._memory_state
    assert "b" not in dummy_mod._memory_state
    assert "c" in dummy_mod._memory_state
    assert "d" in dummy_mod._memory_state


# ---------------------------------------------------------------------------
# Logging — DEBUG in both modes so a 200K-resource register doesn't flood
# ---------------------------------------------------------------------------


def test_dummy_persist_state_log_level_follows_opt_default(persist_opts, caplog):
    """
    Default (on-disk) mode must log save/load at DEBUG — not WARNING.  The
    sibling fix branch (``dwoz/fix/dummy-resource-log-level``) downgrades
    the original WARNINGs; this scale-mode branch stacks on top and the
    log level must survive both paths.
    """
    with caplog.at_level(logging.DEBUG, logger=dummy_mod.log.name):
        dummy_mod._save_state(
            persist_opts,
            "dummy-log-default",
            {"id": "dummy-log-default", "services": {}, "packages": {}},
        )
        dummy_mod._load_state(persist_opts, "dummy-log-default")

    saved = [r for r in caplog.records if "Saved State" in r.getMessage()]
    loaded = [r for r in caplog.records if "Loaded State" in r.getMessage()]
    assert saved, "expected a Saved State log record"
    assert loaded, "expected a Loaded State log record"
    for rec in saved + loaded:
        assert rec.levelno == logging.DEBUG, (
            f"Dummy resource state logging must be DEBUG, got "
            f"{logging.getLevelName(rec.levelno)}: {rec.getMessage()!r}"
        )


def test_dummy_persist_state_log_level_follows_opt_scale(scale_opts, caplog):
    """Scale-mode must log save/load at DEBUG too (same reason)."""
    with caplog.at_level(logging.DEBUG, logger=dummy_mod.log.name):
        dummy_mod._save_state(
            scale_opts,
            "dummy-log-scale",
            {"id": "dummy-log-scale", "services": {}, "packages": {}},
        )
        dummy_mod._load_state(scale_opts, "dummy-log-scale")

    saved = [r for r in caplog.records if "Saved State" in r.getMessage()]
    loaded = [r for r in caplog.records if "Loaded State" in r.getMessage()]
    assert saved, "expected a Saved State log record"
    assert loaded, "expected a Loaded State log record"
    for rec in saved + loaded:
        assert rec.levelno == logging.DEBUG, (
            f"Dummy resource state logging must be DEBUG, got "
            f"{logging.getLevelName(rec.levelno)}: {rec.getMessage()!r}"
        )
