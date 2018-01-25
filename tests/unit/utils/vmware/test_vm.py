# -*- coding: utf-8 -*-
'''
:codeauthor: :email:`Agnes Tevesz <agnes.tevesz@morganstanley.com>`

Tests for virtual machine related functions in salt.utils.vmware
'''

# Import python libraries
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt testing libraries
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock

from salt.exceptions import VMwareRuntimeError, VMwareApiError, ArgumentValueError

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
class ConvertToKbTestCase(TestCase):
    '''
    Tests for converting units
    '''

    def setUp(self):
        pass

    def test_gb_conversion_call(self):
        self.assertEqual(vmware.convert_to_kb('Gb', 10), {'size': int(10485760), 'unit': 'KB'})

    def test_mb_conversion_call(self):
        self.assertEqual(vmware.convert_to_kb('Mb', 10), {'size': int(10240), 'unit': 'KB'})

    def test_kb_conversion_call(self):
        self.assertEqual(vmware.convert_to_kb('Kb', 10), {'size': int(10), 'unit': 'KB'})

    def test_conversion_bad_input_argument_fault(self):
        self.assertRaises(ArgumentValueError, vmware.convert_to_kb, 'test', 10)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@patch('salt.utils.vmware.get_managed_object_name', MagicMock())
@patch('salt.utils.vmware.wait_for_task', MagicMock())
class CreateVirtualMachineTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.create_vm
    '''

    def setUp(self):
        self.vm_name = 'fake_vm'
        self.mock_task = MagicMock()
        self.mock_config_spec = MagicMock()
        self.mock_resourcepool_object = MagicMock()
        self.mock_host_object = MagicMock()
        self.mock_vm_create_task = MagicMock(return_value=self.mock_task)
        self.mock_folder_object = MagicMock(CreateVM_Task=self.mock_vm_create_task)

    def test_create_vm_pool_task_call(self):
        vmware.create_vm(self.vm_name, self.mock_config_spec,
                         self.mock_folder_object, self.mock_resourcepool_object)
        self.assert_called_once(self.mock_vm_create_task)

    def test_create_vm_host_task_call(self):
        vmware.create_vm(self.vm_name, self.mock_config_spec,
                         self.mock_folder_object, self.mock_resourcepool_object,
                         host_object=self.mock_host_object)
        self.assert_called_once(self.mock_vm_create_task)

    def test_create_vm_raise_no_permission(self):
        exception = vim.fault.NoPermission()
        exception.msg = 'vim.fault.NoPermission msg'
        self.mock_folder_object.CreateVM_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareApiError) as exc:
            vmware.create_vm(self.vm_name, self.mock_config_spec,
                             self.mock_folder_object, self.mock_resourcepool_object)
        self.assertEqual(exc.exception.strerror,
                         'Not enough permissions. Required privilege: ')

    def test_create_vm_raise_vim_fault(self):
        exception = vim.fault.VimFault()
        exception.msg = 'vim.fault.VimFault msg'
        self.mock_folder_object.CreateVM_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareApiError) as exc:
            vmware.create_vm(self.vm_name, self.mock_config_spec,
                             self.mock_folder_object, self.mock_resourcepool_object)
        self.assertEqual(exc.exception.strerror, 'vim.fault.VimFault msg')

    def test_create_vm_raise_runtime_fault(self):
        exception = vmodl.RuntimeFault()
        exception.msg = 'vmodl.RuntimeFault msg'
        self.mock_folder_object.CreateVM_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareRuntimeError) as exc:
            vmware.create_vm(self.vm_name, self.mock_config_spec,
                             self.mock_folder_object, self.mock_resourcepool_object)
        self.assertEqual(exc.exception.strerror, 'vmodl.RuntimeFault msg')

    def test_create_vm_wait_for_task(self):
        mock_wait_for_task = MagicMock()
        with patch('salt.utils.vmware.wait_for_task', mock_wait_for_task):
            vmware.create_vm(self.vm_name, self.mock_config_spec,
                             self.mock_folder_object, self.mock_resourcepool_object)
        mock_wait_for_task.assert_called_once_with(
            self.mock_task, self.vm_name, 'CreateVM Task', 10, 'info')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@patch('salt.utils.vmware.get_managed_object_name', MagicMock())
@patch('salt.utils.vmware.wait_for_task', MagicMock())
class RegisterVirtualMachineTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.register_vm
    '''

    def setUp(self):
        self.vm_name = 'fake_vm'
        self.mock_task = MagicMock()
        self.mock_vmx_path = MagicMock()
        self.mock_resourcepool_object = MagicMock()
        self.mock_host_object = MagicMock()
        self.mock_vm_register_task = MagicMock(return_value=self.mock_task)
        self.vm_folder_object = MagicMock(RegisterVM_Task=self.mock_vm_register_task)
        self.datacenter = MagicMock(vmFolder=self.vm_folder_object)

    def test_register_vm_pool_task_call(self):
        vmware.register_vm(self.datacenter, self.vm_name, self.mock_vmx_path,
                           self.mock_resourcepool_object)
        self.assert_called_once(self.mock_vm_register_task)

    def test_register_vm_host_task_call(self):
        vmware.register_vm(self.datacenter, self.vm_name, self.mock_vmx_path,
                           self.mock_resourcepool_object,
                           host_object=self.mock_host_object)
        self.assert_called_once(self.mock_vm_register_task)

    def test_register_vm_raise_no_permission(self):
        exception = vim.fault.NoPermission()
        self.vm_folder_object.RegisterVM_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareApiError) as exc:
            vmware.register_vm(self.datacenter, self.vm_name, self.mock_vmx_path,
                               self.mock_resourcepool_object)
        self.assertEqual(exc.exception.strerror,
                         'Not enough permissions. Required privilege: ')

    def test_register_vm_raise_vim_fault(self):
        exception = vim.fault.VimFault()
        exception.msg = 'vim.fault.VimFault msg'
        self.vm_folder_object.RegisterVM_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareApiError) as exc:
            vmware.register_vm(self.datacenter, self.vm_name, self.mock_vmx_path,
                               self.mock_resourcepool_object)
        self.assertEqual(exc.exception.strerror, 'vim.fault.VimFault msg')

    def test_register_vm_raise_runtime_fault(self):
        exception = vmodl.RuntimeFault()
        exception.msg = 'vmodl.RuntimeFault msg'
        self.vm_folder_object.RegisterVM_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareRuntimeError) as exc:
            vmware.register_vm(self.datacenter, self.vm_name, self.mock_vmx_path,
                               self.mock_resourcepool_object)
        self.assertEqual(exc.exception.strerror, 'vmodl.RuntimeFault msg')

    def test_register_vm_wait_for_task(self):
        mock_wait_for_task = MagicMock()
        with patch('salt.utils.vmware.wait_for_task', mock_wait_for_task):
            vmware.register_vm(self.datacenter, self.vm_name, self.mock_vmx_path,
                               self.mock_resourcepool_object)
        mock_wait_for_task.assert_called_once_with(
            self.mock_task, self.vm_name, 'RegisterVM Task')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@patch('salt.utils.vmware.get_managed_object_name', MagicMock())
