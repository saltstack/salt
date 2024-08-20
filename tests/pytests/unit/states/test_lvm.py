"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.lvm as lvm
from salt.exceptions import ArgumentValueError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def lv01():
    return {
        "/dev/testvg01/testlv01": {
            "Logical Volume Name": "/dev/testvg01/testlv01",
            "Volume Group Name": "testvg01",
            "Logical Volume Access": "3",
            "Logical Volume Status": "1",
            "Internal Logical Volume Number": "-1",
            "Open Logical Volumes": "0",
            "Logical Volume Size": "4194304",
            "Current Logical Extents Associated": "512",
            "Allocated Logical Extents": "-1",
            "Allocation Policy": "0",
            "Read Ahead Sectors": "-1",
            "Major Device Number": "253",
            "Minor Device Number": "9",
        }
    }


@pytest.fixture
def lv02():
    return {
        "/dev/testvg01/testlv02": {
            "Logical Volume Name": "/dev/testvg01/testlv02",
            "Volume Group Name": "testvg01",
            "Logical Volume Access": "3",
            "Logical Volume Status": "1",
            "Internal Logical Volume Number": "-1",
            "Open Logical Volumes": "0",
            "Logical Volume Size": "4194304",
            "Current Logical Extents Associated": "512",
            "Allocated Logical Extents": "-1",
            "Allocation Policy": "0",
            "Read Ahead Sectors": "-1",
            "Major Device Number": "253",
            "Minor Device Number": "9",
        }
    }


@pytest.fixture
def configure_loader_modules():
    return {lvm: {}}


def test_pv_present():
    """
    Test to set a physical device to be used as an LVM physical volume
    """
    name = "/dev/sda5"

    comt = f"Physical Volume {name} already present"

    ret = {"name": name, "changes": {}, "result": True, "comment": comt}

    mock = MagicMock(side_effect=[True, False])
    with patch.dict(lvm.__salt__, {"lvm.pvdisplay": mock}):
        assert lvm.pv_present(name) == ret

        comt = f"Physical Volume {name} is set to be created"
        ret.update({"comment": comt, "result": None})
        with patch.dict(lvm.__opts__, {"test": True}):
            assert lvm.pv_present(name) == ret


def test_pv_absent():
    """
    Test to ensure that a Physical Device is not being used by lvm
    """
    name = "/dev/sda5"

    comt = f"Physical Volume {name} does not exist"

    ret = {"name": name, "changes": {}, "result": True, "comment": comt}

    mock = MagicMock(side_effect=[False, True])
    with patch.dict(lvm.__salt__, {"lvm.pvdisplay": mock}):
        assert lvm.pv_absent(name) == ret

        comt = f"Physical Volume {name} is set to be removed"
        ret.update({"comment": comt, "result": None})
        with patch.dict(lvm.__opts__, {"test": True}):
            assert lvm.pv_absent(name) == ret


def test_vg_present():
    """
    Test to create an LVM volume group
    """
    name = "testvg00"

    comt = f"Failed to create Volume Group {name}"

    ret = {"name": name, "changes": {}, "result": False, "comment": comt}

    mock = MagicMock(return_value=False)
    with patch.dict(lvm.__salt__, {"lvm.vgdisplay": mock, "lvm.vgcreate": mock}):
        with patch.dict(lvm.__opts__, {"test": False}):
            assert lvm.vg_present(name) == ret

        comt = f"Volume Group {name} is set to be created"
        ret.update({"comment": comt, "result": None})
        with patch.dict(lvm.__opts__, {"test": True}):
            assert lvm.vg_present(name) == ret


def test_vg_absent():
    """
    Test to remove an LVM volume group
    """
    name = "testvg00"

    comt = f"Volume Group {name} already absent"

    ret = {"name": name, "changes": {}, "result": True, "comment": comt}

    mock = MagicMock(side_effect=[False, True])
    with patch.dict(lvm.__salt__, {"lvm.vgdisplay": mock}):
        assert lvm.vg_absent(name) == ret

        comt = f"Volume Group {name} is set to be removed"
        ret.update({"comment": comt, "result": None})
        with patch.dict(lvm.__opts__, {"test": True}):
            assert lvm.vg_absent(name) == ret


def test_lv_present(lv01, lv02):
    """
    Test to create a new logical volume
    """
    name = "testlv01"
    vgname = "testvg01"
    comt = f"Logical Volume {name} already present"
    ret = {"name": name, "changes": {}, "result": True, "comment": comt}

    mock = MagicMock(return_value=lv01)
    with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
        assert lvm.lv_present(name, vgname=vgname) == ret

    mock = MagicMock(return_value=lv02)
    with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
        comt = f"Logical Volume {name} is set to be created"
        ret.update({"comment": comt, "result": None})
        with patch.dict(lvm.__opts__, {"test": True}):
            assert lvm.lv_present(name, vgname=vgname) == ret


