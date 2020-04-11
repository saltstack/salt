# -*- coding: utf-8 -*-
"""
    :synopsis: Unit Tests for Advanced Packaging Tool module 'module.aptpkg'
    :platform: Linux
    :maturity: develop
    versionadded:: 2017.7.0
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import copy
import textwrap

import salt.modules.aptpkg as aptpkg
from salt.exceptions import CommandExecutionError, SaltInvocationError

# Import Salt Libs
from salt.ext import six

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, Mock, patch
from tests.support.unit import TestCase, skipIf

try:
    import pytest
except ImportError:
    pytest = None


APT_KEY_LIST = r"""
pub:-:1024:17:46181433FBB75451:1104433784:::-:::scSC:
fpr:::::::::C5986B4F1257FFA86632CBA746181433FBB75451:
uid:-::::1104433784::B4D41942D4B35FF44182C7F9D00C99AF27B93AD0::Ubuntu CD Image Automatic Signing Key <cdimage@ubuntu.com>:
"""

REPO_KEYS = {
    "46181433FBB75451": {
        "algorithm": 17,
        "bits": 1024,
        "capability": "scSC",
        "date_creation": 1104433784,
        "date_expiration": None,
        "fingerprint": "C5986B4F1257FFA86632CBA746181433FBB75451",
        "keyid": "46181433FBB75451",
        "uid": "Ubuntu CD Image Automatic Signing Key <cdimage@ubuntu.com>",
        "uid_hash": "B4D41942D4B35FF44182C7F9D00C99AF27B93AD0",
        "validity": "-",
    }
}

PACKAGES = {"wget": "1.15-1ubuntu1.14.04.2"}

LOWPKG_FILES = {
    "errors": {},
    "packages": {
        "wget": [
            "/.",
            "/etc",
            "/etc/wgetrc",
            "/usr",
            "/usr/bin",
            "/usr/bin/wget",
            "/usr/share",
            "/usr/share/info",
            "/usr/share/info/wget.info.gz",
            "/usr/share/doc",
            "/usr/share/doc/wget",
            "/usr/share/doc/wget/MAILING-LIST",
            "/usr/share/doc/wget/NEWS.gz",
            "/usr/share/doc/wget/AUTHORS",
            "/usr/share/doc/wget/copyright",
            "/usr/share/doc/wget/changelog.Debian.gz",
            "/usr/share/doc/wget/README",
            "/usr/share/man",
            "/usr/share/man/man1",
            "/usr/share/man/man1/wget.1.gz",
        ]
    },
}

LOWPKG_INFO = {
    "wget": {
        "architecture": "amd64",
        "description": "retrieves files from the web",
        "homepage": "http://www.gnu.org/software/wget/",
        "install_date": "2016-08-30T22:20:15Z",
        "maintainer": "Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>",
        "name": "wget",
        "section": "web",
        "source": "wget",
        "version": "1.15-1ubuntu1.14.04.2",
        "status": "ii",
    },
    "apache2": {
        "architecture": "amd64",
        "description": """Apache HTTP Server
 The Apache HTTP Server Project's goal is to build a secure, efficient and
 extensible HTTP server as standards-compliant open source software. The
 result has long been the number one web server on the Internet.
 .
 Installing this package results in a full installation, including the
 configuration files, init scripts and support scripts.""",
        "homepage": "http://httpd.apache.org/",
        "install_date": "2016-08-30T22:20:15Z",
        "maintainer": "Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>",
        "name": "apache2",
        "section": "httpd",
        "source": "apache2",
        "version": "2.4.18-2ubuntu3.9",
        "status": "rc",
    },
}

APT_Q_UPDATE = """
Get:1 http://security.ubuntu.com trusty-security InRelease [65 kB]
Get:2 http://security.ubuntu.com trusty-security/main Sources [120 kB]
Get:3 http://security.ubuntu.com trusty-security/main amd64 Packages [548 kB]
Get:4 http://security.ubuntu.com trusty-security/main i386 Packages [507 kB]
Hit http://security.ubuntu.com trusty-security/main Translation-en
Fetched 1240 kB in 10s (124 kB/s)
Reading package lists...
"""

APT_Q_UPDATE_ERROR = """
Err http://security.ubuntu.com trusty InRelease

