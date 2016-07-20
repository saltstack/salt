# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import ipset

ipset.__salt__ = {}
ipset.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class IpsetTestCase(TestCase):
    '''
    Test cases for salt.states.ipset
    '''
    # 'set_present' function tests: 1

    def test_set_present(self):
        '''
        Test to verify the chain is exist.
        '''
        name = 'salt'
        set_type = {'bitmap': '192.168.0.3'}

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[True, False, False, True, False, ''])
        with patch.dict(ipset.__salt__, {'ipset.check_set': mock,
                                         'ipset.new_set': mock}):
            comt = ('ipset set {0} already exist for ipv4'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(ipset.set_present(name, set_type), ret)

            with patch.dict(ipset.__opts__, {'test': True}):
                comt = ('ipset set {0} needs to added for ipv4'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(ipset.set_present(name, set_type), ret)

            with patch.dict(ipset.__opts__, {'test': False}):
                comt = ('ipset set {0} created successfully for ipv4'
                        .format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {'locale': 'salt'}})
                self.assertDictEqual(ipset.set_present(name, set_type), ret)

                comt = ('Failed to create salt set:  for ipv4')
                ret.update({'comment': comt, 'result': False, 'changes': {}})
                self.assertDictEqual(ipset.set_present(name, set_type), ret)

    # 'set_absent' function tests: 1

    def test_set_absent(self):
        '''
        Test to verify the set is absent.
        '''
        name = 'salt'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[False, True, True, ''])
        with patch.dict(ipset.__salt__, {'ipset.check_set': mock,
                                         'ipset.flush': mock}):
            comt = ('ipset set salt is already absent for family ipv4')
            ret.update({'comment': comt})
            self.assertDictEqual(ipset.set_absent(name), ret)

            with patch.dict(ipset.__opts__, {'test': True}):
                comt = ('ipset set salt needs to be removed family ipv4')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(ipset.set_absent(name), ret)

            with patch.dict(ipset.__opts__, {'test': False}):
                comt = ('Failed to flush salt set:  for ipv4')
                ret.update({'comment': comt, 'result': False, 'changes': {}})
                self.assertDictEqual(ipset.set_absent(name), ret)

    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to append a entry to a set
        '''
        name = 'salt'
        entry = ['192.168.0.3', '192.168.1.3']

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock = MagicMock(return_value=True)
        with patch.dict(ipset.__salt__, {'ipset.check': mock}):
            comt = ('ipset entry must be specified')
            ret.update({'comment': comt})
            self.assertDictEqual(ipset.present(name), ret)

            comt = ('entry for 192.168.0.3 already in set (salt) for ipv4\n'
                    'entry for 192.168.1.3 already in set (salt) for ipv4\n')
#             with patch.dict(ipset.__opts__, {'test': True}):
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(ipset.present(name, entry, set_name='salt'),
                                 ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to remove a entry or entries from a chain
        '''
        name = 'salt'
        entry = ['192.168.0.3', '192.168.1.3']

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[True, False, False])
        with patch.dict(ipset.__salt__, {'ipset.check': mock}):
            comt = ('ipset entry must be specified')
            ret.update({'comment': comt})
            self.assertDictEqual(ipset.absent(name), ret)

            with patch.dict(ipset.__opts__, {'test': True}):
                comt = ('ipset entry 192.168.0.3 needs to removed '
                        'from set salt for family ipv4\n')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(ipset.absent(name, entry, set_name='salt'),
                                     ret)

            comt = ('ipset entry for 192.168.0.3 not present in set (salt) for '
                    'ipv4\nipset entry for 192.168.1.3 not present in set '
                    '(salt) for ipv4\n')
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(ipset.absent(name, entry, set_name='salt'),
                                 ret)

    # 'flush' function tests: 1

    def test_flush(self):
        '''
        Test to flush current ipset set.
        '''
        name = 'salt'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[False, True, True, True])
        mock_f = MagicMock(side_effect=[True, False])
        with patch.dict(ipset.__salt__, {'ipset.check_set': mock,
                                         'ipset.flush': mock_f}):
            comt = ('ipset set {0} does not exist for ipv4'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(ipset.flush(name), ret)

            with patch.dict(ipset.__opts__, {'test': True}):
                comt = ('ipset entries in set {0} family ipv4 needs to '
                        'be flushed'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(ipset.flush(name), ret)

            with patch.dict(ipset.__opts__, {'test': False}):
                comt = ('Flush ipset entries in set {0} family ipv4'
                        .format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {'locale': 'salt'}})
                self.assertDictEqual(ipset.flush(name), ret)

                comt = ('Failed to flush ipset entries')
                ret.update({'comment': comt, 'result': False, 'changes': {}})
                self.assertDictEqual(ipset.flush(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(IpsetTestCase, needs_daemon=False)
