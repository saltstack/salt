# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import nova

# Globals
nova.__grains__ = {}
nova.__salt__ = {}
nova.__context__ = {}
nova.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NovaTestCase(TestCase):
    '''
    Test cases for salt.modules.nova
    '''
    @patch('salt.modules.nova._auth')
    def test_boot(self, mock_auth):
        '''
        Test for Boot (create) a new instance
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'boot', MagicMock(return_value='A')):
            self.assertTrue(nova.boot('name'))

    @patch('salt.modules.nova._auth')
    def test_volume_list(self, mock_auth):
        '''
        Test for List storage volumes
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'volume_list', MagicMock(return_value='A')):
            self.assertTrue(nova.volume_list())

    @patch('salt.modules.nova._auth')
    def test_volume_show(self, mock_auth):
        '''
        Test for Create a block storage volume
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'volume_show', MagicMock(return_value='A')):
            self.assertTrue(nova.volume_show('name'))

    @patch('salt.modules.nova._auth')
    def test_volume_create(self, mock_auth):
        '''
        Test for Create a block storage volume
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'volume_create', MagicMock(return_value='A')):
            self.assertTrue(nova.volume_create('name'))

    @patch('salt.modules.nova._auth')
    def test_volume_delete(self, mock_auth):
        '''
        Test for Destroy the volume
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'volume_delete', MagicMock(return_value='A')):
            self.assertTrue(nova.volume_delete('name'))

    @patch('salt.modules.nova._auth')
    def test_volume_detach(self, mock_auth):
        '''
        Test for Attach a block storage volume
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'volume_detach', MagicMock(return_value='A')):
            self.assertTrue(nova.volume_detach('name'))

    @patch('salt.modules.nova._auth')
    def test_volume_attach(self, mock_auth):
        '''
        Test for Attach a block storage volume
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'volume_attach', MagicMock(return_value='A')):
            self.assertTrue(nova.volume_attach('name', 'serv_name'))

    @patch('salt.modules.nova._auth')
    def test_suspend(self, mock_auth):
        '''
        Test for Suspend an instance
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'suspend', MagicMock(return_value='A')):
            self.assertTrue(nova.suspend('instance_id'))

    @patch('salt.modules.nova._auth')
    def test_resume(self, mock_auth):
        '''
        Test for Resume an instance
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'resume', MagicMock(return_value='A')):
            self.assertTrue(nova.resume('instance_id'))

    @patch('salt.modules.nova._auth')
    def test_lock(self, mock_auth):
        '''
        Test for Lock an instance
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'lock', MagicMock(return_value='A')):
            self.assertTrue(nova.lock('instance_id'))

    @patch('salt.modules.nova._auth')
    def test_delete(self, mock_auth):
        '''
        Test for Delete an instance
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'delete', MagicMock(return_value='A')):
            self.assertTrue(nova.delete('instance_id'))

    @patch('salt.modules.nova._auth')
    def test_flavor_list(self, mock_auth):
        '''
        Test for Return a list of available flavors (nova flavor-list)
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'flavor_list', MagicMock(return_value='A')):
            self.assertTrue(nova.flavor_list())

    @patch('salt.modules.nova._auth')
    def test_flavor_create(self, mock_auth):
        '''
        Test for Add a flavor to nova (nova flavor-create)
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'flavor_create', MagicMock(return_value='A')):
            self.assertTrue(nova.flavor_create('name'))

    @patch('salt.modules.nova._auth')
    def test_flavor_delete(self, mock_auth):
        '''
        Test for Delete a flavor from nova by id (nova flavor-delete)
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'flavor_delete', MagicMock(return_value='A')):
            self.assertTrue(nova.flavor_delete('flavor_id'))

    @patch('salt.modules.nova._auth')
    def test_keypair_list(self, mock_auth):
        '''
        Test for Return a list of available keypairs (nova keypair-list)
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'keypair_list', MagicMock(return_value='A')):
            self.assertTrue(nova.keypair_list())

    @patch('salt.modules.nova._auth')
    def test_keypair_add(self, mock_auth):
        '''
        Test for Add a keypair to nova (nova keypair-add)
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'keypair_add', MagicMock(return_value='A')):
            self.assertTrue(nova.keypair_add('name'))

    @patch('salt.modules.nova._auth')
    def test_keypair_delete(self, mock_auth):
        '''
        Test for Add a keypair to nova (nova keypair-delete)
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'keypair_delete', MagicMock(return_value='A')):
            self.assertTrue(nova.keypair_delete('name'))

    @patch('salt.modules.nova._auth')
    def test_image_list(self, mock_auth):
        '''
        Test for Return a list of available images
         (nova images-list + nova image-show)
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'image_list', MagicMock(return_value='A')):
            self.assertTrue(nova.image_list())

    @patch('salt.modules.nova._auth')
    def test_image_meta_set(self, mock_auth):
        '''
        Test for Sets a key=value pair in the
         metadata for an image (nova image-meta set)
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'image_meta_set', MagicMock(return_value='A')):
            self.assertTrue(nova.image_meta_set())

    @patch('salt.modules.nova._auth')
    def test_image_meta_delete(self, mock_auth):
        '''
        Test for Delete a key=value pair from the metadata for an image
        (nova image-meta set)
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'image_meta_delete', MagicMock(return_value='A')):
            self.assertTrue(nova.image_meta_delete())

    def test_list_(self):
        '''
        Test for To maintain the feel of the nova command line,
         this function simply calls
         the server_list function.
         '''
        with patch.object(nova, 'server_list', return_value=['A']):
            self.assertEqual(nova.list_(), ['A'])

    @patch('salt.modules.nova._auth')
    def test_server_list(self, mock_auth):
        '''
        Test for Return list of active servers
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'server_list', MagicMock(return_value='A')):
            self.assertTrue(nova.server_list())

    def test_show(self):
        '''
        Test for To maintain the feel of the nova command line,
         this function simply calls
         the server_show function.
         '''
        with patch.object(nova, 'server_show', return_value=['A']):
            self.assertEqual(nova.show('server_id'), ['A'])

    @patch('salt.modules.nova._auth')
    def test_server_list_detailed(self, mock_auth):
        '''
        Test for Return detailed list of active servers
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'server_list_detailed', MagicMock(return_value='A')):
            self.assertTrue(nova.server_list_detailed())

    @patch('salt.modules.nova._auth')
    def test_server_show(self, mock_auth):
        '''
        Test for Return detailed information for an active server
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'server_show', MagicMock(return_value='A')):
            self.assertTrue(nova.server_show('serv_id'))

    @patch('salt.modules.nova._auth')
    def test_secgroup_create(self, mock_auth):
        '''
        Test for Add a secgroup to nova (nova secgroup-create)
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'server_list_detailed', MagicMock(return_value='A')):
            self.assertTrue(nova.secgroup_create('name', 'desc'))

    @patch('salt.modules.nova._auth')
    def test_secgroup_delete(self, mock_auth):
        '''
        Test for Delete a secgroup to nova (nova secgroup-delete)
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'secgroup_delete', MagicMock(return_value='A')):
            self.assertTrue(nova.secgroup_delete('name'))

    @patch('salt.modules.nova._auth')
    def test_secgroup_list(self, mock_auth):
        '''
        Test for Return a list of available security groups (nova items-list)
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'secgroup_list', MagicMock(return_value='A')):
            self.assertTrue(nova.secgroup_list())

    @patch('salt.modules.nova._auth')
    def test_server_by_name(self, mock_auth):
        '''
        Test for Return information about a server
        '''
        mock_auth.side_effect = MagicMock()
        with patch.object(mock_auth,
                          'server_by_name', MagicMock(return_value='A')):
            self.assertTrue(nova.server_by_name('name'))
