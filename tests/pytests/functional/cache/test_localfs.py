import logging
import shutil
from pathlib import Path

import pytest

import salt.cache
import salt.loader
from tests.pytests.functional.cache.helpers import run_common_cache_tests

log = logging.getLogger(__name__)


@pytest.fixture
def cache(minion_opts):
    opts = minion_opts.copy()
    opts["cache"] = "localfs"
    cache = salt.cache.factory(opts)
    try:
        yield cache
    finally:
        shutil.rmtree(opts["cachedir"], ignore_errors=True)


def test_caching(subtests, cache):
    run_common_cache_tests(subtests, cache)


def test_store_is_constrained_to_cachedir(cache, tmp_path):
    cache.store(str(tmp_path), "yikes", "wat")
    assert not (tmp_path / "yikes.p").exists()
    assert (Path(cache.cachedir) / str(tmp_path)[1:]).exists()


@pytest.mark.parametrize(
    "full_path,in_key", ((False, False), (False, True), (True, False))
)
def test_fetch_is_constrained_to_cachedir(cache, tmp_path, full_path, in_key):
    fake_data = b"\xa1a"
    if full_path:
        cbank = f"{tmp_path}/yikes"
        ckey = "foo"
        data = {"foo": "wat"}
        fake_data = b"\x81\xa3foo\xa1a"
    elif in_key:
        cbank = "/"
        ckey = f"{tmp_path}/yikes"
        data = "wat"
    else:
        cbank = str(tmp_path)
        ckey = "yikes"
        data = "wat"
    (tmp_path / "yikes.p").write_bytes(fake_data)
    cache.store(str(tmp_path)[1:], "yikes", data)
    res = cache.fetch(cbank, ckey)
    assert res == "wat"


def test_updated_is_constrained_to_cachedir(cache, tmp_path):
    (tmp_path / "yikes.p").touch()
    assert not cache.updated(str(tmp_path), "yikes")


@pytest.mark.parametrize("key", (None, "yikes"))
def test_flush_is_constrained_to_cachedir(cache, tmp_path, key):
    tgt = tmp_path
    if key is not None:
        tgt = tmp_path / f"{key}.p"
        tgt.touch()
    cache.flush(str(tmp_path), key)
    assert tgt.exists()


def test_list_is_constrained_to_cachedir(cache, tmp_path):
    (tmp_path / "yikes").touch()
    res = cache.list(str(tmp_path))
    assert "yikes" not in res


@pytest.mark.parametrize("key", (None, "yikes"))
def test_contains_is_constrained_to_cachedir(cache, tmp_path, key):
    if key is not None:
        (tmp_path / f"{key}.p").touch()
    assert not cache.contains(str(tmp_path), key)


def test_clean_expired_keeps_unexpired_entries(cache):
    """
    clean_expired() must remove only entries whose ``_expires`` has passed and
    leave still-valid entries intact.

    Regression: the generic Cache.clean_expired() fallback used the driver's
    ``updated()`` (the file mtime) as the expiry. A file's mtime is always in
    the past, so ``mtime <= now`` was always true and every entry was purged on
    every sweep -- e.g. the master token-maintenance sweep wiped all still-valid
    eauth tokens, which broke long-running salt-api operations such as batch
    jobs (their mid-run find_job re-auth happened after the token was gone).
    """
    cache.store("clean_expired_test", "live", {"x": 1}, expires=3600)
    cache.store("clean_expired_test", "dead", {"x": 2}, expires=-10)

    cache.clean_expired("clean_expired_test")

    # The unexpired entry must survive (the regression).
    assert cache.fetch("clean_expired_test", "live") == {"x": 1}
    # The expired entry must actually be removed from the backing store.
    assert "dead" not in cache.list("clean_expired_test")
