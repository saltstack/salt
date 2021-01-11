import base64

import pytest
import salt.modules.cmdmod as cmdmod
import salt.utils.path
import salt.utils.stringutils

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


def test_powershell(shell):
    """
    Test cmd.powershell
    """
    ret = cmdmod.powershell("Write-Output foo", shell=shell)
    assert ret == "foo"


def test_powershell_encode_cmd(shell):
    """
    Test cmd.powershell with encode_cmd
    """
    ret = cmdmod.powershell('Write-Output "encoded foo"', encode_cmd=True, shell=shell)
    assert ret == "encoded foo"


def test_powershell_all(shell):
    """
    Test cmd.powershell_all
    """
    ret = cmdmod.powershell_all("Write-Output foo", shell=shell)
    assert isinstance(ret["pid"], int)
    assert ret["retcode"] == 0
    assert ret["stderr"] == ""
    assert ret["result"] == "foo"


def test_powershell_all_encode_cmd(shell):
    """
    Test cmd.powershell_all with encode_cmd
    """
    ret = cmdmod.powershell_all(
        'Write-Output "encoded foo"', encode_cmd=True, shell=shell
    )
    assert isinstance(ret["pid"], int)
    assert ret["retcode"] == 0
    assert ret["stderr"] == ""
    assert ret["result"] == "encoded foo"


def test_cmd_run_all_powershell_list():
    """
    Ensure that cmd.run_all supports running shell='powershell' with cmd passed
    as a list
    """
    ret = cmdmod.run_all(
        cmd=["Write-Output", "salt"], python_shell=False, shell="powershell"
    )
    assert ret["stdout"] == "salt"


def test_cmd_run_all_powershell_string():
    """
    Ensure that cmd.run_all supports running shell='powershell' with cmd passed
     as a string
    """
    ret = cmdmod.run_all(
        cmd="Write-Output salt", python_shell=False, shell="powershell"
    )
    assert ret["stdout"] == "salt"


def test_cmd_run_encoded_cmd(shell):
    cmd = "Write-Output 'encoded command'"
    cmd = "$ProgressPreference='SilentlyContinue'; {}".format(cmd)
    cmd_utf16 = cmd.encode("utf-16-le")
    encoded_cmd = base64.standard_b64encode(cmd_utf16)
    encoded_cmd = salt.utils.stringutils.to_str(encoded_cmd)
    ret = cmdmod.run(cmd=encoded_cmd, shell=shell, encoded_cmd=True)
    assert ret == "encoded command"


def test_cmd_run_all_encoded_cmd(shell):
    cmd = "Write-Output 'encoded command'"
    cmd = "$ProgressPreference='SilentlyContinue'; {}".format(cmd)
    cmd_utf16 = cmd.encode("utf-16-le")
    encoded_cmd = base64.standard_b64encode(cmd_utf16)
    encoded_cmd = salt.utils.stringutils.to_str(encoded_cmd)
    ret = cmdmod.run_all(cmd=encoded_cmd, shell=shell, encoded_cmd=True)
    assert ret["stdout"] == "encoded command"
