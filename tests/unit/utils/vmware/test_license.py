# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for license related functions in salt.utils.vmware
'''

# Import python libraries
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt testing libraries
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock, \
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
    '''
    Tests for salt.utils.vmware.get_license_manager
    '''

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
    '''
    Tests for salt.utils.vmware.get_license_assignment_manager
    '''

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
    '''
    Tests for salt.utils.vmware.get_licenses
    '''

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
    '''
    Tests for salt.utils.vmware.add_license
    '''

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


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetAssignedLicensesTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.get_assigned_licenses
    '''

    def setUp(self):
        self.mock_ent_id = MagicMock()
        self.mock_si = MagicMock()
        type(self.mock_si.content.about).instanceUuid = \
                PropertyMock(return_value=self.mock_ent_id)
        self.mock_moid = MagicMock()
        self.prop_mock_moid = PropertyMock(return_value=self.mock_moid)
        self.mock_entity_ref = MagicMock()
        type(self.mock_entity_ref)._moId = self.prop_mock_moid
        self.mock_assignments = [MagicMock(entityDisplayName='fake_ent1'),
                                 MagicMock(entityDisplayName='fake_ent2')]
        self.mock_query_assigned_licenses = MagicMock(
            return_value=[MagicMock(assignedLicense=self.mock_assignments[0]),
                          MagicMock(assignedLicense=self.mock_assignments[1])])
        self.mock_lic_assign_mgr = MagicMock(
            QueryAssignedLicenses=self.mock_query_assigned_licenses)
        patches = (
            ('salt.utils.vmware.get_license_assignment_manager',
             MagicMock(return_value=self.mock_lic_assign_mgr)),)
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_ent_id', 'mock_si', 'mock_moid', 'prop_mock_moid',
                     'mock_entity_ref', 'mock_assignments',
                     'mock_query_assigned_licenses', 'mock_lic_assign_mgr'):
            delattr(self, attr)

    def test_no_license_assignment_manager_passed_in(self):
        mock_get_license_assign_manager = MagicMock()
        with patch('salt.utils.vmware.get_license_assignment_manager',
                   mock_get_license_assign_manager):
            salt.utils.vmware.get_assigned_licenses(self.mock_si,
                                                    self.mock_entity_ref,
                                                    'fake_entity_name')
        mock_get_license_assign_manager.assert_called_once_with(self.mock_si)

    def test_license_assignment_manager_passed_in(self):
        mock_get_license_assign_manager = MagicMock()
        with patch('salt.utils.vmware.get_license_assignment_manager',
                   mock_get_license_assign_manager):
            salt.utils.vmware.get_assigned_licenses(
                self.mock_si, self.mock_entity_ref, 'fake_entity_name',
                license_assignment_manager=self.mock_lic_assign_mgr)
        self.assertEqual(mock_get_license_assign_manager.call_count, 0)

    def test_entity_name(self):
        mock_trace = MagicMock()
        with patch('salt.log.setup.SaltLoggingClass.trace', mock_trace):
            salt.utils.vmware.get_assigned_licenses(self.mock_si,
                                                    self.mock_entity_ref,
                                                    'fake_entity_name')
        mock_trace.assert_called_once_with(
            "Retrieving licenses assigned to '%s'", 'fake_entity_name')

    def test_instance_uuid(self):
        mock_instance_uuid_prop = PropertyMock()
        type(self.mock_si.content.about).instanceUuid = mock_instance_uuid_prop
        self.mock_lic_assign_mgr.QueryAssignedLicenses = MagicMock(
                    return_value=[MagicMock(entityDisplayName='fake_vcenter')])
        salt.utils.vmware.get_assigned_licenses(self.mock_si,
                                                entity_name='fake_vcenter')
        self.assertEqual(mock_instance_uuid_prop.call_count, 1)

    def test_instance_uuid_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        type(self.mock_si.content.about).instanceUuid = \
                PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.get_assigned_licenses(self.mock_si,
                                                    entity_name='fake_vcenter')
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_instance_uuid_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        type(self.mock_si.content.about).instanceUuid = \
                PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.get_assigned_licenses(self.mock_si,
                                                    entity_name='fake_vcenter')
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_instance_uuid_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        type(self.mock_si.content.about).instanceUuid = \
                PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.vmware.get_assigned_licenses(self.mock_si,
                                                    entity_name='fake_vcenter')
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_vcenter_entity_too_many_assignements(self):
        self.mock_lic_assign_mgr.QueryAssignedLicenses = MagicMock(
            return_value=[MagicMock(), MagicMock()])
        with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
            salt.utils.vmware.get_assigned_licenses(self.mock_si,
                                                    entity_name='fake_vcenter')
        self.assertEqual(excinfo.exception.strerror,
                         'Unexpected return. Expect only a single assignment')

    def test_wrong_vcenter_name(self):
        self.mock_lic_assign_mgr.QueryAssignedLicenses = MagicMock(
            return_value=[MagicMock(entityDisplayName='bad_vcenter')])
        with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
            salt.utils.vmware.get_assigned_licenses(self.mock_si,
                                                    entity_name='fake_vcenter')
        self.assertEqual(excinfo.exception.strerror,
                         'Got license assignment info for a different vcenter')

    def test_query_assigned_licenses_vcenter(self):
        with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
            salt.utils.vmware.get_assigned_licenses(self.mock_si,
                                                    entity_name='fake_vcenter')
        self.mock_query_assigned_licenses.assert_called_once_with(
            self.mock_ent_id)

    def test_query_assigned_licenses_with_entity(self):
        salt.utils.vmware.get_assigned_licenses(self.mock_si,
                                                self.mock_entity_ref,
                                                'fake_entity_name')
        self.mock_query_assigned_licenses.assert_called_once_with(
            self.mock_moid)

    def test_query_assigned_licenses_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_lic_assign_mgr.QueryAssignedLicenses = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.get_assigned_licenses(self.mock_si,
                                                    self.mock_entity_ref,
                                                    'fake_entity_name')
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_query_assigned_licenses_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_lic_assign_mgr.QueryAssignedLicenses = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.get_assigned_licenses(self.mock_si,
                                                    self.mock_entity_ref,
                                                    'fake_entity_name')
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_query_assigned_licenses_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_lic_assign_mgr.QueryAssignedLicenses = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.vmware.get_assigned_licenses(self.mock_si,
                                                    self.mock_entity_ref,
                                                    'fake_entity_name')
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_valid_assignments(self):
        ret = salt.utils.vmware.get_assigned_licenses(self.mock_si,
                                                      self.mock_entity_ref,
                                                      'fake_entity_name')
        self.assertEqual(ret, self.mock_assignments)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class AssignLicenseTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.assign_license
    '''

    def setUp(self):
        self.mock_ent_id = MagicMock()
        self.mock_si = MagicMock()
        type(self.mock_si.content.about).instanceUuid = \
                PropertyMock(return_value=self.mock_ent_id)
        self.mock_lic_key = MagicMock()
        self.mock_moid = MagicMock()
        self.prop_mock_moid = PropertyMock(return_value=self.mock_moid)
        self.mock_entity_ref = MagicMock()
        type(self.mock_entity_ref)._moId = self.prop_mock_moid
        self.mock_license = MagicMock()
        self.mock_update_assigned_license = MagicMock(
            return_value=self.mock_license)
        self.mock_lic_assign_mgr = MagicMock(
            UpdateAssignedLicense=self.mock_update_assigned_license)
        patches = (
            ('salt.utils.vmware.get_license_assignment_manager',
             MagicMock(return_value=self.mock_lic_assign_mgr)),)
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_no_license_assignment_manager_passed_in(self):
        mock_get_license_assign_manager = MagicMock()
        with patch('salt.utils.vmware.get_license_assignment_manager',
                   mock_get_license_assign_manager):
            salt.utils.vmware.assign_license(self.mock_si,
                                             self.mock_lic_key,
                                             'fake_license_name',
                                             self.mock_entity_ref,
                                             'fake_entity_name')
        mock_get_license_assign_manager.assert_called_once_with(self.mock_si)

    def test_license_assignment_manager_passed_in(self):
        mock_get_license_assign_manager = MagicMock()
        with patch('salt.utils.vmware.get_license_assignment_manager',
                   mock_get_license_assign_manager):
            salt.utils.vmware.assign_license(
                self.mock_si, self.mock_lic_key, 'fake_license_name',
                self.mock_entity_ref, 'fake_entity_name',
                license_assignment_manager=self.mock_lic_assign_mgr)
        self.assertEqual(mock_get_license_assign_manager.call_count, 0)
        self.assertEqual(self.mock_update_assigned_license.call_count, 1)

    def test_entity_name(self):
        mock_trace = MagicMock()
        with patch('salt.log.setup.SaltLoggingClass.trace', mock_trace):
            salt.utils.vmware.assign_license(self.mock_si,
                                             self.mock_lic_key,
                                             'fake_license_name',
                                             self.mock_entity_ref,
                                             'fake_entity_name')
        mock_trace.assert_called_once_with(
            "Assigning license to '%s'", 'fake_entity_name')

    def test_instance_uuid(self):
        mock_instance_uuid_prop = PropertyMock()
        type(self.mock_si.content.about).instanceUuid = mock_instance_uuid_prop
        self.mock_lic_assign_mgr.UpdateAssignedLicense = MagicMock(
                    return_value=[MagicMock(entityDisplayName='fake_vcenter')])
        salt.utils.vmware.assign_license(self.mock_si,
                                         self.mock_lic_key,
                                         'fake_license_name',
                                         entity_name='fake_entity_name')
        self.assertEqual(mock_instance_uuid_prop.call_count, 1)

    def test_instance_uuid_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        type(self.mock_si.content.about).instanceUuid = \
                PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.assign_license(self.mock_si,
                                             self.mock_lic_key,
                                             'fake_license_name',
                                             entity_name='fake_entity_name')
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_instance_uuid_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        type(self.mock_si.content.about).instanceUuid = \
                PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.assign_license(self.mock_si,
                                             self.mock_lic_key,
                                             'fake_license_name',
                                             entity_name='fake_entity_name')
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_instance_uuid_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        type(self.mock_si.content.about).instanceUuid = \
                PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.vmware.assign_license(self.mock_si,
                                             self.mock_lic_key,
                                             'fake_license_name',
                                             entity_name='fake_entity_name')
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_update_assigned_licenses_vcenter(self):
        salt.utils.vmware.assign_license(self.mock_si,
                                         self.mock_lic_key,
                                         'fake_license_name',
                                         entity_name='fake_entity_name')
        self.mock_update_assigned_license.assert_called_once_with(
            self.mock_ent_id, self.mock_lic_key)

    def test_update_assigned_licenses_call_with_entity(self):
        salt.utils.vmware.assign_license(self.mock_si,
                                         self.mock_lic_key,
                                         'fake_license_name',
                                         self.mock_entity_ref,
                                         'fake_entity_name')
        self.mock_update_assigned_license.assert_called_once_with(
            self.mock_moid, self.mock_lic_key)

    def test_update_assigned_licenses_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_lic_assign_mgr.UpdateAssignedLicense = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.assign_license(self.mock_si,
                                             self.mock_lic_key,
                                             'fake_license_name',
                                             self.mock_entity_ref,
                                             'fake_entity_name')
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_update_assigned_licenses_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_lic_assign_mgr.UpdateAssignedLicense = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.assign_license(self.mock_si,
                                             self.mock_lic_key,
                                             'fake_license_name',
                                             self.mock_entity_ref,
                                             'fake_entity_name')
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_update_assigned_licenses_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_lic_assign_mgr.UpdateAssignedLicense = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.vmware.assign_license(self.mock_si,
                                             self.mock_lic_key,
                                             'fake_license_name',
                                             self.mock_entity_ref,
                                             'fake_entity_name')
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_valid_assignments(self):
        ret = salt.utils.vmware.assign_license(self.mock_si,
                                               self.mock_lic_key,
                                               'fake_license_name',
                                               self.mock_entity_ref,
                                               'fake_entity_name')
        self.assertEqual(ret, self.mock_license)
