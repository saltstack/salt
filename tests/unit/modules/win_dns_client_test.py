# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

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

# Import Salt Libs
from salt.modules import win_dns_client

# Globals
win_dns_client.__salt__ = {}
win_dns_client.__context__ = {}


class Mockwmi(object):
    '''
    Mock wmi class
    '''
    NetConnectionID = 'Local Area Connection'
    Index = 0
    DNSServerSearchOrder = ['10.1.1.10']
    Description = 'Local Area Connection'
    DHCPEnabled = True

    def __init__(self):
        self.netenabled = None
        self.index = None
        self.ipenabled = None

    @staticmethod
    def WMI():
        '''
        Mock WMI method
        '''
        return Mockwmi()

    def Win32_NetworkAdapter(self, NetEnabled=True):
        '''
        Mock Win32_NetworkAdapter method
        '''
        self.netenabled = NetEnabled
        return [Mockwmi()]

    def Win32_NetworkAdapterConfiguration(self, Index=0, IPEnabled=1):
        '''
        Mock Win32_NetworkAdapterConfiguration method
        '''
        self.index = Index
        self.ipenabled = IPEnabled
        return [Mockwmi()]

win_dns_client.wmi = Mockwmi


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinDnsClientTestCase(TestCase):
    '''
    Test cases for salt.modules.win_dns_client
    '''
    # 'get_dns_servers' function tests: 1

    def test_get_dns_servers(self):
        '''
        Test if it return a list of the configured DNS servers
        of the specified interface.
        '''
        with patch('salt.utils.winapi.Com', MagicMock()):
            self.assertListEqual(win_dns_client.get_dns_servers
                                 ('Local Area Connection'), ['10.1.1.10'])

            self.assertFalse(win_dns_client.get_dns_servers('Ethernet'))

    # 'rm_dns' function tests: 1

    def test_rm_dns(self):
        '''
        Test if it remove the DNS server from the network interface.
        '''
        with patch.dict(win_dns_client.__salt__,
                        {'cmd.retcode': MagicMock(return_value=0)}):
            self.assertTrue(win_dns_client.rm_dns('10.1.1.10'))

    # 'add_dns' function tests: 1

    def test_add_dns(self):
        '''
        Test if it add the DNS server to the network interface.
        '''
        with patch('salt.utils.winapi.Com', MagicMock()):
            self.assertFalse(win_dns_client.add_dns('10.1.1.10', 'Ethernet'))

            self.assertTrue(win_dns_client.add_dns('10.1.1.10',
                                                   'Local Area Connection'))

            with patch.dict(win_dns_client.__salt__,
                            {'cmd.retcode': MagicMock(return_value=0)}):
                self.assertTrue(win_dns_client.add_dns('10.1.1.0',
                                                       'Local Area Connection'))

    # 'dns_dhcp' function tests: 1

    def test_dns_dhcp(self):
        '''
        Test if it configure the interface to get its
        DNS servers from the DHCP server
        '''
        with patch.dict(win_dns_client.__salt__,
                        {'cmd.retcode': MagicMock(return_value=0)}):
            self.assertTrue(win_dns_client.dns_dhcp())

    # 'get_dns_config' function tests: 1

    def test_get_dns_config(self):
        '''
        Test if it get the type of DNS configuration (dhcp / static)
        '''
        with patch('salt.utils.winapi.Com', MagicMock()):
            self.assertTrue(win_dns_client.get_dns_config())


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinDnsClientTestCase, needs_daemon=False)
