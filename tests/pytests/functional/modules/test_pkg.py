import logging
import os

import pytest
import salt.utils.path
import salt.utils.pkg
import salt.utils.platform
from tests.support.pytest.helpers import ShowOutputOnConsole

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_if_not_root,
    pytest.mark.windows_whitelisted,
    pytest.mark.requires_salt_modules("pkg.refresh_db"),
]


@pytest.fixture(scope="module")
def states(loaders):
    return loaders.states


@pytest.fixture(scope="module")
def pkg(modules):
    # Always start these tests with a refreshed package database
    modules.pkg.refresh_db()
    return modules.pkg


@pytest.fixture(scope="module")
def pkg_name(grains):
    if salt.utils.platform.is_windows():
        return "putty"
    if grains["os_family"] == "RedHat":
        if grains["os"] == "VMware Photon OS":
            return "snoopy"
        return "units"
    return "figlet"


@pytest.fixture
def show_output_on_console():
    """
    This fixture is so that the slow tests on this module, namely ``pkg.upgrade()``
    which can take a long time don't make the whole test suite get canceled because
    of no output on the console
    """
    with ShowOutputOnConsole():
        yield


@pytest.fixture
def installed_pkg_name(pkg_name, states):
    ret = states.pkg.installed(pkg_name)
    assert ret.result is True
    try:
        yield pkg_name
    finally:
        states.pkg.removed(pkg_name)


@pytest.fixture
def removed_pkg_name(states, pkg_name):
    states.pkg.removed(name=pkg_name)
    try:
        yield pkg_name
    finally:
        states.pkg.removed(pkg_name)


@pytest.mark.slow_test
@pytest.mark.requires_salt_modules("pkg.list_pkgs")
def test_list(pkg):
    """
    verify that packages are installed
    """
    ret = pkg.list_pkgs()
    assert ret


@pytest.fixture
def versions_comparisson(grains):
    if grains["os_family"] == "Debian":
        lt = ["0.2.4-0ubuntu1", "0.2.4.1-0ubuntu1"]
        eq = ["0.2.4-0ubuntu1", "0.2.4-0ubuntu1"]
        gt = ["0.2.4.1-0ubuntu1", "0.2.4-0ubuntu1"]
    elif grains["os_family"] == "Suse":
        lt = ["2.3.0-1", "2.3.1-15.1"]
        eq = ["2.3.1-15.1", "2.3.1-15.1"]
        gt = ["2.3.2-15.1", "2.3.1-15.1"]
    else:
        lt = ["2.3.0", "2.3.1"]
        eq = ["2.3.1", "2.3.1"]
        gt = ["2.3.2", "2.3.1"]
    return lt, eq, gt


@pytest.mark.slow_test
@pytest.mark.requires_salt_modules("pkg.version_cmp")
def test_version_cmp(pkg, versions_comparisson, subtests):
    """
    test package version comparison on supported platforms
    """
    lt, eq, gt = versions_comparisson
    with subtests.test("{} < {}".format(*lt)):
        assert pkg.version_cmp(*lt) == -1
    with subtests.test("{} == {}".format(*eq)):
        assert pkg.version_cmp(*eq) == 0
    with subtests.test("{} > {}".format(*gt)):
        assert pkg.version_cmp(*gt) == 1


@pytest.mark.slow_test
@pytest.mark.destructive_test
@pytest.mark.requires_network
@pytest.mark.requires_salt_modules("pkg.mod_repo", "pkg.del_repo", "pkg.get_repo")
def test_mod_del_repo(pkg, grains):
    """
    test modifying and deleting a software repository
    """
    if grains["os"] != "Ubuntu" and grains["os_family"] != "RedHat":
        pytest.skip("Test is only applicable to Ubuntu and RedHat based distributions")

    repo = None
    try:
        if grains["os"] == "Ubuntu":
            repo = "ppa:otto-kesselgulasch/gimp-edge"
            uri = "http://ppa.launchpad.net/otto-kesselgulasch/gimp-edge/ubuntu"
            ret = pkg.mod_repo(repo, "comps=main")
            assert ret != {}
            ret = pkg.get_repo(repo)

            assert isinstance(ret, dict)
            assert ret["uri"] == uri
        elif grains["os_family"] == "RedHat":
            repo = "saltstack"
            name = "SaltStack repo for RHEL/CentOS {}".format(grains["osmajorrelease"])
            baseurl = "http://repo.saltstack.com/yum/redhat/{}/x86_64/latest/".format(
                grains["osmajorrelease"]
            )
            gpgkey = "https://repo.saltstack.com/yum/rhel{}/SALTSTACK-GPG-KEY.pub".format(
                grains["osmajorrelease"]
            )
            gpgcheck = 1
            enabled = 1
            ret = pkg.mod_repo(
                repo,
                name=name,
                baseurl=baseurl,
                gpgkey=gpgkey,
                gpgcheck=gpgcheck,
                enabled=enabled,
            )
            # return data from pkg.mod_repo contains the file modified at
            # the top level, so use next(iter(ret)) to get that key
            assert ret
            repo_info = ret[next(iter(ret))]
            assert repo in repo_info
            assert repo_info[repo]["baseurl"] == baseurl
            ret = pkg.get_repo(repo)
            assert ret["baseurl"] == baseurl
    finally:
        pkg.del_repo(repo)


