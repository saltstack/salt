"""
    :codeauthor: `Nitin Madhok <nmadhok@g.clemson.edu>`

    tests.unit.cloud.clouds.vmware_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import pytest

from salt.cloud.clouds import vmware
from salt.exceptions import SaltCloudSystemExit
from tests.support.mock import MagicMock

# Attempt to import pyVim and pyVmomi libs
HAS_LIBS = True
# pylint: disable=import-error,no-name-in-module,unused-import
try:
    from pyVim.connect import Disconnect, SmartConnect
    from pyVmomi import vim, vmodl
except ImportError:
    HAS_LIBS = False
# pylint: enable=import-error,no-name-in-module,unused-import


def _test_clone_type(clone_type):
    """
    Assertions for checking that a certain clone type
    works
    """
    obj_ref = MagicMock()
    obj_ref.snapshot = vim.vm.Snapshot(None, None)
    obj_ref.snapshot.currentSnapshot = vim.vm.Snapshot(None, None)
    clone_spec = vmware.handle_snapshot(
        vim.vm.ConfigSpec(),
        obj_ref,
        vim.vm.RelocateSpec(),
        False,
        {"snapshot": {"disk_move_type": clone_type}},
    )
    assert clone_spec.location.diskMoveType == clone_type

    obj_ref2 = MagicMock()
    obj_ref2.snapshot = vim.vm.Snapshot(None, None)
    obj_ref2.snapshot.currentSnapshot = vim.vm.Snapshot(None, None)

    clone_spec2 = vmware.handle_snapshot(
        vim.vm.ConfigSpec(),
        obj_ref2,
        vim.vm.RelocateSpec(),
        True,
        {"snapshot": {"disk_move_type": clone_type}},
    )

    assert clone_spec2.location.diskMoveType == clone_type


@pytest.mark.skipif(
    HAS_LIBS is False, reason="Install pyVmomi to be able to run this unit test."
)
def test_quick_linked_clone():
    """
    Test that disk move type is
    set to createNewChildDiskBacking
    """
    _test_clone_type(vmware.QUICK_LINKED_CLONE)


@pytest.mark.skipif(
    HAS_LIBS is False, reason="Install pyVmomi to be able to run this unit test."
)
def test_current_state_linked_clone():
    """
    Test that disk move type is
    set to moveChildMostDiskBacking
    """
    _test_clone_type(vmware.CURRENT_STATE_LINKED_CLONE)


@pytest.mark.skipif(
    HAS_LIBS is False, reason="Install pyVmomi to be able to run this unit test."
)
def test_copy_all_disks_full_clone():
    """
    Test that disk move type is
    set to moveAllDiskBackingsAndAllowSharing
    """
    _test_clone_type(vmware.COPY_ALL_DISKS_FULL_CLONE)


@pytest.mark.skipif(
    HAS_LIBS is False, reason="Install pyVmomi to be able to run this unit test."
)
def test_flatten_all_all_disks_full_clone():
    """
    Test that disk move type is
    set to moveAllDiskBackingsAndDisallowSharing
    """
    _test_clone_type(vmware.FLATTEN_DISK_FULL_CLONE)


@pytest.mark.skipif(
    HAS_LIBS is False, reason="Install pyVmomi to be able to run this unit test."
)
def test_raises_error_for_invalid_disk_move_type():
    """
    Test that invalid disk move type
    raises error
    """
    pytest.raises(SaltCloudSystemExit, _test_clone_type, "foobar")
