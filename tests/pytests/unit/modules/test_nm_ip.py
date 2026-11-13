"""
Unit tests for salt.modules.nm_ip (the NetworkManager 'ip' provider, #54791).
"""

import os
import stat

import pytest

import salt.modules.nm_ip as nm_ip
import salt.utils.files
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        nm_ip: {
            "__grains__": {"os_family": "RedHat"},
            "__salt__": {},
        }
    }


def _parse(lines):
    """Parse keyfile lines into {section: {key: value}} (last value wins)."""
    out = {}
    current = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            current = stripped[1:-1]
            out.setdefault(current, {})
        elif "=" in stripped and current is not None:
            key, _, value = stripped.partition("=")
            out[current][key] = value
    return out


# ---- __virtual__ / provider selection ----


def test_virtual_loads_when_nm_managed():
    with patch.dict(nm_ip.__grains__, {"os_family": "RedHat"}), patch.object(
        nm_ip, "nm_managed", MagicMock(return_value=True)
    ):
        assert nm_ip.__virtual__() == "ip"


def test_virtual_declines_when_not_nm_managed():
    with patch.dict(nm_ip.__grains__, {"os_family": "RedHat"}), patch.object(
        nm_ip, "nm_managed", MagicMock(return_value=False)
    ):
        ret = nm_ip.__virtual__()
    assert ret[0] is False


def test_virtual_declines_off_redhat():
    with patch.dict(nm_ip.__grains__, {"os_family": "Debian"}), patch.object(
        nm_ip, "nm_managed", MagicMock(return_value=True)
    ):
        ret = nm_ip.__virtual__()
    assert ret[0] is False


def test_nm_managed_true_on_modern_el():
    # nmcli present, NM running, no ifup/ifdown -> nm_ip owns it.
    def _which(cmd):
        return "/usr/bin/nmcli" if cmd == "nmcli" else None

    with patch("salt.utils.path.which", MagicMock(side_effect=_which)), patch(
        "os.path.isdir", MagicMock(return_value=True)
    ):
        assert nm_ip.nm_managed() is True


def test_nm_managed_false_with_legacy_ifupdown():
    # network-scripts installed (ifup/ifdown present) -> defer to rh_ip.
    with patch(
        "salt.utils.path.which", MagicMock(return_value="/usr/sbin/ifup")
    ), patch("os.path.isdir", MagicMock(return_value=True)):
        assert nm_ip.nm_managed() is False


def test_nm_managed_false_without_nmcli():
    with patch("salt.utils.path.which", MagicMock(return_value=None)), patch(
        "os.path.isdir", MagicMock(return_value=True)
    ):
        assert nm_ip.nm_managed() is False


def test_nm_managed_false_when_nm_not_running():
    def _which(cmd):
        return "/usr/bin/nmcli" if cmd == "nmcli" else None

    with patch("salt.utils.path.which", MagicMock(side_effect=_which)), patch(
        "os.path.isdir", MagicMock(return_value=False)
    ):
        assert nm_ip.nm_managed() is False


# ---- build_interface: ethernet ----


def test_build_interface_static():
    lines = nm_ip.build_interface(
        "eth1",
        "eth",
        True,
        proto="none",
        ipaddr="192.168.99.10",
        netmask="255.255.255.0",
        gateway="192.168.99.1",
        dns=["8.8.8.8", "2001:4860:4860::8888"],
        mtu=1500,
        test=True,
    )
    doc = _parse(lines)
    assert doc["connection"]["type"] == "ethernet"
    assert doc["connection"]["interface-name"] == "eth1"
    assert doc["connection"]["autoconnect"] == "true"
    assert doc["ipv4"]["method"] == "manual"
    assert doc["ipv4"]["address1"] == "192.168.99.10/24,192.168.99.1"
    # IPv4 nameserver on ipv4, IPv6 nameserver split onto ipv6.
    assert doc["ipv4"]["dns"] == "8.8.8.8;"
    assert doc["ipv6"]["dns"] == "2001:4860:4860::8888;"
    assert doc["ethernet"]["mtu"] == "1500"


