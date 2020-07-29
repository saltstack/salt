# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

import textwrap

# Import Salt Libs
import salt.modules.pkgng as pkgng

# Import Salt Testing Libs
from salt.utils.odict import OrderedDict
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class ListPackages(object):
    def __init__(self):
        self._iteration = 0

    def __call__(self, jail=None, chroot=None, root=None):
        pkg_lists = [
            {"openvpn": "2.4.8_2"},
            {
                "gettext-runtime": "0.20.1",
                "openvpn": "2.4.8_2",
                "p5-Mojolicious": "8.40",
            },
        ]
        pkgs = pkg_lists[self._iteration]
        self._iteration += 1
        return pkgs


class PkgNgTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.pkgng
    """

    @classmethod
    def setup_loader_modules(cls):
        return {pkgng: {"__salt__": {}}}

    def test_lock(self):
        """
        Test pkgng.lock
        """
        lock_cmd = MagicMock(
            return_value={"stdout": ("pkga-1.0\n" "pkgb-2.0\n"), "retcode": 0}
        )
        with patch.dict(pkgng.__salt__, {"cmd.run_all": lock_cmd}):

            result = pkgng.lock("pkga")
            self.assertTrue(result)
            lock_cmd.assert_called_with(
                ["pkg", "lock", "-y", "--quiet", "--show-locked", "pkga"],
                output_loglevel="trace",
                python_shell=False,
            )

            result = pkgng.lock("dummy")
            self.assertFalse(result)
            lock_cmd.assert_called_with(
                ["pkg", "lock", "-y", "--quiet", "--show-locked", "dummy"],
                output_loglevel="trace",
                python_shell=False,
            )

    def test_unlock(self):
        """
        Test pkgng.unlock
        """
        unlock_cmd = MagicMock(
            return_value={"stdout": ("pkga-1.0\n" "pkgb-2.0\n"), "retcode": 0}
        )
        with patch.dict(pkgng.__salt__, {"cmd.run_all": unlock_cmd}):

            result = pkgng.unlock("pkga")
            self.assertFalse(result)
            unlock_cmd.assert_called_with(
                ["pkg", "unlock", "-y", "--quiet", "--show-locked", "pkga"],
                output_loglevel="trace",
                python_shell=False,
            )

            result = pkgng.unlock("dummy")
            self.assertTrue(result)
            unlock_cmd.assert_called_with(
                ["pkg", "unlock", "-y", "--quiet", "--show-locked", "dummy"],
                output_loglevel="trace",
                python_shell=False,
            )

    def test_locked(self):
        """
        Test pkgng.unlock
        """
        lock_cmd = MagicMock(
            return_value={"stdout": ("pkga-1.0\n" "pkgb-2.0\n"), "retcode": 0}
        )
        with patch.dict(pkgng.__salt__, {"cmd.run_all": lock_cmd}):

            result = pkgng.locked("pkga")
            self.assertTrue(result)
            lock_cmd.assert_called_with(
                ["pkg", "lock", "-y", "--quiet", "--show-locked"],
                output_loglevel="trace",
                python_shell=False,
            )

            result = pkgng.locked("dummy")
            self.assertFalse(result)
            lock_cmd.assert_called_with(
                ["pkg", "lock", "-y", "--quiet", "--show-locked"],
                output_loglevel="trace",
                python_shell=False,
            )

    def test_list_upgrades_present(self):
        """
        Test pkgng.list_upgrades with upgrades available
        """
        pkg_cmd = MagicMock(
            return_value=textwrap.dedent(
                """
            The following 6 package(s) will be affected (of 0 checked):

            Installed packages to be UPGRADED:
                    pkga: 1.0 -> 1.1
                    pkgb: 2.0 -> 2.1 [FreeBSD]
                    pkgc: 3.0 -> 3.1 [FreeBSD] (dependency changed)
                    pkgd: 4.0 -> 4.1 (dependency changed)

            New packages to be INSTALLED:
                    pkge: 1.0
                    pkgf: 2.0 [FreeBSD]
                    pkgg: 3.0 [FreeBSD] (dependency changed)
                    pkgh: 4.0 (dependency changed)

            Installed packages to be REINSTALLED:
                    pkgi-1.0
                    pkgj-2.0 [FreeBSD]
                    pkgk-3.0 [FreeBSD] (direct dependency changed: pkga)
                    pkgl-4.0 (direct dependency changed: pkgb)

            Installed packages to be DOWNGRADED:
                    pkgm: 1.1 -> 1.0
                    pkgn: 2.1 -> 2.0 [FreeBSD]
                    pkgo: 3.1 -> 3.0 [FreeBSD] (dependency changed)
                    pkgp: 4.1 -> 4.0 (dependency changed)

            Installed packages to be REMOVED:
                    pkgq-1.0
                    pkgr-2.0 [FreeBSD]
                    pkgs-3.0 [FreeBSD] (direct dependency changed: pkga)
                    pkgt-4.0 (direct dependency changed: pkgb)

            Number of packages to be upgraded: 2
            Number of packages to be reinstalled: 2

            The process will require 14 MiB more space.
            22 MiB to be downloaded.
            """
            )
        )

        with patch.dict(pkgng.__salt__, {"cmd.run_stdout": pkg_cmd}):

            result = pkgng.list_upgrades(refresh=False)
            self.assertDictEqual(
                result, {"pkga": "1.1", "pkgb": "2.1", "pkgc": "3.1", "pkgd": "4.1"}
            )
            pkg_cmd.assert_called_with(
                ["pkg", "upgrade", "--dry-run", "--quiet", "--no-repo-update"],
                output_loglevel="trace",
                python_shell=False,
                ignore_retcode=True,
            )

    def test_list_upgrades_absent(self):
        """
        Test pkgng.list_upgrades with no upgrades available
        """
        pkg_cmd = MagicMock(return_value="")

        with patch.dict(pkgng.__salt__, {"cmd.run_stdout": pkg_cmd}):
            result = pkgng.list_upgrades(refresh=False)
            self.assertDictEqual(result, {})
            pkg_cmd.assert_called_with(
                ["pkg", "upgrade", "--dry-run", "--quiet", "--no-repo-update"],
                output_loglevel="trace",
                python_shell=False,
                ignore_retcode=True,
            )

    def test_upgrade_without_fromrepo(self):
        """
        Test pkg upgrade to upgrade all available packages
        """
        pkg_cmd = MagicMock(return_value={"retcode": 0})

        with patch.dict(pkgng.__salt__, {"cmd.run_all": pkg_cmd}):
            with patch("salt.modules.pkgng.list_pkgs", ListPackages()):
                result = pkgng.upgrade()
                expected = {
                    "gettext-runtime": {"new": "0.20.1", "old": ""},
                    "p5-Mojolicious": {"new": "8.40", "old": ""},
                }
                self.assertDictEqual(result, expected)
                pkg_cmd.assert_called_with(
                    ["pkg", "upgrade", "-y"],
                    output_loglevel="trace",
                    python_shell=False,
                )

    def test_upgrade_with_fromrepo(self):
        """
        Test pkg upgrade to upgrade all available packages
        """
        pkg_cmd = MagicMock(return_value={"retcode": 0})

        with patch.dict(pkgng.__salt__, {"cmd.run_all": pkg_cmd}):
            with patch("salt.modules.pkgng.list_pkgs", ListPackages()):
                result = pkgng.upgrade(fromrepo="FreeBSD")
                expected = {
                    "gettext-runtime": {"new": "0.20.1", "old": ""},
                    "p5-Mojolicious": {"new": "8.40", "old": ""},
                }
                self.assertDictEqual(result, expected)
                pkg_cmd.assert_called_with(
                    ["pkg", "upgrade", "-y", "--repository", "FreeBSD"],
                    output_loglevel="trace",
                    python_shell=False,
                )

    def test_upgrade_with_fetchonly(self):
        """
        Test pkg upgrade to fetch packages only
        """
        pkg_cmd = MagicMock(return_value={"retcode": 0})

        with patch.dict(pkgng.__salt__, {"cmd.run_all": pkg_cmd}):
            with patch("salt.modules.pkgng.list_pkgs", ListPackages()):
                result = pkgng.upgrade(fetchonly=True)
                expected = {
                    "gettext-runtime": {"new": "0.20.1", "old": ""},
                    "p5-Mojolicious": {"new": "8.40", "old": ""},
                }
                self.assertDictEqual(result, expected)
                pkg_cmd.assert_called_with(
                    ["pkg", "upgrade", "-Fy"],
                    output_loglevel="trace",
                    python_shell=False,
                )

    def test_stats_with_local(self):
        """
        Test pkg.stats for local packages
        """
        pkg_cmd = MagicMock(return_value="")

        with patch.dict(pkgng.__salt__, {"cmd.run": pkg_cmd}):
            result = pkgng.stats(local=True)
            self.assertEqual(result, [])
            pkg_cmd.assert_called_with(
                ["pkg", "stats", "-l"], output_loglevel="trace", python_shell=False,
            )

    def test_stats_with_remote(self):
        """
        Test pkg.stats for remote packages
        """
        pkg_cmd = MagicMock(return_value="")

        with patch.dict(pkgng.__salt__, {"cmd.run": pkg_cmd}):
            result = pkgng.stats(remote=True)
            self.assertEqual(result, [])
            pkg_cmd.assert_called_with(
                ["pkg", "stats", "-r"], output_loglevel="trace", python_shell=False,
            )

    def test_install_without_args(self):
        """
        Test pkg.install to install a package without arguments
        """
        parsed_targets = (
            OrderedDict((("gettext-runtime", None), ("p5-Mojolicious", None))),
            "repository",
        )
        pkg_cmd = MagicMock(return_value={"retcode": 0})
        patches = {
            "cmd.run_all": pkg_cmd,
            "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
        }
        with patch.dict(pkgng.__salt__, patches):
            with patch("salt.modules.pkgng.list_pkgs", ListPackages()):
                added = pkgng.install()
                expected = {
                    "gettext-runtime": {"new": "0.20.1", "old": ""},
                    "p5-Mojolicious": {"new": "8.40", "old": ""},
                }
                self.assertDictEqual(added, expected)
                pkg_cmd.assert_called_with(
                    ["pkg", "install", "-y", "gettext-runtime", "p5-Mojolicious"],
                    output_loglevel="trace",
                    python_shell=False,
                    env={},
                )

    def test_install_with_local(self):
        """
        Test pkg.install to install a package with local=True argument
        """
        parsed_targets = (
            OrderedDict((("gettext-runtime", None), ("p5-Mojolicious", None))),
            "repository",
        )
        pkg_cmd = MagicMock(return_value={"retcode": 0})
        patches = {
            "cmd.run_all": pkg_cmd,
            "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
        }
        with patch.dict(pkgng.__salt__, patches):
            with patch("salt.modules.pkgng.list_pkgs", ListPackages()):
                added = pkgng.install(local=True)
                expected = {
                    "gettext-runtime": {"new": "0.20.1", "old": ""},
                    "p5-Mojolicious": {"new": "8.40", "old": ""},
                }
                self.assertDictEqual(added, expected)
                pkg_cmd.assert_called_with(
                    ["pkg", "install", "-yU", "gettext-runtime", "p5-Mojolicious"],
                    output_loglevel="trace",
                    python_shell=False,
                    env={},
                )

    def test_install_with_fromrepo(self):
        """
        Test pkg.install to install a package with fromrepo=FreeBSD argument
        """
        parsed_targets = (
            OrderedDict((("gettext-runtime", None), ("p5-Mojolicious", None))),
            "repository",
        )
        pkg_cmd = MagicMock(return_value={"retcode": 0})
        patches = {
            "cmd.run_all": pkg_cmd,
            "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
        }
        with patch.dict(pkgng.__salt__, patches):
            with patch("salt.modules.pkgng.list_pkgs", ListPackages()):
                added = pkgng.install(fromrepo="FreeBSD")
                expected = {
                    "gettext-runtime": {"new": "0.20.1", "old": ""},
                    "p5-Mojolicious": {"new": "8.40", "old": ""},
                }
                self.assertDictEqual(added, expected)
                pkg_cmd.assert_called_with(
                    [
                        "pkg",
                        "install",
                        "-r",
                        "FreeBSD",
                        "-y",
                        "gettext-runtime",
                        "p5-Mojolicious",
                    ],
                    output_loglevel="trace",
                    python_shell=False,
                    env={},
                )

    def test_install_with_glob(self):
        """
        Test pkg.install to install a package with glob=True argument
        """
        parsed_targets = (
            OrderedDict((("gettext-runtime", None), ("p5-Mojolicious", None))),
            "repository",
        )
        pkg_cmd = MagicMock(return_value={"retcode": 0})
        patches = {
            "cmd.run_all": pkg_cmd,
            "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
        }
        with patch.dict(pkgng.__salt__, patches):
            with patch("salt.modules.pkgng.list_pkgs", ListPackages()):
                added = pkgng.install(glob=True)
                expected = {
                    "gettext-runtime": {"new": "0.20.1", "old": ""},
                    "p5-Mojolicious": {"new": "8.40", "old": ""},
                }
                self.assertDictEqual(added, expected)
                pkg_cmd.assert_called_with(
                    ["pkg", "install", "-yg", "gettext-runtime", "p5-Mojolicious"],
                    output_loglevel="trace",
                    python_shell=False,
                    env={},
                )

    def test_install_with_reinstall_requires(self):
        """
        Test pkg.install to install a package with reinstall_requires=True argument
        """
        parsed_targets = (
            OrderedDict((("gettext-runtime", None), ("p5-Mojolicious", None))),
            "repository",
        )
        pkg_cmd = MagicMock(return_value={"retcode": 0})
        patches = {
            "cmd.run_all": pkg_cmd,
            "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
        }
        with patch.dict(pkgng.__salt__, patches):
            with patch("salt.modules.pkgng.list_pkgs", ListPackages()):
                added = pkgng.install(reinstall_requires=True, force=True)
                expected = {
                    "gettext-runtime": {"new": "0.20.1", "old": ""},
                    "p5-Mojolicious": {"new": "8.40", "old": ""},
                }
                self.assertDictEqual(added, expected)
                pkg_cmd.assert_called_with(
                    ["pkg", "install", "-yfR", "gettext-runtime", "p5-Mojolicious"],
                    output_loglevel="trace",
                    python_shell=False,
                    env={},
                )

    def test_install_with_regex(self):
        """
        Test pkg.install to install a package with regex=True argument
        """
        parsed_targets = (
            OrderedDict((("gettext-runtime", None), ("p5-Mojolicious", None))),
            "repository",
        )
        pkg_cmd = MagicMock(return_value={"retcode": 0})
        patches = {
            "cmd.run_all": pkg_cmd,
            "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
        }
        with patch.dict(pkgng.__salt__, patches):
            with patch("salt.modules.pkgng.list_pkgs", ListPackages()):
                added = pkgng.install(regex=True)
                expected = {
                    "gettext-runtime": {"new": "0.20.1", "old": ""},
                    "p5-Mojolicious": {"new": "8.40", "old": ""},
                }
                self.assertDictEqual(added, expected)
                pkg_cmd.assert_called_with(
                    ["pkg", "install", "-yx", "gettext-runtime", "p5-Mojolicious"],
                    output_loglevel="trace",
                    python_shell=False,
                    env={},
                )

    def test_install_with_batch(self):
        """
        Test pkg.install to install a package with batch=True argument
        """
        parsed_targets = (
            OrderedDict((("gettext-runtime", None), ("p5-Mojolicious", None))),
            "repository",
        )
        pkg_cmd = MagicMock(return_value={"retcode": 0})
        patches = {
            "cmd.run_all": pkg_cmd,
            "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
        }
        with patch.dict(pkgng.__salt__, patches):
            with patch("salt.modules.pkgng.list_pkgs", ListPackages()):
                added = pkgng.install(batch=True)
                expected = {
                    "gettext-runtime": {"new": "0.20.1", "old": ""},
                    "p5-Mojolicious": {"new": "8.40", "old": ""},
                }
                self.assertDictEqual(added, expected)
                pkg_cmd.assert_called_with(
                    ["pkg", "install", "-y", "gettext-runtime", "p5-Mojolicious"],
                    output_loglevel="trace",
                    python_shell=False,
                    env={"BATCH": "true", "ASSUME_ALWAYS_YES": "YES"},
                )

    def test_install_with_pcre(self):
        """
        Test pkg.install to install a package with pcre=True argument
        """
        parsed_targets = (
            OrderedDict((("gettext-runtime", None), ("p5-Mojolicious", None))),
            "repository",
        )
        pkg_cmd = MagicMock(return_value={"retcode": 0})
        patches = {
            "cmd.run_all": pkg_cmd,
            "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
        }
        with patch.dict(pkgng.__salt__, patches):
            with patch("salt.modules.pkgng.list_pkgs", ListPackages()):
                added = pkgng.install(pcre=True)
                expected = {
                    "gettext-runtime": {"new": "0.20.1", "old": ""},
                    "p5-Mojolicious": {"new": "8.40", "old": ""},
                }
                self.assertDictEqual(added, expected)
                pkg_cmd.assert_called_with(
                    ["pkg", "install", "-yX", "gettext-runtime", "p5-Mojolicious"],
                    output_loglevel="trace",
                    python_shell=False,
                    env={},
                )

    def test_install_with_orphan(self):
        """
        Test pkg.install to install a package with orphan=True argument
        """
        parsed_targets = (
            OrderedDict((("gettext-runtime", None), ("p5-Mojolicious", None))),
            "repository",
        )
        pkg_cmd = MagicMock(return_value={"retcode": 0})
        patches = {
            "cmd.run_all": pkg_cmd,
            "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
        }
        with patch.dict(pkgng.__salt__, patches):
            with patch("salt.modules.pkgng.list_pkgs", ListPackages()):
                added = pkgng.install(orphan=True)
                expected = {
                    "gettext-runtime": {"new": "0.20.1", "old": ""},
                    "p5-Mojolicious": {"new": "8.40", "old": ""},
                }
                self.assertDictEqual(added, expected)
                pkg_cmd.assert_called_with(
                    ["pkg", "install", "-yA", "gettext-runtime", "p5-Mojolicious"],
                    output_loglevel="trace",
                    python_shell=False,
                    env={},
                )
