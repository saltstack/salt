import copy
import os

import jinja2.exceptions
import pytest

import salt.modules.suse_ip as suse_ip
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {suse_ip: {"__grains__": {"os_family": "Suse"}}}


def test_error_message_iface_should_process_non_str_expected():
    values = [1, True, False, "no-kaboom"]
    iface = "ethtest"
    option = "test"
    msg = suse_ip._error_msg_iface(iface, option, values)
    assert msg
    assert msg.endswith("[1|True|False|no-kaboom]")


def test_error_message_network_should_process_non_str_expected():
    values = [1, True, False, "no-kaboom"]
    msg = suse_ip._error_msg_network("fnord", values)
    assert msg
    assert msg.endswith("[1|True|False|no-kaboom]")


def test_build_interface():
    """
    Test to build an interface script for a network interface.
    """
    with patch.object(suse_ip, "_raise_error_iface", return_value=None):
        with pytest.raises(AttributeError):
            suse_ip.build_interface("iface", "slave", True)

        with patch.dict(
            suse_ip.__salt__, {"network.interfaces": lambda: {"eth": True}}
        ):
            with pytest.raises(AttributeError):
                suse_ip.build_interface(
                    "iface",
                    "eth",
                    True,
                    netmask="255.255.255.255",
                    prefix=32,
                    test=True,
                )
            with pytest.raises(AttributeError):
                suse_ip.build_interface(
                    "iface",
                    "eth",
                    True,
                    ipaddrs=["A"],
                    test=True,
                )
            with pytest.raises(AttributeError):
                suse_ip.build_interface(
                    "iface",
                    "eth",
                    True,
                    ipv6addrs=["A"],
                    test=True,
                )

    with patch.object(suse_ip, "_raise_error_iface", return_value=None), patch.object(
        suse_ip, "_parse_settings_bond", MagicMock()
    ):
        mock = jinja2.exceptions.TemplateNotFound("foo")
        with patch.object(
            jinja2.Environment,
            "get_template",
            MagicMock(side_effect=mock),
        ):
            assert suse_ip.build_interface("iface", "vlan", True) == ""

        with patch.object(
            suse_ip, "_get_non_blank_lines", return_value="A"
        ), patch.object(jinja2.Environment, "get_template", MagicMock()):
            assert suse_ip.build_interface("iface", "vlan", True, test="A") == "A"

            with patch.object(
                suse_ip, "_write_file_iface", return_value=None
            ), patch.object(os.path, "join", return_value="A"), patch.object(
                suse_ip, "_read_file", return_value="A"
            ):
                assert suse_ip.build_interface("iface", "vlan", True) == "A"
                with patch.dict(
                    suse_ip.__salt__,
                    {"network.interfaces": lambda: {"eth": True}},
                ):
                    assert (
                        suse_ip.build_interface(
                            "iface",
                            "eth",
                            True,
                            ipaddrs=["127.0.0.1/8"],
                        )
                        == "A"
                    )
                    assert (
                        suse_ip.build_interface(
                            "iface",
                            "eth",
                            True,
                            ipv6addrs=["fc00::1/128"],
                        )
                        == "A"
                    )


def test_build_routes():
    """
    Test to build a route script for a network interface.
    """
    with patch.object(suse_ip, "_parse_routes", MagicMock()):
        mock = jinja2.exceptions.TemplateNotFound("foo")
        with patch.object(
            jinja2.Environment, "get_template", MagicMock(side_effect=mock)
        ):
            assert suse_ip.build_routes("iface") == ""

        with patch.object(jinja2.Environment, "get_template", MagicMock()):
            with patch.object(suse_ip, "_get_non_blank_lines", return_value=["A"]):
                assert suse_ip.build_routes("i", test="t") == ["A"]

            with patch.object(suse_ip, "_read_file", return_value=["A"]):
                with patch.object(os.path, "join", return_value="A"), patch.object(
                    suse_ip, "_write_file_network", return_value=None
                ):
                    assert suse_ip.build_routes("i", test=None) == ["A"]


def test_down():
    """
    Test to shutdown a network interface
    """
    with patch.dict(suse_ip.__salt__, {"cmd.run": MagicMock(return_value="A")}):
        assert suse_ip.down("iface", "iface_type") == "A"

    assert suse_ip.down("iface", "slave") is None


