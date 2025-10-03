"""
    :codeauthor: `Gareth J. Greenaway <gareth@saltstack.com>`

    tests.unit.cloud.clouds.digitalocean_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import logging

import pytest

from salt.cloud.clouds import digitalocean
from salt.exceptions import SaltCloudSystemExit
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def vpc_list():
    return {
        "vpcs": [
            {
                "name": "env.prod-vpc",
                "description": "VPC for production environment",
                "region": "nyc1",
                "ip_range": "10.10.10.0/24",
                "id": "5a4981aa-9653-4bd1-bef5-d6bff52042e4",
                "urn": "do:vpc:5a4981aa-9653-4bd1-bef5-d6bff52042e4",
                "default": False,
                "created_at": "2020-03-13T19:20:47.442049222Z",
            },
            {
                "id": "e0fe0f4d-596a-465e-a902-571ce57b79fa",
                "urn": "do:vpc:e0fe0f4d-596a-465e-a902-571ce57b79fa",
                "name": "default-nyc1",
                "description": "",
                "region": "nyc1",
                "ip_range": "10.102.0.0/20",
                "created_at": "2020-03-13T19:29:20Z",
                "default": True,
            },
            {
                "id": "d455e75d-4858-4eec-8c95-da2f0a5f93a7",
                "urn": "do:vpc:d455e75d-4858-4eec-8c95-da2f0a5f93a7",
                "name": "default-nyc3",
                "description": "",
                "region": "nyc3",
                "ip_range": "10.100.0.0/20",
                "created_at": "2019-11-19T22:19:35Z",
                "default": True,
            },
        ],
        "links": {},
        "meta": {"total": 3},
    }


def test_reboot_no_call():
    """
    Tests that a SaltCloudSystemExit is raised when
    kwargs that are provided do not include an action.
    """
    with pytest.raises(SaltCloudSystemExit) as excinfo:
        digitalocean.reboot(name="fake_name")

    assert "The reboot action must be called with -a or --action." == str(excinfo.value)


def test__get_vpc_by_name(vpc_list):
    default_nyc1 = {
        "default-nyc1": {
            "default": True,
            "description": "",
            "id": "e0fe0f4d-596a-465e-a902-571ce57b79fa",
            "ip_range": "10.102.0.0/20",
            "name": "default-nyc1",
            "region": "nyc1",
            "urn": "do:vpc:e0fe0f4d-596a-465e-a902-571ce57b79fa",
        }
    }
    with patch(
        "salt.cloud.clouds.digitalocean.query", MagicMock(return_value=vpc_list)
    ):
        ret = digitalocean._get_vpc_by_name("default-nyc1")
        assert ret == default_nyc1
        ret = digitalocean._get_vpc_by_name("NOT-THERE")
        assert ret is None
