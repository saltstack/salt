"""
Unit tests for the Default Job Cache (local_cache).
"""

import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import pytest

import salt.payload
import salt.returners.local_cache as local_cache
import salt.utils.files
import salt.utils.jid
import salt.utils.job
import salt.utils.platform
from tests.support.mock import patch

log = logging.getLogger(__name__)


def _concurrent_save_and_read(args):
    """
    Writes to job cache then immediately reads back to verify no corruption.
    """
    jid, clear_load, opts = args
    with patch.object(local_cache, "__opts__", opts, create=True):
        local_cache.save_load(jid, clear_load)
        result = local_cache.get_load(jid)
        if result is None or "jid" not in result:
            raise AssertionError(f"get_load failed: {result}")
    return True


@pytest.fixture
def configure_loader_modules(tmp_cache_dir):
    return {
        local_cache: {
            "__opts__": {
                "cachedir": str(tmp_cache_dir),
                "keep_jobs_seconds": 0.0000000010,
            }
        }
    }


@pytest.fixture
def tmp_cache_dir(tmp_path):
    return tmp_path / "cache_dir"


@pytest.fixture
def jobs_dir(tmp_cache_dir):
    return tmp_cache_dir / "jobs"


@pytest.fixture
def jid_dir(jobs_dir):
    return (
        jobs_dir
        / "31"
        / "c56eed380a4e899ae12bc42563cfdfc53066fb4a6b53e2378a08ac49064539"
    )


@pytest.fixture
def pki_dir(tmp_path):
    dirname = tmp_path / "pki_dir"
    dirname.mkdir(parents=True, exist_ok=True)
    (dirname / "minion").touch()
    return dirname


@pytest.fixture
def job_cache_dir_files(jid_dir):
    return [str(jid_dir / "jid"), str(jid_dir / "minion" / "return.p")]


def _check_dir_files(msg, contents, status="None"):
    """
    helper method to ensure files or dirs
    are either present or removed
    """
    for content in contents:
        log.debug("CONTENT %s", content)
        if status == "present":
            check_job_dir = os.path.exists(content)
        elif status == "removed":
            if os.path.exists(content):
                check_job_dir = False
            else:
                check_job_dir = True
        assert check_job_dir, msg + content


@pytest.fixture
def add_job(tmp_cache_dir, job_cache_dir_files, pki_dir, tmp_path):
    def _add_job():
        """
        helper method to add job.
        """
        # add the job.
        opts = {
            "cachedir": str(tmp_cache_dir),
            "master_job_cache": "local_cache",
            "pki_dir": str(pki_dir),
            "conf_file": str(tmp_path / "conf"),
            "job_cache": True,
            "keys.cache_driver": "localfs_key",
        }
        load = {
            "fun_args": [],
            "jid": "20160603132323715452",
            "return": True,
            "retcode": 0,
            "success": True,
            "cmd": "_return",
            "fun": "test.ping",
            "id": "minion",
        }

        add_job = salt.utils.job.store_job(opts, load)
        assert add_job is None
        _check_dir_files(
            "Dir/file does not exist: ", job_cache_dir_files, status="present"
        )

    return _add_job


@pytest.mark.slow_test
def test_clean_old_jobs(add_job, job_cache_dir_files):
    """
    test to ensure jobs are removed from job cache
    """
    add_job()

    if salt.utils.platform.is_windows():
        time.sleep(0.01)

    # remove job
    assert local_cache.clean_old_jobs() is None

    _check_dir_files(
        "job cache was not removed: ", job_cache_dir_files, status="removed"
    )


@pytest.mark.slow_test
def test_not_clean_new_jobs(add_job, job_cache_dir_files):
    """
    test to ensure jobs are not removed when
    jobs dir is new
    """
    add_job()

    with patch.dict(local_cache.__opts__, {"keep_jobs_seconds": 86400}):
        assert local_cache.clean_old_jobs() is None

        _check_dir_files(
            "job cache was removed: ", job_cache_dir_files, status="present"
        )


@pytest.mark.slow_test
def test_override_clean_jobs(add_job, job_cache_dir_files):
    """
    test to ensure keep_jobs_seconds overrides keep_jobs if set
    """
    add_job()
    time.sleep(1.5)

    with patch.dict(local_cache.__opts__, {"keep_jobs_seconds": 1, "keep_jobs": 4}):
        assert local_cache.clean_old_jobs() is None

        _check_dir_files(
            "job cache was removed: ", job_cache_dir_files, status="removed"
        )


