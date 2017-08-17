# -*- coding: utf-8 -*-
'''
    :synopsis: Unit Tests for 'module.aptkernelpkg'
    :platform: Linux
    :maturity: develop
    versionadded:: oxygen
'''

# Import Python Libs
from __future__ import absolute_import
import re

try:
    # Import Salt Testing Libs
    from tests.support.mixins import LoaderModuleMockMixin
    from tests.support.unit import TestCase, skipIf
    from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON

    # Import Salt Libs
    from tests.unit.modules.test_kernelpkg import KernelPkgTestCase
    import salt.modules.kernelpkg_linux_apt as kernelpkg
    HAS_MODULES = True
except ImportError:
    HAS_MODULES = False


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_MODULES, 'Salt modules could not be loaded')
class AptKernelPkgTestCase(KernelPkgTestCase, TestCase, LoaderModuleMockMixin):

    _kernelpkg = kernelpkg
    KERNEL_LIST = ['4.4.0-70-generic', '4.4.0-71-generic', '4.5.1-14-generic']
    PACKAGE_DICT = {}

    @classmethod
    def setUpClass(cls):
        version = re.match(r'^(\d+\.\d+\.\d+)-(\d+)', cls.KERNEL_LIST[-1])
        cls.LATEST = '{0}.{1}'.format(version.group(1), version.group(2))

        for kernel in cls.KERNEL_LIST:
            pkg = '{0}-{1}'.format(kernelpkg._package_prefix(), kernel)
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
                    'system.reboot': MagicMock(return_value=None)
                }
            }
        }

    def test_list_installed(self):
        '''
        Test - Return return the latest installed kernel version
        '''
        PACKAGE_LIST = ['{0}-{1}'.format(kernelpkg._package_prefix(), kernel) for kernel in self.KERNEL_LIST]

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
