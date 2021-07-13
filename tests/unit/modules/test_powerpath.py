"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import salt.modules.powerpath as powerpath
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class PowerpathTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.powerpath
    """

    def setup_loader_modules(self):
        return {powerpath: {}}

    def test_has_powerpath(self):
        """
        Test for powerpath
        """
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = True
            self.assertTrue(powerpath.has_powerpath())

            mock_exists.return_value = False
            self.assertFalse(powerpath.has_powerpath())

    def test_list_licenses(self):
        """
        Test to returns a list of applied powerpath license keys
        """
        with patch.dict(
            powerpath.__salt__, {"cmd.run": MagicMock(return_value="A\nB")}
        ):
            self.assertListEqual(powerpath.list_licenses(), [])

    def test_add_license(self):
        """
        Test to add a license
        """
        with patch.object(powerpath, "has_powerpath", return_value=False):
            self.assertDictEqual(
                powerpath.add_license("key"),
                {
                    "output": "PowerPath is not installed",
                    "result": False,
                    "retcode": -1,
                },
            )

        mock = MagicMock(return_value={"retcode": 1, "stderr": "stderr"})
        with patch.object(powerpath, "has_powerpath", return_value=True):
            with patch.dict(powerpath.__salt__, {"cmd.run_all": mock}):
                self.assertDictEqual(
                    powerpath.add_license("key"),
                    {"output": "stderr", "result": False, "retcode": 1},
                )

    def test_remove_license(self):
        """
        Test to remove a license
        """
        with patch.object(powerpath, "has_powerpath", return_value=False):
            self.assertDictEqual(
                powerpath.remove_license("key"),
                {
                    "output": "PowerPath is not installed",
                    "result": False,
                    "retcode": -1,
                },
            )

        mock = MagicMock(return_value={"retcode": 1, "stderr": "stderr"})
        with patch.object(powerpath, "has_powerpath", return_value=True):
            with patch.dict(powerpath.__salt__, {"cmd.run_all": mock}):
                self.assertDictEqual(
                    powerpath.remove_license("key"),
                    {"output": "stderr", "result": False, "retcode": 1},
                )
