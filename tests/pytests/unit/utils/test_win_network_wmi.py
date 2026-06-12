"""
Regression tests for salt.utils.win_network WMI code path.

These tests use mocking to exercise the WMI fallback (used when .NET is older
than 4.7.2) cross-platform; they do not require Windows.
"""

import salt.utils.win_network as win_network
import salt.utils.winapi
from tests.support.mock import MagicMock, patch


def _wmi_module_mock(adapters):
    wmi_mock = MagicMock()
    wmi_mock.WMI.return_value.Win32_NetworkAdapterConfiguration.return_value = adapters
    return wmi_mock


def _adapter(
    description="vmxnet3 Ethernet Adapter",
    mac_address="00:50:56:83:11:D5",
    ip_enabled=True,
    ip_addresses=("10.153.30.240",),
    gateways=("10.153.31.240",),
    subnet=("255.255.252.0",),
):
    adapter = MagicMock()
    adapter.Description = description
    adapter.MACAddress = mac_address
    adapter.IPEnabled = ip_enabled
    adapter.IPAddress = list(ip_addresses)
    adapter.DefaultIPGateway = list(gateways)
    adapter.IPSubnet = list(subnet)
    return adapter


def test_get_interface_info_wmi_gateway_not_reported_as_broadcast():
    """
    The WMI code path must report the default gateway under the ``gateway``
    key, not ``broadcast``. See https://github.com/saltstack/salt/issues/68692.

    It must also compute the real IPv4 broadcast from the address + netmask
    so the WMI path stays consistent with the .NET path
    (``get_interface_info_dot_net_formatted``).
    """
    adapter = _adapter()
    wmi_mock = _wmi_module_mock([adapter])
    with patch.object(win_network, "wmi", wmi_mock, create=True), patch.object(
        salt.utils.winapi, "Com", MagicMock()
    ):
        result = win_network.get_interface_info_wmi()

    inet = result["vmxnet3 Ethernet Adapter"]["inet"][0]
    # Gateway must be exposed under the correct key, not as broadcast.
    assert inet.get("gateway") == "10.153.31.240"
    # Broadcast must be derived from address + netmask (10.153.30.240/22),
    # matching the .NET path's behavior.
    assert inet.get("broadcast") == "10.153.31.255"


def test_get_interface_info_wmi_ipv6_gateway_not_reported_as_broadcast():
    """
    Same as above for IPv6 entries.
    """
    adapter = _adapter(
        ip_addresses=("fe80::1234",),
        gateways=("fe80::208:a2ff:fe0b:de70",),
        subnet=("64",),
    )
    wmi_mock = _wmi_module_mock([adapter])
    with patch.object(win_network, "wmi", wmi_mock, create=True), patch.object(
        salt.utils.winapi, "Com", MagicMock()
    ):
        result = win_network.get_interface_info_wmi()

    inet6 = result["vmxnet3 Ethernet Adapter"]["inet6"][0]
    assert inet6.get("broadcast") != "fe80::208:a2ff:fe0b:de70"
    assert inet6.get("gateway") == "fe80::208:a2ff:fe0b:de70"
