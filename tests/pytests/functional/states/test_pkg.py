"""
tests for pkg state
"""

import logging
import os
import subprocess
import time

import pytest

import salt.utils.files
import salt.utils.path
import salt.utils.pkg.rpm
import salt.utils.platform

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.destructive_test,
    pytest.mark.windows_whitelisted,
    pytest.mark.timeout_unless_on_windows(240),
]


@pytest.fixture(scope="module", autouse=True)
def refresh_db(grains, modules):

    if salt.utils.platform.is_windows():
        modules.winrepo.update_git_repos()

    modules.pkg.refresh_db()

    # If this is Arch Linux, check if pacman is in use by another process
    if grains["os_family"] == "Arch":
        for _ in range(12):
            if not os.path.isfile("/var/lib/pacman/db.lck"):
                break
            else:
                time.sleep(5)
        else:
            pytest.fail("Package database locked after 60 seconds, bailing out")


@pytest.fixture(scope="module", autouse=True)
def refresh_keys(grains, modules):
    if grains["os_family"] == "Arch":
        # We should be running this periodically when building new test runner
        # images, otherwise this could take several minutes to complete.
        proc = subprocess.run(["pacman-key", "--refresh-keys"], check=False)
        if proc.returncode != 0:
            pytest.fail("pacman-key --refresh-keys command failed.")


@pytest.fixture
def PKG_TARGETS(grains):
    _PKG_TARGETS = ["figlet", "sl"]
    if grains["os"] == "Windows":
        _PKG_TARGETS = ["npp_x64", "winrar"]
    elif grains["os"] == "Amazon":
        if grains["osfinger"] == "Amazon Linux-2023":
            _PKG_TARGETS = ["lynx", "gnuplot-minimal"]
        else:
            _PKG_TARGETS = ["lynx", "gnuplot"]
    elif grains["os_family"] == "RedHat":
        if grains["os"] == "VMware Photon OS":
            if grains["osmajorrelease"] >= 5:
                _PKG_TARGETS = ["wget", "zsh"]
            else:
                _PKG_TARGETS = ["wget", "zsh-html"]
        elif (
            grains["os"] in ("CentOS Stream", "Rocky", "AlmaLinux")
            and grains["osmajorrelease"] == 9
        ):
            _PKG_TARGETS = ["units", "zsh"]
        else:
            _PKG_TARGETS = ["units", "zsh-html"]
    elif grains["os_family"] == "Suse":
        _PKG_TARGETS = ["lynx", "htop"]
    return _PKG_TARGETS


@pytest.fixture
def PKG_CAP_TARGETS(grains):
    _PKG_CAP_TARGETS = []
    if grains["os_family"] == "Suse":
        if grains["os"] == "SUSE":
            _PKG_CAP_TARGETS = [("perl(YAML)", "perl-YAML")]
            # sudo zypper install 'perl(YAML)'
            # Loading repository data...
            # Reading installed packages...
            # 'perl(YAML)' not found in package names. Trying capabilities.
            # Resolving package dependencies...
            #
            # The following NEW package is going to be installed:
            #   perl-YAML
            #
            # 1 new package to install.
            # Overall download size: 85.3 KiB. Already cached: 0 B. After the operation, additional 183.3 KiB will be used.
            # Continue? [y/n/v/...? shows all options] (y):

            # So, it just doesn't work here? skip it for now
            _PKG_CAP_TARGETS.clear()
    if not _PKG_CAP_TARGETS:
        pytest.skip("Capability not provided")
    return _PKG_CAP_TARGETS


@pytest.fixture
def PKG_32_TARGETS(grains):
    _PKG_32_TARGETS = []
    if grains["os_family"] == "RedHat" and grains["oscodename"] != "Photon":
        if grains["os"] == "CentOS":
            if grains["osmajorrelease"] == 5:
                _PKG_32_TARGETS = ["xz-devel.i386"]
            else:
                _PKG_32_TARGETS.append("xz-devel.i686")
    elif grains["os"] == "Windows":
        _PKG_32_TARGETS = ["npp", "putty"]
    if not _PKG_32_TARGETS:
        pytest.skip("No 32 bit packages have been specified for testing")
    return _PKG_32_TARGETS


@pytest.fixture
def PKG_DOT_TARGETS(grains):
    _PKG_DOT_TARGETS = []
    if grains["os_family"] == "RedHat" and grains["oscodename"] != "Photon":
        if grains["osmajorrelease"] == 7:
            _PKG_DOT_TARGETS = ["tomcat-el-2.2-api"]
        elif grains["osmajorrelease"] == 8:
            _PKG_DOT_TARGETS = ["aspnetcore-runtime-6.0"]
    if not _PKG_DOT_TARGETS:
        pytest.skip(
            'No packages with "." in their name have been specified',
        )
    return _PKG_DOT_TARGETS


