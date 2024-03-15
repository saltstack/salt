"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.modules.extfs as extfs
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {extfs: {}}


# 'mkfs' function tests: 1


def test_mkfs():
    """
    Tests if a file system created on the specified device
    """
    mock_ret = {
        "pid": 14247,
        "retcode": 0,
        "stdout": "",
        "stderr": "",
    }
    mock = MagicMock(return_value=mock_ret)
    with patch.dict(extfs.__salt__, {"cmd.run_all": mock}):
        assert extfs.mkfs("/dev/sda1", "ext4") == []
        assert extfs.mkfs("/dev/sda1", "ext4", full_return=True) == {
            "pid": 14247,
            "retcode": 0,
            "stdout": "",
            "stderr": "",
            "comment": [],
        }


# 'tune' function tests: 1


def test_tune():
    """
    Tests if specified group was added
    """
    mock_ret = {
        "pid": 14247,
        "retcode": 1,
        "stdout": "tune2fs 1.44.5 (15-Dec-2018)",
        "stderr": "tune2fs: No such file or directory while trying to open /dev/donkey\nCouldn't find valid filesystem superblock.",
    }
    mock = MagicMock(return_value=mock_ret)
    with patch.dict(extfs.__salt__, {"cmd.run_all": mock}):
        assert extfs.tune("/dev/sda1") == [
            "tune2fs 1.44.5 (15-Dec-2018)",
            "tune2fs: No such file or directory while trying to open /dev/donkey",
            "Couldn't find valid filesystem superblock.",
        ]
        assert extfs.tune("/dev/sda1", full_return=True) == {
            "pid": 14247,
            "retcode": 1,
            "stdout": "tune2fs 1.44.5 (15-Dec-2018)",
            "stderr": "tune2fs: No such file or directory while trying to open /dev/donkey\nCouldn't find valid filesystem superblock.",
            "comment": [
                "tune2fs 1.44.5 (15-Dec-2018)",
                "tune2fs: No such file or directory while trying to open /dev/donkey",
                "Couldn't find valid filesystem superblock.",
            ],
        }


# 'dump' function tests: 1


def test_dump():
    """
    Tests if specified group was added
    """
    mock = MagicMock()
    with patch.dict(extfs.__salt__, {"cmd.run": mock}):
        assert {"attributes": {}, "blocks": {}} == extfs.dump("/dev/sda1")


# 'attributes' function tests: 1


def test_attributes():
    """
    Tests if specified group was added
    """
    with patch(
        "salt.modules.extfs.dump",
        MagicMock(return_value={"attributes": {}, "blocks": {}}),
    ):
        assert {} == extfs.attributes("/dev/sda1")


# 'blocks' function tests: 1


def test_blocks():
    """
    Tests if specified group was added
    """
    with patch(
        "salt.modules.extfs.dump",
        MagicMock(return_value={"attributes": {}, "blocks": {}}),
    ):
        assert {} == extfs.blocks("/dev/sda1")
