import pytest

import salt.modules.cmdmod as cmdmod
import salt.utils.path

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
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


@pytest.fixture(scope="module")
def account():
    with pytest.helpers.create_account() as _account:
        yield _account


@pytest.mark.parametrize(
    "cmd, expected, encode_cmd",
    [
        ("Write-Output Foo", "Foo", False),
        (["Write-Output", "Foo"], "Foo", False),
        ('Write-Output "Encoded Foo"', "Encoded Foo", True),
        (["Write-Output", '"Encoded Foo"'], "Encoded Foo", True),
    ],
)
def test_powershell(shell, cmd, expected, encode_cmd):
    """
    Test cmd.powershell
    """
    ret = cmdmod.powershell(cmd=cmd, encode_cmd=encode_cmd, shell=shell)
    assert ret == expected


@pytest.mark.parametrize(
    "cmd, expected, encode_cmd",
    [
        ("Write-Output Foo", "Foo", False),
        (["Write-Output", "Foo"], "Foo", False),
        ('Write-Output "Encoded Foo"', "Encoded Foo", True),
        (["Write-Output", '"Encoded Foo"'], "Encoded Foo", True),
    ],
)
def test_powershell_runas(shell, account, cmd, expected, encode_cmd):
    """
    Test cmd.powershell with runas
    """
    ret = cmdmod.powershell(
        cmd=cmd,
        encode_cmd=encode_cmd,
        shell=shell,
        runas=account.username,
        password=account.password,
    )
    assert ret == expected


@pytest.mark.parametrize(
    "cmd, expected, encode_cmd",
    [
        ("Write-Output Foo", "Foo", False),
        (["Write-Output", "Foo"], "Foo", False),
        ('Write-Output "Encoded Foo"', "Encoded Foo", True),
        (["Write-Output", '"Encoded Foo"'], "Encoded Foo", True),
    ],
)
def test_powershell_all(shell, cmd, expected, encode_cmd):
    """
    Test cmd.powershell_all. `encode_cmd` takes the passed command and encodes
    it. Different from encoded_command where it's receiving an already encoded
    command
    """
    ret = cmdmod.powershell_all(cmd=cmd, encode_cmd=encode_cmd, shell=shell)
    assert isinstance(ret["pid"], int)
    assert ret["retcode"] == 0
    assert ret["stderr"] == ""
    assert ret["result"] == expected


@pytest.mark.parametrize(
    "cmd, expected, encode_cmd",
    [
        ("Write-Output Foo", "Foo", False),
        (["Write-Output", "Foo"], "Foo", False),
        ('Write-Output "Encoded Foo"', "Encoded Foo", True),
        (["Write-Output", '"Encoded Foo"'], "Encoded Foo", True),
    ],
)
def test_powershell_all_runas(shell, account, cmd, expected, encode_cmd):
    """
    Test cmd.powershell_all with runas. `encode_cmd` takes the passed command
    and encodes it. Different from encoded_command where it's receiving an
    already encoded command
    """
    ret = cmdmod.powershell_all(
        cmd=cmd,
        encode_cmd=encode_cmd,
        shell=shell,
        runas=account.username,
        password=account.password,
    )
    assert isinstance(ret["pid"], int)
    assert ret["retcode"] == 0
    assert ret["stderr"] == ""
    assert ret["result"] == expected


@pytest.mark.parametrize(
    "cmd, expected, encoded_cmd",
    [
        ("Write-Output Foo", "Foo", False),
        (["Write-Output", "Foo"], "Foo", False),
        (
            "VwByAGkAdABlAC0ASABvAHMAdAAgACcARQBuAGMAbwBkAGUAZAAgAEYAbwBvACcA",
            "Encoded Foo",
            True,
        ),
    ],
)
def test_cmd_run_all_powershell(shell, cmd, expected, encoded_cmd):
    """
    Ensure that cmd.run_all supports running shell='powershell'
    """
    ret = cmdmod.run_all(cmd=cmd, shell=shell, encoded_cmd=encoded_cmd)
    assert ret["stdout"] == expected


@pytest.mark.parametrize(
    "cmd, expected, encoded_cmd",
    [
        ("Write-Output Foo", "Foo", False),
        (["Write-Output", "Foo"], "Foo", False),
        (
            "VwByAGkAdABlAC0ASABvAHMAdAAgACcARQBuAGMAbwBkAGUAZAAgAEYAbwBvACcA",
            "Encoded Foo",
            True,
        ),
    ],
)
def test_cmd_run_all_powershell_runas(shell, account, cmd, expected, encoded_cmd):
    """
    Ensure that cmd.run_all with runas supports running shell='powershell'
    """
    ret = cmdmod.run_all(
        cmd=cmd,
        shell=shell,
        encoded_cmd=encoded_cmd,
        runas=account.username,
        password=account.password,
    )
    assert ret["stdout"] == expected


@pytest.mark.parametrize(
    "cmd, expected, encoded_cmd",
    [
        ("Write-Output Foo", "Foo", False),
        (["Write-Output", "Foo"], "Foo", False),
        (
            "VwByAGkAdABlAC0ASABvAHMAdAAgACcARQBuAGMAbwBkAGUAZAAgAEYAbwBvACcA",
            "Encoded Foo",
            True,
        ),
    ],
)
def test_cmd_run_encoded_cmd(shell, cmd, expected, encoded_cmd):
    """
    Ensure that cmd.run supports running shell='powershell'
    """
    ret = cmdmod.run(
        cmd=cmd, shell=shell, encoded_cmd=encoded_cmd, redirect_stderr=False
    )
    assert ret == expected


@pytest.mark.parametrize(
    "cmd, expected, encoded_cmd",
    [
        ("Write-Output Foo", "Foo", False),
        (["Write-Output", "Foo"], "Foo", False),
        (
            "VwByAGkAdABlAC0ASABvAHMAdAAgACcARQBuAGMAbwBkAGUAZAAgAEYAbwBvACcA",
            "Encoded Foo",
            True,
        ),
    ],
)
def test_cmd_run_encoded_cmd_runas(shell, account, cmd, expected, encoded_cmd):
    """
    Ensure that cmd.run with runas supports running shell='powershell'
    """
    ret = cmdmod.run(
        cmd=cmd,
        shell=shell,
        encoded_cmd=encoded_cmd,
        runas=account.username,
        password=account.password,
    )
    assert ret == expected