@pytest.fixture
def PKG_EPOCH_TARGETS(grains):
    _PKG_EPOCH_TARGETS = []
    if grains["os_family"] == "RedHat" and grains["oscodename"] != "Photon":
        if grains["osmajorrelease"] == 7:
            _PKG_EPOCH_TARGETS = ["comps-extras"]
        elif grains["osmajorrelease"] == 8:
            _PKG_EPOCH_TARGETS = ["traceroute"]
    if not _PKG_EPOCH_TARGETS:
        pytest.skip('No targets have been configured with "epoch" in the version')
    return _PKG_EPOCH_TARGETS


@pytest.fixture
def VERSION_SPEC_SUPPORTED(grains):
    _VERSION_SPEC_SUPPORTED = True
    if grains["os"] == "FreeBSD":
        _VERSION_SPEC_SUPPORTED = False
    if not _VERSION_SPEC_SUPPORTED:
        pytest.skip("Version specification not supported")
    return _VERSION_SPEC_SUPPORTED


@pytest.fixture
def WILDCARDS_SUPPORTED(grains):
    _WILDCARDS_SUPPORTED = False
    if grains["os_family"] in ("Arch", "Debian"):
        _WILDCARDS_SUPPORTED = True
    if not _WILDCARDS_SUPPORTED:
        pytest.skip("Wildcards in pkg.install are not supported")
    return _WILDCARDS_SUPPORTED


@pytest.fixture
def ctx():
    return {}


@pytest.fixture
def latest_version(ctx, modules):
    """
    Helper function which ensures that we don't make any unnecessary calls to
    pkg.latest_version to figure out what version we need to install. This
    won't stop pkg.latest_version from being run in a pkg.latest state, but it
    will reduce the amount of times we check the latest version here in the
    test suite.
    """

    def run_command(*names):
        key = "latest_version"
        if key not in ctx:
            ctx[key] = dict()
        targets = [x for x in names if x not in ctx[key]]
        if targets:
            result = modules.pkg.latest_version(*targets, refresh=False)
            try:
                ctx[key].update(result)
            except ValueError:
                # Only a single target, pkg.latest_version returned a string
                ctx[key][targets[0]] = result

        ret = {x: ctx[key].get(x, "") for x in names}
        if len(names) == 1:
            return ret[names[0]]
        return ret

    return run_command


@pytest.fixture(scope="function")
def install_7zip(modules):
    try:
        modules.pkg.install(name="7zip", version="22.01.00.0")
        modules.pkg.install(name="7zip", version="19.00.00.0")
        versions = modules.pkg.version("7zip")
        assert "19.00.00.0" in versions
        assert "22.01.00.0" in versions
        yield
    finally:
        modules.pkg.remove(name="7zip", version="19.00.00.0")
        modules.pkg.remove(name="7zip", version="22.01.00.0")
        versions = modules.pkg.version("7zip")
        assert "19.00.00.0" not in versions
        assert "22.01.00.0" not in versions


@pytest.mark.requires_salt_modules("pkg.version")
@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed")
@pytest.mark.slow_test
def test_pkg_001_installed(modules, states, PKG_TARGETS):
    """
    This is a destructive test as it installs and then removes a package
    """
    target = PKG_TARGETS[0]
    version = modules.pkg.version(target)

    # If this assert fails, we need to find new targets, this test needs to
    # be able to test successful installation of packages, so this package
    # needs to not be installed before we run the states below
    assert not version

    ret = states.pkg.installed(name=target, refresh=False)
    assert ret.result is True
    ret = states.pkg.removed(name=target)
    assert ret.result is True


@pytest.mark.usefixtures("VERSION_SPEC_SUPPORTED")
@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed")
@pytest.mark.slow_test
def test_pkg_002_installed_with_version(PKG_TARGETS, states, latest_version):
    """
    This is a destructive test as it installs and then removes a package
    """
    target = PKG_TARGETS[0]
    version = latest_version(target)

    # If this assert fails, we need to find new targets, this test needs to
    # be able to test successful installation of packages, so this package
    # needs to not be installed before we run the states below
    assert version

    ret = states.pkg.installed(name=target, version=version, refresh=False)
    assert ret.result is True
    ret = states.pkg.removed(name=target)
    assert ret.result is True


