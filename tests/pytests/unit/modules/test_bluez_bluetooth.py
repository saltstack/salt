"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""


import pytest

import salt.modules.bluez_bluetooth as bluez
import salt.utils.validate.net
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


class MockBluetooth:
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


@pytest.fixture
def configure_loader_modules():
    return {bluez: {"bluetooth": MockBluetooth()}}


def test_version():
    """
    Test if return bluetooth version
    """
    mock = MagicMock(return_value="5.7")
    with patch.dict(bluez.__salt__, {"cmd.run": mock}):
        assert bluez.version() == {
            "PyBluez": "<= 0.18 (Unknown, but installed)",
            "Bluez": "5.7",
        }


def test_address_():
    """
    Test of getting address of bluetooth adapter
    """
    mock = MagicMock(return_value="hci : hci0")
    with patch.dict(bluez.__salt__, {"cmd.run": mock}):
        assert bluez.address_() == {
            "hci ": {"device": "hci ", "path": "/sys/class/bluetooth/hci "}
        }


def test_power():
    """
    Test of getting address of bluetooth adapter
    """
    mock = MagicMock(return_value={})
    with patch.object(bluez, "address_", mock):
        pytest.raises(CommandExecutionError, bluez.power, "hci0", "on")

    mock = MagicMock(return_value={"hci0": {"device": "hci0", "power": "on"}})
    with patch.object(bluez, "address_", mock):
        mock = MagicMock(return_value="")
        with patch.dict(bluez.__salt__, {"cmd.run": mock}):
            assert bluez.power("hci0", "on")

    mock = MagicMock(return_value={"hci0": {"device": "hci0", "power": "on"}})
    with patch.object(bluez, "address_", mock):
        mock = MagicMock(return_value="")
        with patch.dict(bluez.__salt__, {"cmd.run": mock}):
            assert not bluez.power("hci0", "off")


def test_discoverable():
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
        pytest.raises(CommandExecutionError, bluez.discoverable, "hci0")

        mock = MagicMock(return_value="UP RUNNING ISCAN")
        with patch.dict(bluez.__salt__, {"cmd.run": mock}):
            assert bluez.discoverable("hci0")

        mock = MagicMock(return_value="")
        with patch.dict(bluez.__salt__, {"cmd.run": mock}):
            assert not bluez.discoverable("hci0")


def test_noscan():
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
        pytest.raises(CommandExecutionError, bluez.noscan, "hci0")

        mock = MagicMock(return_value="SCAN")
        with patch.dict(bluez.__salt__, {"cmd.run": mock}):
            assert not bluez.noscan("hci0")

        mock = MagicMock(return_value="")
        with patch.dict(bluez.__salt__, {"cmd.run": mock}):
            assert bluez.noscan("hci0")


def test_scan():
    """
    Test of scanning of bluetooth devices
    """
    assert bluez.scan() == [{"a": "b"}, {"d": "e"}]


def test_block():
    """
    Test of blocking specific bluetooth device
    """
    mock = MagicMock(side_effect=[False, True])
    with patch.object(salt.utils.validate.net, "mac", mock):
        pytest.raises(CommandExecutionError, bluez.block, "DE:AD:BE:EF:CA:ZE")

        mock = MagicMock(return_value="")
        with patch.dict(bluez.__salt__, {"cmd.run": mock}):
            assert bluez.block("DE:AD:BE:EF:CA:FE") is None


def test_unblock():
    """
    Test to unblock specific bluetooth device
    """
    mock = MagicMock(side_effect=[False, True])
    with patch.object(salt.utils.validate.net, "mac", mock):
        pytest.raises(CommandExecutionError, bluez.block, "DE:AD:BE:EF:CA:ZE")

        mock = MagicMock(return_value="")
        with patch.dict(bluez.__salt__, {"cmd.run": mock}):
            assert bluez.unblock("DE:AD:BE:EF:CA:FE") is None


def test_pair():
    """
    Test to pair bluetooth adapter with a device
    """
    mock = MagicMock(side_effect=[False, True, True])
    with patch.object(salt.utils.validate.net, "mac", mock):
        pytest.raises(CommandExecutionError, bluez.pair, "DE:AD:BE:EF:CA:FE", "1234")

        pytest.raises(CommandExecutionError, bluez.pair, "DE:AD:BE:EF:CA:FE", "abcd")

        mock = MagicMock(return_value={"device": "hci0"})
        with patch.object(bluez, "address_", mock):
            mock = MagicMock(return_value="Ok")
            with patch.dict(bluez.__salt__, {"cmd.run": mock}):
                assert bluez.pair("DE:AD:BE:EF:CA:FE", "1234") == ["Ok"]


def test_unpair():
    """
    Test to unpair bluetooth adaptor with a device
    """
    mock = MagicMock(side_effect=[False, True])
    with patch.object(salt.utils.validate.net, "mac", mock):
        pytest.raises(CommandExecutionError, bluez.unpair, "DE:AD:BE:EF:CA:FE")

        mock = MagicMock(return_value="Ok")
        with patch.dict(bluez.__salt__, {"cmd.run": mock}):
            assert bluez.unpair("DE:AD:BE:EF:CA:FE") == ["Ok"]


def test_start():
    """
    Test to start bluetooth service
    """
    mock = MagicMock(return_value="Ok")
    with patch.dict(bluez.__salt__, {"service.start": mock}):
        assert bluez.start() == "Ok"


def test_stop():
    """
    Test to stop bluetooth service
    """
    mock = MagicMock(return_value="Ok")
    with patch.dict(bluez.__salt__, {"service.stop": mock}):
        assert bluez.stop() == "Ok"
