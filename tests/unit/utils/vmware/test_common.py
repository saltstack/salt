# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for common functions in salt.utils.vmware
'''

# Import python libraries
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt testing libraries
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock, call, \
        PropertyMock

# Import Salt libraries
import salt.exceptions as excs
import salt.utils.vmware
# Import Third Party Libs
from salt.ext import six
try:
    from pyVmomi import vim, vmodl
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

# Get Logging Started
log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class WaitForTaskTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.wait_for_task
    '''

    def setUp(self):
        patches = (
            ('salt.utils.vmware.time.time', MagicMock(return_value=1)),
            ('salt.utils.vmware.time.sleep', MagicMock(return_value=None))
        )
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_first_task_info_raise_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        mock_task = MagicMock()
        type(mock_task).info = PropertyMock(side_effect=exc)
        with self.assertRaises(excs.VMwareApiError) as excinfo:
            salt.utils.vmware.wait_for_task(mock_task,
                                            'fake_instance_name',
                                            'task_type')
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_first_task_info_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        mock_task = MagicMock()
        type(mock_task).info = PropertyMock(side_effect=exc)
        with self.assertRaises(excs.VMwareApiError) as excinfo:
            salt.utils.vmware.wait_for_task(mock_task,
                                            'fake_instance_name',
                                            'task_type')
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_first_task_info_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        mock_task = MagicMock()
        type(mock_task).info = PropertyMock(side_effect=exc)
        with self.assertRaises(excs.VMwareRuntimeError) as excinfo:
            salt.utils.vmware.wait_for_task(mock_task,
                                            'fake_instance_name',
                                            'task_type')
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_inner_loop_task_info_raise_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        mock_task = MagicMock()
        mock_info1 = MagicMock()
        type(mock_task).info = PropertyMock(
            side_effect=[mock_info1, exc])
        type(mock_info1).state = PropertyMock(side_effect=['running', 'bad'])
        with self.assertRaises(excs.VMwareApiError) as excinfo:
            salt.utils.vmware.wait_for_task(mock_task,
                                            'fake_instance_name',
                                            'task_type')
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_inner_loop_task_info_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        mock_task = MagicMock()
        mock_info1 = MagicMock()
        type(mock_task).info = PropertyMock(
            side_effect=[mock_info1, exc])
        type(mock_info1).state = PropertyMock(side_effect=['running', 'bad'])
        with self.assertRaises(excs.VMwareApiError) as excinfo:
            salt.utils.vmware.wait_for_task(mock_task,
                                            'fake_instance_name',
                                            'task_type')
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_inner_loop_task_info_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        mock_task = MagicMock()
        mock_info1 = MagicMock()
        type(mock_task).info = PropertyMock(
            side_effect=[mock_info1, exc])
        type(mock_info1).state = PropertyMock(side_effect=['running', 'bad'])
        with self.assertRaises(excs.VMwareRuntimeError) as excinfo:
            salt.utils.vmware.wait_for_task(mock_task,
                                            'fake_instance_name',
                                            'task_type')
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_info_state_running(self):
        # The 'bad' values are invalid in the while loop
        mock_task = MagicMock()
        prop_mock_state = PropertyMock(side_effect=['running', 'bad', 'bad',
                                                    'success'])
        prop_mock_result = PropertyMock()
        type(mock_task.info).state = prop_mock_state
        type(mock_task.info).result = prop_mock_result
        salt.utils.vmware.wait_for_task(mock_task,
                                        'fake_instance_name',
                                        'task_type')
        self.assertEqual(prop_mock_state.call_count, 4)
        self.assertEqual(prop_mock_result.call_count, 1)

    def test_info_state_running_continues_loop(self):
        mock_task = MagicMock()
        # The 'fake' values are required to match all the lookups and end the
        # loop
        prop_mock_state = PropertyMock(side_effect=['running', 'fake', 'fake',
                                                    'success'])
        prop_mock_result = PropertyMock()
        type(mock_task.info).state = prop_mock_state
        type(mock_task.info).result = prop_mock_result
        salt.utils.vmware.wait_for_task(mock_task,
                                        'fake_instance_name',
                                        'task_type')
        self.assertEqual(prop_mock_state.call_count, 4)
        self.assertEqual(prop_mock_result.call_count, 1)

    def test_info_state_queued_continues_loop(self):
        mock_task = MagicMock()
        # The 'fake' values are required to match all the lookups and end the
        # loop
        prop_mock_state = PropertyMock(side_effect=['fake', 'queued', 'fake',
                                                    'fake', 'success'])
        prop_mock_result = PropertyMock()
        type(mock_task.info).state = prop_mock_state
        type(mock_task.info).result = prop_mock_result
        salt.utils.vmware.wait_for_task(mock_task,
                                        'fake_instance_name',
                                        'task_type')
        self.assertEqual(prop_mock_state.call_count, 5)
        self.assertEqual(prop_mock_result.call_count, 1)

    def test_info_state_success(self):
        mock_task = MagicMock()
        prop_mock_state = PropertyMock(return_value='success')
        prop_mock_result = PropertyMock()
        type(mock_task.info).state = prop_mock_state
        type(mock_task.info).result = prop_mock_result
        salt.utils.vmware.wait_for_task(mock_task,
                                        'fake_instance_name',
                                        'task_type')
        self.assertEqual(prop_mock_state.call_count, 3)
        self.assertEqual(prop_mock_result.call_count, 1)

    def test_info_error_exception(self):
        mock_task = MagicMock()
        prop_mock_state = PropertyMock(return_value='error')
        prop_mock_error = PropertyMock(side_effect=Exception('error exc'))
        type(mock_task.info).state = prop_mock_state
        type(mock_task.info).error = prop_mock_error
        with self.assertRaises(Exception) as excinfo:
            salt.utils.vmware.wait_for_task(mock_task,
                                            'fake_instance_name',
                                            'task_type')
        self.assertEqual(six.text_type(excinfo.exception), 'error exc')

    def test_info_error_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        mock_task = MagicMock()
        prop_mock_state = PropertyMock(return_value='error')
        prop_mock_error = PropertyMock(side_effect=exc)
        type(mock_task.info).state = prop_mock_state
        type(mock_task.info).error = prop_mock_error
        with self.assertRaises(excs.VMwareApiError) as excinfo:
            salt.utils.vmware.wait_for_task(mock_task,
                                            'fake_instance_name',
                                            'task_type')
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_info_error_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        mock_task = MagicMock()
        prop_mock_state = PropertyMock(return_value='error')
        prop_mock_error = PropertyMock(side_effect=exc)
        type(mock_task.info).state = prop_mock_state
        type(mock_task.info).error = prop_mock_error
        with self.assertRaises(excs.VMwareApiError) as excinfo:
            salt.utils.vmware.wait_for_task(mock_task,
                                            'fake_instance_name',
                                            'task_type')
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_info_error_system_fault(self):
        exc = vmodl.fault.SystemError()
        exc.msg = 'SystemError msg'
        mock_task = MagicMock()
        prop_mock_state = PropertyMock(return_value='error')
        prop_mock_error = PropertyMock(side_effect=exc)
        type(mock_task.info).state = prop_mock_state
        type(mock_task.info).error = prop_mock_error
        with self.assertRaises(excs.VMwareSystemError) as excinfo:
            salt.utils.vmware.wait_for_task(mock_task,
                                            'fake_instance_name',
                                            'task_type')
        self.assertEqual(excinfo.exception.strerror, 'SystemError msg')

    def test_info_error_invalid_argument_no_fault_message(self):
        exc = vmodl.fault.InvalidArgument()
        exc.faultMessage = None
        exc.msg = 'InvalidArgumentFault msg'
        mock_task = MagicMock()
        prop_mock_state = PropertyMock(return_value='error')
        prop_mock_error = PropertyMock(side_effect=exc)
        type(mock_task.info).state = prop_mock_state
        type(mock_task.info).error = prop_mock_error
        with self.assertRaises(excs.VMwareApiError) as excinfo:
            salt.utils.vmware.wait_for_task(mock_task,
                                            'fake_instance_name',
                                            'task_type')
        self.assertEqual(excinfo.exception.strerror,
                         'InvalidArgumentFault msg')

    def test_info_error_invalid_argument_with_fault_message(self):
        exc = vmodl.fault.InvalidArgument()
        fault_message = vim.LocalizableMessage()
        fault_message.message = 'LocalFault msg'
        exc.faultMessage = [fault_message]
        exc.msg = 'InvalidArgumentFault msg'
        mock_task = MagicMock()
        prop_mock_state = PropertyMock(return_value='error')
        prop_mock_error = PropertyMock(side_effect=exc)
        type(mock_task.info).state = prop_mock_state
        type(mock_task.info).error = prop_mock_error
        with self.assertRaises(excs.VMwareApiError) as excinfo:
            salt.utils.vmware.wait_for_task(mock_task,
                                            'fake_instance_name',
                                            'task_type')
        self.assertEqual(excinfo.exception.strerror,
                         'InvalidArgumentFault msg (LocalFault msg)')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetMorsWithPropertiesTestCase(TestCase):
    '''
    Tests for salt.utils.get_mors_with_properties
    '''

    si = None
    obj_type = None
    prop_list = None
    container_ref = None
    traversal_spec = None

    def setUp(self):
        self.si = MagicMock()
        self.obj_type = MagicMock()
        self.prop_list = MagicMock()
        self.container_ref = MagicMock()
        self.traversal_spec = MagicMock()

    def test_empty_content(self):
        get_content = MagicMock(return_value=[])
        with patch('salt.utils.vmware.get_content', get_content):
            ret = salt.utils.vmware.get_mors_with_properties(
                self.si, self.obj_type, self.prop_list,
                self.container_ref, self.traversal_spec)
        get_content.assert_called_once_with(
            self.si, self.obj_type,
            property_list=self.prop_list,
            container_ref=self.container_ref,
            traversal_spec=self.traversal_spec,
            local_properties=False)
        self.assertEqual(ret, [])

    def test_local_properties_set(self):
        obj_mock = MagicMock()
        # obj.propSet
        propSet_prop = PropertyMock(return_value=[])
        type(obj_mock).propSet = propSet_prop
        # obj.obj
        inner_obj_mock = MagicMock()
        obj_prop = PropertyMock(return_value=inner_obj_mock)
        type(obj_mock).obj = obj_prop

        get_content = MagicMock(return_value=[obj_mock])
        with patch('salt.utils.vmware.get_content', get_content):
            ret = salt.utils.vmware.get_mors_with_properties(
                self.si, self.obj_type, self.prop_list,
                self.container_ref, self.traversal_spec,
                local_properties=True)
        get_content.assert_called_once_with(
            self.si, self.obj_type,
            property_list=self.prop_list,
            container_ref=self.container_ref,
            traversal_spec=self.traversal_spec,
            local_properties=True)

    def test_one_element_content(self):
        obj_mock = MagicMock()
        # obj.propSet
        propSet_prop = PropertyMock(return_value=[])
        type(obj_mock).propSet = propSet_prop
        # obj.obj
        inner_obj_mock = MagicMock()
        obj_prop = PropertyMock(return_value=inner_obj_mock)
        type(obj_mock).obj = obj_prop
        get_content = MagicMock(return_value=[obj_mock])
        with patch('salt.utils.vmware.get_content', get_content):
            ret = salt.utils.vmware.get_mors_with_properties(
                self.si, self.obj_type, self.prop_list,
                self.container_ref, self.traversal_spec)
            get_content.assert_called_once_with(
                self.si, self.obj_type,
                property_list=self.prop_list,
                container_ref=self.container_ref,
                traversal_spec=self.traversal_spec,
                local_properties=False)
        self.assertEqual(propSet_prop.call_count, 1)
        self.assertEqual(obj_prop.call_count, 1)
        self.assertEqual(len(ret), 1)
        self.assertDictEqual(ret[0], {'object': inner_obj_mock})

    def test_multiple_element_content(self):
        # obj1
        obj1_mock = MagicMock()
        # obj1.propSet
        obj1_propSet_prop = PropertyMock(return_value=[])
        type(obj1_mock).propSet = obj1_propSet_prop
        # obj1.obj
        obj1_inner_obj_mock = MagicMock()
        obj1_obj_prop = PropertyMock(return_value=obj1_inner_obj_mock)
        type(obj1_mock).obj = obj1_obj_prop
        # obj2
        obj2_mock = MagicMock()
        # obj2.propSet
        obj2_propSet_prop = PropertyMock(return_value=[])
        type(obj2_mock).propSet = obj2_propSet_prop
        # obj2.obj
        obj2_inner_obj_mock = MagicMock()
        obj2_obj_prop = PropertyMock(return_value=obj2_inner_obj_mock)
        type(obj2_mock).obj = obj2_obj_prop

        get_content = MagicMock(return_value=[obj1_mock, obj2_mock])
        with patch('salt.utils.vmware.get_content', get_content):
            ret = salt.utils.vmware.get_mors_with_properties(
                self.si, self.obj_type, self.prop_list,
                self.container_ref, self.traversal_spec)
        get_content.assert_called_once_with(
            self.si, self.obj_type,
            property_list=self.prop_list,
            container_ref=self.container_ref,
            traversal_spec=self.traversal_spec,
            local_properties=False)
        self.assertEqual(obj1_propSet_prop.call_count, 1)
        self.assertEqual(obj2_propSet_prop.call_count, 1)
        self.assertEqual(obj1_obj_prop.call_count, 1)
        self.assertEqual(obj2_obj_prop.call_count, 1)
        self.assertEqual(len(ret), 2)
        self.assertDictEqual(ret[0], {'object': obj1_inner_obj_mock})
        self.assertDictEqual(ret[1], {'object': obj2_inner_obj_mock})

    def test_one_elem_one_property(self):
        obj_mock = MagicMock()

        # property mock
        prop_set_obj_mock = MagicMock()
        prop_set_obj_name_prop = PropertyMock(return_value='prop_name')
        prop_set_obj_val_prop = PropertyMock(return_value='prop_value')
        type(prop_set_obj_mock).name = prop_set_obj_name_prop
        type(prop_set_obj_mock).val = prop_set_obj_val_prop

        # obj.propSet
        propSet_prop = PropertyMock(return_value=[prop_set_obj_mock])
        type(obj_mock).propSet = propSet_prop

        # obj.obj
        inner_obj_mock = MagicMock()
        obj_prop = PropertyMock(return_value=inner_obj_mock)
        type(obj_mock).obj = obj_prop

        get_content = MagicMock(return_value=[obj_mock])
        with patch('salt.utils.vmware.get_content', get_content):
            ret = salt.utils.vmware.get_mors_with_properties(
                self.si, self.obj_type, self.prop_list,
                self.container_ref, self.traversal_spec,
                local_properties=False)
        get_content.assert_called_once_with(
            self.si, self.obj_type,
            property_list=self.prop_list,
            container_ref=self.container_ref,
            traversal_spec=self.traversal_spec,
            local_properties=False)
        self.assertEqual(propSet_prop.call_count, 1)
        self.assertEqual(prop_set_obj_name_prop.call_count, 1)
        self.assertEqual(prop_set_obj_val_prop.call_count, 1)
        self.assertEqual(obj_prop.call_count, 1)
        self.assertEqual(len(ret), 1)
        self.assertDictEqual(ret[0], {'prop_name': 'prop_value',
                                      'object': inner_obj_mock})

    def test_one_elem_multiple_properties(self):
        obj_mock = MagicMock()

        # property1  mock
        prop_set_obj1_mock = MagicMock()
        prop_set_obj1_name_prop = PropertyMock(return_value='prop_name1')
        prop_set_obj1_val_prop = PropertyMock(return_value='prop_value1')
        type(prop_set_obj1_mock).name = prop_set_obj1_name_prop
        type(prop_set_obj1_mock).val = prop_set_obj1_val_prop

        # property2  mock
        prop_set_obj2_mock = MagicMock()
        prop_set_obj2_name_prop = PropertyMock(return_value='prop_name2')
        prop_set_obj2_val_prop = PropertyMock(return_value='prop_value2')
        type(prop_set_obj2_mock).name = prop_set_obj2_name_prop
        type(prop_set_obj2_mock).val = prop_set_obj2_val_prop

        # obj.propSet
        propSet_prop = PropertyMock(return_value=[prop_set_obj1_mock,
                                                  prop_set_obj2_mock])
        type(obj_mock).propSet = propSet_prop

        # obj.obj
        inner_obj_mock = MagicMock()
        obj_prop = PropertyMock(return_value=inner_obj_mock)
        type(obj_mock).obj = obj_prop

        get_content = MagicMock(return_value=[obj_mock])
        with patch('salt.utils.vmware.get_content', get_content):
            ret = salt.utils.vmware.get_mors_with_properties(
                self.si, self.obj_type, self.prop_list,
                self.container_ref, self.traversal_spec)
        get_content.assert_called_once_with(
            self.si, self.obj_type,
            property_list=self.prop_list,
            container_ref=self.container_ref,
            traversal_spec=self.traversal_spec,
            local_properties=False)
        self.assertEqual(propSet_prop.call_count, 1)
        self.assertEqual(prop_set_obj1_name_prop.call_count, 1)
        self.assertEqual(prop_set_obj1_val_prop.call_count, 1)
        self.assertEqual(prop_set_obj2_name_prop.call_count, 1)
        self.assertEqual(prop_set_obj2_val_prop.call_count, 1)
        self.assertEqual(obj_prop.call_count, 1)
        self.assertEqual(len(ret), 1)
        self.assertDictEqual(ret[0], {'prop_name1': 'prop_value1',
                                      'prop_name2': 'prop_value2',
                                      'object': inner_obj_mock})


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetPropertiesOfManagedObjectTestCase(TestCase):
    '''
    Tests for salt.utils.get_properties_of_managed_object
    '''

    def setUp(self):
        patches = (
            ('salt.utils.vmware.get_service_instance_from_managed_object', MagicMock()),
            ('salt.utils.vmware.get_mors_with_properties', MagicMock(return_value=[MagicMock()]))
        )
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.mock_si = MagicMock()
        self.fake_mo_ref = vim.ManagedEntity('Fake')
        self.mock_props = MagicMock()
        self.mock_item_name = {'name': 'fake_name'}
        self.mock_item = MagicMock()

    def test_get_service_instance_from_managed_object_call(self):
        mock_get_instance_from_managed_object = MagicMock()
        with patch(
            'salt.utils.vmware.get_service_instance_from_managed_object',
            mock_get_instance_from_managed_object):

            salt.utils.vmware.get_properties_of_managed_object(
                self.fake_mo_ref, self.mock_props)
        mock_get_instance_from_managed_object.assert_called_once_with(
            self.fake_mo_ref)

    def test_get_mors_with_properties_calls(self):
        mock_get_mors_with_properties = MagicMock(return_value=[MagicMock()])
        with patch(
            'salt.utils.vmware.get_service_instance_from_managed_object',
            MagicMock(return_value=self.mock_si)):

            with patch('salt.utils.vmware.get_mors_with_properties',
                       mock_get_mors_with_properties):
                salt.utils.vmware.get_properties_of_managed_object(
                    self.fake_mo_ref, self.mock_props)
        mock_get_mors_with_properties.assert_has_calls(
            [call(self.mock_si, vim.ManagedEntity,
                  container_ref=self.fake_mo_ref,
                  property_list=['name'],
                  local_properties=True),
             call(self.mock_si, vim.ManagedEntity,
                  container_ref=self.fake_mo_ref,
                  property_list=self.mock_props,
                  local_properties=True)])

    def test_managed_object_no_name_property(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(side_effect=[vmodl.query.InvalidProperty(), []])):
            with self.assertRaises(excs.VMwareApiError) as excinfo:
                salt.utils.vmware.get_properties_of_managed_object(
                    self.fake_mo_ref, self.mock_props)
        self.assertEqual('Properties of managed object \'<unnamed>\' weren\'t '
                         'retrieved', excinfo.exception.strerror)

    def test_no_items_named_object(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(side_effect=[[self.mock_item_name], []])):
            with self.assertRaises(excs.VMwareApiError) as excinfo:
                salt.utils.vmware.get_properties_of_managed_object(
                    self.fake_mo_ref, self.mock_props)
        self.assertEqual('Properties of managed object \'fake_name\' weren\'t '
                         'retrieved', excinfo.exception.strerror)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetManagedObjectName(TestCase):
    '''
    Tests for salt.utils.get_managed_object_name
    '''

    def setUp(self):
        patches = (
            ('salt.utils.vmware.get_properties_of_managed_object', MagicMock(return_value={'key': 'value'})),
        )
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.mock_mo_ref = MagicMock()

    def test_get_properties_of_managed_object_call(self):
        mock_get_properties_of_managed_object = MagicMock()
        with patch('salt.utils.vmware.get_properties_of_managed_object',
                   mock_get_properties_of_managed_object):
            salt.utils.vmware.get_managed_object_name(self.mock_mo_ref)
        mock_get_properties_of_managed_object.assert_called_once_with(
            self.mock_mo_ref, ['name'])

    def test_no_name_in_property_dict(self):
        ret = salt.utils.vmware.get_managed_object_name(self.mock_mo_ref)
        self.assertIsNone(ret)

    def test_return_managed_object_name(self):
        mock_get_properties_of_managed_object = MagicMock()
        with patch('salt.utils.vmware.get_properties_of_managed_object',
                   MagicMock(return_value={'name': 'fake_name'})):
            ret = salt.utils.vmware.get_managed_object_name(self.mock_mo_ref)
        self.assertEqual(ret, 'fake_name')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetContentTestCase(TestCase):
    '''
    Tests for salt.utils.get_content
    '''

    # Method names to be patched
    traversal_spec_method_name = \
            'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec'
    property_spec_method_name = \
            'salt.utils.vmware.vmodl.query.PropertyCollector.PropertySpec'
    obj_spec_method_name = \
            'salt.utils.vmware.vmodl.query.PropertyCollector.ObjectSpec'
    filter_spec_method_name = \
            'salt.utils.vmware.vmodl.query.PropertyCollector.FilterSpec'

    # Class variables
    si_mock = None
    root_folder_mock = None
    root_folder_prop = None
    container_view_mock = None
    create_container_view_mock = None
    result_mock = None
    retrieve_contents_mock = None
    destroy_mock = None
    obj_type_mock = None
    traversal_spec_ret_mock = None
    traversal_spec_mock = None
    property_spec_ret_mock = None
    property_spec_mock = None
    obj_spec_ret_mock = None
    obj_spec_mock = None
    filter_spec_ret_mock = None
    filter_spec_mock = None

    def setUp(self):
        patches = (
            ('salt.utils.vmware.get_root_folder', MagicMock()),
            ('salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec', MagicMock(return_value=MagicMock())),
            ('salt.utils.vmware.vmodl.query.PropertyCollector.PropertySpec', MagicMock(return_value=MagicMock())),
            ('salt.utils.vmware.vmodl.query.PropertyCollector.ObjectSpec', MagicMock(return_value=MagicMock())),
            ('salt.utils.vmware.vmodl.query.PropertyCollector.FilterSpec', MagicMock(return_value=MagicMock()))
        )
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)
        # setup the service instance
        self.si_mock = MagicMock()
        # RootFolder
        self.root_folder_mock = MagicMock()
        self.get_root_folder_mock = \
                MagicMock(return_value=self.root_folder_mock)
        # CreateContainerView()
        self.container_view_mock = MagicMock()
        self.create_container_view_mock = \
                MagicMock(return_value=self.container_view_mock)
        self.si_mock.content.viewManager.CreateContainerView = \
                self.create_container_view_mock
        # RetrieveContents()
        self.result_mock = MagicMock()
        self.retrieve_contents_mock = MagicMock(return_value=self.result_mock)
        self.si_mock.content.propertyCollector.RetrieveContents = \
                self.retrieve_contents_mock
        # Destroy()
        self.destroy_mock = MagicMock()
        self.container_view_mock.Destroy = self.destroy_mock

        # override mocks
        self.obj_type_mock = MagicMock()
        self.traversal_spec_ret_mock = MagicMock()
        self.traversal_spec_mock = \
                MagicMock(return_value=self.traversal_spec_ret_mock)
        self.property_spec_ret_mock = MagicMock()
        self.property_spec_mock = \
                MagicMock(return_value=self.property_spec_ret_mock)
        self.obj_spec_ret_mock = MagicMock()
        self.obj_spec_mock = \
                MagicMock(return_value=self.obj_spec_ret_mock)
        self.filter_spec_ret_mock = MagicMock()
        self.filter_spec_mock = \
                MagicMock(return_value=self.filter_spec_ret_mock)

    def test_empty_container_ref(self):
        with patch('salt.utils.vmware.get_root_folder',
                   self.get_root_folder_mock):
            salt.utils.vmware.get_content(self.si_mock, self.obj_type_mock)
        self.get_root_folder_mock.assert_called_once_with(self.si_mock)
        self.create_container_view_mock.assert_called_once_with(
            self.root_folder_mock, [self.obj_type_mock], True)

    def test_defined_container_ref(self):
        container_ref_mock = MagicMock()
        with patch('salt.utils.vmware.get_root_folder',
                   self.get_root_folder_mock):
            with patch(self.obj_spec_method_name, self.obj_type_mock):
                salt.utils.vmware.get_content(
                    self.si_mock, self.obj_type_mock,
                    container_ref=container_ref_mock)
        self.assertEqual(self.get_root_folder_mock.call_count, 0)
        self.create_container_view_mock.assert_called_once_with(
            container_ref_mock, [self.obj_type_mock], True)

    # Also checks destroy is called
    def test_local_traversal_spec(self):
        with patch('salt.utils.vmware.get_root_folder',
                   self.get_root_folder_mock):
            with patch(self.traversal_spec_method_name,
                       self.traversal_spec_mock):
                with patch(self.obj_spec_method_name, self.obj_spec_mock):
                    ret = salt.utils.vmware.get_content(self.si_mock,
                                                        self.obj_type_mock)
        self.create_container_view_mock.assert_called_once_with(
            self.root_folder_mock, [self.obj_type_mock], True)
        self.traversal_spec_mock.assert_called_once_with(
            name='traverseEntities', path='view', skip=False,
            type=vim.view.ContainerView)
        self.obj_spec_mock.assert_called_once_with(
            obj=self.container_view_mock,
            skip=True,
            selectSet=[self.traversal_spec_ret_mock])
        # check destroy is called
        self.assertEqual(self.destroy_mock.call_count, 1)

    def test_create_container_view_raise_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.si_mock.content.viewManager.CreateContainerView = \
                MagicMock(side_effect=exc)
        with patch('salt.utils.vmware.get_root_folder',
                   self.get_root_folder_mock):
            with self.assertRaises(excs.VMwareApiError) as excinfo:
                salt.utils.vmware.get_content(self.si_mock, self.obj_type_mock)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_create_container_view_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.si_mock.content.viewManager.CreateContainerView = \
                MagicMock(side_effect=exc)
        with patch('salt.utils.vmware.get_root_folder',
                   self.get_root_folder_mock):
            with self.assertRaises(excs.VMwareApiError) as excinfo:
                salt.utils.vmware.get_content(self.si_mock, self.obj_type_mock)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_create_container_view_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.si_mock.content.viewManager.CreateContainerView = \
                MagicMock(side_effect=exc)
        with patch('salt.utils.vmware.get_root_folder',
                   self.get_root_folder_mock):
            with self.assertRaises(excs.VMwareRuntimeError) as excinfo:
                salt.utils.vmware.get_content(self.si_mock, self.obj_type_mock)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_destroy_raise_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.si_mock.content.viewManager.CreateContainerView = MagicMock(
            return_value=MagicMock(Destroy=MagicMock(side_effect=exc)))
        with patch('salt.utils.vmware.get_root_folder',
                   self.get_root_folder_mock):
            with self.assertRaises(excs.VMwareApiError) as excinfo:
                salt.utils.vmware.get_content(self.si_mock, self.obj_type_mock)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_destroy_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.si_mock.content.viewManager.CreateContainerView = MagicMock(
            return_value=MagicMock(Destroy=MagicMock(side_effect=exc)))
        with patch('salt.utils.vmware.get_root_folder',
                   self.get_root_folder_mock):
            with self.assertRaises(excs.VMwareApiError) as excinfo:
                salt.utils.vmware.get_content(self.si_mock, self.obj_type_mock)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_destroy_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.si_mock.content.viewManager.CreateContainerView = MagicMock(
            return_value=MagicMock(Destroy=MagicMock(side_effect=exc)))
        with patch('salt.utils.vmware.get_root_folder',
                   self.get_root_folder_mock):
            with self.assertRaises(excs.VMwareRuntimeError) as excinfo:
                salt.utils.vmware.get_content(self.si_mock, self.obj_type_mock)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    # Also checks destroy is not called
    def test_external_traversal_spec(self):
        traversal_spec_obj_mock = MagicMock()
        with patch('salt.utils.vmware.get_root_folder',
                   self.get_root_folder_mock):
            with patch(self.traversal_spec_method_name,
                       self.traversal_spec_mock):
                with patch(self.obj_spec_method_name, self.obj_spec_mock):
                    salt.utils.vmware.get_content(
                        self.si_mock,
                        self.obj_type_mock,
                        traversal_spec=traversal_spec_obj_mock)
        self.obj_spec_mock.assert_called_once_with(
            obj=self.root_folder_mock,
            skip=True,
            selectSet=[traversal_spec_obj_mock])
        # Check local traversal methods are not called
        self.assertEqual(self.create_container_view_mock.call_count, 0)
        self.assertEqual(self.traversal_spec_mock.call_count, 0)
        # check destroy is not called
        self.assertEqual(self.destroy_mock.call_count, 0)

    def test_property_obj_filter_specs_and_contents(self):
        with patch(self.traversal_spec_method_name, self.traversal_spec_mock):
            with patch(self.property_spec_method_name, self.property_spec_mock):
                with patch(self.obj_spec_method_name, self.obj_spec_mock):
                    with patch(self.filter_spec_method_name,
                               self.filter_spec_mock):
                        ret = salt.utils.vmware.get_content(
                            self.si_mock,
                            self.obj_type_mock)
        self.traversal_spec_mock.assert_called_once_with(
            name='traverseEntities', path='view', skip=False,
            type=vim.view.ContainerView)
        self.property_spec_mock.assert_called_once_with(
            type=self.obj_type_mock, all=True, pathSet=None)
        self.obj_spec_mock.assert_called_once_with(
            obj=self.container_view_mock, skip=True,
            selectSet=[self.traversal_spec_ret_mock])
        self.retrieve_contents_mock.assert_called_once_with(
            [self.filter_spec_ret_mock])
        self.assertEqual(ret, self.result_mock)

    def test_retrieve_contents_raise_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.si_mock.content.propertyCollector.RetrieveContents = \
                MagicMock(side_effect=exc)
        with self.assertRaises(excs.VMwareApiError) as excinfo:
            salt.utils.vmware.get_content(self.si_mock, self.obj_type_mock)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_retrieve_contents_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.si_mock.content.propertyCollector.RetrieveContents = \
                MagicMock(side_effect=exc)
        with self.assertRaises(excs.VMwareApiError) as excinfo:
            salt.utils.vmware.get_content(self.si_mock, self.obj_type_mock)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_retrieve_contents_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.si_mock.content.propertyCollector.RetrieveContents = \
                MagicMock(side_effect=exc)
        with self.assertRaises(excs.VMwareRuntimeError) as excinfo:
            salt.utils.vmware.get_content(self.si_mock, self.obj_type_mock)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_local_properties_set(self):
        container_ref_mock = MagicMock()
        with patch(self.traversal_spec_method_name, self.traversal_spec_mock):
            with patch(self.property_spec_method_name, self.property_spec_mock):
                with patch(self.obj_spec_method_name, self.obj_spec_mock):
                    salt.utils.vmware.get_content(
                        self.si_mock,
                        self.obj_type_mock,
                        container_ref=container_ref_mock,
                        local_properties=True)
        self.assertEqual(self.traversal_spec_mock.call_count, 0)
        self.obj_spec_mock.assert_called_once_with(
            obj=container_ref_mock, skip=False, selectSet=None)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetRootFolderTestCase(TestCase):
    '''
    Tests for salt.utils.get_root_folder
    '''

    def setUp(self):
        self.mock_root_folder = MagicMock()
        self.mock_content = MagicMock(rootFolder=self.mock_root_folder)
        self.mock_si = MagicMock(
            RetrieveContent=MagicMock(return_value=self.mock_content))

    def test_raise_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        type(self.mock_content).rootFolder = PropertyMock(side_effect=exc)
        with self.assertRaises(excs.VMwareApiError) as excinfo:
            salt.utils.vmware.get_root_folder(self.mock_si)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        type(self.mock_content).rootFolder = PropertyMock(side_effect=exc)
        with self.assertRaises(excs.VMwareApiError) as excinfo:
            salt.utils.vmware.get_root_folder(self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        type(self.mock_content).rootFolder = PropertyMock(side_effect=exc)
        with self.assertRaises(excs.VMwareRuntimeError) as excinfo:
            salt.utils.vmware.get_root_folder(self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_return(self):
        ret = salt.utils.vmware.get_root_folder(self.mock_si)
        self.assertEqual(ret, self.mock_root_folder)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetServiceInfoTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.get_service_info
    '''
    def setUp(self):
        self.mock_about = MagicMock()
        self.mock_si = MagicMock(content=MagicMock())
        type(self.mock_si.content).about = \
                PropertyMock(return_value=self.mock_about)

    def tearDown(self):
        for attr in ('mock_si', 'mock_about'):
            delattr(self, attr)

    def test_about_ret(self):
        ret = salt.utils.vmware.get_service_info(self.mock_si)
        self.assertEqual(ret, self.mock_about)

    def test_about_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        type(self.mock_si.content).about = \
                PropertyMock(side_effect=exc)
        with self.assertRaises(excs.VMwareApiError) as excinfo:
            salt.utils.vmware.get_service_info(self.mock_si)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_about_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        type(self.mock_si.content).about = \
                PropertyMock(side_effect=exc)
        with self.assertRaises(excs.VMwareApiError) as excinfo:
            salt.utils.vmware.get_service_info(self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_about_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        type(self.mock_si.content).about = \
                PropertyMock(side_effect=exc)
        with self.assertRaises(excs.VMwareRuntimeError) as excinfo:
            salt.utils.vmware.get_service_info(self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')
