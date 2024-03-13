"""
    :synopsis: Unit Tests for Package Management module 'module.opkg'
    :platform: Linux
"""

import collections
import copy
import os
import textwrap

import pytest

import salt.modules.opkg as opkg
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, mock_open, patch
from tests.support.unit import TestCase


@pytest.mark.skip_unless_on_linux
class OpkgTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.opkg
    """

    @classmethod
    def setUpClass(cls):
        cls.opkg_vim_info = {
            "vim": {
                "Package": "vim",
                "Version": "7.4.769-r0.31",
                "Status": "install ok installed",
            }
        }
        cls.opkg_vim_files = {
            "errors": [],
            "packages": {
                "vim": [
                    "/usr/bin/view",
                    "/usr/bin/vim.vim",
                    "/usr/bin/xxd",
                    "/usr/bin/vimdiff",
                    "/usr/bin/rview",
                    "/usr/bin/rvim",
                    "/usr/bin/ex",
                ]
            },
        }
        cls.installed = {"vim": {"new": "7.4", "old": ""}}
        cls.removed = {"vim": {"new": "", "old": "7.4"}}
        cls.packages = {"vim": "7.4"}

    @classmethod
    def tearDownClass(cls):
        cls.opkg_vim_info = cls.opkg_vim_files = cls.installed = cls.removed = (
            cls.packages
        ) = None

    def setup_loader_modules(self):  # pylint: disable=no-self-use
        """
        Tested modules
        """
        return {opkg: {}}

    def test_virtual_ni_linux_rt_system(self):
        """
        Test - Module virtual name on NI Linux RT
        """
        with patch.dict(opkg.__grains__, {"os_family": "NILinuxRT"}):
            with patch.object(os, "makedirs", MagicMock(return_value=True)):
                with patch.object(os, "listdir", MagicMock(return_value=[])):
                    with patch.object(opkg, "_update_nilrt_restart_state", MagicMock()):
                        self.assertEqual("pkg", opkg.__virtual__())

    def test_virtual_open_embedded_system(self):
        """
        Test - Module virtual name on Open Embedded
        """
        with patch.object(os.path, "isdir", MagicMock(return_value=True)):
            self.assertEqual("pkg", opkg.__virtual__())

    def test_virtual_not_supported_system(self):
        """
        Test - Module not supported
        """
        with patch.object(os.path, "isdir", MagicMock(return_value=False)):
            expected = (False, "Module opkg only works on OpenEmbedded based systems")
            self.assertEqual(expected, opkg.__virtual__())

    def test_virtual_update_restart_state_called(self):
        """
        Test - Update restart state is called when empty dir
        """
        mock_cmd = MagicMock()
        with patch.dict(opkg.__grains__, {"os_family": "NILinuxRT"}):
            with patch.object(os, "makedirs", MagicMock(return_value=True)):
                with patch.object(os, "listdir", MagicMock(return_value=[])):
                    with patch.object(opkg, "_update_nilrt_restart_state", mock_cmd):
                        opkg.__virtual__()
                        mock_cmd.assert_called_once()

    def test_virtual_update_restart_state_not_called(self):
        """
        Test - Update restart state is not called when dir contains files
        """
        mock_cmd = MagicMock()
        with patch.dict(opkg.__grains__, {"os_family": "NILinuxRT"}):
            with patch.object(os, "makedirs", MagicMock(return_value=True)):
                with patch.object(os, "listdir", MagicMock(return_value=["test"])):
                    with patch.object(opkg, "_update_nilrt_restart_state", mock_cmd):
                        opkg.__virtual__()
                        mock_cmd.assert_not_called()

    def test_version(self):
        """
        Test - Returns a string representing the package version or an empty string if
        not installed.
        """
        version = self.opkg_vim_info["vim"]["Version"]
        mock = MagicMock(return_value=version)
        with patch.dict(opkg.__salt__, {"pkg_resource.version": mock}):
            self.assertEqual(opkg.version(*["vim"]), version)

    def test_upgrade_available(self):
        """
        Test - Check whether or not an upgrade is available for a given package.
        """
        with patch("salt.modules.opkg.latest_version", MagicMock(return_value="")):
            self.assertFalse(opkg.upgrade_available("vim"))

    def test_file_dict(self):
        """
        Test - List the files that belong to a package, grouped by package.
        """
        std_out = "\n".join(self.opkg_vim_files["packages"]["vim"])
        ret_value = {"stdout": std_out}
        mock = MagicMock(return_value=ret_value)
        with patch.dict(opkg.__salt__, {"cmd.run_all": mock}):
            self.assertEqual(opkg.file_dict("vim"), self.opkg_vim_files)

    def test_file_list(self):
        """
        Test - List the files that belong to a package.
        """
        std_out = "\n".join(self.opkg_vim_files["packages"]["vim"])
        ret_value = {"stdout": std_out}
        mock = MagicMock(return_value=ret_value)
        files = {
            "errors": self.opkg_vim_files["errors"],
            "files": self.opkg_vim_files["packages"]["vim"],
        }
        with patch.dict(opkg.__salt__, {"cmd.run_all": mock}):
            self.assertEqual(opkg.file_list("vim"), files)

    def test_owner(self):
        """
        Test - Return the name of the package that owns the file.
        """
        paths = ["/usr/bin/vimdiff"]
        mock = MagicMock(return_value="vim - version - info")
        with patch.dict(opkg.__salt__, {"cmd.run_stdout": mock}):
            self.assertEqual(opkg.owner(*paths), "vim")

    def test_install(self):
        """
        Test - Install packages.
        """
        with patch(
            "salt.modules.opkg.list_pkgs", MagicMock(side_effect=[{}, self.packages])
        ):
            ret_value = {"retcode": 0}
            mock = MagicMock(return_value=ret_value)
            patch_kwargs = {
                "__salt__": {
                    "cmd.run_all": mock,
                    "pkg_resource.parse_targets": MagicMock(
                        return_value=({"vim": "7.4"}, "repository")
                    ),
                    "restartcheck.restartcheck": MagicMock(
                        return_value="No packages seem to need to be restarted"
                    ),
                }
            }
            with patch.multiple(opkg, **patch_kwargs):
                self.assertEqual(opkg.install("vim:7.4"), self.installed)

    def test_install_noaction(self):
        """
        Test - Install packages.
        """
        with patch("salt.modules.opkg.list_pkgs", MagicMock(side_effect=({}, {}))):
            std_out = (
                "Downloading"
                " http://feedserver/feeds/test/vim_7.4_arch.ipk.\n\nInstalling vim"
                " (7.4) on root\n"
            )
            ret_value = {"retcode": 0, "stdout": std_out}
            mock = MagicMock(return_value=ret_value)
            patch_kwargs = {
                "__salt__": {
                    "cmd.run_all": mock,
                    "pkg_resource.parse_targets": MagicMock(
                        return_value=({"vim": "7.4"}, "repository")
                    ),
                    "restartcheck.restartcheck": MagicMock(
                        return_value="No packages seem to need to be restarted"
                    ),
                }
            }
            with patch.multiple(opkg, **patch_kwargs):
                self.assertEqual(opkg.install("vim:7.4", test=True), self.installed)

    def test_remove(self):
        """
        Test - Remove packages.
        """
        with patch(
            "salt.modules.opkg.list_pkgs", MagicMock(side_effect=[self.packages, {}])
        ):
            ret_value = {"retcode": 0}
            mock = MagicMock(return_value=ret_value)
            patch_kwargs = {
                "__salt__": {
                    "cmd.run_all": mock,
                    "pkg_resource.parse_targets": MagicMock(
                        return_value=({"vim": "7.4"}, "repository")
                    ),
                    "restartcheck.restartcheck": MagicMock(
                        return_value="No packages seem to need to be restarted"
                    ),
                }
            }
            with patch.multiple(opkg, **patch_kwargs):
                self.assertEqual(opkg.remove("vim"), self.removed)

    def test_remove_noaction(self):
        """
        Test - Remove packages.
        """
        with patch(
            "salt.modules.opkg.list_pkgs",
            MagicMock(side_effect=[self.packages, self.packages]),
        ):
            std_out = "\nRemoving vim (7.4) from root...\n"
            ret_value = {"retcode": 0, "stdout": std_out}
            mock = MagicMock(return_value=ret_value)
            patch_kwargs = {
                "__salt__": {
                    "cmd.run_all": mock,
                    "pkg_resource.parse_targets": MagicMock(
                        return_value=({"vim": "7.4"}, "repository")
                    ),
                    "restartcheck.restartcheck": MagicMock(
                        return_value="No packages seem to need to be restarted"
                    ),
                }
            }
            with patch.multiple(opkg, **patch_kwargs):
                self.assertEqual(opkg.remove("vim:7.4", test=True), self.removed)

    def test_info_installed(self):
        """
        Test - Return the information of the named package(s) installed on the system.
        """
        installed = copy.deepcopy(self.opkg_vim_info["vim"])
        del installed["Package"]
        ordered_info = collections.OrderedDict(sorted(installed.items()))
        expected_dict = {"vim": {k.lower(): v for k, v in ordered_info.items()}}
        std_out = "\n".join(
            [k + ": " + v for k, v in self.opkg_vim_info["vim"].items()]
        )
        ret_value = {"stdout": std_out, "retcode": 0}
        mock = MagicMock(return_value=ret_value)
        with patch.dict(opkg.__salt__, {"cmd.run_all": mock}):
            self.assertEqual(opkg.info_installed("vim"), expected_dict)

    def test_version_clean(self):
        """
        Test - Return the information of version_clean
        """
        self.assertEqual(opkg.version_clean("1.0.1"), "1.0.1")

    def test_check_extra_requirements(self):
        """
        Test - Return the information of check_extra_requirements
        """
        self.assertEqual(opkg.check_extra_requirements("vim", "1.0.1"), True)

    def _get_repo(self, enabled, compressed, name, uri, file, trusted=None):
        feed = {
            "enabled": enabled,
            "compressed": compressed,
            "name": name,
            "uri": uri,
            "file": file,
        }
        if trusted is not None:
            feed["trusted"] = trusted
        return feed

    def test_list_repos(self):
        feeds_content = textwrap.dedent(
            """\
            src/gz   name1     url1
            src   name2     url2
            #src/gz   name3     url3
            src/gz   name4     url4 [trusted=yes]
            src/gz   "name5 space"    url5 [trusted=no]
            """
        )
        expected_feed1 = self._get_repo(
            True, True, "name1", "url1", "/etc/opkg/test.conf"
        )
        expected_feed2 = self._get_repo(
            True, False, "name2", "url2", "/etc/opkg/test.conf"
        )
        expected_feed3 = self._get_repo(
            False, True, "name3", "url3", "/etc/opkg/test.conf"
        )
        expected_feed4 = self._get_repo(
            True, True, "name4", "url4", "/etc/opkg/test.conf", True
        )
        expected_feed5 = self._get_repo(
            True, True, "name5 space", "url5", "/etc/opkg/test.conf", False
        )

        file_mock = mock_open(read_data={"/etc/opkg/test.conf": feeds_content})
        with patch.object(
            opkg.os, "listdir", MagicMock(return_value=["test.conf", "test"])
        ):
            with patch.object(opkg.salt.utils.files, "fopen", file_mock):
                repos = opkg.list_repos()
                self.assertDictEqual(expected_feed1, repos["url1"][0])
                self.assertDictEqual(expected_feed2, repos["url2"][0])
                self.assertDictEqual(expected_feed3, repos["url3"][0])
                self.assertDictEqual(expected_feed4, repos["url4"][0])
                self.assertDictEqual(expected_feed5, repos["url5"][0])

    def test_mod_repo_add_new_repo(self):
        kwargs = {"uri": "url", "compressed": True, "enabled": True, "trusted": True}
        file_mock = mock_open()
        expected = "src/gz repo url [trusted=yes]\n"
        with patch.object(opkg, "list_repos", MagicMock(return_value=[])):
            with patch.object(opkg.salt.utils.files, "fopen", file_mock):
                opkg.mod_repo("repo", **kwargs)
                handle = file_mock.filehandles["/etc/opkg/repo.conf"][0]
                handle.write.assert_called_once_with(expected)

    def test_mod_repo_set_trusted(self):
        file_content = textwrap.dedent(
            """\
            src/gz   repo     url
            """
        )
        file_mock = mock_open(read_data={"/etc/opkg/repo.conf": file_content})
        kwargs = {"trusted": True}
        expected = "src/gz repo url [trusted=yes]\n"
        with patch.object(opkg.os, "listdir", MagicMock(return_value=["repo.conf"])):
            with patch.object(opkg.salt.utils.files, "fopen", file_mock):
                opkg.mod_repo("repo", **kwargs)
                handle = file_mock.filehandles["/etc/opkg/repo.conf"][2]
                handle.writelines.assert_called_once_with([expected])

    def test_mod_repo_repo_exists(self):
        file_content = textwrap.dedent(
            """\
            src/gz   repo     url
            """
        )
        file_mock = mock_open(read_data={"/etc/opkg/repo.conf": file_content})
        kwargs = {"uri": "url"}
        expected = "Repository 'url' already exists as 'repo'."
        with patch.object(opkg.os, "listdir", MagicMock(return_value=["repo.conf"])):
            with patch.object(opkg.salt.utils.files, "fopen", file_mock):
                with self.assertRaisesRegex(opkg.CommandExecutionError, expected):
                    opkg.mod_repo("repo2", **kwargs)

    def test_mod_repo_uri_not_provided(self):
        expected = "Repository 'repo' not found and no URI passed to create one."
        with patch.object(opkg, "list_repos", MagicMock(return_value=[])):
            with self.assertRaisesRegex(opkg.CommandExecutionError, expected):
                opkg.mod_repo("repo")
