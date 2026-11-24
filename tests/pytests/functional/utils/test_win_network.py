"""
Test the win_network util
"""

import pytest

import salt.utils.win_network as win_network

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture(scope="module", autouse=True)
def _require_dotnet_network():
    # clr_loader ships only x86/amd64 ClrLoader.dll; on Windows ARM64
    # pythonnet fails and win_network falls back to WMI (USE_WMI=True).
    if win_network.USE_WMI:
        pytest.skip(
            "pythonnet NetworkInformation unavailable; win_network using WMI fallback"
        )


def test__get_ip_base_properties():
    interfaces = win_network._get_network_interfaces()
    for interface in interfaces:
        base_properties = win_network._get_ip_base_properties(interface)
        assert "ipv4_dhcp_enabled" in base_properties
        assert "ipv4_forwarding_enabled" in base_properties
        assert "ipv4_wins_enabled" in base_properties


def test_get_interface_info_dot_net_formatted():
    interfaces = win_network.get_interface_info_dot_net_formatted()
    for interface in interfaces:
        assert "description" in interfaces[interface]
        assert "hwaddr" in interfaces[interface]
        assert "up" in interfaces[interface]
        assert "dhcp_enabled" in interfaces[interface]["inet"][0]
