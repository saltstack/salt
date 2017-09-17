# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for license related functions in salt.utils.vmware
'''

# Import python libraries
from __future__ import absolute_import
import logging

# Import Salt testing libraries
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock, call, \
        PropertyMock


# Import Salt libraries
import salt.utils.vmware
from salt.exceptions import VMwareObjectRetrievalError, VMwareApiError, \
        VMwareRuntimeError

# Import Third Party Libs
try:
    from pyVmomi import vim, vmodl
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

# Get Logging Started
log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetLicenseManagerTestCase(TestCase):
    '''Tests for salt.utils.vmware.get_license_manager'''

    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_lic_mgr = MagicMock()
        type(self.mock_si.content).licenseManager = PropertyMock(
            return_value=self.mock_lic_mgr)

    def tearDown(self):
        for attr in ('mock_si', 'mock_lic_mgr'):
            delattr(self, attr)

    def test_raise_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        type(self.mock_si.content).licenseManager = PropertyMock(
            side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.get_license_manager(self.mock_si)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        type(self.mock_si.content).licenseManager = PropertyMock(
            side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.get_license_manager(self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        type(self.mock_si.content).licenseManager = PropertyMock(
            side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.vmware.get_license_manager(self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_valid_assignment_manager(self):
        ret = salt.utils.vmware.get_license_manager(self.mock_si)
        self.assertEqual(ret, self.mock_lic_mgr)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetLicenseAssignmentManagerTestCase(TestCase):
    '''Tests for salt.utils.vmware.get_license_assignment_manager'''

    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_lic_assign_mgr = MagicMock()
        type(self.mock_si.content.licenseManager).licenseAssignmentManager = \
                PropertyMock(return_value=self.mock_lic_assign_mgr)

    def tearDown(self):
        for attr in ('mock_si', 'mock_lic_assign_mgr'):
            delattr(self, attr)

    def test_raise_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        type(self.mock_si.content.licenseManager).licenseAssignmentManager = \
                PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.get_license_assignment_manager(self.mock_si)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        type(self.mock_si.content.licenseManager).licenseAssignmentManager = \
                PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.get_license_assignment_manager(self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        type(self.mock_si.content.licenseManager).licenseAssignmentManager = \
                PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.vmware.get_license_assignment_manager(self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_empty_license_assignment_manager(self):
        type(self.mock_si.content.licenseManager).licenseAssignmentManager = \
                PropertyMock(return_value=None)
        with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
            salt.utils.vmware.get_license_assignment_manager(self.mock_si)
        self.assertEqual(excinfo.exception.strerror,
                         'License assignment manager was not retrieved')

    def test_valid_assignment_manager(self):
        ret = salt.utils.vmware.get_license_assignment_manager(self.mock_si)
        self.assertEqual(ret, self.mock_lic_assign_mgr)
