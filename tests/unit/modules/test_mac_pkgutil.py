import salt.modules.mac_pkgutil as mac_pkgutil
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase


class MacPkgutilTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {mac_pkgutil: {}}

    def test_install(self):
        # Given
        source = "/foo/bar/fubar.pkg"
        package_id = "com.foo.fubar.pkg"

        # When
        with patch("salt.modules.mac_pkgutil.is_installed", return_value=False):
            with patch(
                "salt.modules.mac_pkgutil._install_from_path", return_value=True
            ) as _install_from_path:
                mac_pkgutil.install(source, package_id)

        # Then
        _install_from_path.assert_called_with(source)

    def test_install_already_there(self):
        # Given
        source = "/foo/bar/fubar.pkg"
        package_id = "com.foo.fubar.pkg"

        # When
        with patch("salt.modules.mac_pkgutil.is_installed", return_value=True):
            with patch(
                "salt.modules.mac_pkgutil._install_from_path", return_value=True
            ) as _install_from_path:
                mac_pkgutil.install(source, package_id)

        # Then
        self.assertEqual(_install_from_path.called, 0)
