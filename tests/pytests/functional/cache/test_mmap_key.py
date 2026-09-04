"""
Functional tests for the mmap_key PKI cache backend.

These tests exercise the full ``salt.cache.Cache`` API driven by
``mmap_key`` and mirror the coverage in ``test_localfs_key.py`` so that
both backends remain behaviourally equivalent.
"""

import logging
import os
import time

import pytest

import salt.cache
import salt.cache.mmap_key as mmap_key_mod
from salt.exceptions import SaltCacheError

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cache(minion_opts, tmp_path):
    """Return a ``salt.cache.Cache`` backed by ``mmap_key``."""
    opts = minion_opts.copy()
    opts["keys.cache_driver"] = "mmap_key"
    opts["pki_dir"] = str(tmp_path / "pki")
    opts["mmap_key_size"] = 200
    opts["mmap_key_slot_size"] = 96
    opts["mmap_key_id_size"] = 32
    os.makedirs(opts["pki_dir"], exist_ok=True)

    # Clear any cached MmapCache instances that might reference an old path.
    mmap_key_mod._caches.clear()

    c = salt.cache.Cache(opts, driver="mmap_key")
    try:
        yield c
    finally:
        mmap_key_mod._caches.clear()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

_SAMPLE_PUB = "RSAKEY_minion_a"


# ---------------------------------------------------------------------------
# Lifecycle: pending → rejected → accepted → denied
# ---------------------------------------------------------------------------


def test_key_lifecycle_pending_rejected_accepted(cache):
    """
    Exercise the full state machine: pending → rejected → accepted.

    Unlike localfs_key, mmap_key does not write separate filesystem
    directories; correctness is verified purely through the cache API.
    """
    cache.store("keys", "minion_a", {"state": "pending", "pub": _SAMPLE_PUB})
    assert cache.fetch("keys", "minion_a") == {
        "state": "pending",
        "pub": _SAMPLE_PUB,
    }

    cache.store("keys", "minion_a", {"state": "rejected", "pub": _SAMPLE_PUB})
    assert cache.fetch("keys", "minion_a") == {
        "state": "rejected",
        "pub": _SAMPLE_PUB,
    }

    cache.store("keys", "minion_a", {"state": "accepted", "pub": _SAMPLE_PUB})
    assert cache.fetch("keys", "minion_a") == {
        "state": "accepted",
        "pub": _SAMPLE_PUB,
    }


def test_key_lifecycle_denied(cache):
    """
    Store to the denied_keys bank and verify fetch returns a list.
    """
    cache.store("denied_keys", "minion_a", ["RSAKEY_minion_b"])
    result = cache.fetch("denied_keys", "minion_a")
    assert isinstance(result, list)
    assert result[0].strip() == "RSAKEY_minion_b"


# ---------------------------------------------------------------------------
# updated
# ---------------------------------------------------------------------------


def test_updated(cache):
    now = time.time()
    cache.store("keys", "minion_a", {"state": "accepted", "pub": _SAMPLE_PUB})
    updated = cache.updated("keys", "minion_a")
    assert updated is not None
    assert abs(updated - int(now)) <= 2

    assert cache.updated("keys", "nonexistent") is None


# ---------------------------------------------------------------------------
# minion_id validity
# ---------------------------------------------------------------------------


def test_minion_id_validity_store(cache):
    with pytest.raises(SaltCacheError, match="not a valid minion_id"):
        cache.store("keys", "foo/bar/..", {"state": "pending", "pub": "x"})


def test_minion_id_validity_fetch(cache):
    with pytest.raises(SaltCacheError, match="not a valid minion_id"):
        cache.fetch("keys", "foo/bar/..")


def test_minion_id_validity_updated(cache):
    with pytest.raises(SaltCacheError, match="not a valid minion_id"):
        cache.updated("keys", "foo/bar/..")


def test_minion_id_validity_contains(cache):
    with pytest.raises(SaltCacheError, match="not a valid minion_id"):
        cache.contains("keys", "foo/bar/..")


