# -*- coding: utf-8 -*-
'''
    :codeauthor: `Nitin Madhok <nmadhok@clemson.edu>`

    tests.unit.cloud.clouds.vmware_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import
from copy import deepcopy

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import MagicMock, NO_MOCK, NO_MOCK_REASON, patch
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../../')

# Import Salt Libs
from salt.cloud.clouds import vmware
from salt.exceptions import SaltCloudSystemExit

# Attempt to import pyVim and pyVmomi libs
HAS_LIBS = True
try:
    from pyVim.connect import SmartConnect, Disconnect  # pylint: disable=W0611
    from pyVmomi import vim, vmodl  # pylint: disable=W0611
except Exception:
    HAS_LIBS = False

# Global Variables
vmware.__active_provider_name__ = ''
vmware.__opts__ = {}
PROVIDER_CONFIG = {
  'vcenter01': {
    'vmware': {
      'driver': 'vmware',
      'url': 'vcenter01.domain.com',
      'user': 'DOMAIN\\user',
      'password': 'verybadpass',
    }
  }
}
VM_NAME = 'test-vm'


class ExtendedTestCase(TestCase):
    '''
    Extended TestCase class containing additional helper methods.
    '''

    def assertRaisesWithMessage(self, exc_type, exc_msg, func, *args, **kwargs):
        try:
            func(*args, **kwargs)
            self.assertFail()
        except Exception as exc:
            self.assertEqual(type(exc), exc_type)
            self.assertEqual(exc.message, exc_msg)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.cloud.clouds.vmware.__virtual__', MagicMock(return_value='vmware'))
class VMwareTestCase(ExtendedTestCase):
    '''
    Unit TestCase for salt.cloud.clouds.vmware module.
    '''

    def test_test_vcenter_connection_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call test_vcenter_connection
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.test_vcenter_connection,
            call='action'
        )

    def test_get_vcenter_version_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call get_vcenter_version
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.get_vcenter_version,
            call='action'
        )

    def test_avail_images_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call avail_images
        with --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.avail_images,
            call='action'
        )

    def test_avail_locations_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call avail_locations
        with --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.avail_locations,
            call='action'
        )

    def test_avail_sizes_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call avail_sizes
        with --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.avail_sizes,
            call='action'
        )

    def test_list_datacenters_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_datacenters
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_datacenters,
            call='action'
        )

    def test_list_clusters_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_clusters
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_clusters,
            call='action'
        )

    def test_list_datastore_clusters_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_datastore_clusters
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_datastore_clusters,
            call='action'
        )

    def test_list_datastores_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_datastores
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_datastores,
            call='action'
        )

    def test_list_hosts_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_hosts
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_hosts,
            call='action'
        )

    def test_list_resourcepools_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_resourcepools
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_resourcepools,
            call='action'
        )

    def test_list_networks_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_networks
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_networks,
            call='action'
        )

    def test_list_nodes_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_nodes
        with --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_nodes,
            call='action'
        )

    def test_list_nodes_min_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_nodes_min
        with --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_nodes_min,
            call='action'
        )

    def test_list_nodes_full_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_nodes_full
        with --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_nodes_full,
            call='action'
        )

    def test_list_nodes_select_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_nodes_full
        with --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_nodes_select,
            call='action'
        )

    def test_list_folders_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_folders
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_folders,
            call='action'
        )

    def test_list_snapshots_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_snapshots
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_snapshots,
            call='action'
        )

    def test_list_hosts_by_cluster_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_hosts_by_cluster
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_hosts_by_cluster,
            call='action'
        )

    def test_list_clusters_by_datacenter_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_clusters_by_datacenter
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_clusters_by_datacenter,
            call='action'
        )

    def test_list_hosts_by_datacenter_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_hosts_by_datacenter
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_hosts_by_datacenter,
            call='action'
        )

    def test_list_hbas_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_hbas
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_hbas,
            call='action'
        )

    def test_list_dvs_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_dvs
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_dvs,
            call='action'
        )

    def test_list_vapps_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_vapps
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_vapps,
            call='action'
        )

    def test_list_templates_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_templates
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.list_templates,
            call='action'
        )

    def test_create_datacenter_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call create_datacenter
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.create_datacenter,
            call='action'
        )

    def test_create_cluster_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call create_cluster
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.create_cluster,
            call='action'
        )

    def test_rescan_hba_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call rescan_hba
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.rescan_hba,
            call='action'
        )

    def test_upgrade_tools_all_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call upgrade_tools_all
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.upgrade_tools_all,
            call='action'
        )

    def test_enter_maintenance_mode_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call enter_maintenance_mode
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.enter_maintenance_mode,
            call='action'
        )

    def test_exit_maintenance_mode_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call exit_maintenance_mode
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.exit_maintenance_mode,
            call='action'
        )

    def test_create_folder_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call create_folder
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.create_folder,
            call='action'
        )

    def test_add_host_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call add_host
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.add_host,
            call='action'
        )

    def test_remove_host_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call remove_host
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.remove_host,
            call='action'
        )

    def test_connect_host_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call connect_host
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.connect_host,
            call='action'
        )

    def test_disconnect_host_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call disconnect_host
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.disconnect_host,
            call='action'
        )

    def test_reboot_host_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call reboot_host
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.reboot_host,
            call='action'
        )

    def test_create_datastore_cluster_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call create_datastore_cluster
        with anything other than --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.create_datastore_cluster,
            call='action'
        )

    def test_show_instance_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call show_instance
        with anything other than --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.show_instance,
            name=VM_NAME,
            call='function'
        )

    def test_start_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call start
        with anything other than --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.start,
            name=VM_NAME,
            call='function'
        )

    def test_stop_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call stop
        with anything other than --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.stop,
            name=VM_NAME,
            call='function'
        )

    def test_suspend_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call suspend
        with anything other than --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.suspend,
            name=VM_NAME,
            call='function'
        )

    def test_reset_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call reset
        with anything other than --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.reset,
            name=VM_NAME,
            call='function'
        )

    def test_terminate_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call terminate
        with anything other than --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.terminate,
            name=VM_NAME,
            call='function'
        )

    def test_destroy_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call destroy
        with --function or -f.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.destroy,
            name=VM_NAME,
            call='function'
        )

    def test_upgrade_tools_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call upgrade_tools
        with anything other than --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.upgrade_tools,
            name=VM_NAME,
            call='function'
        )

    def test_create_snapshot_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call create_snapshot
        with anything other than --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.create_snapshot,
            name=VM_NAME,
            call='function'
        )

    def test_revert_to_snapshot_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call revert_to_snapshot
        with anything other than --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.revert_to_snapshot,
            name=VM_NAME,
            call='function'
        )

    def test_remove_all_snapshots_call(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call remove_all_snapshots
        with anything other than --action or -a.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.remove_all_snapshots,
            name=VM_NAME,
            call='function'
        )

    def test_avail_sizes(self):
        '''
        Tests that avail_sizes returns an empty dictionary.
        '''
        self.assertEqual(
            vmware.avail_sizes(call='foo'),
            {}
        )

    def test_create_datacenter_no_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no kwargs are provided to
        create_datacenter.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.create_datacenter,
            kwargs=None,
            call='function')

    def test_create_datacenter_no_name_in_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when name is not present in
        kwargs that are provided to create_datacenter.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.create_datacenter,
            kwargs={'foo': 'bar'},
            call='function')

    def test_create_datacenter_name_too_short(self):
        '''
        Tests that a SaltCloudSystemExit is raised when name is present in kwargs
        that are provided to create_datacenter but is an empty string.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.create_datacenter,
            kwargs={'name': ''},
            call='function')

    def test_create_datacenter_name_too_long(self):
        '''
        Tests that a SaltCloudSystemExit is raised when name is present in kwargs
        that are provided to create_datacenter but is a string with length <= 80.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.create_datacenter,
            kwargs={'name': 'cCD2GgJGPG1DUnPeFBoPeqtdmUxIWxDoVFbA14vIG0BPoUECkgbRMnnY6gaUPBvIDCcsZ5HU48ubgQu5c'},
            call='function')

    def test_create_cluster_no_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no kwargs are provided to
        create_cluster.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.create_cluster,
            kwargs=None,
            call='function')

    def test_create_cluster_no_name_no_datacenter_in_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when neither the name nor the
        datacenter is present in kwargs that are provided to create_cluster.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.create_cluster,
            kwargs={'foo': 'bar'},
            call='function')

    def test_create_cluster_no_datacenter_in_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the name is present but the
        datacenter is not present in kwargs that are provided to create_cluster.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.create_cluster,
            kwargs={'name': 'my-cluster'},
            call='function')

    def test_create_cluster_no_name_in_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the datacenter is present
        but the name is not present in kwargs that are provided to create_cluster.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.create_cluster,
            kwargs={'datacenter': 'my-datacenter'},
            call='function')

    def test_rescan_hba_no_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no kwargs are provided to
        rescan_hba.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.rescan_hba,
            kwargs=None,
            call='function')

    def test_rescan_hba_no_host_in_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when host is not present in
        kwargs that are provided to rescan_hba.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.rescan_hba,
            kwargs={'foo': 'bar'},
            call='function')

    def test_create_snapshot_no_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no kwargs are provided to
        create_snapshot.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.create_snapshot,
            name=VM_NAME,
            kwargs=None,
            call='action')

    def test_create_snapshot_no_snapshot_name_in_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when snapshot_name is not present
        in kwargs that are provided to create_snapshot.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.create_snapshot,
            name=VM_NAME,
            kwargs={'foo': 'bar'},
            call='action')

    def test_add_host_no_esxi_host_user_in_config(self):
        '''
        Tests that a SaltCloudSystemExit is raised when esxi_host_user is not
        specified in the cloud provider configuration when calling add_host.
        '''
        with patch.dict(vmware.__opts__, {'providers': PROVIDER_CONFIG}, clean=True):
            self.assertRaisesWithMessage(
                SaltCloudSystemExit,
                'You must specify the ESXi host username in your providers config.',
                vmware.add_host,
                kwargs=None,
                call='function')

    def test_add_host_no_esxi_host_password_in_config(self):
        '''
        Tests that a SaltCloudSystemExit is raised when esxi_host_password is not
        specified in the cloud provider configuration when calling add_host.
        '''
        provider_config_additions = {
          'esxi_host_user': 'root',
        }

        provider_config = deepcopy(PROVIDER_CONFIG)
        provider_config['vcenter01']['vmware'].update(provider_config_additions)

        with patch.dict(vmware.__opts__, {'providers': provider_config}, clean=True):
            self.assertRaisesWithMessage(
                SaltCloudSystemExit,
                'You must specify the ESXi host password in your providers config.',
                vmware.add_host,
                kwargs=None,
                call='function')

    def test_add_host_no_host_in_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when host is not present in
        kwargs that are provided to add_host.
        '''
        provider_config_additions = {
          'esxi_host_user': 'root',
          'esxi_host_password': 'myhostpassword'
        }

        provider_config = deepcopy(PROVIDER_CONFIG)
        provider_config['vcenter01']['vmware'].update(provider_config_additions)

        with patch.dict(vmware.__opts__, {'providers': provider_config}, clean=True):
            self.assertRaisesWithMessage(
                SaltCloudSystemExit,
                'You must specify either the IP or DNS name of the host system.',
                vmware.add_host,
                kwargs={'foo': 'bar'},
                call='function')

    def test_add_host_both_cluster_and_datacenter_in_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when both cluster and datacenter
        are present in kwargs that are provided to add_host.
        '''
        provider_config_additions = {
          'esxi_host_user': 'root',
          'esxi_host_password': 'myhostpassword'
        }

        provider_config = deepcopy(PROVIDER_CONFIG)
        provider_config['vcenter01']['vmware'].update(provider_config_additions)

        with patch.dict(vmware.__opts__, {'providers': provider_config}, clean=True):
            self.assertRaisesWithMessage(
                SaltCloudSystemExit,
                'You must specify either the cluster name or the datacenter name.',
                vmware.add_host,
                kwargs={'host': 'my-esxi-host', 'datacenter': 'my-datacenter', 'cluster': 'my-cluster'},
                call='function')

    def test_add_host_neither_cluster_nor_datacenter_in_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when neither cluster nor
        datacenter is present in kwargs that are provided to add_host.
        '''
        provider_config_additions = {
          'esxi_host_user': 'root',
          'esxi_host_password': 'myhostpassword'
        }

        provider_config = deepcopy(PROVIDER_CONFIG)
        provider_config['vcenter01']['vmware'].update(provider_config_additions)

        with patch.dict(vmware.__opts__, {'providers': provider_config}, clean=True):
            self.assertRaisesWithMessage(
                SaltCloudSystemExit,
                'You must specify either the cluster name or the datacenter name.',
                vmware.add_host,
                kwargs={'host': 'my-esxi-host'},
                call='function')

    @skipIf(HAS_LIBS is False, "Install pyVmomi to be able to run this unit test.")
    @patch('salt.cloud.clouds.vmware._get_si', MagicMock(return_value=None))
    @patch('salt.utils.vmware.get_mor_by_property', MagicMock(return_value=None))
    def test_add_host_cluster_not_exists(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the specified cluster present
        in kwargs that are provided to add_host does not exist in the VMware
        environment.
        '''
        provider_config_additions = {
          'esxi_host_user': 'root',
          'esxi_host_password': 'myhostpassword'
        }

        provider_config = deepcopy(PROVIDER_CONFIG)
        provider_config['vcenter01']['vmware'].update(provider_config_additions)

        with patch.dict(vmware.__opts__, {'providers': provider_config}, clean=True):
            self.assertRaisesWithMessage(
                SaltCloudSystemExit,
                'Specified cluster does not exist.',
                vmware.add_host,
                kwargs={'host': 'my-esxi-host', 'cluster': 'my-cluster'},
                call='function')

    @skipIf(HAS_LIBS is False, "Install pyVmomi to be able to run this unit test.")
    @patch('salt.cloud.clouds.vmware._get_si', MagicMock(return_value=None))
    @patch('salt.utils.vmware.get_mor_by_property', MagicMock(return_value=None))
    def test_add_host_datacenter_not_exists(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the specified datacenter
        present in kwargs that are provided to add_host does not exist in the VMware
        environment.
        '''
        provider_config_additions = {
          'esxi_host_user': 'root',
          'esxi_host_password': 'myhostpassword'
        }

        provider_config = deepcopy(PROVIDER_CONFIG)
        provider_config['vcenter01']['vmware'].update(provider_config_additions)

        with patch.dict(vmware.__opts__, {'providers': provider_config}, clean=True):
            self.assertRaisesWithMessage(
                SaltCloudSystemExit,
                'Specified datacenter does not exist.',
                vmware.add_host,
                kwargs={'host': 'my-esxi-host', 'datacenter': 'my-datacenter'},
                call='function')

    def test_remove_host_no_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no kwargs are provided to
        remove_host.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.remove_host,
            kwargs=None,
            call='function')

    def test_remove_host_no_host_in_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when host is not present in
        kwargs that are provided to remove_host.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.remove_host,
            kwargs={'foo': 'bar'},
            call='function')

    @skipIf(HAS_LIBS is False, "Install pyVmomi to be able to run this unit test.")
    @patch('salt.cloud.clouds.vmware._get_si', MagicMock(return_value=None))
    @patch('salt.utils.vmware.get_mor_by_property', MagicMock(return_value=None))
    def test_remove_host_not_exists(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the specified host present
        in kwargs that are provided to remove_host does not exist in the VMware
        environment.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.remove_host,
            kwargs={'host': 'my-host'},
            call='function')

    def test_connect_host_no_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no kwargs are provided to
        connect_host.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.connect_host,
            kwargs=None,
            call='function')

    def test_connect_host_no_host_in_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when host is not present in
        kwargs that are provided to connect_host.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.connect_host,
            kwargs={'foo': 'bar'},
            call='function')

    @skipIf(HAS_LIBS is False, "Install pyVmomi to be able to run this unit test.")
    @patch('salt.cloud.clouds.vmware._get_si', MagicMock(return_value=None))
    @patch('salt.utils.vmware.get_mor_by_property', MagicMock(return_value=None))
    def test_connect_host_not_exists(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the specified host present
        in kwargs that are provided to connect_host does not exist in the VMware
        environment.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.connect_host,
            kwargs={'host': 'my-host'},
            call='function')

    def test_disconnect_host_no_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no kwargs are provided to
        disconnect_host.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.disconnect_host,
            kwargs=None,
            call='function')

    def test_disconnect_host_no_host_in_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when host is not present in
        kwargs that are provided to disconnect_host.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.disconnect_host,
            kwargs={'foo': 'bar'},
            call='function')

    @skipIf(HAS_LIBS is False, "Install pyVmomi to be able to run this unit test.")
    @patch('salt.cloud.clouds.vmware._get_si', MagicMock(return_value=None))
    @patch('salt.utils.vmware.get_mor_by_property', MagicMock(return_value=None))
    def test_disconnect_host_not_exists(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the specified host present
        in kwargs that are provided to disconnect_host does not exist in the VMware
        environment.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.disconnect_host,
            kwargs={'host': 'my-host'},
            call='function')

    def test_reboot_host_no_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no kwargs are provided to
        reboot_host.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.reboot_host,
            kwargs=None,
            call='function')

    def test_reboot_host_no_host_in_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when host is not present in
        kwargs that are provided to reboot_host.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.reboot_host,
            kwargs={'foo': 'bar'},
            call='function')

    @skipIf(HAS_LIBS is False, "Install pyVmomi to be able to run this unit test.")
    @patch('salt.cloud.clouds.vmware._get_si', MagicMock(return_value=None))
    @patch('salt.utils.vmware.get_mor_by_property', MagicMock(return_value=None))
    def test_reboot_host_not_exists(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the specified host present
        in kwargs that are provided to connect_host does not exist in the VMware
        environment.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.reboot_host,
            kwargs={'host': 'my-host'},
            call='function')

    def test_create_datastore_cluster_no_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no kwargs are provided to
        create_datastore_cluster.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.create_datastore_cluster,
            kwargs=None,
            call='function')

    def test_create_datastore_cluster_no_name_in_kwargs(self):
        '''
        Tests that a SaltCloudSystemExit is raised when name is not present in
        kwargs that are provided to create_datastore_cluster.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.create_datastore_cluster,
            kwargs={'foo': 'bar'},
            call='function')

    def test_create_datastore_cluster_name_too_short(self):
        '''
        Tests that a SaltCloudSystemExit is raised when name is present in kwargs
        that are provided to create_datastore_cluster but is an empty string.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.create_datastore_cluster,
            kwargs={'name': ''},
            call='function')

    def test_create_datastore_cluster_name_too_long(self):
        '''
        Tests that a SaltCloudSystemExit is raised when name is present in kwargs
        that are provided to create_datastore_cluster but is a string with length <= 80.
        '''
        self.assertRaises(
            SaltCloudSystemExit,
            vmware.create_datastore_cluster,
            kwargs={'name': 'cCD2GgJGPG1DUnPeFBoPeqtdmUxIWxDoVFbA14vIG0BPoUECkgbRMnnY6gaUPBvIDCcsZ5HU48ubgQu5c'},
            call='function')


