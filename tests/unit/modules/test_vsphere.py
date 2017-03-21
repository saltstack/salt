# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for functions in salt.modules.vsphere
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Libs
import salt.modules.vsphere as vsphere
from salt.exceptions import CommandExecutionError, VMwareSaltError

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Globals
HOST = '1.2.3.4'
USER = 'root'
PASSWORD = 'SuperSecret!'
ERROR = 'Some Testing Error Message'
mock_si = MagicMock()

# Inject empty dunders do they can be patched
vsphere.__pillar__ = {}
vsphere.__salt__ = {}


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


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.modules.vsphere.__virtual__', MagicMock(return_value='vsphere'))
class GetProxyTypeTestCase(TestCase):
    '''Tests for salt.modules.vsphere.get_proxy_type'''

    def test_output(self):
        with patch.dict(vsphere.__pillar__,
                        {'proxy': {'proxytype': 'fake_proxy_type'}}):
            ret = vsphere.get_proxy_type()
        self.assertEqual('fake_proxy_type', ret)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.modules.vsphere.__virtual__', MagicMock(return_value='vsphere'))
class SupportsProxiesTestCase(TestCase):
    '''Tests for salt.modules.vsphere.supports_proxies decorator'''

    def test_supported_proxy(self):
        @vsphere.supports_proxies('supported')
        def mock_function():
            return 'fake_function'

        with patch('salt.modules.vsphere.get_proxy_type',
                   MagicMock(return_value='supported')):
            ret = mock_function()
        self.assertEqual('fake_function', ret)

    def test_unsupported_proxy(self):
        @vsphere.supports_proxies('supported')
        def mock_function():
            return 'fake_function'

        with patch('salt.modules.vsphere.get_proxy_type',
                   MagicMock(return_value='unsupported')):
            with self.assertRaises(CommandExecutionError) as excinfo:
                mock_function()
        self.assertEqual('\'unsupported\' proxy is not supported by '
                         'function mock_function',
                         excinfo.exception.strerror)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.modules.vsphere.__virtual__', MagicMock(return_value='vsphere'))
class _GetProxyConnectionDetailsTestCase(TestCase):
    '''Tests for salt.modules.vsphere._get_proxy_connection_details'''

    def setUp(self):
        self.esxi_host_details = {'host': 'fake_host',
                                  'username': 'fake_username',
                                  'password': 'fake_password',
                                  'protocol': 'fake_protocol',
                                  'port': 'fake_port',
                                  'mechanism': 'fake_mechanism',
                                  'principal': 'fake_principal',
                                  'domain': 'fake_domain'}
        self.esxi_vcenter_details = {'vcenter': 'fake_vcenter',
                                     'username': 'fake_username',
                                     'password': 'fake_password',
                                     'protocol': 'fake_protocol',
                                     'port': 'fake_port',
                                     'mechanism': 'fake_mechanism',
                                     'principal': 'fake_principal',
                                     'domain': 'fake_domain'}

    def test_esxi_proxy_host_details(self):
        with patch('salt.modules.vsphere.get_proxy_type',
                   MagicMock(return_value='esxi')):
            with patch.dict(vsphere.__salt__,
                            {'esxi.get_details':
                             MagicMock(return_value=self.esxi_host_details)}):
                ret = vsphere._get_proxy_connection_details()
        self.assertEqual(('fake_host', 'fake_username', 'fake_password',
                          'fake_protocol', 'fake_port', 'fake_mechanism',
                          'fake_principal', 'fake_domain'), ret)

    def test_esxi_proxy_vcenter_details(self):
        with patch('salt.modules.vsphere.get_proxy_type',
                   MagicMock(return_value='esxi')):
            with patch.dict(vsphere.__salt__,
                            {'esxi.get_details':
                             MagicMock(
                                 return_value=self.esxi_vcenter_details)}):
                ret = vsphere._get_proxy_connection_details()
        self.assertEqual(('fake_vcenter', 'fake_username', 'fake_password',
                          'fake_protocol', 'fake_port', 'fake_mechanism',
                          'fake_principal', 'fake_domain'), ret)

    def test_unsupported_proxy_details(self):
        with patch('salt.modules.vsphere.get_proxy_type',
                   MagicMock(return_value='unsupported')):
            with self.assertRaises(CommandExecutionError) as excinfo:
                ret = vsphere._get_proxy_connection_details()
        self.assertEqual('\'unsupported\' proxy is not supported',
                         excinfo.exception.strerror)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.modules.vsphere.__virtual__', MagicMock(return_value='vsphere'))
