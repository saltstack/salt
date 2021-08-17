import textwrap

import pytest
import salt.modules.pkgng as pkgng
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {pkgng: {}}


@pytest.fixture
def pkgs():
    return [
        {"openvpn": "2.4.8_2"},
        {"openvpn": "2.4.8_2", "gettext-runtime": "0.20.1", "p5-Mojolicious": "8.40"},
    ]


def test_latest_version(pkgs):
    """
    Test basic usage of pkgng.latest_version
    """
    pkgs_mock = MagicMock(side_effect=pkgs)
    search_cmd = MagicMock(return_value="bash-5.1.4")
    with patch("salt.modules.pkgng.list_pkgs", pkgs_mock):
        with patch.dict(pkgng.__salt__, {"cmd.run": search_cmd}):
            result = pkgng.latest_version("bash")
            search_cmd.assert_called_with(
                ["pkg", "search", "-eqS", "name", "-U", "bash"],
                output_loglevel="trace",
                python_shell=False,
            )
            assert result == "5.1.4"


def test_latest_version_origin(pkgs):
    """
    Test pkgng.latest_version with a specific package origin
    """
    pkgs_mock = MagicMock(side_effect=pkgs)
    search_cmd = MagicMock(return_value="bash-5.1.4_2")
    with patch("salt.modules.pkgng.list_pkgs", pkgs_mock):
        with patch.dict(pkgng.__salt__, {"cmd.run": search_cmd}):
            result = pkgng.latest_version("shells/bash")
            search_cmd.assert_called_with(
                ["pkg", "search", "-eqS", "origin", "-U", "shells/bash"],
                output_loglevel="trace",
                python_shell=False,
            )
            assert result == "5.1.4_2"


def test_latest_version_outofdatedate(pkgs):
    """
    Test pkgng.latest_version with an out-of-date package
    """
    pkgs_mock = MagicMock(side_effect=pkgs)
    search_cmd = MagicMock(return_value="openvpn-2.4.8_3")
    with patch("salt.modules.pkgng.list_pkgs", pkgs_mock):
        with patch.dict(pkgng.__salt__, {"cmd.run": search_cmd}):
            result = pkgng.latest_version("openvpn")
            search_cmd.assert_called_with(
                ["pkg", "search", "-eqS", "name", "-U", "openvpn"],
                output_loglevel="trace",
                python_shell=False,
            )
            assert result == "2.4.8_3"


def test_latest_version_unavailable(pkgs):
    """
    Test pkgng.latest_version when the requested package is not available
    """
    pkgs_mock = MagicMock(side_effect=pkgs)
    search_cmd = MagicMock(return_value="")
    with patch("salt.modules.pkgng.list_pkgs", pkgs_mock):
        with patch.dict(pkgng.__salt__, {"cmd.run": search_cmd}):
            result = pkgng.latest_version("does_not_exist")
            search_cmd.assert_called_with(
                ["pkg", "search", "-eqS", "name", "-U", "does_not_exist"],
                output_loglevel="trace",
                python_shell=False,
            )


def test_latest_version_uptodate(pkgs):
    """
    Test pkgng.latest_version with an up-to-date package
    """
    pkgs_mock = MagicMock(side_effect=pkgs)
    search_cmd = MagicMock(return_value="openvpn-2.4.8_2")
    with patch("salt.modules.pkgng.list_pkgs", pkgs_mock):
        with patch.dict(pkgng.__salt__, {"cmd.run": search_cmd}):
            result = pkgng.latest_version("openvpn")
            search_cmd.assert_called_with(
                ["pkg", "search", "-eqS", "name", "-U", "openvpn"],
                output_loglevel="trace",
                python_shell=False,
            )
            assert result == ""


def test_lock():
    """
    Test pkgng.lock
    """
    lock_cmd = MagicMock(return_value={"stdout": "pkga-1.0\npkgb-2.0\n", "retcode": 0})
    with patch.dict(pkgng.__salt__, {"cmd.run_all": lock_cmd}):

        result = pkgng.lock("pkga")
        assert result
        lock_cmd.assert_called_with(
            ["pkg", "lock", "-y", "--quiet", "--show-locked", "pkga"],
            output_loglevel="trace",
            python_shell=False,
        )

        result = pkgng.lock("dummy")
        assert not result
        lock_cmd.assert_called_with(
            ["pkg", "lock", "-y", "--quiet", "--show-locked", "dummy"],
            output_loglevel="trace",
            python_shell=False,
        )


