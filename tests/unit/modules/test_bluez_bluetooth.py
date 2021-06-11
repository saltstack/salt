# -*- coding: utf-8 -*-
"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.bluez_bluetooth as bluez
import salt.utils.validate.net
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class MockBluetooth(object):
    """
        Mock class for bluetooth
    """

    def __init__(self):
        pass

    @staticmethod
    def discover_devices(lookup_names):
        """
            Mock method to return all Discoverable devices
        """
        return [["a", "b", "c"], ["d", "e", "f"]]


class BluezTestCase(TestCase, LoaderModuleMockMixin):
    """
        Test cases for salt.modules.bluez
    """

    def setup_loader_modules(self):
        return {bluez: {"bluetooth": MockBluetooth()}}

    def test_version(self):
        """
            Test if return bluetooth version
        """
        mock = MagicMock(return_value="5.7")
        with patch.dict(bluez.__salt__, {"cmd.run": mock}):
            self.assertDictEqual(
                bluez.version(),
                {"PyBluez": "<= 0.18 (Unknown, but installed)", "Bluez": "5.7"},
            )

    def test_address_(self):
        """
            Test of getting address of bluetooth adapter
        """
        mock = MagicMock(return_value="hci : hci0")
        with patch.dict(bluez.__salt__, {"cmd.run": mock}):
            self.assertDictEqual(
                bluez.address_(),
                {"hci ": {"device": "hci ", "path": "/sys/class/bluetooth/hci "}},
            )

    def test_power(self):
        """
            Test of getting address of bluetooth adapter
        """
        mock = MagicMock(return_value={})
        with patch.object(bluez, "address_", mock):
            self.assertRaises(CommandExecutionError, bluez.power, "hci0", "on")

        mock = MagicMock(return_value={"hci0": {"device": "hci0", "power": "on"}})
        with patch.object(bluez, "address_", mock):
            mock = MagicMock(return_value="")
            with patch.dict(bluez.__salt__, {"cmd.run": mock}):
                self.assertTrue(bluez.power("hci0", "on"))

        mock = MagicMock(return_value={"hci0": {"device": "hci0", "power": "on"}})
        with patch.object(bluez, "address_", mock):
            mock = MagicMock(return_value="")
            with patch.dict(bluez.__salt__, {"cmd.run": mock}):
                self.assertFalse(bluez.power("hci0", "off"))

    def test_discoverable(self):
        """
            Test of enabling bluetooth device
        """
        mock = MagicMock(
            side_effect=[
                {},
                {"hci0": {"device": "hci0", "power": "on"}},
                {"hci0": {"device": "hci0", "power": "on"}},
            ]
        )
        with patch.object(bluez, "address_", mock):
            self.assertRaises(CommandExecutionError, bluez.discoverable, "hci0")

            mock = MagicMock(return_value="UP RUNNING ISCAN")
            with patch.dict(bluez.__salt__, {"cmd.run": mock}):
                self.assertTrue(bluez.discoverable("hci0"))

            mock = MagicMock(return_value="")
            with patch.dict(bluez.__salt__, {"cmd.run": mock}):
                self.assertFalse(bluez.discoverable("hci0"))

    def test_noscan(self):
        """
            Test of turning off of scanning modes
        """
        mock = MagicMock(
            side_effect=[
                {},
                {"hci0": {"device": "hci0", "power": "on"}},
                {"hci0": {"device": "hci0", "power": "on"}},
            ]
        )
        with patch.object(bluez, "address_", mock):
            self.assertRaises(CommandExecutionError, bluez.noscan, "hci0")

            mock = MagicMock(return_value="SCAN")
            with patch.dict(bluez.__salt__, {"cmd.run": mock}):
                self.assertFalse(bluez.noscan("hci0"))

            mock = MagicMock(return_value="")
            with patch.dict(bluez.__salt__, {"cmd.run": mock}):
                self.assertTrue(bluez.noscan("hci0"))

    def test_scan(self):
        """
            Test of scanning of bluetooth devices
        """
        self.assertListEqual(bluez.scan(), [{"a": "b"}, {"d": "e"}])

    def test_block(self):
        """
            Test of blocking specific bluetooth device
        """
        mock = MagicMock(side_effect=[False, True])
        with patch.object(salt.utils.validate.net, "mac", mock):
            self.assertRaises(CommandExecutionError, bluez.block, "DE:AD:BE:EF:CA:ZE")

            mock = MagicMock(return_value="")
            with patch.dict(bluez.__salt__, {"cmd.run": mock}):
                self.assertIsNone(bluez.block("DE:AD:BE:EF:CA:FE"))

    def test_unblock(self):
        """
            Test to unblock specific bluetooth device
        """
        mock = MagicMock(side_effect=[False, True])
        with patch.object(salt.utils.validate.net, "mac", mock):
            self.assertRaises(CommandExecutionError, bluez.block, "DE:AD:BE:EF:CA:ZE")

            mock = MagicMock(return_value="")
            with patch.dict(bluez.__salt__, {"cmd.run": mock}):
                self.assertIsNone(bluez.unblock("DE:AD:BE:EF:CA:FE"))

    def test_pair(self):
        """
            Test to pair bluetooth adapter with a device
        """
        mock = MagicMock(side_effect=[False, True, True])
        with patch.object(salt.utils.validate.net, "mac", mock):
            self.assertRaises(
                CommandExecutionError, bluez.pair, "DE:AD:BE:EF:CA:FE", "1234"
            )

            self.assertRaises(
                CommandExecutionError, bluez.pair, "DE:AD:BE:EF:CA:FE", "abcd"
            )

            mock = MagicMock(return_value={"device": "hci0"})
            with patch.object(bluez, "address_", mock):
                mock = MagicMock(return_value="Ok")
                with patch.dict(bluez.__salt__, {"cmd.run": mock}):
                    self.assertListEqual(
                        bluez.pair("DE:AD:BE:EF:CA:FE", "1234"), ["Ok"]
                    )

    def test_unpair(self):
        """
            Test to unpair bluetooth adaptor with a device
        """
        mock = MagicMock(side_effect=[False, True])
        with patch.object(salt.utils.validate.net, "mac", mock):
            self.assertRaises(CommandExecutionError, bluez.unpair, "DE:AD:BE:EF:CA:FE")

            mock = MagicMock(return_value="Ok")
            with patch.dict(bluez.__salt__, {"cmd.run": mock}):
                self.assertListEqual(bluez.unpair("DE:AD:BE:EF:CA:FE"), ["Ok"])

    def test_start(self):
        """
            Test to start bluetooth service
        """
        mock = MagicMock(return_value="Ok")
        with patch.dict(bluez.__salt__, {"service.start": mock}):
            self.assertEqual(bluez.start(), "Ok")

    def test_stop(self):
        """
            Test to stop bluetooth service
        """
        mock = MagicMock(return_value="Ok")
        with patch.dict(bluez.__salt__, {"service.stop": mock}):
            self.assertEqual(bluez.stop(), "Ok")