def test_get_interface():
    """
    Test to return the contents of an interface script
    """
    with patch.object(os.path, "join", return_value="A"), patch.object(
        suse_ip, "_read_file", return_value="A"
    ):
        assert suse_ip.get_interface("iface") == "A"


def test__parse_settings_eth_hwaddr_and_macaddr():
    """
    Test that an AttributeError is thrown when hwaddr and macaddr are
    passed together. They cannot be used together
    """
    opts = {"hwaddr": 1, "macaddr": 2}

    with pytest.raises(AttributeError):
        suse_ip._parse_settings_eth(
            opts=opts, iface_type="eth", enabled=True, iface="eth0"
        )


def test__parse_settings_eth_hwaddr():
    """
    Make sure hwaddr gets added when parsing opts
    """
    opts = {"hwaddr": "AA:BB:CC:11:22:33"}
    with patch.dict(suse_ip.__salt__, {"network.interfaces": MagicMock()}):
        results = suse_ip._parse_settings_eth(
            opts=opts, iface_type="eth", enabled=True, iface="eth0"
        )
    assert "hwaddr" in results
    assert results["hwaddr"] == opts["hwaddr"]


def test__parse_settings_eth_macaddr():
    """
    Make sure macaddr gets added when parsing opts
    """
    opts = {"macaddr": "AA:BB:CC:11:22:33"}
    with patch.dict(suse_ip.__salt__, {"network.interfaces": MagicMock()}):
        results = suse_ip._parse_settings_eth(
            opts=opts, iface_type="eth", enabled=True, iface="eth0"
        )
    assert "macaddr" in results
    assert results["macaddr"] == opts["macaddr"]


def test__parse_settings_eth_ethtool_channels():
    """
    Make sure channels gets added when parsing opts
    """
    opts = {"channels": {"rx": 4, "tx": 4, "combined": 4, "other": 4}}
    with patch.dict(suse_ip.__grains__, {"num_cpus": 4}), patch.dict(
        suse_ip.__salt__, {"network.interfaces": MagicMock()}
    ):
        results = suse_ip._parse_settings_eth(
            opts=opts, iface_type="eth", enabled=True, iface="eth0"
        )
    assert "ethtool" in results
    assert results["ethtool"] == "-L eth0 rx 4 tx 4 other 4 combined 4"


def test_up():
    """
    Test to start up a network interface
    """
    with patch.dict(suse_ip.__salt__, {"cmd.run": MagicMock(return_value="A")}):
        assert suse_ip.up("iface", "iface_type") == "A"

    assert suse_ip.up("iface", "slave") is None


def test_get_routes():
    """
    Test to return the contents of the interface routes script.
    """
    with patch.object(os.path, "join", return_value="A"), patch.object(
        suse_ip, "_read_file", return_value=["A"]
    ):
        assert suse_ip.get_routes("iface") == ["A"]


def test_get_network_settings():
    """
    Test to return the contents of the global network script.
    """
    with patch.object(suse_ip, "_read_file", return_value="A"):
        assert suse_ip.get_network_settings() == "A"


def test_apply_network_settings():
    """
    Test to apply global network configuration.
    """
    with patch.dict(suse_ip.__salt__, {"service.reload": MagicMock(return_value=True)}):
        assert suse_ip.apply_network_settings()


def test_build_network_settings():
    """
    Test to build the global network script.
    """
    with patch.object(suse_ip, "_parse_suse_config", MagicMock()), patch.object(
        suse_ip, "_parse_network_settings", MagicMock()
    ):

        mock = jinja2.exceptions.TemplateNotFound("foo")
        with patch.object(
            jinja2.Environment, "get_template", MagicMock(side_effect=mock)
        ):
            assert suse_ip.build_network_settings() == ""

        with patch.object(
            jinja2.Environment, "get_template", MagicMock()
        ), patch.object(suse_ip, "_get_non_blank_lines", return_value="A"):
            assert suse_ip.build_network_settings(test="t") == "A"

            with patch.object(suse_ip, "_write_file_network", return_value=None):
                cmd_run = MagicMock()
                with patch.object(suse_ip, "_read_file", return_value="A"), patch.dict(
                    suse_ip.__salt__, {"cmd.run": cmd_run}
                ):
                    assert suse_ip.build_network_settings(test=None) == "A"
                    cmd_run.assert_called_once_with("netconfig update -f")