def test_unlock():
    """
    Test pkgng.unlock
    """
    unlock_cmd = MagicMock(
        return_value={"stdout": "pkga-1.0\npkgb-2.0\n", "retcode": 0}
    )
    with patch.dict(pkgng.__salt__, {"cmd.run_all": unlock_cmd}):

        result = pkgng.unlock("pkga")
        assert not result
        unlock_cmd.assert_called_with(
            ["pkg", "unlock", "-y", "--quiet", "--show-locked", "pkga"],
            output_loglevel="trace",
            python_shell=False,
        )

        result = pkgng.unlock("dummy")
        assert result
        unlock_cmd.assert_called_with(
            ["pkg", "unlock", "-y", "--quiet", "--show-locked", "dummy"],
            output_loglevel="trace",
            python_shell=False,
        )


def test_locked():
    """
    Test pkgng.unlock
    """
    lock_cmd = MagicMock(return_value={"stdout": "pkga-1.0\npkgb-2.0\n", "retcode": 0})
    with patch.dict(pkgng.__salt__, {"cmd.run_all": lock_cmd}):

        result = pkgng.locked("pkga")
        assert result
        lock_cmd.assert_called_with(
            ["pkg", "lock", "-y", "--quiet", "--show-locked"],
            output_loglevel="trace",
            python_shell=False,
        )

        result = pkgng.locked("dummy")
        assert not result
        lock_cmd.assert_called_with(
            ["pkg", "lock", "-y", "--quiet", "--show-locked"],
            output_loglevel="trace",
            python_shell=False,
        )


def test_list_upgrades_present():
    """
    Test pkgng.list_upgrades with upgrades available
    """
    pkg_cmd = MagicMock(
        return_value=textwrap.dedent(
            """
        The following 6 package(s) will be affected (of 0 checked):

        Installed packages to be UPGRADED:
                pkga: 1.0 -> 1.1
                pkgb: 2.0 -> 2.1 [FreeBSD]
                pkgc: 3.0 -> 3.1 [FreeBSD] (dependency changed)
                pkgd: 4.0 -> 4.1 (dependency changed)

        New packages to be INSTALLED:
                pkge: 1.0
                pkgf: 2.0 [FreeBSD]
                pkgg: 3.0 [FreeBSD] (dependency changed)
                pkgh: 4.0 (dependency changed)

        Installed packages to be REINSTALLED:
                pkgi-1.0
                pkgj-2.0 [FreeBSD]
                pkgk-3.0 [FreeBSD] (direct dependency changed: pkga)
                pkgl-4.0 (direct dependency changed: pkgb)

        Installed packages to be DOWNGRADED:
                pkgm: 1.1 -> 1.0
                pkgn: 2.1 -> 2.0 [FreeBSD]
                pkgo: 3.1 -> 3.0 [FreeBSD] (dependency changed)
                pkgp: 4.1 -> 4.0 (dependency changed)

        Installed packages to be REMOVED:
                pkgq-1.0
                pkgr-2.0 [FreeBSD]
                pkgs-3.0 [FreeBSD] (direct dependency changed: pkga)
                pkgt-4.0 (direct dependency changed: pkgb)

        Number of packages to be upgraded: 2
        Number of packages to be reinstalled: 2

        The process will require 14 MiB more space.
        22 MiB to be downloaded.
        """
        )
    )

    with patch.dict(pkgng.__salt__, {"cmd.run_stdout": pkg_cmd}):

        result = pkgng.list_upgrades(refresh=False)
        assert result == {"pkga": "1.1", "pkgb": "2.1", "pkgc": "3.1", "pkgd": "4.1"}
        pkg_cmd.assert_called_with(
            ["pkg", "upgrade", "--dry-run", "--quiet", "--no-repo-update"],
            output_loglevel="trace",
            python_shell=False,
            ignore_retcode=True,
        )


