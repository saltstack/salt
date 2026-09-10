import logging
import shutil
import time
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


def test_store_key_with_path_separator_does_not_leak_tmp_files_69741(cache):
    """
    Regression test for issue #69741.

    Since 3008.0 the pillar cache uses ``<minion_id>:<pillarenv>`` as its
    cache key. When ``pillarenv`` contains ``/`` (e.g. a
    hierarchical ``pillar_roots`` name like ``someenv/beta``) the key
    contains a path separator, so ``outfile`` in ``localfs.store()``
    lands in a subdirectory that did not exist yet. The atomic rename
    then failed with ``FileNotFoundError`` and the tmp file created by
    ``tempfile.mkstemp`` was left behind. Reporters saw millions of
    leaked ``tmp*`` files under ``/var/cache/salt/master/pillar/``.

    Storing a key that contains ``/`` must:
      * succeed without raising,
      * write the value to the expected nested path,
      * be readable back via ``fetch``,
      * and leave no ``tmp*`` files behind in the bank directory.
    """
    bank = "pillar"
    key = "minion.example:someenv/beta"

    cache.store(bank, key, {"hello": "world"})

    assert cache.fetch(bank, key) == {"hello": "world"}

    bank_dir = Path(cache.cachedir) / bank
    leftover = [
        entry.name
        for entry in bank_dir.iterdir()
        if entry.name.startswith("tmp") and entry.is_file()
    ]
    assert not leftover, (
        f"localfs.store() leaked tmp files into {bank_dir}: {leftover} "
        "(issue #69741)"
    )


def test_store_tmp_file_cleaned_up_on_write_failure_69741(cache, monkeypatch):
    """
    Regression test for issue #69741 (defensive).

    Even when the atomic rename fails for reasons unrelated to the key
    path (e.g. a lower-level ``OSError``), ``localfs.store()`` must not
    leave the ``tempfile.mkstemp`` tmp file behind. Prior to the fix,
    every failed store leaked one ``tmp*`` file into the bank
    directory; over time this produced millions of orphan files.
    """
    import salt.utils.atomicfile

    def _boom(src, dst):
        raise OSError(2, "boom", src)

    monkeypatch.setattr(salt.utils.atomicfile, "atomic_rename", _boom)
    # localfs.py binds ``salt.utils.atomicfile`` at import time via
    # ``salt.utils.atomicfile.atomic_rename``; patching the attribute on
    # the module object is sufficient because the lookup happens at call
    # time.

    bank = "pillar"
    key = "some-minion"

    from salt.exceptions import SaltCacheError

    with pytest.raises(SaltCacheError):
        cache.store(bank, key, {"hello": "world"})

    bank_dir = Path(cache.cachedir) / bank
    leftover = [
        entry.name
        for entry in bank_dir.iterdir()
        if entry.name.startswith("tmp") and entry.is_file()
    ]
    assert not leftover, (
        f"localfs.store() leaked tmp files into {bank_dir}: {leftover} "
        "(issue #69741)"
    )


def test_clean_expired_does_not_drop_unexpired_entries_69307(cache):
    """
    Regression test for issue #69307.

    ``Cache.clean_expired`` falls back to ``driver.updated()`` for backends
    (like ``localfs``) that don't expose their own ``clean_expired``. The
    fallback previously compared ``updated()`` (the file mtime, an epoch
    in the past) against ``time.time()`` and flushed every key whose
    mtime had passed -- i.e. every key on disk. That deleted freshly
    minted auth tokens within one master ``loop_interval`` (default 60s),
    regardless of the token's actual expiry.

    A freshly stored entry with a ``_expires`` envelope that points into
    the future, and a plain entry with no envelope at all, must both
    survive ``clean_expired``.
    """
    bank = "tokens"
    key_with_envelope = "tok-with-envelope"
    key_plain = "tok-plain"

    # Plain store: no expires kwarg -> no envelope.
    cache.store(bank, key_plain, {"name": "alice", "expire": time.time() + 12 * 3600})

    # Store with a far-future expires duration (12 hours).
    cache.store(
        bank,
        key_with_envelope,
        {"name": "bob", "expire": time.time() + 12 * 3600},
        expires=12 * 3600,
    )

    assert cache.contains(bank, key_plain)
    assert cache.contains(bank, key_with_envelope)

    cache.clean_expired(bank)

    assert cache.contains(bank, key_plain), (
        "Plain (non-enveloped) token was flushed by clean_expired even "
        "though it has no expiry information; the fallback must not "
        "treat file mtime as an absolute expiry epoch (issue #69307)."
    )
    assert cache.contains(bank, key_with_envelope), (
        "Token with future expiry was flushed by clean_expired " "(issue #69307)."
    )
