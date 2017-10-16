# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import salt module
from salt.modules import mac_pkgutil

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, patch


mac_pkgutil.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MacPkgutilTestCase(TestCase):

    def test_install(self):
        # Given
        source = "/foo/bar/fubar.pkg"
        package_id = "com.foo.fubar.pkg"

        # When
        with patch("salt.modules.mac_pkgutil.is_installed",
                   return_value=False):
            with patch("salt.modules.mac_pkgutil._install_from_path",
                       return_value=True) as _install_from_path:
                mac_pkgutil.install(source, package_id)

        # Then
        _install_from_path.assert_called_with(source)

    def test_install_already_there(self):
        # Given
        source = "/foo/bar/fubar.pkg"
        package_id = "com.foo.fubar.pkg"

        # When
        with patch("salt.modules.mac_pkgutil.is_installed",
                   return_value=True):
            with patch("salt.modules.mac_pkgutil._install_from_path",
                       return_value=True) as _install_from_path:
                mac_pkgutil.install(source, package_id)

        # Then
        self.assertEqual(_install_from_path.called, 0)
