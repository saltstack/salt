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
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock
# Import Salt libraries
from salt.exceptions import VMwareApiError, VMwareRuntimeError
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

    def test_create_cluster_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        self.mock_cluster.ReconfigureComputeResource_Task = \
                MagicMock(side_effect=exc)
        with self.assertRaises(VMwareApiError) as excinfo:
            vmware.update_cluster(self.mock_cluster, self.mock_cluster_spec)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_create_cluster_raise_runtime_fault(self):
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
    run_tests(UpdateClusterTestCase, needs_daemon=False)
