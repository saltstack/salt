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


@pytest.fixture
def issue_56195(state_tree, account):
    tmpdir = f"C:\\Users\\{account.username}\\AppData\\Local\\Temp"
    contents = """[CmdLetBinding()]
Param(
    [SecureString] $SecureString
)
$Credential = New-Object System.Net.NetworkCredential("DummyId", $SecureString)
$Credential.Password
"""
    with pytest.helpers.temp_file("test.ps1", contents, tmpdir) as f:
        yield str(f), account


def test_args(issue_56195):
    """
    Ensure that powershell processes an inline script with args where the args
    contain powershell that needs to be rendered
    """
    (script, _) = issue_56195
    password = "i like cheese"
    args = (
        "-SecureString (ConvertTo-SecureString -String '{}' -AsPlainText -Force)"
        " -ErrorAction Stop".format(password)
    )
    # https://github.com/PowerShell/PowerShell/issues/18530
    cmd = f'$env:PSModulePath=""; {script} {args}'
    ret = cmdmod.powershell(cmd, args=args, saltenv="base")
    assert ret == password


def test_args_runas(issue_56195):
    """
    Ensure that powershell with runas processes an inline script with args where
    the args contain powershell that needs to be rendered
    """
    (script, account) = issue_56195
    password = "i like cheese"
    args = (
        "-SecureString (ConvertTo-SecureString -String '{}' -AsPlainText -Force)"
        " -ErrorAction Stop".format(password)
    )
    # https://github.com/PowerShell/PowerShell/issues/18530
    cmd = f'$env:PSModulePath=""; {script} {args}'
    ret = cmdmod.powershell(
        cmd,
        args=args,
        runas=account.username,
        password=account.password,
        saltenv="base",
    )
    assert ret == password


@pytest.mark.parametrize(
    "cmd, expected, encode_cmd",
    [
        ("Write-Output Foo", "Foo", False),
        (["Write-Output", "Foo"], "Foo", False),
        ('Write-Output "Encoded Foo"', "Encoded Foo", True),
        (["Write-Output", '"Encoded Foo"'], "Encoded Foo", True),
        ("$a=\"Plain\";$b=' Foo';Write-Output ${a}${b}", "Plain Foo", False),
        ("(Write-Output Foo)", "Foo", False),
        ("& Write-Output Foo", "Foo", False),
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
        ("$a=\"Plain\";$b=' Foo';Write-Output ${a}${b}", "Plain Foo", False),
        ("(Write-Output Foo)", "Foo", False),
        ("& Write-Output Foo", "Foo", False),
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
        redirect_stderr=False,
        runas=account.username,
        password=account.password,
    )
    assert ret == expected


@pytest.mark.parametrize(
    "command, expected_stdout",
    [
        # LF line endings, as produced by a YAML block scalar (|)
        (
            "powershell -NoProfile -ExecutionPolicy Bypass -Command {\n    Write-Output test\n}\n",
            "test",
        ),
        # CRLF line endings
        (
            "powershell -NoProfile -ExecutionPolicy Bypass -Command {\r\n    Write-Output test\r\n}\r\n",
            "test",
        ),
    ],
)
def test_powershell_multiline_block_no_clixml(command, expected_stdout):
    """
    A multiline ``powershell -Command { }`` block run via cmd.run_all with
    python_shell=True must execute correctly and must not leave CLIXML noise
    in stderr.

    Without special handling, cmd.exe treats newlines as command separators so
    only the first line reaches PowerShell, producing a 'Missing closing }'
    error. Salt collapses the newlines and converts ``-Command { block }`` to
    ``-EncodedCommand`` so the script block executes and stderr is clean.
    """
    result = cmdmod.run_all(command, python_shell=True)
    assert result["retcode"] == 0
    assert result["stdout"] == expected_stdout
    assert "CLIXML" not in result["stderr"]
