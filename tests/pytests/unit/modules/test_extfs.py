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
    mock = MagicMock()
    with patch.dict(extfs.__salt__, {"cmd.run": mock}):
        assert [] == extfs.mkfs("/dev/sda1", "ext4")


# 'tune' function tests: 1


def test_tune():
    """
    Tests if specified group was added
    """
    mock = MagicMock()
    with patch.dict(extfs.__salt__, {"cmd.run": mock}), patch(
        "salt.modules.extfs.tune", MagicMock(return_value="")
    ):
        assert "" == extfs.tune("/dev/sda1")


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