@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed")
@pytest.mark.slow_test
def test_pkg_003_installed_multipkg(caplog, PKG_TARGETS, modules, states, grains):
    """
    This is a destructive test as it installs and then removes two packages
    """
    if grains["os_family"] == "Arch":
        pytest.skip("Arch needs refresh_db logic added to golden image")

    version = modules.pkg.version(*PKG_TARGETS)

    # If this assert fails, we need to find new targets, this test needs to
    # be able to test successful installation of packages, so these
    # packages need to not be installed before we run the states below
    assert not any(version.values())
    ret = states.pkg.removed(name=None, pkgs=PKG_TARGETS)
    assert ret.result is True

    try:
        ret = states.pkg.installed(name=None, pkgs=PKG_TARGETS, refresh=False)
        assert ret.result is True
        if not salt.utils.platform.is_windows():
            assert "WARNING" not in caplog.text
    finally:
        ret = states.pkg.removed(name=None, pkgs=PKG_TARGETS)
        assert ret.result is True


@pytest.mark.usefixtures("VERSION_SPEC_SUPPORTED")
@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed")
@pytest.mark.slow_test
def test_pkg_004_installed_multipkg_with_version(
    PKG_TARGETS, latest_version, states, grains
):
    """
    This is a destructive test as it installs and then removes two packages
    """
    if grains["os_family"] == "Arch":
        pytest.skip("Arch needs refresh_db logic added to golden image")
    version = latest_version(PKG_TARGETS[0])

    # If this assert fails, we need to find new targets, this test needs to
    # be able to test successful installation of packages, so these
    # packages need to not be installed before we run the states below
    assert bool(version)

    pkgs = [{PKG_TARGETS[0]: version}, PKG_TARGETS[1]]

    try:
        ret = states.pkg.installed(name=None, pkgs=pkgs, refresh=False)
        assert ret.result is True
    finally:
        ret = states.pkg.removed(name=None, pkgs=PKG_TARGETS)
        assert ret.result is True


@pytest.mark.requires_salt_modules("pkg.version")
@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed")
@pytest.mark.slow_test
def test_pkg_005_installed_32bit(PKG_32_TARGETS, modules, states):
    """
    This is a destructive test as it installs and then removes a package
    """
    target = PKG_32_TARGETS[0]

    # _PKG_TARGETS_32 is only populated for platforms for which Salt has to
    # munge package names for 32-bit-on-x86_64 (Currently only Ubuntu and
    # RHEL-based). Don't actually perform this test on other platforms.
    version = modules.pkg.version(target)

    # If this assert fails, we need to find a new target. This test
    # needs to be able to test successful installation of packages, so
    # the target needs to not be installed before we run the states
    # below
    assert not version

    ret = states.pkg.installed(name=target, refresh=False)
    assert ret.result is True
    ret = states.pkg.removed(name=target)
    assert ret.result is True


@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed")
@pytest.mark.slow_test
def test_pkg_006_installed_32bit_with_version(PKG_32_TARGETS, latest_version, states):
    """
    This is a destructive test as it installs and then removes a package
    """
    target = PKG_32_TARGETS[0]

    # _PKG_TARGETS_32 is only populated for platforms for which Salt has to
    # munge package names for 32-bit-on-x86_64 (Currently only Ubuntu and
    # RHEL-based). Don't actually perform this test on other platforms.
    version = latest_version(target)

    # If this assert fails, we need to find a new target. This test
    # needs to be able to test successful installation of the package, so
    # the target needs to not be installed before we run the states
    # below
    assert version

    ret = states.pkg.installed(name=target, version=version, refresh=False)
    assert ret.result is True
    ret = states.pkg.removed(name=target)
    assert ret.result is True


@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed")
@pytest.mark.slow_test
def test_pkg_007_with_dot_in_pkgname(PKG_DOT_TARGETS, latest_version, states):
    """
    This tests for the regression found in the following issue:
    https://github.com/saltstack/salt/issues/8614

    This is a destructive test as it installs a package
    """
    target = PKG_DOT_TARGETS[0]

    version = latest_version(target)
    # If this assert fails, we need to find a new target. This test
    # needs to be able to test successful installation of the package, so
    # the target needs to not be installed before we run the
    # pkg.installed state below
    assert bool(version)
    ret = states.pkg.installed(name=target, refresh=False)
    assert ret.result is True
    ret = states.pkg.removed(name=target)
    assert ret.result is True