@patch('salt.modules.vsphere._get_proxy_connection_details', MagicMock())
@patch('salt.utils.vmware.get_service_instance', MagicMock())
@patch('salt.utils.vmware.disconnect', MagicMock())
class GetsServiceInstanceViaProxyTestCase(TestCase):
    '''
    Tests for salt.modules.vsphere.gets_service_instance_via_proxy
    decorator
    '''

    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_details1 = MagicMock()
        self.mock_details2 = MagicMock()

    def test_no_service_instance_or_kwargs_parameters(self):
        @vsphere.gets_service_instance_via_proxy
        def mock_function():
            return 'fake_function'

        with self.assertRaises(CommandExecutionError) as excinfo:
            mock_function()
        self.assertEqual('Function mock_function must have either a '
                         '\'service_instance\', or a \'**kwargs\' type '
                         'parameter', excinfo.exception.strerror)

    def test___get_proxy_connection_details_call(self):
        mock__get_proxy_connection_details = MagicMock()

        @vsphere.gets_service_instance_via_proxy
        def mock_function(service_instance=None):
            return service_instance

        with patch('salt.modules.vsphere._get_proxy_connection_details',
                   mock__get_proxy_connection_details):
            mock_function()
        mock__get_proxy_connection_details.assert_called_once_with()

    def test_service_instance_named_parameter_no_value(self):
        mock_get_service_instance = MagicMock(return_value=self.mock_si)
        mock_disconnect = MagicMock()

        @vsphere.gets_service_instance_via_proxy
        def mock_function(service_instance=None):
            return service_instance

        with patch('salt.modules.vsphere._get_proxy_connection_details',
                   MagicMock(return_value=(self.mock_details1,
                                           self.mock_details2))):
            with patch('salt.utils.vmware.get_service_instance',
                       mock_get_service_instance):
                with patch('salt.utils.vmware.disconnect', mock_disconnect):
                    ret = mock_function()
        mock_get_service_instance.assert_called_once_with(self.mock_details1,
                                                          self.mock_details2)
        mock_disconnect.assert_called_once_with(self.mock_si)
        self.assertEqual(ret, self.mock_si)

    def test_service_instance_kwargs_parameter_no_value(self):
        mock_get_service_instance = MagicMock(return_value=self.mock_si)
        mock_disconnect = MagicMock()

        @vsphere.gets_service_instance_via_proxy
        def mock_function(**kwargs):
            return kwargs['service_instance']

        with patch('salt.modules.vsphere._get_proxy_connection_details',
                   MagicMock(return_value=(self.mock_details1,
                                           self.mock_details2))):
            with patch('salt.utils.vmware.get_service_instance',
                       mock_get_service_instance):
                with patch('salt.utils.vmware.disconnect', mock_disconnect):
                    ret = mock_function()
        mock_get_service_instance.assert_called_once_with(self.mock_details1,
                                                          self.mock_details2)
        mock_disconnect.assert_called_once_with(self.mock_si)
        self.assertEqual(ret, self.mock_si)

    def test_service_instance_positional_parameter_no_default_value(self):
        mock_get_service_instance = MagicMock()
        mock_disconnect = MagicMock()

        @vsphere.gets_service_instance_via_proxy
        def mock_function(service_instance):
            return service_instance

        with patch('salt.modules.vsphere._get_proxy_connection_details',
                   MagicMock(return_value=(self.mock_details1,
                                           self.mock_details2))):
            with patch('salt.utils.vmware.get_service_instance',
                       mock_get_service_instance):
                with patch('salt.utils.vmware.disconnect', mock_disconnect):
                    ret = mock_function(self.mock_si)
        self.assertEqual(mock_get_service_instance.call_count, 0)
        self.assertEqual(mock_disconnect.call_count, 0)
        self.assertEqual(ret, self.mock_si)

    def test_service_instance_positional_parameter_with_default_value(self):
        mock_get_service_instance = MagicMock()
        mock_disconnect = MagicMock()

        @vsphere.gets_service_instance_via_proxy
        def mock_function(service_instance=None):
            return service_instance

        with patch('salt.modules.vsphere._get_proxy_connection_details',
                   MagicMock(return_value=(self.mock_details1,
                                           self.mock_details2))):
            with patch('salt.utils.vmware.get_service_instance',
                       mock_get_service_instance):
                with patch('salt.utils.vmware.disconnect', mock_disconnect):
                    ret = mock_function(self.mock_si)
        self.assertEqual(mock_get_service_instance.call_count, 0)
        self.assertEqual(mock_disconnect.call_count, 0)
        self.assertEqual(ret, self.mock_si)

    def test_service_instance_named_parameter_with_default_value(self):
        mock_get_service_instance = MagicMock()
        mock_disconnect = MagicMock()

        @vsphere.gets_service_instance_via_proxy
        def mock_function(service_instance=None):
            return service_instance

        with patch('salt.modules.vsphere._get_proxy_connection_details',
                   MagicMock(return_value=(self.mock_details1,
                                           self.mock_details2))):
            with patch('salt.utils.vmware.get_service_instance',
                       mock_get_service_instance):
                with patch('salt.utils.vmware.disconnect', mock_disconnect):
                    ret = mock_function(service_instance=self.mock_si)
        self.assertEqual(mock_get_service_instance.call_count, 0)
        self.assertEqual(mock_disconnect.call_count, 0)
        self.assertEqual(ret, self.mock_si)

    def test_service_instance_kwargs_parameter_passthrough(self):
        mock_get_service_instance = MagicMock()
        mock_disconnect = MagicMock()

        @vsphere.gets_service_instance_via_proxy
        def mock_function(**kwargs):
            return kwargs['service_instance']

        with patch('salt.modules.vsphere._get_proxy_connection_details',
                   MagicMock(return_value=(self.mock_details1,
                                           self.mock_details2))):
            with patch('salt.utils.vmware.get_service_instance',
                       mock_get_service_instance):
                with patch('salt.utils.vmware.disconnect', mock_disconnect):
                    ret = mock_function(service_instance=self.mock_si)
        self.assertEqual(mock_get_service_instance.call_count, 0)
        self.assertEqual(mock_disconnect.call_count, 0)
        self.assertEqual(ret, self.mock_si)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.modules.vsphere.__virtual__', MagicMock(return_value='vsphere'))
