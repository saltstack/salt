# -*- coding: utf-8 -*-
'''
integration tests for nilirt_ip
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import time
import re

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest, skip_if_not_root

# Import Salt libs
import salt.utils.platform
import salt.modules.nilrt_ip as ip
# pylint: disable=import-error
from salt.ext.six.moves import configparser
from salt.ext import six
import salt.utils.files

try:
    import pyiface
    from pyiface.ifreqioctls import IFF_LOOPBACK, IFF_RUNNING
except ImportError:
    pyiface = None

try:
    from requests.structures import CaseInsensitiveDict
except ImportError:
    CaseInsensitiveDict = None


# pylint: disable=too-many-ancestors
@skip_if_not_root
@skipIf(not pyiface, 'The python pyiface package is not installed')
@skipIf(not CaseInsensitiveDict, 'The python package request is not installed')
@skipIf(not salt.utils.platform.is_linux(), 'These tests can only be run on linux')
class NilrtIpModuleTest(ModuleCase):
    '''
    Validate the nilrt_ip module
    '''

    @staticmethod
    def setup_loader_modules():
        '''
        Setup loader modules
        '''
        return {ip: {}}

    def setUp(self):
        '''
        Get current settings
        '''
        self.os_grain = self.run_function('grains.item', ['os_family', 'lsb_distrib_id'])
        if self.os_grain['os_family'] != 'NILinuxRT':
            self.skipTest('Tests applicable only to NILinuxRT')
        super(NilrtIpModuleTest, self).setUp()
        if self.os_grain['lsb_distrib_id'] == 'nilrt':
            self.run_function('file.copy', ['/etc/natinst/share/ni-rt.ini', '/tmp/ni-rt.ini', 'remove_existing=True'])
        else:
            self.run_function('file.copy', ['/var/lib/connman', '/tmp/connman', 'recurse=True', 'remove_existing=True'])

    def tearDown(self):
        '''
        Reset to original settings
        '''
        # restore files
        if self.os_grain['lsb_distrib_id'] == 'nilrt':
            self.run_function('file.copy', ['/tmp/ni-rt.ini', '/etc/natinst/share/ni-rt.ini', 'remove_existing=True'])
            self.run_function('cmd.run', ['/etc/init.d/networking restart'])
        else:
            self.run_function('file.copy', ['/tmp/connman', '/var/lib/connman', 'recurse=True', 'remove_existing=True'])
            self.run_function('service.restart', ['connman'])
        time.sleep(10)
        interfaces = self.__interfaces()
        for interface in interfaces:
            self.run_function('ip.up', [interface.name])

    @staticmethod
    def __connected(interface):
        '''
        Check if an interface is up or down
        :param interface: pyiface.Interface object
        :return: True, if interface is up, otherwise False.
        '''
        return interface.flags & IFF_RUNNING != 0

    @staticmethod
    def __interfaces():
        '''
        Return the list of all interfaces without loopback
        '''
        return [interface for interface in pyiface.getIfaces() if interface.flags & IFF_LOOPBACK == 0]

    def __check_ethercat(self):
        '''
        Check if ethercat is installed.

        :return: True if ethercat is installed, otherwise False.
        '''
        if self.os_grain['lsb_distrib_id'] != 'nilrt':
            return False
        with salt.utils.files.fopen('/etc/natinst/share/ni-rt.ini', 'r') as config_file:
            config_parser = configparser.RawConfigParser(dict_type=CaseInsensitiveDict)
            config_parser.readfp(config_file)
            if six.PY2:
                if config_parser.has_option('lvrt', 'AdditionalNetworkProtocols') and 'ethercat' in config_parser.get(
                                            'lvrt', 'AdditionalNetworkProtocols').lower():
                    return True
                return False
            else:
                return 'ethercat' in config_parser.get('lvrt', 'AdditionalNetworkProtocols', fallback='').lower()

    @destructiveTest
    def test_down(self):
        '''
        Test ip.down function
        '''
        interfaces = self.__interfaces()
        for interface in interfaces:
            result = self.run_function('ip.down', [interface.name])
            self.assertTrue(result)
        info = self.run_function('ip.get_interfaces_details', timeout=300)
        for interface in info['interfaces']:
            self.assertEqual(interface['adapter_mode'], 'disabled')
            self.assertFalse(self.__connected(pyiface.Interface(name=interface['connectionid'])))

    @destructiveTest
    def test_up(self):
        '''
        Test ip.up function
        '''
        interfaces = self.__interfaces()
        # first down all interfaces
        for interface in interfaces:
            self.run_function('ip.down', [interface.name])
            self.assertFalse(self.__connected(interface))
        # up interfaces
        for interface in interfaces:
            result = self.run_function('ip.up', [interface.name])
            self.assertTrue(result)
        info = self.run_function('ip.get_interfaces_details', timeout=300)
        for interface in info['interfaces']:
            self.assertEqual(interface['adapter_mode'], 'tcpip')

    @destructiveTest
    def test_set_dhcp_linklocal_all(self):
        '''
        Test ip.set_dhcp_linklocal_all function
        '''
        interfaces = self.__interfaces()
        for interface in interfaces:
            result = self.run_function('ip.set_dhcp_linklocal_all', [interface.name])
            self.assertTrue(result)
        info = self.run_function('ip.get_interfaces_details', timeout=300)
        for interface in info['interfaces']:
            self.assertEqual(interface['ipv4']['requestmode'], 'dhcp_linklocal')
            self.assertEqual(interface['adapter_mode'], 'tcpip')

    @destructiveTest
    def test_set_dhcp_only_all(self):
        '''
        Test ip.set_dhcp_only_all function
        '''
        if self.os_grain['lsb_distrib_id'] != 'nilrt':
            self.skipTest('Test not applicable to newer nilrt')
        interfaces = self.__interfaces()
        for interface in interfaces:
            result = self.run_function('ip.set_dhcp_only_all', [interface.name])
            self.assertTrue(result)
        info = self.run_function('ip.get_interfaces_details', timeout=300)
        for interface in info['interfaces']:
            self.assertEqual(interface['ipv4']['requestmode'], 'dhcp_only')
            self.assertEqual(interface['adapter_mode'], 'tcpip')

    @destructiveTest
    def test_set_linklocal_only_all(self):
        '''
        Test ip.set_linklocal_only_all function
        '''
        if self.os_grain['lsb_distrib_id'] != 'nilrt':
            self.skipTest('Test not applicable to newer nilrt')
        interfaces = self.__interfaces()
        for interface in interfaces:
            result = self.run_function('ip.set_linklocal_only_all', [interface.name])
            self.assertTrue(result)
        info = self.run_function('ip.get_interfaces_details', timeout=300)
        for interface in info['interfaces']:
            self.assertEqual(interface['ipv4']['requestmode'], 'linklocal_only')
            self.assertEqual(interface['adapter_mode'], 'tcpip')

    @destructiveTest
    def test_static_all(self):
        '''
        Test ip.set_static_all function
        '''
        interfaces = self.__interfaces()
        for interface in interfaces:
            result = self.run_function('ip.set_static_all', [interface.name, '192.168.10.4', '255.255.255.0',
                                                             '192.168.10.1', '8.8.4.4 8.8.8.8'])
            self.assertTrue(result)
        info = self.run_function('ip.get_interfaces_details', timeout=300)
        for interface in info['interfaces']:
            self.assertEqual(interface['adapter_mode'], 'tcpip')
            if self.os_grain['lsb_distrib_id'] != 'nilrt':
                self.assertIn('8.8.4.4', interface['ipv4']['dns'])
                self.assertIn('8.8.8.8', interface['ipv4']['dns'])
            else:
                self.assertEqual(interface['ipv4']['dns'], ['8.8.4.4'])
            self.assertEqual(interface['ipv4']['requestmode'], 'static')
            self.assertEqual(interface['ipv4']['address'], '192.168.10.4')
            self.assertEqual(interface['ipv4']['netmask'], '255.255.255.0')
            self.assertEqual(interface['ipv4']['gateway'], '192.168.10.1')

    def test_supported_adapter_modes(self):
        '''
        Test supported adapter modes for each interface
        '''
        interface_pattern = re.compile('^eth[0-9]+$')
        info = self.run_function('ip.get_interfaces_details', timeout=300)
        for interface in info['interfaces']:
            if interface['connectionid'] == 'eth0':
                self.assertEqual(interface['supported_adapter_modes'], ['tcpip'])
            else:
                self.assertIn('tcpip', interface['supported_adapter_modes'])
                if not interface_pattern.match(interface['connectionid']):
                    self.assertNotIn('ethercat', interface['supported_adapter_modes'])
                elif self.__check_ethercat():
                    self.assertIn('ethercat', interface['supported_adapter_modes'])

    @destructiveTest
    def test_ethercat(self):
        '''
        Test ip.set_ethercat function
        '''
        if not self.__check_ethercat():
            self.skipTest('Test is just for systems with Ethercat')
        self.assertTrue(self.run_function('ip.set_ethercat', ['eth1', 19]))
        info = self.run_function('ip.get_interfaces_details', timeout=300)
        for interface in info['interfaces']:
            if interface['connectionid'] == 'eth1':
                self.assertEqual(interface['adapter_mode'], 'ethercat')
                self.assertEqual(int(interface['ethercat']['masterid']), 19)
                break
        self.assertTrue(self.run_function('ip.set_dhcp_linklocal_all', ['eth1']))
        info = self.run_function('ip.get_interfaces_details', timeout=300)
        for interface in info['interfaces']:
            if interface['connectionid'] == 'eth1':
                self.assertEqual(interface['adapter_mode'], 'tcpip')
                self.assertEqual(interface['ipv4']['requestmode'], 'dhcp_linklocal')
                break
