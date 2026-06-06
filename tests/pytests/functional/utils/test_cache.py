import logging
import os

import pytest

import salt.utils.cache
import salt.utils.files
import salt.utils.path
import salt.version

_DUMMY_FILES = (
    "data.txt",
    "foo.t2",
    "bar.t3",
    "nested/test",
    "nested/cache.txt",
    "n/n1/n2/n3/n4/n5",
)


def _make_dummy_files(tmp_path):
    for full_path in _DUMMY_FILES:
        full_path = salt.utils.path.join(tmp_path, full_path)
        path, _ = os.path.split(full_path)
        if not os.path.isdir(path):
            os.makedirs(path)
        with salt.utils.files.fopen(full_path, "w") as file:
            file.write("data")


def _dummy_files_exists(tmp_path):
    """
    True if all files exists
    False if all files are missing
    None if some files exists and others are missing
    """
    ret = None
    for full_path in _DUMMY_FILES:
        full_path = salt.utils.path.join(tmp_path, full_path)
        is_file = os.path.isfile(full_path)
        if ret is None:
            ret = is_file
        elif ret is not is_file:
            return None  # Some files are found and others are missing
    return ret


def test_verify_cache_version_bad_path():
    with pytest.raises(ValueError):
        # cache version should fail if given bad file python
        salt.utils.cache.verify_cache_version("\0/bad/path")


def test_verify_cache_version(tmp_path):
    # cache version should make dir if it does not exist
    tmp_path = str(salt.utils.path.join(str(tmp_path), "work", "salt"))
    cache_version = salt.utils.path.join(tmp_path, "cache_version")

    # check that cache clears when no cache_version is present
    _make_dummy_files(tmp_path)
    assert salt.utils.cache.verify_cache_version(tmp_path) is False
    assert _dummy_files_exists(tmp_path) is False

    # check that cache_version has correct salt version
    with salt.utils.files.fopen(cache_version, "r") as file:
        assert "\n".join(file.readlines()) == salt.version.__version__

    # check that cache does not get clear when check is called multiple times
    _make_dummy_files(tmp_path)
    for _ in range(3):
        assert salt.utils.cache.verify_cache_version(tmp_path) is True
        assert _dummy_files_exists(tmp_path) is True

    # check that cache clears when a different version is present
    with salt.utils.files.fopen(cache_version, "w") as file:
        file.write("-1")
    assert salt.utils.cache.verify_cache_version(tmp_path) is False
    assert _dummy_files_exists(tmp_path) is False

    # check that cache does not get clear when check is called multiple times
    _make_dummy_files(tmp_path)
    for _ in range(3):
        assert salt.utils.cache.verify_cache_version(tmp_path) is True
        assert _dummy_files_exists(tmp_path) is True


def test_verify_cache_version_mismatch_logged_at_debug(tmp_path, caplog):
    """
    Clearing a stale cache because of a version mismatch is a routine
    side effect of upgrades and ephemeral cache directories; it must be
    logged at DEBUG, not WARNING (see issue #69106).
    """
    cache_path = str(salt.utils.path.join(str(tmp_path), "work", "salt"))
    cache_version = salt.utils.path.join(cache_path, "cache_version")

    # Prime the cache directory with a stale version so the next call
    # exercises the "mismatch -> clear" branch.
    os.makedirs(cache_path)
    with salt.utils.files.fopen(cache_version, "w") as file:
        file.write("-1")

    with caplog.at_level(logging.DEBUG, logger="salt.utils.cache"):
        assert salt.utils.cache.verify_cache_version(cache_path) is False

    mismatch_records = [
        record
        for record in caplog.records
        if "Cache version mismatch clearing" in record.getMessage()
    ]
    assert mismatch_records, "expected a 'Cache version mismatch clearing' log record"
    for record in mismatch_records:
        assert record.levelno == logging.DEBUG, (
            f"'Cache version mismatch clearing' was logged at "
            f"{record.levelname}, expected DEBUG"
        )
