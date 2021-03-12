"""
tests.unit.runners.test_asam
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the asam runner
"""

import logging

import salt.runners.asam as asam
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class AsamRunnerVerifySslTest(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        opts = {
            "asam": {
                "prov1.domain.com": {
                    "username": "TheUsername",
                    "password": "ThePassword",
                }
            }
        }
        return {asam: {"__opts__": opts}}

    def test_add_platform(self):
        parse_html_content = MagicMock()
        get_platform_set_name = MagicMock(return_value="plat-foo")
        requests_mock = MagicMock()

        # remove_platform
        with patch("salt.runners.asam._parse_html_content", parse_html_content), patch(
            "salt.runners.asam._get_platformset_name", get_platform_set_name
        ), patch("salt.runners.asam.requests.post", requests_mock):
            asam.add_platform("plat-foo-2", "plat-foo", "prov1.domain.com")

        requests_mock.assert_called_with(
            "https://prov1.domain.com:3451/config/PlatformSetConfig.html",
            auth=("TheUsername", "ThePassword"),
            data={"manual": "false"},
            verify=True,
        )

    def test_remove_platform(self):
        parse_html_content = MagicMock()
        get_platform_set_name = MagicMock(return_value="plat-foo")
        requests_mock = MagicMock()

        # remove_platform
        with patch("salt.runners.asam._parse_html_content", parse_html_content), patch(
            "salt.runners.asam._get_platformset_name", get_platform_set_name
        ), patch("salt.runners.asam.requests.post", requests_mock):
            asam.remove_platform("plat-foo", "prov1.domain.com")

        requests_mock.assert_called_with(
            "https://prov1.domain.com:3451/config/PlatformConfig.html",
            auth=("TheUsername", "ThePassword"),
            data={
                "manual": "false",
                "platformName": "plat-foo",
                "platformSetName": "plat-foo",
                "postType": "platformRemove",
                "Submit": "Yes",
            },
            verify=True,
        )

    def test_list_platforms(self):
        parse_html_content = MagicMock()
        get_platforms = MagicMock(return_value=["plat-foo", "plat-bar"])
        requests_mock = MagicMock()

        # remove_platform
        with patch("salt.runners.asam._parse_html_content", parse_html_content), patch(
            "salt.runners.asam._get_platforms", get_platforms
        ), patch("salt.runners.asam.requests.post", requests_mock):
            asam.list_platforms("prov1.domain.com")

        requests_mock.assert_called_with(
            "https://prov1.domain.com:3451/config/PlatformConfig.html",
            auth=("TheUsername", "ThePassword"),
            data={"manual": "false"},
            verify=True,
        )

    def test_list_platform_sets(self):
        parse_html_content = MagicMock()
        get_platform_sets = MagicMock(return_value=["plat-foo", "plat-bar"])
        requests_mock = MagicMock()

        # remove_platform
        with patch("salt.runners.asam._parse_html_content", parse_html_content), patch(
            "salt.runners.asam._get_platforms", get_platform_sets
        ), patch("salt.runners.asam.requests.post", requests_mock):
            asam.list_platform_sets("prov1.domain.com")

        requests_mock.assert_called_with(
            "https://prov1.domain.com:3451/config/PlatformSetConfig.html",
            auth=("TheUsername", "ThePassword"),
            data={"manual": "false"},
            verify=True,
        )
