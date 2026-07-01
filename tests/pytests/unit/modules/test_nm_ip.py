"""
Unit tests for salt.modules.nm_ip (the NetworkManager 'ip' provider, #54791).
"""

import pytest

import salt.modules.nm_ip as nm_ip
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
