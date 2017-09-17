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


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetLicensesTestCase(TestCase):
    '''Tests for salt.utils.vmware.get_licenses'''

    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_licenses = [MagicMock(), MagicMock()]
        self.mock_lic_mgr = MagicMock()
        type(self.mock_lic_mgr).licenses = \
                PropertyMock(return_value=self.mock_licenses)
        patches = (
            ('salt.utils.vmware.get_license_manager',
             MagicMock(return_value=self.mock_lic_mgr)),)
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_si', 'mock_lic_mgr', 'mock_licenses'):
            delattr(self, attr)

    def test_no_license_manager_passed_in(self):
        mock_get_license_manager = MagicMock()
        with patch('salt.utils.vmware.get_license_manager',
                   mock_get_license_manager):
            salt.utils.vmware.get_licenses(self.mock_si)
        mock_get_license_manager.assert_called_once_with(self.mock_si)

    def test_license_manager_passed_in(self):
        mock_licenses = PropertyMock()
        mock_lic_mgr = MagicMock()
        type(mock_lic_mgr).licenses = mock_licenses
        mock_get_license_manager = MagicMock()
        with patch('salt.utils.vmware.get_license_manager',
                   mock_get_license_manager):
            salt.utils.vmware.get_licenses(self.mock_si,
                                           license_manager=mock_lic_mgr)
        self.assertEqual(mock_get_license_manager.call_count, 0)
        self.assertEqual(mock_licenses.call_count, 1)

    def test_raise_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        type(self.mock_lic_mgr).licenses = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.get_licenses(self.mock_si)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        type(self.mock_lic_mgr).licenses = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.get_licenses(self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        type(self.mock_lic_mgr).licenses = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.vmware.get_licenses(self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_valid_licenses(self):
        ret = salt.utils.vmware.get_licenses(self.mock_si)
        self.assertEqual(ret, self.mock_licenses)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class AddLicenseTestCase(TestCase):
    '''Tests for salt.utils.vmware.add_license'''

    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_license = MagicMock()
        self.mock_add_license = MagicMock(return_value=self.mock_license)
        self.mock_lic_mgr = MagicMock(AddLicense=self.mock_add_license)
        self.mock_label = MagicMock()
        patches = (
            ('salt.utils.vmware.get_license_manager',
             MagicMock(return_value=self.mock_lic_mgr)),
            ('salt.utils.vmware.vim.KeyValue',
             MagicMock(return_value=self.mock_label)))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_si', 'mock_lic_mgr', 'mock_license',
                     'mock_add_license', 'mock_label'):
            delattr(self, attr)

    def test_no_license_manager_passed_in(self):
        mock_get_license_manager = MagicMock()
        with patch('salt.utils.vmware.get_license_manager',
                   mock_get_license_manager):
            salt.utils.vmware.add_license(self.mock_si,
                                          'fake_license_key',
                                          'fake_license_description')
        mock_get_license_manager.assert_called_once_with(self.mock_si)

    def test_license_manager_passed_in(self):
        mock_get_license_manager = MagicMock()
        with patch('salt.utils.vmware.get_license_manager',
                   mock_get_license_manager):
            salt.utils.vmware.add_license(self.mock_si,
                                          'fake_license_key',
                                          'fake_license_description',
                                           license_manager=self.mock_lic_mgr)
        self.assertEqual(mock_get_license_manager.call_count, 0)
        self.assertEqual(self.mock_add_license.call_count, 1)

    def test_label_settings(self):
        salt.utils.vmware.add_license(self.mock_si,
                                      'fake_license_key',
                                      'fake_license_description')
        self.assertEqual(self.mock_label.key, 'VpxClientLicenseLabel')
        self.assertEqual(self.mock_label.value, 'fake_license_description')

    def test_add_license_arguments(self):
        salt.utils.vmware.add_license(self.mock_si,
                                      'fake_license_key',
                                      'fake_license_description')
        self.mock_add_license.assert_called_once_with('fake_license_key',
                                                      [self.mock_label])

    def test_add_license_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_lic_mgr.AddLicense = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.add_license(self.mock_si,
                                          'fake_license_key',
                                          'fake_license_description')
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_add_license_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_lic_mgr.AddLicense = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.add_license(self.mock_si,
                                          'fake_license_key',
                                          'fake_license_description')
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_add_license_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_lic_mgr.AddLicense = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.vmware.add_license(self.mock_si,
                                          'fake_license_key',
                                          'fake_license_description')
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_valid_license_added(self):
        ret = salt.utils.vmware.add_license(self.mock_si,
                                           'fake_license_key',
                                           'fake_license_description')
        self.assertEqual(ret, self.mock_license)