@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed")
@pytest.mark.slow_test
def test_pkg_008_epoch_in_version(PKG_EPOCH_TARGETS, latest_version, states):
    """
    This tests for the regression found in the following issue:
    https://github.com/saltstack/salt/issues/8614

    This is a destructive test as it installs a package
    """
    target = PKG_EPOCH_TARGETS[0]

    version = latest_version(target)
    # If this assert fails, we need to find a new target. This test
    # needs to be able to test successful installation of the package, so
    # the target needs to not be installed before we run the
    # pkg.installed state below
    assert version
    ret = states.pkg.installed(name=target, version=version, refresh=False)
    assert ret.result is True
    ret = states.pkg.removed(name=target)
    assert ret.result is True


@pytest.mark.requires_salt_modules("pkg.version", "pkg.info_installed")
@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed")
@pytest.mark.slow_test
def test_pkg_009_latest_with_epoch(grains, modules, states):
    """
    This tests for the following issue:
    https://github.com/saltstack/salt/issues/31014

    This is a destructive test as it installs a package
    """

    if grains["kernel"] != "linux":
        pytest.skip("Only runs on Linux.")

    if grains["os"] != "Amazon":
        pytest.skip("Does not runs on Amazon Linux.")

    package = "bash-completion"
    pkgquery = "version"

    ret = states.pkg.installed(name=package, refresh=False)
    assert ret.result is True

    ret = modules.pkg.info_installed(package)
    assert pkgquery in str(ret)


@pytest.mark.requires_salt_states("pkg.latest", "pkg.removed")
@pytest.mark.slow_test
def test_pkg_010_latest(PKG_TARGETS, latest_version, states):
    """
    This tests pkg.latest with a package that has no epoch (or a zero
    epoch).
    """
    target = PKG_TARGETS[0]
    version = latest_version(target)

    # If this assert fails, we need to find new targets, this test needs to
    # be able to test successful installation of packages, so this package
    # needs to not be installed before we run the states below
    assert version

    ret = states.pkg.latest(name=target, refresh=False)
    assert ret.result is True
    ret = states.pkg.removed(name=target)
    assert ret.result is True


@pytest.mark.requires_salt_modules("pkg.list_pkgs", "pkg.list_upgrades", "pkg.version")
@pytest.mark.requires_salt_states("pkg.latest")
@pytest.mark.slow_test
def test_pkg_011_latest_only_upgrade(
    grains, PKG_TARGETS, latest_version, states, modules
):
    """
    WARNING: This test will pick a package with an available upgrade (if
    there is one) and upgrade it to the latest version.
    """
    if grains["os_family"] != "Debian":
        pytest.skip("Only runs on Debian based operating systems.")

    target = PKG_TARGETS[0]

    # If this assert fails, we need to find new targets, this test needs to
    # be able to test that the state fails when you try to run the state
    # with only_upgrade=True on a package which is not already installed,
    # so the targeted package needs to not be installed before we run the
    # state below.
    version = latest_version(target)
    assert version

    ret = states.pkg.latest(name=target, refresh=False, only_upgrade=True)
    assert ret.result is False

    # Now look for updates and try to run the state on a package which is already up-to-date.
    installed_pkgs = modules.pkg.list_pkgs()
    updates = modules.pkg.list_upgrades(refresh=False)

    for pkgname in updates:
        if pkgname in installed_pkgs:
            target = pkgname
            break
    else:
        target = ""
        log.warning(
            "No available upgrades to installed packages, skipping "
            "only_upgrade=True test with already-installed package. For "
            "best results run this test on a machine with upgrades "
            "available."
        )

    if target:
        ret = states.pkg.latest(name=target, refresh=False, only_upgrade=True)
        assert ret.result is True
        new_version = modules.pkg.version(target, use_context=False)
        assert new_version == updates[target]
        ret = states.pkg.latest(name=target, refresh=False, only_upgrade=True)
        assert (
            ret.raw["pkg_|-{0}_|-{0}_|-latest".format(target)]["comment"]
            == f"Package {target} is already up-to-date"
        )


@pytest.mark.usefixtures("WILDCARDS_SUPPORTED")
@pytest.mark.requires_salt_modules("pkg.version")
@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed")
@pytest.mark.slow_test
def test_pkg_012_installed_with_wildcard_version(PKG_TARGETS, states, modules):
    """
    This is a destructive test as it installs and then removes a package
    """
    target = PKG_TARGETS[0]
    version = modules.pkg.version(target)

    # If this assert fails, we need to find new targets, this test needs to
    # be able to test successful installation of packages, so this package
    # needs to not be installed before we run the states below
    assert not version

    ret = states.pkg.installed(
        name=target,
        version="*",
        refresh=False,
    )
    assert ret.result is True

    # Repeat state, should pass
    ret = states.pkg.installed(
        name=target,
        version="*",
        refresh=False,
    )

    expected_comment = (
        "All specified packages are already installed and are at the desired version"
    )
    assert ret.result is True
    assert ret.raw[next(iter(ret.raw))]["comment"] == expected_comment

    # Repeat one more time with unavailable version, test should fail
    ret = states.pkg.installed(
        name=target,
        version="93413*",
        refresh=False,
    )
    assert ret.result is False

    # Clean up
    ret = states.pkg.removed(name=target)
    assert ret.result is True


