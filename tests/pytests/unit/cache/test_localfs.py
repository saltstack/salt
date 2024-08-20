"""
Validate the functions in the localfs cache
"""

import errno
import shutil

import pytest

import salt.cache.localfs as localfs
import salt.payload
import salt.utils.files
from salt.exceptions import SaltCacheError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {localfs: {}}


@pytest.fixture
def tmp_cache_file(tmp_path):
    with patch.dict(localfs.__opts__, {"cachedir": tmp_path}):
        localfs.store(bank="bank", key="key", data="payload data", cachedir=tmp_path)
        yield tmp_path


def _create_tmp_cache_file(self, tmp_dir):
    """
    Helper function that creates a temporary cache file using localfs.store. This
    is to used to create DRY unit tests for the localfs cache.
    """
    self.addCleanup(shutil.rmtree, tmp_dir)
    with patch.dict(localfs.__opts__, {"cachedir": tmp_dir}):
        localfs.store(bank="bank", key="key", data="payload data", cachedir=tmp_dir)


# 'store' function tests: 5


def test_handled_exception_cache_dir():
    """
    Tests that a SaltCacheError is raised when the base directory doesn't exist and
    cannot be created.
    """
    with patch("os.makedirs", MagicMock(side_effect=OSError(errno.EEXIST, ""))):
        with patch("tempfile.mkstemp", MagicMock(side_effect=Exception)):
            with pytest.raises(Exception):
                localfs.store(bank="", key="", data="", cachedir="")


def test_unhandled_exception_cache_dir():
    """
    Tests that a SaltCacheError is raised when the base directory doesn't exist and
    cannot be created.
    """
    with patch("os.makedirs", MagicMock(side_effect=OSError(1, ""))):
        with pytest.raises(SaltCacheError):
            localfs.store(bank="", key="", data="", cachedir="")


def test_store_close_mkstemp_file_handle():
    """
    Tests that the file descriptor that is opened by os.open during the mkstemp call
    in localfs.store is closed before calling salt.utils.files.fopen on the filename.

    This test mocks the call to mkstemp, but forces an OSError to be raised when the
    close() function is called on a file descriptor that doesn't exist.
    """
    with patch("os.makedirs", MagicMock(side_effect=OSError(errno.EEXIST, ""))):
        with patch("tempfile.mkstemp", MagicMock(return_value=(12345, "foo"))):
            with pytest.raises(OSError):
                localfs.store(bank="", key="", data="", cachedir="")


def test_store_error_writing_cache():
    """
    Tests that a SaltCacheError is raised when there is a problem writing to the
    cache file.
    """
    with patch("os.makedirs", MagicMock(side_effect=OSError(errno.EEXIST, ""))):
        with patch("tempfile.mkstemp", MagicMock(return_value=("one", "two"))):
            with patch("os.close", MagicMock(return_value=None)):
                with patch("salt.utils.files.fopen", MagicMock(side_effect=IOError)):
                    with pytest.raises(SaltCacheError):
                        localfs.store(bank="", key="", data="", cachedir="")


def test_store_success(tmp_cache_file):
    """
    Tests that the store function writes the data to the serializer for storage.
    """
    # Read in the contents of the key.p file and assert "payload data" was written
    with salt.utils.files.fopen(str(tmp_cache_file / "bank" / "key.p"), "rb") as fh_:
        for line in fh_:
            assert b"payload data" in line


# 'fetch' function tests: 3


def test_fetch_return_when_cache_file_does_not_exist():
    """
    Tests that the fetch function returns an empty dict when the cache key file
    doesn't exist.
    """
    with patch("os.path.isfile", MagicMock(return_value=False)):
        assert localfs.fetch(bank="", key="", cachedir="") == {}


def test_fetch_error_reading_cache():
    """
    Tests that a SaltCacheError is raised when there is a problem reading the cache
    file.
    """
    with patch("os.path.isfile", MagicMock(return_value=True)):
        with patch("salt.utils.files.fopen", MagicMock(side_effect=IOError)):
            with pytest.raises(SaltCacheError):
                localfs.fetch(bank="", key="", cachedir="")


def test_fetch_success(tmp_cache_file):
    """
    Tests that the fetch function is able to read the cache file and return its data.
    """
    assert "payload data" in localfs.fetch(
        bank="bank", key="key", cachedir=tmp_cache_file
    )


