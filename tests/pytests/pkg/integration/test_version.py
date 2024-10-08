import os.path
import pathlib
import subprocess
import time

import pytest
from pytestskipmarkers.utils import platform


@pytest.mark.skip_on_windows
def test_salt_version(version, install_salt):
    """
    Test version output from salt --version
    """
    actual = []
    test_bin = os.path.join(*install_salt.binary_paths["salt"])
    ret = install_salt.proc.run(test_bin, "--version")
    if "+" in version:
        # testing a non-release build artifact version
        actual = ret.stdout.strip().split(" ")[:2]
    else:
        # testing against release build version, for example: downgrade
        actual_ver = ret.stdout.strip().split(" ")[:2]
        actual_ver_salt = actual_ver[1]  # get salt version
        if "+" in actual_ver_salt:
            actual_ver_salt_stripped = actual_ver_salt.split("+")[
                0
            ]  # strip any git versioning
            actual.append(actual_ver[0])
            actual.append(actual_ver_salt_stripped)
        else:
            pytest.skip("Not testing a non-release build artifact, do not run")

    expected = ["salt", version]
    assert actual == expected


@pytest.mark.skip_on_windows
@pytest.mark.skip_on_darwin
def test_salt_versions_report_master(install_salt):
    """
    Test running --versions-report on master
    """
    test_bin = os.path.join(*install_salt.binary_paths["master"])
    python_bin = os.path.join(*install_salt.binary_paths["python"])
    ret = install_salt.proc.run(test_bin, "--versions-report")
    ret.stdout.matcher.fnmatch_lines(["*Salt Version:*"])
    py_version = subprocess.run(
        [str(python_bin), "--version"],
        check=True,
        capture_output=True,
    ).stdout
    py_version = py_version.decode().strip().replace(" ", ": ")
    ret.stdout.matcher.fnmatch_lines([f"*{py_version}*"])


@pytest.mark.skip_on_windows
def test_salt_versions_report_minion(salt_cli, salt_call_cli, salt_master, salt_minion):
    """
    Test running test.versions_report on minion
    """
    # Make sure the minion is running
    for count in range(0, 30):
        if salt_minion.is_running():
            break
        else:
            time.sleep(2)

    assert salt_minion.is_running()

    # Make sure the master is running
    for count in range(0, 30):
        if salt_master.is_running():
            break
        else:
            time.sleep(2)

    assert salt_master.is_running()

    # Make sure we can ping the minion ...
    ret = salt_cli.run(
        "--timeout=600", "test.ping", minion_tgt=salt_minion.id, _timeout=600
    )

    assert ret.returncode == 0
    assert ret.data is True
    ret = salt_cli.run(
        "--hard-crash",
        "--failhard",
        "--timeout=300",
        "test.versions_report",
        minion_tgt=salt_minion.id,
        _timeout=300,
    )
    ret.stdout.matcher.fnmatch_lines(["*Salt Version:*"])


@pytest.mark.skip_on_windows
@pytest.mark.skip_on_darwin
@pytest.mark.parametrize(
    "binary", ["master", "cloud", "syndic", "minion", "call", "api"]
)
def test_compare_versions(binary, install_salt):
    """
    Test compare versions
    """
    version = install_salt.artifact_version
    if binary in install_salt.binary_paths:
        if install_salt.upgrade:
            install_salt.install()

        ret = install_salt.proc.run(
            *install_salt.binary_paths[binary],
            "--version",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        ret.stdout.matcher.fnmatch_lines([f"*{version}*"])
    else:
        if platform.is_windows():
            pytest.skip(f"Binary not available on windows: {binary}")
        pytest.fail(
            f"Platform is not Windows and yet the binary {binary!r} is not available"
        )


@pytest.mark.skip_unless_on_darwin
@pytest.mark.parametrize(
    "symlink",
    [
        # We can't create a salt symlink because there is a salt directory
        "salt",
        "salt-api",
        "salt-call",
        "salt-cloud",
        "salt-cp",
        "salt-key",
        "salt-master",
        "salt-minion",
        "salt-proxy",
        "salt-run",
        "spm",
        "salt-ssh",
        "salt-syndic",
    ],
)
def test_symlinks_created(version, symlink, install_salt):
    """
    Test symlinks created
    """
    ret = install_salt.proc.run(pathlib.Path("/usr/local/sbin") / symlink, "--version")
    ret.stdout.matcher.fnmatch_lines([f"*{version}*"])


@pytest.mark.skip_unless_on_linux
@pytest.mark.skip_if_binaries_missing("rpmdev-vercmp")
def test_compare_pkg_versions_redhat_rc(version, install_salt):
    """
    Test compare pkg versions for redhat RC packages. A tilde should be included
    in RC Packages and it should test to be a lower version than a non RC
    package of the same version. For example, v3004~rc1 should be less than
    v3004.
    """
    if install_salt.distro_id not in (
        "almalinux",
        "rocky",
        "centos",
        "redhat",
        "amzn",
        "fedora",
        "photon",
    ):
        pytest.skip("Only tests rpm packages")

    pkg = [x for x in install_salt.pkgs if "rpm" in x]
    if not pkg:
        pytest.skip("Not testing rpm packages")
    pkg = pkg[0].split("/")[-1]
    if "rc" not in ".".join(pkg.split(".")[:2]):
        pytest.skip("Not testing an RC package")
    assert "~" in pkg
    comp_pkg = pkg.split("~")[0]
    ret = install_salt.proc.run("rpmdev-vercmp", pkg, comp_pkg)
    ret.stdout.matcher.fnmatch_lines([f"{pkg} < {comp_pkg}"])
