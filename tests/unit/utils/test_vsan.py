# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests functions in salt.utils.vsan
'''

# Import python libraries
from __future__ import absolute_import
import logging

# Import Salt testing libraries
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock, call, \
        PropertyMock

# Import Salt libraries
from salt.exceptions import VMwareApiError, VMwareRuntimeError
from salt.utils import vsan

try:
    from pyVmomi import VmomiSupport, SoapStubAdapter, vim, vmodl
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False
HAS_PYVSAN = vsan.HAS_PYVSAN


# Get Logging Started
log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@skipIf(not HAS_PYVSAN, 'The \'vsan\' ext library is missing')
class VsanSupportedTestCase(TestCase):
    '''Tests for salt.utils.vsan.vsan_supported'''

    def test_supported_api_version(self):
        mock_si = MagicMock(content=MagicMock(about=MagicMock()))
        type(mock_si.content.about).apiVersion = \
                PropertyMock(return_value='6.0')
        self.assertTrue(vsan.vsan_supported(mock_si))

    def test_unsupported_api_version(self):
        mock_si = MagicMock(content=MagicMock(about=MagicMock()))
        type(mock_si.content.about).apiVersion = \
                PropertyMock(return_value='5.0')
        self.assertFalse(vsan.vsan_supported(mock_si))

    def test_api_version_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        mock_si = MagicMock(content=MagicMock(about=MagicMock()))
        type(mock_si.content.about).apiVersion = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            vsan.vsan_supported(mock_si)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_api_version_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        mock_si = MagicMock(content=MagicMock(about=MagicMock()))
        type(mock_si.content.about).apiVersion = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            vsan.vsan_supported(mock_si)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_api_version_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        mock_si = MagicMock(content=MagicMock(about=MagicMock()))
        type(mock_si.content.about).apiVersion = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            vsan.vsan_supported(mock_si)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')
