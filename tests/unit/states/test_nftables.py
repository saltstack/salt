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
from salt.states import nftables

# Globals
nftables.__salt__ = {}
nftables.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NftablesTestCase(TestCase):
    '''
        Validate the nftables state
    '''
    def test_chain_present(self):
        '''
            Test to verify the chain is exist.
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}
        mock = MagicMock(side_effect=[True, False, False])
        with patch.dict(nftables.__salt__, {"nftables.check_chain": mock}):
            ret.update({'comment': 'nftables salt chain is already'
                        ' exist in filter table for ipv4'})
            self.assertDictEqual(nftables.chain_present('salt'), ret)

            mock = MagicMock(side_effect=[True, ''])
            with patch.dict(nftables.__salt__, {"nftables.new_chain": mock}):
                ret.update({'changes': {'locale': 'salt'},
                            'comment': 'nftables salt chain in filter'
                            ' table create success for ipv4'})
                self.assertDictEqual(nftables.chain_present('salt'), ret)

                ret.update({'changes': {},
                            'comment': 'Failed to create salt chain'
                            ' in filter table:  for ipv4',
                            'result': False})
                self.assertDictEqual(nftables.chain_present('salt'), ret)

    def test_chain_absent(self):
        '''
            Test to verify the chain is absent.
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}
        mock = MagicMock(side_effect=[False, True])
        with patch.dict(nftables.__salt__, {"nftables.check_chain": mock}):
            ret.update({'comment': 'nftables salt chain is already absent'
                        ' in filter table for ipv4'})
            self.assertDictEqual(nftables.chain_absent('salt'), ret)

            mock = MagicMock(return_value='')
            with patch.dict(nftables.__salt__, {"nftables.flush": mock}):
                ret.update({'result': False,
                            'comment': 'Failed to flush salt chain'
                            ' in filter table:  for ipv4'})
                self.assertDictEqual(nftables.chain_absent('salt'), ret)

    def test_append(self):
        '''
            Test to append a rule to a chain
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}
        mock = MagicMock(return_value=[])
        with patch.object(nftables, '_STATE_INTERNAL_KEYWORDS', mock):
            mock = MagicMock(return_value='a')
            with patch.dict(nftables.__salt__, {"nftables.build_rule": mock}):
                mock = MagicMock(side_effect=[True, False, False, False])
                with patch.dict(nftables.__salt__, {"nftables.check": mock}):
                    ret.update({'comment': 'nftables rule for salt'
                                ' already set (a) for ipv4'})
                    self.assertDictEqual(nftables.append('salt', table='',
                                                         chain=''), ret)

                    with patch.dict(nftables.__opts__, {"test": True}):
                        ret.update({'result': None,
                                    'comment': 'nftables rule for salt needs'
                                    ' to be set (a) for ipv4'})
                        self.assertDictEqual(nftables.append('salt', table='',
                                                             chain=''), ret)

                    with patch.dict(nftables.__opts__, {"test": False}):
                        mock = MagicMock(side_effect=[True, False])
                        with patch.dict(nftables.__salt__,
                                        {"nftables.append": mock}):
                            ret.update({'changes': {'locale': 'salt'},
                                        'comment': 'Set nftables rule for salt'
                                        ' to: a for ipv4',
                                        'result': True})
                            self.assertDictEqual(nftables.append('salt',
                                                                 table='',
                                                                 chain=''),
                                                 ret)

                            ret.update({'changes': {},
                                        'comment': 'Failed to set nftables'
                                        ' rule for salt.\nAttempted rule was'
                                        ' a for ipv4', 'result': False})
                            self.assertDictEqual(nftables.append('salt',
                                                                 table='',
                                                                 chain=''),
                                                 ret)

    def test_insert(self):
        '''
            Test to insert a rule into a chain
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}
        mock = MagicMock(return_value=[])
        with patch.object(nftables, '_STATE_INTERNAL_KEYWORDS', mock):
            mock = MagicMock(return_value='a')
            with patch.dict(nftables.__salt__, {"nftables.build_rule": mock}):
                mock = MagicMock(side_effect=[True, False, False, False])
                with patch.dict(nftables.__salt__, {"nftables.check": mock}):
                    ret.update({'comment': 'nftables rule for salt already'
                                ' set for ipv4 (a)'})
                    self.assertDictEqual(nftables.insert('salt', table='',
                                                         chain=''), ret)

                    with patch.dict(nftables.__opts__, {"test": True}):
                        ret.update({'result': None,
                                    'comment': 'nftables rule for salt'
                                    ' needs to be set for ipv4 (a)'})
                        self.assertDictEqual(nftables.insert('salt', table='',
                                                             chain=''), ret)

                    with patch.dict(nftables.__opts__, {"test": False}):
                        mock = MagicMock(side_effect=[True, False])
                        with patch.dict(nftables.__salt__,
                                        {"nftables.insert": mock}):
                            ret.update({'changes': {'locale': 'salt'},
                                        'comment': 'Set nftables rule for'
                                        ' salt to: a for ipv4',
                                        'result': True})
                            self.assertDictEqual(nftables.insert('salt',
                                                                 table='',
                                                                 chain='',
                                                                 position=''),
                                                 ret)

                            ret.update({'changes': {},
                                        'comment': 'Failed to set nftables'
                                        ' rule for salt.\nAttempted rule was'
                                        ' a', 'result': False})
                            self.assertDictEqual(nftables.insert('salt',
                                                                 table='',
                                                                 chain='',
                                                                 position=''),
                                                 ret)

    def test_delete(self):
        '''
            Test to delete a rule to a chain
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': None,
               'comment': ''}

        mock = MagicMock(return_value=[])
        with patch.object(nftables, '_STATE_INTERNAL_KEYWORDS', mock):
            mock = MagicMock(return_value='a')
            with patch.dict(nftables.__salt__, {'nftables.build_rule': mock}):
                mock = MagicMock(side_effect=[False, True, True, True])
                with patch.dict(nftables.__salt__, {'nftables.check': mock}):
                    ret.update({'comment': 'nftables rule for salt'
                                ' already absent for ipv4 (a)',
                                'result': True})
                    self.assertDictEqual(nftables.delete('salt',
                                                         table='', chain=''),
                                         ret)

                    with patch.dict(nftables.__opts__, {'test': True}):
                        ret.update({'result': None,
                                    'comment': 'nftables rule for salt needs'
                                    ' to be deleted for ipv4 (a)'})
                        self.assertDictEqual(nftables.delete('salt',
                                                             table='',
                                                             chain=''), ret)

                    with patch.dict(nftables.__opts__, {'test': False}):
                        mock = MagicMock(side_effect=[True, False])
                        with patch.dict(nftables.__salt__,
                                        {'nftables.delete': mock}):
                            ret.update({'result': True,
                                        'changes': {'locale': 'salt'},
                                        'comment': 'Delete nftables rule'
                                        ' for salt a'})
                            self.assertDictEqual(nftables.delete('salt',
                                                                 table='',
                                                                 chain='',
                                                                 position=''),
                                                 ret)

                            ret.update({'result': False,
                                        'changes': {},
                                        'comment': 'Failed to delete nftables'
                                        ' rule for salt.\nAttempted rule was a'
                                        })
                            self.assertDictEqual(nftables.delete('salt',
                                                                 table='',
                                                                 chain='',
                                                                 position=''),
                                                 ret)

    def test_flush(self):
        '''
            Test to flush current nftables state
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': None,
               'comment': ''}
        mock = MagicMock(return_value=[])
        with patch.object(nftables, '_STATE_INTERNAL_KEYWORDS', mock):
            mock = MagicMock(side_effect=[False, True, True, True])
            with patch.dict(nftables.__salt__, {'nftables.check_table': mock}):
                ret.update({'comment': 'Failed to flush table  in family'
                            ' ipv4, table does not exist.',
                            'result': False})
                self.assertDictEqual(nftables.flush('salt',
                                                    table='', chain=''),
                                     ret)

                mock = MagicMock(side_effect=[False, True, True])
                with patch.dict(nftables.__salt__,
                                {'nftables.check_chain': mock}):
                    ret.update({'comment': 'Failed to flush chain  in table'
                                '  in family ipv4, chain does not exist.'})
                    self.assertDictEqual(nftables.flush('salt', table='',
                                                        chain=''), ret)

                    mock = MagicMock(side_effect=[True, False])
                    with patch.dict(nftables.__salt__,
                                    {'nftables.flush': mock}):
                        ret.update({'changes': {'locale': 'salt'},
                                    'comment': 'Flush nftables rules in  table'
                                    '  chain ipv4 family',
                                    'result': True})
                        self.assertDictEqual(nftables.flush('salt', table='',
                                                            chain=''), ret)

                        ret.update({'changes': {},
                                    'comment': 'Failed to flush'
                                    ' nftables rules',
                                    'result': False})
                        self.assertDictEqual(nftables.flush('salt', table='',
                                                            chain=''), ret)
