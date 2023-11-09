"""
integration tests for mac_ports
"""

import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="function")
def setup_teardown_vars(salt_call_cli):
    AGREE_INSTALLED = False
    try:
        AGREE_INSTALLED = "agree" in salt_call_cli.run("pkg.list_pkgs")
        salt_call_cli.run("pkg.refresh_db")
        yield
    finally:
        if AGREE_INSTALLED:
            salt_call_cli.run("pkg.remove", "agree")


def test_list_pkgs(salt_call_cli, setup_teardown_vars):
    """
    Test pkg.list_pkgs
    """
    salt_call_cli.run("pkg.install", "agree")
    assert isinstance(salt_call_cli.run("pkg.list_pkgs"), dict)
    assert "agree" in salt_call_cli.run("pkg.list_pkgs")


def test_latest_version(salt_call_cli, setup_teardown_vars):
    """
    Test pkg.latest_version
    """
    salt_call_cli.run("pkg.install", "agree")
    result = salt_call_cli.run("pkg.latest_version", "agree", refresh=False)
    assert isinstance(result, dict)
    assert "agree" in result


def test_remove(salt_call_cli, setup_teardown_vars):
    """
    Test pkg.remove
    """
    salt_call_cli.run("pkg.install", "agree")
    removed = salt_call_cli.run("pkg.remove", "agree")
    assert isinstance(removed, dict)
    assert "agree" in removed


@pytest.mark.destructive_test
def test_install(salt_call_cli, setup_teardown_vars):
    """
    Test pkg.install
    """
    salt_call_cli.run("pkg.remove", "agree")
    installed = salt_call_cli.run("pkg.install", "agree")
    assert isinstance(installed, dict)
    assert "agree" in installed


def test_list_upgrades(salt_call_cli, setup_teardown_vars):
    """
    Test pkg.list_upgrades
    """
    assert isinstance(salt_call_cli.run("pkg.list_upgrades", refresh=False), dict)


def test_upgrade_available(salt_call_cli, setup_teardown_vars):
    """
    Test pkg.upgrade_available
    """
    salt_call_cli.run("pkg.install", "agree")
    assert not salt_call_cli.run("pkg.upgrade_available", "agree", refresh=False)


def test_refresh_db(salt_call_cli, setup_teardown_vars):
    """
    Test pkg.refresh_db
    """
    assert salt_call_cli.run("pkg.refresh_db")


def test_upgrade(salt_call_cli, setup_teardown_vars):
    """
    Test pkg.upgrade
    """
    results = salt_call_cli.run("pkg.upgrade", refresh=False)
    assert isinstance(results, dict)
    assert results["result"]
