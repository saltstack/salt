# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.modules.rbenv as rbenv


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RbenvTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.rbenv
    '''
    def setup_loader_modules(self):
        return {rbenv: {}}

    def test_install(self):
        '''
        Test for install Rbenv systemwide
        '''
        with patch.object(rbenv, '_rbenv_path', return_value=True):
            with patch.object(rbenv, '_install_rbenv', return_value=True):
                with patch.object(rbenv, '_install_ruby_build',
                                  return_value=True):
                    with patch.object(os.path, 'expanduser', return_value='A'):
                        self.assertTrue(rbenv.install())

    def test_update(self):
        '''
        Test for updates the current versions of Rbenv and Ruby-Build
        '''
        with patch.object(rbenv, '_rbenv_path', return_value=True):
            with patch.object(rbenv, '_update_rbenv', return_value=True):
                with patch.object(rbenv, '_update_ruby_build',
                                  return_value=True):
                    with patch.object(os.path, 'expanduser', return_value='A'):
                        self.assertTrue(rbenv.update())

    def test_is_installed(self):
        '''
        Test for check if Rbenv is installed.
        '''
        with patch.object(rbenv, '_rbenv_bin', return_value='A'):
            with patch.dict(rbenv.__salt__,
                            {'cmd.has_exec': MagicMock(return_value=True)}):
                self.assertTrue(rbenv.is_installed())

    def test_install_ruby(self):
        '''
        Test for install a ruby implementation.
        '''
        with patch.dict(rbenv.__grains__, {'os': 'FreeBSD'}):
            with patch.dict(rbenv.__salt__,
                            {'config.get': MagicMock(return_value='True')}):
                with patch.object(rbenv, '_rbenv_exec',
                                  return_value={'retcode': 0,
                                                'stderr': 'stderr'}):
                    with patch.object(rbenv, 'rehash', return_value=None):
                        self.assertEqual(rbenv.install_ruby('ruby'), 'stderr')

                with patch.object(rbenv, '_rbenv_exec',
                                  return_value={'retcode': 1,
                                                'stderr': 'stderr'}):
                    with patch.object(rbenv, 'uninstall_ruby',
                                      return_value=None):
                        self.assertFalse(rbenv.install_ruby('ruby'))

    def test_uninstall_ruby(self):
        '''
        Test for uninstall a ruby implementation.
        '''
        with patch.object(rbenv, '_rbenv_exec', return_value=None):
            self.assertTrue(rbenv.uninstall_ruby('ruby', 'runas'))

    def test_versions(self):
        '''
        Test for list the installed versions of ruby.
        '''
        with patch.object(rbenv, '_rbenv_exec', return_value='A\nBC\nD'):
            self.assertListEqual(rbenv.versions(), ['A', 'BC', 'D'])

    def test_default(self):
        '''
        Test for returns or sets the currently defined default ruby.
        '''
        with patch.object(rbenv, '_rbenv_exec',
                          MagicMock(side_effect=[None, False])):
            self.assertTrue(rbenv.default('ruby', 'runas'))

            self.assertEqual(rbenv.default(), '')

    def test_list_(self):
        '''
        Test for list the installable versions of ruby.
        '''
        with patch.object(rbenv, '_rbenv_exec', return_value='A\nB\nCD\n'):
            self.assertListEqual(rbenv.list_(), ['A', 'B', 'CD'])

    def test_rehash(self):
        '''
        Test for run rbenv rehash to update the installed shims.
        '''
        with patch.object(rbenv, '_rbenv_exec', return_value=None):
            self.assertTrue(rbenv.rehash())

    def test_do_with_ruby(self):
        '''
        Test for execute a ruby command with rbenv's shims using a
        specific ruby version.
        '''
        with patch.object(rbenv, 'do', return_value='A'):
            self.assertEqual(rbenv.do_with_ruby('ruby', 'cmdline'), 'A')