def test_list_upgrades_absent():
    """
    Test pkgng.list_upgrades with no upgrades available
    """
    pkg_cmd = MagicMock(return_value="")

    with patch.dict(pkgng.__salt__, {"cmd.run_stdout": pkg_cmd}):
        result = pkgng.list_upgrades(refresh=False)
        assert result == {}
        pkg_cmd.assert_called_with(
            ["pkg", "upgrade", "--dry-run", "--quiet", "--no-repo-update"],
            output_loglevel="trace",
            python_shell=False,
            ignore_retcode=True,
        )


def test_upgrade_without_fromrepo(pkgs):
    """
    Test pkg upgrade to upgrade all available packages
    """
    pkg_cmd = MagicMock(return_value={"retcode": 0})
    pkgs_mock = MagicMock(side_effect=pkgs)

    with patch.dict(pkgng.__salt__, {"cmd.run_all": pkg_cmd}):
        with patch("salt.modules.pkgng.list_pkgs", pkgs_mock):
            result = pkgng.upgrade()
            expected = {
                "gettext-runtime": {"new": "0.20.1", "old": ""},
                "p5-Mojolicious": {"new": "8.40", "old": ""},
            }
            assert result == expected
            pkg_cmd.assert_called_with(
                ["pkg", "upgrade", "-y"],
                output_loglevel="trace",
                python_shell=False,
            )


def test_upgrade_with_fromrepo(pkgs):
    """
    Test pkg upgrade to upgrade all available packages
    """
    pkg_cmd = MagicMock(return_value={"retcode": 0})
    pkgs_mock = MagicMock(side_effect=pkgs)

    with patch.dict(pkgng.__salt__, {"cmd.run_all": pkg_cmd}):
        with patch("salt.modules.pkgng.list_pkgs", pkgs_mock):
            result = pkgng.upgrade(fromrepo="FreeBSD")
            expected = {
                "gettext-runtime": {"new": "0.20.1", "old": ""},
                "p5-Mojolicious": {"new": "8.40", "old": ""},
            }
            assert result == expected
            pkg_cmd.assert_called_with(
                ["pkg", "upgrade", "-y", "--repository", "FreeBSD"],
                output_loglevel="trace",
                python_shell=False,
            )


def test_upgrade_with_fetchonly(pkgs):
    """
    Test pkg upgrade to fetch packages only
    """
    pkg_cmd = MagicMock(return_value={"retcode": 0})
    pkgs_mock = MagicMock(side_effect=pkgs)

    with patch.dict(pkgng.__salt__, {"cmd.run_all": pkg_cmd}):
        with patch("salt.modules.pkgng.list_pkgs", pkgs_mock):
            result = pkgng.upgrade(fetchonly=True)
            expected = {
                "gettext-runtime": {"new": "0.20.1", "old": ""},
                "p5-Mojolicious": {"new": "8.40", "old": ""},
            }
            assert result == expected
            pkg_cmd.assert_called_with(
                ["pkg", "upgrade", "-Fy"],
                output_loglevel="trace",
                python_shell=False,
            )


def test_upgrade_with_local(pkgs):
    """
    Test pkg upgrade to supress automatic update of the local copy of the
    repository catalogue from remote
    """
    pkg_cmd = MagicMock(return_value={"retcode": 0})
    pkgs_mock = MagicMock(side_effect=pkgs)

    with patch.dict(pkgng.__salt__, {"cmd.run_all": pkg_cmd}):
        with patch("salt.modules.pkgng.list_pkgs", pkgs_mock):
            result = pkgng.upgrade(local=True)
            expected = {
                "gettext-runtime": {"new": "0.20.1", "old": ""},
                "p5-Mojolicious": {"new": "8.40", "old": ""},
            }
            assert result == expected
            pkg_cmd.assert_called_with(
                ["pkg", "upgrade", "-Uy"],
                output_loglevel="trace",
                python_shell=False,
            )