@pytest.mark.slow_test
def test_override_clean_jobs_seconds(add_job, job_cache_dir_files):
    """
    test to ensure keep_jobs still works as long as keep_jobs_seconds is set to default
    """
    add_job()

    with patch.dict(local_cache.__opts__, {"keep_jobs_seconds": 86400, "keep_jobs": 1}):
        assert local_cache.clean_old_jobs() is None

        _check_dir_files(
            "job cache was not removed: ", job_cache_dir_files, status="present"
        )


@pytest.mark.slow_test
def test_empty_jid_dir(jobs_dir):
    """
    test to ensure removal of empty jid dir
    """
    # add empty jid dir
    empty_jid_dir = []
    new_jid_dir = jobs_dir / "z0"
    new_jid_dir.mkdir(parents=True, exist_ok=True)
    new_jid_dir = str(new_jid_dir)
    empty_jid_dir.append(new_jid_dir)

    # This needed due to a race condition in Windows
    # `os.makedirs` hasn't released the handle before
    # `local_cache.clean_old_jobs` tries to delete the new_jid_dir
    if salt.utils.platform.is_windows():
        import time

        lock_dir = new_jid_dir + ".lckchk"
        tries = 0
        while True:
            tries += 1
            if tries > 10:
                break
            # Rename the directory and name it back
            # If it fails, the directory handle is not released, try again
            # If it succeeds, break and continue test
            try:
                os.rename(new_jid_dir, lock_dir)
                time.sleep(1)
                os.rename(lock_dir, new_jid_dir)
                break
            except OSError:  # pylint: disable=E0602
                continue

    # check dir exists
    _check_dir_files("new_jid_dir was not created", empty_jid_dir, status="present")

    # remove job
    assert local_cache.clean_old_jobs() is None

    # check jid dir is removed
    _check_dir_files("new_jid_dir was not removed", empty_jid_dir, status="removed")


def test_save_load_concurrent_writes(tmp_cache_dir):
    """
    Test that save_load can handle concurrent writes without failing.
    This tests the scenario when multiple Salt Syndic masters are writing
    to the same .load.p file simultaneously on return.
    """
    jid = "20160603132323715452"
    clear_load = {
        "fun": "test.ping",
        "jid": jid,
        "tgt": "*",
        "tgt_type": "glob",
        "user": "root",
    }

    opts = {
        "cachedir": str(tmp_cache_dir),
        "hash_type": "sha256",
        "pki_dir": str(tmp_cache_dir / "pki"),
        "key_cache": False,
        "keys.cache_driver": "localfs_key",
    }

    num_procs = 15
    args = [(jid, clear_load, opts) for _ in range(num_procs)]

    with ProcessPoolExecutor(max_workers=num_procs) as executor:
        futures = [executor.submit(_concurrent_save_and_read, arg) for arg in args]
        for future in as_completed(futures):
            future.result()


def test_get_load_minions_data_invalid_no_exception(tmp_cache_dir, caplog):
    """
    Test that get_load handles invalid minions data gracefully without raising exception.
    """
    jid = "20160603132323715452"

    with patch.dict(
        local_cache.__opts__, {"cachedir": str(tmp_cache_dir), "hash_type": "sha256"}
    ):
        jid_dir = salt.utils.jid.jid_dir(
            jid, os.path.join(str(tmp_cache_dir), "jobs"), "sha256"
        )
        os.makedirs(jid_dir, exist_ok=True)

        load_file = os.path.join(jid_dir, ".load.p")
        test_load = {"jid": jid, "fun": "test.ping"}
        with salt.utils.files.fopen(load_file, "wb") as f:
            salt.payload.dump(test_load, f)

        # Create minions file with invalid data
        minions_file = os.path.join(jid_dir, ".minions.p")
        invalid_minions_data = 1234
        with salt.utils.files.fopen(minions_file, "wb") as f:
            salt.payload.dump(invalid_minions_data, f)

        with caplog.at_level(logging.WARNING):
            result = local_cache.get_load(jid)

        assert result is not None
        assert result["jid"] == jid
        assert result["fun"] == "test.ping"
        assert "Minions" not in result
        assert any(
            "contains invalid minion data" in record.message
            for record in caplog.records
        )
