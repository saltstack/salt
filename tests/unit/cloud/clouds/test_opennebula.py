# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import MagicMock, NO_MOCK, NO_MOCK_REASON, patch

# Import Salt Libs
from salt.cloud.clouds import opennebula
from salt.exceptions import SaltCloudSystemExit, SaltCloudNotFound

# Import Third Party Libs
try:
    from lxml import etree  # pylint: disable=W0611
    HAS_XML_LIBS = True
except ImportError:
    HAS_XML_LIBS = False

VM_NAME = 'my-vm'


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.cloud.clouds.opennebula.__virtual__', MagicMock(return_value='opennebula'))
class OpenNebulaTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Unit TestCase for salt.cloud.clouds.opennebula module.
    '''
    def setup_loader_modules(self):
        return {
            opennebula: {
                '__utils__': {
                    'cloud.cache_node': MagicMock()
                },
                '__active_provider_name__': ''
            }
        }

    def test_avail_images_action(self):
        '''
        Tests that a SaltCloudSystemExit error is raised when trying to call
        avail_images with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.avail_images, 'action')

    def test_avail_locations_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call avail_locations
        with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.avail_locations, 'action')

    def test_avail_sizes_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call avail_sizes
        with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.avail_sizes, 'action')

    def test_avail_sizes(self):
        '''
        Tests that avail_sizes returns an empty dictionary.
        '''
        self.assertEqual(opennebula.avail_sizes(call='foo'), {})

    def test_list_clusters_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_clusters
        with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.list_clusters, 'action')

    def test_list_datastores_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_datastores
        with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.list_datastores, 'action')

    def test_list_hosts_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_datastores
        with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.list_hosts, 'action')

    def test_list_nodes_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_nodes
        with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.list_nodes, 'action')

    def test_list_nodes_full_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_nodes_full
        with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.list_nodes_full, 'action')

    def test_list_nodes_select_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_nodes_full
        with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.list_nodes_select, 'action')

    def test_list_security_groups_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call
        list_security_groups with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.list_security_groups, 'action')

    def test_list_templates_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_templates
        with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.list_templates, 'action')

    def test_list_vns_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call list_vns
        with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.list_vns, 'action')

    def test_reboot_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call reboot
        with anything other that --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.reboot, 'my-vm', 'foo')

    def test_start_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call start
        with anything other that --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.start, 'my-vm', 'foo')

    def test_stop_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call stop
        with anything other that --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.stop, 'my-vm', 'foo')

    def test_get_cluster_id_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call
        get_cluster_id with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_cluster_id,
                          call='action')

    def test_get_cluster_id_no_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_cluster_id,
                          None,
                          call='foo')

    @patch('salt.cloud.clouds.opennebula.list_clusters',
           MagicMock(return_value={'foo': {'id': 'bar'}}))
    def test_get_cluster_id_not_found(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_cluster_id,
                          kwargs={'name': 'test'},
                          call='function')

    @patch('salt.cloud.clouds.opennebula.list_clusters',
           MagicMock(return_value={'test-cluster': {'id': '100'}}))
    def test_get_cluster_id_success(self):
        '''
        Tests that the function returns successfully.
        '''
        mock_id = '100'
        mock_kwargs = {'name': 'test-cluster'}
        self.assertEqual(opennebula.get_cluster_id(mock_kwargs, 'foo'),
                         mock_id)

    def test_get_datastore_id_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call
        get_datastore_id with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_datastore_id,
                          call='action')

    def test_get_datastore_id_no_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_datastore_id,
                          None,
                          call='foo')

    @patch('salt.cloud.clouds.opennebula.list_datastores',
           MagicMock(return_value={'test-datastore': {'id': '100'}}))
    def test_get_datastore_id_not_found(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_datastore_id,
                          kwargs={'name': 'test'},
                          call='function')

    @patch('salt.cloud.clouds.opennebula.list_datastores',
           MagicMock(return_value={'test-datastore': {'id': '100'}}))
    def test_get_datastore_id_success(self):
        '''
        Tests that the function returns successfully.
        '''
        mock_id = '100'
        mock_kwargs = {'name': 'test-datastore'}
        self.assertEqual(opennebula.get_datastore_id(mock_kwargs, 'foo'),
                         mock_id)

    def test_get_host_id_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call
        get_host_id with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_host_id,
                          call='action')

    def test_get_host_id_no_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_host_id,
                          None,
                          call='foo')

    @patch('salt.cloud.clouds.opennebula.avail_locations',
           MagicMock(return_value={'test-host': {'id': '100'}}))
    def test_get_host_id_not_found(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_host_id,
                          kwargs={'name': 'test'},
                          call='function')

    @patch('salt.cloud.clouds.opennebula.avail_locations',
           MagicMock(return_value={'test-host': {'id': '100'}}))
    def test_get_host_id_success(self):
        '''
        Tests that the function returns successfully.
        '''
        mock_id = '100'
        mock_kwargs = {'name': 'test-host'}
        self.assertEqual(opennebula.get_host_id(mock_kwargs, 'foo'),
                         mock_id)

    @patch('salt.cloud.clouds.opennebula.avail_images', MagicMock(return_value={}))
    @patch('salt.config.get_cloud_config_value', MagicMock(return_value='foo'))
    def test_get_image_not_found(self):
        '''
        Tests that a SaltCloudNotFound is raised when the image doesn't exist.
        '''
        self.assertRaises(SaltCloudNotFound, opennebula.get_image, 'my-vm')

    @patch('salt.cloud.clouds.opennebula.avail_images',
           MagicMock(return_value={'my-vm': {'name': 'my-vm', 'id': 0}}))
    @patch('salt.config.get_cloud_config_value', MagicMock(return_value='my-vm'))
    def test_get_image_success(self):
        '''
        Tests that the image is returned successfully.
        '''
        self.assertEqual(opennebula.get_image('my-vm'), 0)

    def test_get_image_id_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call
        get_image_id with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_image_id,
                          call='action')

    def test_get_image_id_no_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_image_id,
                          None,
                          call='foo')

    @patch('salt.cloud.clouds.opennebula.avail_images',
           MagicMock(return_value={'test-image': {'id': '100'}}))
    def test_get_image_id_not_found(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_image_id,
                          kwargs={'name': 'test'},
                          call='function')

    @patch('salt.cloud.clouds.opennebula.avail_images',
           MagicMock(return_value={'test-image': {'id': '100'}}))
    def test_get_image_id_success(self):
        '''
        Tests that the function returns successfully.
        '''
        mock_id = '100'
        mock_kwargs = {'name': 'test-image'}
        self.assertEqual(opennebula.get_image_id(mock_kwargs, 'foo'),
                         mock_id)

    @patch('salt.cloud.clouds.opennebula.avail_locations', MagicMock(return_value={}))
    @patch('salt.config.get_cloud_config_value', MagicMock(return_value='foo'))
    def test_get_location_not_found(self):
        '''
        Tests that a SaltCloudNotFound is raised when the location doesn't exist.
        '''
        self.assertRaises(SaltCloudNotFound, opennebula.get_location, 'my-vm')

    @patch('salt.cloud.clouds.opennebula.avail_locations',
           MagicMock(return_value={'my-host': {'name': 'my-host', 'id': 0}}))
    @patch('salt.config.get_cloud_config_value', MagicMock(return_value='my-host'))
    def test_get_location_success(self):
        '''
        Tests that the image is returned successfully.
        '''
        self.assertEqual(opennebula.get_location('my-host'), 0)

    def test_get_secgroup_id_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call
        get_host_id with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_secgroup_id,
                          call='action')

    def test_get_secgroup_id_no_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_secgroup_id,
                          None,
                          call='foo')

    @patch('salt.cloud.clouds.opennebula.list_security_groups',
           MagicMock(return_value={'test-security-group': {'id': '100'}}))
    def test_get_secgroup_id_not_found(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_secgroup_id,
                          kwargs={'name': 'test'},
                          call='function')

    @patch('salt.cloud.clouds.opennebula.list_security_groups',
           MagicMock(return_value={'test-secgroup': {'id': '100'}}))
    def test_get_secgroup_id_success(self):
        '''
        Tests that the function returns successfully.
        '''
        mock_id = '100'
        mock_kwargs = {'name': 'test-secgroup'}
        self.assertEqual(opennebula.get_secgroup_id(mock_kwargs, 'foo'),
                         mock_id)

    def test_get_template_id_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call
        get_template_id with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_template_id,
                          call='action')

    def test_get_template_id_no_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_template_id,
                          None,
                          call='foo')

    @patch('salt.cloud.clouds.opennebula.list_templates',
           MagicMock(return_value={'test-template': {'id': '100'}}))
    def test_get_template_id_not_found(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_template_id,
                          kwargs={'name': 'test'},
                          call='function')

    @patch('salt.cloud.clouds.opennebula.list_templates',
           MagicMock(return_value={'test-template': {'id': '100'}}))
    def test_get_template_id_success(self):
        '''
        Tests that the function returns successfully.
        '''
        mock_id = '100'
        mock_kwargs = {'name': 'test-template'}
        self.assertEqual(opennebula.get_template_id(mock_kwargs, 'foo'),
                         mock_id)

    def test_get_vm_id_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call
        get_vm_id with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_vm_id,
                          call='action')

    def test_get_vm_id_no_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_vm_id,
                          None,
                          call='foo')

    @patch('salt.cloud.clouds.opennebula.list_nodes',
           MagicMock(return_value={'test-vm': {'id': '100'}}))
    def test_get_vm_id_not_found(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_vm_id,
                          kwargs={'name': 'test'},
                          call='function')

    @patch('salt.cloud.clouds.opennebula.list_nodes',
           MagicMock(return_value={'test-vm': {'id': '100'}}))
    def test_get_vm_id_success(self):
        '''
        Tests that the function returns successfully.
        '''
        mock_id = '100'
        mock_kwargs = {'name': 'test-vm'}
        self.assertEqual(opennebula.get_vm_id(mock_kwargs, 'foo'),
                         mock_id)

    def test_get_vn_id_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when trying to call
        get_vn_id with --action or -a.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_vn_id,
                          call='action')

    def test_get_vn_id_no_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_vn_id,
                          None,
                          call='foo')

    @patch('salt.cloud.clouds.opennebula.list_vns',
           MagicMock(return_value={'test-vn': {'id': '100'}}))
    def test_get_vn_id_not_found(self):
        '''
        Tests that a SaltCloudSystemExit is raised when no name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.get_vn_id,
                          kwargs={'name': 'test'},
                          call='function')

    @patch('salt.cloud.clouds.opennebula.list_vns',
           MagicMock(return_value={'test-vn': {'id': '100'}}))
    def test_get_vn_id_success(self):
        '''
        Tests that the function returns successfully.
        '''
        mock_id = '100'
        mock_kwargs = {'name': 'test-vn'}
        self.assertEqual(opennebula.get_vn_id(mock_kwargs, 'foo'),
                         mock_id)

    # TODO: Write tests for create function

    def test_destroy_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.destroy, 'my-vm', 'function')

    def test_image_allocate_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.image_allocate, 'foo')

    def test_image_allocate_no_name_or_datastore_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when a neither a datastore_id
        nor a datastore_name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.image_allocate, 'function')

    def test_image_allocate_no_path_or_data(self):
        '''
        Tests that a SaltCloudSystemExit is raised when neither the path nor data args
        are provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.image_allocate,
                          'function',
                          kwargs={'datastore_id': '5'})

    def test_image_clone_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.image_clone, 'foo')

    def test_image_clone_no_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when a name isn't provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.image_clone, 'function')

    def test_image_clone_no_image_id_or_image_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when neither the image_id nor
        the image_name args are provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.image_clone,
                          'function',
                          kwargs={'name': 'test'})

    @skipIf(True, 'Need to figure out how to mock calls to the O.N. API first.')
    @patch('image.clone', MagicMock(return_value=[True, 11, 0]))
    def test_image_clone_success(self):
        '''
        Tests that image_clone returns successfully
        '''
        name = 'test-image'
        expected = {
            'action': 'image.clone',
            'cloned': 'True',
            'cloned_image_id': '11',
            'cloned_image_name': name,
            'error_code': '0',
        }
        ret = opennebula.image_clone('function', kwargs={'name': name, 'image_id': 1})
        self.assertEqual(expected, ret)

    def test_image_delete_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.image_delete, 'foo')

    def test_image_delete_no_name_or_image_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when a neither an image_id
        nor a name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.image_delete, 'function')

    def test_image_info_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.image_info, 'foo')

    def test_image_info_no_image_id_or_image_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when a neither an image_id
        nor a name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.image_info, 'function')

    def test_image_persist_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.image_persistent, 'foo')

    def test_image_persist_no_persist(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the persist kwarg is missing.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.image_persistent, 'function')

    def test_image_persist_no_name_or_image_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when a neither an image_id
        nor a name is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.image_delete,
                          'function',
                          kwargs={'persist': False})

    def test_image_snapshot_delete_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.image_snapshot_delete,
                          call='foo')

    def test_image_snapshot_delete_no_snapshot_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the snapshot_id kwarg is
        missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.image_snapshot_delete,
                          call='function',
                          kwargs=None)

    def test_image_snapshot_delete_no_image_name_or_image_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the image_id and image_name
        kwargs are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.image_snapshot_delete,
                          call='function',
                          kwargs={'snapshot_id': 0})

    def test_image_snapshot_revert_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.image_snapshot_revert,
                          call='foo')

    def test_image_snapshot_revert_no_snapshot_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the snapshot_id kwarg is
        missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.image_snapshot_revert,
                          call='function',
                          kwargs=None)

    def test_image_snapshot_revert_no_image_name_or_image_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the image_id and image_name
        kwargs are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.image_snapshot_revert,
                          call='function',
                          kwargs={'snapshot_id': 0})

    def test_image_snapshot_flatten_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.image_snapshot_flatten,
                          call='foo')

    def test_image_snapshot_flatten_no_snapshot_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the snapshot_id kwarg is
        missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.image_snapshot_flatten,
                          call='function',
                          kwargs=None)

    def test_image_snapshot_flatten_no_image_name_or_image_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the image_id and image_name
        kwargs are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.image_snapshot_flatten,
                          call='function',
                          kwargs={'snapshot_id': 0})

    def test_image_update_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.image_update, 'foo')

    def test_image_update_no_update_type(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the update_type kwarg is
        missing.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.image_update, 'function')

    def test_image_update_bad_update_type_value(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the update_type kwarg is
        not a valid value.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.image_update,
                          'function',
                          kwargs={'update_type': 'foo'})

    def test_image_update_no_image_id_or_image_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the image_id and image_name
        kwargs are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.image_update,
                          'function',
                          kwargs={'update_type': 'merge'})

    def test_image_update_no_data_or_path(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the data and path
        kwargs are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.image_update,
                          'function',
                          kwargs={'update_type': 'merge', 'image_id': '0'})

    def test_show_instance_action_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --action or -a is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.show_instance,
                          VM_NAME,
                          call='foo')

    @patch('salt.cloud.clouds.opennebula._get_node',
           MagicMock(return_value={'my-vm': {'name': 'my-vm', 'id': 0}}))
    def test_show_instance_success(self):
        '''
        Tests that the node was found successfully.
        '''
        ret = {'my-vm': {'name': 'my-vm', 'id': 0}}
        self.assertEqual(opennebula.show_instance('my-vm', call='action'), ret)

    def test_secgroup_allocate_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.secgroup_allocate, 'foo')

    def test_secgroup_allocate_no_data_or_path(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the data and path
        kwargs are missing.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.secgroup_allocate, 'function')

    def test_secgroup_clone_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.secgroup_clone, 'foo')

    def test_secgroup_clone_no_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the name kwarg is
        missing.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.secgroup_clone, 'function')

    def test_secgroup_clone_no_secgroup_id_or_secgroup_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the secgroup_id and
        secgroup_name kwargs are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.secgroup_clone,
                          'function',
                          kwargs={'name': 'test'})

    def test_secgroup_delete_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.secgroup_delete, 'foo')

    def test_secgroup_delete_no_secgroup_id_or_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the secgroup_id and
        name kwargs are missing.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.secgroup_clone, 'function')

    def test_secgroup_info_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.secgroup_info, 'foo')

    def test_secgroup_info_no_secgroup_id_or_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the secgroup_id and
        name kwargs are missing.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.secgroup_info, 'function')

    def test_secgroup_update_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.secgroup_update, 'foo')

    def test_secgroup_update_no_update_type(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the update_type arg is
        missing.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.secgroup_update, 'function')

    def test_secgroup_update_bad_update_type_value(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the update_type contains
        an invalid value.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.secgroup_update,
                          'function',
                          kwargs={'update_type': 'foo'})

    def test_secgroup_update_no_secgroup_id_or_secgroup_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the secgroup_id and
        secgroup_name kwargs are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.secgroup_update,
                          'function',
                          kwargs={'update_type': 'merge'})

    def test_secgroup_update_no_data_or_path(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the data and
        path kwargs are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.secgroup_update,
                          'function',
                          kwargs={'update_type': 'merge', 'secgroup_id': '0'})

    def test_template_allocate_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.template_allocate, 'foo')

    def test_template_allocate_no_data_or_path(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the data and
        path kwargs are missing.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.template_allocate, 'function')

    def test_template_clone_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.template_clone, 'foo')

    def test_template_clone_no_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the name arg is missing.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.template_clone, 'function')

    def test_template_clone_no_template_name_or_template_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the template_name and
        template_id args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.template_clone,
                          'function',
                          kwargs={'name': 'foo'})

    def test_template_delete_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.template_delete, 'foo')

    def test_template_delete_no_name_or_template_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the name and
        template_id args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.template_delete, 'function')

    def test_template_instantiate_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.template_instantiate, 'foo')

    def test_template_instantiate_no_vm_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the vm_name arg is missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.template_instantiate,
                          'function',
                          None)

    def test_template_instantiate_no_template_id_or_template_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the template_name and
        template_id args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.template_instantiate,
                          'function',
                          kwargs={'vm_name': 'test'})

    def test_template_update_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.template_update,
                          call='foo')

    def test_template_update_bad_update_type_value(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the update_type contains
        and invalid value.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.template_update,
                          call='function',
                          kwargs={'update_type': 'foo'})

    def test_template_update_no_template_id_or_template_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the template_id and the
        template_name args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.template_update,
                          call='function',
                          kwargs={'update_type': 'merge'})

    def test_template_update_no_data_or_path(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the data and the
        path args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.template_update,
                          call='function',
                          kwargs={'update_type': 'merge',
                                  'template_id': '0'})

    def test_vm_action_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --action or -a is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_action,
                          VM_NAME,
                          call='foo')

    def test_vm_action_no_action(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the action arg is missing
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_action,
                          VM_NAME,
                          call='action')

    def test_vm_allocate_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.vm_allocate, 'foo')

    def test_vm_allocate_no_data_or_path(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the data and
        path kwargs are missing.
        '''
        self.assertRaises(SaltCloudSystemExit, opennebula.vm_allocate, 'function')

    def test_vm_attach_action_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --action or -a is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_attach,
                          VM_NAME,
                          call='foo')

    def test_vm_attach_no_data_or_path(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the data and
        path kwargs are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_attach,
                          VM_NAME,
                          call='action')

    def test_vm_attach_nic_action_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --action or -a is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_attach_nic,
                          VM_NAME,
                          call='foo')

    def test_vm_attach_nic_no_data_or_path(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the data and
        path kwargs are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_attach_nic,
                          VM_NAME,
                          call='action')

    def test_vm_deploy_action_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --action or -a is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_deploy,
                          VM_NAME,
                          call='foo')

    def test_vm_deploy_no_host_id_or_host_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the host_id and the
        host_name args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_deploy,
                          VM_NAME,
                          call='action',
                          kwargs=None)

    def test_vm_detach_action_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --action or -a is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_detach,
                          VM_NAME,
                          call='foo')

    def test_vm_detach_no_disk_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the disk_id ar is missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_detach,
                          VM_NAME,
                          call='action')

    def test_vm_detach_nic_action_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --action or -a is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_detach_nic,
                          VM_NAME,
                          call='foo')

    def test_vm_detach_nic_no_nic_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the nic_id arg is missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_detach_nic,
                          VM_NAME,
                          call='action')

    def test_vm_disk_save_action_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --action or -a is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_disk_save,
                          VM_NAME,
                          call='foo')

    def test_vm_disk_save_no_disk_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the disk_id arg is missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_disk_save,
                          VM_NAME,
                          call='action',
                          kwargs={'image_name': 'foo'})

    def test_vm_disk_save_no_image_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the image_name arg is missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_disk_save,
                          VM_NAME,
                          call='action',
                          kwargs={'disk_id': '0'})

    def test_vm_disk_snapshot_create_action_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --action or -a is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_disk_snapshot_create,
                          VM_NAME,
                          call='foo')

    def test_vm_disk_snapshot_create_no_disk_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the disk_id arg is missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_disk_snapshot_create,
                          VM_NAME,
                          call='action',
                          kwargs={'description': 'foo'})

    def test_vm_disk_snapshot_create_no_description(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the image_name arg is missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_disk_snapshot_create,
                          VM_NAME,
                          call='action',
                          kwargs={'disk_id': '0'})

    def test_vm_disk_snapshot_delete_action_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --action or -a is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_disk_snapshot_delete,
                          VM_NAME,
                          call='foo')

    def test_vm_disk_snapshot_delete_no_disk_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the disk_id arg is missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_disk_snapshot_delete,
                          VM_NAME,
                          call='action',
                          kwargs={'snapshot_id': '0'})

    def test_vm_disk_snapshot_delete_no_snapshot_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the snapshot_id arg is missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_disk_snapshot_delete,
                          VM_NAME,
                          call='action',
                          kwargs={'disk_id': '0'})

    def test_vm_disk_snapshot_revert_action_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --action or -a is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_disk_snapshot_revert,
                          VM_NAME,
                          call='foo')

    def test_vm_disk_snapshot_revert_no_disk_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the disk_id arg is missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_disk_snapshot_revert,
                          VM_NAME,
                          call='action',
                          kwargs={'snapshot_id': '0'})

    def test_vm_disk_snapshot_revert_no_snapshot_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the snapshot_id arg is missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_disk_snapshot_revert,
                          VM_NAME,
                          call='action',
                          kwargs={'disk_id': '0'})

    def test_vm_info_action_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --action or -a is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_info,
                          VM_NAME,
                          call='foo')

    def test_vm_migrate_action_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --action or -a is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_migrate,
                          VM_NAME,
                          call='foo')

    def test_vm_migrate_no_datastore_id_or_datastore_name(self):
        '''
        Tests that a SaltCLoudSystemExit is raised when the datastore_id and the
        datastore_name args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_migrate,
                          VM_NAME,
                          call='action',
                          kwargs=None)

    def test_vm_migrate_no_host_id_or_host_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the the host_id and the
        host_name args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_migrate,
                          VM_NAME,
                          call='action',
                          kwargs={'datastore_id': '0'})

    def test_vm_monitoring_action_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --action or -a is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_monitoring,
                          VM_NAME,
                          call='foo')

    def test_vm_resize_action_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --action or -a is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_resize,
                          VM_NAME,
                          call='foo')

    def test_vm_resize_no_data_or_path(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the data and path args
        are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_resize,
                          VM_NAME,
                          call='action',
                          kwargs=None)

    def test_vm_snapshot_create_action_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --action or -a is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_snapshot_create,
                          VM_NAME,
                          call='foo')

    def test_vm_snapshot_create_no_snapshot_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the snapshot_name arg
        is missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_snapshot_create,
                          VM_NAME,
                          call='action',
                          kwargs=None)

    def test_vm_snapshot_delete_action_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --action or -a is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_snapshot_delete,
                          VM_NAME,
                          call='foo')

    def test_vm_snapshot_delete_no_snapshot_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the snapshot_id arg
        is missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_snapshot_delete,
                          VM_NAME,
                          call='action',
                          kwargs=None)

    def test_vm_snapshot_revert_action_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --action or -a is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_snapshot_revert,
                          VM_NAME,
                          call='foo')

    def test_vm_snapshot_revert_no_snapshot_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the snapshot_id arg
        is missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_snapshot_revert,
                          VM_NAME,
                          call='action',
                          kwargs=None)

    def test_vm_update_action_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --action or -a is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_update,
                          VM_NAME,
                          call='foo')

    def test_vm_update_no_update_type(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the update_type arg
        is missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_update,
                          VM_NAME,
                          call='action',
                          kwargs=None)

    def test_vm_update_bad_update_type_value(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the update_type kwarg is
        not a valid value.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_update,
                          VM_NAME,
                          call='action',
                          kwargs={'update_type': 'foo'})

    def test_vm_update_no_data_or_path(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the data and path args
        are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vm_update,
                          VM_NAME,
                          call='action',
                          kwargs={'update_type': 'merge'})

    def test_vn_add_ar_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_add_ar,
                          call='foo')

    def test_vn_add_ar_no_vn_id_or_vn_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the vn_id and vn_name
        args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_add_ar,
                          call='function',
                          kwargs=None)

    def test_vn_add_ar_no_path_or_data(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the path and data
        args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_add_ar,
                          call='function',
                          kwargs={'vn_id': '0'})

    def test_vn_allocate_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_allocate,
                          call='foo')

    def test_vn_allocate_no_data_or_path(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the path and data
        args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_allocate,
                          call='function',
                          kwargs=None)

    def test_vn_delete_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_delete,
                          call='foo')

    def test_vn_delete_no_vn_id_or_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the vn_id and name
        args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_delete,
                          call='function',
                          kwargs=None)

    def test_vn_free_ar_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_free_ar,
                          call='foo')

    def test_vn_free_ar_no_ar_id(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the ar_id is missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_free_ar,
                          call='function',
                          kwargs=None)

    def test_vn_free_ar_no_vn_id_or_vn_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the vn_id and vn_name
        args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_free_ar,
                          call='function',
                          kwargs={'ar_id': '0'})

    def test_vn_hold_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_hold,
                          call='foo')

    def test_vn_hold_no_vn_id_or_vn_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the vn_id and vn_name
        args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_hold,
                          call='function',
                          kwargs=None)

    def test_vn_hold_no_data_or_path(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the data and path
        args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_hold,
                          call='function',
                          kwargs={'vn_id': '0'})

    def test_vn_info_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_info,
                          call='foo')

    def test_vn_info_no_vn_id_or_vn_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the vn_id and vn_name
        args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_info,
                          call='function',
                          kwargs=None)

    def test_vn_release_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_release,
                          call='foo')

    def test_vn_release_no_vn_id_or_vn_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the vn_id and vn_name
        args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_release,
                          call='function',
                          kwargs=None)

    def test_vn_release_no_data_or_path(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the data and path
        args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_release,
                          call='function',
                          kwargs={'vn_id': '0'})

    def test_vn_reserve_function_error(self):
        '''
        Tests that a SaltCloudSystemExit is raised when something other than
        --function or -f is provided.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_reserve,
                          call='foo')

    def test_vn_reserve_no_vn_id_or_vn_name(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the vn_id and vn_name
        args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_reserve,
                          call='function',
                          kwargs=None)

    def test_vn_reserve_no_data_or_path(self):
        '''
        Tests that a SaltCloudSystemExit is raised when the data and path
        args are missing.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula.vn_reserve,
                          call='function',
                          kwargs={'vn_id': '0'})

    @skipIf(not HAS_XML_LIBS, 'cannot find lxml python library')
    def test__get_xml(self):
        '''
        Tests that invalid XML raises SaltCloudSystemExit.
        '''
        self.assertRaises(SaltCloudSystemExit,
                          opennebula._get_xml,
                          "[VirtualMachinePoolInfo] User couldn't be"
                          " authenticated, aborting call.")
