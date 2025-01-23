"""
Functional tests for chocolatey state
"""

import os
import pathlib

import pytest

import salt.utils.path
import salt.utils.win_reg

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
]


@pytest.fixture(scope="module")
def chocolatey(states):
    yield states.chocolatey


@pytest.fixture(scope="module")
def chocolatey_mod(modules):

    current_path = salt.utils.win_reg.read_value(
        hive="HKLM",
        key=r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        vname="PATH",
    )["vdata"]
    url = "https://community.chocolatey.org/api/v2/package/chocolatey/"
    with pytest.helpers.temp_file(name="choco.nupkg") as nupkg:
        choco_pkg = pathlib.Path(str(nupkg))
    choco_dir = choco_pkg.parent / "choco_dir"
    choco_script = choco_dir / "tools" / "chocolateyInstall.ps1"

    def install():
        # Install Chocolatey 1.2.1

        # Download Package
        modules.cp.get_url(path=url, dest=str(choco_pkg))

        # Unzip Package
        modules.archive.unzip(
            zip_file=str(choco_pkg),
            dest=str(choco_dir),
            extract_perms=False,
        )

        # Run installer script
        assert choco_script.exists()
        result = modules.cmd.script(
            source=str(choco_script),
            cwd=str(choco_script.parent),
            shell="powershell",
            python_shell=True,
        )
        assert result["retcode"] == 0

    def uninstall():
        choco_dir = os.environ.get("ChocolateyInstall", False)
        if choco_dir:
            # Remove Chocolatey Directory
            modules.file.remove(path=choco_dir, force=True)
            # Remove Chocolatey Environment Variables
            for env_var in modules.environ.items():
                if env_var.lower().startswith("chocolatey"):
                    modules.environ.setval(
                        key=env_var, val=False, false_unsets=True, permanent="HKLM"
                    )
                    modules.environ.setval(
                        key=env_var, val=False, false_unsets=True, permanent="HKCU"
                    )
        salt.utils.win_reg.set_value(
            hive="HKLM",
            key=r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
            vname="PATH",
            vdata=current_path,
        )
        modules.win_path.rehash()

    # Remove unknown version
    if salt.utils.path.which("choco.exe"):
        uninstall()

    # Install known version
    install()

    yield modules.chocolatey

    # Remove
    uninstall()


@pytest.fixture(scope="function")
def clean(chocolatey_mod):
    chocolatey_mod.uninstall(name="vim", force=True)
    yield
    chocolatey_mod.uninstall(name="vim", force=True)


@pytest.fixture(scope="function")
def vim(chocolatey_mod):
    chocolatey_mod.install(name="vim", version="9.0.1672")
    yield
    chocolatey_mod.uninstall(name="vim", force=True)


@pytest.fixture(scope="function")
def everything(chocolatey_mod):
    chocolatey_mod.install(name="everything", version="1.4.1935")
    yield
    chocolatey_mod.uninstall(name="everything", force=True)


def test_installed_latest(clean, chocolatey, chocolatey_mod):
    chocolatey.installed(name="vim")
    result = chocolatey_mod.version(name="vim")
    assert "vim" in result


def test_installed_version(clean, chocolatey, chocolatey_mod):
    chocolatey.installed(name="vim", version="9.0.1672")
    result = chocolatey_mod.version(name="vim")
    assert "vim" in result
    assert result["vim"]["installed"][0] == "9.0.1672"


def test_installed_version_existing_capitalization(
    everything, chocolatey, chocolatey_mod
):
    result = chocolatey.installed(name="everything", version="1.4.11024")
    expected_changes = {"Everything": {"new": ["1.4.11024"], "old": ["1.4.1935"]}}
    assert result["changes"] == expected_changes


def test_uninstalled(vim, chocolatey, chocolatey_mod):
    chocolatey.uninstalled(name="vim")
    result = chocolatey_mod.version(name="vim")
    assert "vim" not in result


def test_upgraded(vim, chocolatey, chocolatey_mod):
    result = chocolatey_mod.version(name="vim")
    assert "vim" in result
    assert result["vim"]["installed"][0] == "9.0.1672"
    chocolatey.upgraded(name="vim", version="9.0.1677")
    result = chocolatey_mod.version(name="vim")
    assert "vim" in result
    assert result["vim"]["installed"][0] == "9.0.1677"
