"""
Test Salt Pkg Downloads
"""
import logging
import os
import pathlib
import subprocess

import attr
import packaging
import pytest
import requests
from pytestskipmarkers.utils import platform
from saltfactories.utils import random_string

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class PkgImage:
    name = attr.ib()
    os_type = attr.ib()
    os_version = attr.ib()
    os_codename = attr.ib(default=None)
    container_id = attr.ib()
    container = attr.ib(default=None)

    def __str__(self):
        return f"{self.container_id}"


def get_test_versions():
    test_versions = []

    containers = [
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/amazon-linux:2",
            "os_type": "amazon",
            "os_version": 2,
            "container_id": "amazon_2",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/centos:7",
            "os_type": "redhat",
            "os_version": 7,
            "container_id": "centos_7",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/centos-stream:8",
            "os_type": "redhat",
            "os_version": 8,
            "container_id": "centosstream_8",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/centos-stream:9",
            "os_type": "redhat",
            "os_version": 9,
            "container_id": "centosstream_9",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/fedora:36",
            "os_type": "fedora",
            "os_version": 36,
            "container_id": "fedora_36",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/fedora:37",
            "os_type": "fedora",
            "os_version": 37,
            "container_id": "fedora_37",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/fedora:38",
            "os_type": "fedora",
            "os_version": 38,
            "container_id": "fedora_38",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/debian:10",
            "os_type": "debian",
            "os_version": 10,
            "os_codename": "buster",
            "container_id": "debian_10",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/debian:11",
            "os_type": "debian",
            "os_version": 11,
            "os_codename": "bullseye",
            "container_id": "debian_11",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/ubuntu:20.04",
            "os_type": "ubuntu",
            "os_version": 20.04,
            "os_codename": "focal",
            "container_id": "ubuntu_20_04",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/ubuntu:22.04",
            "os_type": "ubuntu",
            "os_version": 22.04,
            "os_codename": "jammy",
            "container_id": "ubuntu_22_04",
        },
    ]
    for container in containers:
        test_versions.append(
            PkgImage(
                name=container["image"],
                os_type=container["os_type"],
                os_version=container["os_version"],
                os_codename=container.get("os_codename", ""),
                container_id=container["container_id"],
            )
        )

    return test_versions


def get_container_type_id(value):
    return f"{value}"


@pytest.fixture(scope="module", params=get_test_versions(), ids=get_container_type_id)
def download_test_image(request):
    return request.param


def get_salt_test_commands():

    salt_release = get_salt_release()
    if platform.is_windows():
        if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
            salt_test_commands = [
                "salt-call.exe --local test.versions",
                "salt-call.exe --local grains.items",
                "salt-minion.exe --version",
            ]
        else:
            salt_test_commands = [
                "salt-call.bat --local test.versions",
                "salt-call.bat --local grains.items",
                "salt.bat --version",
                "salt-master.bat --version",
                "salt-minion.bat --version",
                "salt-ssh.bat --version",
                "salt-syndic.bat --version",
                "salt-api.bat --version",
                "salt-cloud.bat --version",
            ]
    else:
        salt_test_commands = [
            "salt-call --local test.versions",
            "salt-call --local grains.items",
            "salt --version",
            "salt-master --version",
            "salt-minion --version",
            "salt-ssh --version",
            "salt-syndic --version",
            "salt-api --version",
            "salt-cloud --version",
        ]
    return salt_test_commands


