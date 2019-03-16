# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import salt module
import salt.modules.mac_pkgutil as mac_pkgutil

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MacPkgutilTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {mac_pkgutil: {}}

    def test_install(self):
        # Given
        source = '/foo/bar/fubar.pkg'
        package_id = 'com.foo.fubar.pkg'

        # When
        with patch('salt.modules.mac_pkgutil.is_installed',
                   return_value=False):
            with patch('salt.modules.mac_pkgutil._install_from_path',
                       return_value=True) as _install_from_path:
                mac_pkgutil.install(source, package_id)

        # Then
        _install_from_path.assert_called_with(source)

    def test_install_already_there(self):
        # Given
        source = '/foo/bar/fubar.pkg'
        package_id = 'com.foo.fubar.pkg'

        # When
        with patch('salt.modules.mac_pkgutil.is_installed',
                   return_value=True):
            with patch('salt.modules.mac_pkgutil._install_from_path',
                       return_value=True) as _install_from_path:
                mac_pkgutil.install(source, package_id)

        # Then
        self.assertEqual(_install_from_path.called, 0)
