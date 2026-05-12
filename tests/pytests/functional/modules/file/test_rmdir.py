import os
import time

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def file(modules):
    return modules.file


@pytest.fixture(scope="function")
def single_empty_dir(tmp_path):
    yield str(tmp_path)


@pytest.fixture(scope="function")
def single_dir_with_file(tmp_path):
    file = tmp_path / "stuff.txt"
    file.write_text("things")
    yield str(tmp_path)


@pytest.fixture(scope="function")
def nested_empty_dirs(tmp_path):
    num_root = 2
    num_mid = 4
    num_last = 2
    for root in range(1, num_root + 1):
        for mid in range(1, num_mid + 1):
            for last in range(1, num_last + 1):
                nest = tmp_path / f"root{root}" / f"mid{mid}" / f"last{last}"
                nest.mkdir(parents=True, exist_ok=True)
                if last % 2:
                    now = time.time()
                    old = now - (2 * 86400)
                    os.utime(str(nest), (old, old))
    yield str(tmp_path)


@pytest.fixture(scope="function")
def nested_dirs_with_files(tmp_path):
    num_root = 2
    num_mid = 4
    num_last = 2
    for root in range(1, num_root + 1):
        for mid in range(1, num_mid + 1):
            for last in range(1, num_last + 1):
                nest = tmp_path / f"root{root}" / f"mid{mid}" / f"last{last}"
                nest.mkdir(parents=True, exist_ok=True)
                if last % 2:
                    last_file = nest / "stuff.txt"
                    last_file.write_text("things")
    yield str(tmp_path)


def test_rmdir_success_with_default_options(file, single_empty_dir):
    assert file.rmdir(single_empty_dir) is True
    assert not os.path.isdir(single_empty_dir)
    assert not os.path.exists(single_empty_dir)


def test_rmdir_failure_with_default_options(file, single_dir_with_file):
    assert file.rmdir(single_dir_with_file) is False
    assert os.path.isdir(single_dir_with_file)


def test_rmdir_single_dir_success_with_recurse(file, single_empty_dir):
    assert file.rmdir(single_empty_dir, recurse=True) is True
    assert not os.path.isdir(single_empty_dir)
    assert not os.path.exists(single_empty_dir)


def test_rmdir_single_dir_failure_with_recurse(file, single_dir_with_file):
    assert file.rmdir(single_dir_with_file, recurse=True) is False
    assert os.path.isdir(single_dir_with_file)


def test_rmdir_nested_empty_dirs_failure_with_default_options(file, nested_empty_dirs):
    assert file.rmdir(nested_empty_dirs) is False
    assert os.path.isdir(nested_empty_dirs)


def test_rmdir_nested_empty_dirs_success_with_recurse(file, nested_empty_dirs):
    assert file.rmdir(nested_empty_dirs, recurse=True) is True
    assert not os.path.isdir(nested_empty_dirs)
    assert not os.path.exists(nested_empty_dirs)


def test_rmdir_nested_dirs_with_files_failure_with_recurse(
    file, nested_dirs_with_files
):
    assert file.rmdir(nested_dirs_with_files, recurse=True) is False
    assert os.path.isdir(nested_dirs_with_files)


def test_rmdir_verbose_nested_dirs_with_files_failure_with_recurse(
    file, nested_dirs_with_files
):
    ret = file.rmdir(nested_dirs_with_files, recurse=True, verbose=True)
    assert ret["result"] is False
    assert len(ret["deleted"]) == 8
    assert len(ret["errors"]) == 19
    assert os.path.isdir(nested_dirs_with_files)


def test_rmdir_verbose_success(file, single_empty_dir):
    ret = file.rmdir(single_empty_dir, verbose=True)
    assert ret["result"] is True
    assert ret["deleted"][0] == single_empty_dir
    assert not ret["errors"]
    assert not os.path.isdir(single_empty_dir)
    assert not os.path.exists(single_empty_dir)


def test_rmdir_verbose_failure(file, single_dir_with_file):
    ret = file.rmdir(single_dir_with_file, verbose=True)
    assert ret["result"] is False
    assert not ret["deleted"]
    assert ret["errors"][0][0] == single_dir_with_file
    assert os.path.isdir(single_dir_with_file)


def test_rmdir_nested_empty_dirs_recurse_older_than(file, nested_empty_dirs):
    ret = file.rmdir(nested_empty_dirs, recurse=True, verbose=True, older_than=1)
    assert ret["result"] is True
    assert len(ret["deleted"]) == 8
    assert len(ret["errors"]) == 0
    assert os.path.isdir(nested_empty_dirs)


def test_rmdir_nested_empty_dirs_recurse_not_older_than(file, nested_empty_dirs):
    ret = file.rmdir(nested_empty_dirs, recurse=True, verbose=True, older_than=3)
    assert ret["result"] is True
    assert len(ret["deleted"]) == 0
    assert len(ret["errors"]) == 0
    assert os.path.isdir(nested_empty_dirs)
