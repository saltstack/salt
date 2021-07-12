"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import copy
import os

import salt.modules.scsi as scsi
import salt.utils.path
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class ScsiTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.scsi
    """

    def setup_loader_modules(self):
        return {scsi: {}}

    def test_ls_(self):
        """
        Test for list SCSI devices, with details
        """
        lsscsi = {
            "stdout": "[0:0:0:0] disk HP LOGICAL VOLUME 6.68 /dev/sda [8:0]",
            "stderr": "",
            "retcode": 0,
        }

        lsscsi_size = {
            "stdout": "[0:0:0:0] disk HP LOGICAL VOLUME 6.68 /dev/sda [8:0] 1.20TB",
            "stderr": "",
            "retcode": 0,
        }

        result = {
            "[0:0:0:0]": {
                "major": "8",
                "lun": "0:0:0:0",
                "device": "/dev/sda",
                "model": "LOGICAL VOLUME 6.68",
                "minor": "0",
                "size": None,
            }
        }
        result_size = copy.deepcopy(result)
        result_size["[0:0:0:0]"]["size"] = "1.20TB"

        mock = MagicMock(return_value="/usr/bin/lsscsi")
        with patch.object(salt.utils.path, "which", mock):
            # get_size = True

            cmd_mock = MagicMock(return_value=lsscsi_size)
            with patch.dict(scsi.__salt__, {"cmd.run_all": cmd_mock}):
                self.assertDictEqual(scsi.ls_(), result_size)
                with patch.dict(
                    lsscsi_size, {"retcode": 1, "stderr": "An error occurred"}
                ):
                    self.assertEqual(scsi.ls_(), "An error occurred")
                with patch.dict(
                    lsscsi_size,
                    {"retcode": 1, "stderr": "lsscsi: invalid option -- 's'\nUsage:"},
                ):
                    self.assertEqual(
                        scsi.ls_(), "lsscsi: invalid option -- 's' - try get_size=False"
                    )

            # get_size = False
            cmd_mock = MagicMock(return_value=lsscsi)
            with patch.dict(scsi.__salt__, {"cmd.run_all": cmd_mock}):
                self.assertDictEqual(scsi.ls_(get_size=False), result)

        mock = MagicMock(return_value=None)
        with patch.object(salt.utils.path, "which", mock):
            self.assertEqual(
                scsi.ls_(), "scsi.ls not available - lsscsi command not found"
            )

    def test_rescan_all(self):
        """
        Test for list scsi devices
        """
        mock = MagicMock(side_effect=[False, True])
        with patch.object(os.path, "isdir", mock):
            self.assertEqual(scsi.rescan_all("host"), "Host host does not exist")

            with patch.dict(scsi.__salt__, {"cmd.run": MagicMock(return_value="A")}):
                self.assertListEqual(scsi.rescan_all("host"), ["A"])