def test_build_interface_dhcp():
    lines = nm_ip.build_interface("eth1", "eth", True, proto="dhcp", test=True)
    doc = _parse(lines)
    assert doc["ipv4"]["method"] == "auto"
    assert doc["ipv6"]["method"] == "auto"


def test_build_interface_disabled_ipv4():
    lines = nm_ip.build_interface("eth1", "eth", True, proto="none", test=True)
    doc = _parse(lines)
    assert doc["ipv4"]["method"] == "disabled"


def test_build_interface_ipv6_static_and_disabled():
    lines = nm_ip.build_interface(
        "eth1",
        "eth",
        True,
        proto="dhcp",
        ipv6proto="static",
        ipv6ipaddr="2001:db8::10",
        ipv6netmask="64",
        ipv6gateway="2001:db8::1",
        test=True,
    )
    doc = _parse(lines)
    assert doc["ipv6"]["method"] == "manual"
    assert doc["ipv6"]["address1"] == "2001:db8::10/64,2001:db8::1"

    lines = nm_ip.build_interface(
        "eth1", "eth", True, proto="dhcp", ipv6proto="disabled", test=True
    )
    assert _parse(lines)["ipv6"]["method"] == "disabled"


def test_build_interface_disabled_when_not_enabled():
    lines = nm_ip.build_interface("eth1", "eth", False, proto="dhcp", test=True)
    assert _parse(lines)["connection"]["autoconnect"] == "false"


def test_build_interface_rejects_unknown_type():
    with pytest.raises(CommandExecutionError):
        nm_ip.build_interface("eth1", "infiniband", True, test=True)


def test_build_interface_rejects_unsupported_options():
    with pytest.raises(CommandExecutionError):
        nm_ip.build_interface(
            "eth1", "eth", True, proto="dhcp", ethtool="autoneg on", test=True
        )


def test_deterministic_uuid():
    a = _parse(nm_ip.build_interface("eth1", "eth", True, proto="dhcp", test=True))
    b = _parse(nm_ip.build_interface("eth1", "eth", True, proto="dhcp", test=True))
    assert a["connection"]["uuid"] == b["connection"]["uuid"]
    c = _parse(nm_ip.build_interface("eth2", "eth", True, proto="dhcp", test=True))
    assert c["connection"]["uuid"] != a["connection"]["uuid"]


# ---- build_interface: bond / vlan / bridge / slave ----


def test_build_interface_bond():
    lines = nm_ip.build_interface(
        "bond0",
        "bond",
        True,
        mode="active-backup",
        miimon="100",
        slaves="eth1 eth2",
        ipaddr="10.0.0.5",
        netmask="255.255.255.0",
        test=True,
    )
    doc = _parse(lines)
    assert doc["connection"]["type"] == "bond"
    assert doc["bond"]["mode"] == "active-backup"
    assert doc["bond"]["miimon"] == "100"
    assert doc["ipv4"]["address1"] == "10.0.0.5/24"


def test_build_interface_bond_requires_mode():
    with pytest.raises(CommandExecutionError):
        nm_ip.build_interface("bond0", "bond", True, slaves="eth1", test=True)


def test_build_interface_bond_writes_slave_keyfiles(tmp_path):
    with patch.object(nm_ip, "_NM_DIR", str(tmp_path)):
        nm_ip.build_interface(
            "bond0", "bond", True, mode="802.3ad", miimon="100", slaves="eth1 eth2"
        )
        slave = _parse(nm_ip.get_interface("eth1"))
    assert slave["connection"]["master"] == "bond0"
    assert slave["connection"]["slave-type"] == "bond"
    # A port carries no L3 config.
    assert "ipv4" not in slave
    assert "ipv6" not in slave


def test_build_interface_vlan_dotted_name():
    lines = nm_ip.build_interface(
        "eth0.100", "vlan", True, ipaddr="10.1.0.5", netmask="255.255.255.0", test=True
    )
    doc = _parse(lines)
    assert doc["connection"]["type"] == "vlan"
    assert doc["vlan"]["id"] == "100"
    assert doc["vlan"]["parent"] == "eth0"


