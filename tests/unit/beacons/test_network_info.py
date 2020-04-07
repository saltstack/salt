# coding: utf-8

# Python libs
from __future__ import absolute_import

import logging
from collections import namedtuple

# Salt libs
import salt.beacons.network_info as network_info
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch

# Salt testing libs
from tests.support.unit import TestCase

log = logging.getLogger(__name__)

STUB_NET_IO_COUNTERS = {
    "eth0": namedtuple(
        "snetio",
        "bytes_sent bytes_recv \
                                           packets_sent packets_recv \
                                           errin errout \
                                           dropin \
                                           dropout",
    )(93662618, 914626664, 465694, 903802, 0, 0, 0, 0)
}


class NetworkInfoBeaconTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test case for salt.beacons.network_info
    """

    def setup_loader_modules(self):
        return {network_info: {"__context__": {}, "__salt__": {}}}

    def test_non_list_config(self):
        config = {}

        ret = network_info.validate(config)

        self.assertEqual(
            ret, (False, "Configuration for network_info beacon must be a list.")
        )

    def test_empty_config(self):
        config = [{}]

        ret = network_info.validate(config)

        self.assertEqual(ret, (True, "Valid beacon configuration"))

    def test_network_info_equal(self):
        with patch(
            "salt.utils.psutil_compat.net_io_counters",
            MagicMock(return_value=STUB_NET_IO_COUNTERS),
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

            self.assertEqual(ret, (True, "Valid beacon configuration"))

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
            self.assertEqual(ret, _expected_return)

    def test_network_info_greater_than(self):
        with patch(
            "salt.utils.psutil_compat.net_io_counters",
            MagicMock(return_value=STUB_NET_IO_COUNTERS),
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

            self.assertEqual(ret, (True, "Valid beacon configuration"))

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
            self.assertEqual(ret, _expected_return)
