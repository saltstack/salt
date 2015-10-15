# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import win_dns_client

# Globals
win_dns_client.__salt__ = {}
win_dns_client.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinDnsClientTestCase(TestCase):
    '''
        Validate the win_dns_client state
    '''
    def test_dns_exists(self):
        '''
            Test to configure the DNS server list in the specified interface
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': False,
               'comment': ''}
        with patch.dict(win_dns_client.__opts__, {"test": False}):
            ret.update({'changes': {'Servers Added': [],
                                    'Servers Removed': [],
                                    'Servers Reordered': []},
                        'comment': 'servers entry is not a list !'})
            self.assertDictEqual(win_dns_client.dns_exists('salt'), ret)

            mock = MagicMock(return_value=[2, 'salt'])
            with patch.dict(win_dns_client.__salt__,
                            {'win_dns_client.get_dns_servers': mock}):
                ret.update({'changes': {}, 'comment': "[2, 'salt'] are already"
                            " configured", 'result': True})
                self.assertDictEqual(win_dns_client.dns_exists('salt',
                                                               [2, 'salt']),
                                     ret)

                mock = MagicMock(side_effect=[False, True, True])
                with patch.dict(win_dns_client.__salt__,
                                {'win_dns_client.add_dns': mock}):
                    ret.update({'comment': 'Failed to add 1 as DNS'
                                ' server number 1', 'result': False})
                    self.assertDictEqual(win_dns_client.dns_exists('salt',
                                                                   [1, 'salt']
                                                                   ), ret)

                    mock = MagicMock(return_value=False)
                    with patch.dict(win_dns_client.__salt__,
                                    {'win_dns_client.rm_dns': mock}):
                        ret.update({'changes': {'Servers Added': ['a'],
                                                'Servers Removed': [],
                                                'Servers Reordered': []},
                                    'comment': 'Failed to remove 2 from DNS'
                                    ' server list'})
                        self.assertDictEqual(win_dns_client.dns_exists('salt',
                                                                       ['a'],
                                                                       'a',
                                                                       1),
                                             ret)

                    ret.update({'comment': 'DNS Servers have been updated',
                                'result': True})
                    self.assertDictEqual(win_dns_client.dns_exists('salt',
                                                                   ['a']), ret)

    def test_dns_dhcp(self):
        '''
            Test to configure the DNS server list from DHCP Server
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}
        mock = MagicMock(side_effect=['dhcp', 'salt', 'salt'])
        with patch.dict(win_dns_client.__salt__,
                        {'win_dns_client.get_dns_config': mock}):
            ret.update({'comment': 'Local Area Connection already configured'
                        ' with DNS from DHCP'})
            self.assertDictEqual(win_dns_client.dns_dhcp('salt'), ret)

            with patch.dict(win_dns_client.__opts__, {"test": True}):
                ret.update({'comment': '', 'result': None,
                            'changes': {'dns': 'configured from DHCP'}})
                self.assertDictEqual(win_dns_client.dns_dhcp('salt'), ret)

            with patch.dict(win_dns_client.__opts__, {"test": False}):
                mock = MagicMock(return_value=True)
                with patch.dict(win_dns_client.__salt__,
                                {'win_dns_client.dns_dhcp': mock}):
                    ret.update({'result': True})
                    self.assertDictEqual(win_dns_client.dns_dhcp('salt'), ret)

    def test_primary_suffix(self):
        '''
            Test to configure the global primary DNS suffix of a DHCP client.
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': False,
               'comment': ''}
        ret.update({'comment': "'updates' must be a boolean value"})
        self.assertDictEqual(win_dns_client.primary_suffix('salt', updates='a'
                                                           ), ret)

        mock = MagicMock(side_effect=['a', False, 'b', False])
        with patch.dict(win_dns_client.__salt__, {'reg.read_key': mock}):
            ret.update({'comment': 'No changes needed', 'result': True})
            self.assertDictEqual(win_dns_client.primary_suffix('salt', 'a'),
                                 ret)

            mock = MagicMock(return_value=True)
            with patch.dict(win_dns_client.__salt__, {'reg.set_key': mock}):
                ret.update({'changes': {'new': {'suffix': 'a'},
                                        'old': {'suffix': 'b'}},
                            'comment': 'Updated primary DNS suffix (a)'})
                self.assertDictEqual(win_dns_client.primary_suffix('salt',
                                                                   'a'), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinDnsClientTestCase, needs_daemon=False)
