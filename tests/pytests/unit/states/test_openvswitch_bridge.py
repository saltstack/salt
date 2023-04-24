"""
Test cases for salt.states.openvswitch_bridge.
"""

import pytest

import salt.states.openvswitch_bridge as openvswitch_bridge
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {openvswitch_bridge: {"__opts__": {"test": False}}}


def test_present_no_parent_existing_no_parent():
    """
    Test present function, not specifying a parent.

    This tests the case where the bridge already exists and has no parent.
    """
    create_mock = MagicMock()
    exists_mock = MagicMock(return_value=True)
    to_parent_mock = MagicMock(return_value="br0")
    to_vlan_mock = MagicMock(return_value=0)
    with patch.dict(
        openvswitch_bridge.__salt__,
        {
            "openvswitch.bridge_create": create_mock,
            "openvswitch.bridge_exists": exists_mock,
            "openvswitch.bridge_to_parent": to_parent_mock,
            "openvswitch.bridge_to_vlan": to_vlan_mock,
        },
    ):
        ret = openvswitch_bridge.present(name="br0")
        create_mock.assert_not_called()
        assert ret["result"] is True


def test_present_no_parent_existing_with_parent():
    """
    Test present function, not specifying a parent.

    This tests the case where the bridge already exists and has a parent.
    """
    create_mock = MagicMock()
    exists_mock = MagicMock(return_value=True)
    to_parent_mock = MagicMock(return_value="br0")
    to_vlan_mock = MagicMock(return_value=42)
    with patch.dict(
        openvswitch_bridge.__salt__,
        {
            "openvswitch.bridge_create": create_mock,
            "openvswitch.bridge_exists": exists_mock,
            "openvswitch.bridge_to_parent": to_parent_mock,
            "openvswitch.bridge_to_vlan": to_vlan_mock,
        },
    ):
        # Bridge exists, but parent and VLAN do not match, so we expect a
        # result of False.
        ret = openvswitch_bridge.present(name="br1")
        create_mock.assert_not_called()
        assert ret["result"] is False


def test_present_no_parent_not_existing():
    """
    Test present function, not specifying a parent.

    This tests the case where the bridge does not exist yet.
    """
    create_mock = MagicMock(return_value=True)
    exists_mock = MagicMock(return_value=False)
    with patch.dict(
        openvswitch_bridge.__salt__,
        {
            "openvswitch.bridge_create": create_mock,
            "openvswitch.bridge_exists": exists_mock,
        },
    ):
        ret = openvswitch_bridge.present(name="br0")
        create_mock.assert_called_with("br0", parent=None, vlan=None)
        assert ret["result"] is True
        assert ret["changes"] == {
            "br0": {"new": "Bridge br0 created", "old": "Bridge br0 does not exist."}
        }


def test_present_with_parent_existing_with_parent():
    """
    Test present function, specifying a parent.

    This tests the case where the bridge already exists and has a parent that
    matches the specified one.
    """
    create_mock = MagicMock()
    exists_mock = MagicMock(return_value=True)
    to_parent_mock = MagicMock(return_value="br0")
    to_vlan_mock = MagicMock(return_value=42)
    with patch.dict(
        openvswitch_bridge.__salt__,
        {
            "openvswitch.bridge_create": create_mock,
            "openvswitch.bridge_exists": exists_mock,
            "openvswitch.bridge_to_parent": to_parent_mock,
            "openvswitch.bridge_to_vlan": to_vlan_mock,
        },
    ):
        # Bridge exists and parent VLAN matches
        ret = openvswitch_bridge.present(name="br1", parent="br0", vlan=42)
        create_mock.assert_not_called()
        assert ret["result"] is True


def test_present_with_parent_not_existing():
    """
    Test present function, specifying a parent.

    This tests the case where the bridge does not exist yet.
    """
    create_mock = MagicMock(return_value=True)
    exists_mock = MagicMock(return_value=False)
    with patch.dict(
        openvswitch_bridge.__salt__,
        {
            "openvswitch.bridge_create": create_mock,
            "openvswitch.bridge_exists": exists_mock,
        },
    ):
        ret = openvswitch_bridge.present(name="br1", parent="br0", vlan=42)
        create_mock.assert_called_with("br1", parent="br0", vlan=42)
        assert ret["result"] is True
        assert ret["changes"] == {
            "br1": {"new": "Bridge br1 created", "old": "Bridge br1 does not exist."}
        }
