import pytest

import salt.utils.path

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def cmd(modules):
    return modules.cmd


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
def issue_56195(state_tree):
    contents = """
    [CmdLetBinding()]
    Param(
      [SecureString] $SecureString
    )
    $Credential = New-Object System.Net.NetworkCredential("DummyId", $SecureString)
    $Credential.Password
    """
    with pytest.helpers.temp_file("test.ps1", contents, state_tree / "issue-56195"):
        yield


@pytest.mark.skip_unless_on_windows(reason="Minion is not Windows")
def test_windows_script_args_powershell(cmd, shell, issue_56195):
    """
    Ensure that powershell processes an inline script with args where the args
    contain powershell that needs to be rendered
    """
    password = "i like cheese"
    args = (
        "-SecureString (ConvertTo-SecureString -String '{}' -AsPlainText -Force)"
        " -ErrorAction Stop".format(password)
    )
    script = "salt://issue-56195/test.ps1"

    ret = cmd.script(source=script, args=args, shell="powershell", saltenv="base")

    assert ret["stdout"] == password


@pytest.mark.skip_unless_on_windows(reason="Minion is not Windows")
def test_windows_script_args_powershell_runas(cmd, shell, account, issue_56195):
    """
    Ensure that powershell processes an inline script with args where the args
    contain powershell that needs to be rendered
    """
    password = "i like cheese"
    args = (
        "-SecureString (ConvertTo-SecureString -String '{}' -AsPlainText -Force)"
        " -ErrorAction Stop".format(password)
    )
    script = "salt://issue-56195/test.ps1"

    ret = cmd.script(
        source=script,
        args=args,
        shell="powershell",
        saltenv="base",
        runas=account.username,
        password=account.password,
    )

    assert ret["stdout"] == password
