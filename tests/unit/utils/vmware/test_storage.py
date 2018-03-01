# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for storage related functions in salt.utils.vmware
'''

# Import python libraries
from __future__ import absolute_import
import logging

# Import Salt testing libraries
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock, call
from salt.exceptions import VMwareObjectRetrievalError, VMwareApiError, \
        ArgumentValueError, VMwareRuntimeError

#i Import Salt libraries
import salt.utils.vmware
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
class GetStorageSystemTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.get_storage_system
    '''
    def setUp(self):
        self.mock_si = MagicMock(content=MagicMock())
        self.mock_host_ref = MagicMock()
        self.mock_get_managed_object_name = MagicMock(return_value='fake_host')
        self.mock_traversal_spec = MagicMock()
        self.mock_obj = MagicMock()
        self.mock_get_mors = \
             MagicMock(return_value=[{'object': self.mock_obj}])

        patches = (
            ('salt.utils.vmware.get_managed_object_name',
             self.mock_get_managed_object_name),
            ('salt.utils.vmware.get_mors_with_properties',
             self.mock_get_mors),
            ('salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
             MagicMock(return_value=self.mock_traversal_spec)))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_si', 'mock_host_ref',
                     'mock_get_managed_object_name',
                     'mock_traversal_spec', 'mock_obj'):
            delattr(self, attr)

    def test_no_hostname_argument(self):
        salt.utils.vmware.get_storage_system(self.mock_si,
                                             self.mock_host_ref)
        self.mock_get_managed_object_name.assert_called_once_with(
            self.mock_host_ref)

    def test_hostname_argument(self):
        salt.utils.vmware.get_storage_system(self.mock_si,
                                             self.mock_host_ref,
                                             hostname='fake_host')
        self.assertEqual(self.mock_get_managed_object_name.call_count, 0)

    def test_traversal_spec(self):
        mock_traversal_spec = MagicMock(return_value=[{'object':
                                                       self.mock_obj}])
        with patch(
            'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
            mock_traversal_spec):

            salt.utils.vmware.get_storage_system(self.mock_si,
                                                 self.mock_host_ref)
        mock_traversal_spec.assert_called_once_with(
            path='configManager.storageSystem',
            type=vim.HostSystem,
            skip=False)

    def test_get_mors_with_properties(self):
        salt.utils.vmware.get_storage_system(self.mock_si,
                                             self.mock_host_ref)
        self.mock_get_mors.assert_called_once_with(
            self.mock_si,
            vim.HostStorageSystem,
            property_list=['systemFile'],
            container_ref=self.mock_host_ref,
            traversal_spec=self.mock_traversal_spec)

    def test_empty_mors_result(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=[])):
            with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                salt.utils.vmware.get_storage_system(self.mock_si,
                                                     self.mock_host_ref)
        self.assertEqual(excinfo.exception.strerror,
                         'Host\'s \'fake_host\' storage system was '
                         'not retrieved')

    def test_valid_mors_result(self):
        res = salt.utils.vmware.get_storage_system(self.mock_si,
                                                   self.mock_host_ref)
        self.assertEqual(res, self.mock_obj)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetDatastoresTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.get_datastores
    '''

    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_reference = MagicMock(spec=vim.HostSystem)
        self.mock_mount_infos = [
            MagicMock(volume=MagicMock(spec=vim.HostVmfsVolume,
                                       extent=[MagicMock(
                                           diskName='fake_disk2')])),
            MagicMock(volume=MagicMock(spec=vim.HostVmfsVolume,
                                       extent=[MagicMock(
                                           diskName='fake_disk3')]))]
        self.mock_mount_infos[0].volume.name = 'fake_ds2'
        self.mock_mount_infos[1].volume.name = 'fake_ds3'
        self.mock_entries = [{'name': 'fake_ds1', 'object': MagicMock()},
                             {'name': 'fake_ds2', 'object': MagicMock()},
                             {'name': 'fake_ds3', 'object': MagicMock()}]
        self.mock_storage_system = MagicMock()
        self.mock_get_storage_system = MagicMock(
            return_value=self.mock_storage_system)
        self.mock_get_managed_object_name = MagicMock(return_value='fake_host')
        self.mock_traversal_spec = MagicMock()

        patches = (
            ('salt.utils.vmware.get_managed_object_name',
             self.mock_get_managed_object_name),
            ('salt.utils.vmware.get_storage_system',
             self.mock_get_storage_system),
            ('salt.utils.vmware.get_properties_of_managed_object',
             MagicMock(return_value={'fileSystemVolumeInfo.mountInfo':
                                     self.mock_mount_infos})),
            ('salt.utils.vmware.get_mors_with_properties',
             MagicMock(return_value=self.mock_entries)),
            ('salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
             MagicMock(return_value=self.mock_traversal_spec)))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_si', 'mock_reference', 'mock_storage_system',
                     'mock_get_storage_system', 'mock_mount_infos',
                     'mock_entries', 'mock_get_managed_object_name',
                     'mock_traversal_spec'):
            delattr(self, attr)

    def test_get_reference_name_call(self):
        salt.utils.vmware.get_datastores(self.mock_si,
                                         self.mock_reference)
        self.mock_get_managed_object_name.assert_called_once_with(
            self.mock_reference)

    def test_get_no_datastores(self):
        res = salt.utils.vmware.get_datastores(self.mock_si,
                                               self.mock_reference)
        self.assertEqual(res, [])

    def test_get_storage_system_call(self):
        salt.utils.vmware.get_datastores(self.mock_si,
                                         self.mock_reference,
                                         backing_disk_ids=['fake_disk1'])
        self.mock_get_storage_system.assert_called_once_with(
            self.mock_si, self.mock_reference, 'fake_host')

    def test_get_mount_info_call(self):
        mock_get_properties_of_managed_object = MagicMock()
        with patch('salt.utils.vmware.get_properties_of_managed_object',
                   mock_get_properties_of_managed_object):
            salt.utils.vmware.get_datastores(self.mock_si,
                                             self.mock_reference,
                                             backing_disk_ids=['fake_disk1'])
        mock_get_properties_of_managed_object.assert_called_once_with(
            self.mock_storage_system, ['fileSystemVolumeInfo.mountInfo'])

    def test_backing_disks_no_mount_info(self):
        with patch('salt.utils.vmware.get_properties_of_managed_object',
                   MagicMock(return_value={})):
            res = salt.utils.vmware.get_datastores(
                self.mock_si, self.mock_reference,
                backing_disk_ids=['fake_disk_id'])
        self.assertEqual(res, [])

    def test_host_traversal_spec(self):
        # Reference is of type vim.HostSystem
        mock_traversal_spec_init = MagicMock()
        with patch(
            'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
            mock_traversal_spec_init):

            salt.utils.vmware.get_datastores(
                self.mock_si,
                self.mock_reference,
                get_all_datastores=True)
        mock_traversal_spec_init.assert_called_once_with(
            name='host_datastore_traversal',
            path='datastore',
            skip=False,
            type=vim.HostSystem)

    def test_cluster_traversal_spec(self):
        mock_traversal_spec_init = MagicMock()
        # Reference is of type vim.ClusterComputeResource
        mock_reference = MagicMock(spec=vim.ClusterComputeResource)
        with patch(
            'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
            mock_traversal_spec_init):

            salt.utils.vmware.get_datastores(
                self.mock_si,
                mock_reference,
                get_all_datastores=True)
        mock_traversal_spec_init.assert_called_once_with(
            name='cluster_datastore_traversal',
            path='datastore',
            skip=False,
            type=vim.ClusterComputeResource)

    def test_datacenter_traversal_spec(self):
        mock_traversal_spec_init = MagicMock()
        # Reference is of type vim.ClusterComputeResource
        mock_reference = MagicMock(spec=vim.Datacenter)
        with patch(
            'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
            mock_traversal_spec_init):

            salt.utils.vmware.get_datastores(
                self.mock_si,
                mock_reference,
                get_all_datastores=True)
        mock_traversal_spec_init.assert_called_once_with(
            name='datacenter_datastore_traversal',
            path='datastore',
            skip=False,
            type=vim.Datacenter)

    def test_root_folder_traversal_spec(self):
        mock_traversal_spec_init = MagicMock(return_value='traversal')
        mock_reference = MagicMock(spec=vim.Folder)
        with patch('salt.utils.vmware.get_managed_object_name',
                   MagicMock(side_effect=['fake_host', 'Datacenters'])):
            with patch(
                'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
                mock_traversal_spec_init):

                salt.utils.vmware.get_datastores(
                    self.mock_si,
                    mock_reference,
                    get_all_datastores=True)

        mock_traversal_spec_init.assert_has_calls([
            call(path='datastore',
                 skip=False,
                 type=vim.Datacenter),
            call(path='childEntity',
                 selectSet=['traversal'],
                 skip=False,
                 type=vim.Folder)])

    def test_unsupported_reference_type(self):
        class FakeClass(object):
            pass

        mock_reference = MagicMock(spec=FakeClass)
        with self.assertRaises(ArgumentValueError) as excinfo:
            salt.utils.vmware.get_datastores(
                self.mock_si,
                mock_reference,
                get_all_datastores=True)
        self.assertEqual(excinfo.exception.strerror,
                         'Unsupported reference type \'FakeClass\'')

    def test_get_mors_with_properties(self):
        mock_get_mors_with_properties = MagicMock()
        with patch('salt.utils.vmware.get_mors_with_properties',
                   mock_get_mors_with_properties):
            salt.utils.vmware.get_datastores(
                self.mock_si,
                self.mock_reference,
                get_all_datastores=True)
        mock_get_mors_with_properties.assert_called_once_with(
            self.mock_si,
            object_type=vim.Datastore,
            property_list=['name'],
            container_ref=self.mock_reference,
            traversal_spec=self.mock_traversal_spec)

    def test_get_all_datastores(self):
        res = salt.utils.vmware.get_datastores(self.mock_si,
                                               self.mock_reference,
                                               get_all_datastores=True)
        self.assertEqual(res, [self.mock_entries[0]['object'],
                               self.mock_entries[1]['object'],
                               self.mock_entries[2]['object']])

    def test_get_datastores_filtered_by_name(self):
        res = salt.utils.vmware.get_datastores(self.mock_si,
                                               self.mock_reference,
                                               datastore_names=['fake_ds1',
                                                                'fake_ds2'])
        self.assertEqual(res, [self.mock_entries[0]['object'],
                               self.mock_entries[1]['object']])

    def test_get_datastores_filtered_by_backing_disk(self):
        res = salt.utils.vmware.get_datastores(
            self.mock_si, self.mock_reference,
            backing_disk_ids=['fake_disk2', 'fake_disk3'])
        self.assertEqual(res, [self.mock_entries[1]['object'],
                               self.mock_entries[2]['object']])

    def test_get_datastores_filtered_by_both_name_and_backing_disk(self):
        # Simulate VMware data model for volumes fake_ds2, fake_ds3
        res = salt.utils.vmware.get_datastores(
            self.mock_si, self.mock_reference,
            datastore_names=['fake_ds1'],
            backing_disk_ids=['fake_disk3'])
        self.assertEqual(res, [self.mock_entries[0]['object'],
                               self.mock_entries[2]['object']])


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class RenameDatastoreTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.rename_datastore
    '''

    def setUp(self):
        self.mock_ds_ref = MagicMock()
        self.mock_get_managed_object_name = MagicMock(return_value='fake_ds')

        patches = (
            ('salt.utils.vmware.get_managed_object_name',
             self.mock_get_managed_object_name),)
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_ds_ref', 'mock_get_managed_object_name'):
            delattr(self, attr)

    def test_datastore_name_call(self):
        salt.utils.vmware.rename_datastore(self.mock_ds_ref,
                                           'fake_new_name')
        self.mock_get_managed_object_name.assert_called_once_with(
            self.mock_ds_ref)

    def test_rename_datastore_raise_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        type(self.mock_ds_ref).RenameDatastore = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.rename_datastore(self.mock_ds_ref,
                                               'fake_new_name')
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_rename_datastore_raise_vim_fault(self):
        exc = vim.VimFault()
        exc.msg = 'vim_fault'
        type(self.mock_ds_ref).RenameDatastore = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.rename_datastore(self.mock_ds_ref,
                                               'fake_new_name')
        self.assertEqual(excinfo.exception.strerror, 'vim_fault')

    def test_rename_datastore_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'runtime_fault'
        type(self.mock_ds_ref).RenameDatastore = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.vmware.rename_datastore(self.mock_ds_ref,
                                               'fake_new_name')
        self.assertEqual(excinfo.exception.strerror, 'runtime_fault')

    def test_rename_datastore(self):
        salt.utils.vmware.rename_datastore(self.mock_ds_ref, 'fake_new_name')
        self.mock_ds_ref.RenameDatastore.assert_called_once_with(
            'fake_new_name')