def test_stats_with_local():
    """
    Test pkg.stats for local packages
    """
    pkg_cmd = MagicMock(return_value="")

    with patch.dict(pkgng.__salt__, {"cmd.run": pkg_cmd}):
        result = pkgng.stats(local=True)
        assert result == []
        pkg_cmd.assert_called_with(
            ["pkg", "stats", "-l"],
            output_loglevel="trace",
            python_shell=False,
        )


def test_stats_with_remote():
    """
    Test pkg.stats for remote packages
    """
    pkg_cmd = MagicMock(return_value="")

    with patch.dict(pkgng.__salt__, {"cmd.run": pkg_cmd}):
        result = pkgng.stats(remote=True)
        assert result == []
        pkg_cmd.assert_called_with(
            ["pkg", "stats", "-r"],
            output_loglevel="trace",
            python_shell=False,
        )


def test_stats_with_bytes_remote():
    """
    Test pkg.stats to show disk space usage in bytes only for remote
    """
    pkg_cmd = MagicMock(return_value="")

    with patch.dict(pkgng.__salt__, {"cmd.run": pkg_cmd}):
        result = pkgng.stats(remote=True, bytes=True)
        assert result == []
        pkg_cmd.assert_called_with(
            ["pkg", "stats", "-rb"],
            output_loglevel="trace",
            python_shell=False,
        )


def test_stats_with_bytes_local():
    """
    Test pkg.stats to show disk space usage in bytes only for local
    """
    pkg_cmd = MagicMock(return_value="")

    with patch.dict(pkgng.__salt__, {"cmd.run": pkg_cmd}):
        result = pkgng.stats(local=True, bytes=True)
        assert result == []
        pkg_cmd.assert_called_with(
            ["pkg", "stats", "-lb"],
            output_loglevel="trace",
            python_shell=False,
        )


def test_install_without_args(pkgs):
    """
    Test pkg.install to install a package without arguments
    """
    parsed_targets = (
        OrderedDict((("gettext-runtime", None), ("p5-Mojolicious", None))),
        "repository",
    )
    pkg_cmd = MagicMock(return_value={"retcode": 0})
    pkgs_mock = MagicMock(side_effect=pkgs)
    patches = {
        "cmd.run_all": pkg_cmd,
        "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
    }
    with patch.dict(pkgng.__salt__, patches):
        with patch("salt.modules.pkgng.list_pkgs", pkgs_mock):
            added = pkgng.install()
            expected = {
                "gettext-runtime": {"new": "0.20.1", "old": ""},
                "p5-Mojolicious": {"new": "8.40", "old": ""},
            }
            assert added == expected
            pkg_cmd.assert_called_with(
                ["pkg", "install", "-y", "gettext-runtime", "p5-Mojolicious"],
                output_loglevel="trace",
                python_shell=False,
                env={},
            )


def test_install_with_local(pkgs):
    """
    Test pkg.install to install a package with local=True argument
    """
    parsed_targets = (
        OrderedDict((("gettext-runtime", None), ("p5-Mojolicious", None))),
        "repository",
    )
    pkg_cmd = MagicMock(return_value={"retcode": 0})
    pkgs_mock = MagicMock(side_effect=pkgs)
    patches = {
        "cmd.run_all": pkg_cmd,
        "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
    }
    with patch.dict(pkgng.__salt__, patches):
        with patch("salt.modules.pkgng.list_pkgs", pkgs_mock):
            added = pkgng.install(local=True)
            expected = {
                "gettext-runtime": {"new": "0.20.1", "old": ""},
                "p5-Mojolicious": {"new": "8.40", "old": ""},
            }
            assert added == expected
            pkg_cmd.assert_called_with(
                ["pkg", "install", "-yU", "gettext-runtime", "p5-Mojolicious"],
                output_loglevel="trace",
                python_shell=False,
                env={},
            )


