# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.states import win_network

# Globals
win_network.__salt__ = {}
win_network.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinNetworkTestCase(TestCase):
    '''
        Validate the nftables state
    '''
    def test_managed(self):
        '''
            Test to ensure that the named interface is configured properly.
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': False,
               'comment': ''}
        ret.update({'comment': 'dns_proto must be one of the following:'
                    ' static, dhcp. ip_proto must be one of the following:'
                    ' static, dhcp.'})
        self.assertDictEqual(win_network.managed('salt'), ret)

        mock = MagicMock(return_value=False)
        mock1 = MagicMock(side_effect=[False, True, True, True, True, True,
                                       True])
        mock2 = MagicMock(side_effect=[False, True, True, {'salt': 'True'},
                                       {'salt': 'True'}])
        with patch.dict(win_network.__salt__, {"ip.is_enabled": mock,
                                               "ip.is_disabled": mock1,
                                               "ip.enable": mock,
                                               "ip.get_interface": mock2,
                                               "ip.set_dhcp_dns": mock,
                                               "ip.set_dhcp_ip": mock}):
            ret.update({'comment': "Interface 'salt' is up to date."
                        " (already disabled)", 'result': True})
            self.assertDictEqual(win_network.managed('salt',
                                                     dns_proto='static',
                                                     ip_proto='static',
                                                     enabled=False), ret)

            with patch.dict(win_network.__opts__, {"test": False}):
                ret.update({'comment': "Failed to enable interface 'salt'"
                            " to make changes", 'result': False})
                self.assertDictEqual(win_network.managed('salt',
                                                     dns_proto='static',
                                                     ip_proto='static'),
                                     ret)
            mock = MagicMock(side_effect=['True', False, False, False, False,
                                          False])
            with patch.object(win_network, '_validate', mock):
                ret.update({'comment': 'The following SLS configuration'
                            ' errors were detected: T r u e'})
                self.assertDictEqual(win_network.managed('salt',
                                                         dns_proto='static',
                                                         ip_proto='static'),
                                     ret)

                ret.update({'comment': "Unable to get current"
                            " configuration for interface 'salt'",
                            'result': False})
                self.assertDictEqual(win_network.managed('salt',
                                                         dns_proto='dhcp',
                                                         ip_proto='dhcp'),
                                     ret)

                mock = MagicMock(side_effect=[False, [''],
                                              {'dns_proto': 'dhcp',
                                               'ip_proto': 'dhcp'},
                                              {'dns_proto': 'dhcp',
                                               'ip_proto': 'dhcp'}])
                ret.update({'comment': "Interface 'salt' is up to date.",
                            'result': True})
                with patch.object(win_network, '_changes', mock):
                    self.assertDictEqual(win_network.managed('salt',
                                                             dns_proto='dhcp',
                                                             ip_proto='dhcp'
                                                             ), ret)

                    ret.update({'comment': "The following changes will be made"
                                " to interface 'salt': ", 'result': None})
                    with patch.dict(win_network.__opts__, {"test": True}):
                        self.assertDictEqual(win_network.managed('salt',
                                                                 dns_proto='dh'
                                                                 'cp',
                                                                 ip_proto='dhcp'
                                                                 ), ret)

                    with patch.dict(win_network.__opts__, {"test": False}):
                        ret.update({'comment': "Failed to set desired"
                                    " configuration settings for interface"
                                    " 'salt'", 'result': False})
                        self.assertDictEqual(win_network.managed('salt',
                                                                 dns_proto='dh'
                                                                 'cp',
                                                                 ip_proto='dhcp'
                                                                 ), ret)
