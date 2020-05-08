# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import os

# Import 3rd-party libs
import jinja2.exceptions
import salt.modules.rh_ip as rh_ip
from salt.ext import six

# Import Salt Libs
from salt.ext.six.moves import range

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class RhipTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.rh_ip
    """

    def setup_loader_modules(self):
        return {rh_ip: {}}

    def test_error_message_iface_should_process_non_str_expected(self):
        values = [1, True, False, "no-kaboom"]
        iface = "ethtest"
        option = "test"
        msg = rh_ip._error_msg_iface(iface, option, values)
        self.assertTrue(msg.endswith("[1|True|False|no-kaboom]"), msg)

    def test_error_message_network_should_process_non_str_expected(self):
        values = [1, True, False, "no-kaboom"]
        msg = rh_ip._error_msg_network("fnord", values)
        self.assertTrue(msg.endswith("[1|True|False|no-kaboom]"), msg)

    def test_build_bond(self):
        """
        Test to create a bond script in /etc/modprobe.d with the passed
        settings and load the bonding kernel module.
        """
        with patch.dict(rh_ip.__grains__, {"osrelease": "osrelease"}):
            with patch.object(rh_ip, "_parse_settings_bond", MagicMock()):
                mock = jinja2.exceptions.TemplateNotFound("foo")
                with patch.object(
                    jinja2.Environment, "get_template", MagicMock(side_effect=mock)
                ):
                    self.assertEqual(rh_ip.build_bond("iface"), "")

                with patch.dict(
                    rh_ip.__salt__, {"kmod.load": MagicMock(return_value=None)}
                ):
                    with patch.object(rh_ip, "_write_file_iface", return_value=None):
                        with patch.object(rh_ip, "_read_temp", return_value="A"):
                            self.assertEqual(rh_ip.build_bond("iface", test="A"), "A")

                        with patch.object(rh_ip, "_read_file", return_value="A"):
                            self.assertEqual(rh_ip.build_bond("iface", test=None), "A")

    def test_build_interface(self):
        """
        Test to build an interface script for a network interface.
        """
        with patch.dict(rh_ip.__grains__, {"os": "Fedora", "osmajorrelease": 26}):
            with patch.object(rh_ip, "_raise_error_iface", return_value=None):
                self.assertRaises(
                    AttributeError, rh_ip.build_interface, "iface", "slave", True
                )

                with patch.dict(
                    rh_ip.__salt__, {"network.interfaces": lambda: {"eth": True}}
                ):
                    self.assertRaises(
                        AttributeError,
                        rh_ip.build_interface,
                        "iface",
                        "eth",
                        True,
                        netmask="255.255.255.255",
                        prefix=32,
                        test=True,
                    )
                    self.assertRaises(
                        AttributeError,
                        rh_ip.build_interface,
                        "iface",
                        "eth",
                        True,
                        ipaddrs=["A"],
                        test=True,
                    )
                    self.assertRaises(
                        AttributeError,
                        rh_ip.build_interface,
                        "iface",
                        "eth",
                        True,
                        ipv6addrs=["A"],
                        test=True,
                    )

        for osrelease in range(5, 8):
            with patch.dict(
                rh_ip.__grains__,
                {"os": "RedHat", "osrelease": six.text_type(osrelease)},
            ):
                with patch.object(rh_ip, "_raise_error_iface", return_value=None):
                    with patch.object(rh_ip, "_parse_settings_bond", MagicMock()):
                        mock = jinja2.exceptions.TemplateNotFound("foo")
                        with patch.object(
                            jinja2.Environment,
                            "get_template",
                            MagicMock(side_effect=mock),
                        ):
                            self.assertEqual(
                                rh_ip.build_interface("iface", "vlan", True), ""
                            )

                        with patch.object(rh_ip, "_read_temp", return_value="A"):
                            with patch.object(
                                jinja2.Environment, "get_template", MagicMock()
                            ):
                                self.assertEqual(
                                    rh_ip.build_interface(
                                        "iface", "vlan", True, test="A"
                                    ),
                                    "A",
                                )

                                with patch.object(
                                    rh_ip, "_write_file_iface", return_value=None
                                ):
                                    with patch.object(
                                        os.path, "join", return_value="A"
                                    ):
                                        with patch.object(
                                            rh_ip, "_read_file", return_value="A"
                                        ):
                                            self.assertEqual(
                                                rh_ip.build_interface(
                                                    "iface", "vlan", True
                                                ),
                                                "A",
                                            )
                                            if osrelease > 6:
                                                with patch.dict(
                                                    rh_ip.__salt__,
                                                    {
                                                        "network.interfaces": lambda: {
                                                            "eth": True
                                                        }
                                                    },
                                                ):
                                                    self.assertEqual(
                                                        rh_ip.build_interface(
                                                            "iface",
                                                            "eth",
                                                            True,
                                                            ipaddrs=["127.0.0.1/8"],
                                                        ),
                                                        "A",
                                                    )
                                                    self.assertEqual(
                                                        rh_ip.build_interface(
                                                            "iface",
                                                            "eth",
                                                            True,
                                                            ipv6addrs=["fc00::1/128"],
                                                        ),
                                                        "A",
                                                    )

    def test_build_routes(self):
        """
        Test to build a route script for a network interface.
        """
        with patch.dict(rh_ip.__grains__, {"osrelease": "5.0"}):
            with patch.object(rh_ip, "_parse_routes", MagicMock()):
                mock = jinja2.exceptions.TemplateNotFound("foo")
                with patch.object(
                    jinja2.Environment, "get_template", MagicMock(side_effect=mock)
                ):
                    self.assertEqual(rh_ip.build_routes("iface"), "")

                with patch.object(jinja2.Environment, "get_template", MagicMock()):
                    with patch.object(rh_ip, "_read_temp", return_value=["A"]):
                        self.assertEqual(rh_ip.build_routes("i", test="t"), ["A", "A"])

                    with patch.object(rh_ip, "_read_file", return_value=["A"]):
                        with patch.object(os.path, "join", return_value="A"):
                            with patch.object(
                                rh_ip, "_write_file_iface", return_value=None
                            ):
                                self.assertEqual(
                                    rh_ip.build_routes("i", test=None), ["A", "A"]
                                )

    def test_down(self):
        """
        Test to shutdown a network interface
        """
        with patch.dict(rh_ip.__salt__, {"cmd.run": MagicMock(return_value="A")}):
            self.assertEqual(rh_ip.down("iface", "iface_type"), "A")

        self.assertEqual(rh_ip.down("iface", "slave"), None)

    def test_get_bond(self):
        """
        Test to return the content of a bond script
        """
        with patch.object(os.path, "join", return_value="A"):
            with patch.object(rh_ip, "_read_file", return_value="A"):
                self.assertEqual(rh_ip.get_bond("iface"), "A")

    def test_get_interface(self):
        """
        Test to return the contents of an interface script
        """
        with patch.object(os.path, "join", return_value="A"):
            with patch.object(rh_ip, "_read_file", return_value="A"):
                self.assertEqual(rh_ip.get_interface("iface"), "A")

    def test__parse_settings_eth_hwaddr_and_macaddr(self):
        """
        Test that an AttributeError is thrown when hwaddr and macaddr are
        passed together. They cannot be used together
        """
        opts = {"hwaddr": 1, "macaddr": 2}

        self.assertRaises(
            AttributeError,
            rh_ip._parse_settings_eth,
            opts=opts,
            iface_type="eth",
            enabled=True,
            iface="eth0",
        )

    def test__parse_settings_eth_hwaddr(self):
        """
        Make sure hwaddr gets added when parsing opts
        """
        opts = {"hwaddr": "AA:BB:CC:11:22:33"}
        with patch.dict(rh_ip.__salt__, {"network.interfaces": MagicMock()}):
            results = rh_ip._parse_settings_eth(
                opts=opts, iface_type="eth", enabled=True, iface="eth0"
            )
        self.assertIn("hwaddr", results)
        self.assertEqual(results["hwaddr"], opts["hwaddr"])

    def test__parse_settings_eth_macaddr(self):
        """
        Make sure macaddr gets added when parsing opts
        """
        opts = {"macaddr": "AA:BB:CC:11:22:33"}
        with patch.dict(rh_ip.__salt__, {"network.interfaces": MagicMock()}):
            results = rh_ip._parse_settings_eth(
                opts=opts, iface_type="eth", enabled=True, iface="eth0"
            )
        self.assertIn("macaddr", results)
        self.assertEqual(results["macaddr"], opts["macaddr"])

    def test_up(self):
        """
        Test to start up a network interface
        """
        with patch.dict(rh_ip.__salt__, {"cmd.run": MagicMock(return_value="A")}):
            self.assertEqual(rh_ip.up("iface", "iface_type"), "A")

        self.assertEqual(rh_ip.up("iface", "slave"), None)

    def test_get_routes(self):
        """
        Test to return the contents of the interface routes script.
        """
        with patch.object(os.path, "join", return_value="A"):
            with patch.object(rh_ip, "_read_file", return_value=["A"]):
                self.assertEqual(rh_ip.get_routes("iface"), ["A", "A"])

    def test_get_network_settings(self):
        """
        Test to return the contents of the global network script.
        """
        with patch.object(rh_ip, "_read_file", return_value="A"):
            self.assertEqual(rh_ip.get_network_settings(), "A")

    def test_apply_network_settings(self):
        """
        Test to apply global network configuration.
        """
        with patch.dict(
            rh_ip.__salt__, {"service.restart": MagicMock(return_value=True)}
        ):
            self.assertTrue(rh_ip.apply_network_settings())

    def test_build_network_settings(self):
        """
        Test to build the global network script.
        """
        with patch.object(rh_ip, "_parse_rh_config", MagicMock()):
            with patch.object(rh_ip, "_parse_network_settings", MagicMock()):

                mock = jinja2.exceptions.TemplateNotFound("foo")
                with patch.object(
                    jinja2.Environment, "get_template", MagicMock(side_effect=mock)
                ):
                    self.assertEqual(rh_ip.build_network_settings(), "")

                with patch.object(jinja2.Environment, "get_template", MagicMock()):
                    with patch.object(rh_ip, "_read_temp", return_value="A"):
                        self.assertEqual(rh_ip.build_network_settings(test="t"), "A")

                        with patch.object(
                            rh_ip, "_write_file_network", return_value=None
                        ):
                            with patch.object(rh_ip, "_read_file", return_value="A"):
                                self.assertEqual(
                                    rh_ip.build_network_settings(test=None), "A"
                                )
