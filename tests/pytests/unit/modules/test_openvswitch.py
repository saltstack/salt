"""
Test cases for salt.modules.openvswitch.
"""

import pytest

import salt.modules.openvswitch as openvswitch
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {openvswitch: {}}


def test_bridge_create_may_not_exist():
    """
    Test bridge_create function.

    This tests the case where neither a parent nor the may-exists flag are
    specified.
    """
    mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        openvswitch.__salt__,
        {"cmd.run_all": mock},
    ):
        ret = openvswitch.bridge_create("br0", False)
        assert ret is True
        mock.assert_called_with("ovs-vsctl add-br br0")


def test_bridge_create_may_exist():
    """
    Test bridge_create function.

    This tests the case where no parent but the may-exists flag is specified.
    """
    mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        openvswitch.__salt__,
        {"cmd.run_all": mock},
    ):
        ret = openvswitch.bridge_create("br1", True)
        assert ret is True
        mock.assert_called_with("ovs-vsctl --may-exist add-br br1")


def test_bridge_create_with_parent_may_exist():
    """
    Test bridge_create function.

    This tests the case where a parent is specified but the may-exists flag is
    false.
    """
    mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        openvswitch.__salt__,
        {"cmd.run_all": mock},
    ):
        ret = openvswitch.bridge_create("br2", False, "br0", 42)
        assert ret is True
        mock.assert_called_with("ovs-vsctl add-br br2 br0 42")


def test_bridge_to_parent():
    """
    Test bridge_to_parent function.
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": "br0\n"})
    with patch.dict(
        openvswitch.__salt__,
        {"cmd.run_all": mock},
    ):
        ret = openvswitch.bridge_to_parent("br1")
        assert ret == "br0"
        mock.assert_called_with("ovs-vsctl br-to-parent br1")


def test_bridge_to_vlan():
    """
    Test bridge_to_vlan function.
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": "42\n"})
    with patch.dict(
        openvswitch.__salt__,
        {"cmd.run_all": mock},
    ):
        ret = openvswitch.bridge_to_vlan("br0")
        assert ret == 42
        mock.assert_called_with("ovs-vsctl br-to-vlan br0")


def test_db_get():
    """
    Test db_get function.
    """
    mock = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": '{"data":[["01:02:03:04:05:06"]],' '"headings":["mac"]}',
        }
    )
    with patch.dict(
        openvswitch.__salt__,
        {"cmd.run_all": mock},
    ):
        ret = openvswitch.db_get("Interface", "br0", "mac")
        assert ret == "01:02:03:04:05:06"
        mock.assert_called_with(
            [
                "ovs-vsctl",
                "--format=json",
                "--columns=mac",
                "list",
                "Interface",
                "br0",
            ]
        )


def test_db_set():
    """
    Test db_set function.
    """
    mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        openvswitch.__salt__,
        {"cmd.run_all": mock},
    ):
        openvswitch.db_set("Interface", "br0", "mac", "01:02:03:04:05:06")
        mock.assert_called_with(
            ["ovs-vsctl", "set", "Interface", "br0", 'mac="01:02:03:04:05:06"']
        )
