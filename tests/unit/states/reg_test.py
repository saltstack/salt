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
    patch
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import reg

reg.__opts__ = {}
reg.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RegTestCase(TestCase):
    '''
    Test cases for salt.states.reg
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to set a registry entry.
        '''
        name = 'HKEY_CURRENT_USER\\SOFTWARE\\Salt\\version'
        value = '0.15.3'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': '{0} is already configured'.format(name)}

        mock = MagicMock(side_effect=[{'vdata': value}, {'vdata': 'a'}, {'vdata': 'a'}])
        mock_t = MagicMock(return_value=True)
        with patch.dict(reg.__salt__, {'reg.read_value': mock,
                                       'reg.set_value': mock_t}):
            self.assertDictEqual(reg.present(name, value), ret)

            with patch.dict(reg.__opts__, {'test': True}):
                ret.update({'comment': '', 'result': None,
                            'changes': {'reg': 'configured to 0.15.3'}})
                self.assertDictEqual(reg.present(name, value), ret)

            with patch.dict(reg.__opts__, {'test': False}):
                ret.update({'result': True})
                self.assertDictEqual(reg.present(name, value), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to remove a registry entry.
        '''
        name = 'HKEY_CURRENT_USER\\SOFTWARE\\Salt\\version'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': '{0} is already absent'.format(name)}

        mock = MagicMock(side_effect=[{'success': False}, {'success': True}, {'success': True}])
        mock_t = MagicMock(return_value=True)
        with patch.dict(reg.__salt__, {'reg.read_value': mock,
                                       'reg.delete_value': mock_t}):
            self.assertDictEqual(reg.absent(name), ret)

            with patch.dict(reg.__opts__, {'test': True}):
                ret.update({'comment': '', 'result': None,
                            'changes': {'reg': 'Removed {0}'.format(name)}})
                self.assertDictEqual(reg.absent(name), ret)

            with patch.dict(reg.__opts__, {'test': False}):
                ret.update({'result': True})
                self.assertDictEqual(reg.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RegTestCase, needs_daemon=False)
