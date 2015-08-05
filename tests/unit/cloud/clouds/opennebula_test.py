# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import MagicMock, NO_MOCK, NO_MOCK_REASON, patch
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../../')

# Import Salt Libs
from salt.cloud.clouds import opennebula
from salt.exceptions import SaltCloudSystemExit

# Import Third Party Libs
try:
    import salt.ext.six.moves.xmlrpc_client  # pylint: disable=E0611,W0611
    from lxml import etree  # pylint: disable=W0611
    HAS_XML_LIBS = True
except ImportError:
    HAS_XML_LIBS = False

# Global Variables
opennebula.__active_provider_name__ = ''
opennebula.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(HAS_XML_LIBS is False, 'The \'lxml\' library is required to run these tests.')
@patch('salt.cloud.clouds.opennebula.__virtual__', MagicMock(return_value='opennebula'))
@patch('salt.cloud.clouds.opennebula._get_xml_rpc',
       MagicMock(return_value=('server', 'user', 'password')))
class OpenNebulaTestCase(TestCase):
    '''
    Unit TestCase for salt.cloud.clouds.opennebula module.
    '''

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
    def test_get_host_id_success(self):
        '''
        Tests that the function returns successfully.
        '''
        mock_id = '100'
        mock_kwargs = {'name': 'test-host'}
        self.assertEqual(opennebula.get_host_id(mock_kwargs, 'foo'),
                         mock_id)

    # TODO: Write tests for get_image function

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
    def test_get_image_id_success(self):
        '''
        Tests that the function returns successfully.
        '''
        mock_id = '100'
        mock_kwargs = {'name': 'test-image'}
        self.assertEqual(opennebula.get_image_id(mock_kwargs, 'foo'),
                         mock_id)

    # TODO: Write tests for get_location function

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
    def test_get_vn_id_success(self):
        '''
        Tests that the function returns successfully.
        '''
        mock_id = '100'
        mock_kwargs = {'name': 'test-vn'}
        self.assertEqual(opennebula.get_vn_id(mock_kwargs, 'foo'),
                         mock_id)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(OpenNebulaTestCase, needs_daemon=False)
