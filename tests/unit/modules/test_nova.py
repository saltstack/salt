"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import salt.modules.nova as nova
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class NovaTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.nova
    """

    def setup_loader_modules(self):
        patcher = patch("salt.modules.nova._auth")
        self.mock_auth = patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(delattr, self, "mock_auth")
        return {nova: {}}

    def test_boot(self):
        """
        Test for Boot (create) a new instance
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "boot", MagicMock(return_value="A")):
            self.assertTrue(nova.boot("name"))

    def test_volume_list(self):
        """
        Test for List storage volumes
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "volume_list", MagicMock(return_value="A")):
            self.assertTrue(nova.volume_list())

    def test_volume_show(self):
        """
        Test for Create a block storage volume
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "volume_show", MagicMock(return_value="A")):
            self.assertTrue(nova.volume_show("name"))

    def test_volume_create(self):
        """
        Test for Create a block storage volume
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "volume_create", MagicMock(return_value="A")):
            self.assertTrue(nova.volume_create("name"))

    def test_volume_delete(self):
        """
        Test for Destroy the volume
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "volume_delete", MagicMock(return_value="A")):
            self.assertTrue(nova.volume_delete("name"))

    def test_volume_detach(self):
        """
        Test for Attach a block storage volume
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "volume_detach", MagicMock(return_value="A")):
            self.assertTrue(nova.volume_detach("name"))

    def test_volume_attach(self):
        """
        Test for Attach a block storage volume
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "volume_attach", MagicMock(return_value="A")):
            self.assertTrue(nova.volume_attach("name", "serv_name"))

    def test_suspend(self):
        """
        Test for Suspend an instance
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "suspend", MagicMock(return_value="A")):
            self.assertTrue(nova.suspend("instance_id"))

    def test_resume(self):
        """
        Test for Resume an instance
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "resume", MagicMock(return_value="A")):
            self.assertTrue(nova.resume("instance_id"))

    def test_lock(self):
        """
        Test for Lock an instance
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "lock", MagicMock(return_value="A")):
            self.assertTrue(nova.lock("instance_id"))

    def test_delete(self):
        """
        Test for Delete an instance
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "delete", MagicMock(return_value="A")):
            self.assertTrue(nova.delete("instance_id"))

    def test_flavor_list(self):
        """
        Test for Return a list of available flavors (nova flavor-list)
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "flavor_list", MagicMock(return_value="A")):
            self.assertTrue(nova.flavor_list())

    def test_flavor_create(self):
        """
        Test for Add a flavor to nova (nova flavor-create)
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "flavor_create", MagicMock(return_value="A")):
            self.assertTrue(nova.flavor_create("name"))

    def test_flavor_delete(self):
        """
        Test for Delete a flavor from nova by id (nova flavor-delete)
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "flavor_delete", MagicMock(return_value="A")):
            self.assertTrue(nova.flavor_delete("flavor_id"))

    def test_keypair_list(self):
        """
        Test for Return a list of available keypairs (nova keypair-list)
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "keypair_list", MagicMock(return_value="A")):
            self.assertTrue(nova.keypair_list())

    def test_keypair_add(self):
        """
        Test for Add a keypair to nova (nova keypair-add)
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "keypair_add", MagicMock(return_value="A")):
            self.assertTrue(nova.keypair_add("name"))

    def test_keypair_delete(self):
        """
        Test for Add a keypair to nova (nova keypair-delete)
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(
            self.mock_auth, "keypair_delete", MagicMock(return_value="A")
        ):
            self.assertTrue(nova.keypair_delete("name"))

    def test_image_list(self):
        """
        Test for Return a list of available images
         (nova images-list + nova image-show)
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "image_list", MagicMock(return_value="A")):
            self.assertTrue(nova.image_list())

    def test_image_meta_set(self):
        """
        Test for Sets a key=value pair in the
         metadata for an image (nova image-meta set)
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(
            self.mock_auth, "image_meta_set", MagicMock(return_value="A")
        ):
            self.assertTrue(nova.image_meta_set())

    def test_image_meta_delete(self):
        """
        Test for Delete a key=value pair from the metadata for an image
        (nova image-meta set)
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(
            self.mock_auth, "image_meta_delete", MagicMock(return_value="A")
        ):
            self.assertTrue(nova.image_meta_delete())

    def test_list_(self):
        """
        Test for To maintain the feel of the nova command line,
         this function simply calls
         the server_list function.
        """
        with patch.object(nova, "server_list", return_value=["A"]):
            self.assertEqual(nova.list_(), ["A"])

    def test_server_list(self):
        """
        Test for Return list of active servers
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "server_list", MagicMock(return_value="A")):
            self.assertTrue(nova.server_list())

    def test_show(self):
        """
        Test for To maintain the feel of the nova command line,
         this function simply calls
         the server_show function.
        """
        with patch.object(nova, "server_show", return_value=["A"]):
            self.assertEqual(nova.show("server_id"), ["A"])

    def test_server_list_detailed(self):
        """
        Test for Return detailed list of active servers
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(
            self.mock_auth, "server_list_detailed", MagicMock(return_value="A")
        ):
            self.assertTrue(nova.server_list_detailed())

    def test_server_show(self):
        """
        Test for Return detailed information for an active server
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "server_show", MagicMock(return_value="A")):
            self.assertTrue(nova.server_show("serv_id"))

    def test_secgroup_create(self):
        """
        Test for Add a secgroup to nova (nova secgroup-create)
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(
            self.mock_auth, "server_list_detailed", MagicMock(return_value="A")
        ):
            self.assertTrue(nova.secgroup_create("name", "desc"))

    def test_secgroup_delete(self):
        """
        Test for Delete a secgroup to nova (nova secgroup-delete)
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(
            self.mock_auth, "secgroup_delete", MagicMock(return_value="A")
        ):
            self.assertTrue(nova.secgroup_delete("name"))

    def test_secgroup_list(self):
        """
        Test for Return a list of available security groups (nova items-list)
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(self.mock_auth, "secgroup_list", MagicMock(return_value="A")):
            self.assertTrue(nova.secgroup_list())

    def test_server_by_name(self):
        """
        Test for Return information about a server
        """
        self.mock_auth.side_effect = MagicMock()
        with patch.object(
            self.mock_auth, "server_by_name", MagicMock(return_value="A")
        ):
            self.assertTrue(nova.server_by_name("name"))
