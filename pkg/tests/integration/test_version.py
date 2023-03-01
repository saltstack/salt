import os.path
import pathlib
import subprocess

import pytest
from pytestskipmarkers.utils import platform


@pytest.mark.skip_on_windows
def test_salt_version(version, install_salt):
    """
    Test version output from salt --version
    """
    test_bin = os.path.join(*install_salt.binary_paths["salt"])
    ret = install_salt.proc.run(test_bin, "--version")
    actual = ret.stdout.strip().split(" ")[:2]
    expected = ["salt", version]
    assert actual == expected


@pytest.mark.skip_on_windows
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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout
    py_version = py_version.decode().strip().replace(" ", ": ")
    ret.stdout.matcher.fnmatch_lines([f"*{py_version}*"])


@pytest.mark.skip_on_windows
def test_salt_versions_report_minion(salt_cli, salt_minion):
    """
    Test running test.versions_report on minion
    """
    ret = salt_cli.run("test.versions_report", minion_tgt=salt_minion.id)
    ret.stdout.matcher.fnmatch_lines(["*Salt Version:*"])


@pytest.mark.parametrize(
    "binary", ["master", "cloud", "syndic", "minion", "call", "api"]
)
def test_compare_versions(version, binary, install_salt):
    """
    Test compare versions
    """
    if platform.is_windows() and install_salt.singlebin:
        pytest.skip(
            "Already tested in `test_salt_version`. No need to repeat for "
            "Windows single binary installs."
        )

    if binary in install_salt.binary_paths:
        ret = install_salt.proc.run(*install_salt.binary_paths[binary], "--version")
        ret.stdout.matcher.fnmatch_lines([f"*{version}*"])
    else:
        pytest.skip(f"Binary not available: {binary}")


@pytest.mark.skip_unless_on_darwin()
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
    if not install_salt.installer_pkg:
        pytest.skip(
            "This test is for the installer package only (pkg). It does not "
            "apply to the tarball"
        )
    ret = install_salt.proc.run(pathlib.Path("/usr/local/sbin") / symlink, "--version")
    ret.stdout.matcher.fnmatch_lines([f"*{version}*"])


@pytest.mark.skip_on_windows()
@pytest.mark.skipif(
    True, reason="Skipping until images are updated with rpmdev-vercmp for RC2"
)
def test_compare_pkg_versions_redhat_rc(version, install_salt):
    """
    Test compare pkg versions for redhat RC packages. A tilde should be included
    in RC Packages and it should test to be a lower version than a non RC
    package of the same version. For example, v3004~rc1 should be less than
    v3004.
    """
    if install_salt.distro_id not in ("centos", "redhat", "amzn", "fedora"):
        pytest.skip("Only tests rpm packages")

    pkg = [x for x in install_salt.pkgs if "rpm" in x]
    if not pkg:
        pytest.skip("Not testing rpm packages")
    pkg = pkg[0].split("/")[-1]
    if "rc" not in pkg:
        pytest.skip("Not testing an RC package")
    assert "~" in pkg
    comp_pkg = pkg.split("~")[0]
    ret = install_salt.proc.run("rpmdev-vercmp", pkg, comp_pkg)
    ret.stdout.matcher.fnmatch_lines([f"{pkg} < {comp_pkg}"])
