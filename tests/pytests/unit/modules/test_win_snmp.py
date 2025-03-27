"""
    Test cases for salt.modules.win_snmp
"""

import pytest

import salt.modules.win_snmp as win_snmp
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def community_names():
    return {"TestCommunity": "Read Create"}


@pytest.fixture
def configure_loader_modules():
    return {win_snmp: {}}


def test_get_agent_service_types():
    """
    Test - Get the sysServices types that can be configured.
    """
    assert isinstance(win_snmp.get_agent_service_types(), list)


def test_get_permission_types():
    """
    Test - Get the permission types that can be configured for communities.
    """
    assert isinstance(win_snmp.get_permission_types(), list)


def test_get_auth_traps_enabled():
    """
    Test - Determine whether the host is configured to send authentication traps.
    """
    mock_value = MagicMock(return_value={"vdata": 1})
    with patch.dict(win_snmp.__utils__, {"reg.read_value": mock_value}):
        assert win_snmp.get_auth_traps_enabled()


def test_set_auth_traps_enabled():
    """
    Test - Manage the sending of authentication traps.
    """
    mock_value = MagicMock(return_value=True)
    kwargs = {"status": True}
    with patch.dict(win_snmp.__utils__, {"reg.set_value": mock_value}), patch(
        "salt.modules.win_snmp.get_auth_traps_enabled", MagicMock(return_value=True)
    ):
        assert win_snmp.set_auth_traps_enabled(**kwargs)


def test_get_community_names(community_names):
    """
    Test - Get the current accepted SNMP community names and their permissions.
    """
    mock_ret = MagicMock(return_value=[{"vdata": 16, "vname": "TestCommunity"}])
    mock_false = MagicMock(return_value=False)
    with patch.dict(
        win_snmp.__utils__,
        {"reg.list_values": mock_ret, "reg.key_exists": mock_false},
    ):
        assert win_snmp.get_community_names() == community_names


def test_get_community_names_gpo():
    """
    Test - Get the current accepted SNMP community names and their permissions.
    """
    mock_ret = MagicMock(return_value=[{"vdata": "TestCommunity", "vname": 1}])
    mock_false = MagicMock(return_value=True)
    with patch.dict(
        win_snmp.__utils__,
        {"reg.list_values": mock_ret, "reg.key_exists": mock_false},
    ):
        assert win_snmp.get_community_names() == {"TestCommunity": "Managed by GPO"}


def test_set_community_names(community_names):
    """
    Test - Manage the SNMP accepted community names and their permissions.
    """
    mock_true = MagicMock(return_value=True)
    kwargs = {"communities": community_names}
    mock_false = MagicMock(return_value=False)
    with patch.dict(
        win_snmp.__utils__,
        {"reg.set_value": mock_true, "reg.key_exists": mock_false},
    ), patch(
        "salt.modules.win_snmp.get_community_names",
        MagicMock(return_value=community_names),
    ):
        assert win_snmp.set_community_names(**kwargs)


def test_set_community_names_gpo(community_names):
    """
    Test - Manage the SNMP accepted community names and their permissions.
    """
    mock_true = MagicMock(return_value=True)
    kwargs = {"communities": community_names}
    with patch.dict(
        win_snmp.__utils__,
        {"reg.set_value": mock_true, "reg.key_exists": mock_true},
    ), patch(
        "salt.modules.win_snmp.get_community_names",
        MagicMock(return_value=community_names),
    ):
        pytest.raises(CommandExecutionError, win_snmp.set_community_names, **kwargs)
