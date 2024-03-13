"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import os

import pytest

import salt.states.blockdev as blockdev
import salt.utils.path
from tests.support.mock import MagicMock, Mock, patch


@pytest.fixture
def configure_loader_modules():
    return {blockdev: {}}


def test_tuned():
    """
    Test to manage options of block device
    """
    name = "/dev/vg/master-data"

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    comt = ("Changes to {} cannot be applied. Not a block device. ").format(name)
    with patch.dict(blockdev.__salt__, {"file.is_blkdev": False}):
        ret.update({"comment": comt})
        assert blockdev.tuned(name) == ret

    comt = f"Changes to {name} will be applied "
    with patch.dict(blockdev.__salt__, {"file.is_blkdev": True}):
        ret.update({"comment": comt, "result": None})
        with patch.dict(blockdev.__opts__, {"test": True}):
            assert blockdev.tuned(name) == ret


def test_formatted():
    """
    Test to manage filesystems of partitions.
    """
    name = "/dev/vg/master-data"

    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    with patch.object(
        os.path, "exists", MagicMock(side_effect=[False, True, True, True, True])
    ):
        comt = f"{name} does not exist"
        ret.update({"comment": comt})
        assert blockdev.formatted(name) == ret

        mock_ext4 = MagicMock(return_value="ext4")

        # Test state return when block device is already in the correct state
        with patch.dict(blockdev.__salt__, {"cmd.run": mock_ext4}):
            comt = f"{name} already formatted with ext4"
            ret.update({"comment": comt, "result": True})
            assert blockdev.formatted(name) == ret

        # Test state return when provided block device is an invalid fs_type
        with patch.dict(blockdev.__salt__, {"cmd.run": MagicMock(return_value="")}):
            ret.update({"comment": "Invalid fs_type: foo-bar", "result": False})
            with patch.object(salt.utils.path, "which", MagicMock(return_value=False)):
                assert blockdev.formatted(name, fs_type="foo-bar") == ret

        # Test state return when provided block device state will change and test=True
        with patch.dict(
            blockdev.__salt__, {"cmd.run": MagicMock(return_value="new-thing")}
        ):
            comt = f"Changes to {name} will be applied "
            ret.update({"comment": comt, "result": None})
            with patch.object(salt.utils.path, "which", MagicMock(return_value=True)):
                with patch.dict(blockdev.__opts__, {"test": True}):
                    assert blockdev.formatted(name) == ret

        # Test state return when block device format fails
        with patch.dict(
            blockdev.__salt__,
            {
                "cmd.run": MagicMock(return_value=mock_ext4),
                "disk.format": MagicMock(return_value=True),
            },
        ):
            comt = f"Failed to format {name}"
            ret.update({"comment": comt, "result": False})
            with patch.object(salt.utils.path, "which", MagicMock(return_value=True)):
                with patch.dict(blockdev.__opts__, {"test": False}):
                    assert blockdev.formatted(name) == ret


def test__checkblk():
    """
    Confirm that we call cmd.run with ignore_retcode=True
    """
    cmd_mock = Mock()
    with patch.dict(blockdev.__salt__, {"cmd.run": cmd_mock}):
        blockdev._checkblk("/dev/foo")

    cmd_mock.assert_called_once_with(
        ["blkid", "-o", "value", "-s", "TYPE", "/dev/foo"], ignore_retcode=True
    )
