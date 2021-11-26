"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import copy
import os

import pytest
import salt.modules.scsi as scsi
import salt.utils.path
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {scsi: {}}


def test_ls_():
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
            assert scsi.ls_() == result_size
            with patch.dict(lsscsi_size, {"retcode": 1, "stderr": "An error occurred"}):
                assert scsi.ls_() == "An error occurred"
            with patch.dict(
                lsscsi_size,
                {"retcode": 1, "stderr": "lsscsi: invalid option -- 's'\nUsage:"},
            ):
                assert (
                    scsi.ls_() == "lsscsi: invalid option -- 's' - try get_size=False"
                )

        # get_size = False
        cmd_mock = MagicMock(return_value=lsscsi)
        with patch.dict(scsi.__salt__, {"cmd.run_all": cmd_mock}):
            assert scsi.ls_(get_size=False) == result

    mock = MagicMock(return_value=None)
    with patch.object(salt.utils.path, "which", mock):
        assert scsi.ls_() == "scsi.ls not available - lsscsi command not found"


def test_rescan_all():
    """
    Test for list scsi devices
    """
    mock = MagicMock(side_effect=[False, True])
    with patch.object(os.path, "isdir", mock):
        assert scsi.rescan_all("host") == "Host host does not exist"

        with patch.dict(scsi.__salt__, {"cmd.run": MagicMock(return_value="A")}):
            assert scsi.rescan_all("host") == ["A"]