def test_build_interface_vlan_explicit():
    lines = nm_ip.build_interface(
        "myvlan", "vlan", True, vlan_id=42, parent="eth3", test=True
    )
    doc = _parse(lines)
    assert doc["vlan"]["id"] == "42"
    assert doc["vlan"]["parent"] == "eth3"


def test_build_interface_vlan_requires_id_and_parent():
    with pytest.raises(CommandExecutionError):
        nm_ip.build_interface("badvlan", "vlan", True, test=True)


def test_build_interface_bridge_writes_port_keyfiles(tmp_path):
    with patch.object(nm_ip, "_NM_DIR", str(tmp_path)):
        lines = nm_ip.build_interface(
            "br0",
            "bridge",
            True,
            ports="eth1 eth2",
            stp="yes",
            ipaddr="10.2.0.5",
            netmask="255.255.255.0",
        )
        port = _parse(nm_ip.get_interface("eth1"))
    doc = _parse(lines)
    assert doc["connection"]["type"] == "bridge"
    assert doc["bridge"]["stp"] == "true"
    assert port["connection"]["master"] == "br0"
    assert port["connection"]["slave-type"] == "bridge"


def test_build_interface_slave_has_no_l3():
    lines = nm_ip.build_interface("eth1", "slave", True, master="bond0", test=True)
    doc = _parse(lines)
    assert doc["connection"]["master"] == "bond0"
    assert doc["connection"]["slave-type"] == "bond"
    assert "ipv4" not in doc


def test_build_interface_test_flag_skips_write_54791(tmp_path):
    """
    Direct call at the altitude network.managed uses: the state always injects
    kwargs["test"] (from __opts__) before calling
    ip.build_interface(name, iface_type, enabled, **kwargs). test is the
    decisive flag -- with test=True the rendered lines must come back for the
    state's diff without anything hitting disk, and the same call with
    test=False (a real run) must write exactly those lines.
    """
    with patch.object(nm_ip, "_NM_DIR", str(tmp_path)):
        lines = nm_ip.build_interface(
            "eth1",
            "eth",
            True,
            proto="none",
            ipaddr="10.9.0.5",
            netmask="255.255.255.0",
            test=True,
        )
        assert lines
        assert list(tmp_path.iterdir()) == []
        written = nm_ip.build_interface(
            "eth1",
            "eth",
            True,
            proto="none",
            ipaddr="10.9.0.5",
            netmask="255.255.255.0",
            test=False,
        )
        assert written == lines
        assert nm_ip.get_interface("eth1") == lines


def test_build_interface_bond_test_flag_skips_port_keyfiles_54791(tmp_path):
    """
    Guards against overcorrection: writing member port keyfiles is a side
    effect of a real bond build, and it must not start happening under
    test=True -- a state test run may not touch disk at all.
    """
    with patch.object(nm_ip, "_NM_DIR", str(tmp_path)):
        lines = nm_ip.build_interface(
            "bond0",
            "bond",
            True,
            mode="active-backup",
            miimon="100",
            slaves="eth1 eth2",
            test=True,
        )
        assert lines
        assert list(tmp_path.iterdir()) == []


# ---- get_interface / write / idempotency ----


def test_get_interface_empty_when_absent(tmp_path):
    with patch.object(nm_ip, "_NM_DIR", str(tmp_path)):
        assert nm_ip.get_interface("nope") == []


def test_build_interface_writes_and_roundtrips(tmp_path):
    with patch.object(nm_ip, "_NM_DIR", str(tmp_path)):
        written = nm_ip.build_interface(
            "eth1",
            "eth",
            True,
            proto="none",
            ipaddr="10.9.0.5",
            netmask="255.255.255.0",
            gateway="10.9.0.1",
        )
        assert nm_ip.get_interface("eth1") == written
        # Second build is byte-identical -> state sees no change.
        again = nm_ip.build_interface(
            "eth1",
            "eth",
            True,
            proto="none",
            ipaddr="10.9.0.5",
            netmask="255.255.255.0",
            gateway="10.9.0.1",
        )
        assert again == written


def test_keyfile_is_chmod_600(tmp_path):
    import os
    import stat

    with patch.object(nm_ip, "_NM_DIR", str(tmp_path)):
        nm_ip.build_interface("eth1", "eth", True, proto="dhcp")
        mode = stat.S_IMODE(os.stat(nm_ip._keyfile("eth1")).st_mode)
    assert mode == 0o600


