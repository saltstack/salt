"""
Test cases for salt.states.openvswitch_db.
"""

import pytest

import salt.states.openvswitch_db as openvswitch_db
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {openvswitch_db: {"__opts__": {"test": False}}}


def test_managed_different_entry_present():
    """
    Test managed function.

    This tests the case where there already is an entry, but it does not match.
    """
    get_mock = MagicMock(return_value="01:02:03:04:05:06")
    set_mock = MagicMock(return_value=None)
    with patch.dict(
        openvswitch_db.__salt__,
        {"openvswitch.db_get": get_mock, "openvswitch.db_set": set_mock},
    ):
        ret = openvswitch_db.managed(
            name="br0", table="Interface", data={"mac": "01:02:03:04:05:07"}
        )
        get_mock.assert_called_with("Interface", "br0", "mac", True)
        set_mock.assert_called_with("Interface", "br0", "mac", "01:02:03:04:05:07")
        assert ret["result"] is True
        assert ret["changes"] == {
            "mac": {"old": "01:02:03:04:05:06", "new": "01:02:03:04:05:07"}
        }


def test_managed_matching_entry_present():
    """
    Test managed function.

    This tests the case where there already is a matching entry.
    """
    get_mock = MagicMock(return_value="01:02:03:04:05:06")
    set_mock = MagicMock(return_value=None)
    with patch.dict(
        openvswitch_db.__salt__,
        {"openvswitch.db_get": get_mock, "openvswitch.db_set": set_mock},
    ):
        ret = openvswitch_db.managed(
            name="br0", table="Interface", data={"mac": "01:02:03:04:05:06"}
        )
        get_mock.assert_called_with("Interface", "br0", "mac", True)
        set_mock.assert_not_called()
        assert ret["result"] is True
        assert "changes" not in ret or not ret["changes"]


def test_managed_no_entry_present():
    """
    Test managed function.

    This tests the case where there is no entry yet.
    """
    get_mock = MagicMock(return_value="01:02:03:04:05:06")
    set_mock = MagicMock(return_value=None)
    with patch.dict(
        openvswitch_db.__salt__,
        {"openvswitch.db_get": get_mock, "openvswitch.db_set": set_mock},
    ):
        ret = openvswitch_db.managed(
            name="br0", table="Interface", data={"mac": "01:02:03:04:05:07"}
        )
        get_mock.assert_called_with("Interface", "br0", "mac", True)
        set_mock.assert_called_with("Interface", "br0", "mac", "01:02:03:04:05:07")
        assert ret["result"] is True
        assert ret["changes"] == {
            "mac": {"old": "01:02:03:04:05:06", "new": "01:02:03:04:05:07"}
        }
