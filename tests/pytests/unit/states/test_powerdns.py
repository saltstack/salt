import pytest
import salt.states.powerdns as powerdns
from salt.exceptions import CommandExecutionError, SaltInvocationError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {powerdns: {}}


def test_managed_zone_path_empty_key():
    with pytest.raises(SaltInvocationError):
        powerdns.managed_zone("test_domain", "", "server")


def test_managed_zone_path_empty_server():
    with pytest.raises(SaltInvocationError):
        powerdns.managed_zone("test_domain", "key", "")


def test_managed_zone_path_empty_name():
    ret = {
        "name": "",
        "changes": {},
        "result": False,
        "comment": "No name of zone provided",
    }
    result = powerdns.managed_zone("", "key", "server")


def test_managed_zone_was_updated():
    result_changes = {"changes": "Zone was updated"}
    mock_powerdns_modules = {
        "powerdns.manage_zone": MagicMock(return_value=result_changes)
    }
    with patch.dict(powerdns.__salt__, mock_powerdns_modules):
        ret = {
            "name": "zone",
            "changes": "Zone was updated",
            "result": True,
            "comment": "",
        }
        result = powerdns.managed_zone("zone", "key", "server")
    assert result == ret


def test_managed_zone_failed():
    mock_powerdns_modules = {
        "powerdns.manage_zone": MagicMock(side_effect=[CommandExecutionError])
    }
    with patch.dict(powerdns.__salt__, mock_powerdns_modules):

        with pytest.raises(CommandExecutionError):
            powerdns.managed_zone("test_domain", "key", "server")


def test_absent_zone_path_empty_key():
    with pytest.raises(SaltInvocationError):
        powerdns.absent_zone("test_domain", "", "server")


def test_absent_zone_path_empty_server():
    with pytest.raises(SaltInvocationError):
        powerdns.absent_zone("test_domain", "key", "")


def test_absent_zone_path_empty_name():
    ret = {
        "name": "",
        "changes": {},
        "result": False,
        "comment": "No name of zone provided",
    }
    result = powerdns.absent_zone("", "key", "server")
    assert result == ret


def test_absent_zone_deleted():
    result_changes = {"changes": "Zone was deleted"}
    mock_powerdns_modules = {
        "powerdns.delete_zone": MagicMock(return_value=result_changes)
    }
    with patch.dict(powerdns.__salt__, mock_powerdns_modules):
        ret = {
            "name": "zone",
            "changes": "Zone was deleted",
            "result": True,
            "comment": "",
        }
        result = powerdns.absent_zone("zone", "key", "server")
    assert result == ret


def test_absent_zone_failed():
    mock_powerdns_modules = {
        "powerdns.delete_zone": MagicMock(side_effect=[CommandExecutionError])
    }
    with patch.dict(powerdns.__salt__, mock_powerdns_modules):
        with pytest.raises(CommandExecutionError):
            powerdns.absent_zone("test_domain", "key", "server")
