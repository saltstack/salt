"""
Unit tests for the salt.modules.python module
"""

import os
import sys

import pytest

import salt.modules.python as python
from salt.exceptions import SaltInvocationError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {python: {"__opts__": minion_opts}}


def test_get_python_executable():
    assert python._get_python_executable() == os.path.normpath(sys.executable)


def test_run_with_command():
    run_all_mock = MagicMock(return_value={"retcode": 0, "stdout": "", "stderr": ""})
    with patch.dict(python.__salt__, {"cmd.run_all": run_all_mock}):
        python.run(command="print(1)")

    call_args = run_all_mock.call_args
    cmd_list = call_args[0][0]
    assert cmd_list == [python._get_python_executable(), "-c", "print(1)"]
    assert call_args[1]["python_shell"] is False


def test_run_with_args_only():
    run_all_mock = MagicMock(return_value={"retcode": 0, "stdout": "", "stderr": ""})
    with patch.dict(python.__salt__, {"cmd.run_all": run_all_mock}):
        python.run(args=["-m", "json.tool", "foo.json"])

    cmd_list = run_all_mock.call_args[0][0]
    assert cmd_list == [
        python._get_python_executable(),
        "-m",
        "json.tool",
        "foo.json",
    ]


def test_run_with_string_args():
    run_all_mock = MagicMock(return_value={"retcode": 0, "stdout": "", "stderr": ""})
    with patch.dict(python.__salt__, {"cmd.run_all": run_all_mock}):
        python.run(command="print(1)", args="foo bar")

    cmd_list = run_all_mock.call_args[0][0]
    assert cmd_list == [python._get_python_executable(), "-c", "print(1)", "foo", "bar"]


def test_run_no_command_no_args_raises():
    with pytest.raises(SaltInvocationError):
        python.run()


def test_script_cache_success():
    run_all_mock = MagicMock(return_value={"retcode": 0, "stdout": "", "stderr": ""})
    cache_file_mock = MagicMock(return_value="/cache/path/myscript.py")
    remove_mock = MagicMock()
    salt_dunder = {
        "cmd.run_all": run_all_mock,
        "cp.cache_file": cache_file_mock,
        "file.remove": remove_mock,
        "file.user_to_uid": MagicMock(return_value=0),
    }
    with patch.dict(python.__salt__, salt_dunder), patch(
        "shutil.copyfile", MagicMock()
    ):
        ret = python.script("salt://myscript.py", args=["foo", "bar"])

    assert ret["retcode"] == 0
    cache_file_mock.assert_called_once()
    run_all_mock.assert_called_once()
    cmd_list = run_all_mock.call_args[0][0]
    assert cmd_list[0] == python._get_python_executable()
    assert cmd_list[-2:] == ["foo", "bar"]
    remove_mock.assert_called_once()


def test_script_cache_error():
    cache_file_mock = MagicMock(return_value=False)
    remove_mock = MagicMock()
    run_all_mock = MagicMock()
    salt_dunder = {
        "cmd.run_all": run_all_mock,
        "cp.cache_file": cache_file_mock,
        "file.remove": remove_mock,
    }
    with patch.dict(python.__salt__, salt_dunder):
        ret = python.script("salt://myscript.py")

    assert ret == {
        "pid": 0,
        "retcode": 1,
        "stdout": "",
        "stderr": "",
        "cache_error": True,
    }
    run_all_mock.assert_not_called()


def test_script_with_template():
    run_all_mock = MagicMock(return_value={"retcode": 0, "stdout": "", "stderr": ""})
    get_template_mock = MagicMock(return_value="/cache/path/myscript.py")
    remove_mock = MagicMock()
    salt_dunder = {
        "cmd.run_all": run_all_mock,
        "cp.get_template": get_template_mock,
        "file.remove": remove_mock,
    }
    with patch.dict(python.__salt__, salt_dunder):
        ret = python.script("salt://myscript.py", template="jinja")

    assert ret["retcode"] == 0
    get_template_mock.assert_called_once()
    run_all_mock.assert_called_once()
