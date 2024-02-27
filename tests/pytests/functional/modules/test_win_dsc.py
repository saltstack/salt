import os.path
import shutil
import subprocess

import psutil
import pytest

import salt.exceptions

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def dsc(modules):
    # We seem to be hitting an issue where there is a consistency check in
    # progress during some of the tests. When this happens, the test fails
    # This should disabled background refreshes
    # https://github.com/saltstack/salt/issues/62714
    existing_config_mode = modules.dsc.get_lcm_config()["ConfigurationMode"]
    modules.dsc.set_lcm_config(config_mode="ApplyOnly")
    yield modules.dsc
    modules.dsc.set_lcm_config(config_mode=existing_config_mode)


@pytest.fixture(scope="function")
def ps1_file():
    """
    This will create a DSC file to be configured. When configured it will create
    a localhost.mof file in the `HelloWorld` directory in Temp
    """
    ps1_contents = r"""
    Configuration HelloWorld {

        # Import the module that contains the File resource.
        Import-DscResource -ModuleName PsDesiredStateConfiguration

        # The Node statement specifies which targets to compile MOF files for, when this configuration is executed.
        Node ("localhost") {

            # The File resource can ensure the state of files, or copy them from a source to a destination with persistent updates.
            File HelloWorld {
                DestinationPath = "C:\Temp\HelloWorld.txt"
                Ensure          = "Present"
                Contents        = "Hello World, ps1_file"
            }
        }
    }
    """
    with pytest.helpers.temp_file("hello_world.ps1", contents=ps1_contents) as file:
        yield file
    if os.path.exists(file.parent / "HelloWorld"):
        shutil.rmtree(file.parent / "HelloWorld")
    if os.path.exists(file):
        os.remove(file)


@pytest.fixture(scope="function")
def ps1_file_multiple():
    """
    This will create a DSC file to be configured. When configured it will create
    a localhost.mof file in the `HelloWorld2` directory in Temp
    """
    ps1_contents = r"""
    Configuration HelloWorldMultiple {

        # Import the module that contains the File resource.
        Import-DscResource -ModuleName PsDesiredStateConfiguration

        # The Node statement specifies which targets to compile MOF files for, when this configuration is executed.
        Node ("localhost") {

            # The File resource can ensure the state of files, or copy them from a source to a destination with persistent updates.
            File HelloWorld {
                DestinationPath = "C:\Temp\HelloWorld.txt"
                Ensure          = "Present"
                Contents        = "Hello World from DSC!"
            }

            # The File resource can ensure the state of files, or copy them from a source to a destination with persistent updates.
            File HelloWorld2 {
                DestinationPath = "C:\Temp\HelloWorld2.txt"
                Ensure          = "Present"
                Contents        = "Hello World, ps1_file_multiple"
            }
        }
    }
    """

    with pytest.helpers.temp_file(
        "hello_world_multiple.ps1", contents=ps1_contents
    ) as file:
        yield file
    if os.path.exists(file.parent / "HelloWorldMultiple"):
        shutil.rmtree(file.parent / "HelloWorldMultiple")
    if os.path.exists(file):
        os.remove(file)


@pytest.fixture(scope="function")
def ps1_file_meta():
    """
    This will create a DSC file to be configured. When configured it will create
    a localhost.mof file and a localhost.meta.mof file in the `HelloWorld`
    directory in Temp
    """
    ps1_contents = r"""
    Configuration HelloWorld {

        # Import the module that contains the File resource.
        Import-DscResource -ModuleName PsDesiredStateConfiguration

        # The Node statement specifies which targets to compile MOF files for, when this configuration is executed.
        Node ("localhost") {

            # The File resource can ensure the state of files, or copy them from a source to a destination with persistent updates.
            File HelloWorld {
                DestinationPath = "C:\Temp\HelloWorld.txt"
                Ensure          = "Present"
                Contents        = "Hello World, ps1_file_meta "
            }

            # Set some Meta Config
            LocalConfigurationManager {
                ConfigurationMode  = "ApplyAndMonitor"
                RebootNodeIfNeeded = $false
                RefreshMode        = "PUSH"
            }
        }
    }
    """
    with pytest.helpers.temp_file("test.ps1", contents=ps1_contents) as file:
        yield file
    if os.path.exists(file.parent / "HelloWorld"):
        shutil.rmtree(file.parent / "HelloWorld")
    if os.path.exists(file):
        os.remove(file)


@pytest.fixture(scope="module")
def psd1_file():
    """
    This will create a config data file to be applied with the config file in
    Temp
    """
    psd1_contents = r"""
    @{
        AllNodes = @(
            @{
                NodeName = 'localhost'
                PSDscAllowPlainTextPassword = $true
                PSDscAllowDomainUser = $true
            }
        )
    }
    """
    with pytest.helpers.temp_file("test.psd1", contents=psd1_contents) as file:
        yield file
    if os.path.exists(file):
        os.remove(file)


def test_compile_config_missing(dsc):
    path = "C:\\Path\\not\\exists.ps1"
    with pytest.raises(salt.exceptions.CommandExecutionError) as exc:
        dsc.compile_config(path=path)
    assert exc.value.message == f"{path} not found"


@pytest.mark.destructive_test
def test_compile_config(dsc, ps1_file, psd1_file):
    """
    Test compiling a simple config
    """
    dsc.remove_config(reset=False)
    result = dsc.compile_config(
        path=str(ps1_file),
        config_name="HelloWorld",
        config_data=str(psd1_file),
    )
    assert isinstance(result, dict)
    assert result["Exists"] is True


