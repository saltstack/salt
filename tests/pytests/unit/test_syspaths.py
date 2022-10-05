"""
tests.pytests.unit.test_syspaths
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for salt's syspaths module
"""
import pytest

import salt.syspaths
from tests.support.mock import patch


@pytest.mark.skip_unless_on_windows(reason="Test is only applicable to Windows.")
def test__get_windows_root_dir_expand_reg():
    return_value = {"success": True, "vdata": "%ProgramData%\\Salt Project\\Salt"}
    expected = "C:\\ProgramData\\Salt Project\\Salt"
    with patch(
        "salt.utils.win_reg.read_value", autospec=True, return_value=return_value
    ):
        result = salt.syspaths._get_windows_root_dir()

    assert expected == result


@pytest.mark.skip_unless_on_windows(reason="Test is only applicable to Windows.")
def test__get_windows_root_dir_no_expand_reg():
    return_value = {"success": True, "vdata": "C:\\ProgramData\\Salt Project\\Salt"}
    expected = "C:\\ProgramData\\Salt Project\\Salt"
    with patch(
        "salt.utils.win_reg.read_value", autospec=True, return_value=return_value
    ):
        result = salt.syspaths._get_windows_root_dir()

    assert expected == result


@pytest.mark.skip_unless_on_windows(reason="Test is only applicable to Windows.")
def test__get_windows_root_dir_no_reg_old_exists():
    return_value = {"success": False, "comment": "Not found"}
    expected = "C:\\salt"
    with patch(
        "salt.utils.win_reg.read_value", autospec=True, return_value=return_value
    ), patch("os.path.isdir", return_value=True):
        result = salt.syspaths._get_windows_root_dir()

    assert expected == result


@pytest.mark.skip_unless_on_windows(reason="Test is only applicable to Windows.")
def test__get_windows_root_dir_no_reg_default():
    return_value = {"success": False, "comment": "Not found"}
    expected = "C:\\ProgramData\\Salt Project\\Salt"
    with patch(
        "salt.utils.win_reg.read_value", autospec=True, return_value=return_value
    ), patch("os.path.isdir", return_value=False):
        result = salt.syspaths._get_windows_root_dir()

    assert expected == result
