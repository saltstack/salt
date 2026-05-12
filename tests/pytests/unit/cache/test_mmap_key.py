"""
Unit tests for salt.cache.mmap_key — the mmap-native PKI key cache backend.
"""

import os

import pytest

import salt.cache.mmap_key as mmap_key
import salt.utils.files
from salt.exceptions import SaltCacheError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DEFAULT_OPTS = {
    "mmap_key_size": 200,
    "mmap_key_slot_size": 96,
    "mmap_key_id_size": 32,
    "pki_dir": "",
    "__role": "master",
    "cluster_id": None,
}


@pytest.fixture(autouse=True)
def _clean_caches():
    """Ensure module-level cache registry is empty between tests."""
    mmap_key._caches.clear()
    yield
    for c in list(mmap_key._caches.values()):
        try:
            c.close()
        except Exception:  # pylint: disable=broad-except
            pass
    mmap_key._caches.clear()


@pytest.fixture
def pki_dir(tmp_path):
    return str(tmp_path)


@pytest.fixture
def opts(pki_dir):
    o = dict(_DEFAULT_OPTS)
    o["pki_dir"] = pki_dir
    return o


@pytest.fixture
def module(opts, monkeypatch):
    """
    Return the mmap_key module wired with __opts__ pointing at tmp pki_dir.
    """
    monkeypatch.setattr(mmap_key, "__opts__", opts, raising=False)
    return mmap_key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_PUB = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A\n-----END PUBLIC KEY-----\n"


def _accepted(pub=_SAMPLE_PUB):
    return {"state": "accepted", "pub": pub}


def _pending(pub=_SAMPLE_PUB):
    return {"state": "pending", "pub": pub}


def _rejected(pub=_SAMPLE_PUB):
    return {"state": "rejected", "pub": pub}


# ---------------------------------------------------------------------------
# init_kwargs / get_storage_id
# ---------------------------------------------------------------------------


def test_init_kwargs_uses_pki_dir(module, pki_dir):
    result = module.init_kwargs({"pki_dir": pki_dir})
    assert result["cachedir"] == pki_dir


def test_get_storage_id(module, pki_dir):
    sid = module.get_storage_id({"cachedir": pki_dir})
    assert sid == ("mmap_key", pki_dir)


# ---------------------------------------------------------------------------
# keys bank: store / fetch roundtrip
# ---------------------------------------------------------------------------


def test_store_and_fetch_accepted(module, pki_dir):
    module.store("keys", "minion1", _accepted(), pki_dir)
    result = module.fetch("keys", "minion1", pki_dir)
    assert result == {"state": "accepted", "pub": _SAMPLE_PUB}


def test_store_and_fetch_pending(module, pki_dir):
    module.store("keys", "minion2", _pending(), pki_dir)
    result = module.fetch("keys", "minion2", pki_dir)
    assert result["state"] == "pending"


def test_store_and_fetch_rejected(module, pki_dir):
    module.store("keys", "minion3", _rejected(), pki_dir)
    result = module.fetch("keys", "minion3", pki_dir)
    assert result["state"] == "rejected"


def test_fetch_missing_key_returns_none(module, pki_dir):
    result = module.fetch("keys", "noexist", pki_dir)
    assert result is None


def test_store_overwrites_state(module, pki_dir):
    module.store("keys", "minion1", _pending(), pki_dir)
    module.store("keys", "minion1", _accepted(), pki_dir)
    result = module.fetch("keys", "minion1", pki_dir)
    assert result["state"] == "accepted"


def test_store_invalid_state_raises(module, pki_dir):
    with pytest.raises(SaltCacheError):
        module.store("keys", "m1", {"state": "unknown", "pub": "x"}, pki_dir)


def test_store_missing_pub_raises(module, pki_dir):
    with pytest.raises(SaltCacheError):
        module.store("keys", "m1", {"state": "accepted"}, pki_dir)


# ---------------------------------------------------------------------------
# denied_keys bank
# ---------------------------------------------------------------------------


def test_store_and_fetch_denied_key(module, pki_dir):
    module.store("denied_keys", "badminion", [_SAMPLE_PUB], pki_dir)
    result = module.fetch("denied_keys", "badminion", pki_dir)
    assert isinstance(result, list)
    assert result[0].strip() == _SAMPLE_PUB.strip()


def test_fetch_missing_denied_key_returns_empty(module, pki_dir):
    result = module.fetch("denied_keys", "noexist", pki_dir)
    assert result == {}


# ---------------------------------------------------------------------------
# master_keys bank
# ---------------------------------------------------------------------------


def test_store_and_fetch_master_key(module, pki_dir):
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA\n-----END RSA PRIVATE KEY-----\n"
    module.store("master_keys", "master.pem", pem, pki_dir)
    result = module.fetch("master_keys", "master.pem", pki_dir)
    assert "BEGIN RSA PRIVATE KEY" in result


def test_fetch_missing_master_key_returns_empty(module, pki_dir):
    result = module.fetch("master_keys", "nothere.pem", pki_dir)
    assert result == {}


# ---------------------------------------------------------------------------
# contains
# ---------------------------------------------------------------------------


def test_contains_existing_key(module, pki_dir):
    module.store("keys", "m1", _accepted(), pki_dir)
    assert module.contains("keys", "m1", pki_dir) is True


def test_contains_missing_key(module, pki_dir):
    assert module.contains("keys", "ghost", pki_dir) is False


def test_contains_bank_existence_check(module, pki_dir):
    # Before any write the index file doesn't exist
    assert module.contains("keys", None, pki_dir) is False
    module.store("keys", "m1", _accepted(), pki_dir)
    assert module.contains("keys", None, pki_dir) is True


