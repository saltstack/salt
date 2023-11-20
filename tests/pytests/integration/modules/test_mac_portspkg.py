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


@pytest.fixture(scope="function", autouse=True)
def _setup_teardown_vars(salt_call_cli):
    AGREE_INSTALLED = False
    try:
        ret = salt_call_cli.run("pkg.list_pkgs")
        AGREE_INSTALLED = "agree" in ret.data
        salt_call_cli.run("pkg.refresh_db")
        yield
    finally:
        if AGREE_INSTALLED:
            salt_call_cli.run("pkg.remove", "agree")


def test_list_pkgs(salt_call_cli):
    """
    Test pkg.list_pkgs
    """
    salt_call_cli.run("pkg.install", "agree")
    pkg_list_ret = salt_call_cli.run("pkg.list_pkgs")
    assert isinstance(pkg_list_ret.data, dict)
    assert "agree" in pkg_list_ret.data


def test_latest_version(salt_call_cli):
    """
    Test pkg.latest_version
    """
    salt_call_cli.run("pkg.install", "agree")
    result = salt_call_cli.run("pkg.latest_version", "agree", refresh=False)
    assert isinstance(result.data, dict)
    assert "agree" in result.data


def test_remove(salt_call_cli):
    """
    Test pkg.remove
    """
    salt_call_cli.run("pkg.install", "agree")
    removed = salt_call_cli.run("pkg.remove", "agree")
    assert isinstance(removed.data, dict)
    assert "agree" in removed.data


@pytest.mark.destructive_test
def test_install(salt_call_cli):
    """
    Test pkg.install
    """
    salt_call_cli.run("pkg.remove", "agree")
    installed = salt_call_cli.run("pkg.install", "agree")
    assert isinstance(installed.data, dict)
    assert "agree" in installed.data


def test_list_upgrades(salt_call_cli):
    """
    Test pkg.list_upgrades
    """
    upgrade = salt_call_cli.run("pkg.list_upgrades", refresh=False)
    assert isinstance(upgrade.data, dict)


def test_upgrade_available(salt_call_cli):
    """
    Test pkg.upgrade_available
    """
    salt_call_cli.run("pkg.install", "agree")
    upgrade_available = salt_call_cli.run(
        "pkg.upgrade_available", "agree", refresh=False
    )
    assert not upgrade_available.data


def test_refresh_db(salt_call_cli):
    """
    Test pkg.refresh_db
    """
    refresh = salt_call_cli.run("pkg.refresh_db")
    assert refresh.data


def test_upgrade(salt_call_cli):
    """
    Test pkg.upgrade
    """
    results = salt_call_cli.run("pkg.upgrade", refresh=False)
    assert isinstance(results.data, dict)
    assert results.data["result"]