# Decorator mocks
@patch('salt.modules.vsphere.get_proxy_type', MagicMock(return_value='esxi'))
# Function mocks
@patch('salt.modules.vsphere._get_proxy_connection_details', MagicMock())
@patch('salt.utils.vmware.get_service_instance', MagicMock())
class GetServiceInstanceViaProxyTestCase(TestCase):
    '''Tests for salt.modules.vsphere.get_service_instance_via_proxy'''

    def test_supported_proxes(self):
        supported_proxies = ['esxi']
        for proxy_type in supported_proxies:
            with patch('salt.modules.vsphere.get_proxy_type',
                       MagicMock(return_value=proxy_type)):
                vsphere.get_service_instance_via_proxy()

    def test_get_service_instance_call(self):
        mock_connection_details = [MagicMock(), MagicMock(), MagicMock()]
        mock_get_service_instance = MagicMock()
        with patch('salt.modules.vsphere._get_proxy_connection_details',
                    MagicMock(return_value=mock_connection_details)):
            with patch('salt.utils.vmware.get_service_instance',
                       mock_get_service_instance):
                vsphere.get_service_instance_via_proxy()
        mock_get_service_instance.assert_called_once_with(
            *mock_connection_details)

    def test_output(self):
        mock_si = MagicMock()
        with patch('salt.utils.vmware.get_service_instance',
                    MagicMock(return_value=mock_si)):
            res = vsphere.get_service_instance_via_proxy()
        self.assertEqual(res, mock_si)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.modules.vsphere.__virtual__', MagicMock(return_value='vsphere'))