@pytest.fixture(scope="module")
def pkg_container(salt_factories, download_test_image, root_url, salt_release):
    container = salt_factories.get_container(
        random_string(f"{download_test_image.container_id}_"),
        download_test_image.name,
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    with container.started():
        setup_func = globals()[f"setup_{download_test_image.os_type}"]
        try:
            cmds = setup_func(
                download_test_image.os_version,
                download_test_image.os_codename,
                root_url,
                salt_release,
            )
        except KeyError:
            pytest.skip(f"Unable to handle {pkg_container.os_type}.  Skipping.")

        for cmd in cmds:
            res = container.run(cmd)
            assert res.returncode == 0

        download_test_image.container = container
        yield download_test_image


@pytest.fixture(scope="module")
def root_url(salt_release):
    repo_type = os.environ.get("SALT_REPO_TYPE", "staging")
    repo_domain = os.environ.get("SALT_REPO_DOMAIN", "repo.saltproject.io")
    if "rc" in salt_release:
        salt_path = "salt_rc/salt"
    else:
        salt_path = "salt"
    if repo_type == "staging":
        salt_repo_user = os.environ.get("SALT_REPO_USER")
        if salt_repo_user:
            log.warning(
                "SALT_REPO_USER: %s",
                salt_repo_user[0]
                + "*" * (len(salt_repo_user) - 2)
                + salt_repo_user[-1],
            )
        salt_repo_pass = os.environ.get("SALT_REPO_PASS")
        if salt_repo_pass:
            log.warning(
                "SALT_REPO_PASS: %s",
                salt_repo_pass[0]
                + "*" * (len(salt_repo_pass) - 2)
                + salt_repo_pass[-1],
            )
        if salt_repo_user and salt_repo_pass:
            repo_domain = f"{salt_repo_user}:{salt_repo_pass}@{repo_domain}"
    _root_url = f"https://{repo_domain}/{salt_path}/py3"
    log.info("Repository Root URL: %s", _root_url)
    return _root_url


def get_salt_release():
    if platform.is_darwin() or platform.is_windows():
        _DEFAULT_RELEASE = "3005-1"
    else:
        _DEFAULT_RELEASE = "3005.1"
    return os.environ.get("SALT_RELEASE", _DEFAULT_RELEASE)


@pytest.fixture(scope="module")
def salt_release():
    yield get_salt_release()


def setup_amazon(os_version, os_codename, root_url, salt_release):
    if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
        gpg_file = "SALT-PROJECT-GPG-PUBKEY-2023.pub"
    else:
        gpg_file = "salt-archive-keyring.gpg"

    arch = os.environ.get("SALT_REPO_ARCH") or "x86_64"
    if arch == "aarch64":
        arch = "arm64"

    cmds = [
        "pwd",
        f"rpm --import {root_url}/amazon/2/{arch}/minor/{salt_release}/{gpg_file}",
        f"curl -fsSL -o /etc/yum.repos.d/salt-amzn.repo {root_url}/amazon/2/{arch}/minor/{salt_release}.repo",
        [
            "sh",
            "-c",
            f"echo baseurl={root_url}/amazon/2/{arch}/minor/{salt_release} >> /etc/yum.repos.d/salt-amzn.repo",
        ],
        [
            "sh",
            "-c",
            f"echo gpgkey={root_url}/amazon/2/x86_64/minor/{salt_release}/{gpg_file} >> /etc/yum.repos.d/salt-amzn.repo",
        ],
        "yum clean expire-cache",
        "yum install -y salt-master salt-minion salt-ssh salt-syndic salt-cloud salt-api",
    ]
    return cmds


def setup_redhat(os_version, os_codename, root_url, salt_release):
    if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
        gpg_file = "SALT-PROJECT-GPG-PUBKEY-2023.pub"
    else:
        gpg_file = "SALTSTACK-GPG-KEY2.pub"

    arch = os.environ.get("SALT_REPO_ARCH") or "x86_64"
    if arch == "aarch64":
        arch = "arm64"

    cmds = [
        f"rpm --import {root_url}/redhat/{os_version}/{arch}/minor/{salt_release}/{gpg_file}",
        f"curl -fsSL -o /etc/yum.repos.d/salt.repo {root_url}/redhat/{os_version}/{arch}/minor/{salt_release}.repo",
        [
            "sh",
            "-c",
            f"echo baseurl={root_url}/redhat/{os_version}/{arch}/minor/{salt_release} >> /etc/yum.repos.d/salt.repo",
        ],
        "yum clean expire-cache",
        "yum install -y salt-master salt-minion salt-ssh salt-syndic salt-cloud salt-api",
    ]
    return cmds


def setup_fedora(os_version, os_codename, root_url, salt_release):
    if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
        gpg_file = "SALT-PROJECT-GPG-PUBKEY-2023.pub"
    else:
        gpg_file = "SALTSTACK-GPG-KEY2.pub"

    arch = os.environ.get("SALT_REPO_ARCH") or "x86_64"
    if arch == "aarch64":
        arch = "arm64"

    cmds = [
        f"rpm --import {root_url}/fedora/{os_version}/{arch}/minor/{salt_release}/{gpg_file}"
        f"curl -fsSL -o /etc/yum.repos.d/salt.repo {root_url}/fedora/{os_version}/{arch}/minor/{salt_release}.repo",
        [
            "sh",
            "-c",
            f"echo baseurl={root_url}/fedora/{os_version}/{arch}/minor/{salt_release} >> /etc/yum.repos.d/salt.repo",
        ],
        [
            "sh",
            "-c",
            f"echo gpgkey={root_url}/fedora/{os_version}/{arch}/minor/{salt_release}/{gpg_file} >> /etc/yum.repos.d/salt.repo",
        ],
        "yum clean expire-cache",
        "yum install -y salt-master salt-minion salt-ssh salt-syndic salt-cloud salt-api",
    ]
    return cmds


def setup_debian(os_version, os_codename, root_url, salt_release):
    if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
        gpg_file = "SALT-PROJECT-GPG-PUBKEY-2023.gpg"
    else:
        gpg_file = "salt-archive-keyring.gpg"

    arch = os.environ.get("SALT_REPO_ARCH") or "amd64"
    if arch == "aarch64":
        arch = "arm64"
    elif arch == "x86_64":
        arch = "amd64"

    cmds = [
        "apt-get update -y",
        "apt-get install -y curl",
        f"curl -fsSL -o /usr/share/keyrings/{gpg_file} {root_url}/debian/{os_version}/{arch}/minor/{salt_release}/{gpg_file}",
        [
            "sh",
            "-c",
            f'echo "deb [signed-by=/usr/share/keyrings/{gpg_file} arch={arch}] {root_url}/debian/{os_version}/{arch}/minor/{salt_release} {os_codename} main" > /etc/apt/sources.list.d/salt.list',
        ],
        "apt-get update",
        "apt-get install -y salt-master salt-minion salt-ssh salt-syndic salt-cloud salt-api",
    ]
    return cmds


def setup_ubuntu(os_version, os_codename, root_url, salt_release):
    if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
        gpg_file = "SALT-PROJECT-GPG-PUBKEY-2023.gpg"
    else:
        gpg_file = "salt-archive-keyring.gpg"

    arch = os.environ.get("SALT_REPO_ARCH") or "amd64"
    if arch == "aarch64":
        arch = "arm64"
    elif arch == "x86_64":
        arch = "amd64"

    cmds = [
        "apt-get update -y",
        "apt-get install -y curl",
        f"curl -fsSL -o /usr/share/keyrings/{gpg_file} {root_url}/ubuntu/{os_version}/{arch}/minor/{salt_release}/{gpg_file}",
        [
            "sh",
            "-c",
            f'echo "deb [signed-by=/usr/share/keyrings/{gpg_file} arch={arch}] {root_url}/ubuntu/{os_version}/{arch}/minor/{salt_release} {os_codename} main" > /etc/apt/sources.list.d/salt.list',
        ],
        "apt-get update",
        "apt-get install -y salt-master salt-minion salt-ssh salt-syndic salt-cloud salt-api",
    ]

    return cmds


@pytest.fixture(scope="module")
def setup_macos(root_url, salt_release):

    arch = os.environ.get("SALT_REPO_ARCH") or "x86_64"
    if arch == "aarch64":
        arch = "arm64"

    repo_type = os.environ.get("SALT_REPO_TYPE", "staging")
    if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
        if repo_type == "staging":
            mac_pkg = f"salt-{salt_release}-py3-{arch}-unsigned.pkg"
        else:
            mac_pkg = f"salt-{salt_release}-py3-{arch}.pkg"
        mac_pkg_url = f"{root_url}/macos/minor/{salt_release}/{mac_pkg}"
    else:
        mac_pkg_url = f"{root_url}/macos/{salt_release}/{mac_pkg}"
        mac_pkg = f"salt-{salt_release}-macos-{arch}.pkg"

    mac_pkg_path = f"/tmp/{mac_pkg}"

    # We should be able to issue a --help without being root
    ret = subprocess.run(
        ["curl", "-fsSL", "-o", f"/tmp/{mac_pkg}", f"{mac_pkg_url}"],
        check=False,
        capture_output=True,
    )
    assert ret.returncode == 0

    ret = subprocess.run(
        ["installer", "-pkg", mac_pkg_path, "-target", "/"],
        check=False,
        capture_output=True,
    )
    assert ret.returncode == 0

    yield


@pytest.fixture(scope="module")
def setup_windows(root_url, salt_release):

    root_dir = pathlib.Path(r"C:\Program Files\Salt Project\Salt")

    arch = os.environ.get("SALT_REPO_ARCH") or "amd64"
    install_type = os.environ.get("INSTALL_TYPE") or "msi"
    if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
        if install_type.lower() == "nsis":
            if arch.lower() != "x86":
                arch = arch.upper()
            win_pkg = f"Salt-Minion-{salt_release}-Py3-{arch}-Setup.exe"
        else:
            if arch.lower() != "x86":
                arch = arch.upper()
            win_pkg = f"Salt-Minion-{salt_release}-Py3-{arch}.msi"
        win_pkg_url = f"{root_url}/windows/minor/{salt_release}/{win_pkg}"
        ssm_bin = root_dir / "ssm.exe"
    else:
        win_pkg = f"salt-{salt_release}-windows-{arch}.exe"
        win_pkg_url = f"{root_url}/windows/{salt_release}/{win_pkg}"
        ssm_bin = root_dir / "bin" / "ssm_bin"

    pkg_path = pathlib.Path(r"C:\TEMP", win_pkg)
    pkg_path.parent.mkdir(exist_ok=True)

    ret = requests.get(win_pkg_url)
    with open(pkg_path, "wb") as fp:
        fp.write(ret.content)
    ret = subprocess.run(
        [pkg_path, "/start-minion=0", "/S"],
        check=False,
        capture_output=True,
    )
    assert ret.returncode == 0

    log.debug("Removing installed salt-minion service")
    ret = subprocess.run(
        ["cmd", "/c", str(ssm_bin), "remove", "salt-minion", "confirm"],
        check=False,
        capture_output=True,
    )
    assert ret.returncode == 0


@pytest.mark.skip_unless_on_linux
@pytest.mark.parametrize("salt_test_command", get_salt_test_commands())
@pytest.mark.skip_if_binaries_missing("dockerd")
def test_download_linux(salt_test_command, pkg_container, root_url, salt_release):
    """
    Test downloading of Salt packages and running various commands on Linux hosts
    """
    res = pkg_container.container.run(salt_test_command)
    assert res.returncode == 0


@pytest.mark.skip_unless_on_darwin
@pytest.mark.parametrize("salt_test_command", get_salt_test_commands())
def test_download_macos(salt_test_command, setup_macos):
    """
    Test downloading of Salt packages and running various commands on Mac OS hosts
    """
    _cmd = salt_test_command.split()
    ret = subprocess.run(
        _cmd,
        capture_output=True,
        check=False,
    )
    assert ret.returncode == 0


@pytest.mark.skip_unless_on_windows
@pytest.mark.parametrize("salt_test_command", get_salt_test_commands())
def test_download_windows(salt_test_command, setup_windows):
    """
    Test downloading of Salt packages and running various commands on Windows hosts
    """
    _cmd = salt_test_command.split()
    root_dir = pathlib.Path(r"C:\Program Files\Salt Project\Salt")
    _cmd[0] = str(root_dir / _cmd[0])

    ret = subprocess.run(
        _cmd,
        capture_output=True,
        check=False,
    )
    assert ret.returncode == 0
