import os

import pytest

import salt.utils.path

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
    pytest.mark.slow_test,
]


@pytest.fixture(params=["powershell", "pwsh"])
def shell(request):
    """
    This will run the test on powershell and powershell core (pwsh). If
    powershell core is not installed that test run will be skipped
    """

    if request.param == "pwsh" and salt.utils.path.which("pwsh") is None:
        pytest.skip("Powershell 7 Not Present")
    return request.param


def test_cmd_run_unless_true(shell, cmd):
    # We need a directory that we know exists that has stuff in it
    win_dir = os.getenv("WINDIR")
    ret = cmd.run(name="echo foo", unless=f"ls {win_dir}", shell=shell)
    assert ret.filtered["result"] is True
    assert ret.filtered["name"] == "echo foo"
    assert ret.filtered["comment"] == "unless condition is true"
    assert ret.filtered["changes"] == {}


def test_cmd_run_unless_false(shell, cmd):
    # We need a directory that we know does not exist
    win_dir = "C:\\This\\Dir\\Does\\Not\\Exist"
    ret = cmd.run(name="echo foo", unless=f"ls {win_dir}", shell=shell)
    assert ret.filtered["result"] is True
    assert ret.filtered["name"] == "echo foo"
    assert ret.filtered["comment"] == 'Command "echo foo" run'
    assert ret.filtered["changes"]["stdout"] == "foo"


def test_cmd_run_onlyif_true(shell, cmd):
    # We need a directory that we know exists that has stuff in it
    win_dir = os.getenv("WINDIR")
    ret = cmd.run(name="echo foo", onlyif=f"ls {win_dir}", shell=shell)
    assert ret.filtered["result"] is True
    assert ret.filtered["name"] == "echo foo"
    assert ret.filtered["comment"] == 'Command "echo foo" run'
    assert ret.filtered["changes"]["stdout"] == "foo"


def test_cmd_run_onlyif_false(shell, cmd):
    # We need a directory that we know does not exist
    win_dir = "C:\\This\\Dir\\Does\\Not\\Exist"
    ret = cmd.run(name="echo foo", onlyif=f"ls {win_dir}", shell=shell)
    assert ret.filtered["result"] is True
    assert ret.filtered["name"] == "echo foo"
    assert ret.filtered["comment"] == "onlyif condition is false"
    assert ret.filtered["changes"] == {}
