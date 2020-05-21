# -*- coding: utf-8 -*-
"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.mac_brew_pkg as mac_brew
import salt.utils.pkg
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, Mock, patch
from tests.support.unit import TestCase

TAPS_STRING = "homebrew/dupes\nhomebrew/science\nhomebrew/x11"
TAPS_LIST = ["homebrew/dupes", "homebrew/science", "homebrew/x11"]
HOMEBREW_BIN = "/usr/local/bin/brew"


class BrewTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.mac_brew module
    """

    def setup_loader_modules(self):
        return {mac_brew: {"__opts__": {"user": MagicMock(return_value="bar")}}}

    # '_list_taps' function tests: 1

    def test_list_taps(self):
        """
        Tests the return of the list of taps
        """
        mock_taps = MagicMock(return_value={"stdout": TAPS_STRING, "retcode": 0})
        mock_user = MagicMock(return_value="foo")
        mock_cmd = MagicMock(return_value="")
        with patch.dict(
            mac_brew.__salt__,
            {"file.get_user": mock_user, "cmd.run_all": mock_taps, "cmd.run": mock_cmd},
        ):
            self.assertEqual(mac_brew._list_taps(), TAPS_LIST)

    # '_tap' function tests: 3

    def test_tap_installed(self):
        """
        Tests if tap argument is already installed or not
        """
        with patch(
            "salt.modules.mac_brew_pkg._list_taps", MagicMock(return_value=TAPS_LIST)
        ):
            self.assertTrue(mac_brew._tap("homebrew/science"))

    def test_tap_failure(self):
        """
        Tests if the tap installation failed
        """
        mock_failure = MagicMock(
            return_value={"stdout": "", "stderr": "", "retcode": 1}
        )
        mock_user = MagicMock(return_value="foo")
        mock_cmd = MagicMock(return_value="")
        with patch.dict(
            mac_brew.__salt__,
            {
                "cmd.run_all": mock_failure,
                "file.get_user": mock_user,
                "cmd.run": mock_cmd,
            },
        ), patch("salt.modules.mac_brew_pkg._list_taps", MagicMock(return_value={})):
            self.assertFalse(mac_brew._tap("homebrew/test"))

    def test_tap(self):
        """
        Tests adding unofficial GitHub repos to the list of brew taps
        """
        mock_failure = MagicMock(return_value={"retcode": 0})
        mock_user = MagicMock(return_value="foo")
        mock_cmd = MagicMock(return_value="")
        with patch.dict(
            mac_brew.__salt__,
            {
                "cmd.run_all": mock_failure,
                "file.get_user": mock_user,
                "cmd.run": mock_cmd,
            },
        ), patch(
            "salt.modules.mac_brew_pkg._list_taps", MagicMock(return_value=TAPS_LIST)
        ):
            self.assertTrue(mac_brew._tap("homebrew/test"))

    # '_homebrew_bin' function tests: 1

    def test_homebrew_bin(self):
        """
        Tests the path to the homebrew binary
        """
        mock_path = MagicMock(return_value="/usr/local")
        with patch.dict(mac_brew.__salt__, {"cmd.run": mock_path}):
            self.assertEqual(mac_brew._homebrew_bin(), "/usr/local/bin/brew")

    # 'list_pkgs' function tests: 2
    # Only tested a few basics
    # Full functionality should be tested in integration phase

    def test_list_pkgs_removed(self):
        """
        Tests removed implementation
        """
        self.assertEqual(mac_brew.list_pkgs(removed=True), {})

    def test_list_pkgs_versions_true(self):
        """
        Tests if pkg.list_pkgs is already in context and is a list
        """
        mock_context = {"foo": ["bar"]}
        with patch.dict(mac_brew.__context__, {"pkg.list_pkgs": mock_context}):
            self.assertEqual(mac_brew.list_pkgs(versions_as_list=True), mock_context)

    def test_list_pkgs_homebrew_cask_pakages(self):
        """
        Tests if pkg.list_pkgs list properly homebrew cask packages
        """

        def custom_call_brew(cmd, failhard=True):
            result = dict()
            if cmd == "info --json=v1 --installed":
                result = {
                    "stdout": '[{"name":"zsh","full_name":"zsh","oldname":null,'
                    '"aliases":[],"homepage":"https://www.zsh.org/",'
                    '"versions":{"stable":"5.7.1","devel":null,"head":"HEAD","bottle":true},'
                    '"installed":[{"version":"5.7.1","used_options":[],'
                    '"built_as_bottle":true,"poured_from_bottle":true,'
                    '"runtime_dependencies":[{"full_name":"ncurses","version":"6.1"},'
                    '{"full_name":"pcre","version":"8.42"}],'
                    '"installed_as_dependency":false,"installed_on_request":true}]}]',
                    "stderr": "",
                    "retcode": 0,
                }
            elif cmd == "cask list --versions":
                result = {
                    "stdout": "macvim 8.1.151\nfont-firacode-nerd-font 2.0.0",
                    "stderr": "",
                    "retcode": 0,
                }
            elif cmd == "cask info macvim":
                result = {
                    "stdout": "macvim: 8.1.1517,156 (auto_updates)\n"
                    "https://github.com/macvim-dev/macvim\n"
                    "/usr/local/Caskroom/macvim/8.1.151 (64B)\n"
                    "From: https://github.com/Homebrew/homebrew-cask/blob/master/Casks/macvim.rb\n"
                    "==> Name\n"
                    "MacVim",
                    "stderr": "",
                    "retcode": 0,
                }
            elif cmd == "cask info font-firacode-nerd-font":
                result = {
                    "stdout": "font-firacode-nerd-font: 2.0.0\n"
                    "https://github.com/ryanoasis/nerd-fonts\n"
                    "/usr/local/Caskroom/font-firacode-nerd-font/2.0.0 (35 files, 64.8MB)\n"
                    "From: https://github.com/Homebrew/homebrew-cask-fonts/blob/master/Casks/font-firacode-nerd-font.rb\n"
                    "==> Name\n"
                    "FuraCode Nerd Font (FiraCode)",
                    "stderr": "",
                    "retcode": "",
                }

            return result

        def custom_add_pkg(ret, name, newest_version):
            ret[name] = newest_version
            return ret

        expected_pkgs = {
            "zsh": "5.7.1",
            "homebrew/cask/macvim": "8.1.151",
            "homebrew/cask-fonts/font-firacode-nerd-font": "2.0.0",
        }

        with patch(
            "salt.modules.mac_brew_pkg._call_brew", custom_call_brew
        ), patch.dict(
            mac_brew.__salt__,
            {
                "pkg_resource.add_pkg": custom_add_pkg,
                "pkg_resource.sort_pkglist": MagicMock(),
            },
        ):
            self.assertEqual(mac_brew.list_pkgs(versions_as_list=True), expected_pkgs)

    # 'version' function tests: 1

    def test_version(self):
        """
        Tests version name returned
        """
        mock_version = MagicMock(return_value="0.1.5")
        with patch.dict(mac_brew.__salt__, {"pkg_resource.version": mock_version}):
            self.assertEqual(mac_brew.version("foo"), "0.1.5")

    # 'latest_version' function tests: 0
    # It has not been fully implemented

    # 'remove' function tests: 1
    # Only tested a few basics
    # Full functionality should be tested in integration phase

    def test_remove(self):
        """
        Tests if package to be removed exists
        """
        mock_params = MagicMock(return_value=({"foo": None}, "repository"))
        with patch(
            "salt.modules.mac_brew_pkg.list_pkgs", return_value={"test": "0.1.5"}
        ), patch.dict(mac_brew.__salt__, {"pkg_resource.parse_targets": mock_params}):
            self.assertEqual(mac_brew.remove("foo"), {})

    # 'refresh_db' function tests: 2

    def test_refresh_db_failure(self):
        """
        Tests an update of homebrew package repository failure
        """
        mock_user = MagicMock(return_value="foo")
        mock_failure = MagicMock(
            return_value={"stdout": "", "stderr": "", "retcode": 1}
        )
        with patch.dict(
            mac_brew.__salt__, {"file.get_user": mock_user, "cmd.run_all": mock_failure}
        ), patch(
            "salt.modules.mac_brew_pkg._homebrew_bin",
            MagicMock(return_value=HOMEBREW_BIN),
        ):
            with patch.object(salt.utils.pkg, "clear_rtag", Mock()):
                self.assertRaises(CommandExecutionError, mac_brew.refresh_db)

    def test_refresh_db(self):
        """
        Tests a successful update of homebrew package repository
        """
        mock_user = MagicMock(return_value="foo")
        mock_success = MagicMock(return_value={"retcode": 0})
        with patch.dict(
            mac_brew.__salt__, {"file.get_user": mock_user, "cmd.run_all": mock_success}
        ), patch(
            "salt.modules.mac_brew_pkg._homebrew_bin",
            MagicMock(return_value=HOMEBREW_BIN),
        ):
            with patch.object(salt.utils.pkg, "clear_rtag", Mock()):
                self.assertTrue(mac_brew.refresh_db())

    # 'install' function tests: 1
    # Only tested a few basics
    # Full functionality should be tested in integration phase

    def test_install(self):
        """
        Tests if package to be installed exists
        """
        mock_params = MagicMock(return_value=[None, None])
        with patch.dict(mac_brew.__salt__, {"pkg_resource.parse_targets": mock_params}):
            self.assertEqual(mac_brew.install("name=foo"), {})