Err http://security.ubuntu.com trusty Release.gpg
Unable to connect to security.ubuntu.com:http:
Reading package lists...
W: Failed to fetch http://security.ubuntu.com/ubuntu/dists/trusty/InRelease

W: Failed to fetch http://security.ubuntu.com/ubuntu/dists/trusty/Release.gpg  Unable to connect to security.ubuntu.com:http:

W: Some index files failed to download. They have been ignored, or old ones used instead.
"""

AUTOREMOVE = """
Reading package lists... Done
Building dependency tree
Reading state information... Done
0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.
"""

UPGRADE = """
Reading package lists...
Building dependency tree...
Reading state information...
0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.
"""

UNINSTALL = {"tmux": {"new": six.text_type(), "old": "1.8-5"}}


class AptPkgTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.aptpkg
    """

    def setup_loader_modules(self):
        return {aptpkg: {}}

    def test_version(self):
        """
        Test - Returns a string representing the package version or an empty string if
        not installed.
        """
        version = LOWPKG_INFO["wget"]["version"]
        mock = MagicMock(return_value=version)
        with patch.dict(aptpkg.__salt__, {"pkg_resource.version": mock}):
            self.assertEqual(aptpkg.version(*["wget"]), version)

    def test_upgrade_available(self):
        """
        Test - Check whether or not an upgrade is available for a given package.
        """
        with patch("salt.modules.aptpkg.latest_version", MagicMock(return_value="")):
            self.assertFalse(aptpkg.upgrade_available("wget"))

    def test_add_repo_key(self):
        """
        Test - Add a repo key.
        """
        with patch(
            "salt.modules.aptpkg.get_repo_keys", MagicMock(return_value=REPO_KEYS)
        ):
            mock = MagicMock(return_value={"retcode": 0, "stdout": "OK"})
            with patch.dict(aptpkg.__salt__, {"cmd.run_all": mock}):
                self.assertTrue(
                    aptpkg.add_repo_key(
                        keyserver="keyserver.ubuntu.com", keyid="FBB75451"
                    )
                )

    def test_add_repo_key_failed(self):
        """
        Test - Add a repo key using incomplete input data.
        """
        with patch(
            "salt.modules.aptpkg.get_repo_keys", MagicMock(return_value=REPO_KEYS)
        ):
            kwargs = {"keyserver": "keyserver.ubuntu.com"}
            mock = MagicMock(return_value={"retcode": 0, "stdout": "OK"})
            with patch.dict(aptpkg.__salt__, {"cmd.run_all": mock}):
                self.assertRaises(SaltInvocationError, aptpkg.add_repo_key, **kwargs)

    def test_get_repo_keys(self):
        """
        Test - List known repo key details.
        """
        mock = MagicMock(return_value={"retcode": 0, "stdout": APT_KEY_LIST})
        with patch.dict(aptpkg.__salt__, {"cmd.run_all": mock}):
            self.assertEqual(aptpkg.get_repo_keys(), REPO_KEYS)

    def test_file_dict(self):
        """
        Test - List the files that belong to a package, grouped by package.
        """
        mock = MagicMock(return_value=LOWPKG_FILES)
        with patch.dict(aptpkg.__salt__, {"lowpkg.file_dict": mock}):
            self.assertEqual(aptpkg.file_dict("wget"), LOWPKG_FILES)

    def test_file_list(self):
        """
        Test - List the files that belong to a package.
        """
        files = {
            "errors": LOWPKG_FILES["errors"],
            "files": LOWPKG_FILES["packages"]["wget"],
        }
        mock = MagicMock(return_value=files)
        with patch.dict(aptpkg.__salt__, {"lowpkg.file_list": mock}):
            self.assertEqual(aptpkg.file_list("wget"), files)

    def test_get_selections(self):
        """
        Test - View package state from the dpkg database.
        """
        selections = {"install": ["wget"]}
        mock = MagicMock(return_value="wget\t\t\t\t\t\tinstall")
        with patch.dict(aptpkg.__salt__, {"cmd.run_stdout": mock}):
            self.assertEqual(aptpkg.get_selections("wget"), selections)

    def test_info_installed(self):
        """
        Test - Return the information of the named package(s) installed on the system.
        """
        names = {"group": "section", "packager": "maintainer", "url": "homepage"}

        installed = copy.deepcopy({"wget": LOWPKG_INFO["wget"]})
        for name in names:
            if installed["wget"].get(names[name], False):
                installed["wget"][name] = installed["wget"].pop(names[name])

        mock = MagicMock(return_value=LOWPKG_INFO)
        with patch.dict(aptpkg.__salt__, {"lowpkg.info": mock}):
            del installed["wget"]["status"]
            self.assertEqual(aptpkg.info_installed("wget"), installed)
            self.assertEqual(len(aptpkg.info_installed()), 1)

    def test_owner(self):
        """
        Test - Return the name of the package that owns the file.
        """
        paths = ["/usr/bin/wget"]
        mock = MagicMock(return_value="wget: /usr/bin/wget")
        with patch.dict(aptpkg.__salt__, {"cmd.run_stdout": mock}):
            self.assertEqual(aptpkg.owner(*paths), "wget")

    def test_refresh_db(self):
        """
        Test - Updates the APT database to latest packages based upon repositories.
        """
        refresh_db = {
            "http://security.ubuntu.com trusty-security InRelease": True,
            "http://security.ubuntu.com trusty-security/main Sources": True,
            "http://security.ubuntu.com trusty-security/main Translation-en": None,
            "http://security.ubuntu.com trusty-security/main amd64 Packages": True,
            "http://security.ubuntu.com trusty-security/main i386 Packages": True,
        }
        mock = MagicMock(return_value={"retcode": 0, "stdout": APT_Q_UPDATE})
        with patch("salt.utils.pkg.clear_rtag", MagicMock()):
            with patch.dict(
                aptpkg.__salt__,
                {"cmd.run_all": mock, "config.get": MagicMock(return_value=False)},
            ):
                self.assertEqual(aptpkg.refresh_db(), refresh_db)

    def test_refresh_db_failed(self):
        """
        Test - Update the APT database using unreachable repositories.
        """
        kwargs = {"failhard": True}
        mock = MagicMock(return_value={"retcode": 0, "stdout": APT_Q_UPDATE_ERROR})
        with patch("salt.utils.pkg.clear_rtag", MagicMock()):
            with patch.dict(
                aptpkg.__salt__,
                {"cmd.run_all": mock, "config.get": MagicMock(return_value=False)},
            ):
                self.assertRaises(CommandExecutionError, aptpkg.refresh_db, **kwargs)

    def test_autoremove(self):
        """
        Test - Remove packages not required by another package.
        """
        with patch("salt.modules.aptpkg.list_pkgs", MagicMock(return_value=PACKAGES)):
            patch_kwargs = {
                "__salt__": {
                    "config.get": MagicMock(return_value=True),
                    "cmd.run_all": MagicMock(
                        return_value=MagicMock(return_value=AUTOREMOVE)
                    ),
                }
            }
            with patch.multiple(aptpkg, **patch_kwargs):
                assert aptpkg.autoremove() == {}
                assert aptpkg.autoremove(purge=True) == {}
                assert aptpkg.autoremove(list_only=True) == []
                assert aptpkg.autoremove(list_only=True, purge=True) == []

    def test_remove(self):
        """
        Test - Remove packages.
        """
        with patch("salt.modules.aptpkg._uninstall", MagicMock(return_value=UNINSTALL)):
            self.assertEqual(aptpkg.remove(name="tmux"), UNINSTALL)

    def test_purge(self):
        """
        Test - Remove packages along with all configuration files.
        """
        with patch("salt.modules.aptpkg._uninstall", MagicMock(return_value=UNINSTALL)):
            self.assertEqual(aptpkg.purge(name="tmux"), UNINSTALL)

    def test_upgrade(self):
        """
        Test - Upgrades all packages.
        """
        with patch("salt.utils.pkg.clear_rtag", MagicMock()):
            with patch(
                "salt.modules.aptpkg.list_pkgs", MagicMock(return_value=UNINSTALL)
            ):
                mock_cmd = MagicMock(return_value={"retcode": 0, "stdout": UPGRADE})
                patch_kwargs = {
                    "__salt__": {
                        "config.get": MagicMock(return_value=True),
                        "cmd.run_all": mock_cmd,
                    }
                }
                with patch.multiple(aptpkg, **patch_kwargs):
                    self.assertEqual(aptpkg.upgrade(), dict())

    def test_upgrade_downloadonly(self):
        """
        Tests the download-only options for upgrade.
        """
        with patch("salt.utils.pkg.clear_rtag", MagicMock()):
            with patch(
                "salt.modules.aptpkg.list_pkgs", MagicMock(return_value=UNINSTALL)
            ):
                mock_cmd = MagicMock(return_value={"retcode": 0, "stdout": UPGRADE})
                patch_kwargs = {
                    "__salt__": {
                        "config.get": MagicMock(return_value=True),
                        "cmd.run_all": mock_cmd,
                    },
                }
                with patch.multiple(aptpkg, **patch_kwargs):
                    aptpkg.upgrade()
                    args_matching = [
                        True
                        for args in patch_kwargs["__salt__"]["cmd.run_all"].call_args[0]
                        if "--download-only" in args
                    ]
                    # Here we shouldn't see the parameter and args_matching should be empty.
                    self.assertFalse(any(args_matching))

                    aptpkg.upgrade(downloadonly=True)
                    args_matching = [
                        True
                        for args in patch_kwargs["__salt__"]["cmd.run_all"].call_args[0]
                        if "--download-only" in args
                    ]
                    # --download-only should be in the args list and we should have at least on True in the list.
                    self.assertTrue(any(args_matching))

                    aptpkg.upgrade(download_only=True)
                    args_matching = [
                        True
                        for args in patch_kwargs["__salt__"]["cmd.run_all"].call_args[0]
                        if "--download-only" in args
                    ]
                    # --download-only should be in the args list and we should have at least on True in the list.
                    self.assertTrue(any(args_matching))

    def test_show(self):
        """
        Test that the pkg.show function properly parses apt-cache show output.
        This test uses an abridged output per package, for simplicity.
        """
        show_mock_success = MagicMock(
            return_value={
                "retcode": 0,
                "pid": 12345,
                "stderr": "",
                "stdout": textwrap.dedent(
                    """\
                Package: foo1.0
                Architecture: amd64
                Version: 1.0.5-3ubuntu4
                Description: A silly package (1.0 release cycle)
                Provides: foo
                Suggests: foo-doc

                Package: foo1.0
                Architecture: amd64
                Version: 1.0.4-2ubuntu1
                Description: A silly package (1.0 release cycle)
                Provides: foo
                Suggests: foo-doc

                Package: foo-doc
                Architecture: all
                Version: 1.0.5-3ubuntu4
                Description: Silly documentation for a silly package (1.0 release cycle)

                Package: foo-doc
                Architecture: all
                Version: 1.0.4-2ubuntu1
                Description: Silly documentation for a silly package (1.0 release cycle)

                """
                ),
            }
        )

        show_mock_failure = MagicMock(
            return_value={
                "retcode": 1,
                "pid": 12345,
                "stderr": textwrap.dedent(
                    """\
                N: Unable to locate package foo*
                N: Couldn't find any package by glob 'foo*'
                N: Couldn't find any package by regex 'foo*'
                E: No packages found
                """
                ),
                "stdout": "",
            }
        )

        refresh_mock = Mock()

        expected = {
            "foo1.0": {
                "1.0.5-3ubuntu4": {
                    "Architecture": "amd64",
                    "Description": "A silly package (1.0 release cycle)",
                    "Provides": "foo",
                    "Suggests": "foo-doc",
                },
                "1.0.4-2ubuntu1": {
                    "Architecture": "amd64",
                    "Description": "A silly package (1.0 release cycle)",
                    "Provides": "foo",
                    "Suggests": "foo-doc",
                },
            },
            "foo-doc": {
                "1.0.5-3ubuntu4": {
                    "Architecture": "all",
                    "Description": "Silly documentation for a silly package (1.0 release cycle)",
                },
                "1.0.4-2ubuntu1": {
                    "Architecture": "all",
                    "Description": "Silly documentation for a silly package (1.0 release cycle)",
                },
            },
        }

        # Make a copy of the above dict and strip out some keys to produce the
        # expected filtered result.
        filtered = copy.deepcopy(expected)
        for k1 in filtered:
            for k2 in filtered[k1]:
                # Using list() because we will modify the dict during iteration
                for k3 in list(filtered[k1][k2]):
                    if k3 not in ("Description", "Provides"):
                        filtered[k1][k2].pop(k3)

        with patch.dict(
            aptpkg.__salt__, {"cmd.run_all": show_mock_success}
        ), patch.object(aptpkg, "refresh_db", refresh_mock):

            # Test success (no refresh)
            self.assertEqual(aptpkg.show("foo*"), expected)
            refresh_mock.assert_not_called()
            refresh_mock.reset_mock()

            # Test success (with refresh)
            self.assertEqual(aptpkg.show("foo*", refresh=True), expected)
            self.assert_called_once(refresh_mock)
            refresh_mock.reset_mock()

            # Test filtered return
            self.assertEqual(
                aptpkg.show("foo*", filter="description,provides"), filtered
            )
            refresh_mock.assert_not_called()
            refresh_mock.reset_mock()

        with patch.dict(
            aptpkg.__salt__, {"cmd.run_all": show_mock_failure}
        ), patch.object(aptpkg, "refresh_db", refresh_mock):

            # Test failure (no refresh)
            self.assertEqual(aptpkg.show("foo*"), {})
            refresh_mock.assert_not_called()
            refresh_mock.reset_mock()

            # Test failure (with refresh)
            self.assertEqual(aptpkg.show("foo*", refresh=True), {})
            self.assert_called_once(refresh_mock)
            refresh_mock.reset_mock()

    def test_mod_repo_enabled(self):
        """
        Checks if a repo is enabled or disabled depending on the passed kwargs.
        """
        with patch.dict(
            aptpkg.__salt__,
            {"config.option": MagicMock(), "no_proxy": MagicMock(return_value=False)},
        ):
            with patch("salt.modules.aptpkg._check_apt", MagicMock(return_value=True)):
                with patch(
                    "salt.modules.aptpkg.refresh_db", MagicMock(return_value={})
                ):
                    with patch(
                        "salt.utils.data.is_true", MagicMock(return_value=True)
                    ) as data_is_true:
                        with patch(
                            "salt.modules.aptpkg.sourceslist", MagicMock(), create=True
                        ):
                            repo = aptpkg.mod_repo("foo", enabled=False)
                            data_is_true.assert_called_with(False)
                            # with disabled=True; should call salt.utils.data.is_true True
                            data_is_true.reset_mock()
                            repo = aptpkg.mod_repo("foo", disabled=True)
                            data_is_true.assert_called_with(True)
                            # with enabled=True; should call salt.utils.data.is_true with False
                            data_is_true.reset_mock()
                            repo = aptpkg.mod_repo("foo", enabled=True)
                            data_is_true.assert_called_with(True)
                            # with disabled=True; should call salt.utils.data.is_true False
                            data_is_true.reset_mock()
                            repo = aptpkg.mod_repo("foo", disabled=False)
                            data_is_true.assert_called_with(False)

    @patch(
        "salt.utils.path.os_walk", MagicMock(return_value=[("test", "test", "test")])
    )
    @patch("os.path.getsize", MagicMock(return_value=123456))
    @patch("os.path.getctime", MagicMock(return_value=1234567890.123456))
    @patch(
        "fnmatch.filter",
        MagicMock(return_value=["/var/cache/apt/archive/test_package.rpm"]),
    )
    def test_list_downloaded(self):
        """
        Test downloaded packages listing.
        :return:
        """
        DOWNLOADED_RET = {
            "test-package": {
                "1.0": {
                    "path": "/var/cache/apt/archive/test_package.rpm",
                    "size": 123456,
                    "creation_date_time_t": 1234567890,
                    "creation_date_time": "2009-02-13T23:31:30",
                }
            }
        }

        with patch.dict(
            aptpkg.__salt__,
            {
                "lowpkg.bin_pkg_info": MagicMock(
                    return_value={"name": "test-package", "version": "1.0"}
                )
            },
        ):
            list_downloaded = aptpkg.list_downloaded()
            self.assertEqual(len(list_downloaded), 1)
            self.assertDictEqual(list_downloaded, DOWNLOADED_RET)


