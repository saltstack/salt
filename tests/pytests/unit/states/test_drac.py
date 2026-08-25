"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.drac as drac
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {drac: {}}


def test_present():
    """
    Test to ensure the user exists on the Dell DRAC
    """
    name = "damian"
    password = "secret"
    permission = "login,test_alerts,clear_logs"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock = MagicMock(return_value=[name])
    with patch.dict(drac.__salt__, {"drac.list_users": mock}):
        with patch.dict(drac.__opts__, {"test": True}):
            comt = f"`{name}` already exists"
            ret.update({"comment": comt})
            assert drac.present(name, password, permission) == ret

        with patch.dict(drac.__opts__, {"test": False}):
            comt = f"`{name}` already exists"
            ret.update({"comment": comt})
            assert drac.present(name, password, permission) == ret


def test_absent():
    """
    Test to ensure a user does not exist on the Dell DRAC
    """
    name = "damian"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock = MagicMock(return_value=[])
    with patch.dict(drac.__salt__, {"drac.list_users": mock}):
        with patch.dict(drac.__opts__, {"test": True}):
            comt = f"`{name}` does not exist"
            ret.update({"comment": comt})
            assert drac.absent(name) == ret

        with patch.dict(drac.__opts__, {"test": False}):
            comt = f"`{name}` does not exist"
            ret.update({"comment": comt})
            assert drac.absent(name) == ret


def test_network():
    """
    Test to ensure the DRAC network settings are consistent
    """
    ip_ = "10.225.108.29"
    netmask = "255.255.255.224"
    gateway = "10.225.108.1"

    ret = {"name": ip_, "result": None, "comment": "", "changes": {}}

    net_info = {
        "IPv4 settings": {
            "IP Address": ip_,
            "Subnet Mask": netmask,
            "Gateway": gateway,
        }
    }

    mock_info = MagicMock(return_value=net_info)
    mock_bool = MagicMock(side_effect=[True, False])
    with patch.dict(
        drac.__salt__,
        {"drac.network_info": mock_info, "drac.set_network": mock_bool},
    ):
        with patch.dict(drac.__opts__, {"test": True}):
            assert drac.network(ip_, netmask, gateway) == ret

        with patch.dict(drac.__opts__, {"test": False}):
            comt = "Network is in the desired state"
            ret.update({"comment": comt, "result": True})
            assert drac.network(ip_, netmask, gateway) == ret

            comt = "unable to configure network"
            ret.update({"comment": comt, "result": False})
            assert drac.network(ip_, netmask, gateway) == ret