@patch('salt.utils.vmware.wait_for_task', MagicMock())
class UpdateVirtualMachineTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.update_vm
    '''

    def setUp(self):
        self.mock_task = MagicMock()
        self.mock_config_spec = MagicMock()
        self.mock_vm_update_task = MagicMock(return_value=self.mock_task)
        self.mock_vm_ref = MagicMock(ReconfigVM_Task=self.mock_vm_update_task)

    def test_update_vm_task_call(self):
        vmware.update_vm(self.mock_vm_ref, self.mock_config_spec)
        self.assert_called_once(self.mock_vm_update_task)

    def test_update_vm_raise_vim_fault(self):
        exception = vim.fault.VimFault()
        exception.msg = 'vim.fault.VimFault'
        self.mock_vm_ref.ReconfigVM_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareApiError) as exc:
            vmware.update_vm(self.mock_vm_ref, self.mock_config_spec)
        self.assertEqual(exc.exception.strerror, 'vim.fault.VimFault')

    def test_update_vm_raise_runtime_fault(self):
        exception = vmodl.RuntimeFault()
        exception.msg = 'vmodl.RuntimeFault'
        self.mock_vm_ref.ReconfigVM_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareRuntimeError) as exc:
            vmware.update_vm(self.mock_vm_ref, self.mock_config_spec)
        self.assertEqual(exc.exception.strerror, 'vmodl.RuntimeFault')

    def test_update_vm_wait_for_task(self):
        mock_wait_for_task = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   MagicMock(return_value='my_vm')):
            with patch('salt.utils.vmware.wait_for_task', mock_wait_for_task):
                vmware.update_vm(self.mock_vm_ref, self.mock_config_spec)
        mock_wait_for_task.assert_called_once_with(
            self.mock_task, 'my_vm', 'ReconfigureVM Task')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@patch('salt.utils.vmware.get_managed_object_name', MagicMock())
@patch('salt.utils.vmware.wait_for_task', MagicMock())
class DeleteVirtualMachineTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.delete_vm
    '''

    def setUp(self):
        self.mock_task = MagicMock()
        self.mock_vm_destroy_task = MagicMock(return_value=self.mock_task)
        self.mock_vm_ref = MagicMock(Destroy_Task=self.mock_vm_destroy_task)

    def test_destroy_vm_task_call(self):
        vmware.delete_vm(self.mock_vm_ref)
        self.assert_called_once(self.mock_vm_destroy_task)

    def test_destroy_vm_raise_vim_fault(self):
        exception = vim.fault.VimFault()
        exception.msg = 'vim.fault.VimFault'
        self.mock_vm_ref.Destroy_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareApiError) as exc:
            vmware.delete_vm(self.mock_vm_ref)
        self.assertEqual(exc.exception.strerror, 'vim.fault.VimFault')

    def test_destroy_vm_raise_runtime_fault(self):
        exception = vmodl.RuntimeFault()
        exception.msg = 'vmodl.RuntimeFault'
        self.mock_vm_ref.Destroy_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareRuntimeError) as exc:
            vmware.delete_vm(self.mock_vm_ref)
        self.assertEqual(exc.exception.strerror, 'vmodl.RuntimeFault')

    def test_destroy_vm_wait_for_task(self):
        mock_wait_for_task = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   MagicMock(return_value='my_vm')):
            with patch('salt.utils.vmware.wait_for_task', mock_wait_for_task):
                vmware.delete_vm(self.mock_vm_ref)
        mock_wait_for_task.assert_called_once_with(
            self.mock_task, 'my_vm', 'Destroy Task')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@patch('salt.utils.vmware.get_managed_object_name', MagicMock())
class UnregisterVirtualMachineTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.unregister_vm
    '''

    def setUp(self):
        self.mock_vm_unregister = MagicMock()
        self.mock_vm_ref = MagicMock(UnregisterVM=self.mock_vm_unregister)

    def test_unregister_vm_task_call(self):
        vmware.unregister_vm(self.mock_vm_ref)
        self.assert_called_once(self.mock_vm_unregister)

    def test_unregister_vm_raise_vim_fault(self):
        exception = vim.fault.VimFault()
        exception.msg = 'vim.fault.VimFault'
        self.mock_vm_ref.UnregisterVM = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareApiError) as exc:
            vmware.unregister_vm(self.mock_vm_ref)
        self.assertEqual(exc.exception.strerror, 'vim.fault.VimFault')

    def test_unregister_vm_raise_runtime_fault(self):
        exception = vmodl.RuntimeFault()
        exception.msg = 'vmodl.RuntimeFault'
        self.mock_vm_ref.UnregisterVM = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareRuntimeError) as exc:
            vmware.unregister_vm(self.mock_vm_ref)
        self.assertEqual(exc.exception.strerror, 'vmodl.RuntimeFault')