@pytest.mark.slow_test
def test_mod_del_repo_multiline_values(pkg, grains):
    """
    test modifying and deleting a software repository defined with multiline values
    """
    applicable_oses = ["CentOS", "RedHat", "VMware Photon OS"]
    if grains["os"] not in applicable_oses:
        pytest.skip(
            "OS({}) not in applicable OS'es list: {}".format(
                grains["os"], applicable_oses
            )
        )

    repo = None
    try:
        my_baseurl = "http://my.fake.repo/foo/bar/\n http://my.fake.repo.alt/foo/bar/"
        expected_get_repo_baseurl = (
            "http://my.fake.repo/foo/bar/\nhttp://my.fake.repo.alt/foo/bar/"
        )
        repo = "fakerepo"
        name = "Fake repo for RHEL/CentOS/SUSE"
        baseurl = my_baseurl
        gpgkey = "https://my.fake.repo/foo/bar/MY-GPG-KEY.pub"
        failovermethod = "priority"
        gpgcheck = 1
        enabled = 1
        ret = pkg.mod_repo(
            repo,
            name=name,
            baseurl=baseurl,
            gpgkey=gpgkey,
            gpgcheck=gpgcheck,
            enabled=enabled,
            failovermethod=failovermethod,
        )
        # return data from pkg.mod_repo contains the file modified at
        # the top level, so use next(iter(ret)) to get that key
        assert ret
        repo_info = ret[next(iter(ret))]
        assert repo in repo_info
        assert repo_info[repo]["baseurl"] == my_baseurl
        ret = pkg.get_repo(repo)
        assert ret["baseurl"] == expected_get_repo_baseurl
        ret = pkg.mod_repo(repo)
        ret = pkg.get_repo(repo)
        assert ret["baseurl"] == expected_get_repo_baseurl
    finally:
        pkg.del_repo(repo)


@pytest.mark.requires_salt_modules("pkg.owner")
def test_owner(pkg):
    """
    test finding the package owning a file
    """
    ret = pkg.owner("/bin/ls")
    assert ret


# Similar to pkg.owner, but for FreeBSD's pkgng
@pytest.mark.requires_salt_modules("pkg.which")
def test_which(pkg):
    """
    test finding the package owning a file
    """
    ret = pkg.which("/usr/local/bin/salt-call")
    assert ret


@pytest.mark.slow_test
@pytest.mark.destructive_test
@pytest.mark.requires_network
@pytest.mark.requires_salt_modules("pkg.version", "pkg.install", "pkg.remove")
def test_install_remove(pkg, pkg_name, subtests):
    """
    successfully install and uninstall a package
    """

    def test_install():
        with subtests.test("pkg.install({})".format(pkg_name)):
            ret = pkg.install(pkg_name)
            assert pkg_name in ret

    def test_remove():
        with subtests.test("pkg.remove({})".format(pkg_name)):
            ret = pkg.remove(pkg_name)
            assert pkg_name in ret

    version = pkg.version(pkg_name)

    if version:
        test_remove()
        test_install()
    else:
        test_install()
        test_remove()


@pytest.fixture(scope="module")
def installed_versionlock(pkg, states, grains, modules):
    ret = None
    versionlock_pkg = None
    if grains["os_family"] == "RedHat":
        pkgs = {p for p in pkg.list_pkgs() if "-versionlock" in p}
        if not pkgs:
            # Versionlock is not installed
            search = modules.cmd.run(["yum", "search", "versionlock"])
            for line in search.splitlines():
                if "versionlock" in line and not line.startswith("="):
                    versionlock_pkg, _ = [p.strip() for p in line.split(":")]
                    break
            if not versionlock_pkg:
                pytest.skip("No versionlock package found in repositories")
            ret = states.pkg.installed(name=versionlock_pkg, refresh=False)
            assert ret.result is True

            pkgs = {p for p in pkg.list_pkgs(use_context=False) if "-versionlock" in p}
            if not pkgs:
                pytest.fail(
                    "Could not find installed package: {}".format(versionlock_pkg)
                )

    try:
        yield ret
    finally:
        if versionlock_pkg:
            ret = states.pkg.removed(name=versionlock_pkg)
            assert ret.result is True


@pytest.mark.slow_test
@pytest.mark.destructive_test
@pytest.mark.requires_network
@pytest.mark.skipif(
    salt.utils.platform.is_photonos(),
    reason="package hold/unhold unsupported on Photon OS",
)
@pytest.mark.requires_salt_modules(
    "pkg.hold",
    "pkg.unhold",
    "pkg.install",
    "pkg.version",
    "pkg.remove",
    "pkg.list_pkgs",
)
@pytest.mark.requires_salt_states("pkg.installed")
@pytest.mark.usefixtures("installed_versionlock")
def test_hold_unhold(pkg, installed_pkg_name, subtests):
    """
    test holding and unholding a package
    """
    with subtests.test("pkg.hold({})".format(installed_pkg_name)):
        ret = pkg.hold(installed_pkg_name)
        assert installed_pkg_name in ret
        assert ret[installed_pkg_name]["result"]

    with subtests.test("pkg.unhold({})".format(installed_pkg_name)):
        ret = pkg.unhold(installed_pkg_name)
        assert installed_pkg_name in ret
        assert ret[installed_pkg_name]["result"]


