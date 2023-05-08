import json
import os
import pathlib
import shutil
import subprocess

import pytest
from pytestskipmarkers.utils import platform


@pytest.fixture
def pypath():
    if platform.is_windows():
        return pathlib.Path(os.getenv("ProgramFiles"), "Salt Project", "Salt")
    elif platform.is_darwin():
        return pathlib.Path("/opt", "salt", "bin")
    else:
        return pathlib.Path("/opt", "saltstack", "salt", "bin")


@pytest.fixture(autouse=True)
def wipe_pydeps(shell, install_salt, extras_pypath):
    try:
        yield
    finally:
        # Note, uninstalling anything with an associated script will leave the script.
        # This is due to a bug in pip.
        for dep in ["pep8", "PyGithub"]:
            shell.run(
                *(install_salt.binary_paths["pip"] + ["uninstall", "-y", dep]),
            )
        shutil.rmtree(extras_pypath, ignore_errors=True)


def test_pip_install(salt_call_cli):
    """
    Test pip.install and ensure module can use installed library
    """
    dep = "PyGithub"
    repo = "https://github.com/saltstack/salt.git"

    try:
        install = salt_call_cli.run("--local", "pip.install", dep)
        assert install.returncode == 0

        use_lib = salt_call_cli.run("--local", "github.get_repo_info", repo)
        assert "Authentication information could" in use_lib.stderr
    finally:
        ret = salt_call_cli.run("--local", "pip.uninstall", dep)
        assert ret.returncode == 0
        use_lib = salt_call_cli.run("--local", "github.get_repo_info", repo)
        assert "The github execution module cannot be loaded" in use_lib.stderr


def test_pip_install_extras(shell, install_salt, extras_pypath_bin):
    """
    Test salt-pip installs into the correct directory
    """
    dep = "pep8"
    extras_keyword = "extras-3"
    if platform.is_windows():
        check_path = extras_pypath_bin / f"{dep}.exe"
    else:
        check_path = extras_pypath_bin / dep

    install_ret = shell.run(*(install_salt.binary_paths["pip"] + ["install", dep]))
    assert install_ret.returncode == 0

    ret = shell.run(*(install_salt.binary_paths["pip"] + ["list", "--format=json"]))
    assert ret.returncode == 0
    assert ret.data  # We can parse the JSON output
    for pkg in ret.data:
        if pkg["name"] == dep:
            break
    else:
        pytest.fail(
            f"The {dep!r} package was not found installed. Packages Installed: {pkgs_installed}"
        )

    show_ret = shell.run(*(install_salt.binary_paths["pip"] + ["show", dep]))
    assert show_ret.returncode == 0
    assert extras_keyword in show_ret.stdout
    assert check_path.exists()

    ret = shell.run(str(check_path), "--version")
    assert ret.returncode == 0


def demote(user_uid, user_gid):
    def result():
        os.setgid(user_gid)
        os.setuid(user_uid)

    return result


@pytest.mark.skip_on_windows(reason="We can't easily demote users on Windows")
def test_pip_non_root(shell, install_salt, test_account, extras_pypath_bin):
    check_path = extras_pypath_bin / "pep8"
    # We should be able to issue a --help without being root
    ret = subprocess.run(
        install_salt.binary_paths["salt"] + ["--help"],
        preexec_fn=demote(test_account.uid, test_account.gid),
        env=test_account.env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )
    assert ret.returncode == 0, ret.stderr
    assert "Usage" in ret.stdout

    # Let tiamat-pip create the pypath directory for us
    ret = subprocess.run(
        install_salt.binary_paths["pip"] + ["install", "-h"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )
    assert ret.returncode == 0, ret.stderr

    # Now, we should still not be able to install as non-root
    ret = subprocess.run(
        install_salt.binary_paths["pip"] + ["install", "pep8"],
        preexec_fn=demote(test_account.uid, test_account.gid),
        env=test_account.env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )
    assert ret.returncode != 0, ret.stderr
    # But we should be able to install as root
    ret = subprocess.run(
        install_salt.binary_paths["pip"] + ["install", "pep8"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )

    assert check_path.exists()

    assert ret.returncode == 0, ret.stderr


def test_pip_install_salt_extension_in_extras(install_salt, extras_pypath, shell):
    """
    Test salt-pip installs into the correct directory and the salt extension
    is properly loaded.
    """
    dep = "salt-analytics-framework"
    dep_version = "0.1.0"

    install_ret = shell.run(
        *(install_salt.binary_paths["pip"] + ["install", f"{dep}=={dep_version}"]),
    )
    assert install_ret.returncode == 0

    ret = shell.run(
        *(install_salt.binary_paths["pip"] + ["list", "--format=json"]),
    )
    assert ret.returncode == 0
    pkgs_installed = json.loads(ret.stdout.strip())
    for pkg in pkgs_installed:
        if pkg["name"] == dep:
            break
    else:
        pytest.fail(
            f"The {dep!r} package was not found installed. Packages Installed: {pkgs_installed}"
        )

    show_ret = shell.run(
        *(install_salt.binary_paths["pip"] + ["show", dep]),
    )
    assert show_ret.returncode == 0

    assert extras_pypath.joinpath("saf").is_dir()

    ret = shell.run(
        *(install_salt.binary_paths["minion"] + ["--versions-report"]),
    )
    assert show_ret.returncode == 0
    assert "Salt Extensions" in ret.stdout
    assert f"{dep}: {dep_version}" in ret.stdout