@skipIf(pytest is None, "PyTest is missing")
class AptUtilsTestCase(TestCase, LoaderModuleMockMixin):
    """
    apt utils test case
    """

    def setup_loader_modules(self):
        return {aptpkg: {}}

    def test_call_apt_default(self):
        """
        Call default apt.
        :return:
        """
        with patch.dict(
            aptpkg.__salt__,
            {"cmd.run_all": MagicMock(), "config.get": MagicMock(return_value=False)},
        ):
            aptpkg._call_apt(["apt-get", "install", "emacs"])  # pylint: disable=W0106
            aptpkg.__salt__["cmd.run_all"].assert_called_once_with(
                ["apt-get", "install", "emacs"],
                env={},
                output_loglevel="trace",
                python_shell=False,
            )

    @patch("salt.utils.systemd.has_scope", MagicMock(return_value=True))
    def test_call_apt_in_scope(self):
        """
        Call apt within the scope.
        :return:
        """
        with patch.dict(
            aptpkg.__salt__,
            {"cmd.run_all": MagicMock(), "config.get": MagicMock(return_value=True)},
        ):
            aptpkg._call_apt(["apt-get", "purge", "vim"])  # pylint: disable=W0106
            aptpkg.__salt__["cmd.run_all"].assert_called_once_with(
                ["systemd-run", "--scope", "apt-get", "purge", "vim"],
                env={},
                output_loglevel="trace",
                python_shell=False,
            )

    def test_call_apt_with_kwargs(self):
        """
        Call apt with the optinal keyword arguments.
        :return:
        """
        with patch.dict(
            aptpkg.__salt__,
            {"cmd.run_all": MagicMock(), "config.get": MagicMock(return_value=False)},
        ):
            aptpkg._call_apt(
                ["dpkg", "-l", "python"],
                python_shell=True,
                output_loglevel="quiet",
                ignore_retcode=False,
                username="Darth Vader",
            )  # pylint: disable=W0106
            aptpkg.__salt__["cmd.run_all"].assert_called_once_with(
                ["dpkg", "-l", "python"],
                env={},
                ignore_retcode=False,
                output_loglevel="quiet",
                python_shell=True,
                username="Darth Vader",
            )
