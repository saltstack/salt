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
from salt.states import pyenv

pyenv.__opts__ = {}
pyenv.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PyenvTestCase(TestCase):
    '''
    Test cases for salt.states.pyenv
    '''
    # 'installed' function tests: 1

    def test_installed(self):
        '''
        Test to verify that the specified python is installed with pyenv.
        '''
        name = 'python-2.7.6'

        ret = {'name': name,
               'changes': {},
               'result': None,
               'comment': ''}

        with patch.dict(pyenv.__opts__, {'test': True}):
            comt = ('python 2.7.6 is set to be installed')
            ret.update({'comment': comt})
            self.assertDictEqual(pyenv.installed(name), ret)

        with patch.dict(pyenv.__opts__, {'test': False}):
            mock_f = MagicMock(side_effect=[False, False, True])
            mock_fa = MagicMock(side_effect=[False, True])
            mock_str = MagicMock(return_value='2.7.6')
            mock_lst = MagicMock(return_value=['2.7.6'])
            with patch.dict(pyenv.__salt__, {'pyenv.is_installed': mock_f,
                                             'pyenv.install': mock_fa,
                                             'pyenv.default': mock_str,
                                             'pyenv.versions': mock_lst}):
                comt = ('pyenv failed to install')
                ret.update({'comment': comt, 'result': False})
                self.assertDictEqual(pyenv.installed(name), ret)

                comt = ('Requested python exists.')
                ret.update({'comment': comt, 'result': True, 'default': True})
                self.assertDictEqual(pyenv.installed(name), ret)

                self.assertDictEqual(pyenv.installed(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to verify that the specified python is not installed with pyenv.
        '''
        name = 'python-2.7.6'

        ret = {'name': name,
               'changes': {},
               'result': None,
               'comment': ''}

        with patch.dict(pyenv.__opts__, {'test': True}):
            comt = ('python 2.7.6 is set to be uninstalled')
            ret.update({'comment': comt})
            self.assertDictEqual(pyenv.absent(name), ret)

        with patch.dict(pyenv.__opts__, {'test': False}):
            mock_f = MagicMock(side_effect=[False, True])
            mock_t = MagicMock(return_value=True)
            mock_str = MagicMock(return_value='2.7.6')
            mock_lst = MagicMock(return_value=['2.7.6'])
            with patch.dict(pyenv.__salt__, {'pyenv.is_installed': mock_f,
                                             'pyenv.uninstall_python': mock_t,
                                             'pyenv.default': mock_str,
                                             'pyenv.versions': mock_lst}):
                comt = ('pyenv not installed, 2.7.6 not either')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(pyenv.absent(name), ret)

                comt = ('Successfully removed python')
                ret.update({'comment': comt, 'result': True, 'default': True,
                            'changes': {'2.7.6': 'Uninstalled'}})
                self.assertDictEqual(pyenv.absent(name), ret)

    # 'install_pyenv' function tests: 1

    def test_install_pyenv(self):
        '''
        Test to install pyenv if not installed.
        '''
        name = 'python-2.7.6'

        ret = {'name': name,
               'changes': {},
               'result': None,
               'comment': ''}

        with patch.dict(pyenv.__opts__, {'test': True}):
            comt = ('pyenv is set to be installed')
            ret.update({'comment': comt})
            self.assertDictEqual(pyenv.install_pyenv(name), ret)

        with patch.dict(pyenv.__opts__, {'test': False}):
            mock_t = MagicMock(return_value=True)
            mock_str = MagicMock(return_value='2.7.6')
            mock_lst = MagicMock(return_value=['2.7.6'])
            with patch.dict(pyenv.__salt__, {'pyenv.install_python': mock_t,
                                             'pyenv.default': mock_str,
                                             'pyenv.versions': mock_lst}):
                comt = ('Successfully installed python')
                ret.update({'comment': comt, 'result': True, 'default': False,
                            'changes': {None: 'Installed'}})
                self.assertDictEqual(pyenv.install_pyenv(name), ret)
