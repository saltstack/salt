"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.ilo
"""


import tempfile

import pytest

import salt.modules.file
import salt.modules.ilo as ilo
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        ilo: {
            "__opts__": {"cachedir": tempfile.gettempdir()},
            "__salt__": {"file.remove": salt.modules.file.remove},
        }
    }


# '__execute_cmd' function tests: 1


def test_execute_cmd():
    """
    Test if __execute_command opens the temporary file
    properly when calling global_settings.
    """
    mock_cmd_run = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(ilo.__salt__, {"cmd.run_all": mock_cmd_run}):
        ret = ilo.global_settings()
        assert ret  # == True


# 'global_settings' function tests: 1


def test_global_settings():
    """
    Test if it shows global_settings
    """
    with patch(
        "salt.modules.ilo.__execute_cmd",
        MagicMock(return_value={"Global Settings": {}}),
    ):
        assert ilo.global_settings() == {"Global Settings": {}}


# 'set_http_port' function tests: 1


def test_set_http_port():
    """
    Test if it configure the port HTTP should listen on
    """
    with patch.object(
        ilo,
        "global_settings",
        return_value={"Global Settings": {"HTTP_PORT": {"VALUE": 80}}},
    ):
        assert ilo.set_http_port()

    with patch.object(
        ilo,
        "global_settings",
        return_value={"Global Settings": {"HTTP_PORT": {"VALUE": 40}}},
    ):
        with patch.object(ilo, "__execute_cmd", return_value={"Set HTTP Port": {}}):
            assert ilo.set_http_port() == {"Set HTTP Port": {}}


# 'set_https_port' function tests: 1


def test_set_https_port():
    """
    Test if it configure the port HTTPS should listen on
    """
    with patch.object(
        ilo,
        "global_settings",
        return_value={"Global Settings": {"HTTP_PORT": {"VALUE": 443}}},
    ):
        assert ilo.set_https_port()

    with patch.object(
        ilo,
        "global_settings",
        return_value={"Global Settings": {"HTTP_PORT": {"VALUE": 80}}},
    ):
        with patch.object(ilo, "__execute_cmd", return_value={"Set HTTPS Port": {}}):
            assert ilo.set_https_port() == {"Set HTTPS Port": {}}


# 'enable_ssh' function tests: 1


def test_enable_ssh():
    """
    Test if it enable the SSH daemon
    """
    with patch.object(
        ilo,
        "global_settings",
        return_value={"Global Settings": {"SSH_STATUS": {"VALUE": "Y"}}},
    ):
        assert ilo.enable_ssh()

    with patch.object(
        ilo,
        "global_settings",
        return_value={"Global Settings": {"SSH_STATUS": {"VALUE": "N"}}},
    ):
        with patch.object(ilo, "__execute_cmd", return_value={"Enable SSH": {}}):
            assert ilo.enable_ssh() == {"Enable SSH": {}}


# 'disable_ssh' function tests: 1


def test_disable_ssh():
    """
    Test if it disable the SSH daemon
    """
    with patch.object(
        ilo,
        "global_settings",
        return_value={"Global Settings": {"SSH_STATUS": {"VALUE": "N"}}},
    ):
        assert ilo.disable_ssh()

    with patch.object(
        ilo,
        "global_settings",
        return_value={"Global Settings": {"SSH_STATUS": {"VALUE": "Y"}}},
    ):
        with patch.object(ilo, "__execute_cmd", return_value={"Disable SSH": {}}):
            assert ilo.disable_ssh() == {"Disable SSH": {}}


# 'set_ssh_port' function tests: 1


def test_set_ssh_port():
    """
    Test if it enable SSH on a user defined port
    """
    with patch.object(
        ilo,
        "global_settings",
        return_value={"Global Settings": {"SSH_PORT": {"VALUE": 22}}},
    ):
        assert ilo.set_ssh_port()

    with patch.object(
        ilo,
        "global_settings",
        return_value={"Global Settings": {"SSH_PORT": {"VALUE": 20}}},
    ):
        with patch.object(
            ilo, "__execute_cmd", return_value={"Configure SSH Port": {}}
        ):
            assert ilo.set_ssh_port() == {"Configure SSH Port": {}}


# 'set_ssh_key' function tests: 1


def test_set_ssh_key():
    """
    Test if it configure SSH public keys for specific users
    """
    with patch(
        "salt.modules.ilo.__execute_cmd",
        MagicMock(return_value={"Import SSH Publickey": {}}),
    ):
        assert ilo.set_ssh_key("ssh-rsa AAAAB3Nza Salt") == {"Import SSH Publickey": {}}


# 'delete_ssh_key' function tests: 1


def test_delete_ssh_key():
    """
    Test if it delete a users SSH key from the ILO
    """
    with patch(
        "salt.modules.ilo.__execute_cmd",
        MagicMock(return_value={"Delete user SSH key": {}}),
    ):
        assert ilo.delete_ssh_key("Salt") == {"Delete user SSH key": {}}


# 'list_users' function tests: 1


def test_list_users():
    """
    Test if it list all users
    """
    with patch(
        "salt.modules.ilo.__execute_cmd", MagicMock(return_value={"All users": {}})
    ):
        assert ilo.list_users() == {"All users": {}}


# 'list_users_info' function tests: 1


def test_list_users_info():
    """
    Test if it List all users in detail
    """
    with patch(
        "salt.modules.ilo.__execute_cmd",
        MagicMock(return_value={"All users info": {}}),
    ):
        assert ilo.list_users_info() == {"All users info": {}}


# 'create_user' function tests: 1


def test_create_user():
    """
    Test if it create user
    """
    with patch(
        "salt.modules.ilo.__execute_cmd",
        MagicMock(return_value={"Create user": {}}),
    ):
        assert ilo.create_user("Salt", "secretagent", "VIRTUAL_MEDIA_PRIV") == {
            "Create user": {}
        }


# 'delete_user' function tests: 1


def test_delete_user():
    """
    Test if it delete a user
    """
    with patch(
        "salt.modules.ilo.__execute_cmd",
        MagicMock(return_value={"Delete user": {}}),
    ):
        assert ilo.delete_user("Salt") == {"Delete user": {}}


# 'get_user' function tests: 1


def test_get_user():
    """
    Test if it returns local user information, excluding the password
    """
    with patch(
        "salt.modules.ilo.__execute_cmd", MagicMock(return_value={"User Info": {}})
    ):
        assert ilo.get_user("Salt") == {"User Info": {}}


# 'change_username' function tests: 1


def test_change_username():
    """
    Test if it change a username
    """
    with patch(
        "salt.modules.ilo.__execute_cmd",
        MagicMock(return_value={"Change username": {}}),
    ):
        assert ilo.change_username("Salt", "SALT") == {"Change username": {}}


# 'change_password' function tests: 1


def test_change_password():
    """
    Test if it reset a users password
    """
    with patch(
        "salt.modules.ilo.__execute_cmd",
        MagicMock(return_value={"Change password": {}}),
    ):
        assert ilo.change_password("Salt", "saltpasswd") == {"Change password": {}}


# 'network' function tests: 1


def test_network():
    """
    Test if it grab the current network settings
    """
    with patch(
        "salt.modules.ilo.__execute_cmd",
        MagicMock(return_value={"Network Settings": {}}),
    ):
        assert ilo.network() == {"Network Settings": {}}


# 'configure_network' function tests: 1


def test_configure_network():
    """
    Test if it configure Network Interface
    """
    with patch(
        "salt.modules.ilo.__execute_cmd",
        MagicMock(return_value={"Configure_Network": {}}),
    ):
        ret = {
            "Network Settings": {
                "IP_ADDRESS": {"VALUE": "10.0.0.10"},
                "SUBNET_MASK": {"VALUE": "255.255.255.0"},
                "GATEWAY_IP_ADDRESS": {"VALUE": "10.0.0.1"},
            }
        }
        with patch.object(ilo, "network", return_value=ret):
            assert ilo.configure_network("10.0.0.10", "255.255.255.0", "10.0.0.1")

        with patch.object(ilo, "network", return_value=ret):
            with patch.object(
                ilo, "__execute_cmd", return_value={"Network Settings": {}}
            ):
                assert ilo.configure_network(
                    "10.0.0.100", "255.255.255.10", "10.0.0.10"
                ) == {"Network Settings": {}}


# 'enable_dhcp' function tests: 1


def test_enable_dhcp():
    """
    Test if it enable DHCP
    """
    with patch.object(
        ilo,
        "network",
        return_value={"Network Settings": {"DHCP_ENABLE": {"VALUE": "Y"}}},
    ):
        assert ilo.enable_dhcp()

    with patch.object(
        ilo,
        "network",
        return_value={"Network Settings": {"DHCP_ENABLE": {"VALUE": "N"}}},
    ):
        with patch.object(ilo, "__execute_cmd", return_value={"Enable DHCP": {}}):
            assert ilo.enable_dhcp() == {"Enable DHCP": {}}


# 'disable_dhcp' function tests: 1


def test_disable_dhcp():
    """
    Test if it disable DHCP
    """
    with patch.object(
        ilo,
        "network",
        return_value={"Network Settings": {"DHCP_ENABLE": {"VALUE": "N"}}},
    ):
        assert ilo.disable_dhcp()

    with patch.object(
        ilo,
        "network",
        return_value={"Network Settings": {"DHCP_ENABLE": {"VALUE": "Y"}}},
    ):
        with patch.object(ilo, "__execute_cmd", return_value={"Disable DHCP": {}}):
            assert ilo.disable_dhcp() == {"Disable DHCP": {}}


# 'configure_snmp' function tests: 1


def test_configure_snmp():
    """
    Test if it configure SNMP
    """
    with patch(
        "salt.modules.ilo.__execute_cmd",
        MagicMock(return_value={"Configure SNMP": {}}),
    ):
        assert ilo.configure_snmp("Salt") == {"Configure SNMP": {}}
