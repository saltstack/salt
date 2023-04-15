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
        return pathlib.Path(f"{os.sep}opt", "salt", "bin")
    else:
        return pathlib.Path(f"{os.sep}opt", "saltstack", "salt", "bin")


@pytest.fixture(autouse=True)
def wipe_pydeps(install_salt, extras_pypath):
    try:
        yield
    finally:
        # Note, uninstalling anything with an associated script will leave the script.
        # This is due to a bug in pip.
        for dep in ["pep8", "PyGithub"]:
            subprocess.run(
                install_salt.binary_paths["pip"] + ["uninstall", "-y", dep],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                universal_newlines=True,
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


def test_pip_install_extras(install_salt, extras_pypath):
    """
    Test salt-pip installs into the correct directory
    """
    dep = "pep8"
    extras_keyword = "extras"
    if platform.is_windows():
        check_path = extras_pypath / f"{dep}.exe"
    else:
        check_path = extras_pypath / dep

    install_ret = subprocess.run(
        install_salt.binary_paths["pip"] + ["install", dep],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert install_ret.returncode == 0

    ret = subprocess.run(
        install_salt.binary_paths["pip"] + ["list", "--format=json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert ret.returncode == 0
    pkgs_installed = json.loads(ret.stdout.strip().decode())
    for pkg in pkgs_installed:
        if pkg["name"] == dep:
            break
    else:
        pytest.fail(
            f"The {dep!r} package was not found installed. Packages Installed: {pkgs_installed}"
        )

    show_ret = subprocess.run(
        install_salt.binary_paths["pip"] + ["show", dep],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert show_ret.returncode == 0
    assert extras_keyword in show_ret.stdout.decode()
    assert check_path.exists()


def demote(user_uid, user_gid):
    def result():
        os.setgid(user_gid)
        os.setuid(user_uid)

    return result


@pytest.mark.skip_on_windows(reason="We can't easily demote users on Windows")
def test_pip_non_root(install_salt, test_account, extras_pypath):
    check_path = extras_pypath / "pep8"
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