def test_minion_id_validity_flush(cache):
    with pytest.raises(SaltCacheError, match="not a valid minion_id"):
        cache.flush("keys", "foo/bar/..")


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------


def test_fetch_missing_key_returns_none(cache):
    assert cache.fetch("keys", "ghost") is None


def test_fetch_missing_denied_returns_empty(cache):
    assert cache.fetch("denied_keys", "ghost") == {}


def test_fetch_missing_master_key_returns_empty(cache):
    assert cache.fetch("master_keys", "ghost.pem") == {}


# ---------------------------------------------------------------------------
# flush / contains
# ---------------------------------------------------------------------------


def test_flush_contains(cache):
    cache.store("keys", "minion_x", {"state": "pending", "pub": "K_x"})
    cache.store("keys", "minion_y", {"state": "accepted", "pub": "K_y"})
    cache.store("denied_keys", "minion_a", ["K_a"])

    assert cache.contains("keys", "minion_x")
    assert cache.contains("keys", "minion_y")
    assert cache.contains("denied_keys", "minion_a")

    cache.flush("keys", "minion_x")
    cache.flush("keys", "minion_y")
    cache.flush("denied_keys", "minion_a")

    assert not cache.contains("keys", "minion_x")
    assert not cache.contains("keys", "minion_y")
    assert not cache.contains("denied_keys", "minion_a")


def test_flush_whole_bank_removes_index_file(cache, tmp_path):
    """Flushing a bank with key=None should remove all backing files."""
    pki_dir = str(tmp_path / "pki")
    cache.store("keys", "minion_x", {"state": "pending", "pub": "K_x"})
    cache.store("keys", "minion_y", {"state": "accepted", "pub": "K_y"})

    idx = os.path.join(pki_dir, mmap_key_mod._BANK_INDEX_NAME["keys"])
    assert os.path.exists(idx), "index should exist after writes"

    cache.flush("keys")

    assert not os.path.exists(idx), "index should be removed after bank flush"
    mmap_key_mod._caches.clear()
    assert cache.list("keys") == []


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list(cache):
    cache.store("keys", "minion_x", {"state": "pending", "pub": "K_x"})
    cache.store("keys", "minion_y", {"state": "accepted", "pub": "K_y"})
    cache.store("keys", "minion_z", {"state": "pending", "pub": "K_z"})
    cache.store("denied_keys", "minion_a", ["K_a"])

    assert sorted(cache.list("keys")) == ["minion_x", "minion_y", "minion_z"]
    assert cache.list("denied_keys") == ["minion_a"]


def test_list_empty_bank(cache):
    assert cache.list("keys") == []


# ---------------------------------------------------------------------------
# Overwrite / state transition
# ---------------------------------------------------------------------------


def test_overwrite_state(cache):
    cache.store("keys", "m1", {"state": "pending", "pub": "K1"})
    cache.store("keys", "m1", {"state": "accepted", "pub": "K1"})
    assert cache.fetch("keys", "m1")["state"] == "accepted"


# ---------------------------------------------------------------------------
# Multiple banks are independent
# ---------------------------------------------------------------------------


def test_separate_banks_dont_interfere(cache):
    cache.store("keys", "shared", {"state": "accepted", "pub": "K"})
    cache.store("denied_keys", "shared", ["K_denied"])
    assert cache.fetch("keys", "shared")["state"] == "accepted"
    denied = cache.fetch("denied_keys", "shared")
    assert isinstance(denied, list)
    assert denied[0].strip() == "K_denied"


# ---------------------------------------------------------------------------
# master_keys bank
# ---------------------------------------------------------------------------


def test_master_keys_roundtrip(cache):
    pem = "-----BEGIN RSA PRIVATE KEY-----\nBASE64==\n-----END RSA PRIVATE KEY-----\n"
    cache.store("master_keys", "master.pem", pem)
    result = cache.fetch("master_keys", "master.pem")
    assert "BEGIN RSA PRIVATE KEY" in result


