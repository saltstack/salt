import os.path
import pathlib
import subprocess
import time

import pytest
from pytestskipmarkers.utils import platform

from tests.support.pkg import pep440_public_equal


@pytest.mark.skip_on_windows
def test_salt_version(version, install_salt):
    """
    Test version output from salt --version
    """
    test_bin = os.path.join(*install_salt.binary_paths["salt"])
    ret = install_salt.proc.run(test_bin, "--version")
    assert ret.returncode == 0
    parts = ret.stdout.strip().split()
    assert len(parts) >= 2
    assert parts[0] == "salt"
    reported = parts[1]
    assert pep440_public_equal(
        reported, version
    ), f"salt --version reported {reported!r}, expected compatible with {version!r}"


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
    if install_salt.use_prev_version:
        version = install_salt.prev_version
    else:
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
        ver_pat = version.split("+", 1)[0] if "+" in version else version
        ret.stdout.matcher.fnmatch_lines([f"*{ver_pat}*"])
    else:
        if platform.is_windows():
            pytest.skip(f"Binary not available on windows: {binary}")
        pytest.fail(
            f"Platform is not Windows and yet the binary {binary!r} is not available"
        )


_DARWIN_PKG_SYMLINK_TO_BINKEY = {
    "salt": "salt",
    "salt-api": "api",
    "salt-call": "call",
    "salt-cloud": "cloud",
    "salt-cp": "cp",
    "salt-key": "key",
    "salt-master": "master",
    "salt-minion": "minion",
    "salt-proxy": "proxy",
    "salt-run": "run",
    "spm": "spm",
    "salt-ssh": "ssh",
    "salt-syndic": "syndic",
}


@pytest.mark.skip_unless_on_darwin
@pytest.mark.parametrize(
    "symlink",
    [
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
    Test packaged Salt CLI wrappers resolve and report the expected version.

    Older installers dropped symlinks under ``/usr/local/sbin``; newer onedir
    layouts may only ship binaries under the install prefix. Use the same paths
    as the rest of the package tests.
    """
    ret = install_salt.proc.run(pathlib.Path("/usr/local/sbin") / symlink, "--version")
    install_log_file = pathlib.Path("/tmp") / "postinstall.txt"
    install_log_content = install_log_file.read_text()
    ver_pat = version.split("+", 1)[0] if "+" in version else version
    ret.stdout.matcher.fnmatch_lines([f"*{ver_pat}*"])


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