# ---------------------------------------------------------------------------
# updated
# ---------------------------------------------------------------------------


def test_updated_returns_int_after_store(module, pki_dir):
    module.store("keys", "m1", _accepted(), pki_dir)
    ts = module.updated("keys", "m1", pki_dir)
    assert isinstance(ts, int)
    assert ts > 0


def test_updated_missing_key_returns_none(module, pki_dir):
    assert module.updated("keys", "ghost", pki_dir) is None


# ---------------------------------------------------------------------------
# list_
# ---------------------------------------------------------------------------


def test_list_returns_all_keys(module, pki_dir):
    for i in range(5):
        module.store("keys", f"minion{i}", _accepted(), pki_dir)
    keys = module.list_("keys", pki_dir)
    assert set(keys) == {f"minion{i}" for i in range(5)}


def test_list_empty_bank(module, pki_dir):
    assert module.list_("keys", pki_dir) == []


# ---------------------------------------------------------------------------
# flush_ (single key)
# ---------------------------------------------------------------------------


def test_flush_key_removes_entry(module, pki_dir):
    module.store("keys", "m1", _accepted(), pki_dir)
    module.flush_("keys", key="m1", cachedir=pki_dir)
    assert module.fetch("keys", "m1", pki_dir) is None


def test_flush_key_absent_is_falsy(module, pki_dir):
    result = module.flush_("keys", key="ghost", cachedir=pki_dir)
    assert not result


# ---------------------------------------------------------------------------
# flush_ (whole bank)
# ---------------------------------------------------------------------------


def test_flush_bank_removes_all_keys(module, pki_dir):
    for i in range(3):
        module.store("keys", f"m{i}", _accepted(), pki_dir)
    module.flush_("keys", key=None, cachedir=pki_dir)
    # After wipe the index file should be gone and list returns empty
    mmap_key._caches.clear()
    assert module.list_("keys", pki_dir) == []


# ---------------------------------------------------------------------------
# Multiple banks are independent
# ---------------------------------------------------------------------------


def test_separate_banks_dont_interfere(module, pki_dir):
    module.store("keys", "shared_id", _accepted(), pki_dir)
    module.store("denied_keys", "shared_id", [_SAMPLE_PUB], pki_dir)
    assert module.fetch("keys", "shared_id", pki_dir)["state"] == "accepted"
    denied = module.fetch("denied_keys", "shared_id", pki_dir)
    assert isinstance(denied, list)


# ---------------------------------------------------------------------------
# Unrecognised bank raises
# ---------------------------------------------------------------------------


def test_unknown_bank_store_raises(module, pki_dir):
    with pytest.raises(SaltCacheError):
        module.store("bad_bank", "k", {}, pki_dir)


def test_unknown_bank_fetch_raises(module, pki_dir):
    with pytest.raises(SaltCacheError):
        module.fetch("bad_bank", "k", pki_dir)


# ---------------------------------------------------------------------------
# minion_id validity enforcement
# ---------------------------------------------------------------------------


def test_store_invalid_minion_id_raises(module, pki_dir):
    with pytest.raises(SaltCacheError, match="not a valid minion_id"):
        module.store("keys", "foo/bar/..", _accepted(), pki_dir)


def test_fetch_invalid_minion_id_raises(module, pki_dir):
    with pytest.raises(SaltCacheError, match="not a valid minion_id"):
        module.fetch("keys", "../../etc/passwd", pki_dir)


def test_updated_invalid_minion_id_raises(module, pki_dir):
    with pytest.raises(SaltCacheError, match="not a valid minion_id"):
        module.updated("keys", "bad\\id", pki_dir)


def test_flush_invalid_minion_id_raises(module, pki_dir):
    with pytest.raises(SaltCacheError, match="not a valid minion_id"):
        module.flush_("keys", key="bad\x00id", cachedir=pki_dir)


def test_contains_invalid_minion_id_raises(module, pki_dir):
    with pytest.raises(SaltCacheError, match="not a valid minion_id"):
        module.contains("keys", "foo/bar", pki_dir)


def test_master_keys_not_validated(module, pki_dir):
    """master_keys bank does not enforce minion_id rules (file names like master.pem are OK)."""
    module.store("master_keys", "master.pem", "PEMDATA", pki_dir)
    result = module.fetch("master_keys", "master.pem", pki_dir)
    assert "PEMDATA" in result


# ---------------------------------------------------------------------------
# rebuild_from_localfs
# ---------------------------------------------------------------------------


def test_rebuild_from_localfs(module, pki_dir, opts):
    # Populate legacy pki layout
    for state_dir in ("minions", "minions_pre", "minions_rejected", "minions_denied"):
        os.makedirs(os.path.join(pki_dir, state_dir), exist_ok=True)

    for name in ("acc1", "acc2"):
        p = os.path.join(pki_dir, "minions", name)
        with salt.utils.files.fopen(p, "w") as f:
            f.write(_SAMPLE_PUB)

    p = os.path.join(pki_dir, "minions_pre", "pend1")
    with salt.utils.files.fopen(p, "w") as f:
        f.write(_SAMPLE_PUB)

    p = os.path.join(pki_dir, "minions_denied", "bad1")
    with salt.utils.files.fopen(p, "w") as f:
        f.write(_SAMPLE_PUB)

    opts["pki_dir"] = pki_dir
    counts = module.rebuild_from_localfs(opts)
    assert counts["accepted"] == 2
    assert counts["pending"] == 1
    assert counts["denied"] == 1

    assert module.fetch("keys", "acc1", pki_dir)["state"] == "accepted"
    assert module.fetch("keys", "pend1", pki_dir)["state"] == "pending"
    denied = module.fetch("denied_keys", "bad1", pki_dir)
    assert isinstance(denied, list)
