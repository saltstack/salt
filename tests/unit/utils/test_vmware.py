# -*- coding: utf-8 -*-
'''
:codeauthor: Alexandru Bleotu <alexandru.bleotu@morganstanley.com>

Tests for cluster related functions in salt.utils.vmware
'''

# Import python libraries
from __future__ import absolute_import, print_function, unicode_literals
import base64
import logging
import ssl
import sys

# Import Salt testing libraries
from tests.support.unit import TestCase, skipIf
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    patch,
    MagicMock,
    PropertyMock,
    call,
)

# Import Salt libraries
from salt.exceptions import (
    ArgumentValueError,
    CommandExecutionError,
    VMwareApiError,
    VMwareConnectionError,
    VMwareRuntimeError,
    VMwareObjectRetrievalError,
    VMwareSystemError,
)
import salt.utils.vmware

# Import Third Party Libs
from salt.ext import six
try:
    from pyVmomi import vim, vmodl
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

try:
    import gssapi
    HAS_GSSAPI = True
except ImportError:
    HAS_GSSAPI = False

if sys.version_info[:3] > (2, 7, 8):
    SSL_VALIDATION = True
else:
    SSL_VALIDATION = False

if hasattr(ssl, '_create_unverified_context'):
    ssl_context = 'ssl._create_unverified_context'
else:
    ssl_context = 'ssl._create_stdlib_context'

