# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import salt module
from salt.modules import darwin_pkgutil

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch


darwin_pkgutil.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DarwingPkgutilTestCase(TestCase):
    def test_list_installed_command(self):
        # Given
        r_output = "com.apple.pkg.iTunes"

        # When
        mock_cmd = MagicMock(return_value=r_output)
        with patch.dict(darwin_pkgutil.__salt__, {'cmd.run_stdout': mock_cmd}):
            output = darwin_pkgutil.list_()

        # Then
        mock_cmd.assert_called_with("/usr/sbin/pkgutil --pkgs")

    def test_list_installed_output(self):
        # Given
        r_output = "com.apple.pkg.iTunes"

        # When
        mock_cmd = MagicMock(return_value=r_output)
        with patch.dict(darwin_pkgutil.__salt__, {'cmd.run_stdout': mock_cmd}):
            output = darwin_pkgutil.list_()

        # Then
        self.assertEqual(output, r_output)

    def test_is_installed(self):
        # Given
        r_output = "com.apple.pkg.iTunes"

        # When
        mock_cmd = MagicMock(return_value=r_output)
        with patch.dict(darwin_pkgutil.__salt__, {'cmd.run_stdout': mock_cmd}):
            ret = darwin_pkgutil.is_installed("com.apple.pkg.iTunes")

        # Then
        self.assertTrue(ret)

        # When
        with patch.dict(darwin_pkgutil.__salt__, {'cmd.run_stdout': mock_cmd}):
            ret = darwin_pkgutil.is_installed("com.apple.pkg.Safari")

        # Then
        self.assertFalse(ret)

    def test_install(self):
        # Given
        source = "/foo/bar/fubar.pkg"
        package_id = "com.foo.fubar.pkg"

        # When
        mock_cmd = MagicMock(return_value=True)
        with patch("salt.modules.darwin_pkgutil.is_installed",
                   return_value=False) as is_installed:
            with patch("salt.modules.darwin_pkgutil._install_from_path",
                   return_value=True) as _install_from_path:
                ret = darwin_pkgutil.install(source, package_id)

        # Then
        _install_from_path.assert_called_with(source)

    def test_install_already_there(self):
        # Given
        source = "/foo/bar/fubar.pkg"
        package_id = "com.foo.fubar.pkg"

        # When
        mock_cmd = MagicMock(return_value=True)
        with patch("salt.modules.darwin_pkgutil.is_installed",
                   return_value=True) as is_installed:
            with patch("salt.modules.darwin_pkgutil._install_from_path",
                   return_value=True) as _install_from_path:
                ret = darwin_pkgutil.install(source, package_id)

        # Then
        self.assertEqual(_install_from_path.called, 0)
