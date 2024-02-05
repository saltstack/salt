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
    else:
        return pathlib.Path("/opt", "saltstack", "salt", "pypath", "bin")


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
        # Let's remove everything under the extras directory, uninstalling doesn't get dependencies
        dirs = []
        files = []
        for filename in extras_pypath.glob("**/**"):
            if filename != extras_pypath and filename.exists():
                if filename.is_dir():
                    dirs.append(filename)
                else:
                    files.append(filename)
        for fp in files:
            fp.unlink()
        for dirname in dirs:
            shutil.rmtree(dirname, ignore_errors=True)


@pytest.fixture
def pkg_tests_account_environ(pkg_tests_account):
    environ = os.environ.copy()
    environ["LOGNAME"] = environ["USER"] = pkg_tests_account.username
    environ["HOME"] = pkg_tests_account.info.home
    return environ


@pytest.mark.skip("Great module migration")
def test_pip_install(salt_call_cli, install_salt, shell):
    """
    Test pip.install and ensure module can use installed library
    """
    dep = "PyGithub==1.56.0"
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
    if not install_salt.relenv:
        pytest.skip("The extras directory is only in relenv versions")
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
            f"The {dep!r} package was not found installed. Packages Installed: {ret.data}"
        )

    show_ret = shell.run(*(install_salt.binary_paths["pip"] + ["show", dep]))
    assert show_ret.returncode == 0
    assert extras_keyword in show_ret.stdout
    assert check_path.exists()

    ret = shell.run(str(check_path), "--version")
    assert ret.returncode == 0


def demote(account):
    def result():
        # os.setgid does not remove group membership, so we remove them here so they are REALLY non-root
        os.setgroups([])
        os.setgid(account.info.gid)
        os.setuid(account.info.uid)

    return result


@pytest.mark.skip_on_windows(reason="We can't easily demote users on Windows")
def test_pip_non_root(
    shell,
    install_salt,
    pkg_tests_account,
    extras_pypath_bin,
    pypath,
    pkg_tests_account_environ,
):
    if install_salt.classic:
        pytest.skip("We can install non-root for classic packages")
    check_path = extras_pypath_bin / "pep8"
    if not install_salt.relenv and not install_salt.classic:
        check_path = pypath / "pep8"
    # We should be able to issue a --help without being root
    ret = subprocess.run(
        install_salt.binary_paths["salt"] + ["--help"],
        preexec_fn=demote(pkg_tests_account),
        env=pkg_tests_account_environ,
        capture_output=True,
        check=False,
        text=True,
    )
    assert ret.returncode == 0, ret.stderr
    assert "Usage" in ret.stdout

    # Let tiamat-pip create the pypath directory for us
    ret = subprocess.run(
        install_salt.binary_paths["pip"] + ["install", "-h"],
        capture_output=True,
        check=False,
        text=True,
    )
    assert ret.returncode == 0, ret.stderr

    # Now, we should still not be able to install as non-root
    ret = subprocess.run(
        install_salt.binary_paths["pip"] + ["install", "pep8"],
        preexec_fn=demote(pkg_tests_account),
        env=pkg_tests_account_environ,
        capture_output=True,
        check=False,
        text=True,
    )
    assert ret.returncode != 0, ret.stderr
    # But we should be able to install as root
    ret = subprocess.run(
        install_salt.binary_paths["pip"] + ["install", "pep8"],
        capture_output=True,
        check=False,
        text=True,
    )

    assert check_path.exists(), shutil.which("pep8")

    assert ret.returncode == 0, ret.stderr


def test_pip_install_salt_extension_in_extras(install_salt, extras_pypath, shell):
    """
    Test salt-pip installs into the correct directory and the salt extension
    is properly loaded.
    """
    if not install_salt.relenv:
        pytest.skip("The extras directory is only in relenv versions")
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