@pytest.mark.requires_salt_modules("pkg.version", "pkg.latest_version")
@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed")
@pytest.mark.slow_test
def test_pkg_013_installed_with_comparison_operator(
    grains, PKG_TARGETS, states, modules
):
    """
    This is a destructive test as it installs and then removes a package
    """
    if grains["os_family"] != "RedHat" or grains["os_family"] != "Debian":
        pytest.skip("Only runs on Debian or RedHat.")

    target = PKG_TARGETS[0]
    version = modules.pkg.version(target)

    # If this assert fails, we need to find new targets, this test needs to
    # be able to test successful installation of packages, so this package
    # needs to not be installed before we run the states below
    assert not version

    latest_version = modules.pkg.latest_version(target, refresh=False)

    try:
        ret = states.pkg.installed(
            name=target,
            version="<9999999",
            refresh=False,
        )
        assert ret.result is True

        # The version that was installed should be the latest available
        version = modules.pkg.version(target)
        assert version, latest_version
    finally:
        # Clean up
        ret = states.pkg.removed(name=target)
        assert ret.result is True


@pytest.mark.requires_salt_modules("pkg.version")
@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed")
@pytest.mark.slow_test
def test_pkg_014_installed_missing_release(grains, PKG_TARGETS, states, modules):
    """
    Tests that a version number missing the release portion still resolves
    as correctly installed. For example, version 2.0.2 instead of 2.0.2-1.el7
    """
    if grains["os_family"] != "RedHat":
        pytest.skip("Only runs on RedHat based operating systems.")

    target = PKG_TARGETS[0]
    version = modules.pkg.version(target)

    # If this assert fails, we need to find new targets, this test needs to
    # be able to test successful installation of packages, so this package
    # needs to not be installed before we run the states below
    assert not version

    ret = states.pkg.installed(
        name=target,
        version=salt.utils.pkg.rpm.version_to_evr(version)[1],
        refresh=False,
    )
    assert ret.result is True

    # Clean up
    ret = states.pkg.removed(name=target)
    assert ret.result is True


@pytest.mark.requires_salt_modules(
    "pkg.hold", "pkg.unhold", "pkg.version", "pkg.list_pkgs"
)
@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed")
@pytest.mark.slow_test
def test_pkg_015_installed_held(grains, modules, states, PKG_TARGETS):
    """
    Tests that a package can be held even when the package is already installed.
    """
    versionlock_pkg = None
    if grains["os_family"] == "RedHat":
        pkgs = {
            p for p in modules.pkg.list_repo_pkgs() if "yum-plugin-versionlock" in p
        }
        if not pkgs:
            pytest.skip("No versionlock package found in repositories")
        for versionlock_pkg in pkgs:
            ret = states.pkg.installed(name=versionlock_pkg, refresh=False)
            # Exit loop if a versionlock package installed correctly
            try:
                assert ret.result is True
                log.debug("Installed versionlock package: %s", versionlock_pkg)
                break
            except AssertionError as exc:
                log.debug("Versionlock package not found:\n%s", exc)
        else:
            pytest.fail(f"Could not install versionlock package from {pkgs}")

    target = PKG_TARGETS[0]

    # First we ensure that the package is installed
    ret = states.pkg.installed(
        name=target,
        refresh=False,
    )
    assert ret.result is True

    # Then we check that the package is now held
    ret = states.pkg.installed(
        name=target,
        hold=True,
        refresh=False,
    )

    if versionlock_pkg and "-versionlock is not installed" in str(ret):
        pytest.skip(f"{ret}  `{versionlock_pkg}` is installed")

    # changes from pkg.hold for Red Hat family are different
    target_changes = {}
    if (
        grains["os_family"] == "RedHat"
        or grains["os"] == "FreeBSD"
        or grains["os_family"] == "Suse"
    ):
        target_changes = {"new": "hold", "old": ""}
    elif grains["os_family"] == "Debian":
        target_changes = {"new": "hold", "old": "install"}

    try:
        tag = "pkg_|-{0}_|-{0}_|-installed".format(target)
        assert ret.result is True
        assert tag in ret.raw
        assert "changes" in ret.raw[tag]
        assert target in ret.raw[tag]["changes"]
        if not target_changes:
            pytest.skip(
                "Test needs to be configured for {}: {}".format(
                    grains["os"], ret.raw[tag]["changes"][target]
                )
            )
        assert ret.raw[tag]["changes"][target] == target_changes
    finally:
        # Clean up, unhold package and remove
        modules.pkg.unhold(name=target)
        ret = states.pkg.removed(name=target)
        assert ret.result is True
        if versionlock_pkg:
            ret = states.pkg.removed(name=versionlock_pkg)
            assert ret.result is True


