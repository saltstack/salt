"""
Test for the chocolatey module
"""


import os

import salt.modules.chocolatey as chocolatey
import salt.utils
import salt.utils.platform
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf


@skipIf(not salt.utils.platform.is_windows(), "Not a Windows system")
class ChocolateyTestCase(TestCase, LoaderModuleMockMixin):
    """
    Chocolatey private functions tests
    """

    @classmethod
    def setUpClass(cls):
        cls.choco_path = "C:\\path\\to\\chocolatey.exe"
        cls.choco_path_pd = os.path.join(
            os.environ.get("ProgramData"), "Chocolatey", "bin", "chocolatey.exe"
        )
        cls.choco_path_sd = os.path.join(
            os.environ.get("SystemDrive"), "Chocolatey", "bin", "chocolatey.bat"
        )
        cls.mock_false = MagicMock(return_value=False)
        cls.mock_true = MagicMock(return_value=True)

    @classmethod
    def tearDownClass(cls):
        del cls.choco_path
        del cls.choco_path_pd
        del cls.choco_path_sd
        del cls.mock_false
        del cls.mock_true

    def setup_loader_modules(self):
        return {chocolatey: {"__context__": {}, "__salt__": {}}}

    def test__clear_context(self):
        """
        Tests _clear_context function
        """
        context = {
            "chocolatey._yes": ["--yes"],
            "chocolatey._path": self.choco_path,
            "chocolatey._version": "0.9.9",
        }
        with patch.dict(chocolatey.__context__, context):
            chocolatey._clear_context()
            # Did it clear all chocolatey items from __context__P?
            self.assertEqual(chocolatey.__context__, {})

    def test__yes_context(self):
        """
        Tests _yes function when it exists in __context__
        """
        with patch.dict(chocolatey.__context__, {"chocolatey._yes": ["--yes"]}):
            result = chocolatey._yes()
            expected = ["--yes"]
            # Did it return correctly
            self.assertListEqual(result, expected)
            # Did it populate __context__
            self.assertEqual(chocolatey.__context__["chocolatey._yes"], expected)

    def test__yes_version_greater(self):
        """
        Test _yes when Chocolatey version is greater than 0.9.9
        """
        mock_version = MagicMock(return_value="10.0.0")
        with patch("salt.modules.chocolatey.chocolatey_version", mock_version):
            result = chocolatey._yes()
            expected = ["--yes"]
            # Did it return correctly
            self.assertListEqual(result, expected)
            # Did it populate __context__
            self.assertEqual(chocolatey.__context__["chocolatey._yes"], expected)

    def test__yes_version_less_than(self):
        """
        Test _yes when Chocolatey version is less than 0.9.9
        """
        mock_version = MagicMock(return_value="0.9.0")
        with patch("salt.modules.chocolatey.chocolatey_version", mock_version):
            result = chocolatey._yes()
            expected = []
            # Did it return correctly
            self.assertListEqual(result, expected)
            # Did it populate __context__
            self.assertEqual(chocolatey.__context__["chocolatey._yes"], expected)

    def test__find_chocolatey_context(self):
        """
        Test _find_chocolatey when it exists in __context__
        """
        with patch.dict(chocolatey.__context__, {"chocolatey._path": self.choco_path}):
            result = chocolatey._find_chocolatey()
            expected = self.choco_path
            self.assertEqual(result, expected)

    def test__find_chocolatey_which(self):
        """
        Test _find_chocolatey when found with `cmd.which`
        """
        mock_which = MagicMock(return_value=self.choco_path)
        with patch.dict(chocolatey.__salt__, {"cmd.which": mock_which}):
            result = chocolatey._find_chocolatey()
            expected = self.choco_path
            # Does it return the correct path
            self.assertEqual(result, expected)
            # Does it populate __context__
            self.assertEqual(chocolatey.__context__["chocolatey._path"], expected)

    def test__find_chocolatey_programdata(self):
        """
        Test _find_chocolatey when found in ProgramData
        """
        with patch.dict(chocolatey.__salt__, {"cmd.which": self.mock_false}), patch(
            "os.path.isfile", self.mock_true
        ):
            result = chocolatey._find_chocolatey()
            expected = self.choco_path_pd
            # Does it return the correct path
            self.assertEqual(result, expected)
            # Does it populate __context__
            self.assertEqual(chocolatey.__context__["chocolatey._path"], expected)

    def test__find_chocolatey_systemdrive(self):
        """
        Test _find_chocolatey when found on SystemDrive (older versions)
        """
        with patch.dict(chocolatey.__salt__, {"cmd.which": self.mock_false}), patch(
            "os.path.isfile", MagicMock(side_effect=[False, True])
        ):
            result = chocolatey._find_chocolatey()
            expected = self.choco_path_sd
            # Does it return the correct path
            self.assertEqual(result, expected)
            # Does it populate __context__
            self.assertEqual(chocolatey.__context__["chocolatey._path"], expected)

    def test_version_check_remote_false(self):
        """
        Test version when remote is False
        """
        list_return_value = {"ack": ["3.1.1"]}
        with patch.object(chocolatey, "list_", return_value=list_return_value):
            expected = {"ack": ["3.1.1"]}
            result = chocolatey.version("ack", check_remote=False)
            self.assertEqual(result, expected)

    def test_version_check_remote_true(self):
        """
        Test version when remote is True
        """
        list_side_effect = [
            {"ack": ["3.1.1"]},
            {"ack": ["3.1.1"], "Wolfpack": ["3.0.17"], "blackbird": ["1.0.79.3"]},
        ]
        with patch.object(chocolatey, "list_", side_effect=list_side_effect):
            expected = {"ack": {"available": ["3.1.1"], "installed": ["3.1.1"]}}
            result = chocolatey.version("ack", check_remote=True)
            self.assertEqual(result, expected)

    def test_version_check_remote_true_not_available(self):
        """
        Test version when remote is True but remote version is unavailable
        """
        list_side_effect = [
            {"ack": ["3.1.1"]},
            {"Wolfpack": ["3.0.17"], "blackbird": ["1.0.79.3"]},
        ]
        with patch.object(chocolatey, "list_", side_effect=list_side_effect):
            expected = {"ack": {"installed": ["3.1.1"]}}
            result = chocolatey.version("ack", check_remote=True)
            self.assertEqual(result, expected)
