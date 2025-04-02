import pytest

from tests.support.case import ModuleCase

@pytest.mark.destructive_test
class FlatpakModuleTest(ModuleCase):
    """
    Validate the flatpak module
    """

    def setUp(self):
        """
        Prepare variables
        """
        super().setUp()
        self._package = "org.gimp.GIMP"
        self._remote = "flathub"
        self._repo = "https://flathub.org/repo/flathub.flatpakrepo"

    def tearDown(self):
        """
        Ensure that no packages/remotes that were installed/added for testing remain on the system
        """
        self.run_function("flatpak.uninstall", [self._package])
        self.run_function("flatpak.delete_remote", [self._remote])

    @pytest.mark.destructive_test
    def test_install(self):
        """
        Test the function to install a flatpak package
        """
        # install a flatpak package
        ret = self.run_function("flatpak.install", [self._package, self._remote])
        self.assertTrue(ret["result"])
        # validate the installation
        self.assertTrue(self.run_function("flatpak.is_installed", [self._package]))

    @pytest.mark.destructive_test
    def test_uninstall(self):
        """
        Test the function to uninstall a flatpak package
        """
        # install a flatpak package to have something to uninstall
        self.run_function("flatpak.install", [self._package, self._remote])
        # uninstall the flatpak package
        ret = self.run_function("flatpak.uninstall", [self._package])
        self.assertTrue(ret["result"])
        # validate the uninstallation
        self.assertFalse(self.run_function("flatpak.is_installed", [self._package]))

    @pytest.mark.destructive_test
    def test_add_remote(self):
        """
        Test the function to add a flatpak remote
        """
        # add a flatpak remote
        ret = self.run_function("flatpak.add_remote", [self._remote, self._repo])
        self.assertTrue(ret["result"])
        # validate the addition
        self.assertTrue(self.run_function("flatpak.is_remote_added", [self._remote]))

    @pytest.mark.destructive_test
    def test_delete_remote(self):
        """
        Test the function to delete a flatpak remote
        """
        # add a flatpak remote to have something to delete
        self.run_function("flatpak.add_remote", [self._remote, self._repo])
        # delete the flatpak remote
        ret = self.run_function("flatpak.delete_remote", [self._remote])
        self.assertTrue(ret["result"])
        # validate the deletion
        self.assertFalse(self.run_function("flatpak.is_remote_added", [self._remote]))

    @pytest.mark.destructive_test
    def test_remotes_info(self):
        """
        Test the function to get info about all remotes
        """
        # add a flatpak remote to have something to get info about
        self.run_function("flatpak.add_remote", [self._remote, self._repo])
        ret = self.run_function("flatpak.remotes_info")
        self.assertTrue(len(ret) > 0)
        remoteInfo = ret[0]
        # check if the dict has all the expected keys and if any of them are None
        attrs = ["name", "title", "url", "filter", "collection", "priority", "options", "comment", "description", "homepage", "icon"]
        for attr in attrs:
            self.assertIn(attr, remoteInfo)
            self.assertIsNotNone(remoteInfo[attr])

    @pytest.mark.destructive_test
    def test_modify_remote(self):
        """
        Test the function to modify the attributes of a flatpak remote
        """
        # add a flatpak remote
        self.run_function("flatpak.add_remote", [self._remote])
        # we will change the "title" attribute of the remote to this value
        newTitle = "Foobar remote"
        self.assertNotEqual(self.run_function("flatpak.remote_info", [self._remote])["title"], newTitle)
        # modify the remote to set a new "title" attribute
        ret = self.run_function("flatpak.modify_remote", [self._remote], title=newTitle)
        self.assertTrue(ret["result"])
        # validate the change
        self.assertEqual(self.run_function("flatpak.remote_info", [self._remote])["title"], newTitle)
