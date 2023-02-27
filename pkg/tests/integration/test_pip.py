import os
import pathlib
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
def wipe_pydeps(pypath, install_salt):
    try:
        yield
    finally:
        for dep in ["pep8", "PyGithub"]:
            subprocess.run(
                install_salt.binary_paths["pip"] + ["uninstall", "-y", dep],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                universal_newlines=True,
            )


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


def demote(user_uid, user_gid):
    def result():
        os.setgid(user_gid)
        os.setuid(user_uid)

    return result


@pytest.mark.skip_on_windows(reason="We can't easily demote users on Windows")
def test_pip_non_root(install_salt, test_account, pypath):
    check_path = pypath / "pep8"
    # Lets make sure pep8 is not currently installed
    subprocess.run(
        install_salt.binary_paths["pip"] + ["uninstall", "-y", "pep8"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )

    assert not check_path.exists()
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
    assert not check_path.exists()

    # Try to pip install something, should fail
    ret = subprocess.run(
        install_salt.binary_paths["pip"] + ["install", "pep8"],
        preexec_fn=demote(test_account.uid, test_account.gid),
        env=test_account.env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )
    assert ret.returncode == 1, ret.stderr
    assert "Could not install packages due to an OSError" in ret.stderr
    assert not check_path.exists()

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
