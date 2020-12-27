# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.power_dns as power_dns
from salt.exceptions import CommandExecutionError, SaltInvocationError
# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class PowerDnsTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.power_dns
    """

    def setup_loader_modules(self):
        return {power_dns: {}}

    def test_manage_zone_path_empty_key(self):
        self.assertRaises(SaltInvocationError, power_dns.manage_zone, "test_domain", "", "server")

    def test_manage_zone_path_empty_server(self):
        self.assertRaises(SaltInvocationError, power_dns.manage_zone, "test_domain", "key", "")

    def test_manage_zone_path_empty_name(self):
        ret = {
            "name": "",
            "changes": {},
            "result": False,
            "comment": "No name of zone provided",
        }
        self.assertEqual(power_dns.manage_zone(""), ret)

    def test_manage_zone_path_empty_name(self):
        ret = {
            "name": "",
            "changes": {},
            "result": False,
            "comment": "No name of zone provided",
        }
        self.assertEqual(power_dns.manage_zone("", "key", "server"), ret)

    def test_manage_zone_was_updated(self):
        result_changes = {"changes": "Zone was updated"}
        mock_power_dns_modules = {"power_dns.manage_zone": MagicMock(return_value=result_changes)}
        with patch.dict(power_dns.__salt__, mock_power_dns_modules):
            ret = {
                "name": "zone",
                "changes": "Zone was updated",
                "result": True,
                "comment": "",
            }
            self.assertEqual(power_dns.manage_zone("zone", "key", "server"), ret)

    def test_manage_zone_failed(self):
        mock_power_dns_modules = {"power_dns.manage_zone": MagicMock(side_effect=[CommandExecutionError])}
        with patch.dict(power_dns.__salt__, mock_power_dns_modules):
            self.assertRaises(CommandExecutionError, power_dns.manage_zone, "test_domain", "key", "server")

    def test_delete_zone_path_empty_key(self):
        self.assertRaises(SaltInvocationError, power_dns.delete_zone, "test_domain", "", "server")

    def test_delete_zone_path_empty_server(self):
        self.assertRaises(SaltInvocationError, power_dns.delete_zone, "test_domain", "key", "")

    def test_delete_zone_path_empty_name(self):
        ret = {
            "name": "",
            "changes": {},
            "result": False,
            "comment": "No name of zone provided",
        }
        self.assertEqual(power_dns.delete_zone(""), ret)

    def test_delete_zone_path_empty_name(self):
        ret = {
            "name": "",
            "changes": {},
            "result": False,
            "comment": "No name of zone provided",
        }
        self.assertEqual(power_dns.delete_zone("", "key", "server"), ret)

    def test_delete_zone_deleted(self):
        result_changes = {"changes": "Zone was deleted"}
        mock_power_dns_modules = {"power_dns.delete_zone": MagicMock(return_value=result_changes)}
        with patch.dict(power_dns.__salt__, mock_power_dns_modules):
            ret = {
                "name": "zone",
                "changes": "Zone was deleted",
                "result": True,
                "comment": "",
            }
            self.assertEqual(power_dns.delete_zone("zone", "key", "server"), ret)

    def test_delete_zone_failed(self):
        mock_power_dns_modules = {"power_dns.delete_zone": MagicMock(side_effect=[CommandExecutionError])}
        with patch.dict(power_dns.__salt__, mock_power_dns_modules):
            self.assertRaises(CommandExecutionError, power_dns.delete_zone, "test_domain", "key", "server")
