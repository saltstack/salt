# -*- coding: utf-8 -*-
'''
    :synopsis: Unit Tests for 'module.aptkernelpkg'
    :platform: Linux
    :maturity: develop
    versionadded:: 2018.3.0
'''
# pylint: disable=invalid-name,no-member

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import re

try:
    # Import Salt Testing Libs
    from tests.support.mixins import LoaderModuleMockMixin
    from tests.support.unit import TestCase, skipIf
    from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON

    # Import Salt Libs
    from tests.unit.modules.test_kernelpkg import KernelPkgTestCase
    import salt.modules.kernelpkg_linux_apt as kernelpkg
    from salt.exceptions import CommandExecutionError
    HAS_MODULES = True
except ImportError:
    HAS_MODULES = False


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_MODULES, 'Salt modules could not be loaded')
class AptKernelPkgTestCase(KernelPkgTestCase, TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.kernelpkg_linux_apt
    '''

    _kernelpkg = kernelpkg
    KERNEL_LIST = ['4.4.0-70-generic', '4.4.0-71-generic', '4.5.1-14-generic']
    PACKAGE_DICT = {}

    @classmethod
    def setUpClass(cls):
        version = re.match(r'^(\d+\.\d+\.\d+)-(\d+)', cls.KERNEL_LIST[-1])
        cls.LATEST = '{0}.{1}'.format(version.group(1), version.group(2))

        for kernel in cls.KERNEL_LIST:
            pkg = '{0}-{1}'.format(kernelpkg._package_prefix(), kernel)  # pylint: disable=protected-access
            cls.PACKAGE_DICT[pkg] = pkg

    def setup_loader_modules(self):
        return {
            kernelpkg: {
                '__grains__': {
                    'kernelrelease': self.KERNEL_LIST[0]
                },
                '__salt__': {
                    'pkg.install': MagicMock(return_value={}),
                    'pkg.latest_version': MagicMock(return_value=self.LATEST),
                    'pkg.list_pkgs': MagicMock(return_value=self.PACKAGE_DICT),
                    'pkg.purge': MagicMock(return_value=None),
                    'system.reboot': MagicMock(return_value=None)
                }
            }
        }

    def test_list_installed(self):
        '''
        Test - Return return the latest installed kernel version
        '''
        PACKAGE_LIST = ['{0}-{1}'.format(kernelpkg._package_prefix(), kernel) for kernel in self.KERNEL_LIST]  # pylint: disable=protected-access

        mock = MagicMock(return_value=PACKAGE_LIST)
        with patch.dict(self._kernelpkg.__salt__, {'pkg.list_pkgs': mock}):
            self.assertListEqual(self._kernelpkg.list_installed(), self.KERNEL_LIST)

    def test_list_installed_none(self):
        '''
        Test - Return return the latest installed kernel version
        '''
        mock = MagicMock(return_value=None)
        with patch.dict(self._kernelpkg.__salt__, {'pkg.list_pkgs': mock}):
            self.assertListEqual(self._kernelpkg.list_installed(), [])

    def test_remove_success(self):
        '''
        Test - remove kernel package
        '''
        with patch.object(self._kernelpkg, 'active', return_value=self.KERNEL_LIST[-1]):
            with patch.object(self._kernelpkg, 'list_installed', return_value=self.KERNEL_LIST):
                result = self._kernelpkg.remove(release=self.KERNEL_LIST[0])
                self.assertIn('removed', result)
                target = '{0}-{1}'.format(self._kernelpkg._package_prefix(), self.KERNEL_LIST[0])  # pylint: disable=protected-access
                self.assertListEqual(result['removed'], [target])

    def test_remove_error(self):
        '''
        Test - remove kernel package
        '''
        mock = MagicMock(side_effect=CommandExecutionError())
        with patch.dict(self._kernelpkg.__salt__, {'pkg.purge': mock}):
            with patch.object(self._kernelpkg, 'active', return_value=self.KERNEL_LIST[-1]):
                with patch.object(self._kernelpkg, 'list_installed', return_value=self.KERNEL_LIST):
                    self.assertRaises(CommandExecutionError, self._kernelpkg.remove, release=self.KERNEL_LIST[0])