def test_install_with_fromrepo(pkgs):
    """
    Test pkg.install to install a package with fromrepo=FreeBSD argument
    """
    parsed_targets = (
        OrderedDict((("gettext-runtime", None), ("p5-Mojolicious", None))),
        "repository",
    )
    pkg_cmd = MagicMock(return_value={"retcode": 0})
    pkgs_mock = MagicMock(side_effect=pkgs)
    patches = {
        "cmd.run_all": pkg_cmd,
        "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
    }
    with patch.dict(pkgng.__salt__, patches):
        with patch("salt.modules.pkgng.list_pkgs", pkgs_mock):
            added = pkgng.install(fromrepo="FreeBSD")
            expected = {
                "gettext-runtime": {"new": "0.20.1", "old": ""},
                "p5-Mojolicious": {"new": "8.40", "old": ""},
            }
            assert added == expected
            pkg_cmd.assert_called_with(
                [
                    "pkg",
                    "install",
                    "-r",
                    "FreeBSD",
                    "-y",
                    "gettext-runtime",
                    "p5-Mojolicious",
                ],
                output_loglevel="trace",
                python_shell=False,
                env={},
            )


def test_install_with_glob(pkgs):
    """
    Test pkg.install to install a package with glob=True argument
    """
    parsed_targets = (
        OrderedDict((("gettext-runtime", None), ("p5-Mojolicious", None))),
        "repository",
    )
    pkg_cmd = MagicMock(return_value={"retcode": 0})
    pkgs_mock = MagicMock(side_effect=pkgs)
    patches = {
        "cmd.run_all": pkg_cmd,
        "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
    }
    with patch.dict(pkgng.__salt__, patches):
        with patch("salt.modules.pkgng.list_pkgs", pkgs_mock):
            added = pkgng.install(glob=True)
            expected = {
                "gettext-runtime": {"new": "0.20.1", "old": ""},
                "p5-Mojolicious": {"new": "8.40", "old": ""},
            }
            assert added == expected
            pkg_cmd.assert_called_with(
                ["pkg", "install", "-yg", "gettext-runtime", "p5-Mojolicious"],
                output_loglevel="trace",
                python_shell=False,
                env={},
            )


def test_install_with_reinstall_requires(pkgs):
    """
    Test pkg.install to install a package with reinstall_requires=True argument
    """
    parsed_targets = (
        OrderedDict((("gettext-runtime", None), ("p5-Mojolicious", None))),
        "repository",
    )
    pkg_cmd = MagicMock(return_value={"retcode": 0})
    pkgs_mock = MagicMock(side_effect=pkgs)
    patches = {
        "cmd.run_all": pkg_cmd,
        "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
    }
    with patch.dict(pkgng.__salt__, patches):
        with patch("salt.modules.pkgng.list_pkgs", pkgs_mock):
            added = pkgng.install(reinstall_requires=True, force=True)
            expected = {
                "gettext-runtime": {"new": "0.20.1", "old": ""},
                "p5-Mojolicious": {"new": "8.40", "old": ""},
            }
            assert added == expected
            pkg_cmd.assert_called_with(
                ["pkg", "install", "-yfR", "gettext-runtime", "p5-Mojolicious"],
                output_loglevel="trace",
                python_shell=False,
                env={},
            )


def test_install_with_regex(pkgs):
    """
    Test pkg.install to install a package with regex=True argument
    """
    parsed_targets = (
        OrderedDict((("gettext-runtime", None), ("p5-Mojolicious", None))),
        "repository",
    )
    pkg_cmd = MagicMock(return_value={"retcode": 0})
    pkgs_mock = MagicMock(side_effect=pkgs)
    patches = {
        "cmd.run_all": pkg_cmd,
        "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
    }
    with patch.dict(pkgng.__salt__, patches):
        with patch("salt.modules.pkgng.list_pkgs", pkgs_mock):
            added = pkgng.install(regex=True)
            expected = {
                "gettext-runtime": {"new": "0.20.1", "old": ""},
                "p5-Mojolicious": {"new": "8.40", "old": ""},
            }
            assert added == expected
            pkg_cmd.assert_called_with(
                ["pkg", "install", "-yx", "gettext-runtime", "p5-Mojolicious"],
                output_loglevel="trace",
                python_shell=False,
                env={},
            )