# Decorator mocks
@patch('salt.modules.vsphere.get_proxy_type', MagicMock(return_value='esxi'))
# Function mocks
@patch('salt.modules.vsphere._get_proxy_connection_details', MagicMock())
@patch('salt.utils.vmware.disconnect', MagicMock())
class DisconnectTestCase(TestCase):
    '''Tests for salt.modules.vsphere.disconnect'''

    def test_supported_proxes(self):
        supported_proxies = ['esxi']
        for proxy_type in supported_proxies:
            with patch('salt.modules.vsphere.get_proxy_type',
                       MagicMock(return_value=proxy_type)):
                vsphere.disconnect(mock_si)

    def test_disconnect_call(self):
        mock_disconnect = MagicMock()
        with patch('salt.utils.vmware.disconnect', mock_disconnect):
            vsphere.disconnect(mock_si)
        mock_disconnect.assert_called_once_with(mock_si)

    def test_output(self):
        res = vsphere.disconnect(mock_si)
        self.assertEqual(res, True)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.modules.vsphere.__virtual__', MagicMock(return_value='vsphere'))
# Decorator mocks
@patch('salt.modules.vsphere.get_proxy_type', MagicMock(return_value='esxi'))
@patch('salt.modules.vsphere._get_proxy_connection_details', MagicMock())
@patch('salt.utils.vmware.get_service_instance',
       MagicMock(return_value=mock_si))
@patch('salt.utils.vmware.disconnect', MagicMock())
# Function mocks
@patch('salt.utils.vmware.is_connection_to_a_vcenter', MagicMock())
class TestVcenterConnectionTestCase(TestCase):
    '''Tests for salt.modules.vsphere.test_vcenter_connection'''

    def test_supported_proxes(self):
        supported_proxies = ['esxi']
        for proxy_type in supported_proxies:
            with patch('salt.modules.vsphere.get_proxy_type',
                       MagicMock(return_value=proxy_type)):
                vsphere.test_vcenter_connection()

    def test_is_connection_to_a_vcenter_call_default_service_instance(self):
        mock_is_connection_to_a_vcenter = MagicMock()
        with patch('salt.utils.vmware.is_connection_to_a_vcenter',
                    mock_is_connection_to_a_vcenter):
            vsphere.test_vcenter_connection()
        mock_is_connection_to_a_vcenter.assert_called_once_with(mock_si)

    def test_is_connection_to_a_vcenter_call_explicit_service_instance(self):
        expl_mock_si = MagicMock()
        mock_is_connection_to_a_vcenter = MagicMock()
        with patch('salt.utils.vmware.is_connection_to_a_vcenter',
                    mock_is_connection_to_a_vcenter):
            vsphere.test_vcenter_connection(expl_mock_si)
        mock_is_connection_to_a_vcenter.assert_called_once_with(expl_mock_si)

    def test_is_connection_to_a_vcenter_raises_vmware_salt_error(self):
        exc = VMwareSaltError('VMwareSaltError')
        with patch('salt.utils.vmware.is_connection_to_a_vcenter',
                    MagicMock(side_effect=exc)):
            res = vsphere.test_vcenter_connection()
        self.assertEqual(res, False)

    def test_is_connection_to_a_vcenter_raises_non_vmware_salt_error(self):
        exc = Exception('NonVMwareSaltError')
        with patch('salt.utils.vmware.is_connection_to_a_vcenter',
                    MagicMock(side_effect=exc)):
            with self.assertRaises(Exception) as excinfo:
                res = vsphere.test_vcenter_connection()
        self.assertEqual('NonVMwareSaltError', str(excinfo.exception))

    def test_output_true(self):
        with patch('salt.utils.vmware.is_connection_to_a_vcenter',
                    MagicMock(return_value=True)):
            res = vsphere.test_vcenter_connection()
        self.assertEqual(res, True)

    def test_output_false(self):
        with patch('salt.utils.vmware.is_connection_to_a_vcenter',
                    MagicMock(return_value=False)):
            res = vsphere.test_vcenter_connection()
        self.assertEqual(res, False)
