"""
Unit tests for salt.modules.netplan_ip (the netplan 'ip' provider, #62219).
"""

import pytest

import salt.modules.netplan_ip as netplan_ip
import salt.utils.yaml
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        netplan_ip: {
            "__grains__": {"os_family": "Debian"},
            "__salt__": {},
        }
    }


def _parse(lines):
    """Parse build_interface()'s returned lines back into a netplan dict."""
    return salt.utils.yaml.safe_load("".join(lines))


# ---- __virtual__ / provider selection ----


def test_virtual_loads_when_netplan_active():
    with patch.dict(netplan_ip.__grains__, {"os_family": "Debian"}), patch.object(
        netplan_ip, "netplan_active", MagicMock(return_value=True)
    ):
        assert netplan_ip.__virtual__() == "ip"


def test_virtual_declines_without_netplan():
    with patch.dict(netplan_ip.__grains__, {"os_family": "Debian"}), patch.object(
        netplan_ip, "netplan_active", MagicMock(return_value=False)
    ):
        ret = netplan_ip.__virtual__()
    assert ret[0] is False


def test_virtual_declines_off_debian():
    with patch.dict(netplan_ip.__grains__, {"os_family": "RedHat"}), patch.object(
        netplan_ip, "netplan_active", MagicMock(return_value=True)
    ):
        ret = netplan_ip.__virtual__()
    assert ret[0] is False


def test_netplan_active_detection():
    with patch("salt.utils.path.which", MagicMock(return_value="/usr/sbin/netplan")):
        with patch("os.path.isdir", MagicMock(return_value=True)):
            assert netplan_ip.netplan_active() is True
        with patch("os.path.isdir", MagicMock(return_value=False)):
            assert netplan_ip.netplan_active() is False
    with patch("salt.utils.path.which", MagicMock(return_value=None)):
        with patch("os.path.isdir", MagicMock(return_value=True)):
            assert netplan_ip.netplan_active() is False


# ---- build_interface ----


def test_build_interface_static():
    with patch.object(netplan_ip, "_renderer", MagicMock(return_value="networkd")):
        lines = netplan_ip.build_interface(
            "eth1",
            "eth",
            True,
            proto="static",
            ipaddr="192.168.99.10",
            netmask="255.255.255.0",
            gateway="192.168.99.1",
            dns=["8.8.8.8", "8.8.4.4"],
            mtu=1500,
            test=True,
        )
    doc = _parse(lines)
    eth = doc["network"]["ethernets"]["eth1"]
    assert doc["network"]["version"] == 2
    assert doc["network"]["renderer"] == "networkd"
    assert eth["dhcp4"] is False
    assert eth["addresses"] == ["192.168.99.10/24"]
    assert {"to": "default", "via": "192.168.99.1"} in eth["routes"]
    assert eth["nameservers"] == {"addresses": ["8.8.8.8", "8.8.4.4"]}
    assert eth["mtu"] == 1500


def test_build_interface_dhcp():
    with patch.object(netplan_ip, "_renderer", MagicMock(return_value="networkd")):
        lines = netplan_ip.build_interface("eth0", "eth", True, proto="dhcp", test=True)
    eth = _parse(lines)["network"]["ethernets"]["eth0"]
    assert eth["dhcp4"] is True
    assert "addresses" not in eth


def test_build_interface_unsupported_option_raises():
    with patch.object(netplan_ip, "_renderer", MagicMock(return_value="networkd")):
        with pytest.raises(CommandExecutionError, match="does not support"):
            netplan_ip.build_interface(
                "eth0", "eth", True, proto="dhcp", ethtool={"rx": "on"}, test=True
            )


def test_build_interface_bad_type_raises():
    with pytest.raises(CommandExecutionError, match="interface type"):
        netplan_ip.build_interface("eth0", "carrier-pigeon", True, test=True)


def test_build_interface_writes_file_and_get_interface_roundtrips(tmp_path):
    with patch.object(netplan_ip, "_NETPLAN_DIR", str(tmp_path)), patch.object(
        netplan_ip, "_renderer", MagicMock(return_value="networkd")
    ):
        # no file yet
        assert netplan_ip.get_interface("eth1") == []
        written = netplan_ip.build_interface(
            "eth1",
            "eth",
            True,
            proto="static",
            ipaddr="10.0.0.5",
            netmask="255.255.255.0",
        )
        target = tmp_path / "90-salt-eth1.yaml"
        assert target.is_file()
        # get_interface returns exactly what was written -> state diff is stable
        assert netplan_ip.get_interface("eth1") == written
        assert _parse(written)["network"]["ethernets"]["eth1"]["addresses"] == [
            "10.0.0.5/24"
        ]


def test_build_interface_idempotent_serialization():
    """Same settings -> identical output, so the state sees no spurious diff."""
    kw = dict(proto="static", ipaddr="10.0.0.5", netmask="255.255.255.0", mtu=1400)
    with patch.object(netplan_ip, "_renderer", MagicMock(return_value="networkd")):
        a = netplan_ip.build_interface("eth1", "eth", True, test=True, **kw)
        b = netplan_ip.build_interface("eth1", "eth", True, test=True, **kw)
    assert a == b


# ---- routes ----


def test_build_routes_folds_destination_and_default():
    routes = [
        {
            "name": "r1",
            "ipaddr": "10.10.0.0",
            "netmask": "255.255.0.0",
            "gateway": "10.0.0.1",
        },
        {"name": "dflt", "ipaddr": "default", "gateway": "10.0.0.254"},
    ]
    lines = netplan_ip.build_routes("eth1", routes=routes)
    parsed = _parse(lines)["routes"]
    assert {"to": "10.10.0.0/16", "via": "10.0.0.1"} in parsed
    assert {"to": "default", "via": "10.0.0.254"} in parsed


def test_get_network_settings_is_empty():
    assert netplan_ip.get_network_settings() == []
    assert netplan_ip.build_network_settings() == []


# ---- apply ----


def test_apply_network_settings_runs_generate_and_apply():
    run_all = MagicMock(return_value={"retcode": 0, "stdout": "", "stderr": ""})
    with patch("salt.utils.path.which", MagicMock(return_value="/usr/sbin/netplan")):
        with patch.dict(netplan_ip.__salt__, {"cmd.run_all": run_all}):
            assert netplan_ip.apply_network_settings() is True
    called = [c.args[0] for c in run_all.mock_calls if c.args]
    assert ["/usr/sbin/netplan", "generate"] in called
    assert ["/usr/sbin/netplan", "apply"] in called


def test_apply_network_settings_test_mode_is_noop():
    run_all = MagicMock()
    with patch.dict(netplan_ip.__salt__, {"cmd.run_all": run_all}):
        assert netplan_ip.apply_network_settings(test=True) is True
    run_all.assert_not_called()


def test_apply_network_settings_raises_on_generate_failure():
    run_all = MagicMock(return_value={"retcode": 1, "stdout": "", "stderr": "boom"})
    with patch("salt.utils.path.which", MagicMock(return_value="/usr/sbin/netplan")):
        with patch.dict(netplan_ip.__salt__, {"cmd.run_all": run_all}):
            with pytest.raises(CommandExecutionError, match="netplan generate failed"):
                netplan_ip.apply_network_settings()
