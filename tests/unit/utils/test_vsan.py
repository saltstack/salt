# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests functions in salt.utils.vsan
'''

# Import python libraries
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt testing libraries
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock, \
        PropertyMock

# Import Salt libraries
from salt.exceptions import VMwareApiError, VMwareRuntimeError, \
        VMwareObjectRetrievalError
from salt.utils import vsan

try:
    from pyVmomi import vim, vmodl
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


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@skipIf(not HAS_PYVSAN, 'The \'vsan\' ext library is missing')
class GetVsanClusterConfigSystemTestCase(TestCase, LoaderModuleMockMixin):
    '''Tests for salt.utils.vsan.get_vsan_cluster_config_system'''
    def setup_loader_modules(self):
        return {vsan: {
            '__virtual__': MagicMock(return_value='vsan'),
            'sys': MagicMock(),
            'ssl': MagicMock()}}

    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_ret = MagicMock()
        patches = (('salt.utils.vsan.vsanapiutils.GetVsanVcMos',
                    MagicMock(
                        return_value={'vsan-cluster-config-system':
                                      self.mock_ret})),)
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

        type(vsan.sys).version_info = PropertyMock(return_value=(2, 7, 9))
        self.mock_context = MagicMock()
        self.mock_create_default_context = \
                MagicMock(return_value=self.mock_context)
        vsan.ssl.create_default_context = self.mock_create_default_context

    def tearDown(self):
        for attr in ('mock_si', 'mock_ret', 'mock_context',
                     'mock_create_default_context'):
            delattr(self, attr)

    def test_ssl_default_context_loaded(self):
        vsan.get_vsan_cluster_config_system(self.mock_si)
        self.mock_create_default_context.assert_called_once_with()
        self.assertFalse(self.mock_context.check_hostname)
        self.assertEqual(self.mock_context.verify_mode, vsan.ssl.CERT_NONE)

    def test_ssl_default_context_not_loaded(self):
        type(vsan.sys).version_info = PropertyMock(return_value=(2, 7, 8))
        vsan.get_vsan_cluster_config_system(self.mock_si)
        self.assertEqual(self.mock_create_default_context.call_count, 0)

    def test_GetVsanVcMos_call(self):
        mock_get_vsan_vc_mos = MagicMock()
        with patch('salt.utils.vsan.vsanapiutils.GetVsanVcMos',
                   mock_get_vsan_vc_mos):
            vsan.get_vsan_cluster_config_system(self.mock_si)
        mock_get_vsan_vc_mos.assert_called_once_with(self.mock_si._stub,
                                                     context=self.mock_context)

    def test_return(self):
        ret = vsan.get_vsan_cluster_config_system(self.mock_si)
        self.assertEqual(ret, self.mock_ret)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@skipIf(not HAS_PYVSAN, 'The \'pyvsan\' bindings are missing')
class GetVsanDiskManagementSystemTestCase(TestCase, LoaderModuleMockMixin):
    '''Tests for salt.utils.vsan.get_vsan_disk_management_system'''
    def setup_loader_modules(self):
        return {vsan: {
            '__virtual__': MagicMock(return_value='vsan'),
            'sys': MagicMock(),
            'ssl': MagicMock()}}

    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_ret = MagicMock()
        patches = (('salt.utils.vsan.vsanapiutils.GetVsanVcMos',
                    MagicMock(
                        return_value={'vsan-disk-management-system':
                                      self.mock_ret})),)
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

        type(vsan.sys).version_info = PropertyMock(return_value=(2, 7, 9))
        self.mock_context = MagicMock()
        self.mock_create_default_context = \
                MagicMock(return_value=self.mock_context)
        vsan.ssl.create_default_context = self.mock_create_default_context

    def tearDown(self):
        for attr in ('mock_si', 'mock_ret', 'mock_context',
                     'mock_create_default_context'):
            delattr(self, attr)

    def test_ssl_default_context_loaded(self):
        vsan.get_vsan_disk_management_system(self.mock_si)
        self.mock_create_default_context.assert_called_once_with()
        self.assertFalse(self.mock_context.check_hostname)
        self.assertEqual(self.mock_context.verify_mode, vsan.ssl.CERT_NONE)

    def test_ssl_default_context_not_loaded(self):
        type(vsan.sys).version_info = PropertyMock(return_value=(2, 7, 8))
        vsan.get_vsan_disk_management_system(self.mock_si)
        self.assertEqual(self.mock_create_default_context.call_count, 0)

    def test_GetVsanVcMos_call(self):
        mock_get_vsan_vc_mos = MagicMock()
        with patch('salt.utils.vsan.vsanapiutils.GetVsanVcMos',
                   mock_get_vsan_vc_mos):
            vsan.get_vsan_disk_management_system(self.mock_si)
        mock_get_vsan_vc_mos.assert_called_once_with(self.mock_si._stub,
                                                     context=self.mock_context)

    def test_return(self):
        ret = vsan.get_vsan_disk_management_system(self.mock_si)
        self.assertEqual(ret, self.mock_ret)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@skipIf(not HAS_PYVSAN, 'The \'vsan\' ext library is missing')
class GetHostVsanSystemTestCase(TestCase):
    '''Tests for salt.utils.vsan.get_host_vsan_system'''

    def setUp(self):
        self.mock_host_ref = MagicMock()
        self.mock_si = MagicMock()
        self.mock_traversal_spec = MagicMock()
        self.mock_vsan_system = MagicMock()
        patches = (
            ('salt.utils.vmware.get_managed_object_name',
             MagicMock(return_value='fake_hostname')),
            ('salt.utils.vsan.vmodl.query.PropertyCollector.TraversalSpec',
             MagicMock(return_value=self.mock_traversal_spec)),
            ('salt.utils.vmware.get_mors_with_properties',
             MagicMock(return_value=self.mock_traversal_spec)),
            ('salt.utils.vmware.get_mors_with_properties',
             MagicMock(return_value=[{'object': self.mock_vsan_system}])))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_get_hostname(self):
        mock_get_managed_object_name = MagicMock(return_value='fake_hostname')
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vsan.get_host_vsan_system(self.mock_si, self.mock_host_ref)
        mock_get_managed_object_name.assert_called_once_with(
            self.mock_host_ref)

    def test_hostname_argument(self):
        mock_get_managed_object_name = MagicMock(return_value='fake_hostname')
        with patch('salt.utils.vmware.get_managed_object_name',
                   MagicMock(return_value='fake_hostname')):
            vsan.get_host_vsan_system(self.mock_si,
                                      self.mock_host_ref,
                                      hostname='passedin_hostname')
        self.assertEqual(mock_get_managed_object_name.call_count, 0)

    def test_traversal_spec(self):
        mock_traversal_spec = MagicMock(return_value=self.mock_traversal_spec)
        with patch(
            'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
            mock_traversal_spec):

            vsan.get_host_vsan_system(self.mock_si, self.mock_host_ref)
        mock_traversal_spec.assert_called_once_with(
            path='configManager.vsanSystem',
            type=vim.HostSystem,
            skip=False)

    def test_get_mors_with_properties(self):
        mock_get_mors = \
                MagicMock(return_value=[{'object': self.mock_vsan_system}])
        with patch('salt.utils.vmware.get_mors_with_properties',
                   mock_get_mors):
            vsan.get_host_vsan_system(self.mock_si, self.mock_host_ref)
        mock_get_mors.assert_called_once_with(
            self.mock_si,
            vim.HostVsanSystem,
            property_list=['config.enabled'],
            container_ref=self.mock_host_ref,
            traversal_spec=self.mock_traversal_spec)

    def test_empty_mors_result(self):
        mock_get_mors = MagicMock(return_value=None)
        with patch('salt.utils.vmware.get_mors_with_properties',
                   mock_get_mors):

            with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                vsan.get_host_vsan_system(self.mock_si, self.mock_host_ref)
        self.assertEqual(excinfo.exception.strerror,
                         'Host\'s \'fake_hostname\' VSAN system was '
                         'not retrieved')

    def test_valid_mors_result(self):
        res = vsan.get_host_vsan_system(self.mock_si, self.mock_host_ref)
        self.assertEqual(res, self.mock_vsan_system)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@skipIf(not HAS_PYVSAN, 'The \'vsan\' ext library is missing')
class CreateDiskgroupTestCase(TestCase):
    '''Tests for salt.utils.vsan.create_diskgroup'''
    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_task = MagicMock()
        self.mock_initialise_disk_mapping = \
                MagicMock(return_value=self.mock_task)
        self.mock_vsan_disk_mgmt_system = MagicMock(
            InitializeDiskMappings=self.mock_initialise_disk_mapping)
        self.mock_host_ref = MagicMock()
        self.mock_cache_disk = MagicMock()
        self.mock_cap_disk1 = MagicMock()
        self.mock_cap_disk2 = MagicMock()
        self.mock_spec = MagicMock()
        patches = (
            ('salt.utils.vmware.get_managed_object_name',
             MagicMock(return_value='fake_hostname')),
            ('salt.utils.vsan.vim.VimVsanHostDiskMappingCreationSpec',
             MagicMock(return_value=self.mock_spec)),
            ('salt.utils.vsan._wait_for_tasks', MagicMock()))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_get_hostname(self):
        mock_get_managed_object_name = MagicMock(return_value='fake_hostname')
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vsan.create_diskgroup(self.mock_si, self.mock_vsan_disk_mgmt_system,
                                  self.mock_host_ref, self.mock_cache_disk,
                                  [self.mock_cap_disk1, self.mock_cap_disk2])
        mock_get_managed_object_name.assert_called_once_with(
            self.mock_host_ref)

    def test_vsan_spec_all_flash(self):
        self.mock_cap_disk1.ssd = True
        vsan.create_diskgroup(self.mock_si, self.mock_vsan_disk_mgmt_system,
                              self.mock_host_ref, self.mock_cache_disk,
                              [self.mock_cap_disk1, self.mock_cap_disk2])
        self.assertEqual(self.mock_spec.capacityDisks, [self.mock_cap_disk1,
                                                        self.mock_cap_disk2])
        self.assertEqual(self.mock_spec.cacheDisks, [self.mock_cache_disk])
        self.assertEqual(self.mock_spec.creationType, 'allFlash')
        self.assertEqual(self.mock_spec.host, self.mock_host_ref)

    def test_vsan_spec_hybrid(self):
        self.mock_cap_disk1.ssd = False
        vsan.create_diskgroup(self.mock_si, self.mock_vsan_disk_mgmt_system,
                              self.mock_host_ref, self.mock_cache_disk,
                              [self.mock_cap_disk1, self.mock_cap_disk2])
        self.mock_cap_disk1.ssd = False
        self.assertEqual(self.mock_spec.creationType, 'hybrid')

    def test_initialize_disk_mapping(self):
        vsan.create_diskgroup(self.mock_si, self.mock_vsan_disk_mgmt_system,
                              self.mock_host_ref, self.mock_cache_disk,
                              [self.mock_cap_disk1, self.mock_cap_disk2])
        self.mock_initialise_disk_mapping.assert_called_once_with(
            self.mock_spec)

    def test_initialize_disk_mapping_raise_no_permission(self):
        err = vim.fault.NoPermission()
        err.privilegeId = 'Fake privilege'
        self.mock_vsan_disk_mgmt_system.InitializeDiskMappings = \
            MagicMock(side_effect=err)
        with self.assertRaises(VMwareApiError) as excinfo:
            vsan.create_diskgroup(self.mock_si, self.mock_vsan_disk_mgmt_system,
                                  self.mock_host_ref, self.mock_cache_disk,
                                  [self.mock_cap_disk1, self.mock_cap_disk2])
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_initialize_disk_mapping_raise_vim_fault(self):
        err = vim.fault.VimFault()
        err.msg = 'vim_fault'
        self.mock_vsan_disk_mgmt_system.InitializeDiskMappings = \
            MagicMock(side_effect=err)
        with self.assertRaises(VMwareApiError) as excinfo:
            vsan.create_diskgroup(self.mock_si, self.mock_vsan_disk_mgmt_system,
                                  self.mock_host_ref, self.mock_cache_disk,
                                  [self.mock_cap_disk1, self.mock_cap_disk2])
        self.assertEqual(excinfo.exception.strerror, 'vim_fault')

    def test_initialize_disk_mapping_raise_method_not_found(self):
        err = vmodl.fault.MethodNotFound()
        err.method = 'fake_method'
        self.mock_vsan_disk_mgmt_system.InitializeDiskMappings = \
            MagicMock(side_effect=err)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            vsan.create_diskgroup(self.mock_si, self.mock_vsan_disk_mgmt_system,
                                  self.mock_host_ref, self.mock_cache_disk,
                                  [self.mock_cap_disk1, self.mock_cap_disk2])
        self.assertEqual(excinfo.exception.strerror,
                         'Method \'fake_method\' not found')

    def test_initialize_disk_mapping_raise_runtime_fault(self):
        err = vmodl.RuntimeFault()
        err.msg = 'runtime_fault'
        self.mock_vsan_disk_mgmt_system.InitializeDiskMappings = \
            MagicMock(side_effect=err)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            vsan.create_diskgroup(self.mock_si, self.mock_vsan_disk_mgmt_system,
                                  self.mock_host_ref, self.mock_cache_disk,
                                  [self.mock_cap_disk1, self.mock_cap_disk2])
        self.assertEqual(excinfo.exception.strerror, 'runtime_fault')

    def test__wait_for_tasks(self):
        mock___wait_for_tasks = MagicMock()
        with patch('salt.utils.vsan._wait_for_tasks',
                   mock___wait_for_tasks):
            vsan.create_diskgroup(self.mock_si, self.mock_vsan_disk_mgmt_system,
                                  self.mock_host_ref, self.mock_cache_disk,
                                  [self.mock_cap_disk1, self.mock_cap_disk2])
        mock___wait_for_tasks.assert_called_once_with(
            [self.mock_task], self.mock_si)

    def test_result(self):
        res = vsan.create_diskgroup(self.mock_si,
                                    self.mock_vsan_disk_mgmt_system,
                                    self.mock_host_ref, self.mock_cache_disk,
                                    [self.mock_cap_disk1, self.mock_cap_disk2])
        self.assertTrue(res)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@skipIf(not HAS_PYVSAN, 'The \'vsan\' ext library is missing')
class AddCapacityToDiskGroupTestCase(TestCase):
    '''Tests for salt.utils.vsan.add_capacity_to_diskgroup'''
    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_task = MagicMock()
        self.mock_initialise_disk_mapping = \
                MagicMock(return_value=self.mock_task)
        self.mock_vsan_disk_mgmt_system = MagicMock(
            InitializeDiskMappings=self.mock_initialise_disk_mapping)
        self.mock_host_ref = MagicMock()
        self.mock_cache_disk = MagicMock()
        self.mock_diskgroup = MagicMock(ssd=self.mock_cache_disk)
        self.mock_cap_disk1 = MagicMock()
        self.mock_cap_disk2 = MagicMock()
        self.mock_spec = MagicMock()
        patches = (
            ('salt.utils.vmware.get_managed_object_name',
             MagicMock(return_value='fake_hostname')),
            ('salt.utils.vsan.vim.VimVsanHostDiskMappingCreationSpec',
             MagicMock(return_value=self.mock_spec)),
            ('salt.utils.vsan._wait_for_tasks', MagicMock()))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_get_hostname(self):
        mock_get_managed_object_name = MagicMock(return_value='fake_hostname')
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vsan.add_capacity_to_diskgroup(
                self.mock_si, self.mock_vsan_disk_mgmt_system,
                self.mock_host_ref, self.mock_diskgroup,
                [self.mock_cap_disk1, self.mock_cap_disk2])
        mock_get_managed_object_name.assert_called_once_with(
            self.mock_host_ref)

    def test_vsan_spec_all_flash(self):
        self.mock_cap_disk1.ssd = True
        vsan.add_capacity_to_diskgroup(
            self.mock_si, self.mock_vsan_disk_mgmt_system,
            self.mock_host_ref, self.mock_diskgroup,
            [self.mock_cap_disk1, self.mock_cap_disk2])
        self.assertEqual(self.mock_spec.capacityDisks, [self.mock_cap_disk1,
                                                        self.mock_cap_disk2])
        self.assertEqual(self.mock_spec.cacheDisks, [self.mock_cache_disk])
        self.assertEqual(self.mock_spec.creationType, 'allFlash')
        self.assertEqual(self.mock_spec.host, self.mock_host_ref)

    def test_vsan_spec_hybrid(self):
        self.mock_cap_disk1.ssd = False
        vsan.add_capacity_to_diskgroup(
            self.mock_si, self.mock_vsan_disk_mgmt_system,
            self.mock_host_ref, self.mock_diskgroup,
            [self.mock_cap_disk1, self.mock_cap_disk2])
        self.mock_cap_disk1.ssd = False
        self.assertEqual(self.mock_spec.creationType, 'hybrid')

    def test_initialize_disk_mapping(self):
        vsan.add_capacity_to_diskgroup(
            self.mock_si, self.mock_vsan_disk_mgmt_system,
            self.mock_host_ref, self.mock_diskgroup,
            [self.mock_cap_disk1, self.mock_cap_disk2])
        self.mock_initialise_disk_mapping.assert_called_once_with(
            self.mock_spec)

    def test_initialize_disk_mapping_raise_no_permission(self):
        err = vim.fault.NoPermission()
        err.privilegeId = 'Fake privilege'
        self.mock_vsan_disk_mgmt_system.InitializeDiskMappings = \
            MagicMock(side_effect=err)
        with self.assertRaises(VMwareApiError) as excinfo:
            vsan.add_capacity_to_diskgroup(
                self.mock_si, self.mock_vsan_disk_mgmt_system,
                self.mock_host_ref, self.mock_diskgroup,
                [self.mock_cap_disk1, self.mock_cap_disk2])
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_initialize_disk_mapping_raise_vim_fault(self):
        err = vim.fault.VimFault()
        err.msg = 'vim_fault'
        self.mock_vsan_disk_mgmt_system.InitializeDiskMappings = \
            MagicMock(side_effect=err)
        with self.assertRaises(VMwareApiError) as excinfo:
            vsan.add_capacity_to_diskgroup(
                self.mock_si, self.mock_vsan_disk_mgmt_system,
                self.mock_host_ref, self.mock_diskgroup,
                [self.mock_cap_disk1, self.mock_cap_disk2])
        self.assertEqual(excinfo.exception.strerror, 'vim_fault')

    def test_initialize_disk_mapping_raise_method_not_found(self):
        err = vmodl.fault.MethodNotFound()
        err.method = 'fake_method'
        self.mock_vsan_disk_mgmt_system.InitializeDiskMappings = \
            MagicMock(side_effect=err)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            vsan.add_capacity_to_diskgroup(
                self.mock_si, self.mock_vsan_disk_mgmt_system,
                self.mock_host_ref, self.mock_diskgroup,
                [self.mock_cap_disk1, self.mock_cap_disk2])
        self.assertEqual(excinfo.exception.strerror,
                         'Method \'fake_method\' not found')

    def test_initialize_disk_mapping_raise_runtime_fault(self):
        err = vmodl.RuntimeFault()
        err.msg = 'runtime_fault'
        self.mock_vsan_disk_mgmt_system.InitializeDiskMappings = \
            MagicMock(side_effect=err)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            vsan.add_capacity_to_diskgroup(
                self.mock_si, self.mock_vsan_disk_mgmt_system,
                self.mock_host_ref, self.mock_diskgroup,
                [self.mock_cap_disk1, self.mock_cap_disk2])
        self.assertEqual(excinfo.exception.strerror, 'runtime_fault')

    def test__wait_for_tasks(self):
        mock___wait_for_tasks = MagicMock()
        with patch('salt.utils.vsan._wait_for_tasks',
                   mock___wait_for_tasks):
            vsan.add_capacity_to_diskgroup(
                self.mock_si, self.mock_vsan_disk_mgmt_system,
                self.mock_host_ref, self.mock_diskgroup,
                [self.mock_cap_disk1, self.mock_cap_disk2])
        mock___wait_for_tasks.assert_called_once_with(
            [self.mock_task], self.mock_si)

    def test_result(self):
        res = vsan.add_capacity_to_diskgroup(
            self.mock_si, self.mock_vsan_disk_mgmt_system,
            self.mock_host_ref, self.mock_diskgroup,
            [self.mock_cap_disk1, self.mock_cap_disk2])
        self.assertTrue(res)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@skipIf(not HAS_PYVSAN, 'The \'vsan\' ext library is missing')
class RemoveCapacityFromDiskGroup(TestCase):
    '''Tests for salt.utils.vsan.remove_capacity_from_diskgroup'''
    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_task = MagicMock()
        self.mock_remove_disk = \
                MagicMock(return_value=self.mock_task)
        self.mock_host_vsan_system = MagicMock(
            RemoveDisk_Task=self.mock_remove_disk)
        self.mock_host_ref = MagicMock()
        self.mock_cache_disk = MagicMock()
        self.mock_diskgroup = MagicMock(ssd=self.mock_cache_disk)
        self.mock_cap_disk1 = MagicMock()
        self.mock_cap_disk2 = MagicMock()
        self.mock_spec = MagicMock()
        patches = (
            ('salt.utils.vmware.get_managed_object_name',
             MagicMock(return_value='fake_hostname')),
            ('salt.utils.vsan.get_host_vsan_system',
             MagicMock(return_value=self.mock_host_vsan_system)),
            ('salt.utils.vsan.vim.HostMaintenanceSpec',
             MagicMock(return_value=self.mock_spec)),
            ('salt.utils.vsan.vim.VsanHostDecommissionMode', MagicMock()),
            ('salt.utils.vmware.wait_for_task', MagicMock()))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_get_hostname(self):
        mock_get_managed_object_name = MagicMock(return_value='fake_hostname')
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vsan.remove_capacity_from_diskgroup(
                self.mock_si, self.mock_host_ref, self.mock_diskgroup,
                [self.mock_cap_disk1, self.mock_cap_disk2])
        mock_get_managed_object_name.assert_called_once_with(
            self.mock_host_ref)

    def test_maintenance_mode_evacuate_all_data(self):
        vsan.remove_capacity_from_diskgroup(
            self.mock_si, self.mock_host_ref, self.mock_diskgroup,
            [self.mock_cap_disk1, self.mock_cap_disk2])
        self.assertEqual(self.mock_spec.vsanMode.objectAction,
                         vim.VsanHostDecommissionModeObjectAction.evacuateAllData)

    def test_maintenance_mode_no_action(self):
        vsan.remove_capacity_from_diskgroup(
            self.mock_si, self.mock_host_ref, self.mock_diskgroup,
            [self.mock_cap_disk1, self.mock_cap_disk2],
            data_evacuation=False)
        self.assertEqual(self.mock_spec.vsanMode.objectAction,
                         vim.VsanHostDecommissionModeObjectAction.noAction)

    def test_remove_disk(self):
        vsan.remove_capacity_from_diskgroup(
            self.mock_si, self.mock_host_ref, self.mock_diskgroup,
            [self.mock_cap_disk1, self.mock_cap_disk2])
        self.mock_remove_disk.assert_called_once_with(
            disk=[self.mock_cap_disk1, self.mock_cap_disk2],
            maintenanceSpec=self.mock_spec)

    def test_remove_disk_raise_no_permission(self):
        err = vim.fault.NoPermission()
        err.privilegeId = 'Fake privilege'
        self.mock_host_vsan_system.RemoveDisk_Task = \
            MagicMock(side_effect=err)
        with self.assertRaises(VMwareApiError) as excinfo:
            vsan.remove_capacity_from_diskgroup(
                self.mock_si, self.mock_host_ref, self.mock_diskgroup,
                [self.mock_cap_disk1, self.mock_cap_disk2])
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_remove_disk_raise_vim_fault(self):
        err = vim.fault.VimFault()
        err.msg = 'vim_fault'
        self.mock_host_vsan_system.RemoveDisk_Task = \
            MagicMock(side_effect=err)
        with self.assertRaises(VMwareApiError) as excinfo:
            vsan.remove_capacity_from_diskgroup(
                self.mock_si, self.mock_host_ref, self.mock_diskgroup,
                [self.mock_cap_disk1, self.mock_cap_disk2])
        self.assertEqual(excinfo.exception.strerror, 'vim_fault')

    def test_remove_disk_raise_runtime_fault(self):
        err = vmodl.RuntimeFault()
        err.msg = 'runtime_fault'
        self.mock_host_vsan_system.RemoveDisk_Task = \
            MagicMock(side_effect=err)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            vsan.remove_capacity_from_diskgroup(
                self.mock_si, self.mock_host_ref, self.mock_diskgroup,
                [self.mock_cap_disk1, self.mock_cap_disk2])
        self.assertEqual(excinfo.exception.strerror, 'runtime_fault')

    def test_wait_for_tasks(self):
        mock_wait_for_task = MagicMock()
        with patch('salt.utils.vmware.wait_for_task',
                   mock_wait_for_task):
            vsan.remove_capacity_from_diskgroup(
                self.mock_si, self.mock_host_ref, self.mock_diskgroup,
                [self.mock_cap_disk1, self.mock_cap_disk2])
        mock_wait_for_task.assert_called_once_with(
            self.mock_task, 'fake_hostname', 'remove_capacity')

    def test_result(self):
        res = vsan.remove_capacity_from_diskgroup(
            self.mock_si, self.mock_host_ref, self.mock_diskgroup,
            [self.mock_cap_disk1, self.mock_cap_disk2])
        self.assertTrue(res)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@skipIf(not HAS_PYVSAN, 'The \'vsan\' ext library is missing')
class RemoveDiskgroup(TestCase):
    '''Tests for salt.utils.vsan.remove_diskgroup'''
    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_task = MagicMock()
        self.mock_remove_disk_mapping = \
                MagicMock(return_value=self.mock_task)
        self.mock_host_vsan_system = MagicMock(
            RemoveDiskMapping_Task=self.mock_remove_disk_mapping)
        self.mock_host_ref = MagicMock()
        self.mock_cache_disk = MagicMock()
        self.mock_diskgroup = MagicMock(ssd=self.mock_cache_disk)
        self.mock_cap_disk1 = MagicMock()
        self.mock_cap_disk2 = MagicMock()
        self.mock_spec = MagicMock()
        patches = (
            ('salt.utils.vmware.get_managed_object_name',
             MagicMock(return_value='fake_hostname')),
            ('salt.utils.vsan.get_host_vsan_system',
             MagicMock(return_value=self.mock_host_vsan_system)),
            ('salt.utils.vsan.vim.HostMaintenanceSpec',
             MagicMock(return_value=self.mock_spec)),
            ('salt.utils.vsan.vim.VsanHostDecommissionMode', MagicMock()),
            ('salt.utils.vmware.wait_for_task', MagicMock()))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_get_hostname(self):
        mock_get_managed_object_name = MagicMock(return_value='fake_hostname')
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vsan.remove_diskgroup(
                self.mock_si, self.mock_host_ref, self.mock_diskgroup)
        mock_get_managed_object_name.assert_called_once_with(
            self.mock_host_ref)

    def test_maintenance_mode_evacuate_all_data(self):
        vsan.remove_diskgroup(
            self.mock_si, self.mock_host_ref, self.mock_diskgroup)
        vsan.remove_capacity_from_diskgroup(
            self.mock_si, self.mock_host_ref, self.mock_diskgroup,
            [self.mock_cap_disk1, self.mock_cap_disk2])
        self.assertEqual(self.mock_spec.vsanMode.objectAction,
                         vim.VsanHostDecommissionModeObjectAction.evacuateAllData)

    def test_maintenance_mode_no_action(self):
        vsan.remove_diskgroup(
            self.mock_si, self.mock_host_ref, self.mock_diskgroup)
        vsan.remove_capacity_from_diskgroup(
            self.mock_si, self.mock_host_ref, self.mock_diskgroup,
            [self.mock_cap_disk1, self.mock_cap_disk2],
            data_evacuation=False)
        self.assertEqual(self.mock_spec.vsanMode.objectAction,
                         vim.VsanHostDecommissionModeObjectAction.noAction)

    def test_remove_disk_mapping(self):
        vsan.remove_diskgroup(
            self.mock_si, self.mock_host_ref, self.mock_diskgroup)
        vsan.remove_capacity_from_diskgroup(
            self.mock_si, self.mock_host_ref, self.mock_diskgroup,
            [self.mock_cap_disk1, self.mock_cap_disk2])
        self.mock_remove_disk_mapping.assert_called_once_with(
            mapping=[self.mock_diskgroup],
            maintenanceSpec=self.mock_spec)

    def test_remove_disk_mapping_raise_no_permission(self):
        vsan.remove_diskgroup(
            self.mock_si, self.mock_host_ref, self.mock_diskgroup)
        err = vim.fault.NoPermission()
        err.privilegeId = 'Fake privilege'
        self.mock_host_vsan_system.RemoveDiskMapping_Task = \
            MagicMock(side_effect=err)
        with self.assertRaises(VMwareApiError) as excinfo:
            vsan.remove_diskgroup(
                self.mock_si, self.mock_host_ref, self.mock_diskgroup)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_remove_disk_mapping_raise_vim_fault(self):
        err = vim.fault.VimFault()
        err.msg = 'vim_fault'
        self.mock_host_vsan_system.RemoveDiskMapping_Task = \
            MagicMock(side_effect=err)
        with self.assertRaises(VMwareApiError) as excinfo:
            vsan.remove_diskgroup(
                self.mock_si, self.mock_host_ref, self.mock_diskgroup)
        self.assertEqual(excinfo.exception.strerror, 'vim_fault')

    def test_remove_disk_mapping_raise_runtime_fault(self):
        err = vmodl.RuntimeFault()
        err.msg = 'runtime_fault'
        self.mock_host_vsan_system.RemoveDiskMapping_Task = \
            MagicMock(side_effect=err)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            vsan.remove_diskgroup(
                self.mock_si, self.mock_host_ref, self.mock_diskgroup)
        self.assertEqual(excinfo.exception.strerror, 'runtime_fault')

    def test_wait_for_tasks(self):
        mock_wait_for_task = MagicMock()
        with patch('salt.utils.vmware.wait_for_task',
                   mock_wait_for_task):
            vsan.remove_diskgroup(
                self.mock_si, self.mock_host_ref, self.mock_diskgroup)
        mock_wait_for_task.assert_called_once_with(
            self.mock_task, 'fake_hostname', 'remove_diskgroup')

    def test_result(self):
        res = vsan.remove_diskgroup(
            self.mock_si, self.mock_host_ref, self.mock_diskgroup)
        self.assertTrue(res)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@skipIf(not HAS_PYVSAN, 'The \'vsan\' ext library is missing')
class GetClusterVsanInfoTestCase(TestCase, LoaderModuleMockMixin):
    '''Tests for salt.utils.vsan.get_cluster_vsan_info'''
    def setup_loader_modules(self):
        return {vsan: {
            '__virtual__': MagicMock(return_value='vsan')}}

    def setUp(self):
        self.mock_cl_ref = MagicMock()
        self.mock_si = MagicMock()
        patches = (
            ('salt.utils.vmware.get_managed_object_name', MagicMock()),
            ('salt.utils.vmware.get_service_instance_from_managed_object',
             MagicMock(return_value=self.mock_si)),
            ('salt.utils.vsan.get_vsan_cluster_config_system', MagicMock()))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_si', 'mock_cl_ref'):
            delattr(self, attr)

    def test_get_managed_object_name_call(self):
        mock_get_managed_object_name = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vsan.get_cluster_vsan_info(self.mock_cl_ref)
        mock_get_managed_object_name.assert_called_once_with(self.mock_cl_ref)

    def test_get_vsan_cluster_config_system_call(self):
        mock_get_vsan_cl_syst = MagicMock()
        with patch('salt.utils.vsan.get_vsan_cluster_config_system',
                   mock_get_vsan_cl_syst):
            vsan.get_cluster_vsan_info(self.mock_cl_ref)
        mock_get_vsan_cl_syst.assert_called_once_with(self.mock_si)

    def test_VsanClusterGetConfig_call(self):
        mock_vsan_sys = MagicMock()
        with patch('salt.utils.vsan.get_vsan_cluster_config_system',
                   MagicMock(return_value=mock_vsan_sys)):
            vsan.get_cluster_vsan_info(self.mock_cl_ref)
        mock_vsan_sys.VsanClusterGetConfig.assert_called_once_with(
            self.mock_cl_ref)

    def test_VsanClusterGetConfig_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        with patch('salt.utils.vsan.get_vsan_cluster_config_system',
                   MagicMock(return_value=MagicMock(
                       VsanClusterGetConfig=MagicMock(side_effect=exc)))):
            with self.assertRaises(VMwareApiError) as excinfo:
                vsan.get_cluster_vsan_info(self.mock_cl_ref)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_VsanClusterGetConfig_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        with patch('salt.utils.vsan.get_vsan_cluster_config_system',
                   MagicMock(return_value=MagicMock(
                       VsanClusterGetConfig=MagicMock(side_effect=exc)))):
            with self.assertRaises(VMwareApiError) as excinfo:
                vsan.get_cluster_vsan_info(self.mock_cl_ref)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_VsanClusterGetConfig_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        with patch('salt.utils.vsan.get_vsan_cluster_config_system',
                   MagicMock(return_value=MagicMock(
                       VsanClusterGetConfig=MagicMock(side_effect=exc)))):
            with self.assertRaises(VMwareRuntimeError) as excinfo:
                vsan.get_cluster_vsan_info(self.mock_cl_ref)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@skipIf(not HAS_PYVSAN, 'The \'vsan\' ext library is missing')
class ReconfigureClusterVsanTestCase(TestCase):
    '''Tests for salt.utils.vsan.reconfigure_cluster_vsan'''
    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_task = MagicMock()
        self.mock_cl_reconf = MagicMock(return_value=self.mock_task)
        self.mock_get_vsan_conf_sys = MagicMock(
            return_value=MagicMock(VsanClusterReconfig=self.mock_cl_reconf))
        self.mock_cl_ref = MagicMock()
        self.mock_cl_vsan_spec = MagicMock()
        patches = (
            ('salt.utils.vmware.get_managed_object_name', MagicMock()),
            ('salt.utils.vmware.get_service_instance_from_managed_object',
             MagicMock(return_value=self.mock_si)),
            ('salt.utils.vsan.get_vsan_cluster_config_system',
             self.mock_get_vsan_conf_sys),
            ('salt.utils.vsan._wait_for_tasks', MagicMock()))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_si', 'mock_cl_reconf', 'mock_get_vsan_conf_sys',
                     'mock_cl_ref', 'mock_cl_vsan_spec', 'mock_task'):
            delattr(self, attr)

    def test_get_cluster_name_call(self):
        get_managed_object_name_mock = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   get_managed_object_name_mock):

            vsan.reconfigure_cluster_vsan(self.mock_cl_ref,
                                          self.mock_cl_vsan_spec)
        get_managed_object_name_mock.assert_called_once_with(
            self.mock_cl_ref)

    def test_get_service_instance_call(self):
        get_service_instance_from_managed_object_mock = MagicMock()
        with patch(
            'salt.utils.vmware.get_service_instance_from_managed_object',
            get_service_instance_from_managed_object_mock):

            vsan.reconfigure_cluster_vsan(self.mock_cl_ref,
                                          self.mock_cl_vsan_spec)
        get_service_instance_from_managed_object_mock.assert_called_once_with(
            self.mock_cl_ref)

    def test_get_vsan_cluster_config_system_call(self):
        vsan.reconfigure_cluster_vsan(self.mock_cl_ref,
                                      self.mock_cl_vsan_spec)
        self.mock_get_vsan_conf_sys.assert_called_once_with(self.mock_si)

    def test_cluster_reconfig_call(self):
        vsan.reconfigure_cluster_vsan(self.mock_cl_ref,
                                      self.mock_cl_vsan_spec)
        self.mock_cl_reconf.assert_called_once_with(
            self.mock_cl_ref, self.mock_cl_vsan_spec)

    def test_cluster_reconfig_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        with patch('salt.utils.vsan.get_vsan_cluster_config_system',
                   MagicMock(return_value=MagicMock(
                       VsanClusterReconfig=MagicMock(side_effect=exc)))):
            with self.assertRaises(VMwareApiError) as excinfo:
                vsan.reconfigure_cluster_vsan(self.mock_cl_ref,
                                              self.mock_cl_vsan_spec)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_cluster_reconfig_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        with patch('salt.utils.vsan.get_vsan_cluster_config_system',
                   MagicMock(return_value=MagicMock(
                       VsanClusterReconfig=MagicMock(side_effect=exc)))):
            with self.assertRaises(VMwareApiError) as excinfo:
                vsan.reconfigure_cluster_vsan(self.mock_cl_ref,
                                              self.mock_cl_vsan_spec)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_cluster_reconfig_raises_vmodl_runtime_error(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'VimRuntime msg'
        with patch('salt.utils.vsan.get_vsan_cluster_config_system',
                   MagicMock(return_value=MagicMock(
                       VsanClusterReconfig=MagicMock(side_effect=exc)))):
            with self.assertRaises(VMwareRuntimeError) as excinfo:
                vsan.reconfigure_cluster_vsan(self.mock_cl_ref,
                                              self.mock_cl_vsan_spec)
        self.assertEqual(excinfo.exception.strerror, 'VimRuntime msg')

    def test__wait_for_tasks_call(self):
        mock_wait_for_tasks = MagicMock()
        with patch('salt.utils.vsan._wait_for_tasks', mock_wait_for_tasks):
            vsan.reconfigure_cluster_vsan(self.mock_cl_ref,
                                          self.mock_cl_vsan_spec)
        mock_wait_for_tasks.assert_called_once_with([self.mock_task],
                                                    self.mock_si)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@skipIf(not HAS_PYVSAN, 'The \'vsan\' ext library is missing')
class _WaitForTasks(TestCase, LoaderModuleMockMixin):
    '''Tests for salt.utils.vsan._wait_for_tasks'''
    def setup_loader_modules(self):
        return {vsan: {
            '__virtual__': MagicMock(return_value='vsan')}}

    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_tasks = MagicMock()
        patches = (('salt.utils.vsan.vsanapiutils.WaitForTasks', MagicMock()),)
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        for attr in ('mock_si', 'mock_tasks'):
            delattr(self, attr)

    def test_wait_for_tasks_call(self):
        mock_wait_for_tasks = MagicMock()
        with patch('salt.utils.vsan.vsanapiutils.WaitForTasks',
                   mock_wait_for_tasks):
            vsan._wait_for_tasks(self.mock_tasks, self.mock_si)
        mock_wait_for_tasks.assert_called_once_with(self.mock_tasks,
                                                    self.mock_si)

    def test_wait_for_tasks_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        with patch('salt.utils.vsan.vsanapiutils.WaitForTasks',
                   MagicMock(side_effect=exc)):
            with self.assertRaises(VMwareApiError) as excinfo:
                vsan._wait_for_tasks(self.mock_tasks, self.mock_si)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_wait_for_tasks_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        with patch('salt.utils.vsan.vsanapiutils.WaitForTasks',
                   MagicMock(side_effect=exc)):
            with self.assertRaises(VMwareApiError) as excinfo:
                vsan._wait_for_tasks(self.mock_tasks, self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_wait_for_tasks_raises_vmodl_runtime_error(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'VimRuntime msg'
        with patch('salt.utils.vsan.vsanapiutils.WaitForTasks',
                   MagicMock(side_effect=exc)):
            with self.assertRaises(VMwareRuntimeError) as excinfo:
                vsan._wait_for_tasks(self.mock_tasks, self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'VimRuntime msg')