def test_install_with_batch(pkgs):
    """
    Test pkg.install to install a package with batch=True argument
    """
    parsed_targets = (
        OrderedDict((("gettext-runtime", None), ("p5-Mojolicious", None))),
        "repository",
    )
    pkg_cmd = MagicMock(return_value={"retcode": 0})
    pkgs_mock = MagicMock(side_effect=pkgs)
    patches = {
        "cmd.run_all": pkg_cmd,
        "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
    }
    with patch.dict(pkgng.__salt__, patches):
        with patch("salt.modules.pkgng.list_pkgs", pkgs_mock):
            added = pkgng.install(batch=True)
            expected = {
                "gettext-runtime": {"new": "0.20.1", "old": ""},
                "p5-Mojolicious": {"new": "8.40", "old": ""},
            }
            assert added == expected
            pkg_cmd.assert_called_with(
                ["pkg", "install", "-y", "gettext-runtime", "p5-Mojolicious"],
                output_loglevel="trace",
                python_shell=False,
                env={"BATCH": "true", "ASSUME_ALWAYS_YES": "YES"},
            )


def test_install_with_pcre(pkgs):
    """
    Test pkg.install to install a package with pcre=True argument
    """
    parsed_targets = (
        OrderedDict((("gettext-runtime", None), ("p5-Mojolicious", None))),
        "repository",
    )
    pkg_cmd = MagicMock(return_value={"retcode": 0})
    pkgs_mock = MagicMock(side_effect=pkgs)
    patches = {
        "cmd.run_all": pkg_cmd,
        "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
    }
    with patch.dict(pkgng.__salt__, patches):
        with patch("salt.modules.pkgng.list_pkgs", pkgs_mock):
            added = pkgng.install(pcre=True)
            expected = {
                "gettext-runtime": {"new": "0.20.1", "old": ""},
                "p5-Mojolicious": {"new": "8.40", "old": ""},
            }
            assert added == expected
            pkg_cmd.assert_called_with(
                ["pkg", "install", "-yX", "gettext-runtime", "p5-Mojolicious"],
                output_loglevel="trace",
                python_shell=False,
                env={},
            )


def test_install_with_orphan(pkgs):
    """
    Test pkg.install to install a package with orphan=True argument
    """
    parsed_targets = (
        OrderedDict((("gettext-runtime", None), ("p5-Mojolicious", None))),
        "repository",
    )
    pkg_cmd = MagicMock(return_value={"retcode": 0})
    pkgs_mock = MagicMock(side_effect=pkgs)
    patches = {
        "cmd.run_all": pkg_cmd,
        "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
    }
    with patch.dict(pkgng.__salt__, patches):
        with patch("salt.modules.pkgng.list_pkgs", pkgs_mock):
            added = pkgng.install(orphan=True)
            expected = {
                "gettext-runtime": {"new": "0.20.1", "old": ""},
                "p5-Mojolicious": {"new": "8.40", "old": ""},
            }
            assert added == expected
            pkg_cmd.assert_called_with(
                ["pkg", "install", "-yA", "gettext-runtime", "p5-Mojolicious"],
                output_loglevel="trace",
                python_shell=False,
                env={},
            )


def test_check_depends():
    """
    Test pkgng.check to check and install missing dependencies
    """
    pkg_cmd = MagicMock(return_value="")

    with patch.dict(pkgng.__salt__, {"cmd.run": pkg_cmd}):
        result = pkgng.check(depends=True)
        assert result == ""
        pkg_cmd.assert_called_with(
            ["pkg", "check", "-dy"],
            output_loglevel="trace",
            python_shell=False,
        )


def test_check_checksum():
    """
    Test pkgng.check for packages with invalid checksums
    """
    pkg_cmd = MagicMock(return_value="")

    with patch.dict(pkgng.__salt__, {"cmd.run": pkg_cmd}):
        result = pkgng.check(checksum=True)
        assert result == ""
        pkg_cmd.assert_called_with(
            ["pkg", "check", "-s"],
            output_loglevel="trace",
            python_shell=False,
        )


