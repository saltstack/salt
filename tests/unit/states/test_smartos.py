# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.smartos as smartos
from salt.utils.odict import OrderedDict

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase


class SmartOsTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.states.smartos
    """

    def setup_loader_modules(self):
        return {smartos: {"__opts__": {"test": False}}}

    def test_config_present_does_not_exist(self):
        """
        Test salt.states.smartos.config_present
        when the config files does not exist
        """
        name = "test"
        value = "test_value"
        with patch("os.path.isfile", return_value=False):
            with patch("salt.utils.atomicfile.atomic_open", side_effect=IOError):
                ret = smartos.config_present(name=name, value=value)
        assert not ret["result"]
        assert ret[
            "comment"
        ] == 'Could not add property {0} with value "{1}" to config'.format(name, value)

    def test_parse_vmconfig_vrrp(self):
        """
        Test _parse_vmconfig's vrid -> mac convertor

        SmartOS will always use a mac based on the vrrp_vrid,
        so we will replace the provided mac with the one based
        on this value.

        Doing so ensures that 'old' nics are removed and 'new'
        nics get added as these actions are keyed on the mac
        property.
        """
        # NOTE: vmconfig is not a full vmadm payload,
        #       this is not an issue given we are only testing
        #       the vrrp_vrid to mac conversions
        ret = smartos._parse_vmconfig(
            OrderedDict(
                [
                    (
                        "nics",
                        OrderedDict(
                            [
                                (
                                    "00:00:5e:00:01:01",
                                    OrderedDict(
                                        [
                                            ("vrrp_vrid", 1),
                                            ("vrrp_primary_ip", "12.34.5.6"),
                                        ]
                                    ),
                                ),
                                (
                                    "00:00:5e:00:01:24",
                                    OrderedDict(
                                        [
                                            ("vrrp_vrid", 240),
                                            ("vrrp_primary_ip", "12.34.5.6"),
                                        ]
                                    ),
                                ),
                                (
                                    "00:22:06:00:00:01",
                                    OrderedDict([("ips", ["12.34.5.6/24"])]),
                                ),
                            ]
                        ),
                    )
                ]
            ),
            {"nics": "mac"},
        )

        # NOTE: nics.0 is a vrrp nic with correct mac (check mac == vrid based -> unchanged)
        assert ret["nics"][0]["mac"] == "00:00:5e:00:01:01"

        # NOTE: nics.1 is a vrrp nic with incorrect mac (check mac == vrid based -> changed)
        assert ret["nics"][1]["mac"] == "00:00:5e:00:01:f0"

        # NOTE: nics.2 was not a vrrp nic (check mac was not changed)
        assert ret["nics"][2]["mac"] == "00:22:06:00:00:01"