@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed")
@pytest.mark.slow_test
def test_pkg_016_conditionally_ignore_epoch(PKG_EPOCH_TARGETS, latest_version, states):
    """
    See
    https://github.com/saltstack/salt/issues/56654#issuecomment-615034952

    This is a destructive test as it installs a package
    """
    target = PKG_EPOCH_TARGETS[0]

    # Strip the epoch from the latest available version
    version = latest_version(target).split(":", 1)[-1]
    # If this assert fails, we need to find a new target. This test
    # needs to be able to test successful installation of the package, so
    # the target needs to not be installed before we run the
    # pkg.installed state below
    assert version

    # CASE 1: package name passed in "name" param
    ret = states.pkg.installed(name=target, version=version, refresh=False)
    assert ret.result is True
    ret = states.pkg.removed(name=target)
    assert ret.result is True

    # CASE 2: same as case 1 but with "pkgs"
    ret = states.pkg.installed(name="foo", pkgs=[{target: version}], refresh=False)
    assert ret.result is True
    ret = states.pkg.removed(name=target)
    assert ret.result is True


@pytest.mark.skip_on_photonos(
    reason="package hold/unhold unsupported on Photon OS",
)
@pytest.mark.requires_salt_modules(
    "pkg.hold", "pkg.unhold", "pkg.version", "pkg.list_pkgs"
)
@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed")
def test_pkg_017_installed_held_equals_false(grains, modules, states, PKG_TARGETS):
    """
    Tests that a package is installed when hold is explicitly False.

    See https://github.com/saltstack/salt/issues/58801.
    """
    versionlock_pkg = None
    if grains["os_family"] == "RedHat":
        from salt.modules.yumpkg import _versionlock_pkg

        pkgs = {
            p for p in modules.pkg.list_repo_pkgs() if _versionlock_pkg(grains) in p
        }
        if not pkgs:
            pytest.skip("No versionlock package found in repositories")
        for versionlock_pkg in pkgs:
            ret = states.pkg.installed(name=versionlock_pkg, refresh=False)
            # Exit loop if a versionlock package installed correctly
            try:
                assert ret.result is True
                log.debug("Installed versionlock package: %s", versionlock_pkg)
                break
            except AssertionError as exc:
                log.debug("Versionlock package not found:\n%s", exc)
        else:
            pytest.fail(f"Could not install versionlock package from {pkgs}")

    target = PKG_TARGETS[0]

    # First we ensure that the package is installed
    target_ret = states.pkg.installed(
        name=target,
        hold=False,
        refresh=False,
    )
    assert target_ret.result is True

    if versionlock_pkg and "-versionlock is not installed" in str(target_ret):
        pytest.skip(f"{target_ret}  `{versionlock_pkg}` is installed")

    try:
        tag = "pkg_|-{0}_|-{0}_|-installed".format(target)
        assert target_ret.result is True
        assert tag in target_ret.raw
        assert "changes" in target_ret.raw[tag]
        # On Centos 7 package is already installed, no change happened
        if target_ret.raw[tag].get("changes"):
            assert target in target_ret.raw[tag]["changes"]
        if grains["os_family"] == "Suse":
            assert "packages were installed" in target_ret.raw[tag]["comment"]
        else:
            #  The "held" string is part of a longer comment that may look
            #  like:
            #
            #    Package units is not being held.
            assert "held" in target_ret.raw[tag]["comment"]
    finally:
        # Clean up, unhold package and remove
        ret = states.pkg.removed(name=target)
        assert ret.result is True
        if versionlock_pkg:
            ret = states.pkg.removed(name=versionlock_pkg)
            assert ret.result is True


