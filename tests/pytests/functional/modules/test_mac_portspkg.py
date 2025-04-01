"""
integration tests for mac_ports
"""

import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
    pytest.mark.skip_if_binaries_missing("port"),
]


@pytest.fixture(scope="module")
def pkg(modules):
    return modules.pkg


@pytest.fixture
def uninstalled_pkg_name(pkg):
    pkgname = installed_pkg_name
    try:
        pkg.refresh_db()
        yield pkgname
    finally:
        if pkgname in pkg.list_pkgs():
            pkg.remove(pkgname)


@pytest.fixture
def installed_pkg_name(uninstalled_pkg_name):
    pkg.install(uninstalled_pkg_name)
    return uninstalled_pkg_name


@pytest.fixture(scope="function", autouse=True)
def _setup_teardown_vars(pkg):
    AGREE_INSTALLED = False
    try:
        ret = pkg.list_pkgs()
        AGREE_INSTALLED = installed_pkg_name in ret
        pkg.refresh_db()
        yield
    finally:
        if AGREE_INSTALLED:
            pkg.remove(installed_pkg_name)


def test_list_pkgs(pkg, installed_pkg_name):
    """
    Test pkg.list_pkgs
    """
    pkg_list_ret = pkg.list_pkgs()
    assert isinstance(pkg_list_ret, dict)
    assert installed_pkg_name in pkg_list_ret


def test_latest_version(pkg, installed_pkg_name):
    """
    Test pkg.latest_version
    """
    result = pkg.latest_version(installed_pkg_name, refresh=False)
    assert isinstance(result, dict)
    assert installed_pkg_name in result.data


def test_remove(pkg, installed_pkg_name):
    """
    Test pkg.remove
    """
    ret = pkg.remove(installed_pkg_name)
    assert isinstance(ret, dict)
    assert installed_pkg_name in ret


@pytest.mark.destructive_test
def test_install(pkg, uninstalled_pkg_name):
    """
    Test pkg.install
    """
    ret = pkg.install(uninstalled_pkg_name)
    assert isinstance(ret, dict)
    assert uninstalled_pkg_name in ret


def test_list_upgrades_type(pkg):
    """
    Test pkg.list_upgrades return type
    """
    ret = pkg.list_upgrades(refresh=False)
    assert isinstance(ret, dict)


def test_upgrade_available(pkg, installed_pkg_name):
    """
    Test pkg.upgrade_available
    """
    ret = pkg.upgrade_available(installed_pkg_name, refresh=False)
    assert not ret.data


def test_refresh_db(pkg):
    """
    Test pkg.refresh_db
    """
    ret = pkg.refresh_db()
    assert ret


def test_upgrade(pkg):
    """
    Test pkg.upgrade
    """
    ret = pkg.upgrade(refresh=False)
    assert isinstance(ret, dict)
    assert ret.data["result"]
