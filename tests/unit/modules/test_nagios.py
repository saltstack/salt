"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

import os

import salt.modules.nagios as nagios
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class NagiosTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.nagios
    """

    def setup_loader_modules(self):
        return {nagios: {}}

    def test_run(self):
        """
        Test for Run nagios plugin and return all
         the data execution with cmd.run
        """
        with patch.object(nagios, "_execute_cmd", return_value="A"):
            self.assertEqual(nagios.run("plugin"), "A")

    def test_retcode(self):
        """
        Test for Run one nagios plugin and return retcode of the execution
        """
        with patch.object(nagios, "_execute_cmd", return_value="A"):
            self.assertEqual(
                nagios.retcode("plugin", key_name="key"), {"key": {"status": "A"}}
            )

    def test_run_all(self):
        """
        Test for Run nagios plugin and return all
         the data execution with cmd.run_all
        """
        with patch.object(nagios, "_execute_cmd", return_value="A"):
            self.assertEqual(nagios.run_all("plugin"), "A")

    def test_retcode_pillar(self):
        """
        Test for Run one or more nagios plugins from pillar data and
         get the result of cmd.retcode
        """
        with patch.dict(nagios.__salt__, {"pillar.get": MagicMock(return_value={})}):
            self.assertEqual(nagios.retcode_pillar("pillar_name"), {})

    def test_run_pillar(self):
        """
        Test for Run one or more nagios plugins from pillar data
         and get the result of cmd.run
        """
        with patch.object(nagios, "_execute_pillar", return_value="A"):
            self.assertEqual(nagios.run_pillar("pillar"), "A")

    def test_run_all_pillar(self):
        """
        Test for Run one or more nagios plugins from pillar data
         and get the result of cmd.run
        """
        with patch.object(nagios, "_execute_pillar", return_value="A"):
            self.assertEqual(nagios.run_all_pillar("pillar"), "A")

    def test_list_plugins(self):
        """
        Test for List all the nagios plugins
        """
        with patch.object(os, "listdir", return_value=[]):
            self.assertEqual(nagios.list_plugins(), [])