# ---- routes ----


def test_build_and_get_routes_roundtrip(tmp_path):
    with patch.object(nm_ip, "_NM_DIR", str(tmp_path)):
        nm_ip.build_interface(
            "eth1",
            "eth",
            True,
            proto="none",
            ipaddr="10.9.0.5",
            netmask="255.255.255.0",
        )
        nm_ip.build_routes(
            "eth1",
            routes=[
                {
                    "ipaddr": "172.16.0.0",
                    "netmask": "255.255.0.0",
                    "gateway": "10.9.0.1",
                },
                {"ipaddr": "default", "gateway": "10.9.0.254"},
            ],
        )
        doc = _parse(nm_ip.get_interface("eth1"))
        assert doc["ipv4"]["route1"] == "172.16.0.0/16,10.9.0.1"
        assert doc["ipv4"]["route2"] == "0.0.0.0/0,10.9.0.254"
        # Re-applying the same routes stays idempotent (no duplicate routeN).
        before = nm_ip.get_interface("eth1")
        nm_ip.build_routes(
            "eth1",
            routes=[
                {
                    "ipaddr": "172.16.0.0",
                    "netmask": "255.255.0.0",
                    "gateway": "10.9.0.1",
                },
                {"ipaddr": "default", "gateway": "10.9.0.254"},
            ],
        )
        assert nm_ip.get_interface("eth1") == before
        assert nm_ip.get_routes("eth1")


# ---- global network settings (no-op) ----


def test_network_settings_are_noops():
    assert nm_ip.get_network_settings() == []
    assert nm_ip.build_network_settings() == []


# ---- up / down / apply ----


def test_up_calls_nmcli_up():
    run = MagicMock(return_value="ok")
    run_all = MagicMock(return_value={"retcode": 0})
    with patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/nmcli")):
        with patch.dict(nm_ip.__salt__, {"cmd.run": run, "cmd.run_all": run_all}):
            nm_ip.up("eth1", "eth")
    assert run.call_args[0][0] == ["/usr/bin/nmcli", "connection", "up", "eth1"]


def test_down_calls_nmcli_down():
    run = MagicMock(return_value="ok")
    with patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/nmcli")):
        with patch.dict(nm_ip.__salt__, {"cmd.run": run}):
            nm_ip.down("eth1", "eth")
    assert run.call_args[0][0] == ["/usr/bin/nmcli", "connection", "down", "eth1"]


def test_up_down_skip_slaves():
    run = MagicMock()
    with patch.dict(nm_ip.__salt__, {"cmd.run": run}):
        assert nm_ip.up("eth1", "slave") is None
        assert nm_ip.down("eth1", "slave") is None
    run.assert_not_called()


def test_apply_network_settings_reloads():
    run_all = MagicMock(return_value={"retcode": 0})
    with patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/nmcli")):
        with patch.dict(nm_ip.__salt__, {"cmd.run_all": run_all}):
            assert nm_ip.apply_network_settings() is True
    assert run_all.call_args[0][0] == ["/usr/bin/nmcli", "connection", "reload"]


def test_apply_network_settings_raises_on_failure():
    run_all = MagicMock(return_value={"retcode": 1, "stderr": "boom"})
    with patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/nmcli")):
        with patch.dict(nm_ip.__salt__, {"cmd.run_all": run_all}):
            with pytest.raises(CommandExecutionError):
                nm_ip.apply_network_settings()


# ---- nm_managed is shared with rh_ip via salt.utils.network (#5479) ----


def test_nm_managed_delegates_to_utils_network():
    # The gate lives in salt.utils.network so rh_ip and nm_ip share one copy;
    # nm_ip.nm_managed must simply return it.
    with patch("salt.utils.network.nm_managed", MagicMock(return_value=True)):
        assert nm_ip.nm_managed() is True
    with patch("salt.utils.network.nm_managed", MagicMock(return_value=False)):
        assert nm_ip.nm_managed() is False


# ---- mtu on bond / bridge / vlan -> separate [ethernet] section (#5479) ----


