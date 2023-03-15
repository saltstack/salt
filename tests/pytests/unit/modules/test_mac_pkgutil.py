import pytest

import salt.modules.mac_pkgutil as mac_pkgutil
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {mac_pkgutil: {}}


def test_install():
    source = "/foo/bar/fubar.pkg"
    package_id = "com.foo.fubar.pkg"

    with patch("salt.modules.mac_pkgutil.is_installed", return_value=False):
        with patch(
            "salt.modules.mac_pkgutil._install_from_path", return_value=True
        ) as _install_from_path:
            mac_pkgutil.install(source, package_id)

    _install_from_path.assert_called_with(source)


def test_install_already_there():
    source = "/foo/bar/fubar.pkg"
    package_id = "com.foo.fubar.pkg"

    with patch("salt.modules.mac_pkgutil.is_installed", return_value=True):
        with patch(
            "salt.modules.mac_pkgutil._install_from_path", return_value=True
        ) as _install_from_path:
            mac_pkgutil.install(source, package_id)

    assert _install_from_path.called == 0
