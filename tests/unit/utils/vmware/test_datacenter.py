# -*- coding: utf-8 -*-
'''
:codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

Tests for datacenter related functions in salt.utils.vmware
'''

# Import python libraries
from __future__ import absolute_import, print_function, unicode_literals
import logging
# Import Salt testing libraries
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock

from salt.exceptions import VMwareObjectRetrievalError, VMwareApiError, \
        VMwareRuntimeError

# Import Salt libraries
import salt.utils.vmware as vmware
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
class GetDatacentersTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.get_datacenters
    '''

    def setUp(self):
        patches = (
            ('salt.utils.vmware.get_mors_with_properties',
                MagicMock(return_value=[{'name': 'fake_dc', 'object': MagicMock()}])),
        )
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.mock_si = MagicMock()
        self.mock_dc1 = MagicMock()
        self.mock_dc2 = MagicMock()
        self.mock_entries = [{'name': 'fake_dc1',
                              'object': self.mock_dc1},
                             {'name': 'fake_dc2',
                              'object': self.mock_dc2}]

    def test_get_mors_with_properties_call(self):
        mock_get_mors_with_properties = MagicMock(
            return_value=[{'name': 'fake_dc', 'object': MagicMock()}])
        with patch('salt.utils.vmware.get_mors_with_properties',
                   mock_get_mors_with_properties):
            vmware.get_datacenters(self.mock_si, datacenter_names=['fake_dc1'])
        mock_get_mors_with_properties.assert_called_once_with(
            self.mock_si, vim.Datacenter, property_list=['name'])

    def test_get_mors_with_properties_returns_empty_array(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=[])):
            res = vmware.get_datacenters(self.mock_si,
                                         datacenter_names=['fake_dc1'])
        self.assertEqual(res, [])

    def test_no_parameters(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=self.mock_entries)):
            res = vmware.get_datacenters(self.mock_si)
        self.assertEqual(res, [])

    def test_datastore_not_found(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=self.mock_entries)):
            res = vmware.get_datacenters(self.mock_si,
                                         datacenter_names=['fake_dc'])
        self.assertEqual(res, [])

    def test_datastore_found(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=self.mock_entries)):
            res = vmware.get_datacenters(
                self.mock_si, datacenter_names=['fake_dc2'])
        self.assertEqual(res, [self.mock_dc2])

    def test_get_all_datastores(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=self.mock_entries)):
            res = vmware.get_datacenters(
                self.mock_si, get_all_datacenters=True)
        self.assertEqual(res, [self.mock_dc1, self.mock_dc2])


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetDatacenterTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.get_datacenter
    '''

    def setUp(self):
        patches = (
            ('salt.utils.vmware.get_datacenters', MagicMock(return_value=[MagicMock()])),
        )
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.mock_si = MagicMock()
        self.mock_dc = MagicMock()

    def test_get_datacenters_call(self):
        mock_get_datacenters = MagicMock(return_value=[MagicMock()])
        with patch('salt.utils.vmware.get_datacenters',
                   mock_get_datacenters):
            vmware.get_datacenter(self.mock_si, 'fake_dc1')
        mock_get_datacenters.assert_called_once_with(
            self.mock_si, datacenter_names=['fake_dc1'])

    def test_no_datacenters_returned(self):
        with patch('salt.utils.vmware.get_datacenters',
                   MagicMock(return_value=[])):
            with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                vmware.get_datacenter(self.mock_si, 'fake_dc1')
        self.assertEqual('Datacenter \'fake_dc1\' was not found',
                         excinfo.exception.strerror)

    def test_get_datacenter_return(self):
        with patch('salt.utils.vmware.get_datacenters',
                   MagicMock(return_value=[self.mock_dc])):
            res = vmware.get_datacenter(self.mock_si, 'fake_dc1')
        self.assertEqual(res, self.mock_dc)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class CreateDatacenterTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.create_datacenter
    '''

    def setUp(self):
        patches = (
            ('salt.utils.vmware.get_root_folder', MagicMock()),
        )
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.mock_si = MagicMock()
        self.mock_dc = MagicMock()
        self.mock_create_datacenter = MagicMock(return_value=self.mock_dc)
        self.mock_root_folder = MagicMock(
            CreateDatacenter=self.mock_create_datacenter)

    def test_get_root_folder(self):
        mock_get_root_folder = MagicMock()
        with patch('salt.utils.vmware.get_root_folder', mock_get_root_folder):
            vmware.create_datacenter(self.mock_si, 'fake_dc')
        mock_get_root_folder.assert_called_once_with(self.mock_si)

    def test_create_datacenter_call(self):
        with patch('salt.utils.vmware.get_root_folder',
                   MagicMock(return_value=self.mock_root_folder)):
            vmware.create_datacenter(self.mock_si, 'fake_dc')
        self.mock_create_datacenter.assert_called_once_with('fake_dc')

    def test_create_datacenter_raise_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_root_folder = MagicMock(
            CreateDatacenter=MagicMock(side_effect=exc))
        with patch('salt.utils.vmware.get_root_folder',
                   MagicMock(return_value=self.mock_root_folder)):
            with self.assertRaises(VMwareApiError) as excinfo:
                vmware.create_datacenter(self.mock_si, 'fake_dc')
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_create_datacenter_raise_vim_fault(self):
        exc = vim.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_root_folder = MagicMock(
            CreateDatacenter=MagicMock(side_effect=exc))
        with patch('salt.utils.vmware.get_root_folder',
                   MagicMock(return_value=self.mock_root_folder)):
            with self.assertRaises(VMwareApiError) as excinfo:
                vmware.create_datacenter(self.mock_si, 'fake_dc')
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_create_datacenter_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_root_folder = MagicMock(
            CreateDatacenter=MagicMock(side_effect=exc))
        with patch('salt.utils.vmware.get_root_folder',
                   MagicMock(return_value=self.mock_root_folder)):
            with self.assertRaises(VMwareRuntimeError) as excinfo:
                vmware.create_datacenter(self.mock_si, 'fake_dc')
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_datastore_successfully_created(self):
        with patch('salt.utils.vmware.get_root_folder',
                   MagicMock(return_value=self.mock_root_folder)):
            res = vmware.create_datacenter(self.mock_si, 'fake_dc')
        self.assertEqual(res, self.mock_dc)