def test_check_recompute():
    """
    Test pkgng.check to recalculate the checksums of installed packages
    """
    pkg_cmd = MagicMock(return_value="")

    with patch.dict(pkgng.__salt__, {"cmd.run": pkg_cmd}):
        result = pkgng.check(recompute=True)
        assert result == ""
        pkg_cmd.assert_called_with(
            ["pkg", "check", "-r"],
            output_loglevel="trace",
            python_shell=False,
        )


def test_check_checklibs():
    """
    Test pkgng.check to regenerate the library dependency metadata
    """
    pkg_cmd = MagicMock(return_value="")

    with patch.dict(pkgng.__salt__, {"cmd.run": pkg_cmd}):
        result = pkgng.check(checklibs=True)
        assert result == ""
        pkg_cmd.assert_called_with(
            ["pkg", "check", "-B"],
            output_loglevel="trace",
            python_shell=False,
        )


def test_autoremove_with_dryrun():
    """
    Test pkgng.autoremove with dryrun argument
    """
    pkg_cmd = MagicMock(return_value="")

    with patch.dict(pkgng.__salt__, {"cmd.run": pkg_cmd}):
        result = pkgng.autoremove(dryrun=True)
        assert result == ""
        pkg_cmd.assert_called_with(
            ["pkg", "autoremove", "-n"],
            output_loglevel="trace",
            python_shell=False,
        )


def test_autoremove():
    """
    Test pkgng.autoremove
    """
    pkg_cmd = MagicMock(return_value="")

    with patch.dict(pkgng.__salt__, {"cmd.run": pkg_cmd}):

        result = pkgng.autoremove()
        assert result == ""
        pkg_cmd.assert_called_with(
            ["pkg", "autoremove", "-y"],
            output_loglevel="trace",
            python_shell=False,
        )


def test_audit():
    """
    Test pkgng.audit
    """
    pkg_cmd = MagicMock(return_value="")

    with patch.dict(pkgng.__salt__, {"cmd.run": pkg_cmd}):

        result = pkgng.audit()
        assert result == ""
        pkg_cmd.assert_called_with(
            ["pkg", "audit", "-F"],
            output_loglevel="trace",
            python_shell=False,
        )


def test_version():
    """
    Test pkgng.version
    """
    version = "2.0.6"
    mock = MagicMock(return_value=version)
    with patch.dict(pkgng.__salt__, {"pkg_resource.version": mock}):

        assert pkgng.version(*["mutt"]) == version
        assert not pkgng.version(*["mutt"]) == "2.0.10"


def test_refresh_db_without_forced_flag():
    """
    Test pkgng.refresh_db with force=False
    """
    pkg_cmd = MagicMock(return_value=0)
    with patch("salt.utils.pkg.clear_rtag", MagicMock()):
        with patch.dict(pkgng.__salt__, {"cmd.retcode": pkg_cmd}):

            result = pkgng.refresh_db()
            assert result is True
            pkg_cmd.assert_called_with(
                ["pkg", "update"],
                python_shell=False,
            )


def test_refresh_db_with_forced_flag():
    """
    Test pkgng.refresh_db with force=True
    """
    pkg_cmd = MagicMock(return_value=0)
    with patch("salt.utils.pkg.clear_rtag", MagicMock()):
        with patch.dict(pkgng.__salt__, {"cmd.retcode": pkg_cmd}):

            result = pkgng.refresh_db(force=True)
            assert result is True
            pkg_cmd.assert_called_with(
                ["pkg", "update", "-f"],
                python_shell=False,
            )


def test_fetch_with_default_flag():
    """
    Test pkgng.fetch with default options
    """

    targets = "mutt"
    pkg_cmd = MagicMock(return_value=targets)
    patches = {
        "cmd.run": pkg_cmd,
        "pkg_resource.stringify": MagicMock(),
        "pkg_resource.parse_targets": MagicMock(return_value=targets),
    }
    with patch.dict(pkgng.__salt__, patches):
        pkgs = pkgng.fetch(targets)
        assert pkgs == targets
    pkg_cmd.assert_called_once_with(
        ["pkg", "fetch", "-y", "-g", "mutt"],
        output_loglevel="trace",
        python_shell=False,
    )


