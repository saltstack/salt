import pytest

import salt.utils.win_pwsh as win_pwsh
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


def test_run_dict():
    """
    Tests the run_dict function
    """
    result = win_pwsh.run_dict("Get-Item C:\\Windows")
    assert result["Name"] == "Windows"
    assert result["FullName"] == "C:\\Windows"


def test_run_dict_json_string():
    """
    Tests the run_dict function with json string
    """
    ret = {
        "pid": 1,
        "retcode": 0,
        "stderr": "",
        "stdout": '[{"HotFixID": "KB123456"}, {"HotFixID": "KB123457"}]',
    }
    mock_all = MagicMock(return_value=ret)
    with patch("salt.modules.cmdmod.run_all", mock_all):
        result = win_pwsh.run_dict("Junk-Command")
        assert result == [{"HotFixID": "KB123456"}, {"HotFixID": "KB123457"}]


def test_run_dict_empty_return():
    """
    Tests the run_dict function with json string
    """
    ret = {
        "pid": 1,
        "retcode": 0,
        "stderr": "",
        "stdout": "",
    }
    mock_all = MagicMock(return_value=ret)
    with patch("salt.modules.cmdmod.run_all", mock_all):
        result = win_pwsh.run_dict("Junk-Command")
        assert result == {}


def test_run_dict_stderr():
    ret = {
        "pid": 1,
        "retcode": 1,
        "stderr": "This is an error",
        "stdout": "",
    }
    mock_all = MagicMock(return_value=ret)
    with patch("salt.modules.cmdmod.run_all", mock_all):
        with pytest.raises(CommandExecutionError) as exc_info:
            win_pwsh.run_dict("Junk-Command")
        assert "This is an error" in exc_info.value.message


def test_run_dict_missing_retcode():
    ret = {
        "pid": 1,
        "stderr": "",
        "stdout": "",
    }
    mock_all = MagicMock(return_value=ret)
    with patch("salt.modules.cmdmod.run_all", mock_all):
        with pytest.raises(CommandExecutionError) as exc_info:
            win_pwsh.run_dict("Junk-Command")
        assert "Issue executing PowerShell" in exc_info.value.message


def test_run_dict_retcode_not_zero():
    ret = {
        "pid": 1,
        "retcode": 1,
        "stderr": "",
        "stdout": "",
    }
    mock_all = MagicMock(return_value=ret)
    with patch("salt.modules.cmdmod.run_all", mock_all):
        with pytest.raises(CommandExecutionError) as exc_info:
            win_pwsh.run_dict("Junk-Command")
        assert "Issue executing PowerShell" in exc_info.value.message


def test_run_dict_invalid_json():
    ret = {
        "pid": 1,
        "retcode": 0,
        "stderr": "",
        "stdout": "Invalid Json",
    }
    mock_all = MagicMock(return_value=ret)
    with patch("salt.modules.cmdmod.run_all", mock_all):
        with pytest.raises(CommandExecutionError) as exc_info:
            win_pwsh.run_dict("Junk-Command")
        assert "No JSON results from PowerShell" in exc_info.value.message
