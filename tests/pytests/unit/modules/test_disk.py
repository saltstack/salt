"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.modules.disk as disk
from tests.support.mock import MagicMock, patch


@pytest.fixture
def stub_disk_usage():
    return {
        "/": {
            "filesystem": None,
            "1K-blocks": 10000,
            "used": 10000,
            "available": 10000,
            "capacity": 10000,
        },
        "/dev": {
            "filesystem": None,
            "1K-blocks": 10000,
            "used": 10000,
            "available": 10000,
            "capacity": 10000,
        },
        "/run": {
            "filesystem": None,
            "1K-blocks": 10000,
            "used": 10000,
            "available": 10000,
            "capacity": 10000,
        },
        "/run/lock": {
            "filesystem": None,
            "1K-blocks": 10000,
            "used": 10000,
            "available": 10000,
            "capacity": 10000,
        },
        "/run/shm": {
            "filesystem": None,
            "1K-blocks": 10000,
            "used": 10000,
            "available": 10000,
            "capacity": 10000,
        },
        "/run/user": {
            "filesystem": None,
            "1K-blocks": 10000,
            "used": 10000,
            "available": 10000,
            "capacity": 10000,
        },
        "/sys/fs/cgroup": {
            "filesystem": None,
            "1K-blocks": 10000,
            "used": 10000,
            "available": 10000,
            "capacity": 10000,
        },
    }


@pytest.fixture
def stub_disk_inodeusage():
    return {
        "/": {
            "inodes": 10000,
            "used": 10000,
            "free": 10000,
            "use": 10000,
            "filesystem": None,
        },
        "/dev": {
            "inodes": 10000,
            "used": 10000,
            "free": 10000,
            "use": 10000,
            "filesystem": None,
        },
        "/run": {
            "inodes": 10000,
            "used": 10000,
            "free": 10000,
            "use": 10000,
            "filesystem": None,
        },
        "/run/lock": {
            "inodes": 10000,
            "used": 10000,
            "free": 10000,
            "use": 10000,
            "filesystem": None,
        },
        "/run/shm": {
            "inodes": 10000,
            "used": 10000,
            "free": 10000,
            "use": 10000,
            "filesystem": None,
        },
        "/run/user": {
            "inodes": 10000,
            "used": 10000,
            "free": 10000,
            "use": 10000,
            "filesystem": None,
        },
        "/sys/fs/cgroup": {
            "inodes": 10000,
            "used": 10000,
            "free": 10000,
            "use": 10000,
            "filesystem": None,
        },
    }


@pytest.fixture
def stub_disk_percent():
    return {
        "/": 50,
        "/dev": 10,
        "/run": 10,
        "/run/lock": 10,
        "/run/shm": 10,
        "/run/user": 10,
        "/sys/fs/cgroup": 10,
    }


@pytest.fixture
def stub_disk_blkid():
    return {"/dev/sda": {"TYPE": "ext4", "UUID": None}}


@pytest.fixture
def configure_loader_modules():
    return {disk: {}}


def test_usage_dict(stub_disk_usage):
    with patch.dict(disk.__grains__, {"kernel": "Linux"}), patch(
        "salt.modules.disk.usage", MagicMock(return_value=stub_disk_usage)
    ):
        mock_cmd = MagicMock(return_value=1)
        with patch.dict(disk.__salt__, {"cmd.run": mock_cmd}):
            assert stub_disk_usage == disk.usage(args=None)


def test_usage_none():
    with patch.dict(disk.__grains__, {"kernel": "Linux"}), patch(
        "salt.modules.disk.usage", MagicMock(return_value="")
    ):
        mock_cmd = MagicMock(return_value=1)
        with patch.dict(disk.__salt__, {"cmd.run": mock_cmd}):
            assert "" == disk.usage(args=None)


def test_inodeusage(stub_disk_inodeusage):
    with patch.dict(disk.__grains__, {"kernel": "OpenBSD"}), patch(
        "salt.modules.disk.inodeusage", MagicMock(return_value=stub_disk_inodeusage)
    ):
        mock = MagicMock()
        with patch.dict(disk.__salt__, {"cmd.run": mock}):
            assert stub_disk_inodeusage == disk.inodeusage(args=None)


def test_percent(stub_disk_percent):
    with patch.dict(disk.__grains__, {"kernel": "Linux"}), patch(
        "salt.modules.disk.percent", MagicMock(return_value=stub_disk_percent)
    ):
        mock = MagicMock()
        with patch.dict(disk.__salt__, {"cmd.run": mock}):
            assert stub_disk_percent == disk.percent(args=None)


def test_percent_args():
    with patch.dict(disk.__grains__, {"kernel": "Linux"}), patch(
        "salt.modules.disk.percent", MagicMock(return_value="/")
    ):
        mock = MagicMock()
        with patch.dict(disk.__salt__, {"cmd.run": mock}):
            assert "/" == disk.percent("/")


