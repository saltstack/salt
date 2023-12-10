"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
    :codeauthor: Alexandru Bleotu <alexandru.bleotu@morganstanley.com>

    Tests for functions in salt.modules.vsphere
"""
import pytest

import salt.modules.vsphere as vsphere
import salt.utils.args
import salt.utils.vmware
from salt.exceptions import (
    ArgumentValueError,
    CommandExecutionError,
    VMwareObjectRetrievalError,
    VMwareSaltError,
)
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, Mock, call, patch
from tests.support.unit import TestCase

try:
    from pyVmomi import vim, vmodl  # pylint: disable=unused-import,no-name-in-module

    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

try:
    from com.vmware.vapi.std_client import DynamicID  # pylint: disable=unused-import

    HAS_VSPHERE_SDK = True
except ImportError:
    HAS_VSPHERE_SDK = False


# Globals
HOST = "1.2.3.4"
USER = "root"
PASSWORD = "SuperSecret!"
ERROR = "Some Testing Error Message"


class VsphereTestCase(TestCase, LoaderModuleMockMixin):
    """
    Unit TestCase for the salt.modules.vsphere module.
    """

    def setup_loader_modules(self):
        return {vsphere: {}}

    # Tests for get_coredump_network_config function

    def test_get_coredump_network_config_esxi_hosts_not_list(self):
        """
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list.
        """
        self.assertRaises(
            CommandExecutionError,
            vsphere.get_coredump_network_config,
            HOST,
            USER,
            PASSWORD,
            esxi_hosts="foo",
        )

    def test_get_coredump_network_config_host_list_bad_retcode(self):
        """
        Tests error message returned with list of esxi_hosts.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 1, "stdout": ERROR}),
        ):
            host_1 = "host_1.foo.com"
            self.assertEqual(
                {host_1: {"Error": ERROR}},
                vsphere.get_coredump_network_config(
                    HOST, USER, PASSWORD, esxi_hosts=[host_1]
                ),
            )

    def test_get_coredump_network_config_host_list_success(self):
        """
        Tests successful function return when an esxi_host is provided.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 0, "stdout": ""}),
        ):
            with patch(
                "salt.modules.vsphere._format_coredump_stdout",
                MagicMock(return_value={}),
            ):
                host_1 = "host_1.foo.com"
                self.assertEqual(
                    {host_1: {"Coredump Config": {}}},
                    vsphere.get_coredump_network_config(
                        HOST, USER, PASSWORD, esxi_hosts=[host_1]
                    ),
                )

    def test_get_coredump_network_config_bad_retcode(self):
        """
        Tests error message given for a single ESXi host.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 1, "stdout": ERROR}),
        ):
            self.assertEqual(
                {HOST: {"Error": ERROR}},
                vsphere.get_coredump_network_config(HOST, USER, PASSWORD),
            )

    def test_get_coredump_network_config_success(self):
        """
        Tests successful function return for a single ESXi host.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 0, "stdout": ""}),
        ):
            with patch(
                "salt.modules.vsphere._format_coredump_stdout",
                MagicMock(return_value={}),
            ):
                self.assertEqual(
                    {HOST: {"Coredump Config": {}}},
                    vsphere.get_coredump_network_config(HOST, USER, PASSWORD),
                )

    # Tests for coredump_network_enable function

    def test_coredump_network_enable_esxi_hosts_not_list(self):
        """
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list.
        """
        self.assertRaises(
            CommandExecutionError,
            vsphere.coredump_network_enable,
            HOST,
            USER,
            PASSWORD,
            True,
            esxi_hosts="foo",
        )

    def test_coredump_network_enable_host_list_bad_retcode(self):
        """
        Tests error message returned with list of esxi_hosts.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 1, "stdout": ERROR}),
        ):
            host_1 = "host_1.foo.com"
            self.assertEqual(
                {host_1: {"Error": ERROR}},
                vsphere.coredump_network_enable(
                    HOST, USER, PASSWORD, True, esxi_hosts=[host_1]
                ),
            )

    def test_coredump_network_enable_host_list_success(self):
        """
        Tests successful function return when an esxi_host is provided.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 0, "stdout": ""}),
        ):
            with patch(
                "salt.modules.vsphere._format_coredump_stdout",
                MagicMock(return_value={}),
            ):
                enabled = True
                host_1 = "host_1.foo.com"
                self.assertEqual(
                    {host_1: {"Coredump Enabled": enabled}},
                    vsphere.coredump_network_enable(
                        HOST, USER, PASSWORD, enabled, esxi_hosts=[host_1]
                    ),
                )

    def test_coredump_network_enable_bad_retcode(self):
        """
        Tests error message given for a single ESXi host.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 1, "stdout": ERROR}),
        ):
            self.assertEqual(
                {HOST: {"Error": ERROR}},
                vsphere.coredump_network_enable(HOST, USER, PASSWORD, True),
            )

    def test_coredump_network_enable_success(self):
        """
        Tests successful function return for a single ESXi host.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 0, "stdout": ""}),
        ):
            with patch(
                "salt.modules.vsphere._format_coredump_stdout",
                MagicMock(return_value={}),
            ):
                enabled = True
                self.assertEqual(
                    {HOST: {"Coredump Enabled": enabled}},
                    vsphere.coredump_network_enable(HOST, USER, PASSWORD, enabled),
                )

    # Tests for set_coredump_network_config function

    def test_set_coredump_network_config_esxi_hosts_not_list(self):
        """
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list.
        """
        self.assertRaises(
            CommandExecutionError,
            vsphere.set_coredump_network_config,
            HOST,
            USER,
            PASSWORD,
            "loghost",
            "foo",
            esxi_hosts="bar",
        )

    def test_set_coredump_network_config_host_list_bad_retcode(self):
        """
        Tests error message returned with list of esxi_hosts.
        """
        with patch("salt.utils.vmware.esxcli", MagicMock(return_value={"retcode": 1})):
            host_1 = "host_1.foo.com"
            self.assertEqual(
                {host_1: {"retcode": 1, "success": False}},
                vsphere.set_coredump_network_config(
                    HOST, USER, PASSWORD, "dump-ip.test.com", esxi_hosts=[host_1]
                ),
            )

    def test_set_coredump_network_config_host_list_success(self):
        """
        Tests successful function return when an esxi_host is provided.
        """
        with patch("salt.utils.vmware.esxcli", MagicMock(return_value={"retcode": 0})):
            host_1 = "host_1.foo.com"
            self.assertEqual(
                {host_1: {"retcode": 0, "success": True}},
                vsphere.set_coredump_network_config(
                    HOST, USER, PASSWORD, "dump-ip.test.com", esxi_hosts=[host_1]
                ),
            )

    def test_set_coredump_network_config_bad_retcode(self):
        """
        Tests error message given for a single ESXi host.
        """
        with patch("salt.utils.vmware.esxcli", MagicMock(return_value={"retcode": 1})):
            self.assertEqual(
                {HOST: {"retcode": 1, "success": False}},
                vsphere.set_coredump_network_config(
                    HOST, USER, PASSWORD, "dump-ip.test.com"
                ),
            )

    def test_set_coredump_network_config_success(self):
        """
        Tests successful function return for a single ESXi host.
        """
        with patch("salt.utils.vmware.esxcli", MagicMock(return_value={"retcode": 0})):
            self.assertEqual(
                {HOST: {"retcode": 0, "success": True}},
                vsphere.set_coredump_network_config(
                    HOST, USER, PASSWORD, "dump-ip.test.com"
                ),
            )

    # Tests for get_firewall_status function

    def test_get_firewall_status_esxi_hosts_not_list(self):
        """
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list.
        """
        self.assertRaises(
            CommandExecutionError,
            vsphere.get_firewall_status,
            HOST,
            USER,
            PASSWORD,
            esxi_hosts="foo",
        )

    def test_get_firewall_status_host_list_bad_retcode(self):
        """
        Tests error message returned with list of esxi_hosts.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 1, "stdout": ERROR}),
        ):
            host_1 = "host_1.foo.com"
            self.assertEqual(
                {host_1: {"success": False, "Error": ERROR, "rulesets": None}},
                vsphere.get_firewall_status(HOST, USER, PASSWORD, esxi_hosts=[host_1]),
            )

    def test_get_firewall_status_host_list_success(self):
        """
        Tests successful function return when an esxi_host is provided.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 0, "stdout": ""}),
        ):
            host_1 = "host_1.foo.com"
            self.assertEqual(
                {host_1: {"rulesets": {}, "success": True}},
                vsphere.get_firewall_status(HOST, USER, PASSWORD, esxi_hosts=[host_1]),
            )

    def test_get_firewall_status_bad_retcode(self):
        """
        Tests error message given for a single ESXi host.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 1, "stdout": ERROR}),
        ):
            self.assertEqual(
                {HOST: {"success": False, "Error": ERROR, "rulesets": None}},
                vsphere.get_firewall_status(HOST, USER, PASSWORD),
            )

    def test_get_firewall_status_success(self):
        """
        Tests successful function return for a single ESXi host.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 0, "stdout": ""}),
        ):
            self.assertEqual(
                {HOST: {"rulesets": {}, "success": True}},
                vsphere.get_firewall_status(HOST, USER, PASSWORD),
            )

    # Tests for enable_firewall_ruleset function

    def test_enable_firewall_ruleset_esxi_hosts_not_list(self):
        """
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list.
        """
        self.assertRaises(
            CommandExecutionError,
            vsphere.enable_firewall_ruleset,
            HOST,
            USER,
            PASSWORD,
            "foo",
            "bar",
            esxi_hosts="baz",
        )

    # Tests for syslog_service_reload function

    def test_syslog_service_reload_esxi_hosts_not_list(self):
        """
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list.
        """
        self.assertRaises(
            CommandExecutionError,
            vsphere.syslog_service_reload,
            HOST,
            USER,
            PASSWORD,
            esxi_hosts="foo",
        )

    # Tests for set_syslog_config function.
    # These tests only test the firewall=True and syslog_config == 'loghost' if block.
    # The rest of the function is tested in the _set_syslog_config_helper tests below.

    def test_set_syslog_config_esxi_hosts_not_list(self):
        """
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list, but we don't enter the 'loghost'/firewall loop.
        """
        self.assertRaises(
            CommandExecutionError,
            vsphere.set_syslog_config,
            HOST,
            USER,
            PASSWORD,
            "foo",
            "bar",
            esxi_hosts="baz",
        )

    def test_set_syslog_config_esxi_hosts_not_list_firewall(self):
        """
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list, and we enter the 'loghost'/firewall loop.
        """
        self.assertRaises(
            CommandExecutionError,
            vsphere.set_syslog_config,
            HOST,
            USER,
            PASSWORD,
            "loghost",
            "foo",
            firewall=True,
            esxi_hosts="bar",
        )

    def test_set_syslog_config_host_list_firewall_bad_retcode(self):
        """
        Tests error message returned with list of esxi_hosts with 'loghost' as syslog_config.
        """
        with patch(
            "salt.modules.vsphere.enable_firewall_ruleset",
            MagicMock(return_value={"host_1.foo.com": {"retcode": 1, "stdout": ERROR}}),
        ):
            with patch(
                "salt.modules.vsphere._set_syslog_config_helper",
                MagicMock(return_value={}),
            ):
                host_1 = "host_1.foo.com"
                self.assertEqual(
                    {host_1: {"enable_firewall": {"message": ERROR, "success": False}}},
                    vsphere.set_syslog_config(
                        HOST,
                        USER,
                        PASSWORD,
                        "loghost",
                        "foo",
                        firewall=True,
                        esxi_hosts=[host_1],
                    ),
                )

    def test_set_syslog_config_host_list_firewall_success(self):
        """
        Tests successful function return with list of esxi_hosts with 'loghost' as syslog_config.
        """
        with patch(
            "salt.modules.vsphere.enable_firewall_ruleset",
            MagicMock(return_value={"host_1.foo.com": {"retcode": 0}}),
        ):
            with patch(
                "salt.modules.vsphere._set_syslog_config_helper",
                MagicMock(return_value={}),
            ):
                host_1 = "host_1.foo.com"
                self.assertEqual(
                    {host_1: {"enable_firewall": {"success": True}}},
                    vsphere.set_syslog_config(
                        HOST,
                        USER,
                        PASSWORD,
                        "loghost",
                        "foo",
                        firewall=True,
                        esxi_hosts=[host_1],
                    ),
                )

    def test_set_syslog_config_firewall_bad_retcode(self):
        """
        Tests error message given for a single ESXi host with 'loghost' as syslog_config.
        """
        with patch(
            "salt.modules.vsphere.enable_firewall_ruleset",
            MagicMock(return_value={HOST: {"retcode": 1, "stdout": ERROR}}),
        ):
            with patch(
                "salt.modules.vsphere._set_syslog_config_helper",
                MagicMock(return_value={}),
            ):
                self.assertEqual(
                    {HOST: {"enable_firewall": {"message": ERROR, "success": False}}},
                    vsphere.set_syslog_config(
                        HOST, USER, PASSWORD, "loghost", "foo", firewall=True
                    ),
                )

    def test_set_syslog_config_firewall_success(self):
        """
        Tests successful function return for a single ESXi host with 'loghost' as syslog_config.
        """
        with patch(
            "salt.modules.vsphere.enable_firewall_ruleset",
            MagicMock(return_value={HOST: {"retcode": 0}}),
        ):
            with patch(
                "salt.modules.vsphere._set_syslog_config_helper",
                MagicMock(return_value={}),
            ):
                self.assertEqual(
                    {HOST: {"enable_firewall": {"success": True}}},
                    vsphere.set_syslog_config(
                        HOST, USER, PASSWORD, "loghost", "foo", firewall=True
                    ),
                )

    # Tests for get_syslog_config function

    def test_get_syslog_config_esxi_hosts_not_list(self):
        """
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list.
        """
        self.assertRaises(
            CommandExecutionError,
            vsphere.get_syslog_config,
            HOST,
            USER,
            PASSWORD,
            esxi_hosts="foo",
        )

    def test_get_syslog_config_host_list_bad_retcode(self):
        """
        Tests error message returned with list of esxi_hosts.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 1, "stdout": ERROR}),
        ):
            host_1 = "host_1.foo.com"
            self.assertEqual(
                {host_1: {"message": ERROR, "success": False}},
                vsphere.get_syslog_config(HOST, USER, PASSWORD, esxi_hosts=[host_1]),
            )

    def test_get_syslog_config_host_list_success(self):
        """
        Tests successful function return when an esxi_host is provided.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 0, "stdout": ""}),
        ):
            host_1 = "host_1.foo.com"
            self.assertEqual(
                {host_1: {"success": True}},
                vsphere.get_syslog_config(HOST, USER, PASSWORD, esxi_hosts=[host_1]),
            )

    def test_get_syslog_config_bad_retcode(self):
        """
        Tests error message given for a single ESXi host.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 1, "stdout": ERROR}),
        ):
            self.assertEqual(
                {HOST: {"message": ERROR, "success": False}},
                vsphere.get_syslog_config(HOST, USER, PASSWORD),
            )

    def test_get_syslog_config_success(self):
        """
        Tests successful function return for a single ESXi host.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 0, "stdout": ""}),
        ):
            self.assertEqual(
                {HOST: {"success": True}},
                vsphere.get_syslog_config(HOST, USER, PASSWORD),
            )

    # Tests for reset_syslog_config function

    def test_reset_syslog_config_no_syslog_config(self):
        """
        Tests CommandExecutionError is raised when a syslog_config parameter is missing.
        """
        self.assertRaises(
            CommandExecutionError, vsphere.reset_syslog_config, HOST, USER, PASSWORD
        )

    def test_reset_syslog_config_esxi_hosts_not_list(self):
        """
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list.
        """
        self.assertRaises(
            CommandExecutionError,
            vsphere.reset_syslog_config,
            HOST,
            USER,
            PASSWORD,
            syslog_config="test",
            esxi_hosts="foo",
        )

    def test_reset_syslog_config_invalid_config_param(self):
        """
        Tests error message returned when an invalid syslog_config parameter is provided.
        """
        with patch("salt.utils.vmware.esxcli", MagicMock(return_value={})):
            error = "Invalid syslog configuration parameter"
            self.assertEqual(
                {
                    HOST: {
                        "success": False,
                        "test": {"message": error, "success": False},
                    }
                },
                vsphere.reset_syslog_config(HOST, USER, PASSWORD, syslog_config="test"),
            )

    def test_reset_syslog_config_host_list_bad_retcode(self):
        """
        Tests error message returned with list of esxi_hosts.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 1, "stdout": ERROR}),
        ):
            host_1 = "host_1.foo.com"
            self.assertEqual(
                {
                    host_1: {
                        "success": False,
                        "logdir": {"message": ERROR, "success": False},
                    }
                },
                vsphere.reset_syslog_config(
                    HOST, USER, PASSWORD, syslog_config="logdir", esxi_hosts=[host_1]
                ),
            )

    def test_reset_syslog_config_host_list_success(self):
        """
        Tests successful function return when an esxi_host is provided.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 0, "stdout": ""}),
        ):
            host_1 = "host_1.foo.com"
            self.assertEqual(
                {host_1: {"success": True, "loghost": {"success": True}}},
                vsphere.reset_syslog_config(
                    HOST, USER, PASSWORD, syslog_config="loghost", esxi_hosts=[host_1]
                ),
            )

    def test_reset_syslog_config_bad_retcode(self):
        """
        Tests error message given for a single ESXi host.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 1, "stdout": ERROR}),
        ):
            self.assertEqual(
                {
                    HOST: {
                        "success": False,
                        "logdir-unique": {"message": ERROR, "success": False},
                    }
                },
                vsphere.reset_syslog_config(
                    HOST, USER, PASSWORD, syslog_config="logdir-unique"
                ),
            )

    def test_reset_syslog_config_success(self):
        """
        Tests successful function return for a single ESXi host.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 0, "stdout": ""}),
        ):
            self.assertEqual(
                {HOST: {"success": True, "default-rotate": {"success": True}}},
                vsphere.reset_syslog_config(
                    HOST, USER, PASSWORD, syslog_config="default-rotate"
                ),
            )

    def test_reset_syslog_config_success_multiple_configs(self):
        """
        Tests successful function return for a single ESXi host when passing in multiple syslog_config values.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 0, "stdout": ""}),
        ):
            self.assertEqual(
                {
                    HOST: {
                        "success": True,
                        "default-size": {"success": True},
                        "default-timeout": {"success": True},
                    }
                },
                vsphere.reset_syslog_config(
                    HOST, USER, PASSWORD, syslog_config="default-size,default-timeout"
                ),
            )

    def test_reset_syslog_config_success_all_configs(self):
        """
        Tests successful function return for a single ESXi host when passing in multiple syslog_config values.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 0, "stdout": ""}),
        ):
            self.assertEqual(
                {
                    HOST: {
                        "success": True,
                        "logdir": {"success": True},
                        "loghost": {"success": True},
                        "default-rotate": {"success": True},
                        "default-size": {"success": True},
                        "default-timeout": {"success": True},
                        "logdir-unique": {"success": True},
                    }
                },
                vsphere.reset_syslog_config(HOST, USER, PASSWORD, syslog_config="all"),
            )

    # Tests for _reset_syslog_config_params function

    def test_reset_syslog_config_params_no_valid_reset(self):
        """
        Tests function returns False when an invalid syslog config is passed.
        """
        valid_resets = ["hello", "world"]
        config = "foo"
        ret = {
            "success": False,
            config: {
                "success": False,
                "message": "Invalid syslog configuration parameter",
            },
        }
        self.assertEqual(
            ret,
            vsphere._reset_syslog_config_params(
                HOST, USER, PASSWORD, "cmd", config, valid_resets
            ),
        )

    def test_reset_syslog_config_params_error(self):
        """
        Tests function returns False when the esxxli function returns an unsuccessful retcode.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 1, "stdout": ERROR}),
        ):
            valid_resets = ["hello", "world"]
            error_dict = {"success": False, "message": ERROR}
            ret = {"success": False, "hello": error_dict, "world": error_dict}
            self.assertDictEqual(
                ret,
                vsphere._reset_syslog_config_params(
                    HOST, USER, PASSWORD, "cmd", valid_resets, valid_resets
                ),
            )

    def test_reset_syslog_config_params_success(self):
        """
        Tests function returns True when the esxxli function returns a successful retcode.
        """
        with patch("salt.utils.vmware.esxcli", MagicMock(return_value={"retcode": 0})):
            valid_resets = ["hello", "world"]
            ret = {
                "success": True,
                "hello": {"success": True},
                "world": {"success": True},
            }
            self.assertDictEqual(
                ret,
                vsphere._reset_syslog_config_params(
                    HOST, USER, PASSWORD, "cmd", valid_resets, valid_resets
                ),
            )

    # Tests for _set_syslog_config_helper function

    def test_set_syslog_config_helper_no_valid_reset(self):
        """
        Tests function returns False when an invalid syslog config is passed.
        """
        config = "foo"
        ret = {
            "success": False,
            "message": "'{}' is not a valid config variable.".format(config),
        }
        self.assertEqual(
            ret, vsphere._set_syslog_config_helper(HOST, USER, PASSWORD, config, "bar")
        )

    def test_set_syslog_config_helper_bad_retcode(self):
        """
        Tests function returns False when the esxcli function returns an unsuccessful retcode.
        """
        with patch(
            "salt.utils.vmware.esxcli",
            MagicMock(return_value={"retcode": 1, "stdout": ERROR}),
        ):
            config = "default-rotate"
            self.assertEqual(
                {config: {"success": False, "message": ERROR}},
                vsphere._set_syslog_config_helper(HOST, USER, PASSWORD, config, "foo"),
            )

    def test_set_syslog_config_helper_success(self):
        """
        Tests successful function return.
        """
        with patch("salt.utils.vmware.esxcli", MagicMock(return_value={"retcode": 0})):
            config = "logdir"
            self.assertEqual(
                {config: {"success": True}},
                vsphere._set_syslog_config_helper(HOST, USER, PASSWORD, config, "foo"),
            )


class GetProxyTypeTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for salt.modules.vsphere.get_proxy_type
    """

    def setup_loader_modules(self):
        return {vsphere: {}}

    def test_output(self):
        with patch.dict(
            vsphere.__pillar__, {"proxy": {"proxytype": "fake_proxy_type"}}
        ):
            ret = vsphere.get_proxy_type()
        self.assertEqual("fake_proxy_type", ret)


class SupportsProxiesTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for salt.modules.vsphere._supports_proxies decorator
    """

    def setup_loader_modules(self):
        return {vsphere: {}}

    def test_supported_proxy(self):
        @vsphere._supports_proxies("supported")
        def mock_function():
            return "fake_function"

        with patch(
            "salt.modules.vsphere.get_proxy_type", MagicMock(return_value="supported")
        ):
            ret = mock_function()
        self.assertEqual("fake_function", ret)

    def test_unsupported_proxy(self):
        @vsphere._supports_proxies("supported")
        def mock_function():
            return "fake_function"

        with patch(
            "salt.modules.vsphere.get_proxy_type", MagicMock(return_value="unsupported")
        ):
            with self.assertRaises(CommandExecutionError) as excinfo:
                mock_function()
        self.assertEqual(
            "'unsupported' proxy is not supported by function mock_function",
            excinfo.exception.strerror,
        )


class _GetProxyConnectionDetailsTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for salt.modules.vsphere._get_proxy_connection_details
    """

    def setup_loader_modules(self):
        return {vsphere: {}}

    def setUp(self):
        self.esxi_host_details = {
            "host": "fake_host",
            "username": "fake_username",
            "password": "fake_password",
            "protocol": "fake_protocol",
            "port": "fake_port",
            "mechanism": "fake_mechanism",
            "principal": "fake_principal",
            "domain": "fake_domain",
        }
        self.esxi_vcenter_details = {
            "vcenter": "fake_vcenter",
            "username": "fake_username",
            "password": "fake_password",
            "protocol": "fake_protocol",
            "port": "fake_port",
            "mechanism": "fake_mechanism",
            "principal": "fake_principal",
            "domain": "fake_domain",
        }
        self.esxdatacenter_details = {
            "vcenter": "fake_vcenter",
            "datacenter": "fake_dc",
            "username": "fake_username",
            "password": "fake_password",
            "protocol": "fake_protocol",
            "port": "fake_port",
            "mechanism": "fake_mechanism",
            "principal": "fake_principal",
            "domain": "fake_domain",
        }
        self.esxcluster_details = {
            "vcenter": "fake_vcenter",
            "datacenter": "fake_dc",
            "cluster": "fake_cluster",
            "username": "fake_username",
            "password": "fake_password",
            "protocol": "fake_protocol",
            "port": "fake_port",
            "mechanism": "fake_mechanism",
            "principal": "fake_principal",
            "domain": "fake_domain",
        }
        self.vcenter_details = {
            "vcenter": "fake_vcenter",
            "username": "fake_username",
            "password": "fake_password",
            "protocol": "fake_protocol",
            "port": "fake_port",
            "mechanism": "fake_mechanism",
            "principal": "fake_principal",
            "domain": "fake_domain",
        }

    def tearDown(self):
        for attrname in (
            "esxi_host_details",
            "esxi_vcenter_details",
            "esxdatacenter_details",
            "esxcluster_details",
        ):
            try:
                delattr(self, attrname)
            except AttributeError:
                continue

    def test_esxi_proxy_host_details(self):
        with patch(
            "salt.modules.vsphere.get_proxy_type", MagicMock(return_value="esxi")
        ):
            with patch.dict(
                vsphere.__salt__,
                {"esxi.get_details": MagicMock(return_value=self.esxi_host_details)},
            ):
                ret = vsphere._get_proxy_connection_details()
        self.assertEqual(
            (
                "fake_host",
                "fake_username",
                "fake_password",
                "fake_protocol",
                "fake_port",
                "fake_mechanism",
                "fake_principal",
                "fake_domain",
            ),
            ret,
        )

    def test_esxdatacenter_proxy_details(self):
        with patch(
            "salt.modules.vsphere.get_proxy_type",
            MagicMock(return_value="esxdatacenter"),
        ):
            with patch.dict(
                vsphere.__salt__,
                {
                    "esxdatacenter.get_details": MagicMock(
                        return_value=self.esxdatacenter_details
                    )
                },
            ):
                ret = vsphere._get_proxy_connection_details()
        self.assertEqual(
            (
                "fake_vcenter",
                "fake_username",
                "fake_password",
                "fake_protocol",
                "fake_port",
                "fake_mechanism",
                "fake_principal",
                "fake_domain",
            ),
            ret,
        )

    def test_esxcluster_proxy_details(self):
        with patch(
            "salt.modules.vsphere.get_proxy_type", MagicMock(return_value="esxcluster")
        ):
            with patch.dict(
                vsphere.__salt__,
                {
                    "esxcluster.get_details": MagicMock(
                        return_value=self.esxcluster_details
                    )
                },
            ):
                ret = vsphere._get_proxy_connection_details()
        self.assertEqual(
            (
                "fake_vcenter",
                "fake_username",
                "fake_password",
                "fake_protocol",
                "fake_port",
                "fake_mechanism",
                "fake_principal",
                "fake_domain",
            ),
            ret,
        )

    def test_esxi_proxy_vcenter_details(self):
        with patch(
            "salt.modules.vsphere.get_proxy_type", MagicMock(return_value="esxi")
        ):
            with patch.dict(
                vsphere.__salt__,
                {"esxi.get_details": MagicMock(return_value=self.esxi_vcenter_details)},
            ):
                ret = vsphere._get_proxy_connection_details()
        self.assertEqual(
            (
                "fake_vcenter",
                "fake_username",
                "fake_password",
                "fake_protocol",
                "fake_port",
                "fake_mechanism",
                "fake_principal",
                "fake_domain",
            ),
            ret,
        )

    def test_vcenter_proxy_details(self):
        with patch(
            "salt.modules.vsphere.get_proxy_type", MagicMock(return_value="vcenter")
        ):
            with patch.dict(
                vsphere.__salt__,
                {"vcenter.get_details": MagicMock(return_value=self.vcenter_details)},
            ):
                ret = vsphere._get_proxy_connection_details()
        self.assertEqual(
            (
                "fake_vcenter",
                "fake_username",
                "fake_password",
                "fake_protocol",
                "fake_port",
                "fake_mechanism",
                "fake_principal",
                "fake_domain",
            ),
            ret,
        )

    def test_unsupported_proxy_details(self):
        with patch(
            "salt.modules.vsphere.get_proxy_type", MagicMock(return_value="unsupported")
        ):
            with self.assertRaises(CommandExecutionError) as excinfo:
                ret = vsphere._get_proxy_connection_details()
        self.assertEqual(
            "'unsupported' proxy is not supported", excinfo.exception.strerror
        )

    def test_vcenter_proxy_details_verify_ssl(self):
        for verify_ssl in [True, False]:
            details = self.vcenter_details.copy()
            details["verify_ssl"] = verify_ssl

            with patch(
                "salt.modules.vsphere.get_proxy_type", MagicMock(return_value="vcenter")
            ):
                with patch.dict(
                    vsphere.__salt__,
                    {"vcenter.get_details": MagicMock(return_value=details)},
                ):
                    ret = vsphere._get_proxy_connection_details()
            self.assertEqual(
                (
                    "fake_vcenter",
                    "fake_username",
                    "fake_password",
                    "fake_protocol",
                    "fake_port",
                    "fake_mechanism",
                    "fake_principal",
                    "fake_domain",
                    verify_ssl,
                ),
                ret,
            )


class GetsServiceInstanceViaProxyTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for salt.modules.vsphere._gets_service_instance_via_proxy
    decorator
    """

    def setup_loader_modules(self):
        patcher = patch("salt.utils.vmware.get_service_instance", MagicMock())
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch("salt.utils.vmware.disconnect", MagicMock())
        patcher.start()
        self.addCleanup(patcher.stop)
        return {vsphere: {"_get_proxy_connection_details": MagicMock()}}

    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_details1 = MagicMock()
        self.mock_details2 = MagicMock()

    def tearDown(self):
        for attrname in ("mock_si", "mock_details1", "mock_details2"):
            try:
                delattr(self, attrname)
            except AttributeError:
                continue

    def test_no_service_instance_or_kwargs_parameters(self):
        @vsphere._gets_service_instance_via_proxy
        def mock_function():
            return "fake_function"

        with self.assertRaises(CommandExecutionError) as excinfo:
            mock_function()
        self.assertEqual(
            "Function mock_function must have either a "
            "'service_instance', or a '**kwargs' type "
            "parameter",
            excinfo.exception.strerror,
        )

    def test___get_proxy_connection_details_call(self):
        mock__get_proxy_connection_details = MagicMock()

        @vsphere._gets_service_instance_via_proxy
        def mock_function(service_instance=None):
            return service_instance

        with patch(
            "salt.modules.vsphere._get_proxy_connection_details",
            mock__get_proxy_connection_details,
        ):
            mock_function()
        mock__get_proxy_connection_details.assert_called_once_with()

    def test_service_instance_named_parameter_no_value(self):
        mock_get_service_instance = MagicMock(return_value=self.mock_si)
        mock_disconnect = MagicMock()

        @vsphere._gets_service_instance_via_proxy
        def mock_function(service_instance=None):
            return service_instance

        with patch(
            "salt.modules.vsphere._get_proxy_connection_details",
            MagicMock(return_value=(self.mock_details1, self.mock_details2)),
        ):
            with patch(
                "salt.utils.vmware.get_service_instance", mock_get_service_instance
            ):
                with patch("salt.utils.vmware.disconnect", mock_disconnect):
                    ret = mock_function()
        mock_get_service_instance.assert_called_once_with(
            self.mock_details1, self.mock_details2
        )
        mock_disconnect.assert_called_once_with(self.mock_si)
        self.assertEqual(ret, self.mock_si)

    def test_service_instance_kwargs_parameter_no_value(self):
        mock_get_service_instance = MagicMock(return_value=self.mock_si)
        mock_disconnect = MagicMock()

        @vsphere._gets_service_instance_via_proxy
        def mock_function(**kwargs):
            return kwargs["service_instance"]

        with patch(
            "salt.modules.vsphere._get_proxy_connection_details",
            MagicMock(return_value=(self.mock_details1, self.mock_details2)),
        ):
            with patch(
                "salt.utils.vmware.get_service_instance", mock_get_service_instance
            ):
                with patch("salt.utils.vmware.disconnect", mock_disconnect):
                    ret = mock_function()
        mock_get_service_instance.assert_called_once_with(
            self.mock_details1, self.mock_details2
        )
        mock_disconnect.assert_called_once_with(self.mock_si)
        self.assertEqual(ret, self.mock_si)

    def test_service_instance_positional_parameter_no_default_value(self):
        mock_get_service_instance = MagicMock()
        mock_disconnect = MagicMock()

        @vsphere._gets_service_instance_via_proxy
        def mock_function(service_instance):
            return service_instance

        with patch(
            "salt.modules.vsphere._get_proxy_connection_details",
            MagicMock(return_value=(self.mock_details1, self.mock_details2)),
        ):
            with patch(
                "salt.utils.vmware.get_service_instance", mock_get_service_instance
            ):
                with patch("salt.utils.vmware.disconnect", mock_disconnect):
                    ret = mock_function(self.mock_si)
        self.assertEqual(mock_get_service_instance.call_count, 0)
        self.assertEqual(mock_disconnect.call_count, 0)
        self.assertEqual(ret, self.mock_si)

    def test_service_instance_positional_parameter_with_default_value(self):
        mock_get_service_instance = MagicMock()
        mock_disconnect = MagicMock()

        @vsphere._gets_service_instance_via_proxy
        def mock_function(service_instance=None):
            return service_instance

        with patch(
            "salt.modules.vsphere._get_proxy_connection_details",
            MagicMock(return_value=(self.mock_details1, self.mock_details2)),
        ):
            with patch(
                "salt.utils.vmware.get_service_instance", mock_get_service_instance
            ):
                with patch("salt.utils.vmware.disconnect", mock_disconnect):
                    ret = mock_function(self.mock_si)
        self.assertEqual(mock_get_service_instance.call_count, 0)
        self.assertEqual(mock_disconnect.call_count, 0)
        self.assertEqual(ret, self.mock_si)

    def test_service_instance_named_parameter_with_default_value(self):
        mock_get_service_instance = MagicMock()
        mock_disconnect = MagicMock()

        @vsphere._gets_service_instance_via_proxy
        def mock_function(service_instance=None):
            return service_instance

        with patch(
            "salt.modules.vsphere._get_proxy_connection_details",
            MagicMock(return_value=(self.mock_details1, self.mock_details2)),
        ):
            with patch(
                "salt.utils.vmware.get_service_instance", mock_get_service_instance
            ):
                with patch("salt.utils.vmware.disconnect", mock_disconnect):
                    ret = mock_function(service_instance=self.mock_si)
        self.assertEqual(mock_get_service_instance.call_count, 0)
        self.assertEqual(mock_disconnect.call_count, 0)
        self.assertEqual(ret, self.mock_si)

    def test_service_instance_kwargs_parameter_passthrough(self):
        mock_get_service_instance = MagicMock()
        mock_disconnect = MagicMock()

        @vsphere._gets_service_instance_via_proxy
        def mock_function(**kwargs):
            return kwargs["service_instance"]

        with patch(
            "salt.modules.vsphere._get_proxy_connection_details",
            MagicMock(return_value=(self.mock_details1, self.mock_details2)),
        ):
            with patch(
                "salt.utils.vmware.get_service_instance", mock_get_service_instance
            ):
                with patch("salt.utils.vmware.disconnect", mock_disconnect):
                    ret = mock_function(service_instance=self.mock_si)
        self.assertEqual(mock_get_service_instance.call_count, 0)
        self.assertEqual(mock_disconnect.call_count, 0)
        self.assertEqual(ret, self.mock_si)


class GetServiceInstanceViaProxyTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for salt.modules.vsphere.get_service_instance_via_proxy
    """

    def setup_loader_modules(self):
        patcher = patch("salt.utils.vmware.get_service_instance", MagicMock())
        patcher.start()
        self.addCleanup(patcher.stop)
        return {
            vsphere: {
                "get_proxy_type": MagicMock(return_value="esxi"),
                "_get_proxy_connection_details": MagicMock(),
            }
        }

    def test_supported_proxies(self):
        supported_proxies = ["esxi", "esxcluster", "esxdatacenter", "vcenter", "esxvm"]
        for proxy_type in supported_proxies:
            with patch(
                "salt.modules.vsphere.get_proxy_type",
                MagicMock(return_value=proxy_type),
            ):
                vsphere.get_service_instance_via_proxy()

    def test_get_service_instance_call(self):
        mock_connection_details = [MagicMock(), MagicMock(), MagicMock()]
        mock_get_service_instance = MagicMock()
        with patch(
            "salt.modules.vsphere._get_proxy_connection_details",
            MagicMock(return_value=mock_connection_details),
        ):
            with patch(
                "salt.utils.vmware.get_service_instance", mock_get_service_instance
            ):
                vsphere.get_service_instance_via_proxy()
        mock_get_service_instance.assert_called_once_with(*mock_connection_details)

    def test_output(self):
        mock_si = MagicMock()
        with patch(
            "salt.utils.vmware.get_service_instance", MagicMock(return_value=mock_si)
        ):
            res = vsphere.get_service_instance_via_proxy()
        self.assertEqual(res, mock_si)


class DisconnectTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for salt.modules.vsphere.disconnect
    """

    def setup_loader_modules(self):
        self.mock_si = MagicMock()
        self.addCleanup(delattr, self, "mock_si")
        patcher = patch("salt.utils.vmware.disconnect", MagicMock())
        patcher.start()
        self.addCleanup(patcher.stop)
        return {
            vsphere: {
                "_get_proxy_connection_details": MagicMock(),
                "get_proxy_type": MagicMock(return_value="esxi"),
            }
        }

    def test_supported_proxies(self):
        supported_proxies = ["esxi", "esxcluster", "esxdatacenter", "vcenter", "esxvm"]
        for proxy_type in supported_proxies:
            with patch(
                "salt.modules.vsphere.get_proxy_type",
                MagicMock(return_value=proxy_type),
            ):
                vsphere.disconnect(self.mock_si)

    def test_disconnect_call(self):
        mock_disconnect = MagicMock()
        with patch("salt.utils.vmware.disconnect", mock_disconnect):
            vsphere.disconnect(self.mock_si)
        mock_disconnect.assert_called_once_with(self.mock_si)

    def test_output(self):
        res = vsphere.disconnect(self.mock_si)
        self.assertEqual(res, True)


class TestVcenterConnectionTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for salt.modules.vsphere.test_vcenter_connection
    """

    def setup_loader_modules(self):
        self.mock_si = MagicMock()
        self.addCleanup(delattr, self, "mock_si")
        patcher = patch(
            "salt.utils.vmware.get_service_instance",
            MagicMock(return_value=self.mock_si),
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch("salt.utils.vmware.disconnect", MagicMock())
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch("salt.utils.vmware.is_connection_to_a_vcenter", MagicMock())
        patcher.start()
        self.addCleanup(patcher.stop)
        return {
            vsphere: {
                "_get_proxy_connection_details": MagicMock(),
                "get_proxy_type": MagicMock(return_value="esxi"),
            }
        }

    def test_supported_proxies(self):
        supported_proxies = ["esxi", "esxcluster", "esxdatacenter", "vcenter", "esxvm"]
        for proxy_type in supported_proxies:
            with patch(
                "salt.modules.vsphere.get_proxy_type",
                MagicMock(return_value=proxy_type),
            ):
                vsphere.test_vcenter_connection()

    def test_is_connection_to_a_vcenter_call_default_service_instance(self):
        mock_is_connection_to_a_vcenter = MagicMock()
        with patch(
            "salt.utils.vmware.is_connection_to_a_vcenter",
            mock_is_connection_to_a_vcenter,
        ):
            vsphere.test_vcenter_connection()
        mock_is_connection_to_a_vcenter.assert_called_once_with(self.mock_si)

    def test_is_connection_to_a_vcenter_call_explicit_service_instance(self):
        expl_mock_si = MagicMock()
        mock_is_connection_to_a_vcenter = MagicMock()
        with patch(
            "salt.utils.vmware.is_connection_to_a_vcenter",
            mock_is_connection_to_a_vcenter,
        ):
            vsphere.test_vcenter_connection(expl_mock_si)
        mock_is_connection_to_a_vcenter.assert_called_once_with(expl_mock_si)

    def test_is_connection_to_a_vcenter_raises_vmware_salt_error(self):
        exc = VMwareSaltError("VMwareSaltError")
        with patch(
            "salt.utils.vmware.is_connection_to_a_vcenter", MagicMock(side_effect=exc)
        ):
            res = vsphere.test_vcenter_connection()
        self.assertEqual(res, False)

    def test_is_connection_to_a_vcenter_raises_non_vmware_salt_error(self):
        exc = Exception("NonVMwareSaltError")
        with patch(
            "salt.utils.vmware.is_connection_to_a_vcenter", MagicMock(side_effect=exc)
        ):
            with self.assertRaises(Exception) as excinfo:
                res = vsphere.test_vcenter_connection()
        self.assertEqual("NonVMwareSaltError", str(excinfo.exception))

    def test_output_true(self):
        with patch(
            "salt.utils.vmware.is_connection_to_a_vcenter", MagicMock(return_value=True)
        ):
            res = vsphere.test_vcenter_connection()
        self.assertEqual(res, True)

    def test_output_false(self):
        with patch(
            "salt.utils.vmware.is_connection_to_a_vcenter",
            MagicMock(return_value=False),
        ):
            res = vsphere.test_vcenter_connection()
        self.assertEqual(res, False)


@pytest.mark.skipif(not HAS_PYVMOMI, reason="The 'pyvmomi' library is missing")
class ListDatacentersViaProxyTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for salt.modules.vsphere.list_datacenters_via_proxy
    """

    def setup_loader_modules(self):
        self.mock_si = MagicMock()
        self.addCleanup(delattr, self, "mock_si")
        patcher = patch(
            "salt.utils.vmware.get_service_instance",
            MagicMock(return_value=self.mock_si),
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch("salt.utils.vmware.get_datacenters", MagicMock())
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch("salt.utils.vmware.get_managed_object_name", MagicMock())
        patcher.start()
        self.addCleanup(patcher.stop)
        return {
            vsphere: {
                "_get_proxy_connection_details": MagicMock(),
                "get_proxy_type": MagicMock(return_value="esxdatacenter"),
            }
        }

    def test_supported_proxies(self):
        supported_proxies = ["esxcluster", "esxdatacenter", "vcenter", "esxvm"]
        for proxy_type in supported_proxies:
            with patch(
                "salt.modules.vsphere.get_proxy_type",
                MagicMock(return_value=proxy_type),
            ):
                vsphere.list_datacenters_via_proxy()

    def test_default_params(self):
        mock_get_datacenters = MagicMock()
        with patch("salt.utils.vmware.get_datacenters", mock_get_datacenters):
            vsphere.list_datacenters_via_proxy()
        mock_get_datacenters.assert_called_once_with(
            self.mock_si, get_all_datacenters=True
        )

    def test_defined_service_instance(self):
        mock_si = MagicMock()
        mock_get_datacenters = MagicMock()
        with patch("salt.utils.vmware.get_datacenters", mock_get_datacenters):
            vsphere.list_datacenters_via_proxy(service_instance=mock_si)
        mock_get_datacenters.assert_called_once_with(mock_si, get_all_datacenters=True)

    def test_defined_datacenter_names(self):
        mock_datacenters = MagicMock()
        mock_get_datacenters = MagicMock()
        with patch("salt.utils.vmware.get_datacenters", mock_get_datacenters):
            vsphere.list_datacenters_via_proxy(mock_datacenters)
        mock_get_datacenters.assert_called_once_with(self.mock_si, mock_datacenters)

    def test_get_managed_object_name_calls(self):
        mock_get_managed_object_name = MagicMock()
        mock_dcs = [MagicMock(), MagicMock()]
        with patch(
            "salt.utils.vmware.get_datacenters", MagicMock(return_value=mock_dcs)
        ):
            with patch(
                "salt.utils.vmware.get_managed_object_name",
                mock_get_managed_object_name,
            ):
                vsphere.list_datacenters_via_proxy()
        mock_get_managed_object_name.assert_has_calls(
            [call(mock_dcs[0]), call(mock_dcs[1])]
        )

    def test_returned_array(self):
        with patch(
            "salt.utils.vmware.get_datacenters",
            MagicMock(return_value=[MagicMock(), MagicMock()]),
        ):
            # 2 datacenters
            with patch(
                "salt.utils.vmware.get_managed_object_name",
                MagicMock(side_effect=["fake_dc1", "fake_dc2", "fake_dc3"]),
            ):
                # 3 possible names
                res = vsphere.list_datacenters_via_proxy()

        # Just the first two names are in the result
        self.assertEqual(res, [{"name": "fake_dc1"}, {"name": "fake_dc2"}])


@pytest.mark.skipif(not HAS_PYVMOMI, reason="The 'pyvmomi' library is missing")
class CreateDatacenterTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for salt.modules.vsphere.create_datacenter
    """

    def setup_loader_modules(self):
        self.mock_si = MagicMock()
        self.addCleanup(delattr, self, "mock_si")
        patcher = patch(
            "salt.utils.vmware.get_service_instance",
            MagicMock(return_value=self.mock_si),
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch("salt.utils.vmware.create_datacenter", MagicMock())
        patcher.start()
        self.addCleanup(patcher.stop)
        return {
            vsphere: {
                "_get_proxy_connection_details": MagicMock(),
                "get_proxy_type": MagicMock(return_value="esxdatacenter"),
            }
        }

    def test_supported_proxies(self):
        supported_proxies = ["esxdatacenter", "vcenter"]
        for proxy_type in supported_proxies:
            with patch(
                "salt.modules.vsphere.get_proxy_type",
                MagicMock(return_value=proxy_type),
            ):
                vsphere.create_datacenter("fake_dc1")

    def test_default_service_instance(self):
        mock_create_datacenter = MagicMock()
        with patch("salt.utils.vmware.create_datacenter", mock_create_datacenter):
            vsphere.create_datacenter("fake_dc1")
        mock_create_datacenter.assert_called_once_with(self.mock_si, "fake_dc1")

    def test_defined_service_instance(self):
        mock_si = MagicMock()
        mock_create_datacenter = MagicMock()
        with patch("salt.utils.vmware.create_datacenter", mock_create_datacenter):
            vsphere.create_datacenter("fake_dc1", service_instance=mock_si)
        mock_create_datacenter.assert_called_once_with(mock_si, "fake_dc1")

    def test_returned_value(self):
        res = vsphere.create_datacenter("fake_dc1")
        self.assertEqual(res, {"create_datacenter": True})


@pytest.mark.skipif(not HAS_PYVMOMI, reason="The 'pyvmomi' library is missing")
class EraseDiskPartitionsTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for salt.modules.vsphere.erase_disk_partitions
    """

    def setup_loader_modules(self):
        return {
            vsphere: {
                "_get_proxy_connection_details": MagicMock(),
                "__proxy__": {
                    "esxi.get_details": MagicMock(
                        return_value={"esxi_host": "fake_host"}
                    )
                },
            }
        }

    def setUp(self):
        attrs = (("mock_si", MagicMock()), ("mock_host", MagicMock()))
        for attr, mock_obj in attrs:
            setattr(self, attr, mock_obj)
            self.addCleanup(delattr, self, attr)
        attrs = (
            ("mock_proxy_target", MagicMock(return_value=self.mock_host)),
            ("mock_erase_disk_partitions", MagicMock()),
        )
        for attr, mock_obj in attrs:
            setattr(self, attr, mock_obj)
            self.addCleanup(delattr, self, attr)

        patches = (
            (
                "salt.utils.vmware.get_service_instance",
                MagicMock(return_value=self.mock_si),
            ),
            ("salt.modules.vsphere.get_proxy_type", MagicMock(return_value="esxi")),
            (
                "salt.modules.vsphere._get_proxy_target",
                MagicMock(return_value=self.mock_host),
            ),
            (
                "salt.utils.vmware.erase_disk_partitions",
                self.mock_erase_disk_partitions,
            ),
        )
        for module, mock_obj in patches:
            patcher = patch(module, mock_obj)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_supported_proxies(self):
        supported_proxies = ["esxi"]
        for proxy_type in supported_proxies:
            with patch(
                "salt.modules.vsphere.get_proxy_type",
                MagicMock(return_value=proxy_type),
            ):
                vsphere.erase_disk_partitions(disk_id="fake_disk")

    def test_no_disk_id_or_scsi_address(self):
        with self.assertRaises(ArgumentValueError) as excinfo:
            vsphere.erase_disk_partitions()
        self.assertEqual(
            "Either 'disk_id' or 'scsi_address' needs to be specified",
            excinfo.exception.strerror,
        )

    def test_get_proxy_target(self):
        mock_test_proxy_target = MagicMock()
        with patch("salt.modules.vsphere._get_proxy_target", mock_test_proxy_target):
            vsphere.erase_disk_partitions(disk_id="fake_disk")
        mock_test_proxy_target.assert_called_once_with(self.mock_si)

    def test_scsi_address_not_found(self):
        mock = MagicMock(return_value={"bad_scsi_address": "bad_disk_id"})
        with patch("salt.utils.vmware.get_scsi_address_to_lun_map", mock):
            with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                vsphere.erase_disk_partitions(scsi_address="fake_scsi_address")
        self.assertEqual(
            "Scsi lun with address 'fake_scsi_address' was "
            "not found on host 'fake_host'",
            excinfo.exception.strerror,
        )

    def test_scsi_address_to_disk_id_map(self):
        mock_disk_id = MagicMock(canonicalName="fake_scsi_disk_id")
        mock_get_scsi_addr_to_lun = MagicMock(
            return_value={"fake_scsi_address": mock_disk_id}
        )
        with patch(
            "salt.utils.vmware.get_scsi_address_to_lun_map", mock_get_scsi_addr_to_lun
        ):
            vsphere.erase_disk_partitions(scsi_address="fake_scsi_address")
        mock_get_scsi_addr_to_lun.assert_called_once_with(self.mock_host)
        self.mock_erase_disk_partitions.assert_called_once_with(
            self.mock_si, self.mock_host, "fake_scsi_disk_id", hostname="fake_host"
        )

    def test_erase_disk_partitions(self):
        vsphere.erase_disk_partitions(disk_id="fake_disk_id")
        self.mock_erase_disk_partitions.assert_called_once_with(
            self.mock_si, self.mock_host, "fake_disk_id", hostname="fake_host"
        )


@pytest.mark.skipif(not HAS_PYVMOMI, reason="The 'pyvmomi' library is missing")
class RemoveDatastoreTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for salt.modules.vsphere.remove_datastore
    """

    def setup_loader_modules(self):
        return {
            vsphere: {
                "_get_proxy_connection_details": MagicMock(),
                "get_proxy_type": MagicMock(return_value="esxdatacenter"),
            }
        }

    def setUp(self):
        attrs = (
            ("mock_si", MagicMock()),
            ("mock_target", MagicMock()),
            ("mock_ds", MagicMock()),
        )
        for attr, mock_obj in attrs:
            setattr(self, attr, mock_obj)
            self.addCleanup(delattr, self, attr)

        patches = (
            (
                "salt.utils.vmware.get_service_instance",
                MagicMock(return_value=self.mock_si),
            ),
            (
                "salt.modules.vsphere.get_proxy_type",
                MagicMock(return_value="esxdatacenter"),
            ),
            (
                "salt.modules.vsphere._get_proxy_target",
                MagicMock(return_value=self.mock_target),
            ),
            (
                "salt.utils.vmware.get_datastores",
                MagicMock(return_value=[self.mock_ds]),
            ),
            ("salt.utils.vmware.remove_datastore", MagicMock()),
        )
        for module, mock_obj in patches:
            patcher = patch(module, mock_obj)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_supported_proxes(self):
        supported_proxies = ["esxi", "esxcluster", "esxdatacenter"]
        for proxy_type in supported_proxies:
            with patch(
                "salt.modules.vsphere.get_proxy_type",
                MagicMock(return_value=proxy_type),
            ):
                vsphere.remove_datastore(datastore="fake_ds_name")

    def test__get_proxy_target_call(self):
        mock__get_proxy_target = MagicMock(return_value=self.mock_target)
        with patch("salt.modules.vsphere._get_proxy_target", mock__get_proxy_target):
            vsphere.remove_datastore(datastore="fake_ds_name")
        mock__get_proxy_target.assert_called_once_with(self.mock_si)

    def test_get_datastores_call(self):
        mock_get_datastores = MagicMock()
        with patch("salt.utils.vmware.get_datastores", mock_get_datastores):
            vsphere.remove_datastore(datastore="fake_ds")
        mock_get_datastores.assert_called_once_with(
            self.mock_si, reference=self.mock_target, datastore_names=["fake_ds"]
        )

    def test_datastore_not_found(self):
        with patch("salt.utils.vmware.get_datastores", MagicMock(return_value=[])):
            with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                vsphere.remove_datastore(datastore="fake_ds")
        self.assertEqual(
            "Datastore 'fake_ds' was not found", excinfo.exception.strerror
        )

    def test_multiple_datastores_found(self):
        with patch(
            "salt.utils.vmware.get_datastores",
            MagicMock(return_value=[MagicMock(), MagicMock()]),
        ):
            with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                vsphere.remove_datastore(datastore="fake_ds")
        self.assertEqual(
            "Multiple datastores 'fake_ds' were found", excinfo.exception.strerror
        )

    def test_remove_datastore_call(self):
        mock_remove_datastore = MagicMock()
        with patch("salt.utils.vmware.remove_datastore", mock_remove_datastore):
            vsphere.remove_datastore(datastore="fake_ds")
        mock_remove_datastore.assert_called_once_with(self.mock_si, self.mock_ds)

    def test_success_output(self):
        res = vsphere.remove_datastore(datastore="fake_ds")
        self.assertTrue(res)


@pytest.mark.skipif(not HAS_PYVMOMI, reason="The 'pyvmomi' library is missing")
class RemoveDiskgroupTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for salt.modules.vsphere.remove_diskgroup
    """

    def setup_loader_modules(self):
        return {
            vsphere: {
                "_get_proxy_connection_details": MagicMock(),
                "__proxy__": {
                    "esxi.get_details": MagicMock(
                        return_value={"esxi_host": "fake_host"}
                    )
                },
            }
        }

    def setUp(self):
        attrs = (
            ("mock_si", MagicMock()),
            ("mock_host", MagicMock()),
            ("mock_diskgroup", MagicMock()),
        )
        for attr, mock_obj in attrs:
            setattr(self, attr, mock_obj)
            self.addCleanup(delattr, self, attr)

        patches = (
            (
                "salt.utils.vmware.get_service_instance",
                MagicMock(return_value=self.mock_si),
            ),
            ("salt.modules.vsphere.get_proxy_type", MagicMock(return_value="esxi")),
            (
                "salt.modules.vsphere._get_proxy_target",
                MagicMock(return_value=self.mock_host),
            ),
            (
                "salt.utils.vmware.get_diskgroups",
                MagicMock(return_value=[self.mock_diskgroup]),
            ),
            ("salt.utils.vsan.remove_diskgroup", MagicMock()),
        )
        for module, mock_obj in patches:
            patcher = patch(module, mock_obj)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_supported_proxes(self):
        supported_proxies = ["esxi"]
        for proxy_type in supported_proxies:
            with patch(
                "salt.modules.vsphere.get_proxy_type",
                MagicMock(return_value=proxy_type),
            ):
                vsphere.remove_diskgroup(cache_disk_id="fake_disk_id")

    def test__get_proxy_target_call(self):
        mock__get_proxy_target = MagicMock(return_value=self.mock_host)
        with patch("salt.modules.vsphere._get_proxy_target", mock__get_proxy_target):
            vsphere.remove_diskgroup(cache_disk_id="fake_disk_id")
        mock__get_proxy_target.assert_called_once_with(self.mock_si)

    def test_get_disk_groups(self):
        mock_get_diskgroups = MagicMock(return_value=[self.mock_diskgroup])
        with patch("salt.utils.vmware.get_diskgroups", mock_get_diskgroups):
            vsphere.remove_diskgroup(cache_disk_id="fake_disk_id")
        mock_get_diskgroups.assert_called_once_with(
            self.mock_host, cache_disk_ids=["fake_disk_id"]
        )

    def test_disk_group_not_found_safety_checks_set(self):
        with patch("salt.utils.vmware.get_diskgroups", MagicMock(return_value=[])):
            with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                vsphere.remove_diskgroup(cache_disk_id="fake_disk_id")
        self.assertEqual(
            "No diskgroup with cache disk id "
            "'fake_disk_id' was found in ESXi host "
            "'fake_host'",
            excinfo.exception.strerror,
        )

    def test_remove_disk_group(self):
        mock_remove_diskgroup = MagicMock(return_value=None)
        with patch("salt.utils.vsan.remove_diskgroup", mock_remove_diskgroup):
            vsphere.remove_diskgroup(cache_disk_id="fake_disk_id")
        mock_remove_diskgroup.assert_called_once_with(
            self.mock_si, self.mock_host, self.mock_diskgroup, data_accessibility=True
        )

    def test_remove_disk_group_data_accessibility_false(self):
        mock_remove_diskgroup = MagicMock(return_value=None)
        with patch("salt.utils.vsan.remove_diskgroup", mock_remove_diskgroup):
            vsphere.remove_diskgroup(
                cache_disk_id="fake_disk_id", data_accessibility=False
            )
        mock_remove_diskgroup.assert_called_once_with(
            self.mock_si, self.mock_host, self.mock_diskgroup, data_accessibility=False
        )

    def test_success_output(self):
        res = vsphere.remove_diskgroup(cache_disk_id="fake_disk_id")
        self.assertTrue(res)


@pytest.mark.skipif(not HAS_PYVMOMI, reason="The 'pyvmomi' library is missing")
@pytest.mark.skipif(
    not vsphere.HAS_JSONSCHEMA, reason="The 'jsonschema' library is missing"
)
class RemoveCapacityFromDiskgroupTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for salt.modules.vsphere.remove_capacity_from_diskgroup
    """

    def setup_loader_modules(self):
        return {
            vsphere: {
                "_get_proxy_connection_details": MagicMock(),
                "__proxy__": {
                    "esxi.get_details": MagicMock(
                        return_value={"esxi_host": "fake_host"}
                    )
                },
            }
        }

    def setUp(self):
        attrs = (
            ("mock_si", MagicMock()),
            ("mock_schema", MagicMock()),
            ("mock_host", MagicMock()),
            ("mock_disk1", MagicMock(canonicalName="fake_disk1")),
            ("mock_disk2", MagicMock(canonicalName="fake_disk2")),
            ("mock_disk3", MagicMock(canonicalName="fake_disk3")),
            ("mock_diskgroup", MagicMock()),
        )
        for attr, mock_obj in attrs:
            setattr(self, attr, mock_obj)
            self.addCleanup(delattr, self, attr)

        patches = (
            (
                "salt.utils.vmware.get_service_instance",
                MagicMock(return_value=self.mock_si),
            ),
            (
                "salt.modules.vsphere.DiskGroupsDiskIdSchema.serialize",
                MagicMock(return_value=self.mock_schema),
            ),
            ("salt.modules.vsphere.jsonschema.validate", MagicMock()),
            ("salt.modules.vsphere.get_proxy_type", MagicMock(return_value="esxi")),
            (
                "salt.modules.vsphere._get_proxy_target",
                MagicMock(return_value=self.mock_host),
            ),
            (
                "salt.utils.vmware.get_disks",
                MagicMock(
                    return_value=[self.mock_disk1, self.mock_disk2, self.mock_disk3]
                ),
            ),
            (
                "salt.utils.vmware.get_diskgroups",
                MagicMock(return_value=[self.mock_diskgroup]),
            ),
            ("salt.utils.vsan.remove_capacity_from_diskgroup", MagicMock()),
        )
        for module, mock_obj in patches:
            patcher = patch(module, mock_obj)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_validate(self):
        mock_schema_validate = MagicMock()
        with patch("salt.modules.vsphere.jsonschema.validate", mock_schema_validate):
            vsphere.remove_capacity_from_diskgroup(
                cache_disk_id="fake_cache_disk_id",
                capacity_disk_ids=["fake_disk1", "fake_disk2"],
            )
        mock_schema_validate.assert_called_once_with(
            {
                "diskgroups": [
                    {
                        "cache_id": "fake_cache_disk_id",
                        "capacity_ids": ["fake_disk1", "fake_disk2"],
                    }
                ]
            },
            self.mock_schema,
        )

    def test_invalid_schema_validation(self):
        mock_schema_validate = MagicMock(
            side_effect=vsphere.jsonschema.exceptions.ValidationError("err")
        )
        with patch("salt.modules.vsphere.jsonschema.validate", mock_schema_validate):
            with self.assertRaises(ArgumentValueError) as excinfo:
                vsphere.remove_capacity_from_diskgroup(
                    cache_disk_id="fake_cache_disk_id",
                    capacity_disk_ids=["fake_disk1", "fake_disk2"],
                )
        self.assertEqual("err", excinfo.exception.strerror)

    def test_supported_proxes(self):
        supported_proxies = ["esxi"]
        for proxy_type in supported_proxies:
            with patch(
                "salt.modules.vsphere.get_proxy_type",
                MagicMock(return_value=proxy_type),
            ):
                vsphere.remove_capacity_from_diskgroup(
                    cache_disk_id="fake_cache_disk_id",
                    capacity_disk_ids=["fake_disk1", "fake_disk2"],
                )

    def test__get_proxy_target_call(self):
        mock__get_proxy_target = MagicMock(return_value=self.mock_host)
        with patch("salt.modules.vsphere._get_proxy_target", mock__get_proxy_target):
            vsphere.remove_capacity_from_diskgroup(
                cache_disk_id="fake_cache_disk_id",
                capacity_disk_ids=["fake_disk1", "fake_disk2"],
            )
        mock__get_proxy_target.assert_called_once_with(self.mock_si)

    def test_get_disks(self):
        mock_get_disks = MagicMock(
            return_value=[self.mock_disk1, self.mock_disk2, self.mock_disk3]
        )
        with patch("salt.utils.vmware.get_disks", mock_get_disks):
            vsphere.remove_capacity_from_diskgroup(
                cache_disk_id="fake_cache_disk_id",
                capacity_disk_ids=["fake_disk1", "fake_disk2"],
            )
        mock_get_disks.assert_called_once_with(
            self.mock_host, disk_ids=["fake_disk1", "fake_disk2"]
        )

    def test_disk_not_found_safety_checks_set(self):
        mock_get_disks = MagicMock(
            return_value=[self.mock_disk1, self.mock_disk2, self.mock_disk3]
        )
        with patch("salt.utils.vmware.get_disks", mock_get_disks):
            with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                vsphere.remove_capacity_from_diskgroup(
                    cache_disk_id="fake_cache_disk_id",
                    capacity_disk_ids=["fake_disk1", "fake_disk4"],
                    safety_checks=True,
                )
        self.assertEqual(
            "No disk with id 'fake_disk4' was found in ESXi host 'fake_host'",
            excinfo.exception.strerror,
        )

    def test_get_diskgroups(self):
        mock_get_diskgroups = MagicMock(return_value=[self.mock_diskgroup])
        with patch("salt.utils.vmware.get_diskgroups", mock_get_diskgroups):
            vsphere.remove_capacity_from_diskgroup(
                cache_disk_id="fake_cache_disk_id",
                capacity_disk_ids=["fake_disk1", "fake_disk2"],
            )
        mock_get_diskgroups.assert_called_once_with(
            self.mock_host, cache_disk_ids=["fake_cache_disk_id"]
        )

    def test_diskgroup_not_found(self):
        with patch("salt.utils.vmware.get_diskgroups", MagicMock(return_value=[])):
            with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                vsphere.remove_capacity_from_diskgroup(
                    cache_disk_id="fake_cache_disk_id",
                    capacity_disk_ids=["fake_disk1", "fake_disk2"],
                )
        self.assertEqual(
            "No diskgroup with cache disk id "
            "'fake_cache_disk_id' was found in ESXi host "
            "'fake_host'",
            excinfo.exception.strerror,
        )

    def test_remove_capacity_from_diskgroup(self):
        mock_remove_capacity_from_diskgroup = MagicMock()
        with patch(
            "salt.utils.vsan.remove_capacity_from_diskgroup",
            mock_remove_capacity_from_diskgroup,
        ):
            vsphere.remove_capacity_from_diskgroup(
                cache_disk_id="fake_cache_disk_id",
                capacity_disk_ids=["fake_disk1", "fake_disk2"],
            )
        mock_remove_capacity_from_diskgroup.assert_called_once_with(
            self.mock_si,
            self.mock_host,
            self.mock_diskgroup,
            capacity_disks=[self.mock_disk1, self.mock_disk2],
            data_evacuation=True,
        )

    def test_remove_capacity_from_diskgroup_data_evacuation_false(self):
        mock_remove_capacity_from_diskgroup = MagicMock()
        with patch(
            "salt.utils.vsan.remove_capacity_from_diskgroup",
            mock_remove_capacity_from_diskgroup,
        ):
            vsphere.remove_capacity_from_diskgroup(
                cache_disk_id="fake_cache_disk_id",
                capacity_disk_ids=["fake_disk1", "fake_disk2"],
                data_evacuation=False,
            )
        mock_remove_capacity_from_diskgroup.assert_called_once_with(
            self.mock_si,
            self.mock_host,
            self.mock_diskgroup,
            capacity_disks=[self.mock_disk1, self.mock_disk2],
            data_evacuation=False,
        )

    def test_success_output(self):
        res = vsphere.remove_capacity_from_diskgroup(
            cache_disk_id="fake_cache_disk_id",
            capacity_disk_ids=["fake_disk1", "fake_disk2"],
        )
        self.assertTrue(res)


@pytest.mark.skipif(not HAS_PYVMOMI, reason="The 'pyvmomi' library is missing")
class ListClusterTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for salt.modules.vsphere.list_cluster
    """

    def setup_loader_modules(self):
        return {vsphere: {"_get_proxy_connection_details": MagicMock(), "__salt__": {}}}

    def setUp(self):
        attrs = (
            ("mock_si", MagicMock()),
            ("mock_dc", MagicMock()),
            ("mock_cl", MagicMock()),
            ("mock__get_cluster_dict", MagicMock()),
        )
        for attr, mock_obj in attrs:
            setattr(self, attr, mock_obj)
            self.addCleanup(delattr, self, attr)
        attrs = (("mock_get_cluster", MagicMock(return_value=self.mock_cl)),)
        for attr, mock_obj in attrs:
            setattr(self, attr, mock_obj)
            self.addCleanup(delattr, self, attr)
        patches = (
            (
                "salt.utils.vmware.get_service_instance",
                MagicMock(return_value=self.mock_si),
            ),
            (
                "salt.modules.vsphere.get_proxy_type",
                MagicMock(return_value="esxcluster"),
            ),
            (
                "salt.modules.vsphere._get_proxy_target",
                MagicMock(return_value=self.mock_cl),
            ),
            ("salt.utils.vmware.get_cluster", self.mock_get_cluster),
            ("salt.modules.vsphere._get_cluster_dict", self.mock__get_cluster_dict),
        )
        for module, mock_obj in patches:
            patcher = patch(module, mock_obj)
            patcher.start()
            self.addCleanup(patcher.stop)
        # Patch __salt__ dunder
        patcher = patch.dict(
            vsphere.__salt__,
            {"esxcluster.get_details": MagicMock(return_value={"cluster": "cl"})},
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_supported_proxies(self):
        supported_proxies = ["esxcluster", "esxdatacenter"]
        for proxy_type in supported_proxies:
            with patch(
                "salt.modules.vsphere.get_proxy_type",
                MagicMock(return_value=proxy_type),
            ):
                vsphere.list_cluster(cluster="cl")

    def test_default_service_instance(self):
        mock__get_proxy_target = MagicMock()
        with patch("salt.modules.vsphere._get_proxy_target", mock__get_proxy_target):
            vsphere.list_cluster()
        mock__get_proxy_target.assert_called_once_with(self.mock_si)

    def test_defined_service_instance(self):
        mock_si = MagicMock()
        mock__get_proxy_target = MagicMock()
        with patch("salt.modules.vsphere._get_proxy_target", mock__get_proxy_target):
            vsphere.list_cluster(service_instance=mock_si)
        mock__get_proxy_target.assert_called_once_with(mock_si)

    def test_no_cluster_raises_argument_value_error(self):
        with patch(
            "salt.modules.vsphere.get_proxy_type",
            MagicMock(return_value="esxdatacenter"),
        ):
            with patch("salt.modules.vsphere._get_proxy_target", MagicMock()):
                with self.assertRaises(ArgumentValueError) as excinfo:
                    vsphere.list_cluster()
        self.assertEqual(excinfo.exception.strerror, "'cluster' needs to be specified")

    def test_get_cluster_call(self):
        with patch(
            "salt.modules.vsphere.get_proxy_type",
            MagicMock(return_value="esxdatacenter"),
        ):
            with patch(
                "salt.modules.vsphere._get_proxy_target",
                MagicMock(return_value=self.mock_dc),
            ):
                vsphere.list_cluster(cluster="cl")
        self.mock_get_cluster.assert_called_once_with(self.mock_dc, "cl")

    def test__get_cluster_dict_call(self):
        vsphere.list_cluster()
        self.mock__get_cluster_dict.assert_called_once_with("cl", self.mock_cl)


@pytest.mark.skipif(not HAS_PYVMOMI, reason="The 'pyvmomi' library is missing")
class RenameDatastoreTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for salt.modules.vsphere.rename_datastore
    """

    def setup_loader_modules(self):
        return {
            vsphere: {
                "_get_proxy_connection_details": MagicMock(),
                "get_proxy_type": MagicMock(return_value="esxdatacenter"),
            }
        }

    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_target = MagicMock()
        self.mock_ds_ref = MagicMock()
        self.mock_get_datastores = MagicMock(return_value=[self.mock_ds_ref])
        self.mock_rename_datastore = MagicMock()
        patches = (
            (
                "salt.utils.vmware.get_service_instance",
                MagicMock(return_value=self.mock_si),
            ),
            (
                "salt.modules.vsphere._get_proxy_target",
                MagicMock(return_value=self.mock_target),
            ),
            ("salt.utils.vmware.get_datastores", self.mock_get_datastores),
            ("salt.utils.vmware.rename_datastore", self.mock_rename_datastore),
        )
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in (
            "mock_si",
            "mock_target",
            "mock_ds_ref",
            "mock_get_datastores",
            "mock_rename_datastore",
        ):
            delattr(self, attr)

    def test_supported_proxes(self):
        supported_proxies = ["esxi", "esxcluster", "esxdatacenter"]
        for proxy_type in supported_proxies:
            with patch(
                "salt.modules.vsphere.get_proxy_type",
                MagicMock(return_value=proxy_type),
            ):
                vsphere.rename_datastore("current_ds_name", "new_ds_name")

    def test_default_service_instance(self):
        mock__get_proxy_target = MagicMock()
        with patch("salt.modules.vsphere._get_proxy_target", mock__get_proxy_target):
            vsphere.rename_datastore("current_ds_name", "new_ds_name")
        mock__get_proxy_target.assert_called_once_with(self.mock_si)

    def test_defined_service_instance(self):
        mock_si = MagicMock()
        mock__get_proxy_target = MagicMock()
        with patch("salt.modules.vsphere._get_proxy_target", mock__get_proxy_target):
            vsphere.rename_datastore(
                "current_ds_name", "new_ds_name", service_instance=mock_si
            )

        mock__get_proxy_target.assert_called_once_with(mock_si)

    def test_get_datastore_call(self):
        vsphere.rename_datastore("current_ds_name", "new_ds_name")
        self.mock_get_datastores.assert_called_once_with(
            self.mock_si, self.mock_target, datastore_names=["current_ds_name"]
        )

    def test_get_no_datastores(self):
        with patch("salt.utils.vmware.get_datastores", MagicMock(return_value=[])):
            with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                vsphere.rename_datastore("current_ds_name", "new_ds_name")
        self.assertEqual(
            excinfo.exception.strerror, "Datastore 'current_ds_name' was not found"
        )

    def test_rename_datastore_call(self):
        vsphere.rename_datastore("current_ds_name", "new_ds_name")
        self.mock_rename_datastore.assert_called_once_with(
            self.mock_ds_ref, "new_ds_name"
        )


class _GetProxyTargetTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for salt.modules.vsphere._get_proxy_target
    """

    def setup_loader_modules(self):
        return {
            vsphere: {
                "_get_proxy_connection_details": MagicMock(),
                "get_proxy_type": MagicMock(return_value="esxdatacenter"),
            }
        }

    def setUp(self):
        attrs = (
            ("mock_si", MagicMock()),
            ("mock_dc", MagicMock()),
            ("mock_cl", MagicMock()),
            ("mock_root", MagicMock()),
        )
        for attr, mock_obj in attrs:
            setattr(self, attr, mock_obj)
            self.addCleanup(delattr, self, attr)
        attrs = (
            ("mock_get_datacenter", MagicMock(return_value=self.mock_dc)),
            ("mock_get_cluster", MagicMock(return_value=self.mock_cl)),
            ("mock_get_root_folder", MagicMock(return_value=self.mock_root)),
        )
        for attr, mock_obj in attrs:
            setattr(self, attr, mock_obj)
            self.addCleanup(delattr, self, attr)
        patches = (
            (
                "salt.modules.vsphere.get_proxy_type",
                MagicMock(return_value="esxcluster"),
            ),
            (
                "salt.utils.vmware.is_connection_to_a_vcenter",
                MagicMock(return_value=True),
            ),
            (
                "salt.modules.vsphere._get_esxcluster_proxy_details",
                MagicMock(
                    return_value=(
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        "datacenter",
                        "cluster",
                    )
                ),
            ),
            (
                "salt.modules.vsphere._get_esxdatacenter_proxy_details",
                MagicMock(
                    return_value=(
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        "datacenter",
                    )
                ),
            ),
            ("salt.utils.vmware.get_datacenter", self.mock_get_datacenter),
            ("salt.utils.vmware.get_cluster", self.mock_get_cluster),
            ("salt.utils.vmware.get_root_folder", self.mock_get_root_folder),
        )
        for module, mock_obj in patches:
            patcher = patch(module, mock_obj)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_supported_proxies(self):
        supported_proxies = ["esxcluster", "esxdatacenter"]
        for proxy_type in supported_proxies:
            with patch(
                "salt.modules.vsphere.get_proxy_type",
                MagicMock(return_value=proxy_type),
            ):
                vsphere._get_proxy_target(self.mock_si)

    def test_connected_to_esxi(self):
        with patch(
            "salt.utils.vmware.is_connection_to_a_vcenter",
            MagicMock(return_value=False),
        ):
            with self.assertRaises(CommandExecutionError) as excinfo:
                vsphere._get_proxy_target(self.mock_si)
            self.assertEqual(
                excinfo.exception.strerror,
                "'_get_proxy_target' not supported when connected via the ESXi host",
            )

    def test_get_cluster_call(self):
        vsphere._get_proxy_target(self.mock_si)
        self.mock_get_datacenter.assert_called_once_with(self.mock_si, "datacenter")
        self.mock_get_cluster.assert_called_once_with(self.mock_dc, "cluster")

    def test_esxcluster_proxy_return(self):
        with patch(
            "salt.modules.vsphere.get_proxy_type", MagicMock(return_value="esxcluster")
        ):
            ret = vsphere._get_proxy_target(self.mock_si)
        self.assertEqual(ret, self.mock_cl)

    def test_get_datacenter_call(self):
        with patch(
            "salt.modules.vsphere.get_proxy_type",
            MagicMock(return_value="esxdatacenter"),
        ):
            vsphere._get_proxy_target(self.mock_si)
        self.mock_get_datacenter.assert_called_once_with(self.mock_si, "datacenter")
        self.assertEqual(self.mock_get_cluster.call_count, 0)

    def test_esxdatacenter_proxy_return(self):
        with patch(
            "salt.modules.vsphere.get_proxy_type",
            MagicMock(return_value="esxdatacenter"),
        ):
            ret = vsphere._get_proxy_target(self.mock_si)
        self.assertEqual(ret, self.mock_dc)

    def test_vcenter_proxy_return(self):
        with patch(
            "salt.modules.vsphere.get_proxy_type", MagicMock(return_value="vcenter")
        ):
            ret = vsphere._get_proxy_target(self.mock_si)
        self.mock_get_root_folder.assert_called_once_with(self.mock_si)
        self.assertEqual(ret, self.mock_root)


@pytest.mark.skipif(
    not HAS_VSPHERE_SDK, reason="The 'vsphere-automation-sdk' library is missing"
)
class TestVSphereTagging(TestCase, LoaderModuleMockMixin):
    """
    Tests for:
     - salt.modules.vsphere.create_tag_category
     - salt.modules.vsphere.create_tag
     - salt.modules.vsphere.delete_tag_category
     - salt.modules.vsphere.delete_tag
     - salt.modules.vsphere.list_tag_categories
     - salt.modules.vsphere.list_tags
     - salt.modules.vsphere.attach_tags
     - salt.modules.vsphere.list_attached_tags
    """

    def setup_loader_modules(self):
        return {
            vsphere: {
                "_get_proxy_connection_details": MagicMock(),
                "get_proxy_type": MagicMock(return_value="vcenter"),
            }
        }

    # Grains for expected __salt__ calls
    details = {key: None for key in ["vcenter", "username", "password"]}

    # Function attributes
    func_attrs = {
        key: None
        for key in [
            "category_id",
            "object_id",
            "tag_id",
            "name",
            "description",
            "cardinality",
        ]
    }

    # Expected returns
    create_tag_category = {
        "Category created": (
            "urn:vmomi:InventoryServiceTag:bb0350b4-85db-46b0-a726-e7c5989fc857:GLOBAL"
        )
    }

    create_tag = {
        "Tag created": (
            "urn:vmomi:InventoryServiceTag:bb0350b4-85db-46b0-a726-e7c5989fc857:GLOBAL"
        )
    }

    delete_tag_category = {
        "Category deleted": (
            "urn:vmomi:InventoryServiceTag:bb0350b4-85db-46b0-a726-e7c5989fc857:GLOBAL"
        )
    }

    delete_tag = {
        "Tag deleted": (
            "urn:vmomi:InventoryServiceTag:bb0350b4-85db-46b0-a726-e7c5989fc857:GLOBAL"
        )
    }

    list_tag_categories_return = [
        "urn:vmomi:InventoryServiceCategory:"
        "b13f4959-a3f3-48d0-8080-15bb586b4355:GLOBAL",
        "urn:vmomi:InventoryServiceCategory:"
        "f4d41f02-c317-422d-9013-dcbebfcd54ad:GLOBAL",
        "urn:vmomi:InventoryServiceCategory:"
        "2db5b00b-f211-4bba-ba42-e2658ebbb283:GLOBAL",
        "urn:vmomi:InventoryServiceCategory:"
        "cd847c3c-687c-4bd9-8e5a-0eb536f0a01d:GLOBAL",
        "urn:vmomi:InventoryServiceCategory:"
        "d51c24f9-cffb-4ce0-af56-7f18b6e649af:GLOBAL",
    ]

    list_tags_return = [
        "urn:vmomi:InventoryServiceTag:a584a83b-3015-45ad-8057-a3630613052f:GLOBAL",
        "urn:vmomi:InventoryServiceTag:db08019c-15de-4bbf-be46-d81aaf8d25c0:GLOBAL",
        "urn:vmomi:InventoryServiceTag:b55ecc77-f4a5-49f8-ab52-38865467cfbe:GLOBAL",
        "urn:vmomi:InventoryServiceTag:f009ab1b-e1b5-4c40-b8f7-951d9d716b39:GLOBAL",
        "urn:vmomi:InventoryServiceTag:102bb4c5-9b76-4d6c-882a-76a91ee3edcc:GLOBAL",
        "urn:vmomi:InventoryServiceTag:bb0350b4-85db-46b0-a726-e7c5989fc857:GLOBAL",
        "urn:vmomi:InventoryServiceTag:71d30f2d-bb23-48e1-995f-630adfb0dc89:GLOBAL",
    ]

    list_attached_tags_return = [
        "urn:vmomi:InventoryServiceTag:b55ecc77-f4a5-49f8-ab52-38865467cfbe:GLOBAL",
        "urn:vmomi:InventoryServiceTag:bb0350b4-85db-46b0-a726-e7c5989fc857:GLOBAL",
    ]

    list_create_category_return = [
        "urn:vmomi:InventoryServiceCategory:0af54c2d-e8cd-4248-931e-2f5807d8c477:GLOBAL"
    ]

    list_create_tag_return = [
        "urn:vmomi:InventoryServiceCategory:0af54c2d-e8cd-4248-931e-2f5807d8c477:GLOBAL"
    ]

    attach_tags_return = {
        "Tag attached": (
            "urn:vmomi:InventoryServiceTag:bb0350b4-85db-46b0-a726-e7c5989fc857:GLOBAL"
        )
    }

    def test_create_tag_category_client_none(self):
        get_details = MagicMock(return_value=self.details)

        # Start patching each external API return with Mock Objects
        with patch.object(
            vsphere, "get_proxy_type", return_value="vcenter"
        ) as get_proxy_type:
            with patch.object(
                vsphere, "_get_proxy_connection_details", return_value=[]
            ) as get_proxy_connection:
                with patch.object(
                    salt.utils.vmware, "get_service_instance", return_value=None
                ) as get_service_instance:
                    with patch.dict(
                        vsphere.__salt__,
                        {"vcenter.get_details": get_details},
                        clear=True,
                    ) as get_vcenter_details:
                        with patch.object(
                            salt.utils.vmware, "get_vsphere_client", return_value=None
                        ) as get_vsphere_client:
                            ret = vsphere.create_tag_category(
                                self.func_attrs["name"],
                                self.func_attrs["description"],
                                self.func_attrs["cardinality"],
                            )
                            # Check function calls and return data
                            get_proxy_type.assert_called_once()
                            get_proxy_connection.assert_called_once()
                            get_service_instance.assert_called_once()
                            get_vsphere_client.assert_called_once()
                            self.assertEqual(ret, {"Category created": None})

    def test_create_tag_category_client(self):
        for verify_ssl in [True, False, None]:
            details = self.details.copy()
            if verify_ssl is None:
                verify_ssl = True
            else:
                details["verify_ssl"] = verify_ssl
            get_details = MagicMock(return_value=details)

            #  Mock CreateSpec object and create objects
            mock_client = Mock(
                tagging=Mock(
                    Category=Mock(
                        CreateSpec=Mock(return_value=Mock()),
                        create=Mock(
                            return_value=self.create_tag_category["Category created"]
                        ),
                    )
                )
            )

            # Start patching each external API return with Mock Objects
            with patch.object(
                vsphere, "get_proxy_type", return_value="vcenter"
            ) as get_proxy_type:
                with patch.object(
                    vsphere, "_get_proxy_connection_details", return_value=[]
                ) as get_proxy_connection:
                    with patch.object(
                        salt.utils.vmware, "get_service_instance", return_value=None
                    ) as get_service_instance:
                        with patch.dict(
                            vsphere.__salt__,
                            {"vcenter.get_details": get_details},
                            clear=True,
                        ) as get_vcenter_details:
                            with patch.object(
                                salt.utils.vmware,
                                "get_vsphere_client",
                                return_value=mock_client,
                            ) as get_vsphere_client:
                                ret = vsphere.create_tag_category(
                                    self.func_attrs["name"],
                                    self.func_attrs["description"],
                                    self.func_attrs["cardinality"],
                                )

                                # Check function calls and return data
                                get_proxy_type.assert_called_once()
                                get_proxy_connection.assert_called_once()
                                get_service_instance.assert_called_once()
                                get_vsphere_client.assert_called_once()
                                self.assertEqual(ret, self.create_tag_category)
                                self.assertEqual(
                                    get_vsphere_client.call_args_list,
                                    [
                                        call(
                                            ca_bundle=None,
                                            password=None,
                                            server=None,
                                            username=None,
                                            verify_ssl=verify_ssl,
                                        )
                                    ],
                                )

    def test_create_tag_client_none(self):
        get_details = MagicMock(return_value=self.details)

        # Start patching each external API return with Mock Objects
        with patch.object(
            vsphere, "get_proxy_type", return_value="vcenter"
        ) as get_proxy_type:
            with patch.object(
                vsphere, "_get_proxy_connection_details", return_value=[]
            ) as get_proxy_connection:
                with patch.object(
                    salt.utils.vmware, "get_service_instance", return_value=None
                ) as get_service_instance:
                    with patch.dict(
                        vsphere.__salt__,
                        {"vcenter.get_details": get_details},
                        clear=True,
                    ) as get_vcenter_details:
                        with patch.object(
                            salt.utils.vmware, "get_vsphere_client", return_value=None
                        ) as get_vsphere_client:
                            ret = vsphere.create_tag(
                                self.func_attrs["name"],
                                self.func_attrs["description"],
                                self.func_attrs["cardinality"],
                            )
                            # Check function calls and return data
                            get_proxy_type.assert_called_once()
                            get_proxy_connection.assert_called_once()
                            get_service_instance.assert_called_once()
                            get_vsphere_client.assert_called_once()
                            self.assertEqual(ret, {"Tag created": None})

    def test_create_tag_client(self):
        get_details = MagicMock(return_value=self.details)

        #  Mock CreateSpec object and create objects
        mock_client = Mock(
            tagging=Mock(
                Tag=Mock(
                    CreateSpec=Mock(return_value=Mock()),
                    create=Mock(return_value=self.create_tag["Tag created"]),
                )
            )
        )

        # Start patching each external API return with Mock Objects
        with patch.object(
            vsphere, "get_proxy_type", return_value="vcenter"
        ) as get_proxy_type:
            with patch.object(
                vsphere, "_get_proxy_connection_details", return_value=[]
            ) as get_proxy_connection:
                with patch.object(
                    salt.utils.vmware, "get_service_instance", return_value=None
                ) as get_service_instance:
                    with patch.dict(
                        vsphere.__salt__,
                        {"vcenter.get_details": get_details},
                        clear=True,
                    ) as get_vcenter_details:
                        with patch.object(
                            salt.utils.vmware,
                            "get_vsphere_client",
                            return_value=mock_client,
                        ) as get_vsphere_client:
                            ret = vsphere.create_tag(
                                self.func_attrs["name"],
                                self.func_attrs["description"],
                                self.func_attrs["cardinality"],
                            )
                            # Check function calls and return data
                            get_proxy_type.assert_called_once()
                            get_proxy_connection.assert_called_once()
                            get_service_instance.assert_called_once()
                            get_vsphere_client.assert_called_once()
                            self.assertEqual(ret, self.create_tag)

    def test_delete_tag_category_client_none(self):
        get_details = MagicMock(return_value=self.details)

        # Start patching each external API return with Mock Objects
        with patch.object(
            vsphere, "get_proxy_type", return_value="vcenter"
        ) as get_proxy_type:
            with patch.object(
                vsphere, "_get_proxy_connection_details", return_value=[]
            ) as get_proxy_connection:
                with patch.object(
                    salt.utils.vmware, "get_service_instance", return_value=None
                ) as get_service_instance:
                    with patch.dict(
                        vsphere.__salt__,
                        {"vcenter.get_details": get_details},
                        clear=True,
                    ) as get_vcenter_details:
                        with patch.object(
                            salt.utils.vmware, "get_vsphere_client", return_value=None
                        ) as get_vsphere_client:
                            ret = vsphere.delete_tag_category(
                                self.func_attrs["category_id"]
                            )
                            # Check function calls and return data
                            get_proxy_type.assert_called_once()
                            get_proxy_connection.assert_called_once()
                            get_service_instance.assert_called_once()
                            get_vsphere_client.assert_called_once()
                            self.assertEqual(ret, {"Category deleted": None})

    def test_delete_tag_category_client(self):
        for verify_ssl in [True, False, None]:
            details = self.details.copy()
            if verify_ssl is None:
                verify_ssl = True
            else:
                details["verify_ssl"] = verify_ssl
            get_details = MagicMock(return_value=details)

            #  Mock CreateSpec object and create objects
            mock_client = Mock(
                tagging=Mock(
                    Category=Mock(
                        delete=Mock(
                            return_value=self.delete_tag_category["Category deleted"]
                        )
                    )
                )
            )

            # Start patching each external API return with Mock Objects
            with patch.object(
                vsphere, "get_proxy_type", return_value="vcenter"
            ) as get_proxy_type:
                with patch.object(
                    vsphere, "_get_proxy_connection_details", return_value=[]
                ) as get_proxy_connection:
                    with patch.object(
                        salt.utils.vmware, "get_service_instance", return_value=None
                    ) as get_service_instance:
                        with patch.dict(
                            vsphere.__salt__,
                            {"vcenter.get_details": get_details},
                            clear=True,
                        ) as get_vcenter_details:
                            with patch.object(
                                salt.utils.vmware,
                                "get_vsphere_client",
                                return_value=mock_client,
                            ) as get_vsphere_client:
                                ret = vsphere.delete_tag_category(
                                    self.func_attrs["category_id"]
                                )

                                # Check function calls and return data
                                get_proxy_type.assert_called_once()
                                get_proxy_connection.assert_called_once()
                                get_service_instance.assert_called_once()
                                get_vsphere_client.assert_called_once()
                                self.assertEqual(ret, self.delete_tag_category)
                                self.assertEqual(
                                    get_vsphere_client.call_args_list,
                                    [
                                        call(
                                            ca_bundle=None,
                                            password=None,
                                            server=None,
                                            username=None,
                                            verify_ssl=verify_ssl,
                                        )
                                    ],
                                )

    def test_delete_tag_client_none(self):
        get_details = MagicMock(return_value=self.details)

        # Start patching each external API return with Mock Objects
        with patch.object(
            vsphere, "get_proxy_type", return_value="vcenter"
        ) as get_proxy_type:
            with patch.object(
                vsphere, "_get_proxy_connection_details", return_value=[]
            ) as get_proxy_connection:
                with patch.object(
                    salt.utils.vmware, "get_service_instance", return_value=None
                ) as get_service_instance:
                    with patch.dict(
                        vsphere.__salt__,
                        {"vcenter.get_details": get_details},
                        clear=True,
                    ) as get_vcenter_details:
                        with patch.object(
                            salt.utils.vmware, "get_vsphere_client", return_value=None
                        ) as get_vsphere_client:
                            ret = vsphere.delete_tag(self.func_attrs["tag_id"])
                            # Check function calls and return data
                            get_proxy_type.assert_called_once()
                            get_proxy_connection.assert_called_once()
                            get_service_instance.assert_called_once()
                            get_vsphere_client.assert_called_once()
                            self.assertEqual(ret, {"Tag deleted": None})

    def test_delete_tag_client(self):
        get_details = MagicMock(return_value=self.details)

        #  Mock CreateSpec object and create objects
        mock_client = Mock(
            tagging=Mock(
                Tag=Mock(delete=Mock(return_value=self.delete_tag["Tag deleted"]))
            )
        )

        # Start patching each external API return with Mock Objects
        with patch.object(
            vsphere, "get_proxy_type", return_value="vcenter"
        ) as get_proxy_type:
            with patch.object(
                vsphere, "_get_proxy_connection_details", return_value=[]
            ) as get_proxy_connection:
                with patch.object(
                    salt.utils.vmware, "get_service_instance", return_value=None
                ) as get_service_instance:
                    with patch.dict(
                        vsphere.__salt__,
                        {"vcenter.get_details": get_details},
                        clear=True,
                    ) as get_vcenter_details:
                        with patch.object(
                            salt.utils.vmware,
                            "get_vsphere_client",
                            return_value=mock_client,
                        ) as get_vsphere_client:
                            ret = vsphere.delete_tag(self.func_attrs["tag_id"])

                            # Check function calls and return data
                            get_proxy_type.assert_called_once()
                            get_proxy_connection.assert_called_once()
                            get_service_instance.assert_called_once()
                            get_vsphere_client.assert_called_once()
                            self.assertEqual(ret, self.delete_tag)

    def test_list_tag_categories_client_none(self):
        get_details = MagicMock(return_value=self.details)

        # Start patching each external API return with Mock Objects
        with patch.object(
            vsphere, "get_proxy_type", return_value="vcenter"
        ) as get_proxy_type:
            with patch.object(
                vsphere, "_get_proxy_connection_details", return_value=[]
            ) as get_proxy_connection:
                with patch.object(
                    salt.utils.vmware, "get_service_instance", return_value=None
                ) as get_service_instance:
                    with patch.dict(
                        vsphere.__salt__,
                        {"vcenter.get_details": get_details},
                        clear=True,
                    ) as get_vcenter_details:
                        with patch.object(
                            salt.utils.vmware, "get_vsphere_client", return_value=None
                        ) as get_vsphere_client:
                            ret = vsphere.list_tag_categories()
                            # Check function calls and return data
                            get_proxy_type.assert_called_once()
                            get_proxy_connection.assert_called_once()
                            get_service_instance.assert_called_once()
                            get_vsphere_client.assert_called_once()
                            self.assertEqual(ret, {"Categories": None})

    def test_list_tag_categories_client(self):
        for verify_ssl in [True, False, None]:
            details = self.details.copy()
            if verify_ssl is not None:
                details["verify_ssl"] = verify_ssl
            else:
                verify_ssl = True
            get_details = MagicMock(return_value=details)

            #  Mock CreateSpec object and create objects
            mock_client = Mock(
                tagging=Mock(
                    Category=Mock(
                        list=Mock(return_value=self.list_tag_categories_return)
                    )
                )
            )

            # Start patching each external API return with Mock Objects
            with patch.object(
                vsphere, "get_proxy_type", return_value="vcenter"
            ) as get_proxy_type:
                with patch.object(
                    vsphere, "_get_proxy_connection_details", return_value=[]
                ) as get_proxy_connection:
                    with patch.object(
                        salt.utils.vmware, "get_service_instance", return_value=None
                    ) as get_service_instance:
                        with patch.dict(
                            vsphere.__salt__,
                            {"vcenter.get_details": get_details},
                            clear=True,
                        ) as get_vcenter_details:
                            with patch.object(
                                salt.utils.vmware,
                                "get_vsphere_client",
                                return_value=mock_client,
                            ) as get_vsphere_client:
                                ret = vsphere.list_tag_categories()

                                get_proxy_type.assert_called_once()
                                get_proxy_connection.assert_called_once()
                                get_service_instance.assert_called_once()
                                get_vsphere_client.assert_called_once()
                                self.assertEqual(
                                    get_vsphere_client.call_args_list,
                                    [
                                        call(
                                            ca_bundle=None,
                                            password=None,
                                            server=None,
                                            username=None,
                                            verify_ssl=verify_ssl,
                                        )
                                    ],
                                )
                                self.assertEqual(
                                    ret, {"Categories": self.list_tag_categories_return}
                                )

    def test_list_tags_client_none(self):
        get_details = MagicMock(return_value=self.details)

        # Start patching each external API return with Mock Objects
        with patch.object(
            vsphere, "get_proxy_type", return_value="vcenter"
        ) as get_proxy_type:
            with patch.object(
                vsphere, "_get_proxy_connection_details", return_value=[]
            ) as get_proxy_connection:
                with patch.object(
                    salt.utils.vmware, "get_service_instance", return_value=None
                ) as get_service_instance:
                    with patch.dict(
                        vsphere.__salt__,
                        {"vcenter.get_details": get_details},
                        clear=True,
                    ) as get_vcenter_details:
                        with patch.object(
                            salt.utils.vmware, "get_vsphere_client", return_value=None
                        ) as get_vsphere_client:
                            # Check function calls and return
                            ret = vsphere.list_tags()
                            get_proxy_type.assert_called_once()
                            get_proxy_connection.assert_called_once()
                            get_service_instance.assert_called_once()
                            get_vsphere_client.assert_called_once()
                            self.assertEqual(ret, {"Tags": None})

    def test_list_tags_client(self):
        get_details = MagicMock(return_value=self.details)

        #  Mock CreateSpec object and create objects
        mock_client = Mock(
            tagging=Mock(Tag=Mock(list=Mock(return_value=self.list_tags_return)))
        )

        # Start patching each external API return with Mock Objects
        with patch.object(
            vsphere, "get_proxy_type", return_value="vcenter"
        ) as get_proxy_type:
            with patch.object(
                vsphere, "_get_proxy_connection_details", return_value=[]
            ) as get_proxy_connection:
                with patch.object(
                    salt.utils.vmware, "get_service_instance", return_value=None
                ) as get_service_instance:
                    with patch.dict(
                        vsphere.__salt__,
                        {"vcenter.get_details": get_details},
                        clear=True,
                    ) as get_vcenter_details:
                        with patch.object(
                            salt.utils.vmware,
                            "get_vsphere_client",
                            return_value=mock_client,
                        ) as get_vsphere_client:
                            # Check function calls and return
                            ret = vsphere.list_tags()
                            get_proxy_type.assert_called_once()
                            get_proxy_connection.assert_called_once()
                            get_service_instance.assert_called_once()
                            get_vsphere_client.assert_called_once()
                            self.assertEqual(ret, {"Tags": self.list_tags_return})

    def test_list_tags_client_verify_ssl(self):
        for verify_ssl in [True, False]:
            details = self.details.copy()
            if verify_ssl is not None:
                details["verify_ssl"] = verify_ssl
            else:
                verify_ssl = True
            get_details = MagicMock(return_value=details)

            #  Mock CreateSpec object and create objects
            mock_client = Mock(
                tagging=Mock(Tag=Mock(list=Mock(return_value=self.list_tags_return)))
            )

            # Start patching each external API return with Mock Objects
            with patch.object(
                vsphere, "get_proxy_type", return_value="vcenter"
            ) as get_proxy_type:
                with patch.object(
                    vsphere, "_get_proxy_connection_details", return_value=[]
                ) as get_proxy_connection:
                    with patch.object(
                        salt.utils.vmware, "get_service_instance", return_value=None
                    ) as get_service_instance:
                        with patch.dict(
                            vsphere.__salt__,
                            {"vcenter.get_details": get_details},
                            clear=True,
                        ) as get_vcenter_details:
                            with patch.object(
                                salt.utils.vmware,
                                "get_vsphere_client",
                                return_value=mock_client,
                            ) as get_vsphere_client:
                                # Check function calls and return
                                ret = vsphere.list_tags()
                                self.assertEqual(ret, {"Tags": self.list_tags_return})
                                self.assertEqual(
                                    get_vsphere_client.call_args_list,
                                    [
                                        call(
                                            ca_bundle=None,
                                            password=None,
                                            server=None,
                                            username=None,
                                            verify_ssl=verify_ssl,
                                        )
                                    ],
                                )

    def test_list_attached_tags_client_none(self):
        get_details = MagicMock(return_value=self.details)

        # Start patching each external API return with Mock Objects
        with patch.object(
            vsphere, "get_proxy_type", return_value="vcenter"
        ) as get_proxy_type:
            with patch.object(
                vsphere, "_get_proxy_connection_details", return_value=[]
            ) as get_proxy_connection:
                with patch.object(
                    salt.utils.vmware, "get_service_instance", return_value=None
                ) as get_service_instance:
                    with patch.dict(
                        vsphere.__salt__,
                        {"vcenter.get_details": get_details},
                        clear=True,
                    ) as get_vcenter_details:
                        with patch.object(
                            salt.utils.vmware, "get_vsphere_client", return_value=None
                        ) as get_vsphere_client:
                            with patch.object(vsphere, "DynamicID") as dynamic_id:
                                # Check function calls and return
                                ret = vsphere.list_attached_tags("object_id")
                                get_proxy_type.assert_called_once()
                                get_proxy_connection.assert_called_once()
                                get_service_instance.assert_called_once()
                                get_vsphere_client.assert_called_once()
                                self.assertEqual(ret, {"Attached tags": None})

    def test_list_attached_tags_client(self):
        for verify_ssl in [True, False, None]:
            details = self.details.copy()
            if verify_ssl is None:
                verify_ssl = True
            else:
                details["verify_ssl"] = verify_ssl
            get_details = MagicMock(return_value=details)

            #  Mock CreateSpec object and create objects
            mock_client = Mock(
                tagging=Mock(
                    TagAssociation=Mock(
                        list_attached_tags=Mock(
                            return_value=self.list_attached_tags_return
                        )
                    )
                )
            )

            # Start patching each external API return with Mock Objects
            with patch.object(
                vsphere, "get_proxy_type", return_value="vcenter"
            ) as get_proxy_type:
                with patch.object(
                    vsphere, "_get_proxy_connection_details", return_value=[]
                ) as get_proxy_connection:
                    with patch.object(
                        salt.utils.vmware, "get_service_instance", return_value=None
                    ) as get_service_instance:
                        with patch.dict(
                            vsphere.__salt__,
                            {"vcenter.get_details": get_details},
                            clear=True,
                        ) as get_vcenter_details:
                            with patch.object(
                                salt.utils.vmware,
                                "get_vsphere_client",
                                return_value=mock_client,
                            ) as get_vsphere_client:
                                with patch.object(vsphere, "DynamicID") as dynamic_id:
                                    # Check function calls and return
                                    ret = vsphere.list_attached_tags(
                                        self.func_attrs["object_id"]
                                    )
                                    get_proxy_type.assert_called_once()
                                    get_proxy_connection.assert_called_once()
                                    get_service_instance.assert_called_once()
                                    get_vsphere_client.assert_called_once()
                                    self.assertEqual(
                                        ret,
                                        {
                                            "Attached tags": self.list_attached_tags_return
                                        },
                                    )
                                    self.assertEqual(
                                        get_vsphere_client.call_args_list,
                                        [
                                            call(
                                                ca_bundle=None,
                                                password=None,
                                                server=None,
                                                username=None,
                                                verify_ssl=verify_ssl,
                                            )
                                        ],
                                    )

    def test_attach_tags_client_none(self):
        get_details = MagicMock(return_value=self.details)

        # Start patching each external API return with Mock Objects
        with patch.object(
            vsphere, "get_proxy_type", return_value="vcenter"
        ) as get_proxy_type:
            with patch.object(
                vsphere, "_get_proxy_connection_details", return_value=[]
            ) as get_proxy_connection:
                with patch.object(
                    salt.utils.vmware, "get_service_instance", return_value=None
                ) as get_service_instance:
                    with patch.dict(
                        vsphere.__salt__,
                        {"vcenter.get_details": get_details},
                        clear=True,
                    ) as get_vcenter_details:
                        with patch.object(
                            salt.utils.vmware, "get_vsphere_client", return_value=None
                        ) as get_vsphere_client:
                            # Check function calls and return
                            ret = vsphere.attach_tag(
                                object_id=self.func_attrs["object_id"],
                                tag_id=self.func_attrs["tag_id"],
                            )
                            get_proxy_type.assert_called_once()
                            get_proxy_connection.assert_called_once()
                            get_service_instance.assert_called_once()
                            get_vsphere_client.assert_called_once()
                            self.assertEqual(ret, {"Tag attached": None})

    def test_attach_tags_client(self):
        for verify_ssl in [True, False, None]:
            details = self.details.copy()
            if verify_ssl is None:
                verify_ssl = True
            else:
                details["verify_ssl"] = verify_ssl
            get_details = MagicMock(return_value=details)

            #  Mock CreateSpec object and create objects
            mock_client = Mock(
                tagging=Mock(
                    TagAssociation=Mock(
                        attach=Mock(return_value=self.list_attached_tags_return)
                    )
                )
            )

            # Start patching each external API return with Mock Objects
            with patch.object(
                vsphere, "get_proxy_type", return_value="vcenter"
            ) as get_proxy_type:
                with patch.object(
                    vsphere, "_get_proxy_connection_details", return_value=[]
                ) as get_proxy_connection:
                    with patch.object(
                        salt.utils.vmware, "get_service_instance", return_value=None
                    ) as get_service_instance:
                        with patch.dict(
                            vsphere.__salt__,
                            {"vcenter.get_details": get_details},
                            clear=True,
                        ) as get_vcenter_details:
                            with patch.object(
                                salt.utils.vmware,
                                "get_vsphere_client",
                                return_value=mock_client,
                            ) as get_vsphere_client:
                                with patch.object(vsphere, "DynamicID") as dynamic_id:
                                    # Check function calls and return
                                    ret = vsphere.attach_tag(
                                        object_id=self.func_attrs["object_id"],
                                        tag_id=self.func_attrs["tag_id"],
                                    )
                                    get_proxy_type.assert_called_once()
                                    get_proxy_connection.assert_called_once()
                                    get_service_instance.assert_called_once()
                                    get_vsphere_client.assert_called_once()
                                    self.assertEqual(
                                        get_vsphere_client.call_args_list,
                                        [
                                            call(
                                                ca_bundle=None,
                                                password=None,
                                                server=None,
                                                username=None,
                                                verify_ssl=verify_ssl,
                                            )
                                        ],
                                    )
                                    self.assertEqual(
                                        ret,
                                        {
                                            "Tag attached": self.list_attached_tags_return
                                        },
                                    )

    def test_get_client(self):
        """
        test get_client when verify_ssl and ca_bundle are not passed
        """
        mock_client = MagicMock(return_value=None)
        patch_client = patch("salt.utils.vmware.get_vsphere_client", mock_client)

        cert_path = "/test/ca-certificates.crt"
        mock_ca = MagicMock(return_value=cert_path)
        patch_ca = patch("salt.utils.http.get_ca_bundle", mock_ca)

        mock_details = MagicMock(return_value=self.details)
        patch_details = patch.dict(
            vsphere.__salt__, {"vcenter.get_details": mock_details}
        )

        with patch_client, patch_ca, patch_details:
            vsphere._get_client(
                server="localhost", username="testuser", password="testpassword"
            )
            self.assertEqual(
                mock_client.call_args_list,
                [
                    call(
                        ca_bundle=None,
                        password="testpassword",
                        server="localhost",
                        username="testuser",
                        verify_ssl=True,
                    )
                ],
            )
            self.assertEqual(mock_details.assert_called_once(), None)
            self.assertEqual(mock_ca.assert_not_called(), None)

    def test_get_client_verify_ssl_false(self):
        """
        test get_client when verify_ssl=False is set
        """
        details = self.details.copy()
        details["verify_ssl"] = False
        mock_client = MagicMock(return_value=None)
        patch_client = patch("salt.utils.vmware.get_vsphere_client", mock_client)

        cert_path = "/test/ca-certificates.crt"
        mock_ca = MagicMock(return_value=cert_path)
        patch_ca = patch("salt.utils.http.get_ca_bundle", mock_ca)

        mock_details = MagicMock(return_value=details)
        patch_details = patch.dict(
            vsphere.__salt__, {"vcenter.get_details": mock_details}
        )

        with patch_client, patch_ca, patch_details:
            vsphere._get_client(
                server="localhost", username="testuser", password="testpassword"
            )
            self.assertEqual(
                mock_client.call_args_list,
                [
                    call(
                        ca_bundle=None,
                        password="testpassword",
                        server="localhost",
                        username="testuser",
                        verify_ssl=False,
                    )
                ],
            )
            self.assertEqual(mock_details.assert_called_once(), None)
            self.assertEqual(mock_ca.assert_not_called(), None)

    def test_get_client_verify_ssl_false_ca_bundle(self):
        """
        test get_client when verify_ssl=False and ca_bundle set
        """
        details = self.details.copy()
        details["verify_ssl"] = False
        details["ca_bundle"] = "/tmp/test"
        mock_client = MagicMock(return_value=None)
        patch_client = patch("salt.utils.vmware.get_vsphere_client", mock_client)

        cert_path = "/test/ca-certificates.crt"
        mock_ca = MagicMock(return_value=cert_path)
        patch_ca = patch("salt.utils.http.get_ca_bundle", mock_ca)

        mock_details = MagicMock(return_value=details)
        patch_details = patch.dict(
            vsphere.__salt__, {"vcenter.get_details": mock_details}
        )

        with patch_client, patch_ca, patch_details:
            self.assertFalse(
                vsphere._get_client(
                    server="localhost", username="testuser", password="testpassword"
                )
            )
            self.assertEqual(mock_details.assert_called_once(), None)
            self.assertEqual(mock_ca.assert_not_called(), None)

    def test_get_client_ca_bundle(self):
        """
        test get_client when verify_ssl=False and ca_bundle set
        """
        cert_path = "/test/ca-certificates.crt"
        details = self.details.copy()
        details["ca_bundle"] = cert_path
        mock_client = MagicMock(return_value=None)
        patch_client = patch("salt.utils.vmware.get_vsphere_client", mock_client)

        mock_ca = MagicMock(return_value=cert_path)
        patch_ca = patch("salt.utils.http.get_ca_bundle", mock_ca)

        mock_details = MagicMock(return_value=details)
        patch_details = patch.dict(
            vsphere.__salt__, {"vcenter.get_details": mock_details}
        )

        with patch_client, patch_ca, patch_details:
            vsphere._get_client(
                server="localhost", username="testuser", password="testpassword"
            )
            self.assertEqual(
                mock_client.call_args_list,
                [
                    call(
                        ca_bundle=cert_path,
                        password="testpassword",
                        server="localhost",
                        username="testuser",
                        verify_ssl=True,
                    )
                ],
            )
            self.assertEqual(mock_details.assert_called_once(), None)
            self.assertEqual(mock_ca.assert_called_once(), None)
            self.assertEqual(mock_ca.call_args_list, [call({"ca_bundle": cert_path})])


class TestCertificateVerify(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {vsphere: {}}

    def test_upload_ssh_key(self):
        kwargs_values = [
            ("ssh_key", "TheSSHKeyFile"),
            ("ssh_key_file", "TheSSHKeyFile"),
        ]
        certificate_verify_values = (None, True, False)
        for kw_key, kw_value in kwargs_values:
            kwargs = {kw_key: kw_value}
            if kw_key == "ssh_key":
                expected_kwargs = {"data": kw_value}
            else:
                expected_kwargs = {"data_file": kw_value, "data_render": False}
            for certificate_verify_value in certificate_verify_values:
                http_query_mock = MagicMock()
                if certificate_verify_value is None:
                    certificate_verify_value = True
                with patch("salt.utils.http.query", http_query_mock):
                    vsphere.upload_ssh_key(
                        HOST,
                        USER,
                        PASSWORD,
                        certificate_verify=certificate_verify_value,
                        **kwargs
                    )
                http_query_mock.assert_called_once_with(
                    "https://1.2.3.4:443/host/ssh_root_authorized_keys",
                    method="PUT",
                    password="SuperSecret!",
                    status=True,
                    text=True,
                    username="root",
                    verify_ssl=certificate_verify_value,
                    **expected_kwargs
                )

    def test_get_ssh_key(self):
        certificate_verify_values = (None, True, False)
        for certificate_verify_value in certificate_verify_values:
            http_query_mock = MagicMock()
            if certificate_verify_value is None:
                certificate_verify_value = True
            with patch("salt.utils.http.query", http_query_mock):
                vsphere.get_ssh_key(
                    HOST, USER, PASSWORD, certificate_verify=certificate_verify_value
                )
            http_query_mock.assert_called_once_with(
                "https://1.2.3.4:443/host/ssh_root_authorized_keys",
                method="GET",
                password="SuperSecret!",
                status=True,
                text=True,
                username="root",
                verify_ssl=certificate_verify_value,
            )