# # 'updated' function tests: 3


def test_updated_return_when_cache_file_does_not_exist():
    """
    Tests that the updated function returns None when the cache key file doesn't
    exist.
    """
    with patch("os.path.isfile", MagicMock(return_value=False)):
        assert localfs.updated(bank="", key="", cachedir="") is None


def test_updated_error_when_reading_mtime():
    """
    Tests that a SaltCacheError is raised when there is a problem reading the mtime
    of the cache file.
    """
    with patch("os.path.isfile", MagicMock(return_value=True)):
        with patch("os.path.getmtime", MagicMock(side_effect=IOError)):
            with pytest.raises(SaltCacheError):
                localfs.fetch(bank="", key="", cachedir="")


def test_updated_success(tmp_cache_file):
    """
    Test that the updated function returns the modification time of the cache file
    """
    with patch(
        "os.path.join", MagicMock(return_value=str(tmp_cache_file / "bank" / "key.p"))
    ):
        assert isinstance(
            localfs.updated(bank="bank", key="key", cachedir=tmp_cache_file), int
        )


# # 'flush' function tests: 4


def test_flush_key_is_none_and_no_target_dir():
    """
    Tests that the flush function returns False when no key is passed in and the
    target directory doesn't exist.
    """
    with patch("os.path.isdir", MagicMock(return_value=False)):
        assert localfs.flush(bank="", key=None, cachedir="") is False


def test_flush_key_provided_and_no_key_file_false():
    """
    Tests that the flush function returns False when a key file is provided but
    the target key file doesn't exist in the cache bank.
    """
    with patch("os.path.isfile", MagicMock(return_value=False)):
        assert localfs.flush(bank="", key="key", cachedir="") is False


def test_flush_success(tmp_cache_file):
    """
    Tests that the flush function returns True when a key file is provided and
    the target key exists in the cache bank.
    """
    with patch("os.path.isfile", MagicMock(return_value=True)):
        assert localfs.flush(bank="bank", key="key", cachedir=tmp_cache_file) is True


def test_flush_error_raised():
    """
    Tests that a SaltCacheError is raised when there is a problem removing the
    key file from the cache bank
    """
    with patch("os.path.isfile", MagicMock(return_value=True)):
        with patch("os.remove", MagicMock(side_effect=OSError)):
            with pytest.raises(SaltCacheError):
                localfs.flush(bank="", key="key", cachedir="/var/cache/salt")


# # 'list' function tests: 3


def test_list_no_base_dir():
    """
    Tests that the ls function returns an empty list if the bank directory
    doesn't exist.
    """
    with patch("os.path.isdir", MagicMock(return_value=False)):
        assert localfs.list_(bank="", cachedir="") == []


def test_list_error_raised_no_bank_directory_access():
    """
    Tests that a SaltCacheError is raised when there is a problem accessing the
    cache bank directory.
    """
    with patch("os.path.isdir", MagicMock(return_value=True)):
        with patch("os.listdir", MagicMock(side_effect=OSError)):
            with pytest.raises(SaltCacheError):
                localfs.list_(bank="", cachedir="")


def test_list_success(tmp_cache_file):
    """
    Tests the return of the ls function containing bank entries.
    """
    assert localfs.list_(bank="bank", cachedir=tmp_cache_file) == ["key"]


# # 'contains' function tests: 1


def test_contains(tmp_cache_file):
    """
    Test the return of the contains function when key=None and when a key
    is provided.
    """
    assert localfs.contains(bank="bank", key=None, cachedir=tmp_cache_file) is True
    assert localfs.contains(bank="bank", key="key", cachedir=tmp_cache_file) is True


def test_mix_of_utf8_and_non_utf8_can_be_round_tripped(tmp_cache_file):
    data = {
        # Any unicode, which ideally is invalid ascii.
        "unicode": "áéí",
        # Any bytes so long as they're not valid utf-8
        "bytes": b"\xfe\x99\x00\xff",
    }
    bank = "bank"
    key = "key"

    localfs.store(bank, key, data, tmp_cache_file)
    actual = localfs.fetch(bank, key, tmp_cache_file)

    assert data == actual
