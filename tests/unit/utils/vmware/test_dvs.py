# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for dvs related functions in salt.utils.vmware
'''

# Import python libraries
from __future__ import absolute_import
import logging

# Import Salt testing libraries
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock, call, \
        PropertyMock
from salt.exceptions import VMwareObjectRetrievalError, VMwareApiError, \
        ArgumentValueError, VMwareRuntimeError

#i Import Salt libraries
import salt.utils.vmware as vmware
# Import Third Party Libs
try:
    from pyVmomi import vim, vmodl
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

# Get Logging Started
log = logging.getLogger(__name__)


class FakeTaskClass(object):
    pass


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetDvssTestCase(TestCase):
    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_dc_ref = MagicMock()
        self.mock_traversal_spec = MagicMock()
        self.mock_items = [{'object': MagicMock(),
                            'name': 'fake_dvs1'},
                           {'object': MagicMock(),
                            'name': 'fake_dvs2'},
                           {'object': MagicMock(),
                            'name': 'fake_dvs3'}]
        self.mock_get_mors = MagicMock(return_value=self.mock_items)

        patches = (
            ('salt.utils.vmware.get_managed_object_name',
             MagicMock()),
            ('salt.utils.vmware.get_mors_with_properties',
             self.mock_get_mors),
            ('salt.utils.vmware.get_service_instance_from_managed_object',
             MagicMock(return_value=self.mock_si)),
            ('salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
             MagicMock(return_value=self.mock_traversal_spec)))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_si', 'mock_dc_ref', 'mock_traversal_spec',
                     'mock_items', 'mock_get_mors'):
            delattr(self, attr)

    def test_get_managed_object_name_call(self):
        mock_get_managed_object_name = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vmware.get_dvss(self.mock_dc_ref)
        mock_get_managed_object_name.assert_called_once_with(self.mock_dc_ref)

    def test_traversal_spec(self):
        mock_traversal_spec = MagicMock(return_value='traversal_spec')
        with patch(
            'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
            mock_traversal_spec):

            vmware.get_dvss(self.mock_dc_ref)
        mock_traversal_spec.assert_called(
            call(path='networkFolder', skip=True, type=vim.Datacenter,
                 selectSet=['traversal_spec']),
            call(path='childEntity', skip=False, type=vim.Folder))

    def test_get_mors_with_properties(self):
        vmware.get_dvss(self.mock_dc_ref)
        self.mock_get_mors.assert_called_once_with(
            self.mock_si, vim.DistributedVirtualSwitch,
            container_ref=self.mock_dc_ref, property_list=['name'],
            traversal_spec=self.mock_traversal_spec)

    def test_get_no_dvss(self):
        ret = vmware.get_dvss(self.mock_dc_ref)
        self.assertEqual(ret, [])

    def test_get_all_dvss(self):
        ret = vmware.get_dvss(self.mock_dc_ref, get_all_dvss=True)
        self.assertEqual(ret, [i['object'] for i in self.mock_items])

    def test_filtered_all_dvss(self):
        ret = vmware.get_dvss(self.mock_dc_ref,
                              dvs_names=['fake_dvs1', 'fake_dvs3', 'no_dvs'])
        self.assertEqual(ret, [self.mock_items[0]['object'],
                               self.mock_items[2]['object']])


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetNetworkFolderTestCase(TestCase):
    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_dc_ref = MagicMock()
        self.mock_traversal_spec = MagicMock()
        self.mock_entries = [{'object': MagicMock(),
                              'name': 'fake_netw_folder'}]
        self.mock_get_mors = MagicMock(return_value=self.mock_entries)

        patches = (
            ('salt.utils.vmware.get_managed_object_name',
             MagicMock(return_value='fake_dc')),
            ('salt.utils.vmware.get_service_instance_from_managed_object',
             MagicMock(return_value=self.mock_si)),
            ('salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
             MagicMock(return_value=self.mock_traversal_spec)),
            ('salt.utils.vmware.get_mors_with_properties',
             self.mock_get_mors))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_si', 'mock_dc_ref', 'mock_traversal_spec',
                     'mock_entries', 'mock_get_mors'):
            delattr(self, attr)

    def test_get_managed_object_name_call(self):
        mock_get_managed_object_name = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vmware.get_network_folder(self.mock_dc_ref)
        mock_get_managed_object_name.assert_called_once_with(self.mock_dc_ref)

    def test_traversal_spec(self):
        mock_traversal_spec = MagicMock(return_value='traversal_spec')
        with patch(
            'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
            mock_traversal_spec):

            vmware.get_network_folder(self.mock_dc_ref)
        mock_traversal_spec.assert_called_once_with(
            path='networkFolder', skip=False, type=vim.Datacenter)

    def test_get_mors_with_properties(self):
        vmware.get_network_folder(self.mock_dc_ref)
        self.mock_get_mors.assert_called_once_with(
            self.mock_si, vim.Folder, container_ref=self.mock_dc_ref,
            property_list=['name'], traversal_spec=self.mock_traversal_spec)

    def test_get_no_network_folder(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=[])):
            with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                vmware.get_network_folder(self.mock_dc_ref)
        self.assertEqual(excinfo.exception.strerror,
                         'Network folder in datacenter \'fake_dc\' wasn\'t '
                         'retrieved')

    def test_get_network_folder(self):
        ret = vmware.get_network_folder(self.mock_dc_ref)
        self.assertEqual(ret, self.mock_entries[0]['object'])


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class CreateDvsTestCase(TestCase):
    def setUp(self):
        self.mock_dc_ref = MagicMock()
        self.mock_dvs_create_spec = MagicMock()
        self.mock_task = MagicMock(spec=FakeTaskClass)
        self.mock_netw_folder = \
                MagicMock(CreateDVS_Task=MagicMock(
                    return_value=self.mock_task))
        self.mock_wait_for_task = MagicMock()

        patches = (
            ('salt.utils.vmware.get_managed_object_name',
             MagicMock(return_value='fake_dc')),
            ('salt.utils.vmware.get_network_folder',
             MagicMock(return_value=self.mock_netw_folder)),
            ('salt.utils.vmware.wait_for_task', self.mock_wait_for_task))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_dc_ref', 'mock_dvs_create_spec',
                     'mock_task', 'mock_netw_folder', 'mock_wait_for_task'):
            delattr(self, attr)

    def test_get_managed_object_name_call(self):
        mock_get_managed_object_name = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vmware.create_dvs(self.mock_dc_ref, 'fake_dvs')
        mock_get_managed_object_name.assert_called_once_with(self.mock_dc_ref)

    def test_no_dvs_create_spec(self):
        mock_spec = MagicMock(configSpec=None)
        mock_config_spec = MagicMock()
        mock_dvs_create_spec = MagicMock(return_value=mock_spec)
        mock_vmware_dvs_config_spec = \
                MagicMock(return_value=mock_config_spec)
        with patch('salt.utils.vmware.vim.DVSCreateSpec',
                   mock_dvs_create_spec):
            with patch('salt.utils.vmware.vim.VMwareDVSConfigSpec',
                       mock_vmware_dvs_config_spec):
                vmware.create_dvs(self.mock_dc_ref, 'fake_dvs')
        mock_dvs_create_spec.assert_called_once_with()
        mock_vmware_dvs_config_spec.assert_called_once_with()
        self.assertEqual(mock_spec.configSpec, mock_config_spec)
        self.assertEqual(mock_config_spec.name, 'fake_dvs')
        self.mock_netw_folder.CreateDVS_Task.assert_called_once_with(mock_spec)

    def test_get_network_folder(self):
        mock_get_network_folder = MagicMock()
        with patch('salt.utils.vmware.get_network_folder',
                   mock_get_network_folder):
            vmware.create_dvs(self.mock_dc_ref, 'fake_dvs')
        mock_get_network_folder.assert_called_once_with(self.mock_dc_ref)

    def test_create_dvs_task_passed_in_spec(self):
        vmware.create_dvs(self.mock_dc_ref, 'fake_dvs',
                          dvs_create_spec=self.mock_dvs_create_spec)
        self.mock_netw_folder.CreateDVS_Task.assert_called_once_with(
            self.mock_dvs_create_spec)

    def test_create_dvs_task_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_netw_folder.CreateDVS_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            vmware.create_dvs(self.mock_dc_ref, 'fake_dvs',
                              dvs_create_spec=self.mock_dvs_create_spec)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_create_dvs_task_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_netw_folder.CreateDVS_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            vmware.create_dvs(self.mock_dc_ref, 'fake_dvs',
                              dvs_create_spec=self.mock_dvs_create_spec)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_create_dvs_task_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_netw_folder.CreateDVS_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            vmware.create_dvs(self.mock_dc_ref, 'fake_dvs',
                              dvs_create_spec=self.mock_dvs_create_spec)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_wait_for_tasks(self):
        vmware.create_dvs(self.mock_dc_ref, 'fake_dvs',
                          dvs_create_spec=self.mock_dvs_create_spec)
        self.mock_wait_for_task.assert_called_once_with(
            self.mock_task, 'fake_dvs',
            '<class \'unit.utils.vmware.test_dvs.FakeTaskClass\'>')