def test_bond_mtu_emits_separate_ethernet_section():
    # NM has no [bond] mtu key; mtu is carried by an 802-3-ethernet setting
    # attached to the bond master connection.
    lines = nm_ip.build_interface(
        "bond0",
        "bond",
        True,
        mode="active-backup",
        miimon="100",
        mtu=9000,
        slaves="eth1 eth2",
        test=True,
    )
    doc = _parse(lines)
    assert doc["connection"]["type"] == "bond"
    assert doc["ethernet"]["mtu"] == "9000"
    # mtu must NOT leak into the [bond] section.
    assert "mtu" not in doc["bond"]
    assert doc["bond"]["mode"] == "active-backup"


def test_bridge_mtu_emits_separate_ethernet_section():
    lines = nm_ip.build_interface("br0", "bridge", True, stp="yes", mtu=9000, test=True)
    doc = _parse(lines)
    assert doc["connection"]["type"] == "bridge"
    assert doc["ethernet"]["mtu"] == "9000"
    assert doc["bridge"]["stp"] == "true"


def test_vlan_mtu_emits_separate_ethernet_section():
    lines = nm_ip.build_interface(
        "eth0.100", "vlan", True, mtu=9000, ipaddr="10.1.0.5", netmask="24", test=True
    )
    doc = _parse(lines)
    assert doc["connection"]["type"] == "vlan"
    assert doc["ethernet"]["mtu"] == "9000"
    assert doc["vlan"]["id"] == "100"


def test_bond_without_mtu_has_no_ethernet_section():
    # Inverse/no-regress: a bond with no ethernet-family option must not emit an
    # empty [ethernet] section.
    lines = nm_ip.build_interface(
        "bond0", "bond", True, mode="active-backup", slaves="eth1", test=True
    )
    doc = _parse(lines)
    assert "ethernet" not in doc


def test_ethernet_mtu_stays_in_ethernet_device_section():
    # For a plain ethernet interface, mtu still folds into its own [ethernet]
    # device section (one section, not two).
    lines = nm_ip.build_interface(
        "eth1", "eth", True, proto="dhcp", mtu=1500, test=True
    )
    doc = _parse(lines)
    assert doc["ethernet"]["mtu"] == "1500"
    assert list(doc).count("ethernet") == 1


# ---- hwaddr / macaddr (#5479) ----


def test_hwaddr_emits_ethernet_mac_address():
    lines = nm_ip.build_interface(
        "eth1", "eth", True, proto="dhcp", hwaddr="AA:BB:CC:DD:EE:FF", test=True
    )
    doc = _parse(lines)
    assert doc["ethernet"]["mac-address"] == "AA:BB:CC:DD:EE:FF"


def test_hwaddr_auto_and_none_sentinels_skip_emit():
    for sentinel in ("auto", "none"):
        lines = nm_ip.build_interface(
            "eth1", "eth", True, proto="dhcp", hwaddr=sentinel, test=True
        )
        doc = _parse(lines)
        assert "ethernet" not in doc


def test_hwaddr_on_bridge_uses_bridge_mac_address():
    # A bridge sets its own device MAC via bridge.mac-address, not [ethernet].
    lines = nm_ip.build_interface(
        "br0", "bridge", True, hwaddr="AA:BB:CC:DD:EE:FF", test=True
    )
    doc = _parse(lines)
    assert doc["bridge"]["mac-address"] == "AA:BB:CC:DD:EE:FF"
    assert "ethernet" not in doc


def test_hwaddr_on_vlan_uses_ethernet_mac_address():
    lines = nm_ip.build_interface(
        "myvlan",
        "vlan",
        True,
        vlan_id=10,
        parent="eth0",
        hwaddr="AA:BB:CC:DD:EE:FF",
        test=True,
    )
    doc = _parse(lines)
    assert doc["ethernet"]["mac-address"] == "AA:BB:CC:DD:EE:FF"


def test_macaddr_emits_cloned_mac_address():
    lines = nm_ip.build_interface(
        "eth1", "eth", True, proto="dhcp", macaddr="52:54:00:12:34:56", test=True
    )
    doc = _parse(lines)
    assert doc["ethernet"]["cloned-mac-address"] == "52:54:00:12:34:56"


