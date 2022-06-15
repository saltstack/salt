import os

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


def test_rmdir_success_with_default_options(file, single_empty_dir):
    assert file.rmdir(single_empty_dir) is True
    assert not os.path.isdir(single_empty_dir)
    assert not os.path.exists(single_empty_dir)


def test_rmdir_failure_with_default_options(file, single_dir_with_file):
    assert file.rmdir(single_dir_with_file) == "Directory not empty"
    assert os.path.isdir(single_dir_with_file)