# Get Logging Started
log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetClusterTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.get_cluster
    '''

    def setUp(self):
        patches = (
            ('salt.utils.vmware.get_managed_object_name', MagicMock()),
            ('salt.utils.vmware.get_service_instance_from_managed_object', MagicMock()),
            ('salt.utils.vmware.get_mors_with_properties', MagicMock(return_value=[{'name': 'fake_cluster',
                                                                                    'object': MagicMock()}]))
        )
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.mock_si = MagicMock()
        self.mock_dc = MagicMock()
        self.mock_cluster1 = MagicMock()
        self.mock_cluster2 = MagicMock()
        self.mock_entries = [{'name': 'fake_cluster1',
                              'object': self.mock_cluster1},
                             {'name': 'fake_cluster2',
                              'object': self.mock_cluster2}]
        for attr in ('mock_si', 'mock_dc', 'mock_cluster1', 'mock_cluster2', 'mock_entries'):
            self.addCleanup(delattr, self, attr)

    def test_get_managed_object_name_call(self):
        mock_get_managed_object_name = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            salt.utils.vmware.get_cluster(self.mock_dc, 'fake_cluster')
        mock_get_managed_object_name.assert_called_once_with(self.mock_dc)

    def test_get_service_instance_from_managed_object(self):
        mock_dc_name = MagicMock()
        mock_get_service_instance_from_managed_object = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   MagicMock(return_value=mock_dc_name)):
            with patch(
                'salt.utils.vmware.get_service_instance_from_managed_object',
                mock_get_service_instance_from_managed_object):

                salt.utils.vmware.get_cluster(self.mock_dc, 'fake_cluster')
        mock_get_service_instance_from_managed_object.assert_called_once_with(
            self.mock_dc, name=mock_dc_name)

    def test_traversal_spec_init(self):
        mock_dc_name = MagicMock()
        mock_traversal_spec = MagicMock()
        mock_traversal_spec_ini = MagicMock(return_value=mock_traversal_spec)
        mock_get_service_instance_from_managed_object = MagicMock()
        patch_traversal_spec_str = \
                'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec'

        with patch(patch_traversal_spec_str, mock_traversal_spec_ini):
            salt.utils.vmware.get_cluster(self.mock_dc, 'fake_cluster')
        mock_traversal_spec_ini.assert_has_calls(
            [call(path='childEntity',
                  skip=False,
                  type=vim.Folder),
            call(path='hostFolder',
                  skip=True,
                  type=vim.Datacenter,
                  selectSet=[mock_traversal_spec])])

    def test_get_mors_with_properties_call(self):
        mock_get_mors_with_properties = MagicMock(
            return_value=[{'name': 'fake_cluster', 'object': MagicMock()}])
        mock_traversal_spec = MagicMock()
        patch_traversal_spec_str = \
                'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec'
        with patch(
            'salt.utils.vmware.get_service_instance_from_managed_object',
            MagicMock(return_value=self.mock_si)):

            with patch('salt.utils.vmware.get_mors_with_properties',
                       mock_get_mors_with_properties):
                with patch(patch_traversal_spec_str,
                           MagicMock(return_value=mock_traversal_spec)):

                    salt.utils.vmware.get_cluster(self.mock_dc, 'fake_cluster')
        mock_get_mors_with_properties.assert_called_once_with(
            self.mock_si, vim.ClusterComputeResource,
            container_ref=self.mock_dc,
            property_list=['name'],
            traversal_spec=mock_traversal_spec)

    def test_get_mors_with_properties_returns_empty_array(self):
        with patch('salt.utils.vmware.get_managed_object_name',
                   MagicMock(return_value='fake_dc')):
            with patch('salt.utils.vmware.get_mors_with_properties',
                       MagicMock(return_value=[])):
                with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                    salt.utils.vmware.get_cluster(self.mock_dc, 'fake_cluster')
        self.assertEqual(excinfo.exception.strerror,
                         'Cluster \'fake_cluster\' was not found in '
                         'datacenter \'fake_dc\'')

    def test_cluster_not_found(self):
        with patch('salt.utils.vmware.get_managed_object_name',
                   MagicMock(return_value='fake_dc')):
            with patch('salt.utils.vmware.get_mors_with_properties',
                       MagicMock(return_value=self.mock_entries)):
                with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                    salt.utils.vmware.get_cluster(self.mock_dc, 'fake_cluster')
        self.assertEqual(excinfo.exception.strerror,
                         'Cluster \'fake_cluster\' was not found in '
                         'datacenter \'fake_dc\'')

    def test_cluster_found(self):
        with patch('salt.utils.vmware.get_managed_object_name',
                   MagicMock(return_value='fake_dc')):
            with patch('salt.utils.vmware.get_mors_with_properties',
                       MagicMock(return_value=self.mock_entries)):
                res = salt.utils.vmware.get_cluster(self.mock_dc, 'fake_cluster2')
        self.assertEqual(res, self.mock_cluster2)


@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class CreateClusterTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.create_cluster
    '''

    def setUp(self):
        patches = (
            ('salt.utils.vmware.get_managed_object_name', MagicMock()),
        )
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.mock_create_cluster_ex = MagicMock()
        self.mock_dc = MagicMock(
            hostFolder=MagicMock(CreateClusterEx=self.mock_create_cluster_ex))
        self.mock_cluster_spec = MagicMock()
        for attr in ('mock_create_cluster_ex', 'mock_dc', 'mock_cluster_spec'):
            self.addCleanup(delattr, self, attr)

    def test_get_managed_object_name(self):
        mock_get_managed_object_name = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            salt.utils.vmware.create_cluster(self.mock_dc, 'fake_cluster',
                                             self.mock_cluster_spec)
        mock_get_managed_object_name.assert_called_once_with(self.mock_dc)

    def test_create_cluster_call(self):
        salt.utils.vmware.create_cluster(self.mock_dc, 'fake_cluster',
                                         self.mock_cluster_spec)
        self.mock_create_cluster_ex.assert_called_once_with(
           'fake_cluster', self.mock_cluster_spec)

    def test_create_cluster_raise_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_dc.hostFolder.CreateClusterEx = MagicMock(
            side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.create_cluster(self.mock_dc, 'fake_cluster',
                                             self.mock_cluster_spec)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_create_cluster_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_dc.hostFolder.CreateClusterEx = MagicMock(
            side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.create_cluster(self.mock_dc, 'fake_cluster',
                                             self.mock_cluster_spec)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_create_cluster_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_dc.hostFolder.CreateClusterEx = MagicMock(
            side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.vmware.create_cluster(self.mock_dc, 'fake_cluster',
                                             self.mock_cluster_spec)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class UpdateClusterTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.update_cluster
    '''

    def setUp(self):
        patches = (
            ('salt.utils.vmware.get_managed_object_name', MagicMock()),
            ('salt.utils.vmware.wait_for_task', MagicMock()),
        )
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.mock_task = MagicMock()
        self.mock_reconfigure_compute_resource_task = \
                MagicMock(return_value=self.mock_task)
        self.mock_cluster = MagicMock(ReconfigureComputeResource_Task=
            self.mock_reconfigure_compute_resource_task)
        self.mock_cluster_spec = MagicMock()
        for attr in ('mock_task', 'mock_reconfigure_compute_resource_task', 'mock_cluster', 'mock_cluster_spec'):
            self.addCleanup(delattr, self, attr)

    def test_get_managed_object_name(self):
        mock_get_managed_object_name = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            salt.utils.vmware.update_cluster(self.mock_cluster, self.mock_cluster_spec)
        mock_get_managed_object_name.assert_called_once_with(self.mock_cluster)

    def test_reconfigure_compute_resource_task_call(self):
        salt.utils.vmware.update_cluster(self.mock_cluster, self.mock_cluster_spec)
        self.mock_reconfigure_compute_resource_task.assert_called_once_with(
            self.mock_cluster_spec, modify=True)

    def test_reconfigure_compute_resource_raise_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_cluster.ReconfigureComputeResource_Task = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.update_cluster(self.mock_cluster, self.mock_cluster_spec)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_reconfigure_compute_resource_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_cluster.ReconfigureComputeResource_Task = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.update_cluster(self.mock_cluster, self.mock_cluster_spec)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_reconfigure_compute_resource_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_cluster.ReconfigureComputeResource_Task = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.vmware.update_cluster(self.mock_cluster, self.mock_cluster_spec)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_wait_for_task_call(self):
        mock_wait_for_task = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   MagicMock(return_value='fake_cluster')):
            with patch('salt.utils.vmware.wait_for_task', mock_wait_for_task):
                salt.utils.vmware.update_cluster(self.mock_cluster, self.mock_cluster_spec)
        mock_wait_for_task.assert_called_once_with(
            self.mock_task, 'fake_cluster', 'ClusterUpdateTask')


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
        with self.assertRaises(VMwareApiError) as excinfo:
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
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.wait_for_task(mock_task,
                                            'fake_instance_name',
                                            'task_type')
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_first_task_info_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        mock_task = MagicMock()
        type(mock_task).info = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
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
        with self.assertRaises(VMwareApiError) as excinfo:
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
        with self.assertRaises(VMwareApiError) as excinfo:
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
        with self.assertRaises(VMwareRuntimeError) as excinfo:
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
        with self.assertRaises(VMwareApiError) as excinfo:
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
        with self.assertRaises(VMwareApiError) as excinfo:
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
        with self.assertRaises(VMwareSystemError) as excinfo:
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
        with self.assertRaises(VMwareApiError) as excinfo:
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
        with self.assertRaises(VMwareApiError) as excinfo:
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
            with self.assertRaises(VMwareApiError) as excinfo:
                salt.utils.vmware.get_properties_of_managed_object(
                    self.fake_mo_ref, self.mock_props)
        self.assertEqual('Properties of managed object \'<unnamed>\' weren\'t '
                         'retrieved', excinfo.exception.strerror)

    def test_no_items_named_object(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(side_effect=[[self.mock_item_name], []])):
            with self.assertRaises(VMwareApiError) as excinfo:
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
            with self.assertRaises(VMwareApiError) as excinfo:
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
            with self.assertRaises(VMwareApiError) as excinfo:
                salt.utils.vmware.get_content(self.si_mock, self.obj_type_mock)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_create_container_view_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.si_mock.content.viewManager.CreateContainerView = \
                MagicMock(side_effect=exc)
        with patch('salt.utils.vmware.get_root_folder',
                   self.get_root_folder_mock):
            with self.assertRaises(VMwareRuntimeError) as excinfo:
                salt.utils.vmware.get_content(self.si_mock, self.obj_type_mock)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_destroy_raise_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.si_mock.content.viewManager.CreateContainerView = MagicMock(
            return_value=MagicMock(Destroy=MagicMock(side_effect=exc)))
        with patch('salt.utils.vmware.get_root_folder',
                   self.get_root_folder_mock):
            with self.assertRaises(VMwareApiError) as excinfo:
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
            with self.assertRaises(VMwareApiError) as excinfo:
                salt.utils.vmware.get_content(self.si_mock, self.obj_type_mock)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_destroy_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.si_mock.content.viewManager.CreateContainerView = MagicMock(
            return_value=MagicMock(Destroy=MagicMock(side_effect=exc)))
        with patch('salt.utils.vmware.get_root_folder',
                   self.get_root_folder_mock):
            with self.assertRaises(VMwareRuntimeError) as excinfo:
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
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.get_content(self.si_mock, self.obj_type_mock)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_retrieve_contents_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.si_mock.content.propertyCollector.RetrieveContents = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.get_content(self.si_mock, self.obj_type_mock)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_retrieve_contents_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.si_mock.content.propertyCollector.RetrieveContents = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
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
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.get_root_folder(self.mock_si)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        type(self.mock_content).rootFolder = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.get_root_folder(self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        type(self.mock_content).rootFolder = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
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
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.get_service_info(self.mock_si)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_about_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        type(self.mock_si.content).about = \
                PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.get_service_info(self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_about_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        type(self.mock_si.content).about = \
                PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.vmware.get_service_info(self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@skipIf(not HAS_GSSAPI, 'The \'gssapi\' library is missing')
class GssapiTokenTest(TestCase):
    '''
    Test cases for salt.utils.vmware.get_gssapi_token
    '''
    def setUp(self):
        patches = (
            ('gssapi.Name', MagicMock(return_value='service')),
            ('gssapi.InitContext', MagicMock())
        )
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_no_gssapi(self):
        with patch('salt.utils.vmware.HAS_GSSAPI', False):
            with self.assertRaises(ImportError) as excinfo:
                salt.utils.vmware.get_gssapi_token('principal', 'host', 'domain')
                self.assertIn('The gssapi library is not imported.',
                              excinfo.exception.message)

    @skipIf(not HAS_GSSAPI, 'The \'gssapi\' library is missing')
    def test_service_name(self):
        mock_name = MagicMock()
        with patch.object(salt.utils.vmware.gssapi, 'Name', mock_name):

            with self.assertRaises(CommandExecutionError):
                salt.utils.vmware.get_gssapi_token('principal', 'host',
                                                   'domain')
            mock_name.assert_called_once_with('principal/host@domain',
                                              gssapi.C_NT_USER_NAME)

    @skipIf(not HAS_GSSAPI, 'The \'gssapi\' library is missing')
    def test_out_token_defined(self):
        mock_context = MagicMock(return_value=MagicMock())
        mock_context.return_value.established = False
        mock_context.return_value.step = MagicMock(return_value='out_token')
        with patch.object(salt.utils.vmware.gssapi, 'InitContext',
                          mock_context):
            ret = salt.utils.vmware.get_gssapi_token('principal', 'host',
                                                     'domain')
            self.assertEqual(mock_context.return_value.step.called, 1)
            self.assertEqual(ret, base64.b64encode(b'out_token'))

    @skipIf(not HAS_GSSAPI, 'The \'gssapi\' library is missing')
    def test_out_token_undefined(self):
        mock_context = MagicMock(return_value=MagicMock())
        mock_context.return_value.established = False
        mock_context.return_value.step = MagicMock(return_value=None)
        with patch.object(salt.utils.vmware.gssapi, 'InitContext',
                          mock_context):
            with self.assertRaises(CommandExecutionError) as excinfo:
                salt.utils.vmware.get_gssapi_token('principal', 'host',
                                                   'domain')
            self.assertEqual(mock_context.return_value.step.called, 1)
            self.assertIn('Can\'t receive token',
                          excinfo.exception.strerror)

    @skipIf(not HAS_GSSAPI, 'The \'gssapi\' library is missing')
    def test_context_extablished(self):
        mock_context = MagicMock(return_value=MagicMock())
        mock_context.return_value.established = True
        mock_context.return_value.step = MagicMock(return_value='out_token')
        with patch.object(salt.utils.vmware.gssapi, 'InitContext',
                          mock_context):
            mock_context.established = True
            mock_context.step = MagicMock(return_value=None)
            with self.assertRaises(CommandExecutionError) as excinfo:
                salt.utils.vmware.get_gssapi_token('principal', 'host',
                                                   'domain')
            self.assertEqual(mock_context.step.called, 0)
            self.assertIn('Context established, but didn\'t receive token',
                          excinfo.exception.strerror)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class PrivateGetServiceInstanceTestCase(TestCase):
    '''
    Tests for salt.utils.vmware._get_service_instance
    '''

    def setUp(self):
        patches = (
            ('salt.utils.vmware.SmartConnect', MagicMock()),
            ('salt.utils.vmware.Disconnect', MagicMock()),
            ('salt.utils.vmware.get_gssapi_token', MagicMock(return_value='fake_token'))
        )
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_invalid_mechianism(self):
        with self.assertRaises(CommandExecutionError) as excinfo:
            salt.utils.vmware._get_service_instance(
                host='fake_host.fqdn',
                username='fake_username',
                password='fake_password',
                protocol='fake_protocol',
                port=1,
                mechanism='invalid_mechanism',
                principal='fake principal',
                domain='fake_domain')
        self.assertIn('Unsupported mechanism', excinfo.exception.strerror)

    def test_userpass_mechanism_empty_username(self):
        with self.assertRaises(CommandExecutionError) as excinfo:
            salt.utils.vmware._get_service_instance(
                host='fake_host.fqdn',
                username=None,
                password='fake_password',
                protocol='fake_protocol',
                port=1,
                mechanism='userpass',
                principal='fake principal',
                domain='fake_domain')
        self.assertIn('mandatory parameter \'username\'',
                      excinfo.exception.strerror)

    def test_userpass_mechanism_empty_password(self):
        with self.assertRaises(CommandExecutionError) as excinfo:
            salt.utils.vmware._get_service_instance(
                host='fake_host.fqdn',
                username='fake_username',
                password=None,
                protocol='fake_protocol',
                port=1,
                mechanism='userpass',
                principal='fake principal',
                domain='fake_domain')
        self.assertIn('mandatory parameter \'password\'',
                      excinfo.exception.strerror)

    def test_userpass_mechanism_no_domain(self):
        mock_sc = MagicMock()
        with patch('salt.utils.vmware.SmartConnect', mock_sc):
            salt.utils.vmware._get_service_instance(
                host='fake_host.fqdn',
                username='fake_username',
                password='fake_password',
                protocol='fake_protocol',
                port=1,
                mechanism='userpass',
                principal='fake principal',
                domain=None)
            mock_sc.assert_called_once_with(
                host='fake_host.fqdn',
                user='fake_username',
                pwd='fake_password',
                protocol='fake_protocol',
                port=1,
                b64token=None,
                mechanism='userpass')

    def test_userpass_mech_domain_unused(self):
        mock_sc = MagicMock()
        with patch('salt.utils.vmware.SmartConnect', mock_sc):
            salt.utils.vmware._get_service_instance(
                host='fake_host.fqdn',
                username='fake_username@domain',
                password='fake_password',
                protocol='fake_protocol',
                port=1,
                mechanism='userpass',
                principal='fake principal',
                domain='fake_domain')
            mock_sc.assert_called_once_with(
                host='fake_host.fqdn',
                user='fake_username@domain',
                pwd='fake_password',
                protocol='fake_protocol',
                port=1,
                b64token=None,
                mechanism='userpass')
            mock_sc.reset_mock()
            salt.utils.vmware._get_service_instance(
                host='fake_host.fqdn',
                username='domain\\fake_username',
                password='fake_password',
                protocol='fake_protocol',
                port=1,
                mechanism='userpass',
                principal='fake principal',
                domain='fake_domain')
            mock_sc.assert_called_once_with(
                host='fake_host.fqdn',
                user='domain\\fake_username',
                pwd='fake_password',
                protocol='fake_protocol',
                port=1,
                b64token=None,
                mechanism='userpass')

    def test_sspi_empty_principal(self):
        with self.assertRaises(CommandExecutionError) as excinfo:
            salt.utils.vmware._get_service_instance(
                host='fake_host.fqdn',
                username='fake_username',
                password='fake_password',
                protocol='fake_protocol',
                port=1,
                mechanism='sspi',
                principal=None,
                domain='fake_domain')
        self.assertIn('mandatory parameters are missing',
                      excinfo.exception.strerror)

    def test_sspi_empty_domain(self):
        with self.assertRaises(CommandExecutionError) as excinfo:
            salt.utils.vmware._get_service_instance(
                host='fake_host.fqdn',
                username='fake_username',
                password='fake_password',
                protocol='fake_protocol',
                port=1,
                mechanism='sspi',
                principal='fake_principal',
                domain=None)
        self.assertIn('mandatory parameters are missing',
                      excinfo.exception.strerror)

    def test_sspi_get_token_error(self):
        mock_token = MagicMock(side_effect=Exception('Exception'))

        with patch('salt.utils.vmware.get_gssapi_token', mock_token):
            with self.assertRaises(VMwareConnectionError) as excinfo:
                salt.utils.vmware._get_service_instance(
                    host='fake_host.fqdn',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='sspi',
                    principal='fake_principal',
                    domain='fake_domain')
            mock_token.assert_called_once_with('fake_principal',
                                               'fake_host.fqdn',
                                               'fake_domain')
            self.assertEqual('Exception', excinfo.exception.strerror)

    def test_sspi_get_token_success_(self):
        mock_token = MagicMock(return_value='fake_token')
        mock_sc = MagicMock()

        with patch('salt.utils.vmware.get_gssapi_token', mock_token):
            with patch('salt.utils.vmware.SmartConnect', mock_sc):
                salt.utils.vmware._get_service_instance(
                    host='fake_host.fqdn',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='sspi',
                    principal='fake_principal',
                    domain='fake_domain')
            mock_token.assert_called_once_with('fake_principal',
                                               'fake_host.fqdn',
                                               'fake_domain')
            mock_sc.assert_called_once_with(
                host='fake_host.fqdn',
                user='fake_username',
                pwd='fake_password',
                protocol='fake_protocol',
                port=1,
                b64token='fake_token',
                mechanism='sspi')

    def test_first_attempt_successful_connection(self):
        mock_sc = MagicMock()
        with patch('salt.utils.vmware.SmartConnect', mock_sc):
            salt.utils.vmware._get_service_instance(
                host='fake_host.fqdn',
                username='fake_username',
                password='fake_password',
                protocol='fake_protocol',
                port=1,
                mechanism='sspi',
                principal='fake_principal',
                domain='fake_domain')
            mock_sc.assert_called_once_with(
                host='fake_host.fqdn',
                user='fake_username',
                pwd='fake_password',
                protocol='fake_protocol',
                port=1,
                b64token='fake_token',
                mechanism='sspi')

    @skipIf(not SSL_VALIDATION, 'SSL validation is not enabled')
    def test_second_attempt_successful_connection(self):
        with patch('ssl.SSLContext', MagicMock()), \
                patch(ssl_context, MagicMock()):
            exc = vim.fault.HostConnectFault()
            exc.msg = '[SSL: CERTIFICATE_VERIFY_FAILED]'
            mock_sc = MagicMock(side_effect=[exc, None])
            mock_ssl = MagicMock()

            with patch('salt.utils.vmware.SmartConnect', mock_sc):
                with patch(ssl_context,
                           mock_ssl):

                    salt.utils.vmware._get_service_instance(
                        host='fake_host.fqdn',
                        username='fake_username',
                        password='fake_password',
                        protocol='fake_protocol',
                        port=1,
                        mechanism='sspi',
                        principal='fake_principal',
                        domain='fake_domain')

                    mock_ssl.assert_called_once_with()
                    calls = [call(host='fake_host.fqdn',
                                  user='fake_username',
                                  pwd='fake_password',
                                  protocol='fake_protocol',
                                  port=1,
                                  b64token='fake_token',
                                  mechanism='sspi'),
                             call(host='fake_host.fqdn',
                                  user='fake_username',
                                  pwd='fake_password',
                                  protocol='fake_protocol',
                                  port=1,
                                  sslContext=mock_ssl.return_value,
                                  b64token='fake_token',
                                  mechanism='sspi')]
                    mock_sc.assert_has_calls(calls)

    @skipIf(not SSL_VALIDATION, 'SSL validation is not enabled')
    def test_third_attempt_successful_connection(self):
        with patch('ssl.SSLContext', MagicMock()), \
                patch(ssl_context, MagicMock()):
            exc = vim.fault.HostConnectFault()
            exc.msg = '[SSL: CERTIFICATE_VERIFY_FAILED]'
            exc2 = Exception('certificate verify failed')
            mock_sc = MagicMock(side_effect=[exc, exc2, None])
            mock_ssl_unverif = MagicMock()
            mock_ssl_context = MagicMock()

            with patch('salt.utils.vmware.SmartConnect', mock_sc):
                with patch(ssl_context, mock_ssl_unverif):
                    with patch('ssl.SSLContext', mock_ssl_context):

                        salt.utils.vmware._get_service_instance(
                            host='fake_host.fqdn',
                            username='fake_username',
                            password='fake_password',
                            protocol='fake_protocol',
                            port=1,
                            mechanism='sspi',
                            principal='fake_principal',
                            domain='fake_domain')

                        mock_ssl_context.assert_called_once_with(ssl.PROTOCOL_TLSv1)
                        mock_ssl_unverif.assert_called_once_with()
                        calls = [call(host='fake_host.fqdn',
                                      user='fake_username',
                                      pwd='fake_password',
                                      protocol='fake_protocol',
                                      port=1,
                                      b64token='fake_token',
                                      mechanism='sspi'),
                                 call(host='fake_host.fqdn',
                                      user='fake_username',
                                      pwd='fake_password',
                                      protocol='fake_protocol',
                                      port=1,
                                      sslContext=mock_ssl_unverif.return_value,
                                      b64token='fake_token',
                                      mechanism='sspi'),
                                 call(host='fake_host.fqdn',
                                      user='fake_username',
                                      pwd='fake_password',
                                      protocol='fake_protocol',
                                      port=1,
                                      sslContext=mock_ssl_context.return_value,
                                      b64token='fake_token',
                                      mechanism='sspi'),
                                ]
                        mock_sc.assert_has_calls(calls)

    def test_first_attempt_unsuccessful_connection_default_error(self):
        exc = Exception('Exception')
        mock_sc = MagicMock(side_effect=exc)

        with patch('salt.utils.vmware.SmartConnect', mock_sc):
            with self.assertRaises(VMwareConnectionError) as excinfo:
                salt.utils.vmware._get_service_instance(
                    host='fake_host.fqdn',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='sspi',
                    principal='fake_principal',
                    domain='fake_domain')

                self.assertEqual(mock_sc.call_count, 1)
                self.assertIn('Could not connect to host \'fake_host.fqdn\'',
                              excinfo.Exception.message)

    def test_first_attempt_unsuccessful_connection_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault'
        mock_sc = MagicMock(side_effect=exc)

        with patch('salt.utils.vmware.SmartConnect', mock_sc):
            with self.assertRaises(VMwareConnectionError) as excinfo:
                salt.utils.vmware._get_service_instance(
                    host='fake_host.fqdn',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='sspi',
                    principal='fake_principal',
                    domain='fake_domain')

                self.assertEqual(mock_sc.call_count, 1)
                self.assertEqual('VimFault', excinfo.Exception.message)

    @skipIf(not SSL_VALIDATION, 'SSL validation is not enabled')
    def test_second_attempt_unsuccsessful_connection_default_error(self):
        with patch('ssl.SSLContext', MagicMock()), \
                patch(ssl_context, MagicMock()):
            exc = vim.fault.HostConnectFault()
            exc.msg = '[SSL: CERTIFICATE_VERIFY_FAILED]'
            exc2 = Exception('Exception')
            mock_sc = MagicMock(side_effect=[exc, exc2])

            with patch('salt.utils.vmware.SmartConnect', mock_sc):
                with self.assertRaises(VMwareConnectionError) as excinfo:
                    salt.utils.vmware._get_service_instance(
                        host='fake_host.fqdn',
                        username='fake_username',
                        password='fake_password',
                        protocol='fake_protocol',
                        port=1,
                        mechanism='sspi',
                        principal='fake_principal',
                        domain='fake_domain')

                    self.assertEqual(mock_sc.call_count, 2)
                    self.assertIn('Could not connect to host \'fake_host.fqdn\'',
                                  excinfo.Exception.message)

    @skipIf(not SSL_VALIDATION, 'SSL validation is not enabled')
    def test_second_attempt_unsuccsessful_connection_vim_fault(self):
        with patch('ssl.SSLContext', MagicMock()), \
                patch(ssl_context, MagicMock()):
            exc = vim.fault.HostConnectFault()
            exc.msg = '[SSL: CERTIFICATE_VERIFY_FAILED]'
            exc2 = vim.fault.VimFault()
            exc2.msg = 'VimFault'
            mock_sc = MagicMock(side_effect=[exc, exc2])

            with patch('salt.utils.vmware.SmartConnect', mock_sc):
                with self.assertRaises(VMwareConnectionError) as excinfo:
                    salt.utils.vmware._get_service_instance(
                        host='fake_host.fqdn',
                        username='fake_username',
                        password='fake_password',
                        protocol='fake_protocol',
                        port=1,
                        mechanism='sspi',
                        principal='fake_principal',
                        domain='fake_domain')

                    self.assertEqual(mock_sc.call_count, 2)
                    self.assertIn('VimFault', excinfo.Exception.message)

    @skipIf(not SSL_VALIDATION, 'SSL validation is not enabled')
    def test_third_attempt_unsuccessful_connection_detault_error(self):
        with patch('ssl.SSLContext', MagicMock()), \
                patch(ssl_context, MagicMock()):
            exc = vim.fault.HostConnectFault()
            exc.msg = '[SSL: CERTIFICATE_VERIFY_FAILED]'
            exc2 = Exception('certificate verify failed')
            exc3 = Exception('Exception')
            mock_sc = MagicMock(side_effect=[exc, exc2, exc3])

            with patch('salt.utils.vmware.SmartConnect', mock_sc):
                with self.assertRaises(VMwareConnectionError) as excinfo:
                    salt.utils.vmware._get_service_instance(
                        host='fake_host.fqdn',
                        username='fake_username',
                        password='fake_password',
                        protocol='fake_protocol',
                        port=1,
                        mechanism='sspi',
                        principal='fake_principal',
                        domain='fake_domain')

                    self.assertEqual(mock_sc.call_count, 3)
                    self.assertIn('Exception', excinfo.Exception.message)

    @skipIf(not SSL_VALIDATION, 'SSL validation is not enabled')
    def test_third_attempt_unsuccessful_connection_vim_fault(self):
        with patch('ssl.SSLContext', MagicMock()), \
                patch(ssl_context, MagicMock()):
            exc = vim.fault.HostConnectFault()
            exc.msg = '[SSL: CERTIFICATE_VERIFY_FAILED]'
            exc2 = Exception('certificate verify failed')
            exc3 = vim.fault.VimFault()
            exc3.msg = 'VimFault'
            mock_sc = MagicMock(side_effect=[exc, exc2, exc3])

            with patch('salt.utils.vmware.SmartConnect', mock_sc):
                with self.assertRaises(VMwareConnectionError) as excinfo:
                    salt.utils.vmware._get_service_instance(
                        host='fake_host.fqdn',
                        username='fake_username',
                        password='fake_password',
                        protocol='fake_protocol',
                        port=1,
                        mechanism='sspi',
                        principal='fake_principal',
                        domain='fake_domain')

                    self.assertEqual(mock_sc.call_count, 3)
                    self.assertIn('VimFault', excinfo.Exception.message)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetServiceInstanceTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.get_service_instance
    '''
    def setUp(self):
        patches = (
            ('salt.utils.vmware.GetSi', MagicMock(return_value=None)),
            ('salt.utils.vmware._get_service_instance', MagicMock(return_value=MagicMock()))
        )
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_default_params(self):
        mock_get_si = MagicMock()
        with patch('salt.utils.vmware._get_service_instance', mock_get_si):
            salt.utils.vmware.get_service_instance(
                host='fake_host'
            )
            mock_get_si.assert_called_once_with('fake_host', None, None,
                                                'https', 443, 'userpass', None,
                                                None)

    def test_no_cached_service_instance_same_host_on_proxy(self):
        with patch('salt.utils.platform.is_proxy', MagicMock(return_value=True)):
            # Service instance is uncached when using class default mock objs
            mock_get_si = MagicMock()
            with patch('salt.utils.vmware._get_service_instance', mock_get_si):
                salt.utils.vmware.get_service_instance(
                    host='fake_host',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='fake_mechanism',
                    principal='fake_principal',
                    domain='fake_domain'
                )
                mock_get_si.assert_called_once_with('fake_host',
                                                    'fake_username',
                                                    'fake_password',
                                                    'fake_protocol',
                                                    1,
                                                    'fake_mechanism',
                                                    'fake_principal',
                                                    'fake_domain')

    def test_cached_service_instance_different_host(self):
        mock_si = MagicMock()
        mock_si_stub = MagicMock()
        mock_disconnect = MagicMock()
        mock_get_si = MagicMock(return_value=mock_si)
        mock_getstub = MagicMock()
        with patch('salt.utils.vmware.GetSi', mock_get_si):
            with patch('salt.utils.vmware.GetStub', mock_getstub):
                with patch('salt.utils.vmware.Disconnect', mock_disconnect):
                    salt.utils.vmware.get_service_instance(
                        host='fake_host',
                        username='fake_username',
                        password='fake_password',
                        protocol='fake_protocol',
                        port=1,
                        mechanism='fake_mechanism',
                        principal='fake_principal',
                        domain='fake_domain'
                    )
            self.assertEqual(mock_get_si.call_count, 1)
            self.assertEqual(mock_getstub.call_count, 1)
            self.assertEqual(mock_disconnect.call_count, 1)

    def test_uncached_service_instance(self):
        # Service instance is uncached when using class default mock objs
        mock_get_si = MagicMock()
        with patch('salt.utils.vmware._get_service_instance', mock_get_si):
            salt.utils.vmware.get_service_instance(
                host='fake_host',
                username='fake_username',
                password='fake_password',
                protocol='fake_protocol',
                port=1,
                mechanism='fake_mechanism',
                principal='fake_principal',
                domain='fake_domain'
            )
            mock_get_si.assert_called_once_with('fake_host',
                                                'fake_username',
                                                'fake_password',
                                                'fake_protocol',
                                                1,
                                                'fake_mechanism',
                                                'fake_principal',
                                                'fake_domain')

    def test_unauthenticated_service_instance(self):
        mock_si_current_time = MagicMock(side_effect=vim.fault.NotAuthenticated)
        mock_si = MagicMock()
        mock_get_si = MagicMock(return_value=mock_si)
        mock_si.CurrentTime = mock_si_current_time
        mock_disconnect = MagicMock()
        with patch('salt.utils.vmware._get_service_instance', mock_get_si):
            with patch('salt.utils.vmware.Disconnect', mock_disconnect):
                salt.utils.vmware.get_service_instance(
                    host='fake_host',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='fake_mechanism',
                    principal='fake_principal',
                    domain='fake_domain'
                )
                self.assertEqual(mock_si_current_time.call_count, 1)
                self.assertEqual(mock_disconnect.call_count, 1)
                self.assertEqual(mock_get_si.call_count, 2)

    def test_current_time_raise_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        with patch('salt.utils.vmware._get_service_instance',
                   MagicMock(return_value=MagicMock(
                       CurrentTime=MagicMock(side_effect=exc)))):
            with self.assertRaises(VMwareApiError) as excinfo:
                salt.utils.vmware.get_service_instance(
                    host='fake_host',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='fake_mechanism',
                    principal='fake_principal',
                    domain='fake_domain')
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_current_time_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        with patch('salt.utils.vmware._get_service_instance',
                   MagicMock(return_value=MagicMock(
                       CurrentTime=MagicMock(side_effect=exc)))):
            with self.assertRaises(VMwareApiError) as excinfo:
                salt.utils.vmware.get_service_instance(
                    host='fake_host',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='fake_mechanism',
                    principal='fake_principal',
                    domain='fake_domain')
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_current_time_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        with patch('salt.utils.vmware._get_service_instance',
                   MagicMock(return_value=MagicMock(
                       CurrentTime=MagicMock(side_effect=exc)))):
            with self.assertRaises(VMwareRuntimeError) as excinfo:
                salt.utils.vmware.get_service_instance(
                    host='fake_host',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='fake_mechanism',
                    principal='fake_principal',
                    domain='fake_domain')
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class DisconnectTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.disconnect
    '''

    def setUp(self):
        self.mock_si = MagicMock()
        self.addCleanup(delattr, self, 'mock_si')

    def test_disconnect(self):
        mock_disconnect = MagicMock()
        with patch('salt.utils.vmware.Disconnect', mock_disconnect):
            salt.utils.vmware.disconnect(
                service_instance=self.mock_si)
            mock_disconnect.assert_called_once_with(self.mock_si)

    def test_disconnect_raise_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        with patch('salt.utils.vmware.Disconnect', MagicMock(side_effect=exc)):
            with self.assertRaises(VMwareApiError) as excinfo:
                salt.utils.vmware.disconnect(
                    service_instance=self.mock_si)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_disconnect_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        with patch('salt.utils.vmware.Disconnect', MagicMock(side_effect=exc)):
            with self.assertRaises(VMwareApiError) as excinfo:
                salt.utils.vmware.disconnect(
                    service_instance=self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_disconnect_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        with patch('salt.utils.vmware.Disconnect', MagicMock(side_effect=exc)):
            with self.assertRaises(VMwareRuntimeError) as excinfo:
                salt.utils.vmware.disconnect(
                    service_instance=self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class IsConnectionToAVCenterTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.is_connection_to_a_vcenter
    '''

    def test_api_type_raise_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        mock_si = MagicMock()
        type(mock_si.content.about).apiType = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.is_connection_to_a_vcenter(mock_si)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_api_type_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        mock_si = MagicMock()
        type(mock_si.content.about).apiType = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.is_connection_to_a_vcenter(mock_si)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_api_type_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        mock_si = MagicMock()
        type(mock_si.content.about).apiType = PropertyMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.vmware.is_connection_to_a_vcenter(mock_si)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_connected_to_a_vcenter(self):
        mock_si = MagicMock()
        mock_si.content.about.apiType = 'VirtualCenter'

        ret = salt.utils.vmware.is_connection_to_a_vcenter(mock_si)
        self.assertTrue(ret)

    def test_connected_to_a_host(self):
        mock_si = MagicMock()
        mock_si.content.about.apiType = 'HostAgent'

        ret = salt.utils.vmware.is_connection_to_a_vcenter(mock_si)
        self.assertFalse(ret)

    def test_connected_to_invalid_entity(self):
        mock_si = MagicMock()
        mock_si.content.about.apiType = 'UnsupportedType'

        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.is_connection_to_a_vcenter(mock_si)
        self.assertIn('Unexpected api type \'UnsupportedType\'',
                      excinfo.exception.strerror)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetNewServiceInstanceStub(TestCase, LoaderModuleMockMixin):
    '''
    Tests for salt.utils.vmware.get_new_service_instance_stub
    '''
    def setup_loader_modules(self):
        return {salt.utils.vmware: {
            '__virtual__': MagicMock(return_value='vmware'),
            'sys': MagicMock(),
            'ssl': MagicMock()}}

    def setUp(self):
        self.mock_stub = MagicMock(
            host='fake_host:1000',
            cookie='ignore"fake_cookie')
        self.mock_si = MagicMock(
            _stub=self.mock_stub)
        self.mock_ret = MagicMock()
        self.mock_new_stub = MagicMock()
        self.context_dict = {}
        patches = (('salt.utils.vmware.VmomiSupport.GetRequestContext',
                    MagicMock(
                        return_value=self.context_dict)),
                   ('salt.utils.vmware.SoapStubAdapter',
                    MagicMock(return_value=self.mock_new_stub)))
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)

        type(salt.utils.vmware.sys).version_info = \
                PropertyMock(return_value=(2, 7, 9))
        self.mock_context = MagicMock()
        self.mock_create_default_context = \
                MagicMock(return_value=self.mock_context)
        salt.utils.vmware.ssl.create_default_context = \
                   self.mock_create_default_context

    def tearDown(self):
        for attr in ('mock_stub', 'mock_si', 'mock_ret', 'mock_new_stub',
                     'context_dict', 'mock_context',
                     'mock_create_default_context'):
            delattr(self, attr)

    def test_ssl_default_context_loaded(self):
        salt.utils.vmware.get_new_service_instance_stub(
            self.mock_si, 'fake_path')
        self.mock_create_default_context.assert_called_once_with()
        self.assertFalse(self.mock_context.check_hostname)
        self.assertEqual(self.mock_context.verify_mode,
                         salt.utils.vmware.ssl.CERT_NONE)

    def test_ssl_default_context_not_loaded(self):
        type(salt.utils.vmware.sys).version_info = \
                PropertyMock(return_value=(2, 7, 8))
        salt.utils.vmware.get_new_service_instance_stub(
            self.mock_si, 'fake_path')
        self.assertEqual(self.mock_create_default_context.call_count, 0)

    def test_session_cookie_in_context(self):
        salt.utils.vmware.get_new_service_instance_stub(
            self.mock_si, 'fake_path')
        self.assertEqual(self.context_dict['vcSessionCookie'], 'fake_cookie')

    def test_get_new_stub(self):
        mock_get_new_stub = MagicMock()
        with patch('salt.utils.vmware.SoapStubAdapter', mock_get_new_stub):
            salt.utils.vmware.get_new_service_instance_stub(
                self.mock_si, 'fake_path', 'fake_ns', 'fake_version')
        mock_get_new_stub.assert_called_once_with(
            host='fake_host', ns='fake_ns', path='fake_path',
            version='fake_version', poolSize=0, sslContext=self.mock_context)

    def test_get_new_stub_2_7_8_python(self):
        type(salt.utils.vmware.sys).version_info = \
                PropertyMock(return_value=(2, 7, 8))
        mock_get_new_stub = MagicMock()
        with patch('salt.utils.vmware.SoapStubAdapter', mock_get_new_stub):
            salt.utils.vmware.get_new_service_instance_stub(
                self.mock_si, 'fake_path', 'fake_ns', 'fake_version')
        mock_get_new_stub.assert_called_once_with(
            host='fake_host', ns='fake_ns', path='fake_path',
            version='fake_version', poolSize=0, sslContext=None)

    def test_new_stub_returned(self):
        ret = salt.utils.vmware.get_new_service_instance_stub(
            self.mock_si, 'fake_path')
        self.assertEqual(self.mock_new_stub.cookie, 'ignore"fake_cookie')
        self.assertEqual(ret, self.mock_new_stub)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetServiceInstanceFromManagedObjectTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.get_managed_instance_from_managed_object
    '''

    def setUp(self):
        patches = (
            ('salt.utils.vmware.vim.ServiceInstance', MagicMock()),
        )
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.mock_si = MagicMock()
        self.mock_stub = PropertyMock()
        self.mock_mo_ref = MagicMock(_stub=self.mock_stub)
        for attr in ('mock_si', 'mock_stub', 'mock_mo_ref'):
            self.addCleanup(delattr, self, attr)

    def test_default_name_parameter(self):
        mock_trace = MagicMock()
        type(salt.utils.vmware.log).trace = mock_trace
        salt.utils.vmware.get_service_instance_from_managed_object(
            self.mock_mo_ref)
        mock_trace.assert_called_once_with(
            '[%s] Retrieving service instance from managed object',
            '<unnamed>')

    def test_name_parameter_passed_in(self):
        mock_trace = MagicMock()
        type(salt.utils.vmware.log).trace = mock_trace
        salt.utils.vmware.get_service_instance_from_managed_object(
            self.mock_mo_ref, 'fake_mo_name')
        mock_trace.assert_called_once_with(
            '[%s] Retrieving service instance from managed object',
            'fake_mo_name')

    def test_service_instance_instantiation(self):
        mock_service_instance_ini = MagicMock()
        with patch('salt.utils.vmware.vim.ServiceInstance',
                   mock_service_instance_ini):
            salt.utils.vmware.get_service_instance_from_managed_object(
                self.mock_mo_ref)
        mock_service_instance_ini.assert_called_once_with('ServiceInstance')

    def test_si_return_and_stub_assignment(self):
        with patch('salt.utils.vmware.vim.ServiceInstance',
                   MagicMock(return_value=self.mock_si)):
            ret = salt.utils.vmware.get_service_instance_from_managed_object(
                self.mock_mo_ref)
        self.assertEqual(ret, self.mock_si)
        self.assertEqual(ret._stub, self.mock_stub)


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
            salt.utils.vmware.get_datacenters(self.mock_si, datacenter_names=['fake_dc1'])
        mock_get_mors_with_properties.assert_called_once_with(
            self.mock_si, vim.Datacenter, property_list=['name'])

    def test_get_mors_with_properties_returns_empty_array(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=[])):
            res = salt.utils.vmware.get_datacenters(self.mock_si,
                                                    datacenter_names=['fake_dc1'])
        self.assertEqual(res, [])

    def test_no_parameters(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=self.mock_entries)):
            res = salt.utils.vmware.get_datacenters(self.mock_si)
        self.assertEqual(res, [])

    def test_datastore_not_found(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=self.mock_entries)):
            res = salt.utils.vmware.get_datacenters(self.mock_si,
                                                    datacenter_names=['fake_dc'])
        self.assertEqual(res, [])

    def test_datastore_found(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=self.mock_entries)):
            res = salt.utils.vmware.get_datacenters(
                self.mock_si, datacenter_names=['fake_dc2'])
        self.assertEqual(res, [self.mock_dc2])

    def test_get_all_datastores(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=self.mock_entries)):
            res = salt.utils.vmware.get_datacenters(
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
            salt.utils.vmware.get_datacenter(self.mock_si, 'fake_dc1')
        mock_get_datacenters.assert_called_once_with(
            self.mock_si, datacenter_names=['fake_dc1'])

    def test_no_datacenters_returned(self):
        with patch('salt.utils.vmware.get_datacenters',
                   MagicMock(return_value=[])):
            with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                salt.utils.vmware.get_datacenter(self.mock_si, 'fake_dc1')
        self.assertEqual('Datacenter \'fake_dc1\' was not found',
                         excinfo.exception.strerror)

    def test_get_datacenter_return(self):
        with patch('salt.utils.vmware.get_datacenters',
                   MagicMock(return_value=[self.mock_dc])):
            res = salt.utils.vmware.get_datacenter(self.mock_si, 'fake_dc1')
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
            salt.utils.vmware.create_datacenter(self.mock_si, 'fake_dc')
        mock_get_root_folder.assert_called_once_with(self.mock_si)

    def test_create_datacenter_call(self):
        with patch('salt.utils.vmware.get_root_folder',
                   MagicMock(return_value=self.mock_root_folder)):
            salt.utils.vmware.create_datacenter(self.mock_si, 'fake_dc')
        self.mock_create_datacenter.assert_called_once_with('fake_dc')

    def test_create_datacenter_raise_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_root_folder = MagicMock(
            CreateDatacenter=MagicMock(side_effect=exc))
        with patch('salt.utils.vmware.get_root_folder',
                   MagicMock(return_value=self.mock_root_folder)):
            with self.assertRaises(VMwareApiError) as excinfo:
                salt.utils.vmware.create_datacenter(self.mock_si, 'fake_dc')
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
                salt.utils.vmware.create_datacenter(self.mock_si, 'fake_dc')
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_create_datacenter_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_root_folder = MagicMock(
            CreateDatacenter=MagicMock(side_effect=exc))
        with patch('salt.utils.vmware.get_root_folder',
                   MagicMock(return_value=self.mock_root_folder)):
            with self.assertRaises(VMwareRuntimeError) as excinfo:
                salt.utils.vmware.create_datacenter(self.mock_si, 'fake_dc')
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_datastore_successfully_created(self):
        with patch('salt.utils.vmware.get_root_folder',
                   MagicMock(return_value=self.mock_root_folder)):
            res = salt.utils.vmware.create_datacenter(self.mock_si, 'fake_dc')
        self.assertEqual(res, self.mock_dc)


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
            salt.utils.vmware.get_dvss(self.mock_dc_ref)
        mock_get_managed_object_name.assert_called_once_with(self.mock_dc_ref)

    def test_traversal_spec(self):
        mock_traversal_spec = MagicMock(return_value='traversal_spec')
        with patch(
            'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
            mock_traversal_spec):

            salt.utils.vmware.get_dvss(self.mock_dc_ref)
        mock_traversal_spec.assert_has_calls(
            [call(path='childEntity', skip=False, type=vim.Folder),
             call(path='networkFolder', skip=True, type=vim.Datacenter,
                  selectSet=['traversal_spec'])])

    def test_get_mors_with_properties(self):
        salt.utils.vmware.get_dvss(self.mock_dc_ref)
        self.mock_get_mors.assert_called_once_with(
            self.mock_si, vim.DistributedVirtualSwitch,
            container_ref=self.mock_dc_ref, property_list=['name'],
            traversal_spec=self.mock_traversal_spec)

    def test_get_no_dvss(self):
        ret = salt.utils.vmware.get_dvss(self.mock_dc_ref)
        self.assertEqual(ret, [])

    def test_get_all_dvss(self):
        ret = salt.utils.vmware.get_dvss(self.mock_dc_ref, get_all_dvss=True)
        self.assertEqual(ret, [i['object'] for i in self.mock_items])

    def test_filtered_all_dvss(self):
        ret = salt.utils.vmware.get_dvss(self.mock_dc_ref,
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
            salt.utils.vmware.get_network_folder(self.mock_dc_ref)
        mock_get_managed_object_name.assert_called_once_with(self.mock_dc_ref)

    def test_traversal_spec(self):
        mock_traversal_spec = MagicMock(return_value='traversal_spec')
        with patch(
            'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
            mock_traversal_spec):

            salt.utils.vmware.get_network_folder(self.mock_dc_ref)
        mock_traversal_spec.assert_called_once_with(
            path='networkFolder', skip=False, type=vim.Datacenter)

    def test_get_mors_with_properties(self):
        salt.utils.vmware.get_network_folder(self.mock_dc_ref)
        self.mock_get_mors.assert_called_once_with(
            self.mock_si, vim.Folder, container_ref=self.mock_dc_ref,
            property_list=['name'], traversal_spec=self.mock_traversal_spec)

    def test_get_no_network_folder(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=[])):
            with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                salt.utils.vmware.get_network_folder(self.mock_dc_ref)
        self.assertEqual(excinfo.exception.strerror,
                         'Network folder in datacenter \'fake_dc\' wasn\'t '
                         'retrieved')

    def test_get_network_folder(self):
        ret = salt.utils.vmware.get_network_folder(self.mock_dc_ref)
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
            salt.utils.vmware.create_dvs(self.mock_dc_ref, 'fake_dvs')
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
                salt.utils.vmware.create_dvs(self.mock_dc_ref, 'fake_dvs')
        mock_dvs_create_spec.assert_called_once_with()
        mock_vmware_dvs_config_spec.assert_called_once_with()
        self.assertEqual(mock_spec.configSpec, mock_config_spec)
        self.assertEqual(mock_config_spec.name, 'fake_dvs')
        self.mock_netw_folder.CreateDVS_Task.assert_called_once_with(mock_spec)

    def test_get_network_folder(self):
        mock_get_network_folder = MagicMock()
        with patch('salt.utils.vmware.get_network_folder',
                   mock_get_network_folder):
            salt.utils.vmware.create_dvs(self.mock_dc_ref, 'fake_dvs')
        mock_get_network_folder.assert_called_once_with(self.mock_dc_ref)

    def test_create_dvs_task_passed_in_spec(self):
        salt.utils.vmware.create_dvs(self.mock_dc_ref, 'fake_dvs',
                                     dvs_create_spec=self.mock_dvs_create_spec)
        self.mock_netw_folder.CreateDVS_Task.assert_called_once_with(
            self.mock_dvs_create_spec)

    def test_create_dvs_task_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_netw_folder.CreateDVS_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.create_dvs(self.mock_dc_ref, 'fake_dvs',
                                         dvs_create_spec=self.mock_dvs_create_spec)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_create_dvs_task_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_netw_folder.CreateDVS_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.create_dvs(self.mock_dc_ref, 'fake_dvs',
                                         dvs_create_spec=self.mock_dvs_create_spec)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_create_dvs_task_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_netw_folder.CreateDVS_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.vmware.create_dvs(self.mock_dc_ref, 'fake_dvs',
                                         dvs_create_spec=self.mock_dvs_create_spec)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_wait_for_tasks(self):
        salt.utils.vmware.create_dvs(self.mock_dc_ref, 'fake_dvs',
                                     dvs_create_spec=self.mock_dvs_create_spec)
        self.mock_wait_for_task.assert_called_once_with(
            self.mock_task, 'fake_dvs',
            '<class \'unit.utils.test_vmware.FakeTaskClass\'>')


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
            salt.utils.vmware.update_dvs(self.mock_dvs_ref, self.mock_dvs_spec)
        mock_get_managed_object_name.assert_called_once_with(self.mock_dvs_ref)

    def test_reconfigure_dvs_task(self):
        salt.utils.vmware.update_dvs(self.mock_dvs_ref, self.mock_dvs_spec)
        self.mock_dvs_ref.ReconfigureDvs_Task.assert_called_once_with(
            self.mock_dvs_spec)

    def test_reconfigure_dvs_task_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_dvs_ref.ReconfigureDvs_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.update_dvs(self.mock_dvs_ref, self.mock_dvs_spec)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_reconfigure_dvs_task_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_dvs_ref.ReconfigureDvs_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.update_dvs(self.mock_dvs_ref, self.mock_dvs_spec)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_reconfigure_dvs_task_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_dvs_ref.ReconfigureDvs_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.vmware.update_dvs(self.mock_dvs_ref, self.mock_dvs_spec)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_wait_for_tasks(self):
        salt.utils.vmware.update_dvs(self.mock_dvs_ref, self.mock_dvs_spec)
        self.mock_wait_for_task.assert_called_once_with(
            self.mock_task, 'fake_dvs',
            '<class \'unit.utils.test_vmware.FakeTaskClass\'>')


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
            salt.utils.vmware.set_dvs_network_resource_management_enabled(
                self.mock_dvs_ref, self.mock_enabled)
        mock_get_managed_object_name.assert_called_once_with(self.mock_dvs_ref)

    def test_enable_network_resource_management(self):
        salt.utils.vmware.set_dvs_network_resource_management_enabled(
            self.mock_dvs_ref, self.mock_enabled)
        self.mock_dvs_ref.EnableNetworkResourceManagement.assert_called_once_with(
            enable=self.mock_enabled)

    def test_enable_network_resource_management_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_dvs_ref.EnableNetworkResourceManagement = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.set_dvs_network_resource_management_enabled(
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
            salt.utils.vmware.set_dvs_network_resource_management_enabled(
                self.mock_dvs_ref, self.mock_enabled)

    def test_enable_network_resource_management_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_dvs_ref.EnableNetworkResourceManagement = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.vmware.set_dvs_network_resource_management_enabled(
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
            salt.utils.vmware.get_dvportgroups(MagicMock())
        self.assertEqual(excinfo.exception.strerror,
                         'Parent has to be either a datacenter, or a '
                         'distributed virtual switch')

    def test_get_managed_object_name_call(self):
        mock_get_managed_object_name = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            salt.utils.vmware.get_dvportgroups(self.mock_dc_ref)
        mock_get_managed_object_name.assert_called_once_with(self.mock_dc_ref)

    def test_traversal_spec_datacenter_parent(self):
        mock_traversal_spec = MagicMock(return_value='traversal_spec')
        with patch(
            'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
            mock_traversal_spec):

            salt.utils.vmware.get_dvportgroups(self.mock_dc_ref)
        mock_traversal_spec.assert_has_calls(
            [call(path='childEntity', skip=False, type=vim.Folder),
             call(path='networkFolder', skip=True, type=vim.Datacenter,
                  selectSet=['traversal_spec'])])

    def test_traversal_spec_dvs_parent(self):
        mock_traversal_spec = MagicMock(return_value='traversal_spec')
        with patch(
            'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
            mock_traversal_spec):

            salt.utils.vmware.get_dvportgroups(self.mock_dvs_ref)
        mock_traversal_spec.assert_called_once_with(
            path='portgroup', skip=False, type=vim.DistributedVirtualSwitch)

    def test_get_mors_with_properties(self):
        salt.utils.vmware.get_dvportgroups(self.mock_dvs_ref)
        self.mock_get_mors.assert_called_once_with(
            self.mock_si, vim.DistributedVirtualPortgroup,
            container_ref=self.mock_dvs_ref, property_list=['name'],
            traversal_spec=self.mock_traversal_spec)

    def test_get_no_pgs(self):
        ret = salt.utils.vmware.get_dvportgroups(self.mock_dvs_ref)
        self.assertEqual(ret, [])

    def test_get_all_pgs(self):
        ret = salt.utils.vmware.get_dvportgroups(self.mock_dvs_ref,
                                      get_all_portgroups=True)
        self.assertEqual(ret, [i['object'] for i in self.mock_items])

    def test_filtered_pgs(self):
        ret = salt.utils.vmware.get_dvss(self.mock_dc_ref,
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
            salt.utils.vmware.get_uplink_dvportgroup(self.mock_dvs_ref)
        mock_get_managed_object_name.assert_called_once_with(self.mock_dvs_ref)

    def test_traversal_spec(self):
        mock_traversal_spec = MagicMock(return_value='traversal_spec')
        with patch(
            'salt.utils.vmware.vmodl.query.PropertyCollector.TraversalSpec',
            mock_traversal_spec):

            salt.utils.vmware.get_uplink_dvportgroup(self.mock_dvs_ref)
        mock_traversal_spec.assert_called_once_with(
            path='portgroup', skip=False, type=vim.DistributedVirtualSwitch)

    def test_get_mors_with_properties(self):
        salt.utils.vmware.get_uplink_dvportgroup(self.mock_dvs_ref)
        self.mock_get_mors.assert_called_once_with(
            self.mock_si, vim.DistributedVirtualPortgroup,
            container_ref=self.mock_dvs_ref, property_list=['tag'],
            traversal_spec=self.mock_traversal_spec)

    def test_get_no_uplink_pg(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=[])):
            with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                salt.utils.vmware.get_uplink_dvportgroup(self.mock_dvs_ref)
        self.assertEqual(excinfo.exception.strerror,
                         'Uplink portgroup of DVS \'fake_dvs\' wasn\'t found')

    def test_get_uplink_pg(self):
        ret = salt.utils.vmware.get_uplink_dvportgroup(self.mock_dvs_ref)
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
            salt.utils.vmware.create_dvportgroup(self.mock_dvs_ref, self.mock_pg_spec)
        mock_get_managed_object_name.assert_called_once_with(self.mock_dvs_ref)

    def test_create_dvporgroup_task(self):
        salt.utils.vmware.create_dvportgroup(self.mock_dvs_ref, self.mock_pg_spec)
        self.mock_dvs_ref.CreateDVPortgroup_Task.assert_called_once_with(
            self.mock_pg_spec)

    def test_create_dvporgroup_task_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_dvs_ref.CreateDVPortgroup_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.create_dvportgroup(self.mock_dvs_ref, self.mock_pg_spec)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_create_dvporgroup_task_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_dvs_ref.CreateDVPortgroup_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.create_dvportgroup(self.mock_dvs_ref, self.mock_pg_spec)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_create_dvporgroup_task_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_dvs_ref.CreateDVPortgroup_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.vmware.create_dvportgroup(self.mock_dvs_ref, self.mock_pg_spec)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_wait_for_tasks(self):
        salt.utils.vmware.create_dvportgroup(self.mock_dvs_ref, self.mock_pg_spec)
        self.mock_wait_for_task.assert_called_once_with(
            self.mock_task, 'fake_dvs',
            '<class \'unit.utils.test_vmware.FakeTaskClass\'>')


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
            salt.utils.vmware.update_dvportgroup(self.mock_pg_ref, self.mock_pg_spec)
        mock_get_managed_object_name.assert_called_once_with(self.mock_pg_ref)

    def test_reconfigure_dvporgroup_task(self):
        salt.utils.vmware.update_dvportgroup(self.mock_pg_ref, self.mock_pg_spec)
        self.mock_pg_ref.ReconfigureDVPortgroup_Task.assert_called_once_with(
            self.mock_pg_spec)

    def test_reconfigure_dvporgroup_task_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_pg_ref.ReconfigureDVPortgroup_Task = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.update_dvportgroup(self.mock_pg_ref, self.mock_pg_spec)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_reconfigure_dvporgroup_task_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_pg_ref.ReconfigureDVPortgroup_Task = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.update_dvportgroup(self.mock_pg_ref, self.mock_pg_spec)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_reconfigure_dvporgroup_task_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_pg_ref.ReconfigureDVPortgroup_Task = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.vmware.update_dvportgroup(self.mock_pg_ref, self.mock_pg_spec)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_wait_for_tasks(self):
        salt.utils.vmware.update_dvportgroup(self.mock_pg_ref, self.mock_pg_spec)
        self.mock_wait_for_task.assert_called_once_with(
            self.mock_task, 'fake_pg',
            '<class \'unit.utils.test_vmware.FakeTaskClass\'>')


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
            salt.utils.vmware.remove_dvportgroup(self.mock_pg_ref)
        mock_get_managed_object_name.assert_called_once_with(self.mock_pg_ref)

    def test_destroy_task(self):
        salt.utils.vmware.remove_dvportgroup(self.mock_pg_ref)
        self.mock_pg_ref.Destroy_Task.assert_called_once_with()

    def test_destroy_task_raises_no_permission(self):
        exc = vim.fault.NoPermission()
        exc.privilegeId = 'Fake privilege'
        self.mock_pg_ref.Destroy_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.remove_dvportgroup(self.mock_pg_ref)
        self.assertEqual(excinfo.exception.strerror,
                         'Not enough permissions. Required privilege: '
                         'Fake privilege')

    def test_destroy_treconfigure_dvporgroup_task_raises_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_pg_ref.Destroy_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            salt.utils.vmware.remove_dvportgroup(self.mock_pg_ref)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_destroy_treconfigure_dvporgroup_task_raises_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_pg_ref.Destroy_Task = MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            salt.utils.vmware.remove_dvportgroup(self.mock_pg_ref)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_wait_for_tasks(self):
        salt.utils.vmware.remove_dvportgroup(self.mock_pg_ref)
        self.mock_wait_for_task.assert_called_once_with(
            self.mock_task, 'fake_pg',
            '<class \'unit.utils.test_vmware.FakeTaskClass\'>')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class GetHostsTestCase(TestCase):
    '''
    Tests for salt.utils.vmware.get_hosts
    '''

    def setUp(self):
        patches = (
            ('salt.utils.vmware.get_mors_with_properties', MagicMock(return_value=[])),
            ('salt.utils.vmware.get_datacenter', MagicMock(return_value=None)),
            ('salt.utils.vmware.get_cluster', MagicMock(return_value=None))
        )
        for mod, mock in patches:
            patcher = patch(mod, mock)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.mock_root_folder = MagicMock()
        self.mock_si = MagicMock()
        self.mock_host1, self.mock_host2, self.mock_host3 = MagicMock(), \
                MagicMock(), MagicMock()
        self.mock_prop_host1 = {'name': 'fake_hostname1',
                                'object': self.mock_host1}
        self.mock_prop_host2 = {'name': 'fake_hostname2',
                                'object': self.mock_host2}
        self.mock_prop_host3 = {'name': 'fake_hostname3',
                                'object': self.mock_host3}
        self.mock_prop_hosts = [self.mock_prop_host1, self.mock_prop_host2,
                                self.mock_prop_host3]

    def test_cluster_no_datacenter(self):
        with self.assertRaises(ArgumentValueError) as excinfo:
            salt.utils.vmware.get_hosts(self.mock_si,
                                        cluster_name='fake_cluster')
        self.assertEqual(excinfo.exception.strerror,
                         'Must specify the datacenter when specifying the '
                         'cluster')

    def test_get_si_no_datacenter_no_cluster(self):
        mock_get_mors = MagicMock()
        mock_get_root_folder = MagicMock(return_value=self.mock_root_folder)
        with patch('salt.utils.vmware.get_root_folder', mock_get_root_folder):
            with patch('salt.utils.vmware.get_mors_with_properties',
                       mock_get_mors):
                salt.utils.vmware.get_hosts(self.mock_si)
        mock_get_root_folder.assert_called_once_with(self.mock_si)
        mock_get_mors.assert_called_once_with(
            self.mock_si, vim.HostSystem, container_ref=self.mock_root_folder,
            property_list=['name'])

    def test_get_si_datacenter_name_no_cluster_name(self):
        mock_dc = MagicMock()
        mock_get_dc = MagicMock(return_value=mock_dc)
        mock_get_mors = MagicMock()
        with patch('salt.utils.vmware.get_datacenter', mock_get_dc):
            with patch('salt.utils.vmware.get_mors_with_properties',
                       mock_get_mors):
                salt.utils.vmware.get_hosts(self.mock_si,
                                            datacenter_name='fake_datacenter')
        mock_get_dc.assert_called_once_with(self.mock_si, 'fake_datacenter')
        mock_get_mors.assert_called_once_with(self.mock_si,
                                              vim.HostSystem,
                                              container_ref=mock_dc,
                                              property_list=['name'])

    def test_get_si_datacenter_name_and_cluster_name(self):
        mock_dc = MagicMock()
        mock_get_dc = MagicMock(return_value=mock_dc)
        mock_get_cl = MagicMock()
        mock_get_mors = MagicMock()
        with patch('salt.utils.vmware.get_datacenter', mock_get_dc):
            with patch('salt.utils.vmware.get_cluster', mock_get_cl):
                with patch('salt.utils.vmware.get_mors_with_properties',
                           mock_get_mors):
                    salt.utils.vmware.get_hosts(
                        self.mock_si, datacenter_name='fake_datacenter',
                        cluster_name='fake_cluster')
        mock_get_dc.assert_called_once_with(self.mock_si, 'fake_datacenter')
        mock_get_mors.assert_called_once_with(self.mock_si,
                                              vim.HostSystem,
                                              container_ref=mock_dc,
                                              property_list=['name', 'parent'])

    def test_host_get_all_hosts(self):
        with patch('salt.utils.vmware.get_root_folder',
                   MagicMock(return_value=self.mock_root_folder)):
            with patch('salt.utils.vmware.get_mors_with_properties',
                       MagicMock(return_value=self.mock_prop_hosts)):
                res = salt.utils.vmware.get_hosts(self.mock_si, get_all_hosts=True)
        self.assertEqual(res, [self.mock_host1, self.mock_host2,
                               self.mock_host3])

    def test_filter_hostname(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=self.mock_prop_hosts)):
            res = salt.utils.vmware.get_hosts(self.mock_si,
                                              host_names=['fake_hostname1',
                                                          'fake_hostname2'])
        self.assertEqual(res, [self.mock_host1, self.mock_host2])

    def test_get_all_host_flag_not_set_and_no_host_names(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=self.mock_prop_hosts)):
            res = salt.utils.vmware.get_hosts(self.mock_si)
        self.assertEqual(res, [])

    def test_filter_cluster(self):
        self.mock_prop_host1['parent'] = vim.ClusterComputeResource('cluster')
        self.mock_prop_host2['parent'] = vim.ClusterComputeResource('cluster')
        self.mock_prop_host3['parent'] = vim.Datacenter('dc')
        mock_get_cl_name = MagicMock(
            side_effect=['fake_bad_cluster', 'fake_good_cluster'])
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=self.mock_prop_hosts)):
            with patch('salt.utils.vmware.get_managed_object_name',
                       mock_get_cl_name):
                res = salt.utils.vmware.get_hosts(
                    self.mock_si, datacenter_name='fake_datacenter',
                    cluster_name='fake_good_cluster', get_all_hosts=True)
        self.assertEqual(mock_get_cl_name.call_count, 2)
        self.assertEqual(res, [self.mock_host2])

    def test_no_hosts(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=[])):
            res = salt.utils.vmware.get_hosts(self.mock_si, get_all_hosts=True)
        self.assertEqual(res, [])

    def test_one_host_returned(self):
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=[self.mock_prop_host1])):
            res = salt.utils.vmware.get_hosts(self.mock_si, get_all_hosts=True)
        self.assertEqual(res, [self.mock_host1])


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
        with patch('salt._logging.impl.SaltLoggingClass.trace', mock_trace):
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
        with patch('salt._logging.impl.SaltLoggingClass.trace', mock_trace):
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
            self.mock_ent_id, self.mock_lic_key, 'fake_license_name')

    def test_update_assigned_licenses_call_with_entity(self):
        salt.utils.vmware.assign_license(self.mock_si,
                                         self.mock_lic_key,
                                         'fake_license_name',
                                         self.mock_entity_ref,
                                         'fake_entity_name')
        self.mock_update_assigned_license.assert_called_once_with(
            self.mock_moid, self.mock_lic_key, 'fake_license_name')

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


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ConvertToKbTestCase(TestCase):
    '''
    Tests for converting units
    '''

    def setUp(self):
        pass

    def test_gb_conversion_call(self):
        self.assertEqual(salt.utils.vmware.convert_to_kb('Gb', 10), {'size': int(10485760), 'unit': 'KB'})

    def test_mb_conversion_call(self):
        self.assertEqual(salt.utils.vmware.convert_to_kb('Mb', 10), {'size': int(10240), 'unit': 'KB'})

    def test_kb_conversion_call(self):
        self.assertEqual(salt.utils.vmware.convert_to_kb('Kb', 10), {'size': int(10), 'unit': 'KB'})

    def test_conversion_bad_input_argument_fault(self):
        self.assertRaises(ArgumentValueError, salt.utils.vmware.convert_to_kb, 'test', 10)


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
        salt.utils.vmware.create_vm(self.vm_name, self.mock_config_spec,
                                    self.mock_folder_object,
                                    self.mock_resourcepool_object)
        self.assert_called_once(self.mock_vm_create_task)

    def test_create_vm_host_task_call(self):
        salt.utils.vmware.create_vm(self.vm_name, self.mock_config_spec,
                                    self.mock_folder_object,
                                    self.mock_resourcepool_object,
                                    host_object=self.mock_host_object)
        self.assert_called_once(self.mock_vm_create_task)

    def test_create_vm_raise_no_permission(self):
        exception = vim.fault.NoPermission()
        exception.msg = 'vim.fault.NoPermission msg'
        self.mock_folder_object.CreateVM_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareApiError) as exc:
            salt.utils.vmware.create_vm(self.vm_name, self.mock_config_spec,
                                        self.mock_folder_object,
                                        self.mock_resourcepool_object)
        self.assertEqual(exc.exception.strerror,
                         'Not enough permissions. Required privilege: ')

    def test_create_vm_raise_vim_fault(self):
        exception = vim.fault.VimFault()
        exception.msg = 'vim.fault.VimFault msg'
        self.mock_folder_object.CreateVM_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareApiError) as exc:
            salt.utils.vmware.create_vm(self.vm_name, self.mock_config_spec,
                                        self.mock_folder_object,
                                        self.mock_resourcepool_object)
        self.assertEqual(exc.exception.strerror, 'vim.fault.VimFault msg')

    def test_create_vm_raise_runtime_fault(self):
        exception = vmodl.RuntimeFault()
        exception.msg = 'vmodl.RuntimeFault msg'
        self.mock_folder_object.CreateVM_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareRuntimeError) as exc:
            salt.utils.vmware.create_vm(self.vm_name, self.mock_config_spec,
                                        self.mock_folder_object,
                                        self.mock_resourcepool_object)
        self.assertEqual(exc.exception.strerror, 'vmodl.RuntimeFault msg')

    def test_create_vm_wait_for_task(self):
        mock_wait_for_task = MagicMock()
        with patch('salt.utils.vmware.wait_for_task', mock_wait_for_task):
            salt.utils.vmware.create_vm(self.vm_name, self.mock_config_spec,
                                        self.mock_folder_object,
                                        self.mock_resourcepool_object)
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
        salt.utils.vmware.register_vm(self.datacenter, self.vm_name,
                                      self.mock_vmx_path,
                                      self.mock_resourcepool_object)
        self.assert_called_once(self.mock_vm_register_task)

    def test_register_vm_host_task_call(self):
        salt.utils.vmware.register_vm(self.datacenter, self.vm_name,
                                      self.mock_vmx_path,
                                      self.mock_resourcepool_object,
                                      host_object=self.mock_host_object)
        self.assert_called_once(self.mock_vm_register_task)

    def test_register_vm_raise_no_permission(self):
        exception = vim.fault.NoPermission()
        self.vm_folder_object.RegisterVM_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareApiError) as exc:
            salt.utils.vmware.register_vm(self.datacenter, self.vm_name,
                                          self.mock_vmx_path,
                                          self.mock_resourcepool_object)
        self.assertEqual(exc.exception.strerror,
                         'Not enough permissions. Required privilege: ')

    def test_register_vm_raise_vim_fault(self):
        exception = vim.fault.VimFault()
        exception.msg = 'vim.fault.VimFault msg'
        self.vm_folder_object.RegisterVM_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareApiError) as exc:
            salt.utils.vmware.register_vm(self.datacenter, self.vm_name,
                                          self.mock_vmx_path,
                                          self.mock_resourcepool_object)
        self.assertEqual(exc.exception.strerror, 'vim.fault.VimFault msg')

    def test_register_vm_raise_runtime_fault(self):
        exception = vmodl.RuntimeFault()
        exception.msg = 'vmodl.RuntimeFault msg'
        self.vm_folder_object.RegisterVM_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareRuntimeError) as exc:
            salt.utils.vmware.register_vm(self.datacenter, self.vm_name,
                                          self.mock_vmx_path,
                                          self.mock_resourcepool_object)
        self.assertEqual(exc.exception.strerror, 'vmodl.RuntimeFault msg')

    def test_register_vm_wait_for_task(self):
        mock_wait_for_task = MagicMock()
        with patch('salt.utils.vmware.wait_for_task', mock_wait_for_task):
            salt.utils.vmware.register_vm(self.datacenter, self.vm_name,
                                          self.mock_vmx_path,
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
        salt.utils.vmware.update_vm(self.mock_vm_ref, self.mock_config_spec)
        self.assert_called_once(self.mock_vm_update_task)

    def test_update_vm_raise_vim_fault(self):
        exception = vim.fault.VimFault()
        exception.msg = 'vim.fault.VimFault'
        self.mock_vm_ref.ReconfigVM_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareApiError) as exc:
            salt.utils.vmware.update_vm(self.mock_vm_ref, self.mock_config_spec)
        self.assertEqual(exc.exception.strerror, 'vim.fault.VimFault')

    def test_update_vm_raise_runtime_fault(self):
        exception = vmodl.RuntimeFault()
        exception.msg = 'vmodl.RuntimeFault'
        self.mock_vm_ref.ReconfigVM_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareRuntimeError) as exc:
            salt.utils.vmware.update_vm(self.mock_vm_ref, self.mock_config_spec)
        self.assertEqual(exc.exception.strerror, 'vmodl.RuntimeFault')

    def test_update_vm_wait_for_task(self):
        mock_wait_for_task = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   MagicMock(return_value='my_vm')):
            with patch('salt.utils.vmware.wait_for_task', mock_wait_for_task):
                salt.utils.vmware.update_vm(self.mock_vm_ref, self.mock_config_spec)
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
        salt.utils.vmware.delete_vm(self.mock_vm_ref)
        self.assert_called_once(self.mock_vm_destroy_task)

    def test_destroy_vm_raise_vim_fault(self):
        exception = vim.fault.VimFault()
        exception.msg = 'vim.fault.VimFault'
        self.mock_vm_ref.Destroy_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareApiError) as exc:
            salt.utils.vmware.delete_vm(self.mock_vm_ref)
        self.assertEqual(exc.exception.strerror, 'vim.fault.VimFault')

    def test_destroy_vm_raise_runtime_fault(self):
        exception = vmodl.RuntimeFault()
        exception.msg = 'vmodl.RuntimeFault'
        self.mock_vm_ref.Destroy_Task = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareRuntimeError) as exc:
            salt.utils.vmware.delete_vm(self.mock_vm_ref)
        self.assertEqual(exc.exception.strerror, 'vmodl.RuntimeFault')

    def test_destroy_vm_wait_for_task(self):
        mock_wait_for_task = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   MagicMock(return_value='my_vm')):
            with patch('salt.utils.vmware.wait_for_task', mock_wait_for_task):
                salt.utils.vmware.delete_vm(self.mock_vm_ref)
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
        salt.utils.vmware.unregister_vm(self.mock_vm_ref)
        self.assert_called_once(self.mock_vm_unregister)

    def test_unregister_vm_raise_vim_fault(self):
        exception = vim.fault.VimFault()
        exception.msg = 'vim.fault.VimFault'
        self.mock_vm_ref.UnregisterVM = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareApiError) as exc:
            salt.utils.vmware.unregister_vm(self.mock_vm_ref)
        self.assertEqual(exc.exception.strerror, 'vim.fault.VimFault')

    def test_unregister_vm_raise_runtime_fault(self):
        exception = vmodl.RuntimeFault()
        exception.msg = 'vmodl.RuntimeFault'
        self.mock_vm_ref.UnregisterVM = MagicMock(side_effect=exception)
        with self.assertRaises(VMwareRuntimeError) as exc:
            salt.utils.vmware.unregister_vm(self.mock_vm_ref)
        self.assertEqual(exc.exception.strerror, 'vmodl.RuntimeFault')