def test_macaddr_accepts_special_value():
    lines = nm_ip.build_interface(
        "eth1", "eth", True, proto="dhcp", macaddr="random", test=True
    )
    doc = _parse(lines)
    assert doc["ethernet"]["cloned-mac-address"] == "random"


def test_hwaddr_and_macaddr_are_mutually_exclusive():
    with pytest.raises(CommandExecutionError):
        nm_ip.build_interface(
            "eth1",
            "eth",
            True,
            proto="dhcp",
            hwaddr="AA:BB:CC:DD:EE:FF",
            macaddr="random",
            test=True,
        )


# ---- ethtool autoneg / speed / duplex (#5479) ----


def test_ethtool_speed_and_duplex_map_to_ethernet():
    lines = nm_ip.build_interface(
        "eth1",
        "eth",
        True,
        proto="dhcp",
        autoneg="off",
        speed=1000,
        duplex="full",
        test=True,
    )
    doc = _parse(lines)
    assert doc["ethernet"]["auto-negotiate"] == "false"
    assert doc["ethernet"]["speed"] == "1000"
    assert doc["ethernet"]["duplex"] == "full"


def test_ethtool_speed_requires_duplex():
    with pytest.raises(CommandExecutionError):
        nm_ip.build_interface("eth1", "eth", True, proto="dhcp", speed=1000, test=True)


def test_ethtool_offload_key_still_rejected():
    # autoneg/speed/duplex are carved out, but offload knobs stay unsupported.
    with pytest.raises(CommandExecutionError):
        nm_ip.build_interface("eth1", "eth", True, proto="dhcp", gro="on", test=True)


# ---- bond option pass-through beyond the old allow-list (#5479) ----


def test_bond_passes_through_unmapped_option():
    # ad_select was absent from the fixed _BOND_OPT_MAP; it must now reach [bond].
    lines = nm_ip.build_interface(
        "bond0",
        "bond",
        True,
        mode="802.3ad",
        ad_select="bandwidth",
        fail_over_mac="active",
        min_links=2,
        test=True,
    )
    doc = _parse(lines)
    assert doc["bond"]["mode"] == "802.3ad"
    assert doc["bond"]["ad_select"] == "bandwidth"
    assert doc["bond"]["fail_over_mac"] == "active"
    assert doc["bond"]["min_links"] == "2"


def test_bond_does_not_treat_connection_keys_as_options():
    # Non-bond keys (ipaddr, mtu, slaves, ...) must never land in [bond].
    lines = nm_ip.build_interface(
        "bond0",
        "bond",
        True,
        mode="active-backup",
        miimon="100",
        ipaddr="10.0.0.5",
        netmask="24",
        mtu=9000,
        slaves="eth1 eth2",
        zone="public",
        test=True,
    )
    doc = _parse(lines)
    assert set(doc["bond"]) == {"mode", "miimon"}


def test_bond_rejects_invalid_option_name():
    with pytest.raises(CommandExecutionError):
        nm_ip.build_interface(
            "bond0", "bond", True, **{"mode": "active-backup", "bad-opt": "x"}
        )


# ---- dns-search on IPv6 (#5479) ----


def test_dns_search_emitted_on_ipv6_only_host():
    # ipv4 disabled, ipv6 static: search domains must survive under [ipv6].
    lines = nm_ip.build_interface(
        "eth1",
        "eth",
        True,
        proto="none",
        ipv6proto="static",
        ipv6ipaddr="2001:db8::10",
        ipv6netmask="64",
        dns_search=["example.com", "corp.example.com"],
        test=True,
    )
    doc = _parse(lines)
    assert doc["ipv4"]["method"] == "disabled"
    assert doc["ipv6"]["dns-search"] == "example.com;corp.example.com;"
    # A disabled [ipv4] must not carry a dead dns-search line.
    assert "dns-search" not in doc["ipv4"]


def test_dns_search_still_emitted_on_ipv4():
    lines = nm_ip.build_interface(
        "eth1",
        "eth",
        True,
        proto="none",
        ipaddr="10.0.0.5",
        netmask="24",
        dns_search="example.com",
        test=True,
    )
    doc = _parse(lines)
    assert doc["ipv4"]["dns-search"] == "example.com;"