def test_fetch_with_dependency_flag():
    """
    Test pkgng.fetch with enabled dependency flag
    """

    targets = "mutt"
    pkg_cmd = MagicMock(return_value=targets)
    patches = {
        "cmd.run": pkg_cmd,
        "pkg_resource.stringify": MagicMock(),
        "pkg_resource.parse_targets": MagicMock(return_value=targets),
    }
    with patch.dict(pkgng.__salt__, patches):
        pkgs = pkgng.fetch(targets, depends=True)
        assert pkgs == targets
    pkg_cmd.assert_called_once_with(
        ["pkg", "fetch", "-y", "-gd", "mutt"],
        output_loglevel="trace",
        python_shell=False,
    )


def test_fetch_with_regex_flag():
    """
    Test pkgng.fetch with enabled regex flag
    """

    targets = "mutt"
    pkg_cmd = MagicMock(return_value=targets)
    patches = {
        "cmd.run": pkg_cmd,
        "pkg_resource.stringify": MagicMock(),
        "pkg_resource.parse_targets": MagicMock(return_value=targets),
    }
    with patch.dict(pkgng.__salt__, patches):
        pkgs = pkgng.fetch(targets, regex=True)
        assert pkgs == targets
    pkg_cmd.assert_called_once_with(
        ["pkg", "fetch", "-y", "-gx", "mutt"],
        output_loglevel="trace",
        python_shell=False,
    )


def test_fetch_with_fromrepo_flag():
    """
    Test pkgng.fetch with enabled fromrepo flag
    """

    targets = "mutt"
    pkg_cmd = MagicMock(return_value=targets)
    patches = {
        "cmd.run": pkg_cmd,
        "pkg_resource.stringify": MagicMock(),
        "pkg_resource.parse_targets": MagicMock(return_value=targets),
    }
    with patch.dict(pkgng.__salt__, patches):
        pkgs = pkgng.fetch(targets, fromrepo="FreeBSD-poudriere")
        assert pkgs == targets
    pkg_cmd.assert_called_once_with(
        ["pkg", "fetch", "-y", "-r", "FreeBSD-poudriere", "-g", "mutt"],
        output_loglevel="trace",
        python_shell=False,
    )


def test_fetch_with_localcache_flag():
    """
    Test pkgng.fetch with enabled localcache flag
    """

    targets = "mutt"
    pkg_cmd = MagicMock(return_value=targets)
    patches = {
        "cmd.run": pkg_cmd,
        "pkg_resource.stringify": MagicMock(),
        "pkg_resource.parse_targets": MagicMock(return_value=targets),
    }
    with patch.dict(pkgng.__salt__, patches):
        pkgs = pkgng.fetch(targets, local=True)
        assert pkgs == targets
    pkg_cmd.assert_called_once_with(
        ["pkg", "fetch", "-y", "-gL", "mutt"],
        output_loglevel="trace",
        python_shell=False,
    )


def test_which_with_default_flags():
    """
    Test pkgng.which
    """
    which_cmd = MagicMock(
        return_value={
            "stdout": "/usr/local/bin/mutt was installed by package mutt-2.0.6",
            "retcode": 0,
        }
    )
    with patch.dict(pkgng.__salt__, {"cmd.run": which_cmd}):

        result = pkgng.which("/usr/local/bin/mutt")
        assert result
        which_cmd.assert_called_with(
            ["pkg", "which", "/usr/local/bin/mutt"],
            output_loglevel="trace",
            python_shell=False,
        )


def test_which_with_origin_flag():
    """
    Test pkgng.which with enabled origin flag
    """
    which_cmd = MagicMock(
        return_value={
            "stdout": "/usr/local/bin/mutt was installed by package mail/mutt",
            "retcode": 0,
        }
    )
    with patch.dict(pkgng.__salt__, {"cmd.run": which_cmd}):

        result = pkgng.which("/usr/local/bin/mutt", origin=True)
        assert result
        which_cmd.assert_called_with(
            ["pkg", "which", "-o", "/usr/local/bin/mutt"],
            output_loglevel="trace",
            python_shell=False,
        )
