# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt Libs
from salt.states import rbenv

rbenv.__opts__ = {}
rbenv.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RbenvTestCase(TestCase):
    '''
    Test cases for salt.states.rbenv
    '''
    # 'installed' function tests: 1

    def test_installed(self):
        '''
        Test to verify that the specified ruby is installed with rbenv.
        '''
        name = 'rbenv-deps'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': ''}

        mock_t = MagicMock(side_effect=[False, True, True])
        mock_f = MagicMock(return_value=False)
        mock_def = MagicMock(return_value='2.7')
        mock_ver = MagicMock(return_value=['2.7'])
        with patch.dict(rbenv.__salt__,
                        {'rbenv.is_installed': mock_f,
                         'rbenv.install': mock_t,
                         'rbenv.default': mock_def,
                         'rbenv.versions': mock_ver,
                         'rbenv.install_ruby': mock_t}):
            with patch.dict(rbenv.__opts__, {'test': True}):
                comt = ('Ruby rbenv-deps is set to be installed')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(rbenv.installed(name), ret)

            with patch.dict(rbenv.__opts__, {'test': False}):
                comt = ('Rbenv failed to install')
                ret.update({'comment': comt, 'result': False})
                self.assertDictEqual(rbenv.installed(name), ret)

                comt = ('Successfully installed ruby')
                ret.update({'comment': comt, 'result': True, 'default': False,
                            'changes': {name: 'Installed'}})
                self.assertDictEqual(rbenv.installed(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to verify that the specified ruby is not installed with rbenv.
        '''
        name = 'myqueue'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': ''}

        mock = MagicMock(side_effect=[False, True])
        mock_def = MagicMock(return_value='2.7')
        mock_ver = MagicMock(return_value=['2.7'])
        with patch.dict(rbenv.__salt__,
                        {'rbenv.is_installed': mock,
                         'rbenv.default': mock_def,
                         'rbenv.versions': mock_ver}):
            with patch.dict(rbenv.__opts__, {'test': True}):
                comt = ('Ruby myqueue is set to be uninstalled')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(rbenv.absent(name), ret)

            with patch.dict(rbenv.__opts__, {'test': False}):
                comt = ('Rbenv not installed, myqueue not either')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(rbenv.absent(name), ret)

                comt = ('Ruby myqueue is already absent')
                ret.update({'comment': comt, 'result': True})
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

        with patch.dict(rbenv.__opts__, {'test': True}):
            comt = ('Rbenv is set to be installed')
            ret.update({'comment': comt, 'result': None})
            self.assertDictEqual(rbenv.install_rbenv(name), ret)

        with patch.dict(rbenv.__opts__, {'test': False}):
            mock = MagicMock(side_effect=[False, True])
            with patch.dict(rbenv.__salt__,
                            {'rbenv.is_installed': mock,
                             'rbenv.install': mock}):
                comt = ('Rbenv installed')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(rbenv.install_rbenv(name), ret)
