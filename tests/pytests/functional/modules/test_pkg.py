import configparser
import logging
import os
import re
import shutil
import time

import pytest
from saltfactories.utils.functional import Loaders

import salt.utils.path
import salt.utils.pkg
import salt.utils.platform

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.timeout_unless_on_windows(240),
]


@pytest.fixture
def ctx():
    return {}


@pytest.fixture
def _preserve_rhel_yum_conf(tmp_path):

    # save off current yum.conf
    cfg_file = "/etc/yum.conf"
    if not os.path.exists(cfg_file):
        pytest.skip("Only runs on RedHat.")

    tmp_file = tmp_path / "yum.conf"
    shutil.copy2(cfg_file, tmp_file)
    try:
        yield
    finally:
        # restore saved yum.conf
        shutil.copy2(tmp_file, cfg_file)


@pytest.fixture
def _refresh_db(ctx, grains, modules):
    if "refresh" not in ctx:
        modules.pkg.refresh_db()
        ctx["refresh"] = True

    # If this is Arch Linux, check if pacman is in use by another process
    if grains["os_family"] == "Arch":
        for _ in range(12):
            if not os.path.isfile("/var/lib/pacman/db.lck"):
                break
            else:
                time.sleep(5)
        else:
            raise Exception("Package database locked after 60 seconds, bailing out")


@pytest.fixture(autouse=True)
def test_pkg(grains):
    _pkg = "figlet"
    if salt.utils.platform.is_windows():
        _pkg = "putty"
    elif grains["os_family"] == "RedHat":
        if grains["os"] == "VMware Photon OS":
            _pkg = "snoopy"
        elif grains["osfinger"] == "Amazon Linux-2023":
            return "dnf-utils"
        else:
            _pkg = "units"
    elif grains["os_family"] == "Debian":
        _pkg = "ifenslave"
    return _pkg


@pytest.mark.usefixtures("_refresh_db")
@pytest.mark.requires_salt_modules("pkg.list_pkgs")
@pytest.mark.slow_test
def test_list(modules):
    """
    verify that packages are installed
    """
    ret = modules.pkg.list_pkgs()
    assert len(ret.keys()) != 0


@pytest.mark.requires_salt_modules("pkg.version_cmp")
@pytest.mark.slow_test
def test_version_cmp(grains, modules):
    """
    test package version comparison on supported platforms
    """
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

    assert modules.pkg.version_cmp(*lt) == -1
    assert modules.pkg.version_cmp(*eq) == 0
    assert modules.pkg.version_cmp(*gt) == 1


@pytest.mark.usefixtures("_refresh_db")
@pytest.mark.destructive_test
@pytest.mark.requires_salt_modules("pkg.mod_repo", "pkg.del_repo", "pkg.get_repo")
@pytest.mark.slow_test
@pytest.mark.requires_network
def test_mod_del_repo(grains, modules):
    """
    test modifying and deleting a software repository
    """
    repo = None

    try:
        # ppa:otto-kesselgulasch/gimp-edge has no Ubuntu 22.04 repo
        if grains["os"] == "Ubuntu" and grains["osmajorrelease"] < 22:
            repo = "ppa:otto-kesselgulasch/gimp-edge"
            uri = "http://ppa.launchpad.net/otto-kesselgulasch/gimp-edge/ubuntu"
            ret = modules.pkg.mod_repo(repo, "comps=main")
            assert ret != []
            ret = modules.pkg.get_repo(repo)

            assert isinstance(ret, dict) is True
            assert ret["uri"] == uri
        elif grains["os_family"] == "RedHat":
            repo = "saltstack"
            name = "SaltStack repo for RHEL/CentOS {}".format(grains["osmajorrelease"])
            baseurl = "https://repo.saltproject.io/py3/redhat/{}/x86_64/latest/".format(
                grains["osmajorrelease"]
            )
            gpgkey = "https://repo.saltproject.io/py3/redhat/{}/x86_64/latest/SALTSTACK-GPG-KEY.pub".format(
                grains["osmajorrelease"]
            )
            gpgcheck = 1
            enabled = 1
            ret = modules.pkg.mod_repo(
                repo,
                name=name,
                baseurl=baseurl,
                gpgkey=gpgkey,
                gpgcheck=gpgcheck,
                enabled=enabled,
            )
            # return data from pkg.mod_repo contains the file modified at
            # the top level, so use next(iter(ret)) to get that key
            assert ret != {}
            repo_info = ret[next(iter(ret))]
            assert repo in repo_info
            assert repo_info[repo]["baseurl"] == baseurl
            ret = modules.pkg.get_repo(repo)
            assert ret["baseurl"] == baseurl
    finally:
        if repo is not None:
            modules.pkg.del_repo(repo)


