"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
    :codeauthor: Gareth J. Greenaway <greenaway@vmware.com>
"""

import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
    pytest.mark.skip_if_binaries_missing("brew"),
]


@pytest.fixture(scope="module")
def pkg(modules):
    return modules.pkg


# Brew doesn't support local package installation - So, let's
# Grab some small packages available online for brew


@pytest.fixture(scope="function")
def add_pkg():
    yield "algol68g"


@pytest.fixture(scope="function")
def del_pkg():
    yield "acme"


@pytest.fixture(scope="function", autouse=True)
def _setup_teardown_vars(pkg, add_pkg, del_pkg):
    try:
        yield
    finally:
        pkg_list = pkg.list_pkgs()

        # Remove any installed packages
        if add_pkg in pkg_list:
            pkg.remove(add_pkg)
        if del_pkg in pkg_list:
            pkg.remove(del_pkg)


def test_brew_install(pkg, add_pkg):
    """
    Tests the installation of packages
    """
    pkg.install(add_pkg)
    pkg_list = pkg.list_pkgs()
    assert add_pkg in pkg_list


def test_remove(pkg, del_pkg):
    """
    Tests the removal of packages
    """
    # Install a package to delete - If unsuccessful, skip the test
    pkg.install(del_pkg)
    pkg_list = pkg.list_pkgs()
    if del_pkg not in pkg_list:
        pkg.install(del_pkg)
        pytest.skip("Failed to install a package to delete")

    # Now remove the installed package
    pkg.remove(del_pkg)
    del_list = pkg.list_pkgs()
    assert del_pkg not in del_list


def test_version(pkg, add_pkg):
    """
    Test pkg.version for mac. Installs a package and then checks we can get
    a version for the installed package.
    """
    pkg.install(add_pkg)
    pkg_list = pkg.list_pkgs()
    version = pkg.version(add_pkg)
    assert version, f"version: {version} is empty, or other issue is present"
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


def test_latest_version(pkg, add_pkg):
    """
    Test pkg.latest_version:
      - get the latest version available
      - install the package
      - get the latest version available
      - check that the latest version is empty after installing it
    """
    pkg.remove(add_pkg)
    uninstalled_latest = pkg.latest_version(add_pkg)

    pkg.install(add_pkg)
    installed_latest = pkg.latest_version(add_pkg)
    version = pkg.version(add_pkg)
    assert isinstance(uninstalled_latest, str)
    assert installed_latest == version


def test_refresh_db(pkg):
    """
    Integration test to ensure pkg.refresh_db works with brew
    """
    refresh_brew = pkg.refresh_db()
    assert refresh_brew


def test_list_upgrades(pkg, add_pkg):
    """
    Test pkg.list_upgrades: data is in the form {'name1': 'version1',
    'name2': 'version2', ... }
    """
    upgrades = pkg.list_upgrades()
    assert isinstance(upgrades, dict)
    if upgrades:
        for name in upgrades:
            assert isinstance(name, str)
            assert isinstance(upgrades[name], str)


def test_info_installed(pkg, add_pkg):
    """
    Test pkg.info_installed: info returned has certain fields used by
    mac_brew.latest_version
    """
    pkg.install(add_pkg)
    info = pkg.info_installed(add_pkg)
    assert add_pkg in info
    assert "versions" in info[add_pkg]
    assert "revision" in info[add_pkg]
    assert "stable" in info[add_pkg]["versions"]
