"""
Functional tests for the dsc_resource state module.

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
def dsc_resource(states):
    return states.dsc_resource


@pytest.fixture
def temp_file_path(tmp_path):
    """
    Provide a temp file path that does not exist at the start of each test.
    Any file created at this path is removed after the test.
    """
    path = str(tmp_path / "salt_dsc_state_test.txt")
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_managed_already_in_desired_state(dsc_resource, temp_file_path):
    """
    managed() should return result=True and no changes when the resource is
    already in the desired state (live mode).
    """
    with salt.utils.files.fopen(temp_file_path, "w") as fh:
        fh.write("salt test content")

    ret = dsc_resource.managed(
        name=FILE_RESOURCE,
        module_name=FILE_MODULE,
        properties={"DestinationPath": temp_file_path, "Ensure": "Present"},
    )
    assert ret.result is True
    assert ret.changes == {}
    assert "already in the desired state" in ret.comment


@pytest.mark.destructive_test
def test_managed_applies_changes(dsc_resource, temp_file_path):
    """
    managed() should return result=True and a populated changes dict when the
    resource is not in the desired state (live mode).
    """
    assert not os.path.exists(temp_file_path)

    ret = dsc_resource.managed(
        name=FILE_RESOURCE,
        module_name=FILE_MODULE,
        properties={
            "DestinationPath": temp_file_path,
            "Ensure": "Present",
            "Contents": "Hello from Salt",
        },
    )
    assert ret.result is True
    assert ret.changes != {}
    assert "ensure" in ret.changes.get("old", {})
    assert "ensure" in ret.changes.get("new", {})
    assert os.path.exists(temp_file_path)


def test_managed_test_mode_no_changes_needed(dsc_resource, temp_file_path):
    """
    managed() should return result=True and no changes when the resource is
    already in the desired state and test=True.
    """
    with salt.utils.files.fopen(temp_file_path, "w") as fh:
        fh.write("salt test content")

    ret = dsc_resource.managed(
        name=FILE_RESOURCE,
        module_name=FILE_MODULE,
        properties={"DestinationPath": temp_file_path, "Ensure": "Present"},
        test=True,
    )
    assert ret.result is True
    assert ret.changes == {}


@pytest.mark.destructive_test
def test_managed_idempotent(dsc_resource, temp_file_path):
    """
    managed() should apply changes on the first call and return no changes on
    a second call with the same arguments (idempotency).
    """
    assert not os.path.exists(temp_file_path)
    props = {
        "DestinationPath": temp_file_path,
        "Ensure": "Present",
        "Contents": "Hello from Salt",
    }

    first = dsc_resource.managed(
        name=FILE_RESOURCE, module_name=FILE_MODULE, properties=props
    )
    assert first.result is True
    assert first.changes != {}

    second = dsc_resource.managed(
        name=FILE_RESOURCE, module_name=FILE_MODULE, properties=props
    )
    assert second.result is True
    assert second.changes == {}
    assert "already in the desired state" in second.comment


@pytest.mark.destructive_test
def test_managed_test_mode_changes_needed(dsc_resource, temp_file_path):
    """
    managed() should return result=None and a populated changes dict when the
    resource is not in the desired state and test=True. No actual change should
    be made to the system.
    """
    assert not os.path.exists(temp_file_path)

    ret = dsc_resource.managed(
        name=FILE_RESOURCE,
        module_name=FILE_MODULE,
        properties={
            "DestinationPath": temp_file_path,
            "Ensure": "Present",
            "Contents": "Hello from Salt",
        },
        test=True,
    )
    assert ret.result is None
    assert ret.changes != {}
    assert "ensure" in ret.changes.get("old", {})
    assert "ensure" in ret.changes.get("new", {})
    assert not os.path.exists(temp_file_path)
