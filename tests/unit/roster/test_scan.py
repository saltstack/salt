"""
Test the scan roster.
"""

import socket

import salt.roster.scan as scan_
from tests.support import mixins
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class ScanRosterTestCase(TestCase, mixins.LoaderModuleMockMixin):
    """Test the directory roster"""

    def setup_loader_modules(self):
        return {scan_: {"__opts__": {"ssh_scan_ports": "22", "ssh_scan_timeout": 0.01}}}

    def test_single_ip(self):
        """Test that minion files in the directory roster match and render."""
        with patch("salt.utils.network.get_socket"):
            ret = scan_.targets("127.0.0.1")
        self.assertEqual(ret, {"127.0.0.1": {"host": "127.0.0.1", "port": 22}})

    def test_single_network(self):
        """Test that minion files in the directory roster match and render."""
        with patch("salt.utils.network.get_socket"):
            ret = scan_.targets("127.0.0.0/30")
        self.assertEqual(
            ret,
            {
                "127.0.0.1": {"host": "127.0.0.1", "port": 22},
                "127.0.0.2": {"host": "127.0.0.2", "port": 22},
            },
        )

    def test_multiple_ips(self):
        """Test that minion files in the directory roster match and render."""
        with patch("salt.utils.network.get_socket"):
            ret = scan_.targets(["127.0.0.1", "127.0.0.2"], tgt_type="list")
        self.assertEqual(
            ret,
            {
                "127.0.0.1": {"host": "127.0.0.1", "port": 22},
                "127.0.0.2": {"host": "127.0.0.2", "port": 22},
            },
        )

    def test_multiple_networks(self):
        """Test that minion files in the directory roster match and render."""
        with patch("salt.utils.network.get_socket"):
            ret = scan_.targets(
                ["127.0.0.0/30", "127.0.2.1", "127.0.1.0/30"], tgt_type="list"
            )
        self.assertEqual(
            ret,
            {
                "127.0.0.1": {"host": "127.0.0.1", "port": 22},
                "127.0.0.2": {"host": "127.0.0.2", "port": 22},
                "127.0.2.1": {"host": "127.0.2.1", "port": 22},
                "127.0.1.1": {"host": "127.0.1.1", "port": 22},
                "127.0.1.2": {"host": "127.0.1.2", "port": 22},
            },
        )

    def test_malformed_ip(self):
        """Test that minion files in the directory roster match and render."""
        with patch("salt.utils.network.get_socket"):
            ret = scan_.targets("127001")
        self.assertEqual(ret, {})

    def test_multiple_with_malformed(self):
        """Test that minion files in the directory roster match and render."""
        with patch("salt.utils.network.get_socket"):
            ret = scan_.targets(
                ["127.0.0.1", "127002", "127.0.1.0/30"], tgt_type="list"
            )
        self.assertEqual(
            ret,
            {
                "127.0.0.1": {"host": "127.0.0.1", "port": 22},
                "127.0.1.1": {"host": "127.0.1.1", "port": 22},
                "127.0.1.2": {"host": "127.0.1.2", "port": 22},
            },
        )

    def test_multiple_no_connection(self):
        """Test that minion files in the directory roster match and render."""
        socket_mock = MagicMock()
        socket_mock.connect = MagicMock(
            side_effect=[None, socket.error(), None, socket.error(), None]
        )
        with patch("salt.utils.network.get_socket", return_value=socket_mock):
            ret = scan_.targets(
                ["127.0.0.0/30", "127.0.2.1", "127.0.1.0/30"], tgt_type="list"
            )
        self.assertEqual(
            ret,
            {
                "127.0.0.1": {"host": "127.0.0.1", "port": 22},
                "127.0.0.2": {},
                "127.0.2.1": {"host": "127.0.2.1", "port": 22},
                "127.0.1.1": {},
                "127.0.1.2": {"host": "127.0.1.2", "port": 22},
            },
        )
