"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import copy
import os

import jinja2.exceptions

import salt.modules.rh_ip as rh_ip
import salt.modules.systemd_service as service_mod
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, create_autospec, patch
from tests.support.unit import TestCase


class RhipTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.rh_ip
    """

    def setup_loader_modules(self):
        return {rh_ip: {"__grains__": {"os": "CentOS"}}}

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

        for osrelease in range(7, 8):
            with patch.dict(
                rh_ip.__grains__,
                {"os": "RedHat", "osrelease": str(osrelease)},
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

    def test__parse_settings_eth_ethtool_channels(self):
        """
        Make sure channels gets added when parsing opts
        """
        opts = {"channels": {"rx": 4, "tx": 4, "combined": 4, "other": 4}}
        with patch.dict(rh_ip.__grains__, {"num_cpus": 4}), patch.dict(
            rh_ip.__salt__, {"network.interfaces": MagicMock()}
        ):
            results = rh_ip._parse_settings_eth(
                opts=opts, iface_type="eth", enabled=True, iface="eth0"
            )
        self.assertIn("ethtool", results)
        self.assertEqual(results["ethtool"], "-L eth0 rx 4 tx 4 other 4 combined 4")

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
        # This should be pytest.mark.parametrize, when this gets ported to
        # pytest approach. This is just following previous patterns here.
        # Edge cases are 7 & 8
        mock_service = create_autospec(service_mod.restart, return_value=True)
        for majorrelease, expected_service_name in (
            (3, "network"),
            (7, "network"),
            (8, "NetworkManager"),
            (42, "NetworkManager"),
        ):
            with patch.dict(
                rh_ip.__salt__, {"service.restart": mock_service}
            ), patch.dict(
                rh_ip.__grains__,
                {"osmajorrelease": majorrelease},
            ):
                self.assertTrue(rh_ip.apply_network_settings())
                mock_service.assert_called_with(expected_service_name)

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

    def test_build_interface_teamport(self):
        """
        Test that teamport interfaces are properly built
        """
        ifaces = MagicMock(return_value={"eth1": {"hwaddr": "02:42:ac:11:00:02"}})
        dunder_salt = {"network.interfaces": ifaces}
        for version in range(7, 8):
            with patch.dict(
                rh_ip.__grains__, {"osmajorrelease": version, "osrelease": str(version)}
            ), patch.dict(rh_ip.__salt__, dunder_salt):
                ret = sorted(
                    rh_ip.build_interface(
                        "eth1",
                        "teamport",
                        enabled=True,
                        test=True,
                        team_port_config={"prio": 100},
                        team_master="team0",
                    )
                )

            expected = [
                'DEVICE="eth1"',
                'DEVICETYPE="TeamPort"',
                'HWADDR="02:42:ac:11:00:02"',
                'NM_CONTROLLED="no"',
                'ONBOOT="yes"',
                'TEAM_MASTER="team0"',
                "TEAM_PORT_CONFIG='{\"prio\": 100}'",
                'USERCTL="no"',
            ]
            assert ret == expected, ret

    def test_build_interface_team(self):
        """
        Test that team interfaces are properly built
        """
        dunder_salt = {"pkg.version": MagicMock(return_value="1.29-1.el7")}
        for version in range(7, 8):
            with patch.dict(
                rh_ip.__grains__, {"osmajorrelease": version, "osrelease": str(version)}
            ), patch.dict(rh_ip.__salt__, dunder_salt):
                ret = sorted(
                    rh_ip.build_interface(
                        "team0",
                        "team",
                        enabled=True,
                        test=True,
                        ipaddr="1.2.3.4",
                        team_config={"foo": "bar"},
                    )
                )

            expected = [
                'DEVICE="team0"',
                'DEVICETYPE="Team"',
                'IPADDR="1.2.3.4"',
                'NM_CONTROLLED="no"',
                'ONBOOT="yes"',
                'TEAM_CONFIG=\'{"foo": "bar"}\'',
                'USERCTL="no"',
            ]
            assert ret == expected

    @staticmethod
    def _check_common_opts_bond(lines):
        """
        Reduce code duplication by making sure that the expected options are
        present in the config file. Note that this assumes that duplex="full"
        was passed in the kwargs. If it wasn't, then there would be no
        ETHTOOL_OPTS line.
        """
        assert 'DEVICE="bond0"' in lines
        assert 'ETHTOOL_OPTS="duplex full"' in lines
        assert 'NM_CONTROLLED="no"' in lines
        assert 'ONBOOT="yes"' in lines
        assert 'TYPE="Bond"' in lines
        assert 'USERCTL="no"' in lines

    def _validate_miimon_downdelay(self, kwargs):
        """
        Validate that downdelay that is not a multiple of miimon raises an error
        """
        # Make copy of kwargs so we don't modify what was passed in
        kwargs = copy.copy(kwargs)

        # Remove miimon and downdelay (if present) to test invalid input
        for key in ("miimon", "downdelay"):
            kwargs.pop(key, None)

        kwargs["miimon"] = 100
        kwargs["downdelay"] = 201
        try:
            rh_ip.build_interface(
                "bond0",
                "bond",
                enabled=True,
                **kwargs,
            )
        except AttributeError as exc:
            assert "multiple of miimon" in str(exc)
        else:
            raise Exception("AttributeError was not raised")

    def _validate_miimon_conf(self, kwargs, required=True):
        """
        Validate miimon configuration
        """
        # Make copy of kwargs so we don't modify what was passed in
        kwargs = copy.copy(kwargs)

        # Remove miimon and downdelay (if present) to test invalid input
        for key in ("miimon", "downdelay"):
            kwargs.pop(key, None)

        if required:
            # Leaving out miimon should raise an error
            try:
                rh_ip.build_interface(
                    "bond0",
                    "bond",
                    enabled=True,
                    **kwargs,
                )
            except AttributeError as exc:
                assert "miimon" in str(exc)
            else:
                raise Exception("AttributeError was not raised")

        self._validate_miimon_downdelay(kwargs)

    def _get_bonding_opts(self, kwargs):
        results = rh_ip.build_interface(
            "bond0",
            "bond",
            enabled=True,
            **kwargs,
        )
        self._check_common_opts_bond(results)

        for line in results:
            if line.startswith("BONDING_OPTS="):
                return sorted(line.split("=", 1)[-1].strip('"').split())
        raise Exception("BONDING_OPTS not found")

    def _test_mode_0_or_2(self, mode_num=0):
        """
        Modes 0 and 2 share the majority of code, with mode 2 being a superset
        of mode 0. This function will do the proper asserts for the common code
        in these two modes.
        """
        kwargs = {
            "test": True,
            "duplex": "full",
            "slaves": "eth1 eth2",
        }

        if mode_num == 0:
            modes = ("balance-rr", mode_num, str(mode_num))
        else:
            modes = ("balance-xor", mode_num, str(mode_num))

        for version in range(7, 8):
            with patch.dict(
                rh_ip.__grains__, {"osmajorrelease": version, "osrelease": str(version)}
            ):
                for mode in modes:
                    kwargs["mode"] = mode
                    # Remove all miimon/arp settings to test invalid config
                    for key in (
                        "miimon",
                        "downdelay",
                        "arp_interval",
                        "arp_ip_targets",
                    ):
                        kwargs.pop(key, None)

                    # Check that invalid downdelay is handled correctly
                    self._validate_miimon_downdelay(kwargs)

                    # Leaving out miimon and arp_interval should raise an error
                    try:
                        bonding_opts = self._get_bonding_opts(kwargs)
                    except AttributeError as exc:
                        assert "miimon or arp_interval" in str(exc)
                    else:
                        raise Exception("AttributeError was not raised")

                    kwargs["miimon"] = 100
                    kwargs["downdelay"] = 200
                    bonding_opts = self._get_bonding_opts(kwargs)
                    expected = [
                        "downdelay=200",
                        "miimon=100",
                        f"mode={mode_num}",
                        "use_carrier=0",
                    ]
                    assert bonding_opts == expected, bonding_opts

                    # Add arp settings, and test again
                    kwargs["arp_interval"] = 300
                    kwargs["arp_ip_target"] = ["1.2.3.4", "5.6.7.8"]
                    bonding_opts = self._get_bonding_opts(kwargs)
                    expected = [
                        "arp_interval=300",
                        "arp_ip_target=1.2.3.4,5.6.7.8",
                        "downdelay=200",
                        "miimon=100",
                        f"mode={mode_num}",
                        "use_carrier=0",
                    ]
                    assert bonding_opts == expected, bonding_opts

                    # Remove miimon and downdelay and test again
                    del kwargs["miimon"]
                    del kwargs["downdelay"]
                    bonding_opts = self._get_bonding_opts(kwargs)
                    expected = [
                        "arp_interval=300",
                        "arp_ip_target=1.2.3.4,5.6.7.8",
                        f"mode={mode_num}",
                    ]
                    assert bonding_opts == expected, bonding_opts

    def test_build_interface_bond_mode_0(self):
        """
        Test that mode 0 bond interfaces are properly built
        """
        self._test_mode_0_or_2(0)

    def test_build_interface_bond_mode_1(self):
        """
        Test that mode 1 bond interfaces are properly built
        """
        kwargs = {
            "test": True,
            "mode": "active-backup",
            "duplex": "full",
            "slaves": "eth1 eth2",
            "miimon": 100,
            "downdelay": 200,
        }

        for version in range(7, 8):
            with patch.dict(
                rh_ip.__grains__, {"osmajorrelease": version, "osrelease": str(version)}
            ):
                for mode in ("active-backup", 1, "1"):
                    kwargs.pop("primary", None)
                    kwargs["mode"] = mode
                    self._validate_miimon_conf(kwargs)
                    bonding_opts = self._get_bonding_opts(kwargs)
                    expected = [
                        "downdelay=200",
                        "miimon=100",
                        "mode=1",
                        "use_carrier=0",
                    ]
                    assert bonding_opts == expected, bonding_opts

                    # Add a "primary" option and confirm that it shows up in
                    # the bonding opts.
                    kwargs["primary"] = "foo"
                    bonding_opts = self._get_bonding_opts(kwargs)
                    expected = [
                        "downdelay=200",
                        "miimon=100",
                        "mode=1",
                        "primary=foo",
                        "use_carrier=0",
                    ]
                    assert bonding_opts == expected, bonding_opts

    def test_build_interface_bond_mode_2(self):
        """
        Test that mode 2 bond interfaces are properly built
        """
        self._test_mode_0_or_2(2)

        kwargs = {
            "test": True,
            "duplex": "full",
            "slaves": "eth1 eth2",
            "miimon": 100,
            "downdelay": 200,
        }
        for version in range(7, 8):
            with patch.dict(
                rh_ip.__grains__, {"osmajorrelease": version, "osrelease": str(version)}
            ):
                for mode in ("balance-xor", 2, "2"):
                    # Using an invalid hashing algorithm should cause an error
                    # to be raised.
                    kwargs["mode"] = mode
                    kwargs["hashing-algorithm"] = "layer42"
                    try:
                        bonding_opts = self._get_bonding_opts(kwargs)
                    except AttributeError as exc:
                        assert "hashing-algorithm" in str(exc)
                    else:
                        raise Exception("AttributeError was not raised")

                    # Correct the hashing algorithm and re-run
                    kwargs["hashing-algorithm"] = "layer2"
                    bonding_opts = self._get_bonding_opts(kwargs)
                    expected = [
                        "downdelay=200",
                        "miimon=100",
                        "mode=2",
                        "use_carrier=0",
                        "xmit_hash_policy=layer2",
                    ]
                    assert bonding_opts == expected, bonding_opts

    def test_build_interface_bond_mode_3(self):
        """
        Test that mode 3 bond interfaces are properly built
        """
        kwargs = {
            "test": True,
            "duplex": "full",
            "slaves": "eth1 eth2",
            "miimon": 100,
            "downdelay": 200,
        }

        for version in range(7, 8):
            with patch.dict(
                rh_ip.__grains__, {"osmajorrelease": version, "osrelease": str(version)}
            ):
                for mode in ("broadcast", 3, "3"):
                    kwargs["mode"] = mode
                    self._validate_miimon_conf(kwargs)
                    bonding_opts = self._get_bonding_opts(kwargs)
                    expected = [
                        "downdelay=200",
                        "miimon=100",
                        "mode=3",
                        "use_carrier=0",
                    ]
                    assert bonding_opts == expected, bonding_opts

    def test_build_interface_bond_mode_4_xmit(self):
        """
        Test that mode 4 bond interfaces are properly built
        """
        kwargs = {
            "test": True,
            "duplex": "full",
            "slaves": "eth1 eth2",
            "miimon": 100,
            "downdelay": 200,
        }
        valid_lacp_rate = ("fast", "slow", "1", "0")
        valid_ad_select = ("0",)

        for version in range(7, 8):
            with patch.dict(
                rh_ip.__grains__,
                {
                    "osmajorrelease": version,
                    "osrelease": str(version),
                    "os_family": "RedHat",
                },
            ):
                for mode in ("802.3ad", 4, "4"):
                    kwargs["mode"] = mode
                    self._validate_miimon_conf(kwargs)

                    for version in range(7, 8):
                        with patch.dict(rh_ip.__grains__, {"osmajorrelease": version}):
                            # Using an invalid hashing algorithm should cause an error
                            # to be raised.
                            kwargs["hashing-algorithm"] = "layer42"
                            try:
                                bonding_opts = self._get_bonding_opts(kwargs)
                            except AttributeError as exc:
                                assert "hashing-algorithm" in str(exc)
                            else:
                                raise Exception("AttributeError was not raised")

                        hash_alg = "vlan+srcmac"
                        if version == 7:
                            # Using an invalid hashing algorithm should cause an error
                            # to be raised.
                            kwargs["hashing-algorithm"] = hash_alg
                            try:
                                bonding_opts = self._get_bonding_opts(kwargs)
                            except AttributeError as exc:
                                assert "hashing-algorithm" in str(exc)
                            else:
                                raise Exception("AttributeError was not raised")
                        else:
                            # Correct the hashing algorithm and re-run
                            kwargs["hashing-algorithm"] = hash_alg
                            bonding_opts = self._get_bonding_opts(kwargs)
                            expected = [
                                "ad_select=0",
                                "downdelay=200",
                                "lacp_rate=0",
                                "miimon=100",
                                "mode=4",
                                "use_carrier=0",
                                f"xmit_hash_policy={hash_alg}",
                            ]
                            assert bonding_opts == expected, bonding_opts

                        for hash_alg in [
                            "layer2",
                            "layer2+3",
                            "layer3+4",
                            "encap2+3",
                            "encap3+4",
                        ]:
                            # Correct the hashing algorithm and re-run
                            kwargs["hashing-algorithm"] = hash_alg
                            bonding_opts = self._get_bonding_opts(kwargs)
                            expected = [
                                "ad_select=0",
                                "downdelay=200",
                                "lacp_rate=0",
                                "miimon=100",
                                "mode=4",
                                "use_carrier=0",
                                f"xmit_hash_policy={hash_alg}",
                            ]
                            assert bonding_opts == expected, bonding_opts

    def test_build_interface_bond_mode_4_lacp(self):
        """
        Test that mode 4 bond interfaces are properly built
        """
        kwargs = {
            "test": True,
            "duplex": "full",
            "slaves": "eth1 eth2",
            "miimon": 100,
            "downdelay": 200,
        }
        valid_lacp_rate = ("fast", "slow", "1", "0")
        valid_ad_select = ("0",)

        for version in range(7, 8):
            with patch.dict(
                rh_ip.__grains__, {"osmajorrelease": version, "osrelease": str(version)}
            ):
                for mode in ("802.3ad", 4, "4"):
                    kwargs["mode"] = mode
                    self._validate_miimon_conf(kwargs)

                    for lacp_rate in valid_lacp_rate + ("2", "speedy"):
                        for ad_select in valid_ad_select + ("foo",):
                            kwargs["lacp_rate"] = lacp_rate
                            kwargs["ad_select"] = ad_select
                            try:
                                bonding_opts = self._get_bonding_opts(kwargs)
                            except AttributeError as exc:
                                error = str(exc)
                                # Re-raise the exception only if it was
                                # unexpected. It should not be expected when
                                # the lacp_rate or ad_select is valid.
                                if "lacp_rate" in error:
                                    if lacp_rate in valid_lacp_rate:
                                        raise
                                elif "ad_select" in error:
                                    if ad_select in valid_ad_select:
                                        raise
                                else:
                                    raise
                            else:
                                expected = [
                                    f"ad_select={ad_select}",
                                    "downdelay=200",
                                    "lacp_rate={}".format(
                                        "1"
                                        if lacp_rate == "fast"
                                        else "0" if lacp_rate == "slow" else lacp_rate
                                    ),
                                    "miimon=100",
                                    "mode=4",
                                    "use_carrier=0",
                                ]
                                assert bonding_opts == expected, bonding_opts

    def test_build_interface_bond_mode_5(self):
        """
        Test that mode 5 bond interfaces are properly built
        """
        kwargs = {
            "test": True,
            "duplex": "full",
            "slaves": "eth1 eth2",
            "miimon": 100,
            "downdelay": 200,
        }

        for version in range(7, 8):
            with patch.dict(
                rh_ip.__grains__, {"osmajorrelease": version, "osrelease": str(version)}
            ):
                for mode in ("balance-tlb", 5, "5"):
                    kwargs.pop("primary", None)
                    kwargs["mode"] = mode
                    self._validate_miimon_conf(kwargs)
                    bonding_opts = self._get_bonding_opts(kwargs)
                    expected = [
                        "downdelay=200",
                        "miimon=100",
                        "mode=5",
                        "use_carrier=0",
                    ]
                    assert bonding_opts == expected, bonding_opts

                    # Add a "primary" option and confirm that it shows up in
                    # the bonding opts.
                    kwargs["primary"] = "foo"
                    bonding_opts = self._get_bonding_opts(kwargs)
                    expected = [
                        "downdelay=200",
                        "miimon=100",
                        "mode=5",
                        "primary=foo",
                        "use_carrier=0",
                    ]
                    assert bonding_opts == expected, bonding_opts

    def test_build_interface_bond_mode_6(self):
        """
        Test that mode 6 bond interfaces are properly built
        """
        kwargs = {
            "test": True,
            "duplex": "full",
            "slaves": "eth1 eth2",
            "miimon": 100,
            "downdelay": 200,
        }

        for version in range(7, 8):
            with patch.dict(
                rh_ip.__grains__, {"osmajorrelease": version, "osrelease": str(version)}
            ):
                for mode in ("balance-alb", 6, "6"):
                    kwargs.pop("primary", None)
                    kwargs["mode"] = mode
                    self._validate_miimon_conf(kwargs)
                    bonding_opts = self._get_bonding_opts(kwargs)
                    expected = [
                        "downdelay=200",
                        "miimon=100",
                        "mode=6",
                        "use_carrier=0",
                    ]
                    assert bonding_opts == expected, bonding_opts

                    # Add a "primary" option and confirm that it shows up in
                    # the bonding opts.
                    kwargs["primary"] = "foo"
                    bonding_opts = self._get_bonding_opts(kwargs)
                    expected = [
                        "downdelay=200",
                        "miimon=100",
                        "mode=6",
                        "primary=foo",
                        "use_carrier=0",
                    ]
                    assert bonding_opts == expected, bonding_opts

    def test_build_interface_bond_slave(self):
        """
        Test that bond slave interfaces are properly built
        """
        for version in range(7, 8):
            with patch.dict(
                rh_ip.__grains__, {"osmajorrelease": version, "osrelease": str(version)}
            ):
                results = sorted(
                    rh_ip.build_interface(
                        "eth1",
                        "slave",
                        enabled=True,
                        test=True,
                        master="bond0",
                    )
                )
                expected = [
                    'BOOTPROTO="none"',
                    'DEVICE="eth1"',
                    'MASTER="bond0"',
                    'NM_CONTROLLED="no"',
                    'ONBOOT="yes"',
                    'SLAVE="yes"',
                    'USERCTL="no"',
                ]
                assert results == expected, results
