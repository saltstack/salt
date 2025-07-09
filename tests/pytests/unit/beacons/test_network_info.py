"""
    tests.pytests.unit.beacons.test_network_info
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Network info beacon test cases
"""

from collections import namedtuple

import pytest

import salt.beacons.network_info as network_info
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {network_info: {"__context__": {}, "__salt__": {}}}


@pytest.fixture
def stub_net_io_counters():
    return {
        "eth0": namedtuple(
            "snetio",
            "bytes_sent bytes_recv packets_sent packets_recv errin errout dropin"
            " dropout",
        )(93662618, 914626664, 465694, 903802, 0, 0, 0, 0)
    }


def test_non_list_config():
    config = {}

    ret = network_info.validate(config)
    assert ret == (False, "Configuration for network_info beacon must be a list.")


def test_empty_config():
    config = [{}]

    ret = network_info.validate(config)
    assert ret == (True, "Valid beacon configuration")


def test_network_info_equal(stub_net_io_counters):
    with patch(
        "psutil.net_io_counters",
        MagicMock(return_value=stub_net_io_counters),
    ):
        config = [
            {
                "interfaces": {
                    "eth0": {
                        "type": "equal",
                        "bytes_sent": 914626664,
                        "bytes_recv": 93662618,
                        "packets_sent": 465694,
                        "packets_recv": 903802,
                        "errin": 0,
                        "errout": 0,
                        "dropin": 0,
                        "dropout": 0,
                    }
                }
            }
        ]

        ret = network_info.validate(config)
        assert ret == (True, "Valid beacon configuration")

        _expected_return = [
            {
                "interface": "eth0",
                "network_info": {
                    "bytes_recv": 914626664,
                    "bytes_sent": 93662618,
                    "dropin": 0,
                    "dropout": 0,
                    "errin": 0,
                    "errout": 0,
                    "packets_recv": 903802,
                    "packets_sent": 465694,
                },
            }
        ]

        ret = network_info.beacon(config)
        assert ret == _expected_return


def test_network_info_greater_than(stub_net_io_counters):
    with patch(
        "psutil.net_io_counters",
        MagicMock(return_value=stub_net_io_counters),
    ):
        config = [
            {
                "interfaces": {
                    "eth0": {
                        "type": "greater",
                        "bytes_sent": 100000,
                        "bytes_recv": 100000,
                        "packets_sent": 100000,
                        "packets_recv": 100000,
                        "errin": 0,
                        "errout": 0,
                        "dropin": 0,
                        "dropout": 0,
                    }
                }
            }
        ]

        ret = network_info.validate(config)
        assert ret == (True, "Valid beacon configuration")

        _expected_return = [
            {
                "interface": "eth0",
                "network_info": {
                    "bytes_recv": 914626664,
                    "bytes_sent": 93662618,
                    "dropin": 0,
                    "dropout": 0,
                    "errin": 0,
                    "errout": 0,
                    "packets_recv": 903802,
                    "packets_sent": 465694,
                },
            }
        ]

        ret = network_info.beacon(config)
        assert ret == _expected_return