@pytest.mark.requires_salt_modules("pkg.version")
@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed")
@pytest.mark.slow_test
def test_pkg_cap_001_installed(PKG_CAP_TARGETS, modules, states):
    """
    This is a destructive test as it installs and then removes a package
    """
    target, realpkg = PKG_CAP_TARGETS[0]
    version = modules.pkg.version(target)
    realver = modules.pkg.version(realpkg)

    # If this condition is False, we need to find new targets.
    # This needs to be able to test successful installation of packages.
    # These packages need to not be installed before we run the states below
    if not (version and realver):
        pytest.skip("TODO: New pkg cap targets required")

    try:
        ret = states.pkg.installed(
            name=target,
            refresh=False,
            resolve_capabilities=True,
            test=True,
        )
        assert (
            f"The following packages would be installed/updated: {realpkg}"
            in ret.comment
        )
        ret = states.pkg.installed(
            name=target, refresh=False, resolve_capabilities=True
        )
        assert ret.result is True
    finally:
        ret = states.pkg.removed(name=realpkg)
        assert ret.result is True


@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed")
@pytest.mark.slow_test
def test_pkg_cap_002_already_installed(PKG_CAP_TARGETS, modules, states):
    """
    This is a destructive test as it installs and then removes a package
    """
    target, realpkg = PKG_CAP_TARGETS[0]
    version = modules.pkg.version(target)
    realver = modules.pkg.version(realpkg)

    # If this condition is False, we need to find new targets.
    # This needs to be able to test successful installation of packages.
    # These packages need to not be installed before we run the states below
    if not (version and realver):
        pytest.skip("TODO: New pkg cap targets required")

    try:
        # install the package
        ret = states.pkg.installed(name=realpkg, refresh=False)
        assert ret.result is True

        # Try to install again. Nothing should be installed this time.
        ret = states.pkg.installed(
            name=target,
            refresh=False,
            resolve_capabilities=True,
            test=True,
        )
        assert "All specified packages are already installed" in ret.comment

        ret = states.pkg.installed(
            name=target, refresh=False, resolve_capabilities=True
        )
        assert ret.result is True

        assert "packages are already installed" in ret.comment
    finally:
        ret = states.pkg.removed(name=realpkg)
        assert ret.result is True


@pytest.mark.usefixtures("VERSION_SPEC_SUPPORTED")
@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed")
@pytest.mark.slow_test
def test_pkg_cap_003_installed_multipkg_with_version(
    PKG_CAP_TARGETS,
    PKG_TARGETS,
    latest_version,
    modules,
    states,
    grains,
):
    """
    This is a destructive test as it installs and then removes two packages
    """
    target, realpkg = PKG_CAP_TARGETS[0]
    version = latest_version(target)
    realver = latest_version(realpkg)

    # If this condition is False, we need to find new targets.
    # This needs to be able to test successful installation of packages.
    # These packages need to not be installed before we run the states below
    if not (version and realver):
        pytest.skip("TODO: New pkg cap targets required")

    cleanup_pkgs = PKG_TARGETS
    try:
        pkgs = [
            {PKG_TARGETS[0]: version},
            PKG_TARGETS[1],
            {target: realver},
        ]
        ret = states.pkg.installed(
            name="test_pkg_cap_003_installed_multipkg_with_version-install",
            pkgs=pkgs,
            refresh=False,
        )
        assert ret.result is False

        ret = states.pkg.installed(
            name="test_pkg_cap_003_installed_multipkg_with_version-install-capability",
            pkgs=pkgs,
            refresh=False,
            resolve_capabilities=True,
            test=True,
        )
        assert "packages would be installed/updated" in ret.comment
        assert f"{realpkg}={realver}" in ret.comment

        ret = states.pkg.installed(
            name="test_pkg_cap_003_installed_multipkg_with_version-install-capability",
            pkgs=pkgs,
            refresh=False,
            resolve_capabilities=True,
        )
        assert ret.result is True
        cleanup_pkgs.append(realpkg)
    finally:
        ret = states.pkg.removed(
            name="test_pkg_cap_003_installed_multipkg_with_version-remove",
            pkgs=cleanup_pkgs,
        )
        assert ret.result is True