def _check_common_opts_bond(lines):
    """
    Reduce code duplication by making sure that the expected options are
    present in the config file. Note that this assumes that duplex="full"
    was passed in the kwargs. If it wasn't, then there would be no
    ETHTOOL_OPTS line.
    """
    assert "STARTMODE='auto'" in lines
    assert "BONDING_MASTER='yes'" in lines
    assert "BONDING_SLAVE1='eth1'" in lines
    assert "BONDING_SLAVE2='eth2'" in lines
    assert "ETHTOOL_OPTIONS='duplex full'" in lines


def _validate_miimon_downdelay(kwargs):
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
        suse_ip.build_interface(
            "bond0",
            "bond",
            enabled=True,
            **kwargs,
        )
    except AttributeError as exc:
        assert "multiple of miimon" in str(exc)
    else:
        raise Exception("AttributeError was not raised")


def _validate_miimon_conf(kwargs, required=True):
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
            suse_ip.build_interface(
                "bond0",
                "bond",
                enabled=True,
                **kwargs,
            )
        except AttributeError as exc:
            assert "miimon" in str(exc)
        else:
            raise Exception("AttributeError was not raised")

    _validate_miimon_downdelay(kwargs)


def _get_bonding_opts(kwargs):
    results = suse_ip.build_interface(
        "bond0",
        "bond",
        enabled=True,
        **kwargs,
    )
    _check_common_opts_bond(results)

    for line in results:
        if line.startswith("BONDING_MODULE_OPTS="):
            return sorted(line.split("=", 1)[-1].strip("'").split())
    raise Exception("BONDING_MODULE_OPTS not found")


def _test_mode_0_or_2(mode_num=0):
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
        _validate_miimon_downdelay(kwargs)

        # Leaving out miimon and arp_interval should raise an error
        try:
            bonding_opts = _get_bonding_opts(kwargs)
        except AttributeError as exc:
            assert "miimon or arp_interval" in str(exc)
        else:
            raise Exception("AttributeError was not raised")

        kwargs["miimon"] = 100
        kwargs["downdelay"] = 200
        bonding_opts = _get_bonding_opts(kwargs)
        expected = [
            "downdelay=200",
            "miimon=100",
            "mode={}".format(mode_num),
            "use_carrier=0",
        ]
        assert bonding_opts == expected, bonding_opts

        # Add arp settings, and test again
        kwargs["arp_interval"] = 300
        kwargs["arp_ip_target"] = ["1.2.3.4", "5.6.7.8"]
        bonding_opts = _get_bonding_opts(kwargs)
        expected = [
            "arp_interval=300",
            "arp_ip_target=1.2.3.4,5.6.7.8",
            "downdelay=200",
            "miimon=100",
            "mode={}".format(mode_num),
            "use_carrier=0",
        ]
        assert bonding_opts == expected, bonding_opts

        # Remove miimon and downdelay and test again
        del kwargs["miimon"]
        del kwargs["downdelay"]
        bonding_opts = _get_bonding_opts(kwargs)
        expected = [
            "arp_interval=300",
            "arp_ip_target=1.2.3.4,5.6.7.8",
            "mode={}".format(mode_num),
        ]
        assert bonding_opts == expected, bonding_opts


def test_build_interface_bond_mode_0():
    """
    Test that mode 0 bond interfaces are properly built
    """
    _test_mode_0_or_2(0)


def test_build_interface_bond_mode_1():
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

    for mode in ("active-backup", 1, "1"):
        kwargs.pop("primary", None)
        kwargs["mode"] = mode
        _validate_miimon_conf(kwargs)
        bonding_opts = _get_bonding_opts(kwargs)
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
        bonding_opts = _get_bonding_opts(kwargs)
        expected = [
            "downdelay=200",
            "miimon=100",
            "mode=1",
            "primary=foo",
            "use_carrier=0",
        ]
        assert bonding_opts == expected, bonding_opts


