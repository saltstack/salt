import os
import time
from textwrap import dedent

import pytest

import salt.utils.path

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture(scope="module")
def cmd(modules):
    return modules.cmd


@pytest.fixture(scope="module")
def account():
    with pytest.helpers.create_account() as _account:
        yield _account


@pytest.fixture(scope="module")
def exitcode_script(state_tree):
    exit_code = 12345
    script_contents = dedent(
        f"""\
        Write-Host "Expected exit code: {exit_code}"
        exit {exit_code}
        """
    )
    with pytest.helpers.temp_file("exit_code.ps1", script_contents, state_tree):
        yield exit_code


@pytest.fixture(scope="module")
def echo_script(state_tree):
    exit_code = 12345
    script_contents = dedent(
        """\
        param (
            [string]$a,
            [string]$b
        )
        Write-Output "a: $a, b: $b"
        """
    )
    with pytest.helpers.temp_file("echo.ps1", script_contents, state_tree):
        yield exit_code


@pytest.fixture(scope="module")
def marker_script(state_tree):
    """
    Write a marker file so bg=True tests can observe that the real script ran.
    Also records $PSCommandPath so we can assert tempfile cleanup.
    """
    script_contents = dedent(
        """\
        param (
            [Parameter(Mandatory=$true)]
            [string]$OutFile,
            [string]$Payload = "ok"
        )
        Set-Content -LiteralPath $OutFile -Value "$Payload|$PSCommandPath"
        """
    )
    with pytest.helpers.temp_file("marker.ps1", script_contents, state_tree):
        yield


@pytest.fixture(params=["powershell", "pwsh"])
def shell(request):
    """
    This will run the test on PowerShell and PowerShell core (pwsh). If
    PowerShell core is not installed, that test run will be skipped
    """
    if request.param == "pwsh" and salt.utils.path.which("pwsh") is None:
        pytest.skip("Powershell 7 Not Present")
    return request.param


def test_exitcode(cmd, shell, exitcode_script):
    """
    Test receiving an exit code from a PowerShell script
    """
    ret = cmd.script("salt://exit_code.ps1", shell=shell, saltenv="base")
    assert ret["retcode"] == exitcode_script


@pytest.mark.parametrize(
    "args, expected",
    [
        ("foo bar", "a: foo, b: bar"),
        ('foo "bar bar"', "a: foo, b: bar bar"),
        (["foo", "bar"], "a: foo, b: bar"),
        (["foo foo", "bar bar"], "a: foo foo, b: bar bar"),
    ],
)
def test_echo(cmd, shell, echo_script, args, expected):
    """
    Test argument processing with a PowerShell script
    """
    ret = cmd.script("salt://echo.ps1", args=args, shell=shell, saltenv="base")
    assert isinstance(ret["pid"], int)
    assert ret["retcode"] == 0
    assert ret["stderr"] == ""
    assert ret["stdout"] == expected


@pytest.mark.parametrize(
    "args, expected",
    [
        ("foo bar", "a: foo, b: bar"),
        ('foo "bar bar"', "a: foo, b: bar bar"),
        (["foo", "bar"], "a: foo, b: bar"),
        (["foo foo", "bar bar"], "a: foo foo, b: bar bar"),
    ],
)
def test_echo_runas(cmd, shell, account, echo_script, args, expected):
    """
    Test argument processing with a PowerShell script and runas
    """
    ret = cmd.script(
        "salt://echo.ps1",
        args=args,
        shell=shell,
        runas=account.username,
        password=account.password,
        saltenv="base",
    )
    assert isinstance(ret["pid"], int)
    assert ret["retcode"] == 0
    assert ret["stderr"] == ""
    assert ret["stdout"] == expected


def _wait_for_marker(marker_path, timeout=30):
    """Poll until the background script writes the marker file."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if marker_path.is_file() and marker_path.stat().st_size > 0:
            return marker_path.read_text(encoding="utf-8").strip()
        time.sleep(0.1)
    raise AssertionError(f"Marker file not written within {timeout}s: {marker_path}")


def _wait_until_gone(path, timeout=30):
    """Poll until path is removed by the bg self-cleanup wrapper."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not os.path.exists(path):
            return
        time.sleep(0.1)
    raise AssertionError(f"Temp path still present after {timeout}s: {path}")


def test_script_bg_writes_marker_and_cleans_temp(cmd, shell, marker_script, tmp_path):
    """
    Regression for #69959 / #50273: cmd.script bg=True must not delete the
    tempfile before PowerShell can open it, and must still clean up afterward.
    """
    marker = tmp_path / "marker.txt"
    ret = cmd.script(
        "salt://marker.ps1",
        args=["-OutFile", str(marker), "-Payload", "bg-ok"],
        shell=shell,
        saltenv="base",
        bg=True,
    )
    assert isinstance(ret["pid"], int)
    # Background runs do not wait for the process; retcode is not meaningful.
    contents = _wait_for_marker(marker)
    payload, script_path = contents.split("|", 1)
    assert payload == "bg-ok"
    assert script_path.lower().endswith(".ps1")
    _wait_until_gone(script_path)
