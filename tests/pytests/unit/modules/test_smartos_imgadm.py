"""
    :codeauthor: Jorge Schrauwen <info@blackdot.be>

    TestCase for salt.modules.smartos_imgadm module
"""


import pytest

import salt.modules.smartos_imgadm as imgadm
from salt.modules.smartos_imgadm import _parse_image_meta


@pytest.fixture
def image_orphan():
    return {
        "manifest": {"uuid": "07f360fd-12d5-e624-a279-eb8a15b630f6"},
        "zpool": "zones",
        "cloneNames": [],
        "clones": 0,
    }


@pytest.fixture
def image_native():
    return {
        "manifest": {
            "v": 2,
            "uuid": "9d91e334-3bcf-11e8-bb0b-e7b49eb01e38",
            "owner": "00000000-0000-0000-0000-000000000000",
            "name": "pkgbuild",
            "version": "18.1.0",
            "state": "active",
            "disabled": False,
            "public": True,
            "published_at": "2018-04-09T08:25:52Z",
            "type": "zone-dataset",
            "os": "smartos",
            "files": [
                {
                    "sha1": "5efaf95b7f226eb09c7d5e6c3734f8aa654b811d",
                    "size": 465411979,
                    "compression": "gzip",
                }
            ],
            "description": "A SmartOS image pre-configured for building pkgsrc packages.",
            "homepage": "https://docs.joyent.com/images/smartos/pkgbuild",
            "urn": "sdc:sdc:pkgbuild:18.1.0",
            "requirements": {
                "min_platform": {"7.0": "20141030T081701Z"},
                "networks": [{"name": "net0", "description": "public"}],
            },
            "tags": {"role": "os", "group": "pkgbuild"},
        },
        "zpool": "zones",
        "source": "https://images.joyent.com",
        "cloneNames": ["zones/dda70f61-70fe-65e7-cf70-d878d69442d4"],
        "clones": 1,
    }


@pytest.fixture
def image_lx():
    return {
        "manifest": {
            "v": 2,
            "uuid": "05140a7e-279f-11e6-aedf-47d4f69d2887",
            "owner": "00000000-0000-0000-0000-000000000000",
            "name": "ubuntu-16.04",
            "version": "20160601",
            "state": "active",
            "disabled": False,
            "public": True,
            "published_at": "2016-06-01T02:17:41Z",
            "type": "lx-dataset",
            "os": "linux",
            "files": [
                {
                    "sha1": "d342f137c5ccef0702ec479acb63c196cf81b38a",
                    "size": 134969110,
                    "compression": "gzip",
                }
            ],
            "description": (
                "Container-native Ubuntu 16.04 64-bit image. Built to run on containers"
                " with bare metal speed, while offering all the services of a typical unix"
                " host."
            ),
            "homepage": "https://docs.joyent.com/images/container-native-linux",
            "requirements": {
                "networks": [{"name": "net0", "description": "public"}],
                "min_platform": {"7.0": "20160225T122859Z"},
                "brand": "lx",
            },
            "tags": {"role": "os", "kernel_version": "4.3.0"},
        },
        "zpool": "zones",
        "source": "https://images.joyent.com",
        "cloneNames": ["zones/e4c1f6b5-4429-e6c2-ae2a-d6aa58bdeebb"],
        "clones": 1,
    }


@pytest.fixture
def image_zvol():
    return {
        "manifest": {
            "v": 2,
            "uuid": "ac99517a-72ac-44c0-90e6-c7ce3d944a0a",
            "owner": "00000000-0000-0000-0000-000000000000",
            "name": "ubuntu-certified-18.04",
            "version": "20180808",
            "state": "active",
            "disabled": False,
            "public": True,
            "published_at": "2018-10-11T12:45:24.804Z",
            "type": "zvol",
            "os": "linux",
            "files": [
                {
                    "sha1": "9f7704969507bd97e160a8f42a3631487644e457",
                    "size": 372276887,
                    "compression": "gzip",
                }
            ],
            "description": (
                "Ubuntu 18.04 LTS (20180808 64-bit). Certified Ubuntu Server Cloud Image"
                " from Canonical. For kvm and bhyve."
            ),
            "homepage": "https://docs.joyent.com/images/linux/ubuntu-certified",
            "requirements": {
                "min_platform": {"7.0": "20150929T232348Z"},
                "networks": [{"name": "net0", "description": "public"}],
                "ssh_key": True,
            },
            "nic_driver": "virtio",
            "disk_driver": "virtio",
            "cpu_type": "host",
            "image_size": 10240,
            "tags": {"default_user": "ubuntu", "role": "os"},
        },
        "zpool": "zones",
        "source": "https://images.joyent.com",
        "cloneNames": [],
        "clones": 0,
    }


