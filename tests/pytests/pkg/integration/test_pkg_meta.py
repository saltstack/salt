import subprocess

import pytest
from pytestskipmarkers.utils import platform

import salt.utils.path
from tests.support.pkg import ARTIFACTS_DIR


@pytest.mark.skipif(not salt.utils.path.which("rpm"), reason="rpm is not installed")
def test_provides(install_salt, version):
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
    if platform.is_aarch64():
        arch = "aarch64"
    else:
        arch = "x86_64"
    name = f"salt-{version}-0.{arch}.rpm"
    package = ARTIFACTS_DIR / name
    assert package.exists()
    valid_provides = [
        f"config: config(salt) = {version}-0",
        f"manual: salt = {version}",
        f"manual: salt = {version}-0",
        f"manual: salt({arch.replace('_', '-')}) = {version}-0",
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
def test_requires(install_salt, version):
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
    if platform.is_aarch64():
        arch = "arm64"
    else:
        arch = "x86_64"
    name = f"salt-{version}-0.{arch}.rpm"
    package = ARTIFACTS_DIR / name
    assert package.exists()
    valid_requires = [
        "manual: /bin/sh",
        "pre,interp: /bin/sh",
        "post,interp: /bin/sh",
        "preun,interp: /bin/sh",
        "manual: /usr/sbin/groupadd",
        "manual: /usr/sbin/useradd",
        "manual: /usr/sbin/usermod",
        f"config: config(salt) = {version}-0",
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
    for line in proc.stdout.decode().splitlines():
        assert line in valid_requires
