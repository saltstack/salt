# -*- coding: utf-8 -*-
'''
:codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

Tests for cluster related functions in salt.utils.vmware
'''

# Import python libraries
from __future__ import absolute_import
import logging
# Import Salt testing libraries
from salttesting import TestCase, skipIf
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock, call
# Import Salt libraries
from salt.exceptions import VMwareApiError, VMwareRuntimeError, \
        VMwareObjectRetrievalError
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
@patch('salt.utils.vmware.get_managed_object_name',
       MagicMock())
@patch('salt.utils.vmware.get_service_instance_from_managed_object',
       MagicMock())
@patch('salt.utils.vmware.get_mors_with_properties',
       MagicMock(return_value=[{'name': 'fake_cluster',
                                'object': MagicMock()}]))
class GetClusterTestCase(TestCase):
    '''Tests for salt.utils.vmware.get_cluster'''

    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_dc = MagicMock()
        self.mock_cluster1 = MagicMock()
        self.mock_cluster2 = MagicMock()
        self.mock_entries = [{'name': 'fake_cluster1',
                              'object': self.mock_cluster1},
                             {'name': 'fake_cluster2',
                              'object': self.mock_cluster2}]

    def test_get_managed_object_name_call(self):
        mock_get_managed_object_name = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vmware.get_cluster(self.mock_dc, 'fake_cluster')
        mock_get_managed_object_name.assert_called_once_with(self.mock_dc)

    def test_get_service_instance_from_managed_object(self):
        mock_dc_name = MagicMock()
        mock_get_service_instance_from_managed_object = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   MagicMock(return_value=mock_dc_name)):
            with patch(
                'salt.utils.vmware.get_service_instance_from_managed_object',
                mock_get_service_instance_from_managed_object):

                vmware.get_cluster(self.mock_dc, 'fake_cluster')
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
            vmware.get_cluster(self.mock_dc, 'fake_cluster')
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

                    vmware.get_cluster(self.mock_dc, 'fake_cluster')
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
                    vmware.get_cluster(self.mock_dc, 'fake_cluster')
        self.assertEqual(excinfo.exception.strerror,
                         'Cluster \'fake_cluster\' was not found in '
                         'datacenter \'fake_dc\'')

    def test_cluster_not_found(self):
        with patch('salt.utils.vmware.get_managed_object_name',
                   MagicMock(return_value='fake_dc')):
            with patch('salt.utils.vmware.get_mors_with_properties',
                       MagicMock(return_value=self.mock_entries)):
                with self.assertRaises(VMwareObjectRetrievalError) as excinfo:
                    vmware.get_cluster(self.mock_dc, 'fake_cluster')
        self.assertEqual(excinfo.exception.strerror,
                         'Cluster \'fake_cluster\' was not found in '
                         'datacenter \'fake_dc\'')

    def test_cluster_found(self):
        with patch('salt.utils.vmware.get_managed_object_name',
                   MagicMock(return_value='fake_dc')):
            with patch('salt.utils.vmware.get_mors_with_properties',
                       MagicMock(return_value=self.mock_entries)):
                res = vmware.get_cluster(self.mock_dc, 'fake_cluster2')
        self.assertEqual(res, self.mock_cluster2)


@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@patch('salt.utils.vmware.get_managed_object_name', MagicMock())
class CreateClusterTestCase(TestCase):
    '''Tests for salt.utils.vmware.create_cluster'''

    def setUp(self):
        self.mock_create_cluster_ex = MagicMock()
        self.mock_dc = MagicMock(
            hostFolder=MagicMock(CreateClusterEx=self.mock_create_cluster_ex))
        self.mock_cluster_spec = MagicMock()

    def test_get_managed_object_name(self):
        mock_get_managed_object_name = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vmware.create_cluster(self.mock_dc, 'fake_cluster',
                                  self.mock_cluster_spec)
        mock_get_managed_object_name.assert_called_once_with(self.mock_dc)

    def test_create_cluster_call(self):
        vmware.create_cluster(self.mock_dc, 'fake_cluster',
                              self.mock_cluster_spec)
        self.mock_create_cluster_ex.assert_called_once_with(
           'fake_cluster', self.mock_cluster_spec)

    def test_create_cluster_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_dc.hostFolder.CreateClusterEx = MagicMock(
            side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            vmware.create_cluster(self.mock_dc, 'fake_cluster',
                                  self.mock_cluster_spec)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_create_cluster_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_dc.hostFolder.CreateClusterEx = MagicMock(
            side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            vmware.create_cluster(self.mock_dc, 'fake_cluster',
                                  self.mock_cluster_spec)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@patch('salt.utils.vmware.get_managed_object_name', MagicMock())
@patch('salt.utils.vmware.wait_for_task', MagicMock())
class UpdateClusterTestCase(TestCase):
    '''Tests for salt.utils.vmware.update_cluster'''

    def setUp(self):
        self.mock_task = MagicMock()
        self.mock_reconfigure_compute_resource_task = \
                MagicMock(return_value=self.mock_task)
        self.mock_cluster = MagicMock(ReconfigureComputeResource_Task=
            self.mock_reconfigure_compute_resource_task)
        self.mock_cluster_spec = MagicMock()

    def test_get_managed_object_name(self):
        mock_get_managed_object_name = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   mock_get_managed_object_name):
            vmware.update_cluster(self.mock_cluster, self.mock_cluster_spec)
        mock_get_managed_object_name.assert_called_once_with(self.mock_cluster)

    def test_reconfigure_compute_resource_task_call(self):
        vmware.update_cluster(self.mock_cluster, self.mock_cluster_spec)
        self.mock_reconfigure_compute_resource_task.assert_called_once_with(
            self.mock_cluster_spec, modify=True)

    def test_reconfigure_compute_resource_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_cluster.ReconfigureComputeResource_Task = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            vmware.update_cluster(self.mock_cluster, self.mock_cluster_spec)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_reconfigure_compute_resource_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        self.mock_cluster.ReconfigureComputeResource_Task = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareRuntimeError) as excinfo:
            vmware.update_cluster(self.mock_cluster, self.mock_cluster_spec)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_wait_for_task_call(self):
        mock_wait_for_task = MagicMock()
        with patch('salt.utils.vmware.get_managed_object_name',
                   MagicMock(return_value='fake_cluster')):
            with patch('salt.utils.vmware.wait_for_task', mock_wait_for_task):
                vmware.update_cluster(self.mock_cluster,
                                      self.mock_cluster_spec)
        mock_wait_for_task.assert_called_once_with(
            self.mock_task, 'fake_cluster', 'ClusterUpdateTask')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GetClusterTestCase, needs_daemon=False)
    run_tests(CreateClusterTestCase, needs_daemon=False)
    run_tests(UpdateClusterTestCase, needs_daemon=False)
