import os

import pytest

import salt.modules.pkgin as pkgin
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules(tmp_path):
    return {pkgin: {"__opts__": {"cachedir": str(tmp_path)}}}


def test_search():
    """
    Test searching for a package
    """

    pkgin_out = [
        "somepkg-1.0          Some package description here",
        "",
        "=: package is installed and up-to-date",
        "<: package is installed but newer version is available",
        ">: installed package has a greater version than available package",
    ]

    pkgin__get_version_mock = MagicMock(return_value=["0", "9", "0"])
    pkgin__check_pkgin_mock = MagicMock(return_value="/opt/pkg/bin/pkgin")
    pkgin_search_cmd = MagicMock(return_value=os.linesep.join(pkgin_out))

    with patch("salt.modules.pkgin._get_version", pkgin__get_version_mock), patch(
        "salt.modules.pkgin._check_pkgin", pkgin__check_pkgin_mock
    ), patch.dict(pkgin.__salt__, {"cmd.run": pkgin_search_cmd}):
        assert pkgin.search("somepkg") == {"somepkg": "1.0"}

    pkgin_out = [
        "somepkg-1.0 =          Some package description here",
        "",
        "=: package is installed and up-to-date",
        "<: package is installed but newer version is available",
        ">: installed package has a greater version than available package",
    ]

    pkgin_search_cmd = MagicMock(return_value=os.linesep.join(pkgin_out))

    with patch("salt.modules.pkgin._get_version", pkgin__get_version_mock), patch(
        "salt.modules.pkgin._check_pkgin", pkgin__check_pkgin_mock
    ), patch.dict(pkgin.__salt__, {"cmd.run": pkgin_search_cmd}):
        assert pkgin.search("somepkg") == {"somepkg": "1.0"}


def test_latest_version():
    """
    Test getting the latest version of a package
    """

    pkgin_out = [
        "somepkg-1.0;;Some package description here",
        "",
        "=: package is installed and up-to-date",
        "<: package is installed but newer version is available",
        ">: installed package has a greater version than available package",
    ]

    pkgin__get_version_mock = MagicMock(return_value=["0", "9", "0"])
    pkgin__check_pkgin_mock = MagicMock(return_value="/opt/pkg/bin/pkgin")
    pkgin_refresh_db_mock = MagicMock(return_value=True)
    pkgin_search_cmd = MagicMock(return_value=os.linesep.join(pkgin_out))

    with patch("salt.modules.pkgin.refresh_db", pkgin_refresh_db_mock), patch(
        "salt.modules.pkgin._get_version", pkgin__get_version_mock
    ), patch("salt.modules.pkgin._check_pkgin", pkgin__check_pkgin_mock), patch.dict(
        pkgin.__salt__, {"cmd.run": pkgin_search_cmd}
    ):
        assert pkgin.latest_version("somepkg") == "1.0"

    pkgin_out = [
        "somepkg-1.1;<;Some package description here",
        "",
        "=: package is installed and up-to-date",
        "<: package is installed but newer version is available",
        ">: installed package has a greater version than available package",
    ]

    pkgin_refresh_db_mock = MagicMock(return_value=True)
    pkgin_search_cmd = MagicMock(return_value=os.linesep.join(pkgin_out))

    with patch("salt.modules.pkgin.refresh_db", pkgin_refresh_db_mock), patch(
        "salt.modules.pkgin._get_version", pkgin__get_version_mock
    ), patch("salt.modules.pkgin._check_pkgin", pkgin__check_pkgin_mock), patch.dict(
        pkgin.__salt__, {"cmd.run": pkgin_search_cmd}
    ):
        assert pkgin.latest_version("somepkg") == "1.1"

    pkgin_out = [
        "somepkg-1.2;=;Some package description here",
        "",
        "=: package is installed and up-to-date",
        "<: package is installed but newer version is available",
        ">: installed package has a greater version than available package",
    ]

    pkgin_refresh_db_mock = MagicMock(return_value=True)
    pkgin_search_cmd = MagicMock(return_value=os.linesep.join(pkgin_out))

    with patch("salt.modules.pkgin.refresh_db", pkgin_refresh_db_mock), patch(
        "salt.modules.pkgin._get_version", pkgin__get_version_mock
    ), patch("salt.modules.pkgin._check_pkgin", pkgin__check_pkgin_mock), patch.dict(
        pkgin.__salt__, {"cmd.run": pkgin_search_cmd}
    ):
        assert pkgin.latest_version("somepkg") == "1.2"

    pkgin_out = "No results found for ^boguspkg$"

    pkgin_refresh_db_mock = MagicMock(return_value=True)
    pkgin_search_cmd = MagicMock(return_value=pkgin_out)

    with patch("salt.modules.pkgin.refresh_db", pkgin_refresh_db_mock), patch(
        "salt.modules.pkgin._get_version", pkgin__get_version_mock
    ), patch("salt.modules.pkgin._check_pkgin", pkgin__check_pkgin_mock), patch.dict(
        pkgin.__salt__, {"cmd.run": pkgin_search_cmd}
    ):
        assert pkgin.latest_version("boguspkg") == {}


def test_file_dict():
    """
    Test that file_dict doesn't crash
    """
    pkg_info_stdout = [
        "/opt/pkg/bin/pkgin",
        "/opt/pkg/man/man1/pkgin.1",
        "/opt/pkg/share/examples/pkgin/preferred.conf.example",
        "/opt/pkg/share/examples/pkgin/repositories.conf.example",
    ]

    pkg_info_out = {
        "pid": 1234,
        "retcode": 0,
        "stderr": "",
        "stdout": os.linesep.join(pkg_info_stdout),
    }

    pkg_info_cmd = MagicMock(return_value=pkg_info_out)

    with patch.dict(pkgin.__salt__, {"cmd.run_all": pkg_info_cmd}):
        assert pkgin.file_dict("pkgin") == {
            "files": {
                "pkgin": [
                    "/opt/pkg/bin/pkgin",
                    "/opt/pkg/man/man1/pkgin.1",
                    "/opt/pkg/share/examples/pkgin/preferred.conf.example",
                    "/opt/pkg/share/examples/pkgin/repositories.conf.example",
                ]
            }
        }
