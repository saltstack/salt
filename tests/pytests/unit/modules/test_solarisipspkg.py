import logging

import salt.modules.solarisipspkg as solarisipspkg
from tests.support.mock import MagicMock, call, patch

try:
    import pytest
except ImportError:
    pytest = None

log = logging.getLogger(__name__)


class ListPackages:
    def __init__(self):
        self._iteration = 0

    def __call__(self):
        pkg_lists = [
            {
                "pkg://solaris/compress/bzip2": "1.0.6-11.4.0.0.1.14.0:20180814T153143Z",
                "pkg://solaris/compress/gzip": "1.8-11.4.0.0.1.14.0:20180814T153144Z",
                "pkg://solaris/compress/p7zip": "16.2.3-11.4.0.0.1.14.0:20180814T153145Z",
                "pkg://solaris/compress/pbzip2": "1.1.13-11.4.0.0.1.14.0:20180814T153147Z",
                "pkg://solaris/compress/unzip": "6.0.3.23-11.4.0.0.1.14.0:20180814T153150Z",
            },
            {
                "pkg://solaris/compress/bzip2": "1.0.6-11.4.0.0.1.14.0:20180814T153143Z",
                "pkg://solaris/compress/gzip": "1.8-11.4.0.0.1.14.0:20180814T153144Z",
                "pkg://solaris/compress/p7zip": "16.2.3-11.4.0.0.1.14.0:20180814T153145Z",
                "pkg://solaris/compress/pbzip2": "1.1.13-11.4.0.0.1.14.0:20180814T153147Z",
                "pkg://solaris/compress/unzip": "6.0.3.23-11.4.0.0.1.14.0:20180814T153150Z",
                "pkg://solaris/compress/zip": "3.0-11.4.0.0.1.14.0:20180814T153154Z",
            },
        ]
        pkgs = pkg_lists[self._iteration]
        self._iteration += 1
        return pkgs


class ListPackagesDict:
    def __init__(self):
        self._iteration = 0

    def __call__(self):
        pkg_lists = [
            {
                "pkg://solaris/compress/bzip2": "1.0.6-11.4.0.0.1.14.0:20180814T153143Z",
                "pkg://solaris/compress/gzip": "1.8-11.4.0.0.1.14.0:20180814T153144Z",
                "pkg://solaris/compress/p7zip": "16.2.3-11.4.0.0.1.14.0:20180814T153145Z",
                "pkg://solaris/compress/pbzip2": "1.1.13-11.4.0.0.1.14.0:20180814T153147Z",
                "pkg://solaris/compress/unzip": "6.0.3.23-11.4.0.0.1.14.0:20180814T153150Z",
            },
            {
                "pkg://solaris/compress/bzip2": "1.0.6-11.4.0.0.1.14.0:20180814T153143Z",
                "pkg://solaris/compress/gzip": "1.8-11.4.0.0.1.14.0:20180814T153144Z",
                "pkg://solaris/compress/p7zip": "16.2.3-11.4.0.0.1.14.0:20180814T153145Z",
                "pkg://solaris/compress/pbzip2": "1.1.13-11.4.0.0.1.14.0:20180814T153147Z",
                "pkg://solaris/compress/unzip": "6.0.3.23-11.4.0.0.1.14.0:20180814T153150Z",
                "pkg://solaris/file/tree": "1.7.0-11.4.0.0.1.14.0:20180814T163602Z",
                "pkg://solaris/x11/xclock": "1.0.7-11.4.0.0.1.14.0:20180814T173537Z",
            },
        ]
        pkgs = pkg_lists[self._iteration]
        self._iteration += 1
        return pkgs


