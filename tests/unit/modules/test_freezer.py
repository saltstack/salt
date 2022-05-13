"""
:maintainer:    Alberto Planas <aplanas@suse.com>
:platform:      Linux
"""


import salt.modules.freezer as freezer
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class FreezerTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.freezer
    """

    def setup_loader_modules(self):
        return {freezer: {"__salt__": {}, "__opts__": {"cachedir": ""}}}

    @patch("os.path.isfile")
    def test_status(self, isfile):
        """
        Test if a frozen state exist.
        """
        isfile.side_effect = (True, True)
        self.assertTrue(freezer.status())

        isfile.side_effect = (True, False)
        self.assertFalse(freezer.status())

    @patch("os.listdir")
    @patch("os.path.isdir")
    def test_list(self, isdir, listdir):
        """
        Test the listing of all frozen states.
        """
        # There is no freezer directory
        isdir.return_value = False
        self.assertEqual(freezer.list_(), [])

        # There is freezer directory, but is empty
        isdir.return_value = True
        listdir.return_value = []
        self.assertEqual(freezer.list_(), [])

        # There is freezer directory with states
        isdir.return_value = True
        listdir.return_value = [
            "freezer-pkgs.yml",
            "freezer-reps.yml",
            "state-pkgs.yml",
            "state-reps.yml",
            "random-file",
        ]
        self.assertEqual(freezer.list_(), ["freezer", "state"])

    @patch("os.makedirs")
    def test_freeze_fails_cache(self, makedirs):
        """
        Test to freeze a current installation
        """
        # Fails when creating the freeze cache directory
        makedirs.side_effect = OSError()
        self.assertRaises(CommandExecutionError, freezer.freeze)

    @patch("salt.modules.freezer.status")
    @patch("os.makedirs")
    def test_freeze_fails_already_frozen(self, makedirs, status):
        """
        Test to freeze a current installation
        """
        # Fails when there is already a frozen state
        status.return_value = True
        self.assertRaises(CommandExecutionError, freezer.freeze)
        makedirs.assert_called_once()

    @patch("salt.utils.json.dump")
    @patch("salt.modules.freezer.fopen")
    @patch("salt.modules.freezer.status")
    @patch("os.makedirs")
    def test_freeze_success_two_freeze(self, makedirs, status, fopen, dump):
        """
        Test to freeze a current installation
        """
        # Freeze the current new state
        status.return_value = False
        salt_mock = {
            "pkg.list_pkgs": MagicMock(return_value={}),
            "pkg.list_repos": MagicMock(return_value={}),
        }
        with patch.dict(freezer.__salt__, salt_mock):
            self.assertTrue(freezer.freeze("one"))
            self.assertTrue(freezer.freeze("two"))

            self.assertEqual(makedirs.call_count, 2)
            self.assertEqual(salt_mock["pkg.list_pkgs"].call_count, 2)
            self.assertEqual(salt_mock["pkg.list_repos"].call_count, 2)
            fopen.assert_called()
            dump.assert_called()

    @patch("salt.utils.json.dump")
    @patch("salt.modules.freezer.fopen")
    @patch("salt.modules.freezer.status")
    @patch("os.makedirs")
    def test_freeze_success_new_state(self, makedirs, status, fopen, dump):
        """
        Test to freeze a current installation
        """
        # Freeze the current new state
        status.return_value = False
        salt_mock = {
            "pkg.list_pkgs": MagicMock(return_value={}),
            "pkg.list_repos": MagicMock(return_value={}),
        }
        with patch.dict(freezer.__salt__, salt_mock):
            self.assertTrue(freezer.freeze())
            makedirs.assert_called_once()
            salt_mock["pkg.list_pkgs"].assert_called_once()
            salt_mock["pkg.list_repos"].assert_called_once()
            fopen.assert_called()
            dump.assert_called()

    @patch("salt.utils.json.dump")
    @patch("salt.modules.freezer.fopen")
    @patch("salt.modules.freezer.status")
    @patch("os.makedirs")
    def test_freeze_success_force(self, makedirs, status, fopen, dump):
        """
        Test to freeze a current installation
        """
        # Freeze the current old state
        status.return_value = True
        salt_mock = {
            "pkg.list_pkgs": MagicMock(return_value={}),
            "pkg.list_repos": MagicMock(return_value={}),
        }
        with patch.dict(freezer.__salt__, salt_mock):
            self.assertTrue(freezer.freeze(force=True))
            makedirs.assert_called_once()
            salt_mock["pkg.list_pkgs"].assert_called_once()
            salt_mock["pkg.list_repos"].assert_called_once()
            fopen.assert_called()
            dump.assert_called()

    @patch("salt.modules.freezer.status")
    def test_restore_fails_missing_state(self, status):
        """
        Test to restore an old state
        """
        # Fails if the state is not found
        status.return_value = False
        self.assertRaises(CommandExecutionError, freezer.restore)

    @patch("salt.utils.json.load")
    @patch("salt.modules.freezer.fopen")
    @patch("salt.modules.freezer.status")
    def test_restore_add_missing_repo(self, status, fopen, load):
        """
        Test to restore an old state
        """
        # Only a missing repo is installed
        status.return_value = True
        load.side_effect = ({}, {"missing-repo": {}})
        salt_mock = {
            "pkg.list_pkgs": MagicMock(return_value={}),
            "pkg.list_repos": MagicMock(return_value={}),
            "pkg.mod_repo": MagicMock(),
        }
        with patch.dict(freezer.__salt__, salt_mock):
            self.assertEqual(
                freezer.restore(),
                {
                    "pkgs": {"add": [], "remove": []},
                    "repos": {"add": ["missing-repo"], "remove": []},
                    "comment": [],
                },
            )
            salt_mock["pkg.list_pkgs"].assert_called()
            salt_mock["pkg.list_repos"].assert_called()
            salt_mock["pkg.mod_repo"].assert_called_once()
            fopen.assert_called()
            load.assert_called()

    @patch("salt.utils.json.load")
    @patch("salt.modules.freezer.fopen")
    @patch("salt.modules.freezer.status")
    def test_restore_add_missing_package(self, status, fopen, load):
        """
        Test to restore an old state
        """
        # Only a missing package is installed
        status.return_value = True
        load.side_effect = ({"missing-package": {}}, {})
        salt_mock = {
            "pkg.list_pkgs": MagicMock(return_value={}),
            "pkg.list_repos": MagicMock(return_value={}),
            "pkg.install": MagicMock(),
        }
        with patch.dict(freezer.__salt__, salt_mock):
            self.assertEqual(
                freezer.restore(),
                {
                    "pkgs": {"add": ["missing-package"], "remove": []},
                    "repos": {"add": [], "remove": []},
                    "comment": [],
                },
            )
            salt_mock["pkg.list_pkgs"].assert_called()
            salt_mock["pkg.list_repos"].assert_called()
            salt_mock["pkg.install"].assert_called_once()
            fopen.assert_called()
            load.assert_called()

    @patch("salt.utils.json.load")
    @patch("salt.modules.freezer.fopen")
    @patch("salt.modules.freezer.status")
    def test_restore_remove_extra_package(self, status, fopen, load):
        """
        Test to restore an old state
        """
        # Only an extra package is removed
        status.return_value = True
        load.side_effect = ({}, {})
        salt_mock = {
            "pkg.list_pkgs": MagicMock(return_value={"extra-package": {}}),
            "pkg.list_repos": MagicMock(return_value={}),
            "pkg.remove": MagicMock(),
        }
        with patch.dict(freezer.__salt__, salt_mock):
            self.assertEqual(
                freezer.restore(),
                {
                    "pkgs": {"add": [], "remove": ["extra-package"]},
                    "repos": {"add": [], "remove": []},
                    "comment": [],
                },
            )
            salt_mock["pkg.list_pkgs"].assert_called()
            salt_mock["pkg.list_repos"].assert_called()
            salt_mock["pkg.remove"].assert_called_once()
            fopen.assert_called()
            load.assert_called()

    @patch("salt.utils.json.load")
    @patch("salt.modules.freezer.fopen")
    @patch("salt.modules.freezer.status")
    def test_restore_remove_extra_repo(self, status, fopen, load):
        """
        Test to restore an old state
        """
        # Only an extra repository is removed
        status.return_value = True
        load.side_effect = ({}, {})
        salt_mock = {
            "pkg.list_pkgs": MagicMock(return_value={}),
            "pkg.list_repos": MagicMock(return_value={"extra-repo": {}}),
            "pkg.del_repo": MagicMock(),
        }
        with patch.dict(freezer.__salt__, salt_mock):
            self.assertEqual(
                freezer.restore(),
                {
                    "pkgs": {"add": [], "remove": []},
                    "repos": {"add": [], "remove": ["extra-repo"]},
                    "comment": [],
                },
            )
            salt_mock["pkg.list_pkgs"].assert_called()
            salt_mock["pkg.list_repos"].assert_called()
            salt_mock["pkg.del_repo"].assert_called_once()
            fopen.assert_called()
            load.assert_called()

    @patch("os.remove")
    @patch("salt.utils.json.load")
    @patch("salt.modules.freezer.fopen")
    @patch("salt.modules.freezer.status")
    def test_restore_clean_yml(self, status, fopen, load, remove):
        """
        Test to restore an old state
        """
        status.return_value = True
        salt_mock = {
            "pkg.list_pkgs": MagicMock(return_value={}),
            "pkg.list_repos": MagicMock(return_value={}),
            "pkg.install": MagicMock(),
        }
        with patch.dict(freezer.__salt__, salt_mock):
            self.assertEqual(
                freezer.restore(clean=True),
                {
                    "pkgs": {"add": [], "remove": []},
                    "repos": {"add": [], "remove": []},
                    "comment": [],
                },
            )
            salt_mock["pkg.list_pkgs"].assert_called()
            salt_mock["pkg.list_repos"].assert_called()
            fopen.assert_called()
            load.assert_called()
            self.assertEqual(remove.call_count, 2)
