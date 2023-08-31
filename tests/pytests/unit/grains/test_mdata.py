"""
    :codeauthor: :email:`Jorge Schrauwen <sjorge@blackdot.be>`
"""

import pytest

import salt.grains.mdata as mdata
from tests.support.mock import Mock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        mdata: {"__salt__": {}},
    }


def test_user_mdata_missing_cmd_both():
    """
    When both or either of the commands is missing there should
    be no grain output.
    """
    grains_exp_res = {}

    which_mock = Mock(side_effect=[None, None])
    with patch("salt.utils.path.which", which_mock):
        grains_res = mdata._user_mdata()
        assert grains_exp_res == grains_res


def test_user_mdata_missing_cmd_one():
    """
    When both or either of the commands is missing there should
    be no grain output.
    """
    grains_exp_res = {}

    which_mock = Mock(side_effect=["/usr/sbin/mdata-list", None])
    with patch("salt.utils.path.which", which_mock):
        grains_res = mdata._user_mdata()
        assert grains_exp_res == grains_res


def test_user_mdata_empty_list():
    """
    When there are no user grains, there are no mdata-get calls
    so there are also no grains.
    """
    grains_exp_res = {}

    which_mock = Mock(side_effect=["/usr/sbin/mdata-list", "/usr/sbin/mdata-get"])
    cmd_mock = Mock(side_effect=[""])
    with patch("salt.utils.path.which", which_mock), patch.dict(
        mdata.__salt__, {"cmd.run": cmd_mock}
    ):
        grains_res = mdata._user_mdata()
        assert grains_exp_res == grains_res


def test_user_mdata():
    """
    We have a list of two grains, so there should be two mdata-get
    calls, resulting in 2 grains.
    """
    grains_exp_res = {
        "mdata": {
            "multi_text_data": "multi\nline\ntext",
            "simple_text_data": "some text data",
        },
    }

    which_mock = Mock(side_effect=["/usr/sbin/mdata-list", "/usr/sbin/mdata-get"])
    cmd_mock = Mock(
        side_effect=[
            "simple_text_data\nmulti_text_data",
            "some text data",
            "multi\nline\ntext",
        ]
    )
    with patch("salt.utils.path.which", which_mock), patch.dict(
        mdata.__salt__, {"cmd.run": cmd_mock}
    ):
        grains_res = mdata._user_mdata()

        assert grains_exp_res == grains_res


def test_sdc_mdata_missing_cmd_both():
    """
    When both or either of the commands is missing there should
    be no grain output.
    """
    which_mock = Mock(side_effect=[None, None])
    with patch("salt.utils.path.which", which_mock):
        grains = mdata._sdc_mdata()
        assert grains == {}


def test_sdc_mdata_missing_cmd_one():
    """
    When both or either of the commands is missing there should
    be no grain output.
    """
    grains_exp_res = {}

    which_mock = Mock(side_effect=["/usr/sbin/mdata-list", None])
    with patch("salt.utils.path.which", which_mock):
        grains_res = mdata._sdc_mdata()
        assert grains_exp_res == grains_res


def test_sdc_mdata():
    """
    Simulate all mdata_get calls from a test zone.
    """
    grains_exp_res = {
        "mdata": {
            "sdc": {
                "alias": "test",
                "dns_domain": "example.org",
                "hostname": "test_salt",
                "nics": [
                    {
                        "gateway": "10.12.3.1",
                        "gateways": ["10.12.3.1"],
                        "interface": "net0",
                        "ip": "10.12.3.123",
                        "ips": ["10.12.3.123/24", "2001:ffff:ffff:123::123/64"],
                        "mac": "00:00:00:00:00:01",
                        "mtu": 1500,
                        "netmask": "255.255.255.0",
                        "nic_tag": "trunk",
                        "primary": True,
                        "vlan_id": 123,
                    }
                ],
                "resolvers": ["10.12.3.1", "2001:ffff:ffff:123::1"],
                "routes": [],
                "server_uuid": "00000000-0000-0000-0000-000123456789",
                "uuid": "bae504b1-4594-47de-e2ed-e4f454776689",
            },
        },
    }

    which_mock = Mock(side_effect=["/usr/sbin/mdata-list", "/usr/sbin/mdata-get"])
    cmd_mock = Mock(
        side_effect=[
            "bae504b1-4594-47de-e2ed-e4f454776689",
            "00000000-0000-0000-0000-000123456789",
            "No metadata for 'sdc:datacenter_name'",
            "test_salt",
            "example.org",
            "test",
            '["10.12.3.1","2001:ffff:ffff:123::1"]',
            '[{"interface":"net0","mac":"00:00:00:00:00:01","vlan_id":123,"nic_tag":"trunk","gateway":"10.12.3.1","gateways":["10.12.3.1"],"netmask":"255.255.255.0","ip":"10.12.3.123","ips":["10.12.3.123/24","2001:ffff:ffff:123::123/64"],"mtu":1500,"primary":true}]',
            "[]",
        ]
    )
    with patch("salt.utils.path.which", which_mock), patch.dict(
        mdata.__salt__, {"cmd.run": cmd_mock}
    ):
        grains_res = mdata._sdc_mdata()

        assert grains_exp_res == grains_res
