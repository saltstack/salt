"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.win_ip
"""

import pytest

import salt.modules.win_ip as win_ip
from salt.exceptions import CommandExecutionError, SaltInvocationError
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def configure_loader_modules():
    return {win_ip: {}}


@pytest.fixture
def ethernet_config():
    return (
        'Configuration for interface "Ethernet"\n'
        "DHCP enabled: Yes\n"
        "IP Address: 1.2.3.74\n"
        "Subnet Prefix: 1.2.3.0/24 (mask 255.255.255.0)\n"
        "Default Gateway: 1.2.3.1\n"
        "Gateway Metric: 0\n"
        "InterfaceMetric: 20\n"
        "DNS servers configured through DHCP: 1.2.3.4\n"
        "Register with which suffix: Primary only\n"
        "WINS servers configured through DHCP: None\n"
    )


@pytest.fixture
def ethernet_enable():
    return "Ethernet\nType: Dedicated\nAdministrative state: Enabled\nConnect state: Connected"


# 'raw_interface_configs' function tests: 1


def test_raw_interface_configs(ethernet_config):
    """
    Test if it return raw configs for all interfaces.
    """
    mock_cmd = MagicMock(return_value=ethernet_config)
    with patch.dict(win_ip.__salt__, {"cmd.run": mock_cmd}):
        assert win_ip.raw_interface_configs() == ethernet_config


# 'get_all_interfaces' function tests: 1


def test_get_all_interfaces(ethernet_config):
    """
    Test if it return configs for all interfaces.
    """
    ret = {
        "Ethernet": {
            "DHCP enabled": "Yes",
            "DNS servers configured through DHCP": ["1.2.3.4"],
            "Default Gateway": "1.2.3.1",
            "Gateway Metric": "0",
            "InterfaceMetric": "20",
            "Register with which suffix": "Primary only",
            "WINS servers configured through DHCP": ["None"],
            "ip_addrs": [
                {
                    "IP Address": "1.2.3.74",
                    "Netmask": "255.255.255.0",
                    "Subnet": "1.2.3.0/24",
                }
            ],
        }
    }

    mock_cmd = MagicMock(return_value=ethernet_config)
    with patch.dict(win_ip.__salt__, {"cmd.run": mock_cmd}):
        assert win_ip.get_all_interfaces() == ret


# 'get_interface' function tests: 1


def test_get_interface(ethernet_config):
    """
    Test if it return the configuration of a network interface.
    """
    ret = {
        "DHCP enabled": "Yes",
        "DNS servers configured through DHCP": ["1.2.3.4"],
        "Default Gateway": "1.2.3.1",
        "Gateway Metric": "0",
        "InterfaceMetric": "20",
        "Register with which suffix": "Primary only",
        "WINS servers configured through DHCP": ["None"],
        "ip_addrs": [
            {
                "IP Address": "1.2.3.74",
                "Netmask": "255.255.255.0",
                "Subnet": "1.2.3.0/24",
            }
        ],
    }

    mock_cmd = MagicMock(return_value=ethernet_config)
    with patch.dict(win_ip.__salt__, {"cmd.run": mock_cmd}):
        assert win_ip.get_interface("Ethernet") == ret


# 'is_enabled' function tests: 1


def test_is_enabled(ethernet_enable):
    """
    Test if it returns `True` if interface is enabled, otherwise `False`.
    """
    mock_cmd = MagicMock(side_effect=[ethernet_enable, ""])
    with patch.dict(win_ip.__salt__, {"cmd.run": mock_cmd}):
        assert win_ip.is_enabled("Ethernet")
        pytest.raises(CommandExecutionError, win_ip.is_enabled, "Ethernet")


# 'is_disabled' function tests: 1


def test_is_disabled(ethernet_enable):
    """
    Test if it returns `True` if interface is disabled, otherwise `False`.
    """
    mock_cmd = MagicMock(return_value=ethernet_enable)
    with patch.dict(win_ip.__salt__, {"cmd.run": mock_cmd}):
        assert not win_ip.is_disabled("Ethernet")


# 'enable' function tests: 1


def test_enable():
    """
    Test if it enable an interface.
    """
    # Test with enabled interface
    with patch.object(win_ip, "is_enabled", return_value=True):
        assert win_ip.enable("Ethernet")

    mock_cmd = MagicMock()
    with patch.object(win_ip, "is_enabled", side_effect=[False, True]), patch.dict(
        win_ip.__salt__, {"cmd.run": mock_cmd}
    ):
        assert win_ip.enable("Ethernet")

    mock_cmd.assert_called_once_with(
        [
            "netsh",
            "interface",
            "set",
            "interface",
            "name=Ethernet",
            "admin=ENABLED",
        ],
        python_shell=False,
    )


# 'disable' function tests: 1


def test_disable():
    """
    Test if it disable an interface.
    """
    with patch.object(win_ip, "is_disabled", return_value=True):
        assert win_ip.disable("Ethernet")

    mock_cmd = MagicMock()
    with patch.object(win_ip, "is_disabled", side_effect=[False, True]), patch.dict(
        win_ip.__salt__, {"cmd.run": mock_cmd}
    ):
        assert win_ip.disable("Ethernet")

    mock_cmd.assert_called_once_with(
        [
            "netsh",
            "interface",
            "set",
            "interface",
            "name=Ethernet",
            "admin=DISABLED",
        ],
        python_shell=False,
    )


# 'get_subnet_length' function tests: 1


def test_get_subnet_length():
    """
    Test if it disable an interface.
    """
    assert win_ip.get_subnet_length("255.255.255.0") == 24
    pytest.raises(SaltInvocationError, win_ip.get_subnet_length, "255.255.0")


# 'set_static_ip' function tests: 1


@pytest.mark.slow_test
def test_set_static_ip(ethernet_config):
    """
    Test if it set static IP configuration on a Windows NIC.
    """
    pytest.raises(
        SaltInvocationError,
        win_ip.set_static_ip,
        "Local Area Connection",
        "10.1.2/24",
    )

    mock_cmd = MagicMock(return_value=ethernet_config)
    mock_all = MagicMock(return_value={"retcode": 1, "stderr": "Error"})
    with patch.dict(win_ip.__salt__, {"cmd.run": mock_cmd, "cmd.run_all": mock_all}):
        pytest.raises(
            CommandExecutionError,
            win_ip.set_static_ip,
            "Ethernet",
            "1.2.3.74/24",
            append=True,
        )
        pytest.raises(
            CommandExecutionError, win_ip.set_static_ip, "Ethernet", "1.2.3.74/24"
        )

    mock_all = MagicMock(return_value={"retcode": 0})
    with patch.dict(win_ip.__salt__, {"cmd.run": mock_cmd, "cmd.run_all": mock_all}):
        assert win_ip.set_static_ip("Local Area Connection", "1.2.3.74/24") == {}
        assert win_ip.set_static_ip("Ethernet", "1.2.3.74/24") == {
            "Address Info": {
                "IP Address": "1.2.3.74",
                "Netmask": "255.255.255.0",
                "Subnet": "1.2.3.0/24",
            }
        }


# 'set_dhcp_ip' function tests: 1


def test_set_dhcp_ip(ethernet_config):
    """
    Test if it set Windows NIC to get IP from DHCP.
    """
    mock_cmd = MagicMock(return_value=ethernet_config)
    with patch.dict(win_ip.__salt__, {"cmd.run": mock_cmd}):
        assert win_ip.set_dhcp_ip("Ethernet") == {
            "DHCP enabled": "Yes",
            "Interface": "Ethernet",
        }


# 'set_static_dns' function tests: 1


def test_set_static_dns():
    """
    Test if it set static DNS configuration on a Windows NIC.
    """
    mock_cmd = MagicMock()
    with patch.dict(win_ip.__salt__, {"cmd.run": mock_cmd}):
        assert win_ip.set_static_dns("Ethernet", "192.168.1.252", "192.168.1.253") == {
            "DNS Server": ("192.168.1.252", "192.168.1.253"),
            "Interface": "Ethernet",
        }
        mock_cmd.assert_has_calls(
            [
                call(
                    [
                        "netsh",
                        "interface",
                        "ip",
                        "set",
                        "dns",
                        "name=Ethernet",
                        "source=static",
                        "address=192.168.1.252",
                        "register=primary",
                    ],
                    python_shell=False,
                ),
                call(
                    [
                        "netsh",
                        "interface",
                        "ip",
                        "add",
                        "dns",
                        "name=Ethernet",
                        "address=192.168.1.253",
                        "index=2",
                    ],
                    python_shell=False,
                ),
            ]
        )


def test_set_static_dns_clear():
    """
    Test if it set static DNS configuration on a Windows NIC.
    """
    mock_cmd = MagicMock()
    with patch.dict(win_ip.__salt__, {"cmd.run": mock_cmd}):
        assert win_ip.set_static_dns("Ethernet", []) == {
            "DNS Server": [],
            "Interface": "Ethernet",
        }
        mock_cmd.assert_called_once_with(
            [
                "netsh",
                "interface",
                "ip",
                "set",
                "dns",
                "name=Ethernet",
                "source=static",
                "address=none",
            ],
            python_shell=False,
        )


def test_set_static_dns_no_action():
    """
    Test if it set static DNS configuration on a Windows NIC.
    """
    # Test passing nothing
    assert win_ip.set_static_dns("Ethernet") == {
        "DNS Server": "No Changes",
        "Interface": "Ethernet",
    }
    # Test passing None
    assert win_ip.set_static_dns("Ethernet", None) == {
        "DNS Server": "No Changes",
        "Interface": "Ethernet",
    }

    # Test passing string None
    assert win_ip.set_static_dns("Ethernet", "None") == {
        "DNS Server": "No Changes",
        "Interface": "Ethernet",
    }


# 'set_dhcp_dns' function tests: 1


def test_set_dhcp_dns(ethernet_config):
    """
    Test if it set DNS source to DHCP on Windows.
    """
    mock_cmd = MagicMock(return_value=ethernet_config)
    with patch.dict(win_ip.__salt__, {"cmd.run": mock_cmd}):
        assert win_ip.set_dhcp_dns("Ethernet") == {
            "DNS Server": "DHCP",
            "Interface": "Ethernet",
        }


# 'set_dhcp_all' function tests: 1


def test_set_dhcp_all(ethernet_config):
    """
    Test if it set both IP Address and DNS to DHCP.
    """
    mock_cmd = MagicMock(return_value=ethernet_config)
    with patch.dict(win_ip.__salt__, {"cmd.run": mock_cmd}):
        assert win_ip.set_dhcp_all("Ethernet") == {
            "Interface": "Ethernet",
            "DNS Server": "DHCP",
            "DHCP enabled": "Yes",
        }


# 'get_default_gateway' function tests: 1


def test_get_default_gateway(ethernet_config):
    """
    Test if it set DNS source to DHCP on Windows.
    """
    mock_cmd = MagicMock(return_value=ethernet_config)
    with patch.dict(win_ip.__salt__, {"cmd.run": mock_cmd}):
        assert win_ip.get_default_gateway() == "1.2.3.1"
