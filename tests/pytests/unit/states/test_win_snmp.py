import pytest
import salt.states.win_snmp as win_snmp
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {win_snmp: {}}


def test_agent_settings():
    """
    Test - Manage the SNMP sysContact, sysLocation, and sysServices settings.
    """
    kwargs = {
        "name": "agent-settings",
        "contact": "TestContact",
        "location": "TestLocation",
        "services": ["Internet"],
    }
    ret = {
        "name": kwargs["name"],
        "changes": {},
        "comment": "Agent settings already contain the provided values.",
        "result": True,
    }
    # Using this instead of dictionary comprehension in order to make pylint happy.
    get_ret = {key: value for (key, value) in kwargs.items() if key != "name"}
    mock_value_get = MagicMock(return_value=get_ret)
    mock_value_set = MagicMock(return_value=True)
    with patch.dict(
        win_snmp.__salt__,
        {
            "win_snmp.get_agent_settings": mock_value_get,
            "win_snmp.set_agent_settings": mock_value_set,
        },
    ):
        with patch.dict(win_snmp.__opts__, {"test": False}):
            assert win_snmp.agent_settings(**kwargs) == ret


def test_auth_traps_enabled():
    """
    Test - Manage the sending of authentication traps.
    """
    kwargs = {"name": "auth-traps", "status": True}
    ret = {
        "name": kwargs["name"],
        "changes": {"old": False, "new": True},
        "comment": "Set EnableAuthenticationTraps to contain the provided value.",
        "result": True,
    }
    mock_value_get = MagicMock(return_value=False)
    mock_value_set = MagicMock(return_value=True)
    with patch.dict(
        win_snmp.__salt__,
        {
            "win_snmp.get_auth_traps_enabled": mock_value_get,
            "win_snmp.set_auth_traps_enabled": mock_value_set,
        },
    ):
        with patch.dict(win_snmp.__opts__, {"test": False}):
            assert win_snmp.auth_traps_enabled(**kwargs) == ret
        with patch.dict(win_snmp.__opts__, {"test": True}):
            ret["comment"] = "EnableAuthenticationTraps will be changed."
            ret["result"] = None
            assert win_snmp.auth_traps_enabled(**kwargs) == ret


def test_community_names():
    """
    Test - Manage the SNMP accepted community names and their permissions.
    """
    kwargs = {
        "name": "community-names",
        "communities": {"TestCommunity": "Read Create"},
    }
    ret = {
        "name": kwargs["name"],
        "changes": {},
        "comment": "Communities already contain the provided values.",
        "result": True,
    }
    mock_value_get = MagicMock(return_value=kwargs["communities"])
    mock_value_set = MagicMock(return_value=True)
    with patch.dict(
        win_snmp.__salt__,
        {
            "win_snmp.get_community_names": mock_value_get,
            "win_snmp.set_community_names": mock_value_set,
        },
    ):
        with patch.dict(win_snmp.__opts__, {"test": False}):
            assert win_snmp.community_names(**kwargs) == ret
