# -*- coding: utf-8 -*-
"""
    :codeauthor: Eric Radman <ericshane@eradman.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.openbsdpkg as openbsdpkg

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, call, patch
from tests.support.unit import TestCase


class ListPackages(object):
    def __init__(self):
        self._iteration = 0

    def __call__(self):
        pkg_lists = [
            {"vim": "7.4.1467p1-gtk2"},
            {"png": "1.6.23", "vim": "7.4.1467p1-gtk2", "ruby": "2.3.1p1"},
        ]
        pkgs = pkg_lists[self._iteration]
        self._iteration += 1
        return pkgs


class OpenbsdpkgTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.openbsdpkg
    """

    def setup_loader_modules(self):
        return {openbsdpkg: {}}

    def test_list_pkgs(self):
        """
        Test for listing installed packages.
        """

        def _add_data(data, key, value):
            data[key] = value

        pkg_info_out = [
            "png-1.6.23",
            "vim-7.4.1467p1-gtk2",  # vim--gtk2
            "ruby-2.3.1p1",  # ruby%2.3
        ]
        run_stdout_mock = MagicMock(return_value="\n".join(pkg_info_out))
        patches = {
            "cmd.run_stdout": run_stdout_mock,
            "pkg_resource.add_pkg": _add_data,
            "pkg_resource.sort_pkglist": MagicMock(),
            "pkg_resource.stringify": MagicMock(),
        }
        with patch.dict(openbsdpkg.__salt__, patches):
            pkgs = openbsdpkg.list_pkgs()
            self.assertDictEqual(
                pkgs, {"png": "1.6.23", "vim--gtk2": "7.4.1467p1", "ruby": "2.3.1p1"}
            )
        run_stdout_mock.assert_called_once_with(
            "pkg_info -q -a", output_loglevel="trace"
        )

    def test_install_pkgs(self):
        """
        Test package install behavior for the following conditions:
        - only base package name is given ('png')
        - a flavor is specified ('vim--gtk2')
        - a branch is specified ('ruby%2.3')
        """

        parsed_targets = (
            {"vim--gtk2": None, "png": None, "ruby%2.3": None},
            "repository",
        )
        cmd_out = {
            "retcode": 0,
            "stdout": "quirks-2.241 signed on 2016-07-26T16:56:10Z",
            "stderr": "",
        }
        run_all_mock = MagicMock(return_value=cmd_out)
        patches = {
            "cmd.run_all": run_all_mock,
            "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
            "pkg_resource.stringify": MagicMock(),
            "pkg_resource.sort_pkglist": MagicMock(),
        }

        with patch.dict(openbsdpkg.__salt__, patches):
            with patch("salt.modules.openbsdpkg.list_pkgs", ListPackages()):
                added = openbsdpkg.install()
                expected = {
                    "png": {"new": "1.6.23", "old": ""},
                    "ruby": {"new": "2.3.1p1", "old": ""},
                }
                self.assertDictEqual(added, expected)
        expected_calls = [
            call("pkg_add -x -I png--%", output_loglevel="trace", python_shell=False),
            call(
                "pkg_add -x -I ruby--%2.3", output_loglevel="trace", python_shell=False
            ),
            call(
                "pkg_add -x -I vim--gtk2%", output_loglevel="trace", python_shell=False
            ),
        ]
        run_all_mock.assert_has_calls(expected_calls, any_order=True)
        self.assertEqual(run_all_mock.call_count, 3)

    def test_upgrade_available(self):
        """
        Test upgrade_available when an update is available.
        """
        ret = MagicMock(return_value="5.4.2p0")
        with patch("salt.modules.openbsdpkg.latest_version", ret):
            self.assertTrue(openbsdpkg.upgrade_available("zsh"))

    def test_upgrade_not_available(self):
        """
        Test upgrade_available when an update is not available.
        """
        ret = MagicMock(return_value="")
        with patch("salt.modules.openbsdpkg.latest_version", ret):
            self.assertFalse(openbsdpkg.upgrade_available("zsh"))

    def test_upgrade(self):
        """
        Test upgrading packages.
        """
        ret = {}
        pkg_add_u_stdout = [
            "quirks-2.402 signed on 2018-01-02T16:30:59Z",
            "Read shared items: ok",
        ]
        ret["stdout"] = "\n".join(pkg_add_u_stdout)
        ret["retcode"] = 0
        run_all_mock = MagicMock(return_value=ret)
        with patch.dict(openbsdpkg.__salt__, {"cmd.run_all": run_all_mock}):
            with patch("salt.modules.openbsdpkg.list_pkgs", ListPackages()):
                upgraded = openbsdpkg.upgrade()
                expected = {
                    "png": {"new": "1.6.23", "old": ""},
                    "ruby": {"new": "2.3.1p1", "old": ""},
                }
                self.assertDictEqual(upgraded, expected)
