"""
    tests.pytests.unit.beacons.test_diskusage
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Disk usage beacon test cases
"""
from collections import namedtuple

import pytest

import salt.beacons.diskusage as diskusage
from tests.support.mock import MagicMock, Mock, patch


@pytest.fixture
def configure_loader_modules():
    return {}


@pytest.fixture
def stub_disk_partition():
    return [
        namedtuple("partition", "device mountpoint fstype, opts")(
            "tmpfs", "/mnt/tmp", "tmpfs", "rw,nosuid,nodev,relatime,size=10240k"
        ),
        namedtuple("partition", "device mountpoint fstype, opts")(
            "/dev/disk0s2", "/", "hfs", "rw,local,rootfs,dovolfs,journaled,multilabel"
        ),
    ]


@pytest.fixture
def windows_stub_disk_partition():
    return [
        namedtuple("partition", "device mountpoint fstype, opts")(
            "C:\\", "C:\\", "NTFS", "rw,fixed"
        ),
        namedtuple("partition", "device mountpoint fstype, opts")(
            "D:\\", "D:\\", "CDFS", "ro,cdrom"
        ),
    ]


@pytest.fixture
def stub_disk_usage():
    return [
        namedtuple("usage", "total used free percent")(1000, 500, 500, 50),
        namedtuple("usage", "total used free percent")(100, 75, 25, 25),
    ]


@pytest.fixture
def windows_stub_disk_usage():
    return namedtuple("usage", "total used free percent")(1000, 500, 500, 50)


def test_non_list_config():
    config = {}

    ret = diskusage.validate(config)
    assert ret == (False, "Configuration for diskusage beacon must be a list.")


def test_empty_config():
    config = [{}]

    ret = diskusage.validate(config)
    assert ret == (True, "Valid beacon configuration")


def test_diskusage_match(stub_disk_usage, stub_disk_partition):
    disk_usage_mock = Mock(side_effect=stub_disk_usage)
    with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)), patch(
        "psutil.disk_partitions", MagicMock(return_value=stub_disk_partition)
    ), patch("psutil.disk_usage", disk_usage_mock):
        config = [{"/": "50%"}]

        ret = diskusage.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = diskusage.beacon(config)
        assert ret == [{"diskusage": 50, "mount": "/"}]


def test_diskusage_match_no_percent(stub_disk_usage, stub_disk_partition):
    disk_usage_mock = Mock(side_effect=stub_disk_usage)
    with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)), patch(
        "psutil.disk_partitions", MagicMock(return_value=stub_disk_partition)
    ), patch("psutil.disk_usage", disk_usage_mock):

        # Test without the percent
        config = [{"/": 50}]

        ret = diskusage.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = diskusage.beacon(config)
        assert ret == [{"diskusage": 50, "mount": "/"}]


def test_diskusage_nomatch(stub_disk_usage, stub_disk_partition):
    disk_usage_mock = Mock(side_effect=stub_disk_usage)
    with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)), patch(
        "psutil.disk_partitions", MagicMock(return_value=stub_disk_partition)
    ), patch("psutil.disk_usage", disk_usage_mock):
        config = [{"/": "70%"}]

        ret = diskusage.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = diskusage.beacon(config)
        assert ret != [{"diskusage": 50, "mount": "/"}]


def test_diskusage_match_regex(stub_disk_usage, stub_disk_partition):
    disk_usage_mock = Mock(side_effect=stub_disk_usage)
    with patch("salt.utils.platform.is_windows", MagicMock(return_value=False)), patch(
        "psutil.disk_partitions", MagicMock(return_value=stub_disk_partition)
    ), patch("psutil.disk_usage", disk_usage_mock):
        config = [{"/": "50%"}]

        ret = diskusage.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = diskusage.beacon(config)
        assert ret == [{"diskusage": 50, "mount": "/"}]


def test_diskusage_windows_single_slash(
    windows_stub_disk_usage, windows_stub_disk_partition
):
    r"""
    This tests new behavior (C:\)
    """
    disk_usage_mock = Mock(return_value=windows_stub_disk_usage)
    with patch("salt.utils.platform.is_windows", MagicMock(return_value=True)):
        with patch(
            "psutil.disk_partitions",
            MagicMock(return_value=windows_stub_disk_partition),
        ), patch("psutil.disk_usage", disk_usage_mock):
            config = [{"C:\\": "50%"}]

            ret = diskusage.validate(config)
            assert ret == (True, "Valid beacon configuration")

            ret = diskusage.beacon(config)
            assert ret == [{"diskusage": 50, "mount": "C:\\"}]


def test_diskusage_windows_double_slash(
    windows_stub_disk_usage, windows_stub_disk_partition
):
    """
    This tests original behavior (C:\\)
    """
    disk_usage_mock = Mock(return_value=windows_stub_disk_usage)
    with patch("salt.utils.platform.is_windows", MagicMock(return_value=True)):
        with patch(
            "psutil.disk_partitions",
            MagicMock(return_value=windows_stub_disk_partition),
        ), patch("psutil.disk_usage", disk_usage_mock):
            config = [{"C:\\\\": "50%"}]

            ret = diskusage.validate(config)
            assert ret == (True, "Valid beacon configuration")

            ret = diskusage.beacon(config)
            assert ret == [{"diskusage": 50, "mount": "C:\\"}]


def test_diskusage_windows_lowercase(
    windows_stub_disk_usage, windows_stub_disk_partition
):
    r"""
    This tests lowercase drive letter (c:\)
    """
    disk_usage_mock = Mock(return_value=windows_stub_disk_usage)
    with patch("salt.utils.platform.is_windows", MagicMock(return_value=True)):
        with patch(
            "psutil.disk_partitions",
            MagicMock(return_value=windows_stub_disk_partition),
        ), patch("psutil.disk_usage", disk_usage_mock):
            config = [{"c:\\": "50%"}]

            ret = diskusage.validate(config)
            assert ret == (True, "Valid beacon configuration")

            ret = diskusage.beacon(config)
            assert ret == [{"diskusage": 50, "mount": "C:\\"}]


def test_diskusage_windows_match_regex(
    windows_stub_disk_usage, windows_stub_disk_partition
):
    disk_usage_mock = Mock(return_value=windows_stub_disk_usage)
    with patch("salt.utils.platform.is_windows", MagicMock(return_value=True)):
        with patch(
            "psutil.disk_partitions",
            MagicMock(return_value=windows_stub_disk_partition),
        ), patch("psutil.disk_usage", disk_usage_mock):
            config = [{"^[a-zA-Z]:\\": "50%"}]

            ret = diskusage.validate(config)
            assert ret == (True, "Valid beacon configuration")

            ret = diskusage.beacon(config)
            _expected = [
                {"diskusage": 50, "mount": "C:\\"},
                {"diskusage": 50, "mount": "D:\\"},
            ]
            assert ret == _expected
