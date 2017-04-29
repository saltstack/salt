# -*- coding: utf-8 -*-
'''
    :synopsis: Unit Tests for 'module.yumkernelpkg'
    :platform: Linux
    :maturity: develop
    versionadded:: oxygen
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON

# Import Salt Libs
from tests.unit.modules.test_kernelpkg import KernelPkgTestCase
import salt.modules.yumkernelpkg as kernelpkg
import salt.modules.yumpkg as pkg


@skipIf(NO_MOCK, NO_MOCK_REASON)
class YumKernelPkgTestCase(KernelPkgTestCase, TestCase, LoaderModuleMockMixin):

    _kernelpkg = kernelpkg
    KERNEL_LIST = ['3.10.0-327.el7', '3.11.0-327.el7', '4.9.1-100.el7']
    LATEST = KERNEL_LIST[-1]
    OS_ARCH = 'x86_64'

    def setup_loader_modules(self):
        return {
            kernelpkg: {
                '__grains__': {
                    'kernelrelease': '{0}.{1}'.format(self.KERNEL_LIST[0], self.OS_ARCH)
                },
                '__salt__': {
                    'pkg.normalize_name': pkg.normalize_name,
                    'pkg.upgrade': MagicMock(return_value={}),
                    'system.reboot': MagicMock(return_value=None)
                }
            },
            pkg: {
                '__grains__': {
                    'osarch': self.OS_ARCH
                }
            }
        }

    def test_list_installed(self):
        '''
        Test - Return the latest installed kernel version
        '''
        mock = MagicMock(return_value=self.KERNEL_LIST)
        with patch.dict(self._kernelpkg.__salt__, {'pkg.version': mock}):
            self.assertListEqual(self._kernelpkg.list_installed(), self.KERNEL_LIST)

    def test_list_installed_none(self):
        '''
        Test - Return the latest installed kernel version
        '''
        mock = MagicMock(return_value=None)
        with patch.dict(self._kernelpkg.__salt__, {'pkg.version': mock}):
            self.assertListEqual(self._kernelpkg.list_installed(), [])
