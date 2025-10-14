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
    script_contents = f"""Write-Host "Expected exit code: {exit_code}"
exit {exit_code}
"""
    with pytest.helpers.temp_file("exit_code.ps1", script_contents, state_tree):
        yield exit_code


@pytest.fixture(scope="module")
def echo_script(state_tree):
    exit_code = 12345
    script_contents = """param (
    [string]$a,
    [string]$b
)
Write-Output "a: $a, b: $b"
"""
    with pytest.helpers.temp_file("echo.ps1", script_contents, state_tree):
        yield exit_code


@pytest.fixture(params=["powershell", "pwsh"])
def shell(request):
    """
    This will run the test on powershell and powershell core (pwsh). If
    powershell core is not installed that test run will be skipped
    """
    if request.param == "pwsh" and salt.utils.path.which("pwsh") is None:
        pytest.skip("Powershell 7 Not Present")
    return request.param


def test_exitcode(cmd, shell, exitcode_script):
    """
    Test receiving an exit code from a powershell script
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
    Test argument processing with a powershell script
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
    Test argument processing with a powershell script and runas
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
