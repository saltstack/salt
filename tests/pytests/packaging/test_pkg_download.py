"""
Test Salt Pkg Uploads
"""
import logging
import os

import attr
import pytest
from saltfactories.utils import random_string

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd"),
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
            "image": "ubuntu:18.04",
            "os_type": "ubuntu",
            "os_version": 18.04,
            "os_codename": "bionic",
            "container_id": "ubuntu_18_04",
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
def upload_test_image(request):
    return request.param


def get_salt_test_commands():
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
def pkg_container(salt_factories, upload_test_image, root_url, minor_url, salt_release):
    container = salt_factories.get_container(
        random_string("{}_".format(upload_test_image.container_id)),
        upload_test_image.name,
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    with container.started():
        setup_func = globals()["setup_{}".format(upload_test_image.os_type)]
        try:
            cmds = setup_func(
                upload_test_image.os_version,
                upload_test_image.os_codename,
                root_url,
                minor_url,
                salt_release,
            )
        except KeyError:
            pytest.skip("Unable to handle {}.  Skipping.".format(pkg_container.os_type))

        for cmd in cmds:
            res = container.run(cmd)
            assert res.returncode == 0

        upload_test_image.container = container
        yield upload_test_image


@pytest.fixture(scope="module")
def root_url():
    root_url = os.environ.get("SALT_REPO_ROOT_URL", "repo.saltproject.io")
    if "staging" in root_url:
        staging_repo_user = os.environ.get("STAGING_REPO_USER")
        staging_repo_pass = os.environ.get("STAGING_REPO_PASS")
        if not staging_repo_user or not staging_repo_pass:
            pytest.skip(
                "Values for Staging User or Staging Password are unavailable. Skipping."
            )
        root_url = "https://{}:{}@{}/salt/py3".format(
            staging_repo_user, staging_repo_pass, root_url
        )
    else:
        root_url = "https://{}/salt/py3".format(root_url)
    yield root_url


@pytest.fixture(scope="module")
def minor_url():
    minor_url = "minor/"
    yield minor_url


@pytest.fixture(scope="module")
def salt_release():
    salt_release = os.environ.get("SALT_RELEASE", "3005.1")
    yield salt_release


def setup_amazon(os_version, os_codename, root_url, minor_url, salt_release):
    cmds = [
        "pwd",
        "sudo rpm --import {}/amazon/2/x86_64/{}{}/SALTSTACK-GPG-KEY.pub".format(
            root_url, minor_url, salt_release
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
    cmds = []
    if os_version >= 9:
        cmds.append(
            "sudo rpm --import {}/redhat/{}/x86_64/{}{}/SALTSTACK-GPG-KEY2.pub".format(
                root_url, os_version, minor_url, salt_release
            )
        )
    else:
        cmds.append(
            "sudo rpm --import {}/redhat/{}/x86_64/{}{}/SALTSTACK-GPG-KEY.pub".format(
                root_url, os_version, minor_url, salt_release
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
            "echo gpgkey={}/redhat/{}/x86_64/{}{}/SALTSTACK-GPG-KEY.pub >> /etc/yum.repos.d/salt.repo".format(
                root_url, os_version, minor_url, salt_release
            ),
        ]
    )
    cmds.append("sudo yum clean expire-cache")
    cmds.append(
        "sudo yum install salt-master salt-minion salt-ssh salt-syndic salt-cloud salt-api -y"
    )
    return cmds


def setup_debian(os_version, os_codename, root_url, minor_url, salt_release):
    cmds = [
        "apt-get update -y",
        "apt-get install sudo -y",
        "apt-get install curl -y",
        "sudo curl -fsSL -o /usr/share/keyrings/salt-archive-keyring.gpg {}/debian/{}/amd64/{}{}/salt-archive-keyring.gpg".format(
            root_url, os_version, minor_url, salt_release
        ),
        [
            "sh",
            "-c",
            'echo "deb [signed-by=/usr/share/keyrings/salt-archive-keyring.gpg arch=amd64] {}/debian/{}/amd64/{}{} {} main" | sudo tee /etc/apt/sources.list.d/salt.list'.format(
                root_url, os_version, minor_url, salt_release, os_codename
            ),
        ],
        "sudo apt-get update",
        "sudo apt-get install salt-master salt-minion salt-ssh salt-syndic salt-cloud salt-api -y",
    ]
    return cmds


def setup_ubuntu(os_version, os_codename, root_url, minor_url, salt_release):
    cmds = [
        "apt-get update -y",
        "apt-get install sudo -y",
        "apt-get install curl -y",
        "sudo curl -fsSL -o /usr/share/keyrings/salt-archive-keyring.gpg {}/ubuntu/{}/amd64/{}{}/salt-archive-keyring.gpg".format(
            root_url, os_version, minor_url, salt_release
        ),
        [
            "sh",
            "-c",
            'echo "deb [signed-by=/usr/share/keyrings/salt-archive-keyring.gpg arch=amd64] {}/ubuntu/{}/amd64/{}{} {} main" | sudo tee /etc/apt/sources.list.d/salt.list'.format(
                root_url, os_version, minor_url, salt_release, os_codename
            ),
        ],
        "sudo apt-get update",
        "sudo apt-get install salt-master salt-minion salt-ssh salt-syndic salt-cloud salt-api -y",
    ]

    return cmds


@pytest.mark.parametrize("salt_test_command", get_salt_test_commands())
def test_download(salt_test_command, pkg_container, root_url, minor_url, salt_release):
    """
    Test downloading of Salt packages and running various commands
    """
    res = pkg_container.container.run(salt_test_command)
    assert res.returncode == 0
