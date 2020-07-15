# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.openstack_config as openstack_config
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class OpenstackConfigTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.openstack_config
    """

    def setup_loader_modules(self):
        return {openstack_config: {"__opts__": {"test": False}}}

    # 'present' function tests: 1

    def test_present(self):
        """
        Test to ensure a value is set in an OpenStack configuration file.
        """
        name = "salt"
        filename = "/tmp/salt"
        section = "A"
        value = "SALT"

        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        mock_lst = MagicMock(side_effect=[value, CommandExecutionError, "A"])
        mock_t = MagicMock(return_value=True)
        with patch.dict(
            openstack_config.__salt__,
            {"openstack_config.get": mock_lst, "openstack_config.set": mock_t},
        ):
            comt = "The value is already set to the correct value"
            ret.update({"comment": comt, "result": True})
            self.assertDictEqual(
                openstack_config.present(name, filename, section, value), ret
            )

            self.assertRaises(
                CommandExecutionError,
                openstack_config.present,
                name,
                filename,
                section,
                value,
            )

            comt = "The value has been updated"
            ret.update({"comment": comt, "changes": {"Value": "Updated"}})
            self.assertDictEqual(
                openstack_config.present(name, filename, section, value), ret
            )

    # 'absent' function tests: 1

    def test_absent(self):
        """
        Test to ensure a value is not set in an OpenStack configuration file.
        """
        name = "salt"
        filename = "/tmp/salt"
        section = "A"

        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        mock_lst = MagicMock(
            side_effect=[
                CommandExecutionError("parameter not found:"),
                CommandExecutionError,
                "A",
            ]
        )
        mock_t = MagicMock(return_value=True)
        with patch.dict(
            openstack_config.__salt__,
            {"openstack_config.get": mock_lst, "openstack_config.delete": mock_t},
        ):
            comt = "The value is already absent"
            ret.update({"comment": comt, "result": True})
            self.assertDictEqual(openstack_config.absent(name, filename, section), ret)

            self.assertRaises(
                CommandExecutionError, openstack_config.absent, name, filename, section
            )

            comt = "The value has been deleted"
            ret.update({"comment": comt, "changes": {"Value": "Deleted"}})
            self.assertDictEqual(openstack_config.absent(name, filename, section), ret)
