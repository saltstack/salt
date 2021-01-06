import pytest
import salt.modules.cmdmod as cmdmod
import salt.utils.path

pytestmark = [
    pytest.mark.windows_whitelisted
]


@pytest.mark.skip_unless_on_windows(reason="Only run on Windows")
def test_powershell():
    """
    Test cmd.powershell
    """
    ret = cmdmod.powershell("Write-Output foo")
    assert ret == '"foo"'


@pytest.mark.skip_unless_on_windows(reason="Only run on Windows")
def test_powershell_encode_cmd():
    """
    Test cmd.powershell with encode_cmd
    """
    ret = cmdmod.powershell('Write-Output "encoded foo"', encode_cmd=True)
    assert ret == '"encoded foo"'


@pytest.mark.skip_unless_on_windows(reason="Only run on Windows")
@pytest.mark.skipif(not salt.utils.path.which("pwsh"), reason="Powershell 7 Not Present")
def test_powershell_pwsh():
    """
    Test cmd.powershell with Powershell 7 (shell="pwsh")
    """
    ret = cmdmod.powershell("Write-Output foo", shell="pwsh")
    assert ret == '"foo"'


@pytest.mark.skip_unless_on_windows(reason="Only run on Windows")
@pytest.mark.skipif(not salt.utils.path.which("pwsh"), reason="Powershell 7 Not Present")
def test_powershell_encode_cmd_pwsh():
    """
    Test cmd.powershell with encode_cmd on Powershell 7 (shell="pwsh")
    """
    ret = cmdmod.powershell('Write-Output "encoded foo"', shell="pwsh", encode_cmd=True)
    assert ret == '"encoded foo"'


@pytest.mark.skip_unless_on_windows(reason="Only run on Windows")
def test_powershell_all():
    """
    Test cmd.powershell_all
    """
    ret = cmdmod.powershell_all("Write-Output foo")
    assert isinstance(ret["pid"], int)
    assert ret["retcode"] == 0
    assert ret["stderr"] == ""
    assert ret["result"] == "foo"


@pytest.mark.skip_unless_on_windows(reason="Only run on Windows")
def test_powershell_all_encode_cmd():
    """
    Test cmd.powershell_all with encode_cmd
    """
    ret = cmdmod.powershell_all('Write-Output "encoded foo"', encode_cmd=True)
    assert isinstance(ret["pid"], int)
    assert ret["retcode"] == 0
    assert ret["stderr"] == ""
    assert ret["result"] == "encoded foo"


@pytest.mark.skip_unless_on_windows(reason="Only run on Windows")
@pytest.mark.skipif(not salt.utils.path.which("pwsh"), reason="Powershell 7 Not Present")
def test_powershell_all_pwsh():
    """
    Test cmd.powershell_all with Powershell 7 (shell="pwsh")
    """
    ret = cmdmod.powershell_all("Write-Output foo", shell="pwsh")
    assert isinstance(ret["pid"], int)
    assert ret["retcode"] == 0
    assert ret["stderr"] == ""
    assert ret["result"] == "foo"


@pytest.mark.skip_unless_on_windows(reason="Only run on Windows")
@pytest.mark.skipif(not salt.utils.path.which("pwsh"), reason="Powershell 7 Not Present")
def test_powershell_all_encode_cmd_pwsh():
    """
    Test cmd.powershell_all with encode_cmd on Powershell 7 (shell="pwsh")
    """
    ret = cmdmod.powershell_all('Write-Output "encoded foo"', shell="pwsh")
    assert isinstance(ret["pid"], int)
    assert ret["retcode"] == 0
    assert ret["stderr"] == ""
    assert ret["result"] == "encoded foo"


@pytest.mark.skip_unless_on_windows(reason="Only run on Windows")
def test_cmd_run_all_powershell_list():
    """
    Ensure that cmd.run_all supports running shell='powershell' with cmd passed
    as a list
    """
    ret = cmdmod.run_all(
        cmd=["Write-Output", "salt"],
        python_shell=False,
        shell="powershell"
    )
    assert ret["stdout"] == "salt"


@pytest.mark.skip_unless_on_windows(reason="Only run on Windows")
def test_cmd_run_all_powershell_string():
    """
    Ensure that cmd.run_all supports running shell='powershell' with cmd passed
     as a string
    """
    ret = cmdmod.run_all(
        cmd="Write-Output salt",
        python_shell=False,
        shell="powershell"
    )
    assert ret["stdout"] == "salt"