def test_master_keys_list(cache):
    cache.store("master_keys", "master.pem", "PEMDATA1")
    cache.store("master_keys", "master.pub", "PEMDATA2")
    keys = cache.list("master_keys")
    assert "master.pem" in keys
    assert "master.pub" in keys


# ---------------------------------------------------------------------------
# salt-key workflows
# ---------------------------------------------------------------------------


def test_salt_key_list_workflow(cache):
    """
    Simulate the ``salt-key --list-all`` workflow: store keys with different
    states and verify list_keys()-style retrieval.
    """
    minions = {
        "accepted1": "accepted",
        "accepted2": "accepted",
        "pending1": "pending",
        "rejected1": "rejected",
    }
    for name, state in minions.items():
        cache.store("keys", name, {"state": state, "pub": f"KEY_{name}"})

    cache.store("denied_keys", "denied1", ["KEY_denied1"])

    keys = cache.list("keys")
    denied = cache.list("denied_keys")

    assert set(keys) == set(minions.keys())
    assert "denied1" in denied

    for name, state in minions.items():
        entry = cache.fetch("keys", name)
        assert entry["state"] == state


def test_salt_key_accept_workflow(cache):
    """
    Simulate ``salt-key --accept``: move a key from pending to accepted.
    """
    cache.store("keys", "m1", {"state": "pending", "pub": "K1"})
    entry = cache.fetch("keys", "m1")
    assert entry["state"] == "pending"

    entry["state"] = "accepted"
    cache.store("keys", "m1", entry)
    assert cache.fetch("keys", "m1")["state"] == "accepted"


def test_salt_key_reject_workflow(cache):
    """
    Simulate ``salt-key --reject``: move a key from pending to rejected.
    """
    cache.store("keys", "m1", {"state": "pending", "pub": "K1"})
    entry = cache.fetch("keys", "m1")
    entry["state"] = "rejected"
    cache.store("keys", "m1", entry)
    assert cache.fetch("keys", "m1")["state"] == "rejected"


def test_salt_key_delete_workflow(cache):
    """
    Simulate ``salt-key --delete``: remove a key and verify it is gone.
    """
    cache.store("keys", "m1", {"state": "accepted", "pub": "K1"})
    assert cache.contains("keys", "m1")
    cache.flush("keys", "m1")
    assert not cache.contains("keys", "m1")
    assert cache.fetch("keys", "m1") is None


def test_salt_key_deny_workflow(cache):
    """
    Simulate key denial: move pub from keys to denied_keys.
    """
    cache.store("keys", "m1", {"state": "accepted", "pub": "K1"})
    entry = cache.fetch("keys", "m1")
    cache.flush("keys", "m1")
    cache.store("denied_keys", "m1", [entry["pub"]])

    assert not cache.contains("keys", "m1")
    denied = cache.fetch("denied_keys", "m1")
    assert isinstance(denied, list)
    assert denied[0].strip() == "K1"


def test_salt_key_finger_workflow(cache):
    """
    Simulate ``salt-key --finger``: fetch pub key material for fingerprinting.
    """
    import salt.utils.crypt

    pub = (
        "-----BEGIN PUBLIC KEY-----\n"
        "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0+Cq8JAlbM5YLJHZ3LKH\n"
        "-----END PUBLIC KEY-----\n"
    )
    cache.store("keys", "m1", {"state": "accepted", "pub": pub})
    entry = cache.fetch("keys", "m1")
    assert "pub" in entry
    # Verify that the pub can be passed to pem_finger without errors
    salt.utils.crypt.pem_finger(key=entry["pub"].encode("utf-8"), sum_type="sha256")


# ---------------------------------------------------------------------------
# Large-scale: many minions
# ---------------------------------------------------------------------------


def test_many_minions(cache):
    """Store and list 50 minion keys — exercises index packing."""
    for i in range(50):
        cache.store("keys", f"minion{i:03d}", {"state": "accepted", "pub": f"K{i}"})

    keys = cache.list("keys")
    assert len(keys) == 50
    for i in range(50):
        assert f"minion{i:03d}" in keys
        assert cache.fetch("keys", f"minion{i:03d}")["state"] == "accepted"
