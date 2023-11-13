"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import pytest

from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
    pytest.mark.skip_if_binaries_missing("brew"),
]

# Brew doesn't support local package installation - So, let's
# Grab some small packages available online for brew


@pytest.fixture(scope="function")
def add_pkg():
    yield "algol68g"


@pytest.fixture(scope="function")
def del_pkg():
    yield "acme"


@pytest.fixture(scope="function")
def setup_teardown_vars(salt_call_cli, add_pkg, del_pkg):
    try:
        yield
    finally:
        ret = salt_call_cli.run("pkg.list_pkgs")
        pkg_list = ret.data

        # Remove any installed packages
        if add_pkg in pkg_list:
            salt_call_cli.run("pkg.remove", add_pkg)
        if del_pkg in pkg_list:
            salt_call_cli.run("pkg.remove", del_pkg)


def test_brew_install(salt_call_cli, add_pkg, setup_teardown_vars):
    """
    Tests the installation of packages
    """
    try:
        salt_call_cli.run("pkg.install", add_pkg)
        ret = salt_call_cli.run("pkg.list_pkgs")
        pkg_list = ret.data
        try:
            assert add_pkg in pkg_list
        except AssertionError:
            salt_call_cli.run("pkg.remove", add_pkg)
            raise
    except CommandExecutionError:
        salt_call_cli.run("pkg.remove", add_pkg)
        raise


def test_remove(salt_call_cli, del_pkg, setup_teardown_vars):
    """
    Tests the removal of packages
    """
    try:
        # Install a package to delete - If unsuccessful, skip the test
        salt_call_cli.run("pkg.install", del_pkg)
        ret = salt_call_cli.run("pkg.list_pkgs")
        pkg_list = ret.data
        if del_pkg not in pkg_list:
            salt_call_cli.run("pkg.install", del_pkg)
            pytest.skip("Failed to install a package to delete")

        # Now remove the installed package
        salt_call_cli.run("pkg.remove", del_pkg)
        ret = salt_call_cli.run("pkg.list_pkgs")
        del_list = ret.data
        assert del_pkg not in del_list
    except CommandExecutionError:
        salt_call_cli.run("pkg.remove", del_pkg)
        raise


def test_version(salt_call_cli, add_pkg, setup_teardown_vars):
    """
    Test pkg.version for mac. Installs a package and then checks we can get
    a version for the installed package.
    """
    try:
        salt_call_cli.run("pkg.install", add_pkg)
        ret = salt_call_cli.run("pkg.list_pkgs")
        pkg_list = ret.data
        ret = salt_call_cli.run("pkg.version", add_pkg)
        version = ret.data
        try:
            assert version, "version: {} is empty, or other issue is present".format(
                version
            )
            assert (
                add_pkg in pkg_list
            ), "package: {} is not in the list of installed packages: {}".format(
                add_pkg, pkg_list
            )
            # make sure the version is accurate and is listed in the pkg_list
            assert version in str(
                pkg_list[add_pkg]
            ), "The {} version: {} is not listed in the pkg_list: {}".format(
                add_pkg, version, pkg_list[add_pkg]
            )
        except AssertionError:
            salt_call_cli.run("pkg.remove", add_pkg)
            raise
    except CommandExecutionError:
        salt_call_cli.run("pkg.remove", add_pkg)
        raise


def test_latest_version(salt_call_cli, add_pkg, setup_teardown_vars):
    """
    Test pkg.latest_version:
      - get the latest version available
      - install the package
      - get the latest version available
      - check that the latest version is empty after installing it
    """
    try:
        salt_call_cli.run("pkg.remove", add_pkg)
        uninstalled_latest = salt_call_cli.run("pkg.latest_version", add_pkg)

        salt_call_cli.run("pkg.install", add_pkg)
        installed_latest = salt_call_cli.run("pkg.latest_version", add_pkg)
        version = salt_call_cli.run("pkg.version", add_pkg)
        try:
            assert isinstance(uninstalled_latest.data, str)
            assert installed_latest.data == version.data
        except AssertionError:
            salt_call_cli.run("pkg.remove", add_pkg)
            raise
    except CommandExecutionError:
        salt_call_cli.run("pkg.remove", add_pkg)
        raise


def test_refresh_db(salt_call_cli, setup_teardown_vars):
    """
    Integration test to ensure pkg.refresh_db works with brew
    """
    refresh_brew = salt_call_cli.run("pkg.refresh_db")
    assert refresh_brew.data


def test_list_upgrades(salt_call_cli, add_pkg, setup_teardown_vars):
    """
    Test pkg.list_upgrades: data is in the form {'name1': 'version1',
    'name2': 'version2', ... }
    """
    try:
        ret = salt_call_cli.run("pkg.list_upgrades")
        upgrades = ret.data
        try:
            assert isinstance(upgrades, dict)
            if upgrades:
                for name in upgrades:
                    assert isinstance(name, str)
                    assert isinstance(upgrades[name], str)
        except AssertionError:
            salt_call_cli.run("pkg.remove", add_pkg)
            raise
    except CommandExecutionError:
        salt_call_cli.run("pkg.remove", add_pkg)
        raise


def test_info_installed(salt_call_cli, add_pkg, setup_teardown_vars):
    """
    Test pkg.info_installed: info returned has certain fields used by
    mac_brew.latest_version
    """
    try:
        salt_call_cli.run("pkg.install", add_pkg)
        ret = salt_call_cli.run("pkg.info_installed", add_pkg)
        info = ret.data
        try:
            assert add_pkg in info
            assert "versions" in info[add_pkg]
            assert "revision" in info[add_pkg]
            assert "stable" in info[add_pkg]["versions"]
        except AssertionError:
            salt_call_cli.run("pkg.remove", add_pkg)
            raise
    except CommandExecutionError:
        salt_call_cli.run("pkg.remove", add_pkg)
        raise