@pytest.mark.slow_test
@pytest.mark.destructive_test
@pytest.mark.requires_network
def test_refresh_db(pkg, grains, minion_opts):
    """
    test refreshing the package database
    """
    rtag = salt.utils.pkg.rtag(minion_opts)
    salt.utils.pkg.write_rtag(minion_opts)
    assert os.path.isfile(rtag)

    ret = pkg.refresh_db()
    if not isinstance(ret, dict):
        pytest.skip("Upstream repo did not return coherent results: {}".format(ret))

    if grains["os_family"] == "RedHat":
        assert ret in (True, None)
    elif grains["os_family"] == "Suse":
        assert ret
        for state in ret.values():
            assert state in (True, False, None)

    assert not os.path.isfile(rtag)


@pytest.fixture
def info_pkgs(grains, pkg_name):
    if grains["os_family"] == "Debian":
        return ("bash", "dpkg")
    if grains["os_family"] == "RedHat":
        return ("rpm", "bash")
    if grains["os_family"] == "Suse":
        return ("less", "zypper")
    return (pkg_name,)


@pytest.mark.slow_test
@pytest.mark.requires_salt_modules("pkg.info_installed")
def test_pkg_info(pkg, info_pkgs):
    """
    Test returning useful information on Ubuntu systems.
    """
    ret = pkg.info_installed(*info_pkgs)
    for pkg_name in info_pkgs:
        assert pkg_name in ret


@pytest.mark.slow_test
@pytest.mark.destructive_test
@pytest.mark.requires_network
@pytest.mark.usefixtures("show_output_on_console")
@pytest.mark.requires_salt_modules("pkg.upgrade", "pkg.list_upgrades")
def test_pkg_upgrade_has_pending_upgrades(pkg):
    """
    Test running a system upgrade when there are packages that need upgrading
    """
    pending_upgrades = pkg.list_upgrades()
    log.debug("Pending upgrades: %s", pending_upgrades)
    if not pending_upgrades:
        pytest.skip("No updates available for this machine. Skipping pkg.upgrade test.")

    ret = pkg.upgrade()
    for pkg_name in ret:
        if pkg_name in pending_upgrades:
            # We upgraded at least one package. It's enough for the test
            break
    else:
        pytest.fail(
            "Failed to upgrade packages?! Pending upgrades: {} // Upgrade Call Returned: {}".format(
                pending_upgrades, ret
            )
        )


@pytest.fixture
def pkg_listing(pkg, grains, modules, removed_pkg_name):
    if salt.utils.platform.is_windows():
        return pkg.list_available()

    kwargs = {}
    if salt.utils.platform.is_darwin():
        brew_bin = salt.utils.path.which("brew")
        mac_user = modules.file.get_user(brew_bin)
        if mac_user == "root":
            pytest.skip(
                "brew cannot run as root, try a user in {}".format(
                    os.listdir("/Users/")
                )
            )
        kwargs["run_as"] = mac_user
        cmd_pkg = ["brew", "info", removed_pkg_name]
    elif grains["os_family"] == "RedHat":
        cmd_pkg = ["yum", "list", removed_pkg_name]
    elif grains["os_family"] == "Debian":
        cmd_pkg = ["apt", "list", removed_pkg_name]
    elif grains["os_family"] == "Arch":
        cmd_pkg = ["pacman", "-Si", removed_pkg_name]
    elif grains["os_family"] == "FreeBSD":
        cmd_pkg = [
            "pkg",
            "search",
            "-S",
            "name",
            "-qQ",
            "version",
            "-e",
            removed_pkg_name,
        ]
    elif grains["os_family"] == "Suse":
        cmd_pkg = ["zypper", "info", removed_pkg_name]
    else:
        pytest.skip("TODO: test not configured for {}".format(grains["os_family"]))
    return modules.cmd.run(cmd_pkg, **kwargs)


@pytest.mark.slow_test
@pytest.mark.destructive_test
@pytest.mark.skip_on_darwin(
    reason="The jenkins user is equivalent to root on mac, causing the test to be unrunnable"
)
@pytest.mark.requires_salt_modules("pkg.remove", "pkg.latest_version")
@pytest.mark.requires_salt_states("pkg.removed")
def test_pkg_latest_version(pkg, pkg_name, pkg_listing):
    """
    Check that pkg.latest_version returns the latest version of the uninstalled package.
    The package is not installed. Only the package version is checked.
    """
    pkg_latest = pkg.latest_version(pkg_name)
    assert pkg_latest in pkg_listing