@pytest.mark.destructive_test
def test_compile_config_issue_61261(dsc, ps1_file_meta, psd1_file):
    """
    Test compiling a config that includes meta data
    """
    dsc.remove_config(reset=False)
    result = dsc.compile_config(
        path=str(ps1_file_meta),
        config_name="HelloWorld",
        config_data=str(psd1_file),
    )
    assert isinstance(result, dict)
    assert result["Exists"] is True


def test_apply_config_missing(dsc):
    path = "C:\\Path\\not\\exists"
    with pytest.raises(salt.exceptions.CommandExecutionError) as exc:
        dsc.apply_config(path=path)
    assert exc.value.message == f"{path} not found"


@pytest.mark.destructive_test
def test_apply_config(dsc, ps1_file, psd1_file):
    """
    Test applying a simple config
    """
    dsc.remove_config(reset=False)
    dsc.compile_config(
        path=str(ps1_file),
        config_name="HelloWorld",
        config_data=str(psd1_file),
    )
    result = dsc.apply_config(path=ps1_file.parent / "HelloWorld")
    assert result is True


def test_get_config_not_configured(dsc):
    dsc.remove_config(reset=False)
    with pytest.raises(salt.exceptions.CommandExecutionError) as exc:
        dsc.get_config()
    assert exc.value.message == "Not Configured"


def test_get_config_single(dsc, ps1_file, psd1_file):
    dsc.remove_config(reset=False)
    dsc.run_config(
        path=str(ps1_file),
        config_name="HelloWorld",
        config_data=str(psd1_file),
    )
    result = dsc.get_config()
    assert "HelloWorld" in result
    assert "[File]HelloWorld" in result["HelloWorld"]
    assert "DestinationPath" in result["HelloWorld"]["[File]HelloWorld"]


def test_get_config_multiple(dsc, ps1_file_multiple, psd1_file):
    dsc.remove_config(reset=False)
    dsc.run_config(
        path=str(ps1_file_multiple),
        config_name="HelloWorldMultiple",
        config_data=str(psd1_file),
    )
    result = dsc.get_config()
    assert "HelloWorldMultiple" in result
    assert "[File]HelloWorld" in result["HelloWorldMultiple"]
    assert "DestinationPath" in result["HelloWorldMultiple"]["[File]HelloWorld"]
    assert "[File]HelloWorld2" in result["HelloWorldMultiple"]
    assert "DestinationPath" in result["HelloWorldMultiple"]["[File]HelloWorld2"]


def _reset_config(dsc):
    """
    Resets the DSC config. If files are locked, this will attempt to kill the
    all running WmiPrvSE processes. Windows will respawn the ones it needs
    """
    tries = 1
    while True:
        try:
            tries += 1
            dsc.remove_config(reset=True)
            break
        except salt.exceptions.CommandExecutionError:
            if tries > 12:
                raise

            # Kill the processes
            proc_name = "wmiprvse.exe"
            for proc in psutil.process_iter():
                if proc.name().lower() == proc_name:
                    proc.kill()

            continue


def test_get_config_status_not_configured(dsc):
    _reset_config(dsc)
    with pytest.raises(salt.exceptions.CommandExecutionError) as exc:
        dsc.get_config_status()
    assert exc.value.message == "Not Configured"


def test_get_config_status(dsc, ps1_file, psd1_file):
    dsc.remove_config(reset=False)
    dsc.run_config(
        path=str(ps1_file),
        config_name="HelloWorld",
        config_data=str(psd1_file),
    )
    result = dsc.get_config_status()
    assert "MetaData" in result
    assert "HelloWorld" in result["MetaData"]
    assert result["Status"] == "Success"


def test_test_config_not_configured(dsc):
    subprocess.run(
        ["cmd", "/c", "winrm", "quickconfig", "-quiet"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    dsc.remove_config(reset=False)
    with pytest.raises(salt.exceptions.CommandExecutionError) as exc:
        dsc.test_config()
    assert exc.value.message == "Not Configured"


def test_test_config(dsc, ps1_file, psd1_file):
    dsc.remove_config(reset=False)
    dsc.run_config(
        path=str(ps1_file),
        config_name="HelloWorld",
        config_data=str(psd1_file),
    )
    result = dsc.test_config()
    assert result is True


def test_get_lcm_config(dsc):
    config_items = [
        "ConfigurationModeFrequencyMins",
        "LCMState",
        "RebootNodeIfNeeded",
        "ConfigurationMode",
        "ActionAfterReboot",
        "RefreshMode",
        "CertificateID",
        "ConfigurationID",
        "RefreshFrequencyMins",
        "AllowModuleOverwrite",
        "DebugMode",
        "StatusRetentionTimeInDays",
    ]
    dsc.remove_config(reset=False)
    result = dsc.get_lcm_config()
    for item in config_items:
        assert item in result


def test_set_lcm_config(dsc):
    current = dsc.get_lcm_config()["ConfigurationMode"]
    dsc.set_lcm_config(config_mode="ApplyOnly")
    try:
        results = dsc.get_lcm_config()
        assert results["ConfigurationMode"] == "ApplyOnly"
    finally:
        dsc.set_lcm_config(config_mode=current)
