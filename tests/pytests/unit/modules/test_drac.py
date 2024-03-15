"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

import pytest

import salt.modules.drac as drac
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {drac: {}}


def test_system_info():
    """
    Tests to return System information
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": None})
    with patch.dict(drac.__salt__, {"cmd.run_all": mock}):
        mock = MagicMock(return_value="ABC")
        with patch.object(drac, "__parse_drac", mock):
            assert drac.system_info() == "ABC"


def test_network_info():
    """
    Tests to return Network Configuration
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": None})
    with patch.dict(drac.__salt__, {"cmd.run_all": mock}):
        mock = MagicMock(return_value="ABC")
        with patch.object(drac, "__parse_drac", mock):
            assert drac.network_info() == "ABC"


def test_nameservers():
    """
    tests for configure the nameservers on the DRAC
    """
    assert not drac.nameservers("a", "b", "c")

    mock = MagicMock(return_value=False)
    with patch.object(drac, "__execute_cmd", mock):
        assert not drac.nameservers("a")

    mock = MagicMock(return_value=True)
    with patch.object(drac, "__execute_cmd", mock):
        assert drac.nameservers("a")


def test_syslog():
    """
    Tests for configure syslog remote logging, by default syslog will
    automatically be enabled if a server is specified. However,
    if you want to disable syslog you will need to specify a server
    followed by False
    """
    mock = MagicMock(return_value=True)
    with patch.object(drac, "__execute_cmd", mock):
        assert drac.syslog("server")

    mock = MagicMock(return_value=True)
    with patch.object(drac, "__execute_cmd", mock):
        assert drac.syslog("server", False)


def test_email_alerts():
    """
    Test to Enable/Disable email alerts
    """
    mock = MagicMock(return_value=True)
    with patch.object(drac, "__execute_cmd", mock):
        assert drac.email_alerts(True)

    mock = MagicMock(return_value=True)
    with patch.object(drac, "__execute_cmd", mock):
        assert drac.email_alerts(False)


def test_list_users():
    """
    Test for list all DRAC users
    """
    mock = MagicMock(
        return_value={"retcode": 0, "stdout": "cfgUserAdminUserName=value"}
    )
    with patch.dict(drac.__salt__, {"cmd.run_all": mock}):
        assert drac.list_users() == {"value": {"index": 16}}


def test_delete_user():
    """
    Tests to delete a user
    """
    mock = MagicMock(return_value="ABC")
    with patch.object(drac, "__execute_cmd", mock):
        assert drac.delete_user("username", 1) == "ABC"

    assert not drac.delete_user("username", False)


def test_change_password():
    """
    Tests to change users password
    """
    mock = MagicMock(return_value="ABC")
    with patch.object(drac, "__execute_cmd", mock):
        assert drac.change_password("username", "password", 1) == "ABC"

    assert not drac.change_password("username", "password", False), False


def test_create_user():
    """
    Tests to create user accounts
    """
    assert not drac.create_user(
        "username", "password", "permissions", {"username": None}
    )

    mock = MagicMock(return_value=False)
    with patch.object(drac, "__execute_cmd", mock):
        mock = MagicMock(return_value=None)
        with patch.object(drac, "delete_user", mock):
            assert not drac.create_user(
                "username",
                "password",
                "permissions",
                {"username1": {"index": 1}},
            )

    mock = MagicMock(return_value=True)
    with patch.object(drac, "__execute_cmd", mock):
        mock = MagicMock(return_value=False)
        with patch.object(drac, "set_permissions", mock):
            mock = MagicMock(return_value=None)
            with patch.object(drac, "delete_user", mock):
                assert not drac.create_user(
                    "username",
                    "password",
                    "permissions",
                    {"username1": {"index": 1}},
                )

        mock = MagicMock(return_value=True)
        with patch.object(drac, "set_permissions", mock):
            mock = MagicMock(return_value=False)
            with patch.object(drac, "change_password", mock):
                mock = MagicMock(return_value=None)
                with patch.object(drac, "delete_user", mock):
                    assert not drac.create_user(
                        "username",
                        "password",
                        "permissions",
                        {"username1": {"index": 1}},
                    )

    mock = MagicMock(side_effect=[True, False])
    with patch.object(drac, "__execute_cmd", mock):
        mock = MagicMock(return_value=True)
        with patch.object(drac, "set_permissions", mock):
            mock = MagicMock(return_value=True)
            with patch.object(drac, "change_password", mock):
                mock = MagicMock(return_value=None)
                with patch.object(drac, "delete_user", mock):
                    assert not drac.create_user(
                        "username",
                        "password",
                        "permissions",
                        {"username1": {"index": 1}},
                    )

    mock = MagicMock(side_effect=[True, True])
    with patch.object(drac, "__execute_cmd", mock):
        mock = MagicMock(return_value=True)
        with patch.object(drac, "set_permissions", mock):
            mock = MagicMock(return_value=True)
            with patch.object(drac, "change_password", mock):
                mock = MagicMock(return_value=None)
                with patch.object(drac, "delete_user", mock):
                    assert drac.create_user(
                        "username",
                        "password",
                        "permissions",
                        {"username1": {"index": 1}},
                    )


def test_set_permissions():
    """
    Test to configure users permissions
    """
    mock = MagicMock(return_value=True)
    with patch.object(drac, "__execute_cmd", mock):
        assert drac.set_permissions("username", "A,B,C", 1)


def test_set_snmp():
    """
    Test to configure SNMP community string
    """
    mock = MagicMock(return_value=True)
    with patch.object(drac, "__execute_cmd", mock):
        assert drac.set_snmp("username")


def test_set_network():
    """
    Test to configure Network
    """
    mock = MagicMock(return_value=True)
    with patch.object(drac, "__execute_cmd", mock):
        assert drac.set_network("ip", "netmask", "gateway")


def test_server_reboot():
    """
    Tests for issues a power-cycle operation on the managed server.
    This action is similar to pressing the power button on the system's
    front panel to power down and then power up the system.
    """
    mock = MagicMock(return_value=True)
    with patch.object(drac, "__execute_cmd", mock):
        assert drac.server_reboot()


def test_server_poweroff():
    """
    Tests for powers down the managed server.
    """
    mock = MagicMock(return_value=True)
    with patch.object(drac, "__execute_cmd", mock):
        assert drac.server_poweroff()


def test_server_poweron():
    """
    Tests for powers up the managed server.
    """
    mock = MagicMock(return_value=True)
    with patch.object(drac, "__execute_cmd", mock):
        assert drac.server_poweron()


def test_server_hardreset():
    """
    Tests for performs a reset (reboot) operation on the managed server.
    """
    mock = MagicMock(return_value=True)
    with patch.object(drac, "__execute_cmd", mock):
        assert drac.server_hardreset()


def test_server_pxe():
    """
    Tests to configure server to PXE perform a one off PXE boot
    """
    mock = MagicMock(return_value=True)
    with patch.object(drac, "__execute_cmd", mock):
        assert drac.server_pxe()

    mock = MagicMock(side_effect=[True, False])
    with patch.object(drac, "__execute_cmd", mock):
        assert not drac.server_pxe()

    mock = MagicMock(return_value=False)
    with patch.object(drac, "__execute_cmd", mock):
        assert not drac.server_pxe()
