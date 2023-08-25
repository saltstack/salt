import os

import salt.utils.cache
import salt.utils.files
import salt.utils.path

_ROOT_DIR = (
    "data.txt",
    "foo.t2",
    "bar.t3",
    "nested/test",
    "nested/cache.txt",
    "n/n1/n2/n3/n4/n5",
)


def _make_dummy_files(tmp_path):
    for full_path in _ROOT_DIR:
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
    for full_path in _ROOT_DIR:
        full_path = salt.utils.path.join(tmp_path, full_path)
        path, _ = os.path.split(full_path)
        is_file = os.path.isdir(path) and os.path.isfile(full_path)
        if ret is None:
            ret = is_file
        elif ret is not is_file:
            return None  # Some files are found and others are missing
    return ret


def test_verify_cache_version(tmp_path):
    tmp_path = str(tmp_path)
    cache_version = salt.utils.path.join(tmp_path, "cache_version")

    # check that cache clears when no cache_version is present
    _make_dummy_files(tmp_path)
    assert salt.utils.cache.verify_cache_version(tmp_path) is False
    assert _dummy_files_exists(tmp_path) is False

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
