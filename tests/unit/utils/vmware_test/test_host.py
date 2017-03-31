# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for host functions in salt.utils.vmware
'''

# Import python libraries
from __future__ import absolute_import
import logging

# Import Salt testing libraries
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock

# Import Salt libraries
import salt.utils.vmware
# Import Third Party Libs
try:
    from pyVmomi import vim
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

# Get Logging Started
log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@patch('salt.utils.vmware.get_mors_with_properties',
       MagicMock(return_value=[]))
@patch('salt.utils.vmware.get_datacenter',
       MagicMock(return_value=None))
@patch('salt.utils.vmware.get_cluster',
       MagicMock(return_value=None))
class GetHostsTestCase(TestCase):
    '''Tests for salt.utils.vmware.get_hosts'''

    def setUp(self):
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
        mock_get_cl.assert_called_once_with(mock_dc, 'fake_cluster')
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
        cluster1 = vim.ClusterComputeResource('fake_good_cluster')
        cluster2 = vim.ClusterComputeResource('fake_bad_cluster')
        # Mock cluster1.name and cluster2.name
        cluster1._stub = MagicMock(InvokeAccessor=MagicMock(
            return_value='fake_good_cluster'))
        cluster2._stub = MagicMock(InvokeAccessor=MagicMock(
            return_value='fake_bad_cluster'))
        self.mock_prop_host1['parent'] = cluster2
        self.mock_prop_host2['parent'] = cluster1
        self.mock_prop_host3['parent'] = cluster1
        with patch('salt.utils.vmware.get_mors_with_properties',
                   MagicMock(return_value=self.mock_prop_hosts)):
            res = salt.utils.vmware.get_hosts(self.mock_si,
                                              datacenter_name='fake_datacenter',
                                              cluster_name='fake_good_cluster',
                                              get_all_hosts=True)
        self.assertEqual(res, [self.mock_host2, self.mock_host3])

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
