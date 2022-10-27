"""
    :codeauthor: :email:`Shane Lee <slee@saltstack.com>`
"""

import textwrap

import pytest

import salt.grains.disks as disks
from tests.support.mock import MagicMock, mock_open, patch


@pytest.fixture
def configure_loader_modules():
    return {
        disks: {"__salt__": {}},
    }


def test__windows_disks():
    """
    Test grains._windows_disks, normal return
    Should return a populated dictionary
    """
    mock_which = MagicMock(return_value="C:\\Windows\\System32\\wbem\\WMIC.exe")
    wmic_result = textwrap.dedent(
        """
        DeviceId  MediaType
        0         4
        1         0
        2         3
        3         5
    """
    )
    mock_run_all = MagicMock(return_value={"stdout": wmic_result, "retcode": 0})

    with patch("salt.utils.path.which", mock_which), patch.dict(
        disks.__salt__, {"cmd.run_all": mock_run_all}
    ):
        result = disks._windows_disks()
        expected = {
            "ssds": ["\\\\.\\PhysicalDrive0"],
            "disks": [
                "\\\\.\\PhysicalDrive0",
                "\\\\.\\PhysicalDrive1",
                "\\\\.\\PhysicalDrive2",
                "\\\\.\\PhysicalDrive3",
            ],
        }
        assert result == expected
        cmd = " ".join(
            [
                "C:\\Windows\\System32\\wbem\\WMIC.exe",
                "/namespace:\\\\root\\microsoft\\windows\\storage",
                "path",
                "MSFT_PhysicalDisk",
                "get",
                "DeviceID,MediaType",
                "/format:table",
            ]
        )
        mock_run_all.assert_called_once_with(cmd)


def test__windows_disks_retcode():
    """
    Test grains._windows_disks, retcode 1
    Should return empty lists
    """
    mock_which = MagicMock(return_value="C:\\Windows\\System32\\wbem\\WMIC.exe")
    mock_run_all = MagicMock(return_value={"stdout": "", "retcode": 1})
    with patch("salt.utils.path.which", mock_which), patch.dict(
        disks.__salt__, {"cmd.run_all": mock_run_all}
    ):
        result = disks._windows_disks()
        expected = {"ssds": [], "disks": []}
        assert result == expected


def test__linux_disks():
    """
    Test grains._linux_disks, normal return
    Should return a populated dictionary
    """

    files = [
        "/sys/block/asm!.asm_ctl_vbg0",
        "/sys/block/dm-0",
        "/sys/block/loop0",
        "/sys/block/ram0",
        "/sys/block/sda",
        "/sys/block/sdb",
        "/sys/block/vda",
    ]
    links = [
        "../devices/virtual/block/asm!.asm_ctl_vbg0",
        "../devices/virtual/block/dm-0",
        "../devices/virtual/block/loop0",
        "../devices/virtual/block/ram0",
        "../devices/pci0000:00/0000:00:1f.2/ata1/host0/target0:0:0/0:0:0:0/block/sda",
        "../devices/pci0000:35/0000:35:00.0/0000:36:00.0/host2/target2:1:0/2:1:0:0/block/sdb",
        "../devices/pci0000L00:0000:00:05.0/virtio2/block/vda",
    ]
    contents = [
        "1",
        "1",
        "1",
        "0",
        "1",
        "1",
        "1",
    ]

    patch_glob = patch("glob.glob", autospec=True, return_value=files)
    patch_readlink = patch("salt.utils.path.readlink", autospec=True, side_effect=links)
    patch_fopen = patch("salt.utils.files.fopen", mock_open(read_data=contents))
    with patch_glob, patch_readlink, patch_fopen:
        ret = disks._linux_disks()

    assert ret == {"disks": ["sda", "sdb", "vda"], "ssds": []}, ret