@pytest.mark.requires_salt_modules("pkg.version")
@pytest.mark.requires_salt_states("pkg.latest", "pkg.removed")
@pytest.mark.slow_test
def test_pkg_cap_004_latest(PKG_CAP_TARGETS, modules, states):
    """
    This tests pkg.latest with a package that has no epoch (or a zero
    epoch).
    """
    target, realpkg = PKG_CAP_TARGETS[0]
    version = modules.pkg.version(target)
    realver = modules.pkg.version(realpkg)

    # If this condition is False, we need to find new targets.
    # This needs to be able to test successful installation of packages.
    # These packages need to not be installed before we run the states below
    if not (version and realver):
        pytest.skip("TODO: New pkg cap targets required")

    try:
        ret = states.pkg.latest(
            name=target,
            refresh=False,
            resolve_capabilities=True,
            test=True,
        )
        assert (
            f"The following packages would be installed/upgraded: {realpkg}"
            in ret.comment
        )
        ret = states.pkg.latest(name=target, refresh=False, resolve_capabilities=True)
        assert ret.result is True

        ret = states.pkg.latest(name=target, refresh=False, resolve_capabilities=True)
        assert ret.result is True
        assert "is already up-to-date" in ret.comment
    finally:
        ret = states.pkg.removed(name=realpkg)
        assert ret.result is True


@pytest.mark.requires_salt_modules("pkg.version")
@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed", "pkg.downloaded")
@pytest.mark.slow_test
def test_pkg_cap_005_downloaded(PKG_CAP_TARGETS, modules, states):
    """
    This is a destructive test as it installs and then removes a package
    """
    target, realpkg = PKG_CAP_TARGETS[0]
    version = modules.pkg.version(target)
    realver = modules.pkg.version(realpkg)

    # If this condition is False, we need to find new targets.
    # This needs to be able to test successful installation of packages.
    # These packages need to not be installed before we run the states below
    if not (version and realver):
        pytest.skip("TODO: New pkg cap targets required")

    ret = states.pkg.downloaded(name=target, refresh=False)
    assert ret.result is False

    ret = states.pkg.downloaded(
        name=target,
        refresh=False,
        resolve_capabilities=True,
        test=True,
    )
    assert f"The following packages would be downloaded: {realpkg}" in ret.comment

    ret = states.pkg.downloaded(name=target, refresh=False, resolve_capabilities=True)
    assert ret.result is True


@pytest.mark.requires_salt_modules("pkg.version")
@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed", "pkg.uptodate")
@pytest.mark.slow_test
def test_pkg_cap_006_uptodate(PKG_CAP_TARGETS, modules, states):
    """
    This is a destructive test as it installs and then removes a package
    """
    target, realpkg = PKG_CAP_TARGETS[0]
    version = modules.pkg.version(target)
    realver = modules.pkg.version(realpkg)

    # If this condition is False, we need to find new targets.
    # This needs to be able to test successful installation of packages.
    # These packages need to not be installed before we run the states below
    if not (version and realver):
        pytest.skip("TODO: New pkg cap targets required")

    try:
        ret = states.pkg.installed(
            name=target, refresh=False, resolve_capabilities=True
        )
        assert ret.result is True
        ret = states.pkg.uptodate(
            name="test_pkg_cap_006_uptodate",
            pkgs=[target],
            refresh=False,
            resolve_capabilities=True,
        )
        assert ret.result is True
        assert "System is already up-to-date" in ret.comment
    finally:
        ret = states.pkg.removed(name=realpkg)
        assert ret.result is True


@pytest.mark.requires_salt_modules(
    "pkg.version", "pkg.latest_version", "pkg.remove", "pkg.purge", "pkg.list_pkgs"
)
@pytest.mark.requires_salt_states("pkg.installed", "pkg.removed", "pkg.purged")
def test_pkg_purged_with_removed_pkg(grains, PKG_TARGETS, states, modules):
    """
    This is a destructive test as it installs and then removes a package, then purges a removed package
    """
    if grains["os_family"] != "Debian":
        pytest.skip("Only runs on Debian.")

    target = PKG_TARGETS[0]

    ret = states.pkg.installed(
        name=target,
        version="<9999999",
        refresh=False,
    )
    assert ret.result is True

    # The version that was installed should be the latest available
    version = modules.pkg.version(target)
    assert version

    # Clean up
    ret = states.pkg.removed(name=target)
    assert ret.result is True

    ret = states.pkg.purged(name=target)
    assert ret.result is True
    assert ret.name == target
    assert ret.comment == "All targeted packages were purged."
    assert ret.changes == {
        "installed": {},
        "removed": {target: {"new": "", "old": version}},
    }


@pytest.mark.skip_unless_on_windows()
def test_pkg_removed_with_version_multiple(install_7zip, modules, states):
    """
    This tests removing a specific version of a package when multiple versions
    are installed. This is specific to Windows. The only version I could find
    that allowed multiple installs of differing versions was 7zip, so we'll use
    that.
    """
    ret = states.pkg.removed(name="7zip", version="19.00.00.0")
    assert ret.result is True
    current = modules.pkg.version("7zip")
    assert "22.01.00.0" in current
