import pytest

import salt.utils.win_dotnet as win_dotnet
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

pytestmark = [
    pytest.mark.skip_unless_on_windows,
]


class WinDotNetTestCase(TestCase):
    """
    Test cases for salt.utils.win_dotnet
    """

    def setUp(self):
        self.mock_reg_list = MagicMock(
            return_value=["CDF", "v2.0.50727", "v3.0", "v3.5", "v4", "v4.0"]
        )
        self.mock_reg_exists = MagicMock(
            side_effect=[
                True,  # Version exists in v2.0.50727
                True,  # Version exists in v3.0
                True,  # Version exists in v3.5
                False,  # Version not in v4
                True,  # Release exists in v4
                False,  # Version not in v4.0
                False,  # Release not in v4.0
            ]
        )
        self.mock_reg_read = MagicMock(
            side_effect=[
                # v2.0.50727
                {"vdata": 1},
                {"vdata": "2.0.50727.4927"},
                {"vdata": 2},
                # v3.0
                {"vdata": 1},
                {"vdata": "3.0.30729.4926"},
                {"vdata": 2},
                # v3.5
                {"vdata": 1},
                {"vdata": "3.5.30729.4926"},
                {"vdata": 1},
                # v4
                {"vdata": 1},
                {"vdata": 461814},
            ]
        )

    def test_versions(self):
        """
        Test the versions function
        """
        expected = {
            "details": {
                "v2.0.50727": {
                    "full": "2.0.50727.4927 SP2",
                    "service_pack": 2,
                    "version": "2.0.50727.4927",
                },
                "v3.0": {
                    "full": "3.0.30729.4926 SP2",
                    "service_pack": 2,
                    "version": "3.0.30729.4926",
                },
                "v3.5": {
                    "full": "3.5.30729.4926 SP1",
                    "service_pack": 1,
                    "version": "3.5.30729.4926",
                },
                "v4": {"full": "4.7.2", "service_pack": "N/A", "version": "4.7.2"},
            },
            "versions": ["2.0.50727.4927", "3.0.30729.4926", "3.5.30729.4926", "4.7.2"],
        }
        with patch("salt.utils.win_reg.list_keys", self.mock_reg_list), patch(
            "salt.utils.win_reg.value_exists", self.mock_reg_exists
        ), patch("salt.utils.win_reg.read_value", self.mock_reg_read):
            result = win_dotnet.versions()
            self.assertDictEqual(result, expected)

    def test_versions_list(self):
        expected = ["2.0.50727.4927", "3.0.30729.4926", "3.5.30729.4926", "4.7.2"]
        with patch("salt.utils.win_reg.list_keys", self.mock_reg_list), patch(
            "salt.utils.win_reg.value_exists", self.mock_reg_exists
        ), patch("salt.utils.win_reg.read_value", self.mock_reg_read):
            result = win_dotnet.versions_list()
            self.assertListEqual(result, expected)

    def test_versions_details(self):
        """
        Test the versions function
        """
        expected = {
            "v2.0.50727": {
                "full": "2.0.50727.4927 SP2",
                "service_pack": 2,
                "version": "2.0.50727.4927",
            },
            "v3.0": {
                "full": "3.0.30729.4926 SP2",
                "service_pack": 2,
                "version": "3.0.30729.4926",
            },
            "v3.5": {
                "full": "3.5.30729.4926 SP1",
                "service_pack": 1,
                "version": "3.5.30729.4926",
            },
            "v4": {"full": "4.7.2", "service_pack": "N/A", "version": "4.7.2"},
        }
        with patch("salt.utils.win_reg.list_keys", self.mock_reg_list), patch(
            "salt.utils.win_reg.value_exists", self.mock_reg_exists
        ), patch("salt.utils.win_reg.read_value", self.mock_reg_read):
            result = win_dotnet.versions_details()
            self.assertDictEqual(result, expected)

    def test_version_atleast_35(self):
        with patch("salt.utils.win_reg.list_keys", self.mock_reg_list), patch(
            "salt.utils.win_reg.value_exists", self.mock_reg_exists
        ), patch("salt.utils.win_reg.read_value", self.mock_reg_read):
            self.assertTrue(win_dotnet.version_at_least("3.5"))

    def test_version_atleast_47(self):
        with patch("salt.utils.win_reg.list_keys", self.mock_reg_list), patch(
            "salt.utils.win_reg.value_exists", self.mock_reg_exists
        ), patch("salt.utils.win_reg.read_value", self.mock_reg_read):
            self.assertTrue(win_dotnet.version_at_least("4.7"))

    def test_version_atleast_472(self):
        with patch("salt.utils.win_reg.list_keys", self.mock_reg_list), patch(
            "salt.utils.win_reg.value_exists", self.mock_reg_exists
        ), patch("salt.utils.win_reg.read_value", self.mock_reg_read):
            self.assertTrue(win_dotnet.version_at_least("4.7.2"))

    def test_version_not_atleast_473(self):
        with patch("salt.utils.win_reg.list_keys", self.mock_reg_list), patch(
            "salt.utils.win_reg.value_exists", self.mock_reg_exists
        ), patch("salt.utils.win_reg.read_value", self.mock_reg_read):
            self.assertFalse(win_dotnet.version_at_least("4.7.3"))
