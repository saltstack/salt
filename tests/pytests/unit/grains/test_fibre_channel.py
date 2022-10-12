"""
    :codeauthor: :email:`Shane Lee <slee@saltstack.com>`
"""

import salt.grains.fibre_channel as fibre_channel
from tests.support.mock import MagicMock, mock_open, patch


def test_windows_fibre_channel_wwns_grains():
    wwns = [
        "20:00:00:25:b5:11:11:4c",
        "20:00:00:25:b5:11:11:5c",
        "20:00:00:25:b5:44:44:4c",
        "20:00:00:25:b5:44:44:5c",
    ]
    cmd_run_mock = MagicMock(return_value=wwns)
    with patch("salt.modules.cmdmod.powershell", cmd_run_mock):
        ret = fibre_channel._windows_wwns()
    assert ret == wwns, ret


def test_linux_fibre_channel_wwns_grains():

    contents = ["0x500143802426baf4", "0x500143802426baf5"]
    files = ["file1", "file2"]
    with patch("glob.glob", MagicMock(return_value=files)), patch(
        "salt.utils.files.fopen", mock_open(read_data=contents)
    ):
        ret = fibre_channel._linux_wwns()

    assert ret == ["500143802426baf4", "500143802426baf5"], ret
