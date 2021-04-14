"""
    :codeauthor: :email:`Mike Adams <adammike@us.ibm.com>`
"""

import os

import pytest
import salt.modules.network as network
import salt.utils.network as utils_network
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {network: {}}


@pytest.fixture
def expected_routes():
    return [
        {
            "destination": "0.0.0.0",
            "addr_family": "inet",
            "netmask": "0.0.0.0",
            "flags": "UG",
            "interface": "eth0",
            "gateway": "100.64.24.145",
        },
        {
            "destination": "100.64.24.144",
            "addr_family": "inet",
            "netmask": "255.255.255.240",
            "flags": "U",
            "interface": "eth0",
            "gateway": "0.0.0.0",
        },
        {
            "destination": "169.254.0.0",
            "addr_family": "inet",
            "netmask": "255.255.0.0",
            "flags": "U",
            "interface": "eth0",
            "gateway": "0.0.0.0",
        },
        {
            "destination": "192.168.0.0",
            "addr_family": "inet",
            "netmask": "255.255.255.0",
            "flags": "UG",
            "interface": "eth0",
            "gateway": "100.64.24.145",
        },
        {
            "destination": "192.168.1.0",
            "addr_family": "inet",
            "netmask": "255.255.255.0",
            "flags": "UG",
            "interface": "eth0",
            "gateway": "100.64.24.145",
        },
    ]


def test_ip_route_linux_ipv4(expected_routes):
    """
    Tests that _ip_route_linux can parse ipv4 routes appropriately
    """
    ip_route_output = [
        "default via 100.64.24.145 dev eth0",
        "100.64.24.144/28 dev eth0 proto kernel scope link src 100.64.24.148",
        "169.254.0.0/16 dev eth0 scope link metric 1002",
        "192.168.0.0/24 via 100.64.24.145 dev eth0",
        "192.168.1.0/24 via 100.64.24.145 dev eth0",
    ]

    mock_cmd = MagicMock(return_value=os.linesep.join(ip_route_output))
    mock_path = MagicMock(return_value=False)
    with patch.dict(network.__grains__, {"kernel": "Linux"}):
        with patch.dict(
            network.__utils__,
            {"path.which": mock_path, "network.calc_net": utils_network.calc_net},
        ):
            with patch.dict(network.__salt__, {"cmd.run": mock_cmd}):
                routes = network.routes(family="inet")
                assert len(routes) == len(expected_routes)
                for route in expected_routes:
                    assert route in routes


def test_netstat_route_linux_ipv4(expected_routes):
    """
    Tests that _netstat_route_linux can parse ipv4 routes appropriately
    """
    netstat_output = [
        "0.0.0.0         100.64.24.145   0.0.0.0         UG        0 0          0 eth0",
        "100.64.24.144   0.0.0.0         255.255.255.240 U         0 0          0 eth0",
        "169.254.0.0     0.0.0.0         255.255.0.0     U         0 0          0 eth0",
        "192.168.0.0     100.64.24.145   255.255.255.0   UG        0 0          0 eth0",
        "192.168.1.0     100.64.24.145   255.255.255.0   UG        0 0          0 eth0",
    ]

    mock_cmd = MagicMock(return_value=os.linesep.join(netstat_output))
    mock_path = MagicMock(return_value=True)
    mock_grains = {"kernel": "Linux"}
    with patch.dict(network.__grains__, mock_grains):
        with patch.dict(
            network.__utils__,
            {"path.which": mock_path, "network.calc_net": utils_network.calc_net},
        ):
            with patch.dict(network.__salt__, {"cmd.run": mock_cmd}):
                routes = network.routes(family="inet")
                assert len(routes) == len(expected_routes)
                for route in expected_routes:
                    assert route in routes
