import pathlib
import re
import subprocess

import packaging
import pytest
from pytestskipmarkers.utils import platform

import salt.utils.path
from tests.support.pkg import ARTIFACTS_DIR


@pytest.fixture
def pkg_arch():
    if platform.is_aarch64():
        return "aarch64"
    else:
        return "x86_64"


@pytest.fixture
def provides_arch():
    if platform.is_aarch64():
        return "aarch-64"
    else:
        return "x86-64"


@pytest.fixture
def rpm_version():
    proc = subprocess.run(["rpm", "--version"], capture_output=True, check=True)
    return packaging.version.Version(proc.stdout.decode().rsplit(" ", 1)[-1])


@pytest.fixture
def required_version():
    return packaging.version.Version("4.12")


@pytest.fixture
def artifact_version(install_salt):
    return install_salt.artifact_version


@pytest.fixture
def rpm_pkg_version_release(package):
    """
    ``(version, release)`` from the RPM file itself.

    For GA packages ``%{VERSION}`` matches the on-disk filename (no ``~``).
    Pre-release RPMs use a tilde in ``%{VERSION}`` (e.g. ``3008.0~rc1+7...``)
    while :py:attr:`SaltPkgInstall.artifact_version` normalizes tildes away.
    """
    ver = (
        subprocess.run(
            ["rpm", "-qp", "--qf", "%{VERSION}\n", str(package)],
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )
    rel = (
        subprocess.run(
            ["rpm", "-qp", "--qf", "%{RELEASE}\n", str(package)],
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )
    return ver, rel


@pytest.fixture
def package(install_salt, artifact_version, pkg_arch):
    """
    Path to the main ``salt`` metapackage RPM.

    RPM file names use ``~`` before pre-release segments (e.g. ``3008.0~rc1``)
    while ``artifact_version`` strips that tilde when parsing from artifacts;
    match the real file from ``install_salt.pkgs`` instead of string-building.
    """
    rpm_re = re.compile(
        rf"^salt-\d.*-0\.{re.escape(pkg_arch)}\.rpm$",
        re.IGNORECASE,
    )
    for pkg_path in install_salt.pkgs:
        path = pathlib.Path(pkg_path)
        if rpm_re.match(path.name):
            return path
    name = f"salt-{artifact_version}-0.{pkg_arch}.rpm"
    return ARTIFACTS_DIR / name


@pytest.mark.skipif(not salt.utils.path.which("rpm"), reason="rpm is not installed")
def test_provides(
    install_salt,
    package,
    rpm_pkg_version_release,
    provides_arch,
    rpm_version,
    required_version,
):
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
    if rpm_version < required_version:
        pytest.skip(f"Test requires rpm version {required_version}")

    assert package.exists()
    rpm_ver, rpm_rel = rpm_pkg_version_release
    vr = f"{rpm_ver}-{rpm_rel}"
    valid_provides = [
        f"config: config(salt) = {vr}",
        f"manual: salt = {rpm_ver}",
        f"manual: salt = {vr}",
        f"manual: salt({provides_arch}) = {vr}",
    ]
    proc = subprocess.run(
        ["rpm", "-q", "-v", "-provides", package], capture_output=True, check=True
    )
    for line in proc.stdout.decode().splitlines():
        # If we have a provide that does not contain the word "salt" we should
        # fail.
        assert "salt" in line
        # Check sepecific provide lines.
        assert line in valid_provides


@pytest.mark.skipif(not salt.utils.path.which("rpm"), reason="rpm is not installed")
def test_requires(
    install_salt, package, rpm_pkg_version_release, rpm_version, required_version
):
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
    if rpm_version < required_version:
        pytest.skip(f"Test requires rpm version {required_version}")
    assert package.exists()
    rpm_ver, rpm_rel = rpm_pkg_version_release
    vr = f"{rpm_ver}-{rpm_rel}"
    valid_requires = [
        "manual: /bin/sh",
        "pre,interp: /bin/sh",
        "post,interp: /bin/sh",
        "preun,interp: /bin/sh",
        "manual: /usr/sbin/groupadd",
        "manual: /usr/sbin/useradd",
        "manual: /usr/sbin/usermod",
        f"config: config(salt) = {vr}",
        "manual: dmidecode",
        "manual: openssl",
        "manual: pciutils",
        # Not sure how often these will change, if this check causes things to
        # break often we'll want to re-factor.
        "rpmlib: rpmlib(CompressedFileNames) <= 3.0.4-1",
        "rpmlib: rpmlib(FileDigests) <= 4.6.0-1",
        "rpmlib: rpmlib(PayloadFilesHavePrefix) <= 4.0-1",
        "manual: which",
    ]
    proc = subprocess.run(
        ["rpm", "-q", "-v", "-requires", package], capture_output=True, check=True
    )
    requires_lines = proc.stdout.decode().splitlines()
    # ``rpmlib(TildeInVersions)`` appears only for some packages (e.g. ``~`` in
    # NEVRA) and the bound varies by ``rpm`` version; accept the exact line from
    # this RPM so GA packages (no such line) and future ``rpm`` strings stay valid.
    for line in requires_lines:
        if line.startswith("rpmlib: rpmlib(TildeInVersions)"):
            valid_requires.append(line)
    for line in requires_lines:
        assert line in valid_requires