def test_build_interface_bond_mode_2():
    """
    Test that mode 2 bond interfaces are properly built
    """
    _test_mode_0_or_2(2)

    kwargs = {
        "test": True,
        "duplex": "full",
        "slaves": "eth1 eth2",
        "miimon": 100,
        "downdelay": 200,
    }
    for mode in ("balance-xor", 2, "2"):
        # Using an invalid hashing algorithm should cause an error
        # to be raised.
        kwargs["mode"] = mode
        kwargs["hashing-algorithm"] = "layer42"
        try:
            bonding_opts = _get_bonding_opts(kwargs)
        except AttributeError as exc:
            assert "hashing-algorithm" in str(exc)
        else:
            raise Exception("AttributeError was not raised")

        # Correct the hashing algorithm and re-run
        kwargs["hashing-algorithm"] = "layer2"
        bonding_opts = _get_bonding_opts(kwargs)
        expected = [
            "downdelay=200",
            "miimon=100",
            "mode=2",
            "use_carrier=0",
            "xmit_hash_policy=layer2",
        ]
        assert bonding_opts == expected, bonding_opts


def test_build_interface_bond_mode_3():
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

    for mode in ("broadcast", 3, "3"):
        kwargs["mode"] = mode
        _validate_miimon_conf(kwargs)
        bonding_opts = _get_bonding_opts(kwargs)
        expected = [
            "downdelay=200",
            "miimon=100",
            "mode=3",
            "use_carrier=0",
        ]
        assert bonding_opts == expected, bonding_opts


def test_build_interface_bond_mode_4():
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

    for mode in ("802.3ad", 4, "4"):
        kwargs["mode"] = mode
        _validate_miimon_conf(kwargs)

        for lacp_rate in valid_lacp_rate + ("2", "speedy"):
            for ad_select in valid_ad_select + ("foo",):
                kwargs["lacp_rate"] = lacp_rate
                kwargs["ad_select"] = ad_select
                try:
                    bonding_opts = _get_bonding_opts(kwargs)
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
                        "ad_select={}".format(ad_select),
                        "downdelay=200",
                        "lacp_rate={}".format(
                            "1"
                            if lacp_rate == "fast"
                            else "0"
                            if lacp_rate == "slow"
                            else lacp_rate
                        ),
                        "miimon=100",
                        "mode=4",
                        "use_carrier=0",
                    ]
                    assert bonding_opts == expected, bonding_opts


def test_build_interface_bond_mode_5():
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

    for mode in ("balance-tlb", 5, "5"):
        kwargs.pop("primary", None)
        kwargs["mode"] = mode
        _validate_miimon_conf(kwargs)
        bonding_opts = _get_bonding_opts(kwargs)
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
        bonding_opts = _get_bonding_opts(kwargs)
        expected = [
            "downdelay=200",
            "miimon=100",
            "mode=5",
            "primary=foo",
            "use_carrier=0",
        ]
        assert bonding_opts == expected, bonding_opts


def test_build_interface_bond_mode_6():
    """
    Test that mode 6 bond interfaces are properly built
    """
    kwargs = {
        "test": True,
        "duplex": "full",
        "slaves": ["eth1", "eth2"],
        "miimon": 100,
        "downdelay": 200,
    }

    for mode in ("balance-alb", 6, "6"):
        kwargs.pop("primary", None)
        kwargs["mode"] = mode
        _validate_miimon_conf(kwargs)
        bonding_opts = _get_bonding_opts(kwargs)
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
        bonding_opts = _get_bonding_opts(kwargs)
        expected = [
            "downdelay=200",
            "miimon=100",
            "mode=6",
            "primary=foo",
            "use_carrier=0",
        ]
        assert bonding_opts == expected, bonding_opts


def test_build_interface_bond_slave():
    """
    Test that bond slave interfaces are properly built
    """
    results = sorted(
        suse_ip.build_interface(
            "eth1",
            "slave",
            enabled=True,
            test=True,
            master="bond0",
        )
    )
    expected = [
        "BOOTPROTO='none'",
        "STARTMODE='auto'",
    ]
    assert results == expected, results