def test_lv_present_with_valid_suffixes(lv01, lv02):
    """
    Test to create a new logical volume specifying valid suffixes
    """
    name = "testlv01"
    vgname = "testvg01"
    sizes_list = [
        "2048",
        "2048m",
        "2048M",
        "2048MB",
        "2048mb",
        "2g",
        "2G",
        "2GB",
        "2gb",
        "4194304s",
        "4194304S",
    ]
    comt = f"Logical Volume {name} already present"
    ret = {"name": name, "changes": {}, "result": True, "comment": comt}

    mock = MagicMock(return_value=lv01)
    with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
        for size in sizes_list:
            assert lvm.lv_present(name, vgname=vgname, size=size) == ret

    sizes_list = [
        "1G",
        "1g",
        "2M",
        "2m",
        "3T",
        "3t",
        "4P",
        "4p",
        "5s",
        "5S",
        "1GB",
        "1gb",
        "2MB",
        "2mb",
        "3TB",
        "3tb",
        "4PB",
        "4pb",
    ]
    mock = MagicMock(return_value=lv02)
    with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
        comt = f"Logical Volume {name} is set to be created"
        ret.update({"comment": comt, "result": None})
        with patch.dict(lvm.__opts__, {"test": True}):
            for size in sizes_list:
                assert lvm.lv_present(name, vgname=vgname, size=size) == ret


def test_lv_present_with_invalid_suffixes(lv02):
    """
    Test to create a new logical volume specifying valid suffixes
    """
    name = "testlv01"
    vgname = "testvg01"
    sizes_list = ["1B", "1b", "2K", "2k", "2KB", "2kb", "3BB", "3Bb", "4JKL", "YJK"]
    comt = f"Logical Volume {name} already present"
    ret = {"name": name, "changes": {}, "result": True, "comment": comt}

    mock = MagicMock(return_value=lv02)
    with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
        comt = f"Logical Volume {name} is set to be created"
        ret.update({"comment": comt, "result": None})
        with patch.dict(lvm.__opts__, {"test": True}):
            for size in sizes_list:
                pytest.raises(
                    ArgumentValueError,
                    lvm.lv_present,
                    name,
                    vgname=vgname,
                    size=size,
                )


def test_lv_present_with_percentage_extents(lv01, lv02):
    """
    Test to create a new logical volume specifying extents as a percentage
    """
    name = "testlv01"
    vgname = "testvg01"
    extents = "42%FREE"
    comt = "Logical Volume {} already present, {} won't be resized.".format(
        name, extents
    )
    ret = {"name": name, "changes": {}, "result": True, "comment": comt}

    mock = MagicMock(return_value=lv01)
    with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
        assert lvm.lv_present(name, vgname=vgname, extents=extents) == ret

    extents = "42%VG"
    mock = MagicMock(return_value=lv02)
    with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
        comt = f"Logical Volume {name} is set to be created"
        ret.update({"comment": comt, "result": None})
        with patch.dict(lvm.__opts__, {"test": True}):
            assert lvm.lv_present(name, vgname=vgname, extents=extents) == ret


def test_lv_present_with_force(lv01, lv02):
    """
    Test to create a new logical volume with force=True
    """
    name = "testlv01"
    vgname = "testvg01"
    comt = f"Logical Volume {name} already present"
    ret = {"name": name, "changes": {}, "result": True, "comment": comt}

    mock = MagicMock(return_value=lv01)
    with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
        assert lvm.lv_present(name, vgname=vgname, force=True) == ret

    mock = MagicMock(return_value=lv02)
    with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
        comt = f"Logical Volume {name} is set to be created"
        ret.update({"comment": comt, "result": None})
        with patch.dict(lvm.__opts__, {"test": True}):
            assert lvm.lv_present(name, vgname=vgname, force=True) == ret


def test_lv_present_with_same_size(lv01):
    """
    Test to specify the same volume size as parameter
    """
    name = "testlv01"
    vgname = "testvg01"
    comt = f"Logical Volume {name} already present"
    ret = {"name": name, "changes": {}, "result": True, "comment": comt}

    mock = MagicMock(return_value=lv01)
    with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
        assert lvm.lv_present(name, vgname=vgname, size="2G") == ret


def test_lv_present_with_increase(lv01):
    """
    Test to increase a logical volume
    """
    name = "testlv01"
    vgname = "testvg01"
    comt = f"Logical Volume {name} is set to be resized"
    ret = {"name": name, "changes": {}, "result": None, "comment": comt}

    mock = MagicMock(return_value=lv01)
    with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
        with patch.dict(lvm.__opts__, {"test": True}):
            assert lvm.lv_present(name, vgname=vgname, size="10G") == ret


def test_lv_present_with_reduce_without_force(lv01):
    """
    Test to reduce a logical volume
    """
    name = "testlv01"
    vgname = "testvg01"
    comt = "To reduce a Logical Volume option 'force' must be True."
    ret = {"name": name, "changes": {}, "result": False, "comment": comt}

    mock = MagicMock(return_value=lv01)
    with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
        assert lvm.lv_present(name, vgname=vgname, size="1G") == ret


def test_lv_present_with_reduce_with_force(lv01):
    """
    Test to reduce a logical volume
    """
    name = "testlv01"
    vgname = "testvg01"
    comt = f"Logical Volume {name} is set to be resized"
    ret = {"name": name, "changes": {}, "result": None, "comment": comt}

    mock = MagicMock(return_value=lv01)
    with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
        with patch.dict(lvm.__opts__, {"test": True}):
            assert lvm.lv_present(name, vgname=vgname, size="1G", force=True) == ret


def test_lv_absent():
    """
    Test to remove a given existing logical volume from a named existing volume group
    """
    name = "testlv00"

    comt = f"Logical Volume {name} already absent"

    ret = {"name": name, "changes": {}, "result": True, "comment": comt}

    mock = MagicMock(side_effect=[False, True])
    with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
        assert lvm.lv_absent(name) == ret

        comt = f"Logical Volume {name} is set to be removed"
        ret.update({"comment": comt, "result": None})
        with patch.dict(lvm.__opts__, {"test": True}):
            assert lvm.lv_absent(name) == ret
