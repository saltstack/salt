"""
Test the scan roster.
"""

import socket

import pytest

import salt.roster.scan as scan_
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {scan_: {"__opts__": {"ssh_scan_ports": "22", "ssh_scan_timeout": 0.01}}}


def test_single_ip():
    """Test that minion files in the directory roster match and render."""
    with patch("salt.utils.network.get_socket"):
        ret = scan_.targets("127.0.0.1")
    assert ret == {"127.0.0.1": {"host": "127.0.0.1", "port": 22}}


def test_single_network():
    """Test that minion files in the directory roster match and render."""
    with patch("salt.utils.network.get_socket"):
        ret = scan_.targets("127.0.0.0/30")
    assert ret == {
        "127.0.0.1": {"host": "127.0.0.1", "port": 22},
        "127.0.0.2": {"host": "127.0.0.2", "port": 22},
    }


def test_multiple_ips():
    """Test that minion files in the directory roster match and render."""
    with patch("salt.utils.network.get_socket"):
        ret = scan_.targets(["127.0.0.1", "127.0.0.2"], tgt_type="list")
    assert ret == {
        "127.0.0.1": {"host": "127.0.0.1", "port": 22},
        "127.0.0.2": {"host": "127.0.0.2", "port": 22},
    }


def test_multiple_networks():
    """Test that minion files in the directory roster match and render."""
    with patch("salt.utils.network.get_socket"):
        ret = scan_.targets(
            ["127.0.0.0/30", "127.0.2.1", "127.0.1.0/30"], tgt_type="list"
        )
    assert ret == {
        "127.0.0.1": {"host": "127.0.0.1", "port": 22},
        "127.0.0.2": {"host": "127.0.0.2", "port": 22},
        "127.0.2.1": {"host": "127.0.2.1", "port": 22},
        "127.0.1.1": {"host": "127.0.1.1", "port": 22},
        "127.0.1.2": {"host": "127.0.1.2", "port": 22},
    }


def test_malformed_ip():
    """Test that minion files in the directory roster match and render."""
    with patch("salt.utils.network.get_socket"):
        ret = scan_.targets("127001")
    assert ret == {}


def test_multiple_with_malformed():
    """Test that minion files in the directory roster match and render."""
    with patch("salt.utils.network.get_socket"):
        ret = scan_.targets(["127.0.0.1", "127002", "127.0.1.0/30"], tgt_type="list")
    assert ret == {
        "127.0.0.1": {"host": "127.0.0.1", "port": 22},
        "127.0.1.1": {"host": "127.0.1.1", "port": 22},
        "127.0.1.2": {"host": "127.0.1.2", "port": 22},
    }


def test_multiple_no_connection():
    """Test that minion files in the directory roster match and render."""
    socket_mock = MagicMock()
    socket_mock.connect = MagicMock(
        side_effect=[None, socket.error(), None, socket.error(), None]
    )
    with patch("salt.utils.network.get_socket", return_value=socket_mock):
        ret = scan_.targets(
            ["127.0.0.0/30", "127.0.2.1", "127.0.1.0/30"], tgt_type="list"
        )
    assert ret == {
        "127.0.0.1": {"host": "127.0.0.1", "port": 22},
        "127.0.0.2": {},
        "127.0.2.1": {"host": "127.0.2.1", "port": 22},
        "127.0.1.1": {},
        "127.0.1.2": {"host": "127.0.1.2", "port": 22},
    }