@pytest.mark.slow_test
@pytest.mark.usefixtures("_refresh_db")
def test_mod_del_repo_multiline_values(modules):
    """
    test modifying and deleting a software repository defined with multiline values
    """
    os_grain = modules.grains.item("os")["os"]
    repo = None
    try:
        if os_grain in ["CentOS", "RedHat", "VMware Photon OS"]:
            my_baseurl = (
                "http://my.fake.repo/foo/bar/\n http://my.fake.repo.alt/foo/bar/"
            )
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
            ret = modules.pkg.mod_repo(
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
            assert ret != {}
            repo_info = ret[next(iter(ret))]
            assert repo in repo_info
            assert repo_info[repo]["baseurl"] == my_baseurl
            ret = modules.pkg.get_repo(repo)
            assert ret["baseurl"] == expected_get_repo_baseurl
            modules.pkg.mod_repo(repo)
            ret = modules.pkg.get_repo(repo)
            assert ret["baseurl"] == expected_get_repo_baseurl
    finally:
        if repo is not None:
            modules.pkg.del_repo(repo)


@pytest.mark.requires_salt_modules("pkg.owner")
def test_owner(modules, grains):
    """
    test finding the package owning a file
    """
    binary = "/bin/ls"
    if grains["os"] == "Ubuntu" and grains["osmajorrelease"] >= 24:
        binary = "/usr/bin/ls"

    ret = modules.pkg.owner(binary)
    assert len(ret) != 0


# Similar to pkg.owner, but for FreeBSD's pkgng
@pytest.mark.skip_on_freebsd(reason="test for new package manager for FreeBSD")
@pytest.mark.requires_salt_modules("pkg.which")
def test_which(modules, grains):
    """
    test finding the package owning a file
    """
    binary = "/bin/ls"
    if grains["os"] == "Ubuntu" and grains["osmajorrelease"] >= 24:
        binary = "/usr/bin/ls"
    ret = modules.pkg.which(binary)
    assert len(ret) != 0


@pytest.mark.usefixtures("_refresh_db")
@pytest.mark.destructive_test
@pytest.mark.requires_salt_modules("pkg.version", "pkg.install", "pkg.remove")
@pytest.mark.slow_test
@pytest.mark.requires_network
def test_install_remove(modules, test_pkg):
    """
    successfully install and uninstall a package
    """
    version = modules.pkg.version(test_pkg)

    def test_install():
        install_ret = modules.pkg.install(test_pkg)
        assert test_pkg in install_ret

    def test_remove():
        remove_ret = modules.pkg.remove(test_pkg)
        assert test_pkg in remove_ret

    if version and isinstance(version, dict):
        version = version[test_pkg]

    if version:
        test_remove()
        test_install()
    else:
        test_install()
        test_remove()


@pytest.mark.usefixtures("_refresh_db")
@pytest.mark.destructive_test
@pytest.mark.skip_on_photonos(
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
@pytest.mark.slow_test
@pytest.mark.requires_network
@pytest.mark.requires_salt_states("pkg.installed")
def test_hold_unhold(grains, modules, states, test_pkg):
    """
    test holding and unholding a package
    """
    versionlock_pkg = None
    if grains["os_family"] == "RedHat":
        pkgs = {p for p in modules.pkg.list_repo_pkgs() if "-versionlock" in p}
        if not pkgs:
            pytest.skip("No versionlock package found in repositories")
        for versionlock_pkg in pkgs:
            ret = states.pkg.installed(name=versionlock_pkg, refresh=False)
            # Exit loop if a versionlock package installed correctly
            try:
                assert ret.result is True
                break
            except AssertionError:
                pass
        else:
            pytest.fail(f"Could not install versionlock package from {pkgs}")

    modules.pkg.install(test_pkg)

    try:
        hold_ret = modules.pkg.hold(test_pkg)
        if versionlock_pkg and "-versionlock is not installed" in str(hold_ret):
            pytest.skip(f"{hold_ret}  `{versionlock_pkg}` is installed")
        assert test_pkg in hold_ret
        assert hold_ret[test_pkg]["result"] is True

        unhold_ret = modules.pkg.unhold(test_pkg)
        assert test_pkg in unhold_ret
        assert unhold_ret[test_pkg]["result"] is True
        modules.pkg.remove(test_pkg)
    except salt.exceptions.SaltInvocationError as err:
        if "versionlock is not installed" in err.message:
            pytest.skip("Correct versionlock package is not installed")
    finally:
        if versionlock_pkg:
            ret = states.pkg.removed(name=versionlock_pkg)
            assert ret.result is True


@pytest.mark.usefixtures("_refresh_db")
@pytest.mark.destructive_test
@pytest.mark.requires_salt_modules("pkg.refresh_db")
@pytest.mark.slow_test
@pytest.mark.requires_network
def test_refresh_db(grains, minion_opts):
    """
    test refreshing the package database
    """
    rtag = salt.utils.pkg.rtag(minion_opts)
    salt.utils.pkg.write_rtag(minion_opts)
    assert os.path.isfile(rtag) is True

    loader = Loaders(minion_opts)
    ret = loader.modules.pkg.refresh_db()
    if not isinstance(ret, dict):
        pytest.skip(f"Upstream repo did not return coherent results: {ret}")

    if grains["os_family"] == "RedHat":
        assert ret in (True, None)
    elif grains["os_family"] == "Suse":
        if not isinstance(ret, dict):
            pytest.skip("Upstream repo did not return coherent results. Skipping test.")
        assert ret != {}
        for source, state in ret.items():
            assert state in (True, False, None)

    assert os.path.isfile(rtag) is False


@pytest.mark.usefixtures("_refresh_db")
@pytest.mark.requires_salt_modules("pkg.info_installed")
@pytest.mark.slow_test
def test_pkg_info(grains, modules, test_pkg):
    """
    Test returning useful information on Ubuntu systems.
    """
    if grains["os_family"] == "Debian":
        ret = modules.pkg.info_installed("bash", "dpkg")
        keys = ret.keys()
        assert "bash" in keys
        assert "dpkg" in keys
    elif grains["os_family"] == "RedHat":
        ret = modules.pkg.info_installed("rpm", "bash")
        keys = ret.keys()
        assert "rpm" in keys
        assert "bash" in keys
    elif grains["os_family"] == "Suse":
        ret = modules.pkg.info_installed("less", "zypper")
        keys = ret.keys()
        assert "less" in keys
        assert "zypper" in keys
    else:
        ret = modules.pkg.info_installed(test_pkg)
        keys = ret.keys()
        assert test_pkg in keys


@pytest.mark.usefixtures("_refresh_db")
@pytest.mark.skipif(True, reason="Temporary Skip - Causes centos 8 test to fail")
@pytest.mark.destructive_test
@pytest.mark.requires_salt_modules(
    "pkg.refresh_db",
    "pkg.upgrade",
    "pkg.install",
    "pkg.list_repo_pkgs",
    "pkg.list_upgrades",
)
@pytest.mark.slow_test
@pytest.mark.requires_network
def test_pkg_upgrade_has_pending_upgrades(grains, modules):
    """
    Test running a system upgrade when there are packages that need upgrading
    """
    if grains["os"] == "Arch":
        pytest.skip("Arch moved to Python 3.8 and we're not ready for it yet")

    modules.pkg.upgrade()

    # First make sure that an up-to-date copy of the package db is available
    modules.pkg.refresh_db()

    if grains["os_family"] == "Suse":
        # This test assumes that there are multiple possible versions of a
        # package available. That makes it brittle if you pick just one
        # target, as changes in the available packages will break the test.
        # Therefore, we'll choose from several packages to make sure we get
        # one that is suitable for this test.
        packages = ("hwinfo", "avrdude", "diffoscope", "vim")
        available = modules.pkg.list_repo_pkgs(packages)

        for package in packages:
            try:
                new, old = available[package][:2]
            except (KeyError, ValueError):
                # Package not available, or less than 2 versions
                # available. This is not a suitable target.
                continue
            else:
                target = package
                break
        else:
            # None of the packages have more than one version available, so
            # we need to find new package(s). pkg.list_repo_pkgs can be
            # used to get an overview of the available packages. We should
            # try to find packages with few dependencies and small download
            # sizes, to keep this test from taking longer than necessary.
            pytest.fail("No suitable package found for this test")

        # Make sure we have the 2nd-oldest available version installed
        ret = modules.pkg.install(target, version=old)
        if not isinstance(ret, dict):
            if ret.startswith("ERROR"):
                pytest.skip(f"Could not install older {target} to complete test.")

        # Run a system upgrade, which should catch the fact that the
        # targeted package needs upgrading, and upgrade it.
        ret = modules.pkg.upgrade()

        # The changes dictionary should not be empty.
        if "changes" in ret:
            assert target in ret["changes"]
        else:
            assert target in ret
    else:
        ret = modules.pkg.list_upgrades()
        if ret == "" or ret == {}:
            pytest.skip(
                "No updates available for this machine.  Skipping pkg.upgrade test."
            )
        else:
            args = []
            if grains["os_family"] == "Debian":
                args = ["dist_upgrade=True"]
            ret = modules.pkg.upgrade(args)
            assert ret != {}


@pytest.mark.usefixtures("_refresh_db")
@pytest.mark.destructive_test
@pytest.mark.skip_on_darwin(
    reason="The jenkins user is equivalent to root on mac, causing the test to be unrunnable"
)
@pytest.mark.requires_salt_modules("pkg.remove", "pkg.latest_version")
@pytest.mark.slow_test
@pytest.mark.requires_salt_states("pkg.removed")
def test_pkg_latest_version(grains, modules, states, test_pkg):
    """
    Check that pkg.latest_version returns the latest version of the uninstalled package.
    The package is not installed. Only the package version is checked.
    """
    states.pkg.removed(test_pkg)

    cmd_pkg = []
    if grains["os_family"] == "RedHat":
        cmd_pkg = modules.cmd.run(f"yum list {test_pkg}")
    elif salt.utils.platform.is_windows():
        cmd_pkg = modules.pkg.list_available(test_pkg)
    elif grains["os_family"] == "Debian":
        cmd_pkg = modules.cmd.run(f"apt list {test_pkg}")
    elif grains["os_family"] == "Arch":
        cmd_pkg = modules.cmd.run(f"pacman -Si {test_pkg}")
    elif grains["os_family"] == "FreeBSD":
        cmd_pkg = modules.cmd.run(f"pkg search -S name -qQ version -e {test_pkg}")
    elif grains["os_family"] == "Suse":
        cmd_pkg = modules.cmd.run(f"zypper info {test_pkg}")
    elif grains["os_family"] == "MacOS":
        brew_bin = salt.utils.path.which("brew")
        mac_user = modules.file.get_user(brew_bin)
        if mac_user == "root":
            pytest.skip(
                "brew cannot run as root, try a user in {}".format(
                    os.listdir("/Users/")
                )
            )
        cmd_pkg = modules.cmd.run(f"brew info {test_pkg}", run_as=mac_user)
    else:
        pytest.skip("TODO: test not configured for {}".format(grains["os_family"]))
    pkg_latest = modules.pkg.latest_version(test_pkg)
    assert pkg_latest in cmd_pkg


@pytest.mark.usefixtures("_preserve_rhel_yum_conf")
@pytest.mark.destructive_test
@pytest.mark.requires_salt_modules("pkg.list_repos")
@pytest.mark.slow_test
def test_list_repos_duplicate_entries(grains, modules):
    """
    test duplicate entries in /etc/yum.conf

    This is a destructive test as it installs and then removes a package
    """
    if grains["os_family"] != "RedHat":
        pytest.skip("Only runs on RedHat.")

    if grains["os"] == "Amazon":
        pytest.skip("Only runs on RedHat, Amazon /etc/yum.conf differs.")

    # write valid config with duplicates entries
    cfg_file = "/etc/yum.conf"
    with salt.utils.files.fpopen(cfg_file, "w", mode=0o644) as fp_:
        fp_.write("[main]\n")
        fp_.write("gpgcheck=1\n")
        fp_.write("installonly_limit=3\n")
        fp_.write("clean_requirements_on_remove=True\n")
        fp_.write("best=True\n")
        fp_.write("skip_if_unavailable=False\n")
        fp_.write("http_caching=True\n")
        fp_.write("http_caching=True\n")

    ret = modules.pkg.list_repos(strict_config=False)
    assert ret != []
    assert isinstance(ret, dict) is True

    # test explicitly strict_config
    expected = "While reading from '/etc/yum.conf' [line  8]: option 'http_caching' in section 'main' already exists"
    with pytest.raises(configparser.DuplicateOptionError) as exc_info:
        modules.pkg.list_repos(strict_config=True)
    assert str(exc_info.value) == expected

    # test implicitly strict_config
    with pytest.raises(configparser.DuplicateOptionError) as exc_info:
        modules.pkg.list_repos()
    assert str(exc_info.value) == expected


@pytest.mark.destructive_test
@pytest.mark.slow_test
def test_pkg_install_port(grains, modules):
    """
    test install package with a port in the url
    """
    pkgs = modules.pkg.list_pkgs()
    nano = pkgs.get("nano")
    if nano:
        modules.pkg.remove("nano")

    if grains["os_family"] == "Debian":
        url = modules.cmd.run("apt download --print-uris nano").split()[-4]
        if url.startswith("'mirror+file"):
            url = "http://ftp.debian.org/debian/pool/" + url.split("pool")[1].rstrip(
                "'"
            )
        try:
            ret = modules.pkg.install(sources=f'[{{"nano":{url}}}]')
            version = re.compile(r"\d\.\d")
            assert version.search(url).group(0) in ret["nano"]["new"]
        finally:
            modules.pkg.remove("nano")
            if nano:
                # If nano existed on the machine before the test ran
                # re-install that version
                modules.pkg.install(f"nano={nano}")