@pytest.fixture
def image_docker():
    return {
        "manifest": {
            "v": 2,
            "uuid": "4a3db8cb-0e94-ae23-588c-ee7934088927",
            "owner": "00000000-0000-0000-0000-000000000000",
            "name": "docker-layer",
            "version": "62487cf6a7f6",
            "disabled": False,
            "public": True,
            "published_at": "2019-03-23T01:32:25.320Z",
            "type": "docker",
            "os": "linux",
            "description": '/bin/sh -c #(nop)  CMD ["/bin/bash" "/opt/start.sh" "-bash"]',
            "tags": {
                "docker:repo": "busybox42/zimbra-docker-centos",
                "docker:id": "sha256:62487cf6a7f698af4edc20707e14b1b3bba13b98bea3375f05af04859a30b222",
                "docker:architecture": "amd64",
                "docker:tag:latest": True,
                "docker:config": {
                    "Cmd": ["/bin/bash", "/opt/start.sh", "-bash"],
                    "Entrypoint": None,
                    "Env": [
                        "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
                    ],
                    "WorkingDir": "",
                },
            },
            "origin": "2f0c529b-7bab-28d1-ff34-bdc9281b7a4b",
        },
        "zpool": "zones",
        "source": "https://docker.io",
        "cloneNames": [],
        "clones": 0,
    }


@pytest.fixture
def configure_loader_modules():
    return {imgadm: {}}


def test_parse_image_meta_orphan(image_orphan):
    """
    Test the internal _parse_image_meta methode
    Feed it an 'orphan' image as we get it from from imgadm list -j
    """
    ret = {"Error": "This looks like an orphaned image, image payload was invalid."}
    assert _parse_image_meta(image_orphan, True) == ret


def test_parse_image_meta_native(image_native):
    """
    Test the internal _parse_image_meta methode
    Feed it an 'native' image as we get it from from imgadm list -j
    """
    ret = {
        "description": ("A SmartOS image pre-configured for building pkgsrc packages."),
        "name": "pkgbuild",
        "os": "smartos",
        "published": "2018-04-09T08:25:52Z",
        "source": "https://images.joyent.com",
        "version": "18.1.0",
    }
    assert _parse_image_meta(image_native, True) == ret


def test_parse_image_meta_lx(image_lx):
    """
    Test the internal _parse_image_meta methode
    Feed it an 'lx' image as we get it from from imgadm list -j
    """
    ret = {
        "description": (
            "Container-native Ubuntu 16.04 64-bit image. Built to run on "
            "containers with bare metal speed, while offering all the "
            "services of a typical unix host."
        ),
        "name": "ubuntu-16.04",
        "os": "linux",
        "published": "2016-06-01T02:17:41Z",
        "source": "https://images.joyent.com",
        "version": "20160601",
    }
    assert _parse_image_meta(image_lx, True) == ret


def test_parse_image_meta_zvol(image_zvol):
    """
    Test the internal _parse_image_meta methode
    Feed it an 'zvol' image as we get it from from imgadm list -j
    """
    ret = {
        "description": (
            "Ubuntu 18.04 LTS (20180808 64-bit). Certified Ubuntu Server "
            "Cloud Image from Canonical. For kvm and bhyve."
        ),
        "name": "ubuntu-certified-18.04",
        "os": "linux",
        "published": "2018-10-11T12:45:24.804Z",
        "source": "https://images.joyent.com",
        "version": "20180808",
    }
    assert _parse_image_meta(image_zvol, True) == ret


def test_parse_image_meta_docker(image_docker):
    """
    Test the internal _parse_image_meta methode
    Feed it an 'docker' image as we get it from from imgadm list -j
    """
    ret = {
        "description": (
            "Docker image imported from "
            "busybox42/zimbra-docker-centos:latest on "
            "2019-03-23T01:32:25.320Z."
        ),
        "name": "busybox42/zimbra-docker-centos:latest",
        "os": "linux",
        "published": "2019-03-23T01:32:25.320Z",
        "source": "https://docker.io",
        "version": "62487cf6a7f6",
    }
    assert _parse_image_meta(image_docker, True) == ret
