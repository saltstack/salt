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

pytestmark = [
    pytest.mark.slow_test,
]


@attr.s(kw_only=True, slots=True)
class PkgImage:
    name = attr.ib()
    os_type = attr.ib()
    os_version = attr.ib()
    os_codename = attr.ib(default=None)
    container_id = attr.ib()
    container = attr.ib(default=None)

    def __str__(self):
        return "{}".format(self.container_id)


def get_test_versions():
    test_versions = []

    containers = [
        {
            "image": "saltstack/ci-amazon-2",
            "os_type": "amazon",
            "os_version": 2,
            "container_id": "amazon_2",
        },
        {
            "image": "saltstack/ci-centos-7",
            "os_type": "redhat",
            "os_version": 7,
            "container_id": "centos_7",
        },
        {
            "image": "saltstack/ci-centosstream-8",
            "os_type": "redhat",
            "os_version": 8,
            "container_id": "centosstream_8",
        },
        {
            "image": "saltstack/ci-centosstream-9",
            "os_type": "redhat",
            "os_version": 9,
            "container_id": "centosstream_9",
        },
        {
            "image": "debian:10",
            "os_type": "debian",
            "os_version": 10,
            "os_codename": "buster",
            "container_id": "debian_10",
        },
        {
            "image": "debian:11",
            "os_type": "debian",
            "os_version": 11,
            "os_codename": "bullseye",
            "container_id": "debian_11",
        },
        {
            "image": "ubuntu:20.04",
            "os_type": "ubuntu",
            "os_version": 20.04,
            "os_codename": "focal",
            "container_id": "ubuntu_20_04",
        },
        {
            "image": "ubuntu:22.04",
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
    return "{}".format(value)


@pytest.fixture(scope="module", params=get_test_versions(), ids=get_container_type_id)
def download_test_image(request):
    return request.param


def get_salt_test_commands():

    if platform.is_windows():
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
def pkg_container(
    salt_factories, download_test_image, root_url, minor_url, salt_release
):
    container = salt_factories.get_container(
        random_string("{}_".format(download_test_image.container_id)),
        download_test_image.name,
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    with container.started():
        setup_func = globals()["setup_{}".format(download_test_image.os_type)]
        try:
            cmds = setup_func(
                download_test_image.os_version,
                download_test_image.os_codename,
                root_url,
                minor_url,
                salt_release,
            )
        except KeyError:
            pytest.skip("Unable to handle {}.  Skipping.".format(pkg_container.os_type))

        for cmd in cmds:
            res = container.run(cmd)
            assert res.returncode == 0

        download_test_image.container = container
        yield download_test_image


@pytest.fixture(scope="module")
def root_url():
    repo_type = os.environ.get("SALT_REPO_TYPE", "staging")
    root_url = os.environ.get("SALT_REPO_ROOT_URL", "repo.saltproject.io")
    if "staging" in root_url or repo_type == "staging":
        salt_repo_user = os.environ.get("SALT_REPO_USER")
        salt_repo_pass = os.environ.get("SALT_REPO_PASS")
        if not salt_repo_user or not salt_repo_pass:
            pytest.skip(
                "Values for SALT_REPO_USER or SALT_REPO_PASS are unavailable. Skipping."
            )
        root_url = "https://{}:{}@{}/salt/py3".format(
            salt_repo_user, salt_repo_pass, root_url
        )
    else:
        root_url = "https://{}/salt/py3".format(root_url)
    yield root_url


@pytest.fixture(scope="module")
def minor_url(salt_release):
    if "." in salt_release:
        minor_url = "minor/"
    else:
        minor_url = ""
    yield minor_url


@pytest.fixture(scope="module")
def salt_release():
    if platform.is_darwin() or platform.is_windows():
        _DEFAULT_RELEASE = "3005-1"
    else:
        _DEFAULT_RELEASE = "3005.1"
    salt_release = os.environ.get("SALT_RELEASE", _DEFAULT_RELEASE)
    yield salt_release


def setup_amazon(os_version, os_codename, root_url, minor_url, salt_release):
    if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
        GPG_FILE = "SALT-PROJECT-GPG-PUBKEY-2023.pub"
    else:
        GPG_FILE = "salt-archive-keyring.gpg"

    cmds = [
        "pwd",
        "sudo rpm --import {}/amazon/2/x86_64/{}{}/{}".format(
            root_url, minor_url, salt_release, GPG_FILE
        ),
        "curl -fsSL -o /etc/yum.repos.d/salt-amzn.repo {}/amazon/2/x86_64/{}{}.repo".format(
            root_url, minor_url, salt_release
        ),
        [
            "sh",
            "-c",
            "echo baseurl={}/amazon/2/x86_64/{}{}  >> /etc/yum.repos.d/salt-amzn.repo".format(
                root_url, minor_url, salt_release
            ),
        ],
        [
            "sh",
            "-c",
            "echo gpgkey={}/amazon/2/x86_64/{}{}/SALTSTACK-GPG-KEY.pub >> /etc/yum.repos.d/salt-amzn.repo".format(
                root_url, minor_url, salt_release
            ),
        ],
        "sudo yum clean expire-cache",
        "sudo yum install salt-master salt-minion salt-ssh salt-syndic salt-cloud salt-api -y",
    ]
    return cmds


def setup_redhat(os_version, os_codename, root_url, minor_url, salt_release):
    if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
        GPG_FILE = "SALT-PROJECT-GPG-PUBKEY-2023.pub"
    else:
        GPG_FILE = "SALTSTACK-GPG-KEY2.pub"

    cmds = []
    if os_version >= 9:
        cmds.append(
            "sudo rpm --import {}/redhat/{}/x86_64/{}{}/{}".format(
                root_url, os_version, minor_url, salt_release, GPG_FILE
            )
        )
    else:
        cmds.append(
            "sudo rpm --import {}/redhat/{}/x86_64/{}{}/{}".format(
                root_url, os_version, minor_url, salt_release, GPG_FILE
            )
        )

    cmds.append(
        "curl -fsSL -o /etc/yum.repos.d/salt.repo {}/redhat/{}/x86_64/{}{}.repo".format(
            root_url, os_version, minor_url, salt_release
        )
    )
    cmds.append(
        [
            "sh",
            "-c",
            "echo baseurl={}/redhat/{}/x86_64/{}{}  >> /etc/yum.repos.d/salt.repo".format(
                root_url, os_version, minor_url, salt_release
            ),
        ]
    )
    cmds.append(
        [
            "sh",
            "-c",
            "echo gpgkey={}/redhat/{}/x86_64/{}{}/{} >> /etc/yum.repos.d/salt.repo".format(
                root_url, os_version, minor_url, salt_release, GPG_FILE
            ),
        ]
    )
    cmds.append("sudo yum clean expire-cache")
    cmds.append(
        "sudo yum install salt-master salt-minion salt-ssh salt-syndic salt-cloud salt-api -y"
    )
    return cmds


def setup_debian(os_version, os_codename, root_url, minor_url, salt_release):
    if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
        GPG_FILE = "SALT-PROJECT-GPG-PUBKEY-2023.gpg"
    else:
        GPG_FILE = "salt-archive-keyring.gpg"

    cmds = [
        "apt-get update -y",
        "apt-get install sudo -y",
        "apt-get install curl -y",
        "sudo curl -fsSL -o /usr/share/keyrings/{} {}/debian/{}/amd64/{}{}/{}".format(
            GPG_FILE, root_url, os_version, minor_url, salt_release, GPG_FILE
        ),
        [
            "sh",
            "-c",
            'echo "deb [signed-by=/usr/share/keyrings/{} arch=amd64] {}/debian/{}/amd64/{}{} {} main" | sudo tee /etc/apt/sources.list.d/salt.list'.format(
                GPG_FILE, root_url, os_version, minor_url, salt_release, os_codename
            ),
        ],
        "sudo apt-get update",
        "sudo apt-get install salt-master salt-minion salt-ssh salt-syndic salt-cloud salt-api -y",
    ]
    return cmds


def setup_ubuntu(os_version, os_codename, root_url, minor_url, salt_release):
    if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
        GPG_FILE = "SALT-PROJECT-GPG-PUBKEY-2023.gpg"
    else:
        GPG_FILE = "salt-archive-keyring.gpg"

    cmds = [
        "apt-get update -y",
        "apt-get install sudo -y",
        "apt-get install curl -y",
        "sudo curl -fsSL -o /usr/share/keyrings/{} {}/ubuntu/{}/amd64/{}{}/{}".format(
            GPG_FILE, root_url, os_version, minor_url, salt_release, GPG_FILE
        ),
        [
            "sh",
            "-c",
            'echo "deb [signed-by=/usr/share/keyrings/{} arch=amd64] {}/ubuntu/{}/amd64/{}{} {} main" | sudo tee /etc/apt/sources.list.d/salt.list'.format(
                GPG_FILE, root_url, os_version, minor_url, salt_release, os_codename
            ),
        ],
        "sudo apt-get update",
        "sudo apt-get install salt-master salt-minion salt-ssh salt-syndic salt-cloud salt-api -y",
    ]

    return cmds


@pytest.fixture(scope="module")
def setup_macos(root_url, minor_url, salt_release):
    mac_pkg = f"salt-{salt_release}-macos-x86_64.pkg"
    mac_pkg_url = f"{root_url}/macos/{salt_release}/{mac_pkg}"
    mac_pkg_path = f"/tmp/{mac_pkg}"

    # We should be able to issue a --help without being root
    ret = subprocess.run(
        ["curl", "-fsSL", "-o", f"/tmp/{mac_pkg}", f"{mac_pkg_url}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert ret.returncode == 0

    ret = subprocess.run(
        ["installer", "-pkg", mac_pkg_path, "-target", "/"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert ret.returncode == 0

    yield


@pytest.fixture(scope="module")
def setup_windows(root_url, minor_url, salt_release):
    win_pkg = f"salt-{salt_release}-windows-amd64.exe"
    win_pkg_url = f"{root_url}/windows/{salt_release}/{win_pkg}"
    pkg_path = pathlib.Path(r"C:\TEMP", win_pkg)
    pkg_path.parent.mkdir(exist_ok=True)
    root_dir = pathlib.Path(r"C:\Program Files\Salt Project\Salt")
    ssm_bin = root_dir / "bin" / "ssm_bin"

    ret = requests.get(win_pkg_url)
    with open(pkg_path, "wb") as fp:
        fp.write(ret.content)
    ret = subprocess.run(
        [pkg_path, "/start-minion=0", "/S"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert ret.returncode == 0

    log.debug("Removing installed salt-minion service")
    ret = subprocess.run(
        ["cmd", "/c", str(ssm_bin), "remove", "salt-minion", "confirm"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert ret.returncode == 0


@pytest.mark.parametrize("salt_test_command", get_salt_test_commands())
@pytest.mark.skip_if_binaries_missing("dockerd")
@pytest.mark.skip_unless_on_linux
def test_download_linux(
    salt_test_command, pkg_container, root_url, minor_url, salt_release
):
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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert ret.returncode == 0
