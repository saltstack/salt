# -*- coding: utf-8 -*-
'''
    :codeauthor: `Nitin Madhok <nmadhok@clemson.edu>`

    tests.unit.cloud.clouds.vmware_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import MagicMock, NO_MOCK, NO_MOCK_REASON, patch
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../../')

# Import Salt Libs
from salt.cloud.clouds import vmware
from salt.exceptions import SaltCloudSystemExit

# Global Variables
vmware.__active_provider_name__ = ''
vmware.__opts__ = {}
VM_NAME = 'test-vm'


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.cloud.clouds.vmware.__virtual__', MagicMock(return_value='vmware'))
class VMwareTestCase(TestCase):
    '''
    Unit TestCase for salt.cloud.clouds.vmware module.
    '''

    def test_test_vcenter_connection_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call test_vcenter_connection
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.test_vcenter_connection, call='action')

    def test_get_vcenter_version_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call get_vcenter_version
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.get_vcenter_version, call='action')

    def test_avail_images_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call avail_images
        with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.avail_images, call='action')

    def test_avail_locations_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call avail_locations
        with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.avail_locations, call='action')

    def test_avail_sizes_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call avail_sizes
        with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.avail_sizes, call='action')

    def test_list_datacenters_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_datacenters
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_datacenters, call='action')

    def test_list_clusters_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_clusters
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_clusters, call='action')

    def test_list_datastore_clusters_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_datastore_clusters
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_datastore_clusters, call='action')

    def test_list_datastores_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_datastores
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_datastores, call='action')

    def test_list_hosts_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_hosts
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_hosts, call='action')

    def test_list_resourcepools_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_resourcepools
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_resourcepools, call='action')

    def test_list_networks_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_networks
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_networks, call='action')

    def test_list_nodes_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_nodes
        with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_nodes, call='action')

    def test_list_nodes_min_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_nodes_min
        with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_nodes_min, call='action')

    def test_list_nodes_full_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_nodes_full
        with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_nodes_full, call='action')

    def test_list_nodes_select_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_nodes_full
        with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_nodes_select, call='action')

    def test_list_folders_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_folders
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_folders, call='action')

    def test_list_snapshots_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_snapshots
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_snapshots, call='action')

    def test_list_hosts_by_cluster_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_hosts_by_cluster
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_hosts_by_cluster, call='action')

    def test_list_clusters_by_datacenter_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_clusters_by_datacenter
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_clusters_by_datacenter, call='action')

    def test_list_hosts_by_datacenter_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_hosts_by_datacenter
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_hosts_by_datacenter, call='action')

    def test_list_hbas_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_hbas
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_hbas, call='action')

    def test_list_dvs_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_dvs
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_dvs, call='action')

    def test_list_vapps_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_vapps
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_vapps, call='action')

    def test_list_templates_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_templates
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.list_templates, call='action')

    def test_create_datacenter_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call create_datacenter
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.create_datacenter, call='action')

    def test_create_cluster_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call create_cluster
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.create_cluster, call='action')

    def test_rescan_hba_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call rescan_hba
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.rescan_hba, call='action')

    def test_upgrade_tools_all_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call upgrade_tools_all
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.upgrade_tools_all, call='action')

    def test_enter_maintenance_mode_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call enter_maintenance_mode
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.enter_maintenance_mode, call='action')

    def test_exit_maintenance_mode_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call exit_maintenance_mode
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.exit_maintenance_mode, call='action')

    def test_create_folder_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call create_folder
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.create_folder, call='action')

    def test_add_host_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call add_host
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.add_host, call='action')

    def test_remove_host_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call remove_host
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.remove_host, call='action')

    def test_connect_host_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call connect_host
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.connect_host, call='action')

    def test_disconnect_host_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call disconnect_host
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.disconnect_host, call='action')

    def test_reboot_host_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call reboot_host
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.reboot_host, call='action')

    def test_create_datastore_cluster_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call create_datastore_cluster
        with anything other than --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.create_datastore_cluster, call='action')

    def test_show_instance_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call show_instance
        with anything other than --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.show_instance, name=VM_NAME, call='function')

    def test_start_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call start
        with anything other than --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.start, name=VM_NAME, call='function')

    def test_stop_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call stop
        with anything other than --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.stop, name=VM_NAME, call='function')

    def test_suspend_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call suspend
        with anything other than --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.suspend, name=VM_NAME, call='function')

    def test_reset_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call reset
        with anything other than --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.reset, name=VM_NAME, call='function')

    def test_terminate_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call terminate
        with anything other than --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.terminate, name=VM_NAME, call='function')

    def test_destroy_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call destroy
        with --function or -f.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.destroy, name=VM_NAME, call='function')

    def test_upgrade_tools_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call upgrade_tools
        with anything other than --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.upgrade_tools, name=VM_NAME, call='function')

    def test_create_snapshot_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call create_snapshot
        with anything other than --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.create_snapshot, name=VM_NAME, call='function')

    def test_revert_to_snapshot_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call revert_to_snapshot
        with anything other than --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.revert_to_snapshot, name=VM_NAME, call='function')

    def test_remove_all_snapshots_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call remove_all_snapshots
        with anything other than --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, vmware.remove_all_snapshots, name=VM_NAME, call='function')

    def test_avail_sizes(self):
        '''
        Tests that avail_sizes returns an empty dictionary.
        '''
        self.assertEqual(vmware.avail_sizes(call='foo'), {})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(VMwareTestCase, needs_daemon=False)