def test_dns_search_not_emitted_when_ipv6_disabled():
    # Inverse: a disabled ipv6 stack must not carry a pointless dns-search.
    lines = nm_ip.build_interface(
        "eth1",
        "eth",
        True,
        proto="none",
        ipaddr="10.0.0.5",
        netmask="24",
        ipv6proto="disabled",
        dns_search="example.com",
        test=True,
    )
    doc = _parse(lines)
    assert doc["ipv6"]["method"] == "disabled"
    assert "dns-search" not in doc["ipv6"]


# ---- vlan flags (#5479) ----


def test_vlan_reorder_hdr_off_emits_flags_zero():
    lines = nm_ip.build_interface(
        "eth0.100", "vlan", True, reorder_hdr=False, test=True
    )
    doc = _parse(lines)
    assert doc["vlan"]["flags"] == "0"


def test_vlan_gvrp_sets_flag_bit_over_default():
    # reorder-headers stays on by default (0x1); gvrp adds 0x2 -> 3.
    lines = nm_ip.build_interface("eth0.100", "vlan", True, gvrp="yes", test=True)
    doc = _parse(lines)
    assert doc["vlan"]["flags"] == "3"


def test_vlan_default_flags_not_emitted():
    # Inverse: no flag option, or reorder_hdr left at its default, emits no
    # flags= line.
    doc = _parse(nm_ip.build_interface("eth0.100", "vlan", True, test=True))
    assert "flags" not in doc["vlan"]
    doc = _parse(
        nm_ip.build_interface("eth0.100", "vlan", True, reorder_hdr=True, test=True)
    )
    assert "flags" not in doc["vlan"]


# ---- wake-on-lan (#5479) ----


def test_wol_named_flag_maps_to_mask():
    lines = nm_ip.build_interface(
        "eth1", "eth", True, proto="dhcp", wol="magic", test=True
    )
    doc = _parse(lines)
    assert doc["ethernet"]["wake-on-lan"] == "64"


def test_wol_integer_mask_passthrough():
    lines = nm_ip.build_interface("eth1", "eth", True, proto="dhcp", wol=66, test=True)
    doc = _parse(lines)
    assert doc["ethernet"]["wake-on-lan"] == "66"


def test_listify_splits_on_semicolons():
    # NetworkManager uses ';' as its on-disk array delimiter, so a pillar value
    # pre-formatted that way (e.g. copied from an existing keyfile) must split
    # into individual entries rather than one malformed element.
    assert nm_ip._listify("10.0.0.1;10.0.0.2;") == ["10.0.0.1", "10.0.0.2"]
    assert nm_ip._listify("a, b;c d") == ["a", "b", "c", "d"]
    # Lists still pass through untouched.
    assert nm_ip._listify(["10.0.0.1", "10.0.0.2"]) == ["10.0.0.1", "10.0.0.2"]


def test_write_keyfile_atomic_forces_0600_even_over_existing_0644(tmp_path):
    # The keyfile write must land at 0600 regardless of any pre-existing mode.
    # A copy-that-preserves-dest-mode (salt.utils.files.copyfile does exactly
    # that) would leave an existing 0644 keyfile world-readable, which NM
    # rejects and which can leak connection secrets. Also guards against a
    # non-atomic in-place write leaving a stray temp file behind.
    with patch.object(nm_ip, "_NM_DIR", str(tmp_path)):
        path = nm_ip._keyfile("eth0")
        nm_ip._write_keyfile("eth0", ["[connection]\n", "id=eth0\n"])
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
        with salt.utils.files.fopen(path) as fh:
            assert "id=eth0" in fh.read()

        # Rewriting an over-permissive existing keyfile still yields 0600.
        os.chmod(path, 0o644)
        nm_ip._write_keyfile("eth0", ["[connection]\n", "id=eth0-v2\n"])
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
        with salt.utils.files.fopen(path) as fh:
            assert "id=eth0-v2" in fh.read()

        # No stray temporary files left in the keyfile directory.
        assert [p.name for p in tmp_path.iterdir()] == [os.path.basename(path)]
