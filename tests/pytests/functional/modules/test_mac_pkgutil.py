"""
integration tests for mac_pkgutil
"""

import shutil

import pytest

from salt.exceptions import SaltInvocationError

pytestmark = [
    pytest.mark.timeout(120, func_only=True),
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
    pytest.mark.skip_if_binaries_missing("pkgutil"),
]


@pytest.fixture(scope="module")
def pkgutil(modules):
    return modules.pkgutil


@pytest.fixture
def macports_package_name(pkgutil):
    pacakge_name = "org.macports.MacPorts"
    try:
        yield pacakge_name
    finally:
        try:
            pkgutil.forget(pacakge_name)
        except Exception:  # pylint: disable=broad-except
            pass
        shutil.rmtree("/opt/local", ignore_errors=True)


@pytest.fixture(scope="module")
def macports_package_filename(grains):
    if grains["osrelease_info"][0] == 12:
        return "MacPorts-2.7.2-12-Monterey.pkg"
    if grains["osrelease_info"][0] == 11:
        return "MacPorts-2.7.2-11-BigSur.pkg"
    if grains["osrelease_info"][:2] == (10, 15):
        return "MacPorts-2.7.2-10.15-Catalina.pkg"
    pytest.fail(
        "Don't know how to handle '{}'. Please fix the test".format(grains["osfinger"])
    )


@pytest.fixture(scope="module")
def macports_package_url(macports_package_filename):
    return "https://distfiles.macports.org/MacPorts/{}".format(
        macports_package_filename
    )


@pytest.fixture(scope="module")
def pkg_name(grains):
    if grains["osrelease_info"][0] >= 13:
        return "com.apple.pkg.CLTools_SDK_macOS13"
    if grains["osrelease_info"][0] >= 12:
        return "com.apple.pkg.XcodeSystemResources"
    if grains["osrelease_info"][0] >= 11:
        return "com.apple.pkg.InstallAssistant.macOSBigSur"
    if grains["osrelease_info"][:2] == (10, 15):
        return "com.apple.pkg.iTunesX"
    pytest.fail(
        "Don't know how to handle '{}'. Please fix the test".format(grains["osfinger"])
    )


def test_list(pkgutil, pkg_name):
    """
    Test pkgutil.list
    """
    packages_list = pkgutil.list()
    assert isinstance(packages_list, list)
    assert pkg_name in packages_list


def test_is_installed(pkgutil, pkg_name):
    """
    Test pkgutil.is_installed
    """
    # Test Package is installed
    assert pkgutil.is_installed(pkg_name)

    # Test Package is not installed
    assert not pkgutil.is_installed("spongebob")


@pytest.mark.skip(
    reason="I don't know how to fix this test. Pedro(s0undt3ch), 2022-04-08"
)
def test_install_forget(
    tmp_path,
    modules,
    pkgutil,
    macports_package_name,
    macports_package_filename,
    macports_package_url,
):
    """
    Test pkgutil.install
    Test pkgutil.forget
    """
    pkg_local_path = str(tmp_path / macports_package_filename)

    # Test if installed
    assert not pkgutil.is_installed(macports_package_name)

    # Download the package
    modules.cp.get_url(macports_package_url, pkg_local_path)

    # Test install
    assert pkgutil.install(pkg_local_path, macports_package_name)
    assert pkgutil.is_installed(macports_package_name)

    # Test forget
    assert pkgutil.forget(macports_package_name)


def test_install_unsupported_scheme(pkgutil):
    with pytest.raises(SaltInvocationError) as exc:
        pkgutil.install("ftp://test", "spongebob")
    assert "Unsupported scheme" in str(exc.value)
