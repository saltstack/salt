"""
Test for the chocolatey module
"""


import os

import pytest

import salt.modules.chocolatey as chocolatey
import salt.utils
import salt.utils.platform
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skipif(
        not salt.utils.platform.is_windows(), reason="Not a Windows system"
    )
]


@pytest.fixture(scope="module")
def choco_path():
    return "C:\\path\\to\\chocolatey.exe"


@pytest.fixture(scope="module")
def choco_path_pd():
    return os.path.join(
        os.environ.get("ProgramData"), "Chocolatey", "bin", "chocolatey.exe"
    )


@pytest.fixture(scope="module")
def choco_path_sd():
    return os.path.join(
        os.environ.get("SystemDrive"), "Chocolatey", "bin", "chocolatey.bat"
    )


@pytest.fixture(scope="module")
def mock_false():
    return MagicMock(return_value=False)


@pytest.fixture(scope="module")
def mock_true():
    return MagicMock(return_value=True)


@pytest.fixture()
def configure_loader_modules():
    return {chocolatey: {"__context__": {}, "__salt__": {}}}


def test__clear_context(choco_path):
    """
    Tests _clear_context function
    """
    context = {
        "chocolatey._yes": ["--yes"],
        "chocolatey._path": choco_path,
        "chocolatey._version": "0.9.9",
    }
    with patch.dict(chocolatey.__context__, context):
        chocolatey._clear_context()
        # Did it clear all chocolatey items from __context__P?
        assert chocolatey.__context__ == {}


def test__yes_context():
    """
    Tests _yes function when it exists in __context__
    """
    with patch.dict(chocolatey.__context__, {"chocolatey._yes": ["--yes"]}):
        result = chocolatey._yes()
        expected = ["--yes"]
        # Did it return correctly
        assert result == expected
        # Did it populate __context__
        assert chocolatey.__context__["chocolatey._yes"] == expected


def test__yes_version_greater():
    """
    Test _yes when Chocolatey version is greater than 0.9.9
    """
    mock_version = MagicMock(return_value="10.0.0")
    with patch("salt.modules.chocolatey.chocolatey_version", mock_version):
        result = chocolatey._yes()
        expected = ["--yes"]
        # Did it return correctly
        assert result == expected
        # Did it populate __context__
        assert chocolatey.__context__["chocolatey._yes"] == expected


def test__yes_version_less_than():
    """
    Test _yes when Chocolatey version is less than 0.9.9
    """
    mock_version = MagicMock(return_value="0.9.0")
    with patch("salt.modules.chocolatey.chocolatey_version", mock_version):
        result = chocolatey._yes()
        expected = []
        # Did it return correctly
        assert result == expected
        # Did it populate __context__
        assert chocolatey.__context__["chocolatey._yes"] == expected


def test__find_chocolatey_context(choco_path):
    """
    Test _find_chocolatey when it exists in __context__
    """
    with patch.dict(chocolatey.__context__, {"chocolatey._path": choco_path}):
        result = chocolatey._find_chocolatey()
        expected = choco_path
        assert result == expected


def test__find_chocolatey_which(choco_path):
    """
    Test _find_chocolatey when found with `cmd.which`
    """
    mock_which = MagicMock(return_value=choco_path)
    with patch.dict(chocolatey.__salt__, {"cmd.which": mock_which}):
        result = chocolatey._find_chocolatey()
        expected = choco_path
        # Does it return the correct path
        assert result == expected
        # Does it populate __context__
        assert chocolatey.__context__["chocolatey._path"] == expected


def test__find_chocolatey_programdata(mock_false, mock_true, choco_path_pd):
    """
    Test _find_chocolatey when found in ProgramData
    """
    with patch.dict(chocolatey.__salt__, {"cmd.which": mock_false}), patch(
        "os.path.isfile", mock_true
    ):
        result = chocolatey._find_chocolatey()
        expected = choco_path_pd
        # Does it return the correct path
        assert result == expected
        # Does it populate __context__
        assert chocolatey.__context__["chocolatey._path"] == expected


def test__find_chocolatey_systemdrive(mock_false, choco_path_sd):
    """
    Test _find_chocolatey when found on SystemDrive (older versions)
    """
    with patch.dict(chocolatey.__salt__, {"cmd.which": mock_false}), patch(
        "os.path.isfile", MagicMock(side_effect=[False, True])
    ):
        result = chocolatey._find_chocolatey()
        expected = choco_path_sd
        # Does it return the correct path
        assert result == expected
        # Does it populate __context__
        assert chocolatey.__context__["chocolatey._path"] == expected


def test_version_check_remote_false():
    """
    Test version when remote is False
    """
    list_return_value = {"ack": ["3.1.1"]}
    with patch.object(chocolatey, "list_", return_value=list_return_value):
        expected = {"ack": ["3.1.1"]}
        result = chocolatey.version("ack", check_remote=False)
        assert result == expected


def test_version_check_remote_true():
    """
    Test version when remote is True
    """
    list_side_effect = [
        {"ack": ["3.1.1"]},
        {"ack": ["3.1.1"], "Wolfpack": ["3.0.17"], "blackbird": ["1.0.79.3"]},
    ]
    with patch.object(chocolatey, "list_", side_effect=list_side_effect):
        expected = {"ack": {"available": ["3.1.1"], "installed": ["3.1.1"]}}
        result = chocolatey.version("ack", check_remote=True)
        assert result == expected


def test_version_check_remote_true_not_available():
    """
    Test version when remote is True but remote version is unavailable
    """
    list_side_effect = [
        {"ack": ["3.1.1"]},
        {"Wolfpack": ["3.0.17"], "blackbird": ["1.0.79.3"]},
    ]
    with patch.object(chocolatey, "list_", side_effect=list_side_effect):
        expected = {"ack": {"installed": ["3.1.1"]}}
        result = chocolatey.version("ack", check_remote=True)
        assert result == expected


def test_add_source(choco_path):
    """
    Test add_source when remote is False
    """
    cmd_run_all_mock = MagicMock(return_value={"retcode": 0, "stdout": "data"})
    cmd_run_which_mock = MagicMock(return_value=choco_path)
    with patch.dict(
        chocolatey.__salt__,
        {"cmd.which": cmd_run_which_mock, "cmd.run_all": cmd_run_all_mock},
    ):
        expected_call = [
            choco_path,
            "sources",
            "add",
            "--name",
            "source_name",
            "--source",
            "source_location",
        ]

        result = chocolatey.add_source("source_name", "source_location")
        cmd_run_all_mock.assert_called_with(expected_call, python_shell=False)

        expected_call = [
            choco_path,
            "sources",
            "add",
            "--name",
            "source_name",
            "--source",
            "source_location",
            "--priority",
            "priority",
        ]

        result = chocolatey.add_source(
            "source_name", "source_location", priority="priority"
        )
        cmd_run_all_mock.assert_called_with(expected_call, python_shell=False)
