"""
Unit tests for the salt.states.python module
"""

import pytest

import salt.states.python as python
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {python: {"__env__": "base", "__opts__": {"test": False}}}


def test_run_test_mode():
    name = "print(1)"
    with patch.dict(python.__opts__, {"test": True}):
        run_mock = MagicMock()
        with patch.dict(python.__salt__, {"python.run": run_mock}):
            ret = python.run(name)

    assert ret["result"] is None
    run_mock.assert_not_called()


def test_run_invalid_env():
    name = "print(1)"
    ret = python.run(name, env="not-a-list-or-dict")
    assert ret["result"] is False
    assert "env" in ret["comment"]


def test_run_success():
    name = "print(1)"
    run_mock = MagicMock(return_value={"retcode": 0, "stdout": "", "stderr": ""})
    with patch.dict(python.__salt__, {"python.run": run_mock}):
        ret = python.run(name)

    assert ret["result"] is True
    run_mock.assert_called_once()
    assert run_mock.call_args[1]["command"] == name


def test_run_failure():
    name = "raise ValueError()"
    run_mock = MagicMock(return_value={"retcode": 1, "stdout": "", "stderr": ""})
    with patch.dict(python.__salt__, {"python.run": run_mock}):
        ret = python.run(name)

    assert ret["result"] is False


def test_run_exception():
    name = "print(1)"
    run_mock = MagicMock(side_effect=CommandExecutionError("boom"))
    with patch.dict(python.__salt__, {"python.run": run_mock}):
        ret = python.run(name)

    assert ret["result"] is False
    assert ret["comment"] == "boom"


def test_run_cwd_not_dir():
    name = "print(1)"
    ret = python.run(name, cwd="/this/path/does/not/exist")
    assert ret["result"] is False
    assert "not available" in ret["comment"]


def test_script_test_mode():
    name = "salt://myscript.py"
    with patch.dict(python.__opts__, {"test": True}):
        script_mock = MagicMock()
        with patch.dict(python.__salt__, {"python.script": script_mock}):
            ret = python.script(name)

    assert ret["result"] is None
    script_mock.assert_not_called()


def test_script_invalid_env():
    name = "salt://myscript.py"
    ret = python.script(name, env="not-a-list-or-dict")
    assert ret["result"] is False
    assert "env" in ret["comment"]


def test_script_invalid_context():
    name = "salt://myscript.py"
    ret = python.script(name, context="not-a-dict")
    assert ret["result"] is False
    assert "context" in ret["comment"]


def test_script_invalid_defaults():
    name = "salt://myscript.py"
    ret = python.script(name, defaults="not-a-dict")
    assert ret["result"] is False
    assert "defaults" in ret["comment"]


def test_script_success():
    name = "salt://myscript.py"
    script_mock = MagicMock(return_value={"retcode": 0, "stdout": "", "stderr": ""})
    with patch.dict(python.__salt__, {"python.script": script_mock}):
        ret = python.script(name)

    assert ret["result"] is True
    script_mock.assert_called_once()


def test_script_cache_error_comment():
    name = "salt://myscript.py"
    script_mock = MagicMock(
        return_value={
            "retcode": 1,
            "stdout": "",
            "stderr": "",
            "cache_error": True,
        }
    )
    with patch.dict(python.__salt__, {"python.script": script_mock}):
        ret = python.script(name)

    assert ret["result"] is False
    assert "Unable to cache script" in ret["comment"]


def test_script_cwd_not_dir():
    name = "salt://myscript.py"
    ret = python.script(name, cwd="/this/path/does/not/exist")
    assert ret["result"] is False
    assert "not available" in ret["comment"]
