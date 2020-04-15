# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.openstack_config as openstack_config
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class OpenstackConfigTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.openstack_config
    """

    def setup_loader_modules(self):
        patcher = patch("salt.utils.path.which", MagicMock(return_value=True))
        patcher.start()
        self.addCleanup(patcher.stop)
        return {openstack_config: {}}

    # 'set_' function tests: 1

    def test_set(self):
        """
        Test if it set a value in an OpenStack configuration file.
        """
        mock = MagicMock(
            return_value={"retcode": 0, "stderr": "error", "stdout": "salt"}
        )
        with patch.dict(openstack_config.__salt__, {"cmd.run_all": mock}):
            self.assertEqual(
                openstack_config.set_(
                    "/etc/keystone/keys.conf", "sql", "connection", "foo"
                ),
                "salt",
            )

        mock = MagicMock(
            return_value={"retcode": 1, "stderr": "error", "stdout": "salt"}
        )
        with patch.dict(openstack_config.__salt__, {"cmd.run_all": mock}):
            self.assertRaises(
                CommandExecutionError,
                openstack_config.set_,
                "/etc/keystone/keystone.conf",
                "sql",
                "connection",
                "foo",
            )

    # 'get' function tests: 1

    def test_get(self):
        """
        Test if it get a value from an OpenStack configuration file.
        """
        mock = MagicMock(
            return_value={"retcode": 0, "stderr": "error", "stdout": "salt"}
        )
        with patch.dict(openstack_config.__salt__, {"cmd.run_all": mock}):
            self.assertEqual(
                openstack_config.get("/etc/keystone/keys.conf", "sql", "connection"),
                "salt",
            )

        mock = MagicMock(
            return_value={"retcode": 1, "stderr": "error", "stdout": "salt"}
        )
        with patch.dict(openstack_config.__salt__, {"cmd.run_all": mock}):
            self.assertRaises(
                CommandExecutionError,
                openstack_config.get,
                "/etc/key/keystone.conf",
                "sql",
                "connection",
            )

    # 'delete' function tests: 1

    def test_delete(self):
        """
        Test if it delete a value from an OpenStack configuration file.
        """
        mock = MagicMock(
            return_value={"retcode": 0, "stderr": "error", "stdout": "salt"}
        )
        with patch.dict(openstack_config.__salt__, {"cmd.run_all": mock}):
            self.assertEqual(
                openstack_config.delete("/etc/keystone/keys.conf", "sql", "connection"),
                "salt",
            )

        mock = MagicMock(
            return_value={"retcode": 1, "stderr": "error", "stdout": "salt"}
        )
        with patch.dict(openstack_config.__salt__, {"cmd.run_all": mock}):
            self.assertRaises(
                CommandExecutionError,
                openstack_config.delete,
                "/etc/key/keystone.conf",
                "sql",
                "connection",
            )