@pytest.fixture
def configure_loader_modules():

    return {
        solarisipspkg: {
            "__grains__": {
                "osarch": "sparcv9",
                "os_family": "Solaris",
                "osmajorrelease": 11,
                "kernelrelease": 5.11,
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
        "pkg://solaris/compress/bzip2@1.0.6-11.4.0.0.1.14.0:20180814T153143Z          i--",
        "pkg://solaris/compress/gzip@1.8-11.4.0.0.1.14.0:20180814T153144Z             i--",
        "pkg://solaris/compress/p7zip@16.2.3-11.4.0.0.1.14.0:20180814T153145Z         i--",
        "pkg://solaris/compress/pbzip2@1.1.13-11.4.0.0.1.14.0:20180814T153147Z        i--",
        "pkg://solaris/compress/unzip@6.0.3.23-11.4.0.0.1.14.0:20180814T153150Z       i--",
    ]
    run_stdout_mock = MagicMock(return_value="\n".join(pkg_info_out))
    patches = {
        "cmd.run_stdout": run_stdout_mock,
        "pkg_resource.add_pkg": _add_data,
        "pkg_resource.sort_pkglist": MagicMock(),
        "pkg_resource.stringify": MagicMock(),
    }
    with patch.dict(solarisipspkg.__salt__, patches):
        pkgs = solarisipspkg.list_pkgs()
        assert pkgs == {
            "pkg://solaris/compress/bzip2": "1.0.6-11.4.0.0.1.14.0:20180814T153143Z",
            "pkg://solaris/compress/gzip": "1.8-11.4.0.0.1.14.0:20180814T153144Z",
            "pkg://solaris/compress/p7zip": "16.2.3-11.4.0.0.1.14.0:20180814T153145Z",
            "pkg://solaris/compress/pbzip2": "1.1.13-11.4.0.0.1.14.0:20180814T153147Z",
            "pkg://solaris/compress/unzip": "6.0.3.23-11.4.0.0.1.14.0:20180814T153150Z",
        }
    run_stdout_mock.assert_called_once_with("/bin/pkg list -Hv")


def test_install_single_named_package():
    """
    Test installing a single package
    - a single package pkg://solaris/compress/zip 3.0-11.4.0.0.1.14.0:20180814T153154Z
    """

    install_target = "compress/zip"
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
        "solarisipspkg.is_installed": MagicMock(return_value=False),
        "cmd.retcode": MagicMock(return_value=False),
    }

    with patch.dict(solarisipspkg.__salt__, patches):
        with patch("salt.modules.solarisipspkg.list_pkgs", ListPackages()), patch(
            "salt.modules.solarisipspkg.is_installed", MagicMock(return_value=False)
        ):
            added = solarisipspkg.install(install_target, refresh=False)
            expected = {
                "pkg://solaris/compress/zip": {
                    "new": "3.0-11.4.0.0.1.14.0:20180814T153154Z",
                    "old": "",
                }
            }
            assert added == expected

    expected_calls = [
        call(
            ["pkg", "install", "-v", "--accept", install_target],
            output_loglevel="trace",
        ),
    ]
    run_all_mock.assert_has_calls(expected_calls, any_order=True)
    assert run_all_mock.call_count == 1


def test_install_single_pkg_package():
    """
    Test installing a single package
    - a single package pkg://solaris/compress/zip 3.0-11.4.0.0.1.14.0:20180814T153154Z
    """

    install_target = "pkg://solaris/compress/zip"
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
        "solarisipspkg.is_installed": MagicMock(return_value=False),
        "cmd.retcode": MagicMock(return_value=False),
    }

    with patch.dict(solarisipspkg.__salt__, patches):
        with patch("salt.modules.solarisipspkg.list_pkgs", ListPackages()):
            added = solarisipspkg.install(pkgs=[install_target], refresh=False)
            expected = {
                "pkg://solaris/compress/zip": {
                    "new": "3.0-11.4.0.0.1.14.0:20180814T153154Z",
                    "old": "",
                }
            }
            assert added == expected

    expected_calls = [
        call(
            ["pkg", "install", "-v", "--accept", install_target],
            output_loglevel="trace",
        ),
    ]
    run_all_mock.assert_has_calls(expected_calls, any_order=True)
    assert run_all_mock.call_count == 1


