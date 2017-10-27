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
from salt.states import selinux

selinux.__opts__ = {}
selinux.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SelinuxTestCase(TestCase):
    '''
    Test cases for salt.states.selinux
    '''
    # 'mode' function tests: 1

    def test_mode(self):
        '''
        Test to verifies the mode SELinux is running in,
        can be set to enforcing or permissive.
        '''
        ret = {'name': 'unknown',
               'changes': {},
               'result': False,
               'comment': 'unknown is not an accepted mode'}
        self.assertDictEqual(selinux.mode('unknown'), ret)

        mock_en = MagicMock(return_value='Enforcing')
        mock_pr = MagicMock(side_effect=['Permissive', 'Enforcing'])
        with patch.dict(selinux.__salt__,
                        {'selinux.getenforce': mock_en,
                         'selinux.getconfig': mock_en,
                         'selinux.setenforce': mock_pr}):
            comt = ('SELinux is already in Enforcing mode')
            ret = {'name': 'Enforcing', 'comment': comt, 'result': True, 'changes': {}}
            self.assertDictEqual(selinux.mode('Enforcing'), ret)

            with patch.dict(selinux.__opts__, {'test': True}):
                comt = ('SELinux mode is set to be changed to Permissive')
                ret = {'name': 'Permissive', 'comment': comt,
                       'result': None, 'changes': {'new': 'Permissive', 'old': 'Enforcing'}}
                self.assertDictEqual(selinux.mode('Permissive'), ret)

            with patch.dict(selinux.__opts__, {'test': False}):
                comt = ('SELinux has been set to Permissive mode')
                ret = {'name': 'Permissive', 'comment': comt,
                       'result': True, 'changes': {'new': 'Permissive', 'old': 'Enforcing'}}
                self.assertDictEqual(selinux.mode('Permissive'), ret)

                comt = ('Failed to set SELinux to Permissive mode')
                ret.update({'name': 'Permissive', 'comment': comt,
                            'result': False, 'changes': {}})
                self.assertDictEqual(selinux.mode('Permissive'), ret)

    # 'boolean' function tests: 1

    def test_boolean(self):
        '''
        Test to set up an SELinux boolean.
        '''
        name = 'samba_create_home_dirs'
        value = True
        ret = {'name': name,
               'changes': {},
               'result': False,
               'comment': ''}

        mock_en = MagicMock(return_value=[])
        with patch.dict(selinux.__salt__,
                        {'selinux.list_sebool': mock_en}):
            comt = ('Boolean {0} is not available'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(selinux.boolean(name, value), ret)

        mock_bools = MagicMock(return_value={name: {'State': 'on',
                                                    'Default': 'on'}})
        with patch.dict(selinux.__salt__,
                        {'selinux.list_sebool': mock_bools}):
            comt = ('None is not a valid value for the boolean')
            ret.update({'comment': comt})
            self.assertDictEqual(selinux.boolean(name, None), ret)

            comt = ('Boolean is in the correct state')
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(selinux.boolean(name, value, True), ret)

            comt = ('Boolean is in the correct state')
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(selinux.boolean(name, value), ret)

        mock_bools = MagicMock(return_value={name: {'State': 'off',
                                                    'Default': 'on'}})
        mock = MagicMock(side_effect=[True, False])
        with patch.dict(selinux.__salt__,
                        {'selinux.list_sebool': mock_bools,
                         'selinux.setsebool': mock}):
            with patch.dict(selinux.__opts__, {'test': True}):
                comt = ('Boolean samba_create_home_dirs'
                        ' is set to be changed to on')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(selinux.boolean(name, value), ret)

            with patch.dict(selinux.__opts__, {'test': False}):
                comt = ('Boolean samba_create_home_dirs has been set to on')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(selinux.boolean(name, value), ret)

                comt = ('Failed to set the boolean '
                        'samba_create_home_dirs to on')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(selinux.boolean(name, value), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SelinuxTestCase, needs_daemon=False)
