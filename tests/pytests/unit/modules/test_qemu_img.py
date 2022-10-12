"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""


import os

import pytest

import salt.modules.qemu_img as qemu_img
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {qemu_img: {}}


def test_make_image():
    """
    Test for create a blank virtual machine image file
    of the specified size in megabytes
    """
    with patch.object(
        os.path, "isabs", MagicMock(side_effect=[False, True, True, True])
    ):
        assert qemu_img.make_image("location", "size", "fmt") == ""

        with patch.object(os.path, "isdir", MagicMock(side_effect=[False, True, True])):
            assert qemu_img.make_image("location", "size", "fmt") == ""

            with patch.dict(
                qemu_img.__salt__,
                {"cmd.retcode": MagicMock(side_effect=[False, True])},
            ):
                assert qemu_img.make_image("location", "size", "fmt") == "location"
                assert qemu_img.make_image("location", "size", "fmt") == ""
