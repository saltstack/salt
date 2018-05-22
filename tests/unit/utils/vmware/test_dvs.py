# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for dvs related functions in salt.utils.vmware
'''

# Import python libraries
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt testing libraries
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock, call
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
        mock_traversal_spec.assert_has_calls(
            [call(path='childEntity', skip=False, type=vim.Folder),
             call(path='networkFolder', skip=True, type=vim.Datacenter,
                  selectSet=['traversal_spec'])])

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


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class UpdateDvsTestCase(TestCase):
    def setUp(self):
        self.mock_task = MagicMock(spec=FakeTaskClass)
        self.mock_dvs_ref = MagicMock(
            ReconfigureDvs_Task=MagicMock(return_value=self.mock_task))
        self.mock_dvs_spec = MagicMock()
        self.mock_wait_for_task = MagicMock()

        patches = (
            ('salt.utils.vmware.get_managed_object_name',
             MagicMock(return_value='fake_dvs')),
            ('salt.utils.vmware.wait_for_task', self.mock_wait_for_task))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_dvs_ref', 'mock_task', 'mock_dvs_spec',
                     'mock_wait_for_task'):
            delattr(self, attr)

    def test_get_managed_object_name_call(self):
        mock_get_managed_object_name = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vmware.update_dvs(self.mock_dvs_ref, self.mock_dvs_spec)
        mock_get_managed_object_name.assert_called_once_with(self.mock_dvs_ref)

    def test_reconfigure_dvs_task(self):
        vmware.update_dvs(self.mock_dvs_ref, self.mock_dvs_spec)
        self.mock_dvs_ref.ReconfigureDvs_Task.assert_called_once_with(
            self.mock_dvs_spec)

    def test_reconfigure_dvs_task_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_dvs_ref.ReconfigureDvs_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            vmware.update_dvs(self.mock_dvs_ref, self.mock_dvs_spec)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_reconfigure_dvs_task_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_dvs_ref.ReconfigureDvs_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            vmware.update_dvs(self.mock_dvs_ref, self.mock_dvs_spec)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_reconfigure_dvs_task_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_dvs_ref.ReconfigureDvs_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            vmware.update_dvs(self.mock_dvs_ref, self.mock_dvs_spec)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_wait_for_tasks(self):
        vmware.update_dvs(self.mock_dvs_ref, self.mock_dvs_spec)
        self.mock_wait_for_task.assert_called_once_with(
            self.mock_task, 'fake_dvs',
            '<class \'unit.utils.vmware.test_dvs.FakeTaskClass\'>')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class SetDvsNetworkResourceManagementEnabledTestCase(TestCase):
    def setUp(self):
        self.mock_enabled = MagicMock()
        self.mock_dvs_ref = MagicMock(
            EnableNetworkResourceManagement=MagicMock())

        patches = (
            ('salt.utils.vmware.get_managed_object_name',
             MagicMock(return_value='fake_dvs')),)
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_dvs_ref', 'mock_enabled'):
            delattr(self, attr)

    def test_get_managed_object_name_call(self):
        mock_get_managed_object_name = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vmware.set_dvs_network_resource_management_enabled(
                self.mock_dvs_ref, self.mock_enabled)
        mock_get_managed_object_name.assert_called_once_with(self.mock_dvs_ref)

    def test_enable_network_resource_management(self):
        vmware.set_dvs_network_resource_management_enabled(
            self.mock_dvs_ref, self.mock_enabled)
        self.mock_dvs_ref.EnableNetworkResourceManagement.assert_called_once_with(
            enable=self.mock_enabled)

    def test_enable_network_resource_management_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_dvs_ref.EnableNetworkResourceManagement = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            vmware.set_dvs_network_resource_management_enabled(
                self.mock_dvs_ref, self.mock_enabled)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_enable_network_resource_management_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_dvs_ref.EnableNetworkResourceManagement = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            vmware.set_dvs_network_resource_management_enabled(
                self.mock_dvs_ref, self.mock_enabled)

    def test_enable_network_resource_management_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_dvs_ref.EnableNetworkResourceManagement = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            vmware.set_dvs_network_resource_management_enabled(
                self.mock_dvs_ref, self.mock_enabled)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetDvportgroupsTestCase(TestCase):
    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_dc_ref = MagicMock(spec=vim.Datacenter)
        self.mock_dvs_ref = MagicMock(spec=vim.DistributedVirtualSwitch)
        self.mock_traversal_spec = MagicMock()
        self.mock_items = [{'object': MagicMock(),
                            'name': 'fake_pg1'},
                           {'object': MagicMock(),
                            'name': 'fake_pg2'},
                           {'object': MagicMock(),
                            'name': 'fake_pg3'}]
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
        for attr in ('mock_si', 'mock_dc_ref', 'mock_dvs_ref',
                     'mock_traversal_spec', 'mock_items', 'mock_get_mors'):
            delattr(self, attr)

    def test_unsupported_parrent(self):
        with self.assertRaises(ArgumentValueError) as excinfo:
            vmware.get_dvportgroups(MagicMock())
        self.assertEqual(excinfo.exception.strerror,
                         'Parent has to be either a datacenter, or a '
                         'distributed virtual switch')

    def test_get_managed_object_name_call(self):
        mock_get_managed_object_name = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vmware.get_dvportgroups(self.mock_dc_ref)
        mock_get_managed_object_name.assert_called_once_with(self.mock_dc_ref)

    def test_traversal_spec_datacenter_parent(self):
        mock_traversal_spec = MagicMock(return_value='traversal_spec')
        with patch(
            'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
            mock_traversal_spec):

            vmware.get_dvportgroups(self.mock_dc_ref)
        mock_traversal_spec.assert_has_calls(
            [call(path='childEntity', skip=False, type=vim.Folder),
             call(path='networkFolder', skip=True, type=vim.Datacenter,
                  selectSet=['traversal_spec'])])

    def test_traversal_spec_dvs_parent(self):
        mock_traversal_spec = MagicMock(return_value='traversal_spec')
        with patch(
            'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
            mock_traversal_spec):

            vmware.get_dvportgroups(self.mock_dvs_ref)
        mock_traversal_spec.assert_called_once_with(
            path='portgroup', skip=False, type=vim.DistributedVirtualSwitch)

    def test_get_mors_with_properties(self):
        vmware.get_dvportgroups(self.mock_dvs_ref)
        self.mock_get_mors.assert_called_once_with(
            self.mock_si, vim.DistributedVirtualPortgroup,
            container_ref=self.mock_dvs_ref, property_list=['name'],
            traversal_spec=self.mock_traversal_spec)

    def test_get_no_pgs(self):
        ret = vmware.get_dvportgroups(self.mock_dvs_ref)
        self.assertEqual(ret, [])

    def test_get_all_pgs(self):
        ret = vmware.get_dvportgroups(self.mock_dvs_ref,
                                      get_all_portgroups=True)
        self.assertEqual(ret, [i['object'] for i in self.mock_items])

    def test_filtered_pgs(self):
        ret = vmware.get_dvss(self.mock_dc_ref,
                              dvs_names=['fake_pg1', 'fake_pg3', 'no_pg'])
        self.assertEqual(ret, [self.mock_items[0]['object'],
                               self.mock_items[2]['object']])


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetUplinkDvportgroupTestCase(TestCase):
    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_dvs_ref = MagicMock(spec=vim.DistributedVirtualSwitch)
        self.mock_traversal_spec = MagicMock()
        self.mock_items = [{'object': MagicMock(),
                            'tag': [MagicMock(key='fake_tag')]},
                           {'object': MagicMock(),
                            'tag': [MagicMock(key='SYSTEM/DVS.UPLINKPG')]}]
        self.mock_get_mors = MagicMock(return_value=self.mock_items)

        patches = (
            ('salt.utils.vmware.get_managed_object_name',
             MagicMock(return_value='fake_dvs')),
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
        for attr in ('mock_si', 'mock_dvs_ref', 'mock_traversal_spec',
                     'mock_items', 'mock_get_mors'):
            delattr(self, attr)

    def test_get_managed_object_name_call(self):
        mock_get_managed_object_name = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vmware.get_uplink_dvportgroup(self.mock_dvs_ref)
        mock_get_managed_object_name.assert_called_once_with(self.mock_dvs_ref)

    def test_traversal_spec(self):
        mock_traversal_spec = MagicMock(return_value='traversal_spec')
        with patch(
            'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
            mock_traversal_spec):

            vmware.get_uplink_dvportgroup(self.mock_dvs_ref)
        mock_traversal_spec.assert_called_once_with(
            path='portgroup', skip=False, type=vim.DistributedVirtualSwitch)

    def test_get_mors_with_properties(self):
        vmware.get_uplink_dvportgroup(self.mock_dvs_ref)
        self.mock_get_mors.assert_called_once_with(
            self.mock_si, vim.DistributedVirtualPortgroup,
            container_ref=self.mock_dvs_ref, property_list=['tag'],
            traversal_spec=self.mock_traversal_spec)

    def test_get_no_uplink_pg(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=[])):
            with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                vmware.get_uplink_dvportgroup(self.mock_dvs_ref)
        self.assertEqual(excinfo.exception.strerror,
                         'Uplink portgroup of DVS \'fake_dvs\' wasn\'t found')

    def test_get_uplink_pg(self):
        ret = vmware.get_uplink_dvportgroup(self.mock_dvs_ref)
        self.assertEqual(ret, self.mock_items[1]['object'])


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class CreateDvportgroupTestCase(TestCase):
    def setUp(self):
        self.mock_pg_spec = MagicMock()
        self.mock_task = MagicMock(spec=FakeTaskClass)
        self.mock_dvs_ref = \
                MagicMock(CreateDVPortgroup_Task=MagicMock(
                    return_value=self.mock_task))
        self.mock_wait_for_task = MagicMock()

        patches = (
            ('salt.utils.vmware.get_managed_object_name',
             MagicMock(return_value='fake_dvs')),
            ('salt.utils.vmware.wait_for_task', self.mock_wait_for_task))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_pg_spec', 'mock_dvs_ref', 'mock_task',
                     'mock_wait_for_task'):
            delattr(self, attr)

    def test_get_managed_object_name_call(self):
        mock_get_managed_object_name = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vmware.create_dvportgroup(self.mock_dvs_ref, self.mock_pg_spec)
        mock_get_managed_object_name.assert_called_once_with(self.mock_dvs_ref)

    def test_create_dvporgroup_task(self):
        vmware.create_dvportgroup(self.mock_dvs_ref, self.mock_pg_spec)
        self.mock_dvs_ref.CreateDVPortgroup_Task.assert_called_once_with(
            self.mock_pg_spec)

    def test_create_dvporgroup_task_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_dvs_ref.CreateDVPortgroup_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            vmware.create_dvportgroup(self.mock_dvs_ref, self.mock_pg_spec)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_create_dvporgroup_task_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_dvs_ref.CreateDVPortgroup_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            vmware.create_dvportgroup(self.mock_dvs_ref, self.mock_pg_spec)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_create_dvporgroup_task_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_dvs_ref.CreateDVPortgroup_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            vmware.create_dvportgroup(self.mock_dvs_ref, self.mock_pg_spec)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_wait_for_tasks(self):
        vmware.create_dvportgroup(self.mock_dvs_ref, self.mock_pg_spec)
        self.mock_wait_for_task.assert_called_once_with(
            self.mock_task, 'fake_dvs',
            '<class \'unit.utils.vmware.test_dvs.FakeTaskClass\'>')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class UpdateDvportgroupTestCase(TestCase):
    def setUp(self):
        self.mock_pg_spec = MagicMock()
        self.mock_task = MagicMock(spec=FakeTaskClass)
        self.mock_pg_ref = \
                MagicMock(ReconfigureDVPortgroup_Task=MagicMock(
                    return_value=self.mock_task))
        self.mock_wait_for_task = MagicMock()

        patches = (
            ('salt.utils.vmware.get_managed_object_name',
             MagicMock(return_value='fake_pg')),
            ('salt.utils.vmware.wait_for_task', self.mock_wait_for_task))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_pg_spec', 'mock_pg_ref', 'mock_task',
                     'mock_wait_for_task'):
            delattr(self, attr)

    def test_get_managed_object_name_call(self):
        mock_get_managed_object_name = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vmware.update_dvportgroup(self.mock_pg_ref, self.mock_pg_spec)
        mock_get_managed_object_name.assert_called_once_with(self.mock_pg_ref)

    def test_reconfigure_dvporgroup_task(self):
        vmware.update_dvportgroup(self.mock_pg_ref, self.mock_pg_spec)
        self.mock_pg_ref.ReconfigureDVPortgroup_Task.assert_called_once_with(
            self.mock_pg_spec)

    def test_reconfigure_dvporgroup_task_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_pg_ref.ReconfigureDVPortgroup_Task = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            vmware.update_dvportgroup(self.mock_pg_ref, self.mock_pg_spec)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_reconfigure_dvporgroup_task_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_pg_ref.ReconfigureDVPortgroup_Task = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            vmware.update_dvportgroup(self.mock_pg_ref, self.mock_pg_spec)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_reconfigure_dvporgroup_task_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_pg_ref.ReconfigureDVPortgroup_Task = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            vmware.update_dvportgroup(self.mock_pg_ref, self.mock_pg_spec)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_wait_for_tasks(self):
        vmware.update_dvportgroup(self.mock_pg_ref, self.mock_pg_spec)
        self.mock_wait_for_task.assert_called_once_with(
            self.mock_task, 'fake_pg',
            '<class \'unit.utils.vmware.test_dvs.FakeTaskClass\'>')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class RemoveDvportgroupTestCase(TestCase):
    def setUp(self):
        self.mock_task = MagicMock(spec=FakeTaskClass)
        self.mock_pg_ref = \
                MagicMock(Destroy_Task=MagicMock(
                    return_value=self.mock_task))
        self.mock_wait_for_task = MagicMock()

        patches = (
            ('salt.utils.vmware.get_managed_object_name',
             MagicMock(return_value='fake_pg')),
            ('salt.utils.vmware.wait_for_task', self.mock_wait_for_task))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_pg_ref', 'mock_task', 'mock_wait_for_task'):
            delattr(self, attr)

    def test_get_managed_object_name_call(self):
        mock_get_managed_object_name = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vmware.remove_dvportgroup(self.mock_pg_ref)
        mock_get_managed_object_name.assert_called_once_with(self.mock_pg_ref)

    def test_destroy_task(self):
        vmware.remove_dvportgroup(self.mock_pg_ref)
        self.mock_pg_ref.Destroy_Task.assert_called_once_with()

    def test_destroy_task_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_pg_ref.Destroy_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            vmware.remove_dvportgroup(self.mock_pg_ref)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_destroy_treconfigure_dvporgroup_task_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_pg_ref.Destroy_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            vmware.remove_dvportgroup(self.mock_pg_ref)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_destroy_treconfigure_dvporgroup_task_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_pg_ref.Destroy_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            vmware.remove_dvportgroup(self.mock_pg_ref)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_wait_for_tasks(self):
        vmware.remove_dvportgroup(self.mock_pg_ref)
        self.mock_wait_for_task.assert_called_once_with(
            self.mock_task, 'fake_pg',
            '<class \'unit.utils.vmware.test_dvs.FakeTaskClass\'>')