class CloneFromSnapshotTest(TestCase):
    '''
    Test functionality to clone from snapshot
    '''
    @skipIf(HAS_LIBS is False, "Install pyVmomi to be able to run this unit test.")
    def test_quick_linked_clone(self):
        '''
        Test that disk move type is
        set to createNewChildDiskBacking
        '''
        self._test_clone_type(vmware.QUICK_LINKED_CLONE)

    @skipIf(HAS_LIBS is False, "Install pyVmomi to be able to run this unit test.")
    def test_current_state_linked_clone(self):
        '''
        Test that disk move type is
        set to moveChildMostDiskBacking
        '''
        self._test_clone_type(vmware.CURRENT_STATE_LINKED_CLONE)

    @skipIf(HAS_LIBS is False, "Install pyVmomi to be able to run this unit test.")
    def test_copy_all_disks_full_clone(self):
        '''
        Test that disk move type is
        set to moveAllDiskBackingsAndAllowSharing
        '''
        self._test_clone_type(vmware.COPY_ALL_DISKS_FULL_CLONE)

    @skipIf(HAS_LIBS is False, "Install pyVmomi to be able to run this unit test.")
    def test_flatten_all_all_disks_full_clone(self):
        '''
        Test that disk move type is
        set to moveAllDiskBackingsAndDisallowSharing
        '''
        self._test_clone_type(vmware.FLATTEN_DISK_FULL_CLONE)

    @skipIf(HAS_LIBS is False, "Install pyVmomi to be able to run this unit test.")
    def test_raises_error_for_invalid_disk_move_type(self):
        '''
        Test that invalid disk move type
        raises error
        '''
        with self.assertRaises(SaltCloudSystemExit):
            self._test_clone_type('foobar')

    def _test_clone_type(self, clone_type):
        '''
        Assertions for checking that a certain clone type
        works
        '''
        obj_ref = MagicMock()
        obj_ref.snapshot = vim.vm.Snapshot(None, None)
        obj_ref.snapshot.currentSnapshot = vim.vm.Snapshot(None, None)
        clone_spec = vmware.handle_snapshot(
            vim.vm.ConfigSpec(),
            obj_ref,
            vim.vm.RelocateSpec(),
            False,
            {'snapshot': {
                'disk_move_type': clone_type}})
        self.assertEqual(clone_spec.location.diskMoveType, clone_type)

        obj_ref2 = MagicMock()
        obj_ref2.snapshot = vim.vm.Snapshot(None, None)
        obj_ref2.snapshot.currentSnapshot = vim.vm.Snapshot(None, None)

        clone_spec2 = vmware.handle_snapshot(
            vim.vm.ConfigSpec(),
            obj_ref2,
            vim.vm.RelocateSpec(),
            True,
            {'snapshot': {
                'disk_move_type': clone_type}})

        self.assertEqual(clone_spec2.location.diskMoveType, clone_type)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(VMwareTestCase, needs_daemon=False)
    run_tests(CloneFromSnapshotTest, needs_daemon=False)
