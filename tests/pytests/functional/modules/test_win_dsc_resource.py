"""
Functional tests for the dsc_resource execution module.

These tests use the built-in ``File`` DSC resource from the
``PSDesiredStateConfiguration`` module, which is available on all supported
Windows versions with no external dependencies.
"""

import os

import pytest

import salt.utils.files

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
]

FILE_RESOURCE = "File"
FILE_MODULE = "PSDesiredStateConfiguration"


@pytest.fixture(scope="module")
def dsc_resource(modules):
    return modules.dsc_resource


@pytest.fixture
def temp_file_path(tmp_path):
    """
    Provide a temp file path that does not exist at the start of each test.
    Any file created at this path is removed after the test.
    """
    path = str(tmp_path / "salt_dsc_resource_test.txt")
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_get_returns_dict(dsc_resource, temp_file_path):
    """
    get() should return a dict with at least a DestinationPath key regardless
    of whether the file exists.
    """
    result = dsc_resource.get(
        FILE_RESOURCE,
        FILE_MODULE,
        {"DestinationPath": temp_file_path, "Ensure": "Present"},
    )
    assert isinstance(result, dict)
    assert "DestinationPath" in result


def test_test_returns_false_when_file_absent(dsc_resource, temp_file_path):
    """
    test() should return False when the file does not exist and Ensure=Present.
    """
    assert not os.path.exists(temp_file_path)
    result = dsc_resource.test(
        FILE_RESOURCE,
        FILE_MODULE,
        {"DestinationPath": temp_file_path, "Ensure": "Present"},
    )
    assert result is False


def test_test_returns_true_when_file_present(dsc_resource, temp_file_path):
    """
    test() should return True when the file exists and Ensure=Present.
    """
    with salt.utils.files.fopen(temp_file_path, "w") as fh:
        fh.write("salt test content")
    result = dsc_resource.test(
        FILE_RESOURCE,
        FILE_MODULE,
        {"DestinationPath": temp_file_path, "Ensure": "Present"},
    )
    assert result is True


@pytest.mark.destructive_test
def test_set_creates_file(dsc_resource, temp_file_path):
    """
    set() should create the file when Ensure=Present and the file is absent.
    """
    assert not os.path.exists(temp_file_path)
    result = dsc_resource.set(
        FILE_RESOURCE,
        FILE_MODULE,
        {
            "DestinationPath": temp_file_path,
            "Ensure": "Present",
            "Contents": "Hello from Salt",
        },
    )
    assert result is True
    assert os.path.exists(temp_file_path)


@pytest.mark.destructive_test
def test_set_removes_file(dsc_resource, temp_file_path):
    """
    set() should remove the file when Ensure=Absent and the file is present.
    """
    with salt.utils.files.fopen(temp_file_path, "w") as fh:
        fh.write("salt test content")
    assert os.path.exists(temp_file_path)

    result = dsc_resource.set(
        FILE_RESOURCE,
        FILE_MODULE,
        {"DestinationPath": temp_file_path, "Ensure": "Absent"},
    )
    assert result is True
    assert not os.path.exists(temp_file_path)
