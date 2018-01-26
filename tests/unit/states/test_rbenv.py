# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt Libs
import salt.states.rbenv as rbenv


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RbenvTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.rbenv
    '''
    def setup_loader_modules(self):
        return {rbenv: {}}

    # 'installed' function tests: 1

    def test_installed(self):
        '''
        Test to verify that the specified ruby is installed with rbenv.
        '''
        # rbenv.is_installed is used wherever test is False.
        mock_is = MagicMock(side_effect=[False, True, True, True, True])

        # rbenv.install is only called when an action is attempted
        # (ie. Successfully... or Failed...)
        mock_i = MagicMock(side_effect=[False, False, False])

        # rbenv.install_ruby is only called when rbenv is successfully
        # installed and an attempt to install a version of Ruby is
        # made.
        mock_ir = MagicMock(side_effect=[True, False])
        mock_def = MagicMock(return_value='2.3.4')
        mock_ver = MagicMock(return_value=['2.3.4', '2.4.1'])
        with patch.dict(rbenv.__salt__,
                        {'rbenv.is_installed': mock_is,
                         'rbenv.install': mock_i,
                         'rbenv.default': mock_def,
                         'rbenv.versions': mock_ver,
                         'rbenv.install_ruby': mock_ir}):
            with patch.dict(rbenv.__opts__, {'test': True}):
                name = '1.9.3-p551'
                comt = 'Ruby {0} is set to be installed'.format(name)
                ret = {'name': name, 'changes': {}, 'comment': comt,
                       'result': None}
                self.assertDictEqual(rbenv.installed(name), ret)

                name = '2.4.1'
                comt = 'Ruby {0} is already installed'.format(name)
                ret = {'name': name, 'changes': {}, 'comment': comt,
                       'default': False, 'result': True}
                self.assertDictEqual(rbenv.installed(name), ret)

                name = '2.3.4'
                comt = 'Ruby {0} is already installed'.format(name)
                ret = {'name': name, 'changes': {}, 'comment': comt,
                       'default': True, 'result': True}
                self.assertDictEqual(rbenv.installed(name), ret)

            with patch.dict(rbenv.__opts__, {'test': False}):
                name = '2.4.1'
                comt = 'Rbenv failed to install'
                ret = {'name': name, 'changes': {}, 'comment': comt,
                       'result': False}
                self.assertDictEqual(rbenv.installed(name), ret)

                comt = 'Requested ruby exists'
                ret = {'name': name, 'comment': comt, 'default': False,
                       'changes': {}, 'result': True}
                self.assertDictEqual(rbenv.installed(name), ret)

                name = '2.3.4'
                comt = 'Requested ruby exists'
                ret = {'name': name, 'comment': comt, 'default': True,
                       'changes': {}, 'result': True}
                self.assertDictEqual(rbenv.installed(name), ret)

                name = '1.9.3-p551'
                comt = 'Successfully installed ruby'
                ret = {'name': name, 'comment': comt, 'default': False,
                       'changes': {name: 'Installed'}, 'result': True}
                self.assertDictEqual(rbenv.installed(name), ret)

                comt = 'Failed to install ruby'
                ret = {'name': name, 'comment': comt,
                       'changes': {}, 'result': False}
                self.assertDictEqual(rbenv.installed(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to verify that the specified ruby is not installed with rbenv.
        '''
        # rbenv.is_installed is used for all tests here.
        mock_is = MagicMock(side_effect=[False, True, True, True, False,
                                         True, True, True, True, True])
        # rbenv.uninstall_ruby is only called when an action is
        # attempted (ie. Successfully... or Failed...)
        mock_uninstalled = MagicMock(side_effect=[True, False, False, True])
        mock_def = MagicMock(return_value='2.3.4')
        mock_ver = MagicMock(return_value=['2.3.4', '2.4.1'])
        with patch.dict(rbenv.__salt__,
                        {'rbenv.is_installed': mock_is,
                         'rbenv.default': mock_def,
                         'rbenv.versions': mock_ver,
                         'rbenv.uninstall_ruby': mock_uninstalled}):

            with patch.dict(rbenv.__opts__, {'test': True}):
                name = '1.9.3-p551'
                comt = 'Rbenv not installed, {0} not either'.format(name)
                ret = {'name': name, 'changes': {}, 'comment': comt,
                       'result': True}
                self.assertDictEqual(rbenv.absent(name), ret)

                comt = 'Ruby {0} is already uninstalled'.format(name)
                ret = {'name': name, 'changes': {}, 'comment': comt,
                       'result': True}
                self.assertDictEqual(rbenv.absent(name), ret)

                name = '2.3.4'
                comt = 'Ruby {0} is set to be uninstalled'.format(name)
                ret = {'name': name, 'changes': {}, 'comment': comt,
                       'default': True, 'result': None}
                self.assertDictEqual(rbenv.absent('2.3.4'), ret)

                name = '2.4.1'
                comt = 'Ruby {0} is set to be uninstalled'.format(name)
                ret = {'name': name, 'changes': {}, 'comment': comt,
                       'default': False, 'result': None}
                self.assertDictEqual(rbenv.absent('2.4.1'), ret)

            with patch.dict(rbenv.__opts__, {'test': False}):
                name = '1.9.3-p551'
                comt = 'Rbenv not installed, {0} not either'.format(name)
                ret = {'name': name, 'changes': {}, 'comment': comt,
                       'result': True}
                self.assertDictEqual(rbenv.absent(name), ret)

                comt = 'Ruby {0} is already absent'.format(name)
                ret = {'name': name, 'changes': {}, 'comment': comt,
                       'result': True}
                self.assertDictEqual(rbenv.absent(name), ret)

                name = '2.3.4'
                comt = 'Successfully removed ruby'
                ret = {'name': name, 'changes': {name: 'Uninstalled'},
                       'comment': comt, 'default': True, 'result': True}
                self.assertDictEqual(rbenv.absent(name), ret)

                comt = 'Failed to uninstall ruby'
                ret = {'name': name, 'changes': {}, 'comment': comt,
                       'default': True, 'result': False}
                self.assertDictEqual(rbenv.absent(name), ret)

                name = '2.4.1'
                comt = 'Failed to uninstall ruby'
                ret = {'name': name, 'changes': {}, 'comment': comt,
                       'default': False, 'result': False}
                self.assertDictEqual(rbenv.absent(name), ret)

                comt = 'Successfully removed ruby'
                ret = {'name': name, 'changes': {name: 'Uninstalled'},
                       'comment': comt, 'default': False, 'result': True}
                self.assertDictEqual(rbenv.absent(name), ret)

    # 'install_rbenv' function tests: 1

    def test_install_rbenv(self):
        '''
        Test to install rbenv if not installed.
        '''
        name = 'myqueue'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': ''}

        mock_is = MagicMock(side_effect=[False, True, True, False, False])
        mock_i = MagicMock(side_effect=[False, True])
        with patch.dict(rbenv.__salt__,
                        {'rbenv.is_installed': mock_is,
                         'rbenv.install': mock_i}):

            with patch.dict(rbenv.__opts__, {'test': True}):
                comt = 'Rbenv is set to be installed'
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(rbenv.install_rbenv(name), ret)

                comt = 'Rbenv is already installed'
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(rbenv.install_rbenv(name), ret)

            with patch.dict(rbenv.__opts__, {'test': False}):
                comt = 'Rbenv is already installed'
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(rbenv.install_rbenv(name), ret)

                comt = 'Rbenv failed to install'
                ret.update({'comment': comt, 'result': False})
                self.assertDictEqual(rbenv.install_rbenv(name), ret)

                comt = 'Rbenv installed'
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(rbenv.install_rbenv(name), ret)
