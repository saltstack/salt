"""
Unit tests for the Default Job Cache (local_cache).
"""

import os
import time

import pytest

import salt.returners.local_cache as local_cache
import salt.utils.files
import salt.utils.jid
import salt.utils.job
import salt.utils.platform
from tests.support.mock import MagicMock, patch


@pytest.fixture
def tmp_cache_dir(tmp_path):
    return tmp_path / "cache_dir"


@pytest.fixture
def tmp_jid_dir(tmp_cache_dir):
    return tmp_cache_dir / "jobs"


@pytest.fixture
def configure_loader_modules(tmp_cache_dir):
    return {
        local_cache: {
            "__opts__": {
                "cachedir": str(tmp_cache_dir),
                "keep_jobs_seconds": 3600,
            },
        }
    }


@pytest.fixture
def make_tmp_jid_dirs(tmp_jid_dir):
    def _make_tmp_jid_dirs(create_files=True):
        """
        Helper function to set up temporary directories and files used for
        testing the clean_old_jobs function.

        This emulates salt.utils.jid.jid_dir() by creating this structure:

        RUNTIME_VARS.TMP_JID_DIR dir/
            random dir from tempfile.mkdtemp/
            'jid' directory/
                'jid' file

        Returns a temp_dir name and a jid_file_path. If create_files is False,
        the jid_file_path will be None.
        """
        # First, create the /tmp/salt_test_job_cache/jobs/ directory to hold jid dirs
        tmp_jid_dir.mkdir(parents=True, exist_ok=True)

        # Then create a JID temp file in "/tmp/salt_test_job_cache/"
        temp_dir = tmp_jid_dir / "tmp_dir"
        temp_dir.mkdir(parents=True, exist_ok=True)

        jid_file_path = None
        if create_files:
            dir_name = temp_dir / "jid"
            dir_name.mkdir(parents=True, exist_ok=True)
            jid_file_path = dir_name / "jid"
            jid_file_path.write_text("this is a jid file")
            jid_file_path = str(jid_file_path)

        return str(temp_dir), jid_file_path

    return _make_tmp_jid_dirs


def test_clean_old_jobs_no_jid_root():
    """
    Tests that the function returns None when no jid_root is found.
    """
    with patch("os.path.exists", MagicMock(return_value=False)):
        assert local_cache.clean_old_jobs() is None


def test_clean_old_jobs_empty_jid_dir_removed(make_tmp_jid_dirs, tmp_jid_dir):
    """
    Tests that an empty JID dir is removed when it is old enough to be deleted.
    """
    # Create temp job cache dir without files in it.
    jid_dir, jid_file = make_tmp_jid_dirs(create_files=False)

    # File timestamps on Windows aren't as precise. Let a little time pass
    if salt.utils.platform.is_windows():
        time.sleep(0.01)

    # Make sure there are no files in the directory before continuing
    assert jid_file is None

    # Call clean_old_jobs function, patching the keep_jobs_seconds value
    # with a very small value to force the call to clean the job.
    with patch.dict(local_cache.__opts__, {"keep_jobs_seconds": 0.00000001}):
        # Sleep on Windows because time.time is only precise to 3 decimal
        # points, and therefore subtracting the jid_ctime from time.time
        # will result in a negative number
        if salt.utils.platform.is_windows():
            time.sleep(0.25)
        local_cache.clean_old_jobs()

    # Assert that the JID dir was removed
    assert [] == os.listdir(tmp_jid_dir)


def test_clean_old_jobs_empty_jid_dir_remains(make_tmp_jid_dirs, tmp_jid_dir):
    """
    Tests that an empty JID dir is NOT removed because it was created within
    the keep_jobs_seconds time frame.
    """
    # Create temp job cache dir without files in it.
    jid_dir, jid_file = make_tmp_jid_dirs(create_files=False)

    # Make sure there are no files in the directory
    assert jid_file is None

    # Call clean_old_jobs function
    local_cache.clean_old_jobs()

    # Get the name of the JID directory that was created to test against
    if salt.utils.platform.is_windows():
        jid_dir_name = jid_dir.rpartition("\\")[2]
    else:
        jid_dir_name = jid_dir.rpartition("/")[2]

    # Assert the JID directory is still present to be cleaned after keep_jobs_seconds interval
    assert [jid_dir_name] == os.listdir(tmp_jid_dir)


def test_clean_old_jobs_jid_file_corrupted(make_tmp_jid_dirs, tmp_jid_dir):
    """
    Tests that the entire JID dir is removed when the jid_file is not a file.
    This scenario indicates a corrupted cache entry, so the entire dir is scrubbed.
    """
    # Create temp job cache dir and jid file
    jid_dir, jid_file = make_tmp_jid_dirs()

    # Make sure there is a jid file in a new job cache director
    jid_dir_name = jid_file.rpartition(os.sep)[2]
    assert jid_dir_name == "jid"

    # Even though we created a valid jid file in the _make_tmp_jid_dirs call to get
    # into the correct loop, we need to mock the 'os.path.isfile' check to force the
    # "corrupted file" check in the clean_old_jobs call.
    with patch("os.path.isfile", MagicMock(return_value=False)) as mock:
        local_cache.clean_old_jobs()

    # there should be only 1 dir in TMP_JID_DIR
    assert 1 == len(os.listdir(tmp_jid_dir))
    # top level dir should still be present
    assert os.path.exists(jid_dir) is True
    assert os.path.isdir(jid_dir) is True
    # while the 'jid' dir inside it should be gone
    assert os.path.exists(jid_dir_name) is False


def test_clean_old_jobs_jid_file_is_cleaned(make_tmp_jid_dirs, tmp_jid_dir):
    """
    Test that the entire JID dir is removed when a job is old enough to be removed.
    """
    # Create temp job cache dir and jid file
    jid_dir, jid_file = make_tmp_jid_dirs()

    # File timestamps on Windows aren't as precise. Let a little time pass
    if salt.utils.platform.is_windows():
        time.sleep(0.01)

    # Make sure there is a jid directory
    jid_dir_name = jid_file.rpartition(os.sep)[2]
    assert jid_dir_name == "jid"

    # Call clean_old_jobs function, patching the keep_jobs_seconds value with a
    # very small value to force the call to clean the job.
    with patch.dict(local_cache.__opts__, {"keep_jobs_seconds": 0.00000001}):
        # Sleep on Windows because time.time is only precise to 3 decimal
        # points, and therefore subtracting the jid_ctime from time.time
        # will result in a negative number
        if salt.utils.platform.is_windows():
            time.sleep(0.25)
        local_cache.clean_old_jobs()

    # there should be only 1 dir in TMP_JID_DIR
    assert 1 == len(os.listdir(tmp_jid_dir))
    # top level dir should still be present
    assert os.path.exists(jid_dir) is True
    assert os.path.isdir(jid_dir) is True
    # while the 'jid' dir inside it should be gone
    assert os.path.exists(jid_dir_name) is False
