import base64
import pytest
import salt.modules.cmdmod as cmdmod
import salt.utils.stringutils

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_onI_windows,
]


def test_powershell():
    """
    Test cmd.powershell
    """
    ret = cmdmod.powershell("Write-Output foo")
    assert ret == "foo"


def test_powershell_encode_cmd():
    """
    Test cmd.powershell with encode_cmd
    """
    ret = cmdmod.powershell('Write-Output "encoded foo"', encode_cmd=True)
    assert ret == "encoded foo"


@pytest.mark.skip_if_binaries_missing("pwsh", message="Powershell 7 Not Present")
def test_powershell_pwsh():
    """
    Test cmd.powershell with Powershell 7 (shell="pwsh")
    """
    ret = cmdmod.powershell("Write-Output foo", shell="pwsh")
    assert ret == "foo"


@pytest.mark.skip_if_binaries_missing("pwsh", message="Powershell 7 Not Present")
def test_powershell_encode_cmd_pwsh():
    """
    Test cmd.powershell with encode_cmd on Powershell 7 (shell="pwsh")
    """
    ret = cmdmod.powershell('Write-Output "encoded foo"', shell="pwsh", encode_cmd=True)
    assert ret == "encoded foo"


def test_powershell_all():
    """
    Test cmd.powershell_all
    """
    ret = cmdmod.powershell_all("Write-Output foo")
    assert isinstance(ret["pid"], int)
    assert ret["retcode"] == 0
    assert ret["stderr"] == ""
    assert ret["result"] == "foo"


def test_powershell_all_encode_cmd():
    """
    Test cmd.powershell_all with encode_cmd
    """
    ret = cmdmod.powershell_all('Write-Output "encoded foo"', encode_cmd=True)
    assert isinstance(ret["pid"], int)
    assert ret["retcode"] == 0
    assert ret["stderr"] == ""
    assert ret["result"] == "encoded foo"


@pytest.mark.skip_if_binaries_missing("pwsh", message="Powershell 7 Not Present")
def test_powershell_all_pwsh():
    """
    Test cmd.powershell_all with Powershell 7 (shell="pwsh")
    """
    ret = cmdmod.powershell_all("Write-Output foo", shell="pwsh")
    assert isinstance(ret["pid"], int)
    assert ret["retcode"] == 0
    assert ret["stderr"] == ""
    assert ret["result"] == "foo"


@pytest.mark.skip_if_binaries_missing("pwsh", message="Powershell 7 Not Present")
def test_powershell_all_encode_cmd_pwsh():
    """
    Test cmd.powershell_all with encode_cmd on Powershell 7 (shell="pwsh")
    """
    ret = cmdmod.powershell_all('Write-Output "encoded foo"', shell="pwsh")
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


def test_cmd_run_encoded_cmd():
    cmd = "Write-Output 'encoded command'"
    cmd = "$ProgressPreference='SilentlyContinue'; {0}".format(cmd)
    cmd_utf16 = cmd.encode("utf-16-le")
    encoded_cmd = base64.standard_b64encode(cmd_utf16)
    encoded_cmd = salt.utils.stringutils.to_str(encoded_cmd)
    ret = cmdmod.run(cmd=encoded_cmd, shell="powershell", encoded_cmd=True)
    assert ret == "encoded command"


@pytest.mark.skip_if_binaries_missing("pwsh", message="Powershell 7 Not Present")
def test_cmd_run_encoded_cmd_pwsh():
    cmd = "Write-Output 'encoded command'"
    cmd = "$ProgressPreference='SilentlyContinue'; {0}".format(cmd)
    cmd_utf16 = cmd.encode("utf-16-le")
    encoded_cmd = base64.standard_b64encode(cmd_utf16)
    encoded_cmd = salt.utils.stringutils.to_str(encoded_cmd)
    ret = cmdmod.run(cmd=encoded_cmd, shell="pwsh", encoded_cmd=True)
    assert ret == "encoded command"


def test_cmd_run_all_encoded_cmd():
    cmd = "Write-Output 'encoded command'"
    cmd = "$ProgressPreference='SilentlyContinue'; {0}".format(cmd)
    cmd_utf16 = cmd.encode("utf-16-le")
    encoded_cmd = base64.standard_b64encode(cmd_utf16)
    encoded_cmd = salt.utils.stringutils.to_str(encoded_cmd)
    ret = cmdmod.run_all(cmd=encoded_cmd, shell="powershell", encoded_cmd=True)
    assert ret["stdout"] == "encoded command"


@pytest.mark.skip_if_binaries_missing("pwsh", message="Powershell 7 Not Present")
def test_cmd_run_all_encoded_cmd_pwsh():
    cmd = "Write-Output 'encoded command'"
    cmd = "$ProgressPreference='SilentlyContinue'; {0}".format(cmd)
    cmd_utf16 = cmd.encode("utf-16-le")
    encoded_cmd = base64.standard_b64encode(cmd_utf16)
    encoded_cmd = salt.utils.stringutils.to_str(encoded_cmd)
    ret = cmdmod.run_all(cmd=encoded_cmd, shell="pwsh", encoded_cmd=True)
    assert ret["stdout"] == "encoded command"
