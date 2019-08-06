# -*- coding: utf-8 -*-
'''
Tests for the win_pkg module
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

# Import Salt Libs
import salt.modules.pkg_resource as pkg_resource
import salt.modules.win_pkg as win_pkg
import salt.utils.platform
import salt.utils.win_reg as win_reg

# Import 3rd Party Libs
from salt.ext import six


@skipIf(not salt.utils.platform.is_windows(), "Must be on Windows!")
class WinPkgInstallTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.win_pkg
    '''
    def setup_loader_modules(self):
        pkg_info = {
            '3.03': {
                'full_name': 'Nullsoft Install System',
                'installer': 'http://download.sourceforge.net/project/nsis/NSIS%203/3.03/nsis-3.03-setup.exe',
                'install_flags': '/S',
                'uninstaller': '%PROGRAMFILES(x86)%\\NSIS\\uninst-nsis.exe',
                'uninstall_flags': '/S',
                'msiexec': False,
                'reboot': False
            },
            '3.02': {
                'full_name': 'Nullsoft Install System',
                'installer': 'http://download.sourceforge.net/project/nsis/NSIS%203/3.02/nsis-3.02-setup.exe',
                'install_flags': '/S',
                'uninstaller': '%PROGRAMFILES(x86)%\\NSIS\\uninst-nsis.exe',
                'uninstall_flags': '/S',
                'msiexec': False,
                'reboot': False
            }
        }

        return{
            win_pkg: {
                '_get_latest_package_version': MagicMock(return_value='3.03'),
                '_get_package_info': MagicMock(return_value=pkg_info),
                '__salt__': {
                    'pkg_resource.add_pkg': pkg_resource.add_pkg,
                    'pkg_resource.parse_targets': pkg_resource.parse_targets,
                    'pkg_resource.sort_pkglist': pkg_resource.sort_pkglist,
                    'pkg_resource.stringify': pkg_resource.stringify,
                },
                '__utils__': {
                    'reg.key_exists': win_reg.key_exists,
                    'reg.list_keys': win_reg.list_keys,
                    'reg.read_value': win_reg.read_value,
                    'reg.value_exists': win_reg.value_exists,
                },
            },
            pkg_resource: {
                '__grains__': {
                    'os': 'Windows'
                }
            },
        }

    def test_pkg__get_reg_software(self):
        result = win_pkg._get_reg_software()
        self.assertTrue(isinstance(result, dict))
        found_python = False
        search = 'Python 2' if six.PY2 else 'Python 3'
        for key in result:
            if search in key:
                found_python = True
        self.assertTrue(found_python)

    def test_pkg_install_not_found(self):
        '''
        Test pkg.install when the Version is NOT FOUND in the Software
        Definition
        '''
        ret_reg = {'Nullsoft Install System': '3.03'}
        # The 2nd time it's run with stringify
        se_list_pkgs = {'nsis': ['3.03']}
        with patch.object(win_pkg, 'list_pkgs', return_value=se_list_pkgs), \
                patch.object(win_pkg, '_get_reg_software', return_value=ret_reg):
            expected = {'nsis': {'not found': '3.01'}}
            result = win_pkg.install(name='nsis', version='3.01')
            self.assertDictEqual(expected, result)

    def test_pkg_install_rollback(self):
        '''
        test pkg.install rolling back to a previous version
        '''
        ret_reg = {'Nullsoft Install System': '3.03'}
        # The 2nd time it's run, pkg.list_pkgs uses with stringify
        se_list_pkgs = [{'nsis': ['3.03']},
                        {'nsis': '3.02'}]
        with patch.object(win_pkg, 'list_pkgs', side_effect=se_list_pkgs), \
                patch.object(
                    win_pkg, '_get_reg_software', return_value=ret_reg), \
                patch.dict(
                    win_pkg.__salt__,
                    {'cp.is_cached': MagicMock(return_value=False)}), \
                patch.dict(
                    win_pkg.__salt__,
                    {'cp.cache_file':
                         MagicMock(return_value='C:\\fake\\path.exe')}), \
                patch.dict(
                    win_pkg.__salt__,
                    {'cmd.run_all':
                         MagicMock(return_value={'retcode': 0})}):
            expected = {'nsis': {'new': '3.02', 'old': '3.03'}}
            result = win_pkg.install(name='nsis', version='3.02')
            self.assertDictEqual(expected, result)

    def test_pkg_install_existing(self):
        '''
        test pkg.install when the package is already installed
        no version passed
        '''
        ret_reg = {'Nullsoft Install System': '3.03'}
        # The 2nd time it's run, pkg.list_pkgs uses with stringify
        se_list_pkgs = {'nsis': ['3.03']}
        with patch.object(win_pkg, 'list_pkgs', return_value=se_list_pkgs), \
                patch.object(
                    win_pkg, '_get_reg_software', return_value=ret_reg), \
                patch.dict(
                    win_pkg.__salt__,
                    {'cp.is_cached': MagicMock(return_value=False)}), \
                patch.dict(
                    win_pkg.__salt__,
                    {'cp.cache_file':
                         MagicMock(return_value='C:\\fake\\path.exe')}), \
                patch.dict(
                    win_pkg.__salt__,
                    {'cmd.run_all':
                         MagicMock(return_value={'retcode': 0})}):
            expected = {}
            result = win_pkg.install(name='nsis')
            self.assertDictEqual(expected, result)

    def test_pkg_install_existing_with_version(self):
        '''
        test pkg.install when the package is already installed
        A version is passed
        '''
        ret_reg = {'Nullsoft Install System': '3.03'}
        # The 2nd time it's run, pkg.list_pkgs uses with stringify
        se_list_pkgs = {'nsis': ['3.03']}
        with patch.object(win_pkg, 'list_pkgs', return_value=se_list_pkgs), \
                patch.object(
                    win_pkg, '_get_reg_software', return_value=ret_reg), \
                patch.dict(
                    win_pkg.__salt__,
                    {'cp.is_cached': MagicMock(return_value=False)}), \
                patch.dict(
                    win_pkg.__salt__,
                    {'cp.cache_file':
                         MagicMock(return_value='C:\\fake\\path.exe')}), \
                patch.dict(
                    win_pkg.__salt__,
                    {'cmd.run_all':
                         MagicMock(return_value={'retcode': 0})}):
            expected = {}
            result = win_pkg.install(name='nsis', version='3.03')
            self.assertDictEqual(expected, result)