def test_install_dict_pkgs_no_version():
    """
    Test installing a list of packages in a dict with no versions
    """

    install_target = [{"tree": ""}, {"xclock": ""}]
    cmd_out = {
        "retcode": 0,
        "stdout": "",
        "stderr": "",
    }
    run_all_mock = MagicMock(return_value=cmd_out)
    patches = {
        "cmd.run_all": run_all_mock,
        "solarisipspkg.is_installed": MagicMock(return_value=False),
        "cmd.retcode": MagicMock(return_value=False),
    }

    with patch.dict(solarisipspkg.__salt__, patches):
        with patch("salt.modules.solarisipspkg.list_pkgs", ListPackagesDict()), patch(
            "salt.modules.solarisipspkg.is_installed", MagicMock(return_value=False)
        ):
            added = solarisipspkg.install(pkgs=install_target, refresh=False)
            expected = {
                "pkg://solaris/file/tree": {
                    "new": "1.7.0-11.4.0.0.1.14.0:20180814T163602Z",
                    "old": "",
                },
                "pkg://solaris/x11/xclock": {
                    "new": "1.0.7-11.4.0.0.1.14.0:20180814T173537Z",
                    "old": "",
                },
            }
            assert added == expected

    list_first = tuple(install_target[0].keys())[0]
    list_second = tuple(install_target[1].keys())[0]
    expected_calls = [
        call(
            ["pkg", "install", "-v", "--accept", list_first, list_second],
            output_loglevel="trace",
        ),
    ]
    run_all_mock.assert_has_calls(expected_calls, any_order=True)
    assert run_all_mock.call_count == 1


def test_install_dict_pkgs_with_version():
    """
    Test installing a list of packages in a dict with versions
    """

    install_target = [
        {"tree": "1.7.0-11.4.0.0.1.14.0:20180814T163602Z"},
        {"xclock": "1.0.7-11.4.0.0.1.14.0:20180814T173537Z"},
    ]
    cmd_out = {
        "retcode": 0,
        "stdout": "",
        "stderr": "",
    }
    run_all_mock = MagicMock(return_value=cmd_out)
    patches = {
        "cmd.run_all": run_all_mock,
        "solarisipspkg.is_installed": MagicMock(return_value=False),
        "cmd.retcode": MagicMock(return_value=False),
    }

    with patch.dict(solarisipspkg.__salt__, patches):
        with patch("salt.modules.solarisipspkg.list_pkgs", ListPackagesDict()), patch(
            "salt.modules.solarisipspkg.is_installed", MagicMock(return_value=False)
        ):
            added = solarisipspkg.install(pkgs=install_target, refresh=False)
            expected = {
                "pkg://solaris/file/tree": {
                    "new": "1.7.0-11.4.0.0.1.14.0:20180814T163602Z",
                    "old": "",
                },
                "pkg://solaris/x11/xclock": {
                    "new": "1.0.7-11.4.0.0.1.14.0:20180814T173537Z",
                    "old": "",
                },
            }
            assert added == expected

    list_first = (
        tuple(install_target[0].keys())[0] + "@1.7.0-11.4.0.0.1.14.0:20180814T163602Z"
    )
    list_second = (
        tuple(install_target[1].keys())[0] + "@1.0.7-11.4.0.0.1.14.0:20180814T173537Z"
    )
    expected_calls = [
        call(
            ["pkg", "install", "-v", "--accept", list_first, list_second],
            output_loglevel="trace",
        ),
    ]
    run_all_mock.assert_has_calls(expected_calls, any_order=True)
    assert run_all_mock.call_count == 1


def test_install_already_installed_single_pkg():
    """
    Test installing a package that is already installed
    """
    result = None
    expected_result = {}
    install_target = "compress/zip"

    patches = {
        "solarisipspkg.is_installed": MagicMock(return_value=True),
        "cmd.retcode": MagicMock(return_value=False),
    }

    with patch.dict(solarisipspkg.__salt__, patches):
        result = solarisipspkg.install(install_target)
        assert result == expected_result
