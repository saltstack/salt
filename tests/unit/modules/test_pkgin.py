import os

import salt.modules.pkgin as pkgin
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class PkginTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.pkgin
    """

    def setup_loader_modules(self):
        return {pkgin: {"__opts__": {"cachedir": "/tmp"}}}

    def test_search(self):
        """
        Test searching for a package
        """

        # Test searching for an available and uninstalled package
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
            self.assertDictEqual(pkgin.search("somepkg"), {"somepkg": "1.0"})

        # Test searching for an available and installed package
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
            self.assertDictEqual(pkgin.search("somepkg"), {"somepkg": "1.0"})

    def test_latest_version(self):
        """
        Test getting the latest version of a package
        """

        # Test getting the latest version of an uninstalled package
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
        ), patch(
            "salt.modules.pkgin._check_pkgin", pkgin__check_pkgin_mock
        ), patch.dict(
            pkgin.__salt__, {"cmd.run": pkgin_search_cmd}
        ):
            self.assertEqual(pkgin.latest_version("somepkg"), "1.0")

        # Test getting the latest version of an installed package
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
        ), patch(
            "salt.modules.pkgin._check_pkgin", pkgin__check_pkgin_mock
        ), patch.dict(
            pkgin.__salt__, {"cmd.run": pkgin_search_cmd}
        ):
            self.assertEqual(pkgin.latest_version("somepkg"), "1.1")

        # Test getting the latest version of a package that is already installed
        # and is already at the latest version
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
        ), patch(
            "salt.modules.pkgin._check_pkgin", pkgin__check_pkgin_mock
        ), patch.dict(
            pkgin.__salt__, {"cmd.run": pkgin_search_cmd}
        ):
            self.assertEqual(pkgin.latest_version("somepkg"), "1.2")

        # Test getting the latest version of a bogus package
        pkgin_out = "No results found for ^boguspkg$"

        pkgin_refresh_db_mock = MagicMock(return_value=True)
        pkgin_search_cmd = MagicMock(return_value=pkgin_out)

        with patch("salt.modules.pkgin.refresh_db", pkgin_refresh_db_mock), patch(
            "salt.modules.pkgin._get_version", pkgin__get_version_mock
        ), patch(
            "salt.modules.pkgin._check_pkgin", pkgin__check_pkgin_mock
        ), patch.dict(
            pkgin.__salt__, {"cmd.run": pkgin_search_cmd}
        ):
            self.assertEqual(pkgin.latest_version("boguspkg"), {})

    def test_file_dict(self):
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
            self.assertDictEqual(
                pkgin.file_dict("pkgin"),
                {
                    "files": {
                        "pkgin": [
                            "/opt/pkg/bin/pkgin",
                            "/opt/pkg/man/man1/pkgin.1",
                            "/opt/pkg/share/examples/pkgin/preferred.conf.example",
                            "/opt/pkg/share/examples/pkgin/repositories.conf.example",
                        ]
                    }
                },
            )