def test_blkid(stub_disk_blkid):
    with patch.dict(
        disk.__salt__, {"cmd.run_stdout": MagicMock(return_value=1)}
    ), patch("salt.modules.disk.blkid", MagicMock(return_value=stub_disk_blkid)):
        assert stub_disk_blkid == disk.blkid()


@pytest.mark.skip_on_windows(reason="Skip on Windows")
@pytest.mark.skip_on_darwin(reason="Skip on Darwin")
@pytest.mark.skip_on_freebsd
def test_blkid_token():
    run_stdout_mock = MagicMock(return_value={"retcode": 1})
    with patch.dict(disk.__salt__, {"cmd.run_all": run_stdout_mock}):
        disk.blkid(token="TYPE=ext4")
        run_stdout_mock.assert_called_with(
            ["blkid", "-t", "TYPE=ext4"], python_shell=False
        )


def test_dump():
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(disk.__salt__, {"cmd.run_all": mock}):
        disk.dump("/dev/sda")
        mock.assert_called_once_with(
            "blockdev --getro --getsz --getss --getpbsz --getiomin "
            "--getioopt --getalignoff --getmaxsect --getsize "
            "--getsize64 --getra --getfra /dev/sda",
            python_shell=False,
        )


def test_wipe():
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(disk.__salt__, {"cmd.run_all": mock}):
        disk.wipe("/dev/sda")
        mock.assert_called_once_with("wipefs -a /dev/sda", python_shell=False)


def test_tune():
    mock = MagicMock(
        return_value=(
            "712971264\n512\n512\n512\n0\n0\n88\n712971264\n365041287168\n512\n512"
        )
    )
    with patch.dict(disk.__salt__, {"cmd.run": mock}):
        mock_dump = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch("salt.modules.disk.dump", mock_dump):
            kwargs = {"read-ahead": 512, "filesystem-read-ahead": 1024}
            disk.tune("/dev/sda", **kwargs)

            mock.assert_called_with(
                "blockdev --setra 512 --setfra 1024 /dev/sda", python_shell=False
            )


def test_format():
    """
    unit tests for disk.format
    """
    device = "/dev/sdX1"
    mock = MagicMock(return_value=0)
    with patch.dict(disk.__salt__, {"cmd.retcode": mock}), patch(
        "salt.utils.path.which", MagicMock(return_value=True)
    ):
        assert disk.format_(device) is True


def test_fat_format():
    """
    unit tests for disk.format when using fat argument
    """
    device = "/dev/sdX1"
    expected = ["mkfs", "-t", "fat", "-F", 12, "/dev/sdX1"]
    mock = MagicMock(return_value=0)
    with patch.dict(disk.__salt__, {"cmd.retcode": mock}), patch(
        "salt.utils.path.which", MagicMock(return_value=True)
    ):
        assert disk.format_(device, fs_type="fat", fat=12) is True
        args, kwargs = mock.call_args_list[0]
        assert expected == args[0]


@pytest.mark.skip_if_binaries_missing("lsblk", "df", check_all=True)
def test_fstype():
    """
    unit tests for disk.fstype
    """
    device = "/dev/sdX1"
    fs_type = "ext4"
    mock = MagicMock(return_value=f"FSTYPE\n{fs_type}")
    with patch.dict(disk.__grains__, {"kernel": "Linux"}), patch.dict(
        disk.__salt__, {"cmd.run": mock}
    ), patch("salt.utils.path.which", MagicMock(return_value=True)):
        assert disk.fstype(device) == fs_type


def test_resize2fs():
    """
    unit tests for disk.resize2fs
    """
    device = "/dev/sdX1"
    mock = MagicMock()
    with patch.dict(disk.__salt__, {"cmd.run_all": mock}), patch(
        "salt.utils.path.which", MagicMock(return_value=True)
    ):
        disk.resize2fs(device)
        mock.assert_called_once_with(f"resize2fs {device}", python_shell=False)


@pytest.mark.skip_on_windows(reason="Skip on Windows")
@pytest.mark.skip_if_binaries_missing("mkfs")
def test_format_():
    """
    unit tests for disk.format_
    """
    device = "/dev/sdX1"
    mock = MagicMock(return_value=0)
    with patch.dict(disk.__salt__, {"cmd.retcode": mock}):
        disk.format_(device=device)
        mock.assert_any_call(["mkfs", "-t", "ext4", device], ignore_retcode=True)


@pytest.mark.skip_on_windows(reason="Skip on Windows")
@pytest.mark.skip_if_binaries_missing("mkfs")
def test_format__fat():
    """
    unit tests for disk.format_ with FAT parameter
    """
    device = "/dev/sdX1"
    mock = MagicMock(return_value=0)
    with patch.dict(disk.__salt__, {"cmd.retcode": mock}):
        disk.format_(device=device, fs_type="fat", fat=12)
        mock.assert_any_call(
            ["mkfs", "-t", "fat", "-F", 12, device], ignore_retcode=True
        )
