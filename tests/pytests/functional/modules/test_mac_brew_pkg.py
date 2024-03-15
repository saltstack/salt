"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
    :codeauthor: Gareth J. Greenaway <greenaway@vmware.com>
"""

import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.timeout(120),
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
    pytest.mark.skip_if_binaries_missing("brew"),
]


@pytest.fixture(scope="module")
def pkg(modules):
    return modules.pkg


@pytest.fixture
def pkg_1_name(pkg):
    pkg_name = "algol68g"
    try:
        yield pkg_name
    finally:
        pkg_list = pkg.list_pkgs()

        # Remove package if installed
        if pkg_name in pkg_list:
            pkg.remove(pkg_name)


@pytest.fixture
def pkg_2_name(pkg):
    pkg_name = "acme"
    try:
        pkg.install(pkg_name)
        pkg_list = pkg.list_pkgs()
        if pkg_name not in pkg_list:
            pytest.skip(f"Failed to install the '{pkg_name}' package to delete")
        yield pkg_name
    finally:
        pkg_list = pkg.list_pkgs()

        # Remove package if still installed
        if pkg_name in pkg_list:
            pkg.remove(pkg_name)


def test_brew_install(pkg, pkg_1_name):
    """
    Tests the installation of packages
    """
    pkg.install(pkg_1_name)
    pkg_list = pkg.list_pkgs()
    assert pkg_1_name in pkg_list


def test_remove(pkg, pkg_2_name):
    """
    Tests the removal of packages
    """
    pkg.remove(pkg_2_name)
    pkg_list = pkg.list_pkgs()
    assert pkg_2_name not in pkg_list


def test_version(pkg, pkg_1_name):
    """
    Test pkg.version for mac. Installs a package and then checks we can get
    a version for the installed package.
    """
    pkg.install(pkg_1_name)
    pkg_list = pkg.list_pkgs()
    version = pkg.version(pkg_1_name)
    assert version
    assert pkg_1_name in pkg_list
    # make sure the version is accurate and is listed in the pkg_list
    assert version in str(pkg_list[pkg_1_name])


def test_latest_version(pkg, pkg_1_name):
    """
    Test pkg.latest_version:
      - get the latest version available
      - install the package
      - get the latest version available
      - check that the latest version is empty after installing it
    """
    pkg.remove(pkg_1_name)
    uninstalled_latest = pkg.latest_version(pkg_1_name)

    pkg.install(pkg_1_name)
    installed_latest = pkg.latest_version(pkg_1_name)
    version = pkg.version(pkg_1_name)
    assert isinstance(uninstalled_latest, str)
    assert installed_latest == version


def test_refresh_db(pkg):
    """
    Integration test to ensure pkg.refresh_db works with brew
    """
    refresh_brew = pkg.refresh_db()
    assert refresh_brew


def test_list_upgrades(pkg, pkg_1_name):
    """
    Test pkg.list_upgrades: data is in the form {'name1': 'version1', 'name2': 'version2', ... }
    """
    upgrades = pkg.list_upgrades()
    assert isinstance(upgrades, dict)
    if upgrades:
        for name in upgrades:
            assert isinstance(name, str)
            assert isinstance(upgrades[name], str)


def test_info_installed(pkg, pkg_1_name):
    """
    Test pkg.info_installed: info returned has certain fields used by
    mac_brew.latest_version
    """
    pkg.install(pkg_1_name)
    info = pkg.info_installed(pkg_1_name)
    assert pkg_1_name in info
    assert "versions" in info[pkg_1_name]
    assert "revision" in info[pkg_1_name]
    assert "stable" in info[pkg_1_name]["versions"]
