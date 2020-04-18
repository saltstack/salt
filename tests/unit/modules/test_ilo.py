# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import tempfile

import salt.modules.file

# Import Salt Libs
import salt.modules.ilo as ilo

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class IloTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.ilo
    """

    def setup_loader_modules(self):
        return {
            ilo: {
                "__opts__": {"cachedir": tempfile.gettempdir()},
                "__salt__": {"file.remove": salt.modules.file.remove},
            }
        }

    # '__execute_cmd' function tests: 1

    def test_execute_cmd(self):
        """
        Test if __execute_command opens the temporary file
        properly when calling global_settings.
        """
        mock_cmd_run = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(ilo.__salt__, {"cmd.run_all": mock_cmd_run}):
            ret = ilo.global_settings()
            self.assertEqual(ret, True)

    # 'global_settings' function tests: 1

    def test_global_settings(self):
        """
        Test if it shows global_settings
        """
        with patch(
            "salt.modules.ilo.__execute_cmd",
            MagicMock(return_value={"Global Settings": {}}),
        ):
            self.assertDictEqual(ilo.global_settings(), {"Global Settings": {}})

    # 'set_http_port' function tests: 1

    def test_set_http_port(self):
        """
        Test if it configure the port HTTP should listen on
        """
        with patch.object(
            ilo,
            "global_settings",
            return_value={"Global Settings": {"HTTP_PORT": {"VALUE": 80}}},
        ):
            self.assertTrue(ilo.set_http_port())

        with patch.object(
            ilo,
            "global_settings",
            return_value={"Global Settings": {"HTTP_PORT": {"VALUE": 40}}},
        ):
            with patch.object(ilo, "__execute_cmd", return_value={"Set HTTP Port": {}}):
                self.assertDictEqual(ilo.set_http_port(), {"Set HTTP Port": {}})

    # 'set_https_port' function tests: 1

    def test_set_https_port(self):
        """
        Test if it configure the port HTTPS should listen on
        """
        with patch.object(
            ilo,
            "global_settings",
            return_value={"Global Settings": {"HTTP_PORT": {"VALUE": 443}}},
        ):
            self.assertTrue(ilo.set_https_port())

        with patch.object(
            ilo,
            "global_settings",
            return_value={"Global Settings": {"HTTP_PORT": {"VALUE": 80}}},
        ):
            with patch.object(
                ilo, "__execute_cmd", return_value={"Set HTTPS Port": {}}
            ):
                self.assertDictEqual(ilo.set_https_port(), {"Set HTTPS Port": {}})

    # 'enable_ssh' function tests: 1

    def test_enable_ssh(self):
        """
        Test if it enable the SSH daemon
        """
        with patch.object(
            ilo,
            "global_settings",
            return_value={"Global Settings": {"SSH_STATUS": {"VALUE": "Y"}}},
        ):
            self.assertTrue(ilo.enable_ssh())

        with patch.object(
            ilo,
            "global_settings",
            return_value={"Global Settings": {"SSH_STATUS": {"VALUE": "N"}}},
        ):
            with patch.object(ilo, "__execute_cmd", return_value={"Enable SSH": {}}):
                self.assertDictEqual(ilo.enable_ssh(), {"Enable SSH": {}})

    # 'disable_ssh' function tests: 1

    def test_disable_ssh(self):
        """
        Test if it disable the SSH daemon
        """
        with patch.object(
            ilo,
            "global_settings",
            return_value={"Global Settings": {"SSH_STATUS": {"VALUE": "N"}}},
        ):
            self.assertTrue(ilo.disable_ssh())

        with patch.object(
            ilo,
            "global_settings",
            return_value={"Global Settings": {"SSH_STATUS": {"VALUE": "Y"}}},
        ):
            with patch.object(ilo, "__execute_cmd", return_value={"Disable SSH": {}}):
                self.assertDictEqual(ilo.disable_ssh(), {"Disable SSH": {}})

    # 'set_ssh_port' function tests: 1

    def test_set_ssh_port(self):
        """
        Test if it enable SSH on a user defined port
        """
        with patch.object(
            ilo,
            "global_settings",
            return_value={"Global Settings": {"SSH_PORT": {"VALUE": 22}}},
        ):
            self.assertTrue(ilo.set_ssh_port())

        with patch.object(
            ilo,
            "global_settings",
            return_value={"Global Settings": {"SSH_PORT": {"VALUE": 20}}},
        ):
            with patch.object(
                ilo, "__execute_cmd", return_value={"Configure SSH Port": {}}
            ):
                self.assertDictEqual(ilo.set_ssh_port(), {"Configure SSH Port": {}})

    # 'set_ssh_key' function tests: 1

    def test_set_ssh_key(self):
        """
        Test if it configure SSH public keys for specific users
        """
        with patch(
            "salt.modules.ilo.__execute_cmd",
            MagicMock(return_value={"Import SSH Publickey": {}}),
        ):
            self.assertDictEqual(
                ilo.set_ssh_key("ssh-rsa AAAAB3Nza Salt"), {"Import SSH Publickey": {}}
            )

    # 'delete_ssh_key' function tests: 1

    def test_delete_ssh_key(self):
        """
        Test if it delete a users SSH key from the ILO
        """
        with patch(
            "salt.modules.ilo.__execute_cmd",
            MagicMock(return_value={"Delete user SSH key": {}}),
        ):
            self.assertDictEqual(
                ilo.delete_ssh_key("Salt"), {"Delete user SSH key": {}}
            )

    # 'list_users' function tests: 1

    def test_list_users(self):
        """
        Test if it list all users
        """
        with patch(
            "salt.modules.ilo.__execute_cmd", MagicMock(return_value={"All users": {}})
        ):
            self.assertDictEqual(ilo.list_users(), {"All users": {}})

    # 'list_users_info' function tests: 1

    def test_list_users_info(self):
        """
        Test if it List all users in detail
        """
        with patch(
            "salt.modules.ilo.__execute_cmd",
            MagicMock(return_value={"All users info": {}}),
        ):
            self.assertDictEqual(ilo.list_users_info(), {"All users info": {}})

    # 'create_user' function tests: 1

    def test_create_user(self):
        """
        Test if it create user
        """
        with patch(
            "salt.modules.ilo.__execute_cmd",
            MagicMock(return_value={"Create user": {}}),
        ):
            self.assertDictEqual(
                ilo.create_user("Salt", "secretagent", "VIRTUAL_MEDIA_PRIV"),
                {"Create user": {}},
            )

    # 'delete_user' function tests: 1

    def test_delete_user(self):
        """
        Test if it delete a user
        """
        with patch(
            "salt.modules.ilo.__execute_cmd",
            MagicMock(return_value={"Delete user": {}}),
        ):
            self.assertDictEqual(ilo.delete_user("Salt"), {"Delete user": {}})

    # 'get_user' function tests: 1

    def test_get_user(self):
        """
        Test if it returns local user information, excluding the password
        """
        with patch(
            "salt.modules.ilo.__execute_cmd", MagicMock(return_value={"User Info": {}})
        ):
            self.assertDictEqual(ilo.get_user("Salt"), {"User Info": {}})

    # 'change_username' function tests: 1

    def test_change_username(self):
        """
        Test if it change a username
        """
        with patch(
            "salt.modules.ilo.__execute_cmd",
            MagicMock(return_value={"Change username": {}}),
        ):
            self.assertDictEqual(
                ilo.change_username("Salt", "SALT"), {"Change username": {}}
            )

    # 'change_password' function tests: 1

    def test_change_password(self):
        """
        Test if it reset a users password
        """
        with patch(
            "salt.modules.ilo.__execute_cmd",
            MagicMock(return_value={"Change password": {}}),
        ):
            self.assertDictEqual(
                ilo.change_password("Salt", "saltpasswd"), {"Change password": {}}
            )

    # 'network' function tests: 1

    def test_network(self):
        """
        Test if it grab the current network settings
        """
        with patch(
            "salt.modules.ilo.__execute_cmd",
            MagicMock(return_value={"Network Settings": {}}),
        ):
            self.assertDictEqual(ilo.network(), {"Network Settings": {}})

    # 'configure_network' function tests: 1

    def test_configure_network(self):
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
                self.assertTrue(
                    ilo.configure_network("10.0.0.10", "255.255.255.0", "10.0.0.1")
                )

            with patch.object(ilo, "network", return_value=ret):
                with patch.object(
                    ilo, "__execute_cmd", return_value={"Network Settings": {}}
                ):
                    self.assertDictEqual(
                        ilo.configure_network(
                            "10.0.0.100", "255.255.255.10", "10.0.0.10"
                        ),
                        {"Network Settings": {}},
                    )

    # 'enable_dhcp' function tests: 1

    def test_enable_dhcp(self):
        """
        Test if it enable DHCP
        """
        with patch.object(
            ilo,
            "network",
            return_value={"Network Settings": {"DHCP_ENABLE": {"VALUE": "Y"}}},
        ):
            self.assertTrue(ilo.enable_dhcp())

        with patch.object(
            ilo,
            "network",
            return_value={"Network Settings": {"DHCP_ENABLE": {"VALUE": "N"}}},
        ):
            with patch.object(ilo, "__execute_cmd", return_value={"Enable DHCP": {}}):
                self.assertDictEqual(ilo.enable_dhcp(), {"Enable DHCP": {}})

    # 'disable_dhcp' function tests: 1

    def test_disable_dhcp(self):
        """
        Test if it disable DHCP
        """
        with patch.object(
            ilo,
            "network",
            return_value={"Network Settings": {"DHCP_ENABLE": {"VALUE": "N"}}},
        ):
            self.assertTrue(ilo.disable_dhcp())

        with patch.object(
            ilo,
            "network",
            return_value={"Network Settings": {"DHCP_ENABLE": {"VALUE": "Y"}}},
        ):
            with patch.object(ilo, "__execute_cmd", return_value={"Disable DHCP": {}}):
                self.assertDictEqual(ilo.disable_dhcp(), {"Disable DHCP": {}})

    # 'configure_snmp' function tests: 1

    def test_configure_snmp(self):
        """
        Test if it configure SNMP
        """
        with patch(
            "salt.modules.ilo.__execute_cmd",
            MagicMock(return_value={"Configure SNMP": {}}),
        ):
            self.assertDictEqual(ilo.configure_snmp("Salt"), {"Configure SNMP": {}})
