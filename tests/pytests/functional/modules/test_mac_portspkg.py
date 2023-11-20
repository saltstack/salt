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


@pytest.fixture(scope="function", autouse=True)
def _setup_teardown_vars(pkg):
    AGREE_INSTALLED = False
    try:
        ret = pkg.list_pkgs()
        AGREE_INSTALLED = "agree" in ret
        pkg.refresh_db()
        yield
    finally:
        if AGREE_INSTALLED:
            pkg.remove("agree")


def test_list_pkgs(pkg):
    """
    Test pkg.list_pkgs
    """
    pkg.install("agree")
    pkg_list_ret = pkg.list_pkgs()
    assert isinstance(pkg_list_ret, dict)
    assert "agree" in pkg_list_ret


def test_latest_version(pkg):
    """
    Test pkg.latest_version
    """
    pkg.install("agree")
    result = pkg.latest_version("agree", refresh=False)
    assert isinstance(result, dict)
    assert "agree" in result.data


def test_remove(pkg):
    """
    Test pkg.remove
    """
    pkg.install("agree")
    removed = pkg.remove("agree")
    assert isinstance(removed, dict)
    assert "agree" in removed


@pytest.mark.destructive_test
def test_install(pkg):
    """
    Test pkg.install
    """
    pkg.remove("agree")
    installed = pkg.install("agree")
    assert isinstance(installed, dict)
    assert "agree" in installed


def test_list_upgrades(pkg):
    """
    Test pkg.list_upgrades
    """
    upgrade = pkg.list_upgrades(refresh=False)
    assert isinstance(upgrade, dict)


def test_upgrade_available(pkg):
    """
    Test pkg.upgrade_available
    """
    pkg.install("agree")
    upgrade_available = pkg.upgrade_available("agree", refresh=False)
    assert not upgrade_available.data


def test_refresh_db(pkg):
    """
    Test pkg.refresh_db
    """
    refresh = pkg.refresh_db()
    assert refresh


def test_upgrade(pkg):
    """
    Test pkg.upgrade
    """
    results = pkg.upgrade(refresh=False)
    assert isinstance(results, dict)
    assert results.data["result"]
