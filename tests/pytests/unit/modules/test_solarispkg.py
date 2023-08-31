import logging

import pytest

import salt.modules.solarispkg as solarispkg
from tests.support.mock import ANY, MagicMock, call, patch

log = logging.getLogger(__name__)


class ListPackages:
    def __init__(self, iteration=0):
        self._iteration = iteration

    def __call__(self):
        # Package information returned two lines per package. On even-offset
        # lines, the package name is in the first column. On odd-offset lines, the
        # package version is in the second column.
        pkg_lists = [
            {
                "SUNWbzip": "11.10.0,REV=2005.01.08.01.09",
                "SUNWgzip": "11.10.0,REV=2005.01.08.01.09",
                "SUNWzip": "11.10.0,REV=2005.01.08.01.09",
                "SUNWzlib": "11.10.0,REV=2005.01.08.01.09",
            },
            {
                "SUNWbzip": "11.10.0,REV=2005.01.08.01.09",
                "SUNWgzip": "11.10.0,REV=2005.01.08.01.09",
                "SUNWzip": "11.10.0,REV=2005.01.08.01.09",
                "SUNWzlib": "11.10.0,REV=2005.01.08.01.09",
                "SUNWbashS": "11.10.0,REV=2005.01.08.01.09",
            },
        ]
        pkgs = pkg_lists[self._iteration]
        self._iteration = (self._iteration + 1) % 2
        return pkgs


@pytest.fixture
def configure_loader_modules():

    return {
        solarispkg: {
            "__grains__": {
                "osarch": "sparcv9",
                "os_family": "Solaris",
                "osmajorrelease": 10,
                "kernelrelease": 5.10,
            },
        },
    }


def test_list_pkgs():
    """
    Test for listing installed packages.
    """

    def _add_data(data, key, value):
        data[key] = value

    pkg_info_out = [
        "SUNWbzip                          The bzip compression utility",
        "                                  (i386) 11.10.0,REV=2005.01.08.01.09",
        "SUNWgzip                          The GNU Zip (gzip) compression utility",
        "                                  (i386) 11.10.0,REV=2005.01.08.01.09",
        "SUNWzip                           The Info-Zip (zip) compression utility",
        "                                  (i386) 11.10.0,REV=2005.01.08.01.09",
        "SUNWzlib                          The Zip compression library",
        "                                  (i386) 11.10.0,REV=2005.01.08.01.09",
    ]
    run_mock = MagicMock(return_value="\n".join(pkg_info_out))
    patches = {
        "cmd.run": run_mock,
        "pkg_resource.add_pkg": _add_data,
        "pkg_resource.sort_pkglist": MagicMock(),
        "pkg_resource.stringify": MagicMock(),
    }
    with patch.dict(solarispkg.__salt__, patches):
        pkgs = solarispkg.list_pkgs()
        assert pkgs == {
            "SUNWbzip": "11.10.0,REV=2005.01.08.01.09",
            "SUNWgzip": "11.10.0,REV=2005.01.08.01.09",
            "SUNWzip": "11.10.0,REV=2005.01.08.01.09",
            "SUNWzlib": "11.10.0,REV=2005.01.08.01.09",
        }
    run_mock.assert_called_once_with(
        "/usr/bin/pkginfo -x", output_loglevel="trace", python_shell=False
    )


def test_install_single_named_package():
    """
    Test installing a single package
    - a single package SUNWbashS from current drive
    """

    install_target = "SUNWbashS"
    parsed_targets = (
        {install_target: None},
        "repository",
    )
    cmd_out = {
        "retcode": 0,
        "stdout": "",
        "stderr": "",
    }
    run_all_mock = MagicMock(return_value=cmd_out)
    patches = {
        "cmd.run_all": run_all_mock,
        "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
        "pkg_resource.stringify": MagicMock(),
        "pkg_resource.sort_pkglist": MagicMock(),
        "cmd.retcode": MagicMock(return_value=False),
    }

    with patch.dict(solarispkg.__salt__, patches):
        with patch("salt.modules.solarispkg.list_pkgs", ListPackages()):
            added = solarispkg.install(
                install_target,
                sources=[{install_target: "tests/pytest/unit/module/sol10_pkg/bashs"}],
                refresh=False,
            )
            expected = {
                "SUNWbashS": {"new": "11.10.0,REV=2005.01.08.01.09", "old": ""},
            }
            assert added == expected

    expected_calls = [
        call(
            ["/usr/sbin/pkgadd", "-n", "-a", ANY, "-d", install_target, "all"],
            output_loglevel="trace",
            python_shell=False,
        ),
    ]
    run_all_mock.assert_has_calls(expected_calls, any_order=True)
    assert run_all_mock.call_count == 1


