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
        name = 'HKEY_CURRENT_USER\\SOFTWARE\\Salt'
        vname = 'version'
        vdata = '0.15.3'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': '{0} in {1} is already configured'.format(vname, name)}

        mock_read = MagicMock(side_effect=[{'vdata': vdata, 'success': True},
                                           {'vdata': 'a', 'success': True},
                                           {'vdata': 'a', 'success': True}])
        mock_t = MagicMock(return_value=True)
        with patch.dict(reg.__salt__, {'reg.read_value': mock_read,
                                       'reg.set_value': mock_t}):
            self.assertDictEqual(reg.present(name,
                                             vname=vname,
                                             vdata=vdata), ret)

            with patch.dict(reg.__opts__, {'test': True}):
                ret.update({'comment': '', 'result': None,
                            'changes': {'reg': {'Will add': {'Key': name,
                                                             'Entry': vname,
                                                             'Value': vdata}}}})
                self.assertDictEqual(reg.present(name,
                                                 vname=vname,
                                                 vdata=vdata), ret)

            with patch.dict(reg.__opts__, {'test': False}):
                ret.update({'comment': 'Added {0} to {0}'.format(name),
                            'result': True,
                            'changes': {'reg': {'Added': {'Key': name,
                                                          'Entry': vname,
                                                          'Value': vdata}}}})
                self.assertDictEqual(reg.present(name,
                                                 vname=vname,
                                                 vdata=vdata), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to remove a registry entry.
        '''
        hive = 'HKEY_CURRENT_USER'
        key = 'SOFTWARE\\Salt'
        name = hive + '\\' + key
        vname = 'version'
        vdata = '0.15.3'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': '{0} is already absent'.format(name)}

        mock_read_true = MagicMock(return_value={'success': True, 'vdata': vdata})
        mock_read_false = MagicMock(return_value={'success': False, 'vdata': False})

        mock_t = MagicMock(return_value=True)
        with patch.dict(reg.__salt__, {'reg.read_value': mock_read_false,
                                       'reg.delete_value': mock_t}):
            self.assertDictEqual(reg.absent(name, vname), ret)

        with patch.dict(reg.__salt__, {'reg.read_value': mock_read_true}):
            with patch.dict(reg.__opts__, {'test': True}):
                ret.update({'comment': '', 'result': None,
                            'changes': {'reg': {'Will remove': {'Entry': vname, 'Key': name}}}})
                self.assertDictEqual(reg.absent(name, vname), ret)

        with patch.dict(reg.__salt__, {'reg.read_value': mock_read_true,
                                       'reg.delete_value': mock_t}):
            with patch.dict(reg.__opts__, {'test': False}):
                ret.update({'result': True,
                            'changes': {'reg': {'Removed': {'Entry': vname, 'Key': name}}},
                            'comment': 'Removed {0} from {1}'.format(key, hive)})
                self.assertDictEqual(reg.absent(name, vname), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RegTestCase, needs_daemon=False)
