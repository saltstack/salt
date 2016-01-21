# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Libs
from salt.modules import vsphere
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Globals
HOST = '1.2.3.4'
USER = 'root'
PASSWORD = 'SuperSecret!'
ERROR = 'Some Testing Error Message'


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.modules.vsphere.__virtual__', MagicMock(return_value='vsphere'))
class VsphereTestCase(TestCase):
    '''
    Unit TestCase for the salt.modules.vsphere module.
    '''

    # Tests for get_coredump_network_config function

    def test_get_coredump_network_config_esxi_hosts_not_list(self):
        '''
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list.
        '''
        self.assertRaises(CommandExecutionError,
                          vsphere.get_coredump_network_config,
                          HOST, USER, PASSWORD, esxi_hosts='foo')

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 1, 'stdout': ERROR}))
    def test_get_coredump_network_config_host_list_bad_retcode(self):
        '''
        Tests error message returned with list of esxi_hosts.
        '''
        host_1 = 'host_1.foo.com'
        self.assertEqual({host_1: {'Error': ERROR}},
                         vsphere.get_coredump_network_config(HOST, USER, PASSWORD, esxi_hosts=[host_1]))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 0, 'stdout': ''}))
    @patch('salt.modules.vsphere._format_coredump_stdout', MagicMock(return_value={}))
    def test_get_coredump_network_config_host_list_success(self):
        '''
        Tests successful function return when an esxi_host is provided.
        '''
        host_1 = 'host_1.foo.com'
        self.assertEqual({host_1: {'Coredump Config': {}}},
                         vsphere.get_coredump_network_config(HOST, USER, PASSWORD, esxi_hosts=[host_1]))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 1, 'stdout': ERROR}))
    def test_get_coredump_network_config_bad_retcode(self):
        '''
        Tests error message given for a single ESXi host.
        '''
        self.assertEqual({HOST: {'Error': ERROR}},
                         vsphere.get_coredump_network_config(HOST, USER, PASSWORD))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 0, 'stdout': ''}))
    @patch('salt.modules.vsphere._format_coredump_stdout', MagicMock(return_value={}))
    def test_get_coredump_network_config_success(self):
        '''
        Tests successful function return for a single ESXi host.
        '''
        self.assertEqual({HOST: {'Coredump Config': {}}},
                         vsphere.get_coredump_network_config(HOST, USER, PASSWORD))

    # Tests for coredump_network_enable function

    def test_coredump_network_enable_esxi_hosts_not_list(self):
        '''
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list.
        '''
        self.assertRaises(CommandExecutionError,
                          vsphere.coredump_network_enable,
                          HOST, USER, PASSWORD, True, esxi_hosts='foo')

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 1, 'stdout': ERROR}))
    def test_coredump_network_enable_host_list_bad_retcode(self):
        '''
        Tests error message returned with list of esxi_hosts.
        '''
        host_1 = 'host_1.foo.com'
        self.assertEqual({host_1: {'Error': ERROR}},
                         vsphere.coredump_network_enable(HOST, USER, PASSWORD, True, esxi_hosts=[host_1]))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 0, 'stdout': ''}))
    @patch('salt.modules.vsphere._format_coredump_stdout', MagicMock(return_value={}))
    def test_coredump_network_enable_host_list_success(self):
        '''
        Tests successful function return when an esxi_host is provided.
        '''
        enabled = True
        host_1 = 'host_1.foo.com'
        self.assertEqual({host_1: {'Coredump Enabled': enabled}},
                         vsphere.coredump_network_enable(HOST, USER, PASSWORD, enabled, esxi_hosts=[host_1]))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 1, 'stdout': ERROR}))
    def test_coredump_network_enable_bad_retcode(self):
        '''
        Tests error message given for a single ESXi host.
        '''
        self.assertEqual({HOST: {'Error': ERROR}},
                         vsphere.coredump_network_enable(HOST, USER, PASSWORD, True))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 0, 'stdout': ''}))
    @patch('salt.modules.vsphere._format_coredump_stdout', MagicMock(return_value={}))
    def test_coredump_network_enable_success(self):
        '''
        Tests successful function return for a single ESXi host.
        '''
        enabled = True
        self.assertEqual({HOST: {'Coredump Enabled': enabled}},
                         vsphere.coredump_network_enable(HOST, USER, PASSWORD, enabled))

    # Tests for set_coredump_network_config function

    def test_set_coredump_network_config_esxi_hosts_not_list(self):
        '''
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list.
        '''
        self.assertRaises(CommandExecutionError,
                          vsphere.set_coredump_network_config,
                          HOST, USER, PASSWORD, 'loghost', 'foo', esxi_hosts='bar')

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 1}))
    def test_set_coredump_network_config_host_list_bad_retcode(self):
        '''
        Tests error message returned with list of esxi_hosts.
        '''
        host_1 = 'host_1.foo.com'
        self.assertEqual({host_1: {'retcode': 1, 'success': False}},
                         vsphere.set_coredump_network_config(HOST,
                                                             USER,
                                                             PASSWORD,
                                                             'dump-ip.test.com',
                                                             esxi_hosts=[host_1]))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 0}))
    def test_set_coredump_network_config_host_list_success(self):
        '''
        Tests successful function return when an esxi_host is provided.
        '''
        host_1 = 'host_1.foo.com'
        self.assertEqual({host_1: {'retcode': 0, 'success': True}},
                         vsphere.set_coredump_network_config(HOST,
                                                             USER,
                                                             PASSWORD,
                                                             'dump-ip.test.com',
                                                             esxi_hosts=[host_1]))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 1}))
    def test_set_coredump_network_config_bad_retcode(self):
        '''
        Tests error message given for a single ESXi host.
        '''
        self.assertEqual({HOST: {'retcode': 1, 'success': False}},
                         vsphere.set_coredump_network_config(HOST,
                                                             USER,
                                                             PASSWORD,
                                                             'dump-ip.test.com'))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 0}))
    def test_set_coredump_network_config_success(self):
        '''
        Tests successful function return for a single ESXi host.
        '''
        self.assertEqual({HOST: {'retcode': 0, 'success': True}},
                         vsphere.set_coredump_network_config(HOST,
                                                             USER,
                                                             PASSWORD,
                                                             'dump-ip.test.com'))

    # Tests for get_firewall_status function

    def test_get_firewall_status_esxi_hosts_not_list(self):
        '''
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list.
        '''
        self.assertRaises(CommandExecutionError,
                          vsphere.get_firewall_status,
                          HOST, USER, PASSWORD, esxi_hosts='foo')

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 1, 'stdout': ERROR}))
    def test_get_firewall_status_host_list_bad_retcode(self):
        '''
        Tests error message returned with list of esxi_hosts.
        '''
        host_1 = 'host_1.foo.com'
        self.assertEqual({host_1: {'success': False, 'Error': ERROR, 'rulesets': None}},
                         vsphere.get_firewall_status(HOST, USER, PASSWORD, esxi_hosts=[host_1]))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 0, 'stdout': ''}))
    def test_get_firewall_status_host_list_success(self):
        '''
        Tests successful function return when an esxi_host is provided.
        '''
        host_1 = 'host_1.foo.com'
        self.assertEqual({host_1: {'rulesets': {}, 'success': True}},
                         vsphere.get_firewall_status(HOST, USER, PASSWORD, esxi_hosts=[host_1]))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 1, 'stdout': ERROR}))
    def test_get_firewall_status_bad_retcode(self):
        '''
        Tests error message given for a single ESXi host.
        '''
        self.assertEqual({HOST: {'success': False, 'Error': ERROR, 'rulesets': None}},
                         vsphere.get_firewall_status(HOST, USER, PASSWORD))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 0, 'stdout': ''}))
    def test_get_firewall_status_success(self):
        '''
        Tests successful function return for a single ESXi host.
        '''
        self.assertEqual({HOST: {'rulesets': {}, 'success': True}},
                         vsphere.get_firewall_status(HOST, USER, PASSWORD))

    # Tests for enable_firewall_ruleset function

    def test_enable_firewall_ruleset_esxi_hosts_not_list(self):
        '''
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list.
        '''
        self.assertRaises(CommandExecutionError,
                          vsphere.enable_firewall_ruleset,
                          HOST, USER, PASSWORD, 'foo', 'bar', esxi_hosts='baz')

    # Tests for syslog_service_reload function

    def test_syslog_service_reload_esxi_hosts_not_list(self):
        '''
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list.
        '''
        self.assertRaises(CommandExecutionError,
                          vsphere.syslog_service_reload,
                          HOST, USER, PASSWORD, esxi_hosts='foo')

    # Tests for set_syslog_config function.
    # These tests only test the firewall=True and syslog_config == 'loghost' if block.
    # The rest of the function is tested in the _set_syslog_config_helper tests below.

    def test_set_syslog_config_esxi_hosts_not_list(self):
        '''
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list, but we don't enter the 'loghost'/firewall loop.
        '''
        self.assertRaises(CommandExecutionError,
                          vsphere.set_syslog_config,
                          HOST, USER, PASSWORD, 'foo', 'bar', esxi_hosts='baz')

    def test_set_syslog_config_esxi_hosts_not_list_firewall(self):
        '''
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list, and we enter the 'loghost'/firewall loop.
        '''
        self.assertRaises(CommandExecutionError,
                          vsphere.set_syslog_config,
                          HOST, USER, PASSWORD, 'loghost', 'foo', firewall=True, esxi_hosts='bar')

    @patch('salt.modules.vsphere.enable_firewall_ruleset',
           MagicMock(return_value={'host_1.foo.com': {'retcode': 1, 'stdout': ERROR}}))
    @patch('salt.modules.vsphere._set_syslog_config_helper',
           MagicMock(return_value={}))
    def test_set_syslog_config_host_list_firewall_bad_retcode(self):
        '''
        Tests error message returned with list of esxi_hosts with 'loghost' as syslog_config.
        '''
        host_1 = 'host_1.foo.com'
        self.assertEqual({host_1: {'enable_firewall': {'message': ERROR, 'success': False}}},
                         vsphere.set_syslog_config(HOST,
                                                   USER,
                                                   PASSWORD,
                                                   'loghost',
                                                   'foo',
                                                   firewall=True,
                                                   esxi_hosts=[host_1]))

    @patch('salt.modules.vsphere.enable_firewall_ruleset',
           MagicMock(return_value={'host_1.foo.com': {'retcode': 0}}))
    @patch('salt.modules.vsphere._set_syslog_config_helper',
           MagicMock(return_value={}))
    def test_set_syslog_config_host_list_firewall_success(self):
        '''
        Tests successful function return with list of esxi_hosts with 'loghost' as syslog_config.
        '''
        host_1 = 'host_1.foo.com'
        self.assertEqual({host_1: {'enable_firewall': {'success': True}}},
                         vsphere.set_syslog_config(HOST,
                                                   USER,
                                                   PASSWORD,
                                                   'loghost',
                                                   'foo',
                                                   firewall=True,
                                                   esxi_hosts=[host_1]))

    @patch('salt.modules.vsphere.enable_firewall_ruleset',
           MagicMock(return_value={HOST: {'retcode': 1, 'stdout': ERROR}}))
    @patch('salt.modules.vsphere._set_syslog_config_helper',
           MagicMock(return_value={}))
    def test_set_syslog_config_firewall_bad_retcode(self):
        '''
        Tests error message given for a single ESXi host with 'loghost' as syslog_config.
        '''
        self.assertEqual({HOST: {'enable_firewall': {'message': ERROR, 'success': False}}},
                         vsphere.set_syslog_config(HOST,
                                                   USER,
                                                   PASSWORD,
                                                   'loghost',
                                                   'foo',
                                                   firewall=True))

    @patch('salt.modules.vsphere.enable_firewall_ruleset',
           MagicMock(return_value={HOST: {'retcode': 0}}))
    @patch('salt.modules.vsphere._set_syslog_config_helper',
           MagicMock(return_value={}))
    def test_set_syslog_config_firewall_success(self):
        '''
        Tests successful function return for a single ESXi host with 'loghost' as syslog_config.
        '''
        self.assertEqual({HOST: {'enable_firewall': {'success': True}}},
                         vsphere.set_syslog_config(HOST,
                                                   USER,
                                                   PASSWORD,
                                                   'loghost',
                                                   'foo',
                                                   firewall=True))

    # Tests for get_syslog_config function

    def test_get_syslog_config_esxi_hosts_not_list(self):
        '''
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list.
        '''
        self.assertRaises(CommandExecutionError,
                          vsphere.get_syslog_config,
                          HOST, USER, PASSWORD, esxi_hosts='foo')

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 1, 'stdout': ERROR}))
    def test_get_syslog_config_host_list_bad_retcode(self):
        '''
        Tests error message returned with list of esxi_hosts.
        '''
        host_1 = 'host_1.foo.com'
        self.assertEqual({host_1: {'message': ERROR, 'success': False}},
                         vsphere.get_syslog_config(HOST, USER, PASSWORD, esxi_hosts=[host_1]))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 0, 'stdout': ''}))
    def test_get_syslog_config_host_list_success(self):
        '''
        Tests successful function return when an esxi_host is provided.
        '''
        host_1 = 'host_1.foo.com'
        self.assertEqual({host_1: {'success': True}},
                         vsphere.get_syslog_config(HOST, USER, PASSWORD, esxi_hosts=[host_1]))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 1, 'stdout': ERROR}))
    def test_get_syslog_config_bad_retcode(self):
        '''
        Tests error message given for a single ESXi host.
        '''
        self.assertEqual({HOST: {'message': ERROR, 'success': False}},
                         vsphere.get_syslog_config(HOST, USER, PASSWORD))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 0, 'stdout': ''}))
    def test_get_syslog_config_success(self):
        '''
        Tests successful function return for a single ESXi host.
        '''
        self.assertEqual({HOST: {'success': True}},
                         vsphere.get_syslog_config(HOST, USER, PASSWORD))

    # Tests for reset_syslog_config function

    def test_reset_syslog_config_no_syslog_config(self):
        '''
        Tests CommandExecutionError is raised when a syslog_config parameter is missing.
        '''
        self.assertRaises(CommandExecutionError,
                          vsphere.reset_syslog_config,
                          HOST, USER, PASSWORD)

    def test_reset_syslog_config_esxi_hosts_not_list(self):
        '''
        Tests CommandExecutionError is raised when esxi_hosts is provided,
        but is not a list.
        '''
        self.assertRaises(CommandExecutionError,
                          vsphere.reset_syslog_config,
                          HOST, USER, PASSWORD, syslog_config='test', esxi_hosts='foo')

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={}))
    def test_reset_syslog_config_invalid_config_param(self):
        '''
        Tests error message returned when an invalid syslog_config parameter is provided.
        '''
        error = 'Invalid syslog configuration parameter'
        self.assertEqual({HOST: {'success': False, 'test': {'message': error, 'success': False}}},
                         vsphere.reset_syslog_config(HOST, USER, PASSWORD,
                                                     syslog_config='test'))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 1, 'stdout': ERROR}))
    def test_reset_syslog_config_host_list_bad_retcode(self):
        '''
        Tests error message returned with list of esxi_hosts.
        '''
        host_1 = 'host_1.foo.com'
        self.assertEqual({host_1: {'success': False, 'logdir': {'message': ERROR, 'success': False}}},
                         vsphere.reset_syslog_config(HOST, USER, PASSWORD,
                                                     syslog_config='logdir',
                                                     esxi_hosts=[host_1]))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 0, 'stdout': ''}))
    def test_reset_syslog_config_host_list_success(self):
        '''
        Tests successful function return when an esxi_host is provided.
        '''
        host_1 = 'host_1.foo.com'
        self.assertEqual({host_1: {'success': True, 'loghost': {'success': True}}},
                         vsphere.reset_syslog_config(HOST, USER, PASSWORD,
                                                     syslog_config='loghost',
                                                     esxi_hosts=[host_1]))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 1, 'stdout': ERROR}))
    def test_reset_syslog_config_bad_retcode(self):
        '''
        Tests error message given for a single ESXi host.
        '''
        self.assertEqual({HOST: {'success': False, 'logdir-unique': {'message': ERROR, 'success': False}}},
                         vsphere.reset_syslog_config(HOST, USER, PASSWORD,
                                                     syslog_config='logdir-unique'))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 0, 'stdout': ''}))
    def test_reset_syslog_config_success(self):
        '''
        Tests successful function return for a single ESXi host.
        '''
        self.assertEqual({HOST: {'success': True, 'default-rotate': {'success': True}}},
                         vsphere.reset_syslog_config(HOST, USER, PASSWORD,
                                                     syslog_config='default-rotate'))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 0, 'stdout': ''}))
    def test_reset_syslog_config_success_multiple_configs(self):
        '''
        Tests successful function return for a single ESXi host when passing in multiple syslog_config values.
        '''
        self.assertEqual({HOST: {'success': True,
                                 'default-size': {'success': True},
                                 'default-timeout': {'success': True}}},
                         vsphere.reset_syslog_config(HOST, USER, PASSWORD,
                                                     syslog_config='default-size,default-timeout'))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 0, 'stdout': ''}))
    def test_reset_syslog_config_success_all_configs(self):
        '''
        Tests successful function return for a single ESXi host when passing in multiple syslog_config values.
        '''
        self.assertEqual({HOST: {'success': True,
                                 'logdir': {'success': True},
                                 'loghost': {'success': True},
                                 'default-rotate': {'success': True},
                                 'default-size': {'success': True},
                                 'default-timeout': {'success': True},
                                 'logdir-unique': {'success': True}}},
                         vsphere.reset_syslog_config(HOST, USER, PASSWORD,
                                                     syslog_config='all'))

    # Tests for _reset_syslog_config_params function

    def test_reset_syslog_config_params_no_valid_reset(self):
        '''
        Tests function returns False when an invalid syslog config is passed.
        '''
        valid_resets = ['hello', 'world']
        config = 'foo'
        ret = {'success': False, config: {'success': False, 'message': 'Invalid syslog configuration parameter'}}
        self.assertEqual(ret, vsphere._reset_syslog_config_params(HOST, USER, PASSWORD,
                                                                  'cmd', config, valid_resets))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 1, 'stdout': ERROR}))
    def test_reset_syslog_config_params_error(self):
        '''
        Tests function returns False when the esxxli function returns an unsuccessful retcode.
        '''
        valid_resets = ['hello', 'world']
        error_dict = {'success': False, 'message': ERROR}
        ret = {'success': False, 'hello': error_dict, 'world': error_dict}
        self.assertDictEqual(ret, vsphere._reset_syslog_config_params(HOST, USER, PASSWORD,
                                                                      'cmd', valid_resets, valid_resets))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 0}))
    def test_reset_syslog_config_params_success(self):
        '''
        Tests function returns True when the esxxli function returns a successful retcode.
        '''
        valid_resets = ['hello', 'world']
        ret = {'success': True, 'hello': {'success': True}, 'world': {'success': True}}
        self.assertDictEqual(ret, vsphere._reset_syslog_config_params(HOST, USER, PASSWORD,
                                                                      'cmd', valid_resets, valid_resets))

    # Tests for _set_syslog_config_helper function

    def test_set_syslog_config_helper_no_valid_reset(self):
        '''
        Tests function returns False when an invalid syslog config is passed.
        '''
        config = 'foo'
        ret = {'success': False, 'message': '\'{0}\' is not a valid config variable.'.format(config)}
        self.assertEqual(ret, vsphere._set_syslog_config_helper(HOST, USER, PASSWORD, config, 'bar'))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 1, 'stdout': ERROR}))
    def test_set_syslog_config_helper_bad_retcode(self):
        '''
        Tests function returns False when the esxcli function returns an unsuccessful retcode.
        '''
        config = 'default-rotate'
        self.assertEqual({config: {'success': False, 'message': ERROR}},
                         vsphere._set_syslog_config_helper(HOST, USER, PASSWORD, config, 'foo'))

    @patch('salt.utils.vmware.esxcli', MagicMock(return_value={'retcode': 0}))
    def test_set_syslog_config_helper_success(self):
        '''
        Tests successful function return.
        '''
        config = 'logdir'
        self.assertEqual({config: {'success': True}},
                         vsphere._set_syslog_config_helper(HOST, USER, PASSWORD, config, 'foo'))