def test_install_single_named_package_global_zone_boolean():
    """
    Test installing a single package
    - a single package SUNWbashS from current drive
    """

    install_target = "SUNWbashS"
    parsed_targets = (
        {install_target: None},
        "repository",
    )
    cmd_out = {
        "retcode": 0,
        "stdout": "",
        "stderr": "",
    }
    run_all_mock = MagicMock(return_value=cmd_out)
    patches = {
        "cmd.run_all": run_all_mock,
        "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
        "pkg_resource.stringify": MagicMock(),
        "pkg_resource.sort_pkglist": MagicMock(),
        "cmd.retcode": MagicMock(return_value=False),
    }

    with patch.dict(solarispkg.__salt__, patches):
        with patch("salt.modules.solarispkg.list_pkgs", ListPackages()):
            added = solarispkg.install(
                install_target,
                sources=[{install_target: "tests/pytest/unit/module/sol10_pkg/bashs"}],
                refresh=False,
                current_zone_only=True,
            )
            expected = {
                "SUNWbashS": {"new": "11.10.0,REV=2005.01.08.01.09", "old": ""},
            }
            assert added == expected

    expected_calls = [
        call(
            [
                "/usr/sbin/pkgadd",
                "-n",
                "-a",
                ANY,
                "-G ",
                "-d",
                install_target,
                "all",
            ],
            output_loglevel="trace",
            python_shell=False,
        ),
    ]
    run_all_mock.assert_has_calls(expected_calls, any_order=True)
    assert run_all_mock.call_count == 1


def test_install_single_named_package_global_zone_text():
    """
    Test installing a single package
    - a single package SUNWbashS from current drive
    """

    install_target = "SUNWbashS"
    parsed_targets = (
        {install_target: None},
        "repository",
    )
    cmd_out = {
        "retcode": 0,
        "stdout": "",
        "stderr": "",
    }
    run_all_mock = MagicMock(return_value=cmd_out)
    patches = {
        "cmd.run_all": run_all_mock,
        "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
        "pkg_resource.stringify": MagicMock(),
        "pkg_resource.sort_pkglist": MagicMock(),
        "cmd.retcode": MagicMock(return_value=False),
    }

    with patch.dict(solarispkg.__salt__, patches):
        with patch("salt.modules.solarispkg.list_pkgs", ListPackages()):
            added = solarispkg.install(
                install_target,
                sources=[{install_target: "tests/pytest/unit/module/sol10_pkg/bashs"}],
                refresh=False,
                current_zone_only="True",
            )
            expected = {
                "SUNWbashS": {"new": "11.10.0,REV=2005.01.08.01.09", "old": ""},
            }
            assert added == expected

    expected_calls = [
        call(
            [
                "/usr/sbin/pkgadd",
                "-n",
                "-a",
                ANY,
                "-G ",
                "-d",
                install_target,
                "all",
            ],
            output_loglevel="trace",
            python_shell=False,
        ),
    ]
    run_all_mock.assert_has_calls(expected_calls, any_order=True)
    assert run_all_mock.call_count == 1


def test_remove_single_named_package():
    """
    Test removing a single specific named package
    - a single package SUNWbashS
    """

    install_target = "SUNWbashS"
    parsed_targets = (
        {install_target: None},
        "repository",
    )
    cmd_out = {
        "retcode": 0,
        "stdout": "",
        "stderr": "",
    }
    run_all_mock = MagicMock(return_value=cmd_out)
    patches = {
        "cmd.run_all": run_all_mock,
        "pkg_resource.parse_targets": MagicMock(return_value=parsed_targets),
        "pkg_resource.stringify": MagicMock(),
        "pkg_resource.sort_pkglist": MagicMock(),
        "cmd.retcode": MagicMock(return_value=False),
    }

    with patch.dict(solarispkg.__salt__, patches):
        with patch("salt.modules.solarispkg.list_pkgs", ListPackages(1)):
            added = solarispkg.remove(install_target, refresh=False)
            expected = {
                "SUNWbashS": {"new": "", "old": "11.10.0,REV=2005.01.08.01.09"},
            }
            assert added == expected

    expected_calls = [
        call(
            ["/usr/sbin/pkgrm", "-n", "-a", ANY, install_target],
            output_loglevel="trace",
            python_shell=False,
        ),
    ]
    run_all_mock.assert_has_calls(expected_calls, any_order=True)
    assert run_all_mock.call_count == 1
