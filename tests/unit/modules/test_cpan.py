# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import os.path

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)
from tests.support.unit import TestCase, skipIf

# Import Salt Libs
import salt.modules.cpan as cpan
import salt.utils.path


@skipIf(NO_MOCK, NO_MOCK_REASON)
class CpanTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.cpan
    '''

    # 'install' function tests: 2

    def setup_loader_modules(self):
        return {cpan: {}}

    @staticmethod
    def _patch_binary(func, *args, **kwargs):
        with patch.object(salt.utils.path, 'which', MagicMock(return_value='/usr/bin/cpan')):
            with patch.object(cpan, '_configure', MagicMock(return_value=True)):
                return func(*args, **kwargs)

    def test__get_binary_no_env(self):
        # Verify that the name of the default cpan executable starts with 'cpan'
        bin_path = self._patch_binary(cpan._get_cpan_bin)
        self.assertEqual('cpan', os.path.split(bin_path)[-1])

    def test__get_binary(self):
        # Verify that the name of the default cpan executable starts with 'cpan'
        bin_path = self._patch_binary(cpan._get_cpan_bin, 'cpan')
        self.assertEqual('cpan', os.path.split(bin_path)[-1])

    def test__configure(self):
        with patch.dict(cpan.__salt__, {'cmd.run_all': MagicMock(return_value={'retcode': 0})}):
            self.assertTrue(cpan._configure("/usr/bin/cpan"))

    def test__configure_fail(self):
        with patch.dict(cpan.__salt__, {'cmd.run_all': MagicMock(return_value={'retcode': 1})}):
            self.assertFalse(cpan._configure("/usr/bin/cpan"))

    def test_get_version(self):
        mock = MagicMock(return_value={
                'installed version': '2.26',
                'installed file': "",
                'cpan build dirs': []
            }
        )
        with patch.object(cpan, 'show', mock):
            self.assertEqual(cpan.version(), "2.26")

    def test_install(self):
        '''
        Test if it install a module from cpan
        '''
        module = 'Template::Alloy'
        mock1 = MagicMock(return_value={'retval': 0})
        with patch.dict(cpan.__salt__, {'cmd.run_all': mock1}):
            mock = MagicMock(side_effect=[{'installed version': None},
                                          {'installed version': '3.1'}])
            with patch.object(cpan, 'show', mock):
                self.assertDictEqual(cpan.install(module), {
                    'new': {'installed version': '3.1'},
                    'old': {'installed version': None},
                    'error': None})
                self.assertIn("-i", mock1.call_args[0][0])
                self.assertIn(module, mock1.call_args[0][0])

    def test_install_mirror(self):
        mock = MagicMock(return_value={'retval': 0})
        mirrors = ['ftp://mirror1.org', 'http://mirror2.org']
        with patch.dict(cpan.__salt__, {'cmd.run_all': mock}):
            with patch.object(cpan, 'show', MagicMock()):
                # Pass a list of mirrors
                cpan.install('Module', mirror=mirrors, bin_env='')
                self.assertIn("-M", mock.call_args[0][0])
                self.assertIn(",".join(mirrors), mock.call_args[0][0])

                # Same test but pass a string instead of a list
                cpan.install('Module', mirror=",".join(mirrors), bin_env='')
                self.assertIn(",".join(mirrors), mock.call_args[0][0])

    def test_install_notest(self):
        mock = MagicMock(return_value={'retval': 0})
        with patch.dict(cpan.__salt__, {'cmd.run_all': mock}):
            with patch.object(cpan, 'show', MagicMock()):
                # Pass a list of mirrors
                cpan.install('Module', notest=True)
                self.assertIn("-T", mock.call_args[0][0])

    def test_install_force(self):
        mock = MagicMock(return_value={'retval': 0})
        with patch.dict(cpan.__salt__, {'cmd.run_all': mock}):
            with patch.object(cpan, 'show', MagicMock()):
                # Pass a list of mirrors
                cpan.install('Module', force=True)
                self.assertIn("-f", mock.call_args[0][0])

    def test_install_error(self):
        '''
        Test if it install a module from cpan
        '''
        mock = MagicMock(return_value={'retval': 1})
        module = 'Template::Alloy'
        with patch.dict(cpan.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(cpan.install(module), {
                'error': 'Could not find package {}'.format(module),
                'new': {},
                'old': {}})

    # 'remove' function tests: 4
    def test_remove(self):
        '''
        Test if it remove a module using cpan
        '''
        with patch('os.listdir', MagicMock(return_value=[''])):
            mock = MagicMock(return_value={})
            module = 'Template::Alloy'
            with patch.dict(cpan.__salt__, {'cmd.run_all': mock}):
                mock = MagicMock(return_value={'installed version': '2.1',
                                               'cpan build dirs': [''],
                                               'installed file': '/root'})
                with patch.object(cpan, 'show', mock):
                    self.assertDictEqual(cpan.remove(module), {
                        'error': None,
                        'new': None,
                        'old': None})

    def test_remove_unexist_error(self):
        '''
        Test if it try to remove an unexist module using cpan
        '''
        mock = MagicMock(return_value={'error': ""})
        module = 'Nonexistant::Package'
        with patch.dict(cpan.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(cpan.remove(module), {
                'error': 'Could not find package {}'.format(module),
                'new': None,
                'old': None})

    def test_remove_noninstalled_error(self):
        '''
        Test if it remove non installed module using cpan
        '''
        mock = MagicMock(return_value={'installed version': None})
        with patch.object(cpan, 'show', mock):
            self.assertDictEqual(cpan.remove('Template::Alloy'), {
                'error': None,
                'new': None,
                'old': None})

    def test_remove_nopan_error(self):
        '''
        Test if it gives no cpan error while removing,
        If nothing has changed then an empty dictionary will be returned
        '''
        mock = MagicMock(return_value={'installed version': '2.1',
                                       'installed file': "",
                                       'cpan build dirs': []})
        with patch.object(cpan, 'show', mock):
            self.assertDictEqual(cpan.remove('Template::Alloy'), {
                'error': None,
                'new': None,
                'old': None})

    # 'list' function tests: 1
    def test_list(self):
        '''
        Test if it list installed Perl module
        '''
        mock = MagicMock(return_value={})
        with patch.dict(cpan.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(cpan.list_(), {})

    # 'show' function tests: 2
    def test_show(self):
        '''
        Test if it show information about a specific Perl module
        '''
        mock = MagicMock(return_value={})
        with patch.dict(cpan.__salt__,
                        {'cmd.run_all': mock,
                         'cpan._grt_bin_env': 'cpan'}):
            module = 'Nonexistant::Package'
            self.assertDictEqual(cpan.show(module),
                                 {'error':
                                      'Could not find package {}'.format(
                                          module),
                                  'name': module})

    def test_show_mock(self):
        '''
        Test if it show information about a specific Perl module
        '''
        with patch('salt.modules.cpan.show',
                   MagicMock(return_value={'Salt': 'salt'})):
            mock = MagicMock(return_value='Salt module installed')
            with patch.dict(cpan.__salt__, {'cmd.run_all': mock}):
                self.assertDictEqual(cpan.show('Template::Alloy'),
                                     {'Salt': 'salt'})

    # 'show' function tests: 1
    def test_config(self):
        '''
        Test if it return a dict of CPAN configuration values
        '''
        mock = MagicMock(return_value={})
        with patch.dict(cpan.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(cpan.config(), {})
