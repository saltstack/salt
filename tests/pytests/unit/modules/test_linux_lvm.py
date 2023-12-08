"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>

    TestCase for the salt.modules.linux_lvm module
"""


import os.path

import pytest

import salt.modules.linux_lvm as linux_lvm
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {linux_lvm: {}}


def test_version():
    """
    Tests LVM version info from lvm version
    """
    mock = MagicMock(
        return_value=(
            "  LVM version:     2.02.168(2) (2016-11-30)\n"
            "  Library version: 1.03.01 (2016-11-30)\n"
            "  Driver version:  4.35.0\n"
        )
    )
    with patch.dict(linux_lvm.__salt__, {"cmd.run": mock}):
        assert linux_lvm.version() == "2.02.168(2) (2016-11-30)"


def test_fullversion():
    """
    Tests all version info from lvm version
    """
    mock = MagicMock(
        return_value=(
            "  LVM version:     2.02.168(2) (2016-11-30)\n"
            "  Library version: 1.03.01 (2016-11-30)\n"
            "  Driver version:  4.35.0\n"
        )
    )
    with patch.dict(linux_lvm.__salt__, {"cmd.run": mock}):
        assert linux_lvm.fullversion() == {
            "LVM version": "2.02.168(2) (2016-11-30)",
            "Library version": "1.03.01 (2016-11-30)",
            "Driver version": "4.35.0",
        }


def test_pvdisplay():
    """
    Tests information about the physical volume(s)
    """
    mock = MagicMock(return_value={"retcode": 1})
    with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
        assert linux_lvm.pvdisplay() == {}

    mock = MagicMock(return_value={"retcode": 1})
    with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
        assert linux_lvm.pvdisplay(quiet=True) == {}
        mock.assert_called_with(
            ["pvdisplay", "-c"], ignore_retcode=True, python_shell=False
        )

    mock = MagicMock(return_value={"retcode": 0, "stdout": "A:B:C:D:E:F:G:H:I:J:K"})
    with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
        assert linux_lvm.pvdisplay() == {
            "A": {
                "Allocated Physical Extents": "K",
                "Current Logical Volumes Here": "G",
                "Free Physical Extents": "J",
                "Internal Physical Volume Number": "D",
                "Physical Extent Size (kB)": "H",
                "Physical Volume (not) Allocatable": "F",
                "Physical Volume Device": "A",
                "Physical Volume Size (kB)": "C",
                "Physical Volume Status": "E",
                "Total Physical Extents": "I",
                "Volume Group Name": "B",
            }
        }

        mockpath = MagicMock(return_value="Z")
        with patch.object(os.path, "realpath", mockpath):
            assert linux_lvm.pvdisplay(real=True) == {
                "Z": {
                    "Allocated Physical Extents": "K",
                    "Current Logical Volumes Here": "G",
                    "Free Physical Extents": "J",
                    "Internal Physical Volume Number": "D",
                    "Physical Extent Size (kB)": "H",
                    "Physical Volume (not) Allocatable": "F",
                    "Physical Volume Device": "A",
                    "Physical Volume Size (kB)": "C",
                    "Physical Volume Status": "E",
                    "Real Physical Volume Device": "Z",
                    "Total Physical Extents": "I",
                    "Volume Group Name": "B",
                }
            }


def test_vgdisplay():
    """
    Tests information about the volume group(s)
    """
    mock = MagicMock(return_value={"retcode": 1})
    with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
        assert linux_lvm.vgdisplay() == {}

    mock = MagicMock(return_value={"retcode": 1})
    with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
        assert linux_lvm.vgdisplay(quiet=True) == {}
        mock.assert_called_with(
            ["vgdisplay", "-c"], ignore_retcode=True, python_shell=False
        )

    mock = MagicMock(
        return_value={"retcode": 0, "stdout": "A:B:C:D:E:F:G:H:I:J:K:L:M:N:O:P:Q"}
    )
    with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
        assert linux_lvm.vgdisplay() == {
            "A": {
                "Actual Physical Volumes": "K",
                "Allocated Physical Extents": "O",
                "Current Logical Volumes": "F",
                "Current Physical Volumes": "J",
                "Free Physical Extents": "P",
                "Internal Volume Group Number": "D",
                "Maximum Logical Volume Size": "H",
                "Maximum Logical Volumes": "E",
                "Maximum Physical Volumes": "I",
                "Open Logical Volumes": "G",
                "Physical Extent Size (kB)": "M",
                "Total Physical Extents": "N",
                "UUID": "Q",
                "Volume Group Access": "B",
                "Volume Group Name": "A",
                "Volume Group Size (kB)": "L",
                "Volume Group Status": "C",
            }
        }


def test_lvdisplay():
    """
    Return information about the logical volume(s)
    """
    mock = MagicMock(return_value={"retcode": 1})
    with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
        assert linux_lvm.lvdisplay() == {}

    mock = MagicMock(return_value={"retcode": 0, "stdout": "A:B:C:D:E:F:G:H:I:J:K:L:M"})
    with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
        assert linux_lvm.lvdisplay() == {
            "A": {
                "Allocated Logical Extents": "I",
                "Allocation Policy": "J",
                "Current Logical Extents Associated": "H",
                "Internal Logical Volume Number": "E",
                "Logical Volume Access": "C",
                "Logical Volume Name": "A",
                "Logical Volume Size": "G",
                "Logical Volume Status": "D",
                "Major Device Number": "L",
                "Minor Device Number": "M",
                "Open Logical Volumes": "F",
                "Read Ahead Sectors": "K",
                "Volume Group Name": "B",
            }
        }


def test_pvcreate():
    """
    Tests for set a physical device to be used as an LVM physical volume
    """
    assert linux_lvm.pvcreate("") == "Error: at least one device is required"

    assert linux_lvm.pvcreate("A") == "A does not exist"

    # pvdisplay() would be called by pvcreate() twice: firstly to check
    # whether a device is already initialized for use by LVM and then to
    # ensure that the pvcreate executable did its job correctly.
    pvdisplay = MagicMock(side_effect=[False, True])
    with patch("salt.modules.linux_lvm.pvdisplay", pvdisplay):
        with patch.object(os.path, "exists", return_value=True):
            ret = {
                "stdout": "saltines",
                "stderr": "cheese",
                "retcode": 0,
                "pid": "1337",
            }
            mock = MagicMock(return_value=ret)
            with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
                assert linux_lvm.pvcreate("A", metadatasize=1000) is True


def test_pvcreate_existing_pvs():
    """
    Test a scenario when all the submitted devices are already LVM PVs.
    """
    pvdisplay = MagicMock(return_value=True)
    with patch("salt.modules.linux_lvm.pvdisplay", pvdisplay):
        with patch.object(os.path, "exists", return_value=True):
            ret = {
                "stdout": "saltines",
                "stderr": "cheese",
                "retcode": 0,
                "pid": "1337",
            }
            cmd_mock = MagicMock(return_value=ret)
            with patch.dict(linux_lvm.__salt__, {"cmd.run_all": cmd_mock}):
                assert linux_lvm.pvcreate("A", metadatasize=1000) is True
                assert cmd_mock.call_count == 0


def test_pvremove_not_pv():
    """
    Tests for remove a physical device not being used as an LVM physical volume
    """
    pvdisplay = MagicMock(return_value=False)
    with patch("salt.modules.linux_lvm.pvdisplay", pvdisplay):
        assert linux_lvm.pvremove("A", override=False) == "A is not a physical volume"

    pvdisplay = MagicMock(return_value=False)
    with patch("salt.modules.linux_lvm.pvdisplay", pvdisplay):
        assert linux_lvm.pvremove("A") is True


def test_pvremove():
    """
    Tests for remove a physical device being used as an LVM physical volume
    """
    pvdisplay = MagicMock(return_value=False)
    with patch("salt.modules.linux_lvm.pvdisplay", pvdisplay):
        mock = MagicMock(return_value=True)
        with patch.dict(linux_lvm.__salt__, {"lvm.pvdisplay": mock}):
            ret = {
                "stdout": "saltines",
                "stderr": "cheese",
                "retcode": 0,
                "pid": "1337",
            }
            mock = MagicMock(return_value=ret)
            with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
                assert linux_lvm.pvremove("A") is True


def test_pvresize_not_pv():
    """
    Tests for resize a physical device not being used as an LVM physical volume
    """
    pvdisplay = MagicMock(return_value=False)
    with patch("salt.modules.linux_lvm.pvdisplay", pvdisplay):
        assert linux_lvm.pvresize("A", override=False) == "A is not a physical volume"

    pvdisplay = MagicMock(return_value=False)
    with patch("salt.modules.linux_lvm.pvdisplay", pvdisplay):
        assert linux_lvm.pvresize("A") is True


def test_pvresize():
    """
    Tests for resize a physical device being used as an LVM physical volume
    """
    pvdisplay = MagicMock(return_value=False)
    with patch("salt.modules.linux_lvm.pvdisplay", pvdisplay):
        mock = MagicMock(return_value=True)
        with patch.dict(linux_lvm.__salt__, {"lvm.pvdisplay": mock}):
            ret = {
                "stdout": "saltines",
                "stderr": "cheese",
                "retcode": 0,
                "pid": "1337",
            }
            mock = MagicMock(return_value=ret)
            with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
                assert linux_lvm.pvresize("A") is True


def test_vgcreate():
    """
    Tests create an LVM volume group
    """
    assert linux_lvm.vgcreate("", "") == "Error: vgname and device(s) are both required"

    mock = MagicMock(return_value={"retcode": 0, "stderr": ""})
    with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
        with patch.object(linux_lvm, "vgdisplay", return_value={}):
            assert linux_lvm.vgcreate("fakevg", "B") == {
                "Output from vgcreate": ('Volume group "fakevg" successfully created')
            }


def test_vgextend():
    """
    Tests add physical volumes to an LVM volume group
    """
    assert linux_lvm.vgextend("", "") == "Error: vgname and device(s) are both required"

    mock = MagicMock(return_value={"retcode": 0, "stderr": ""})
    with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
        with patch.object(linux_lvm, "vgdisplay", return_value={}):
            assert linux_lvm.vgextend("fakevg", "B") == {
                "Output from vgextend": ('Volume group "fakevg" successfully extended')
            }


def test_lvcreate():
    """
    Test create a new logical volume, with option
    for which physical volume to be used
    """
    assert (
        linux_lvm.lvcreate(None, None, 1, 1)
        == "Error: Please specify only one of size or extents"
    )

    assert (
        linux_lvm.lvcreate(None, None, None, None)
        == "Error: Either size or extents must be specified"
    )

    assert (
        linux_lvm.lvcreate(None, None, thinvolume=True, thinpool=True)
        == "Error: Please set only one of thinvolume or thinpool to True"
    )

    assert (
        linux_lvm.lvcreate(None, None, thinvolume=True, extents=1)
        == "Error: Thin volume size cannot be specified as extents"
    )

    mock = MagicMock(return_value={"retcode": 0, "stderr": ""})
    with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
        with patch.object(linux_lvm, "lvdisplay", return_value={}):
            assert linux_lvm.lvcreate(None, None, None, 1) == {
                "Output from lvcreate": 'Logical volume "None" created.'
            }


def test_lvcreate_with_force():
    """
    Test create a new logical volume, with option
    for which physical volume to be used
    """
    mock = MagicMock(return_value={"retcode": 0, "stderr": ""})
    with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
        with patch.object(linux_lvm, "lvdisplay", return_value={}):
            assert linux_lvm.lvcreate(None, None, None, 1, force=True) == {
                "Output from lvcreate": 'Logical volume "None" created.'
            }


def test_lvcreate_extra_arguments_no_parameter():
    extra_args = {
        "nosync": None,
        "noudevsync": None,
        "ignoremonitoring": None,
        "thin": None,
    }
    mock = MagicMock(return_value={"retcode": 0, "stderr": ""})
    with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
        with patch.object(linux_lvm, "lvdisplay", return_value={}):
            assert linux_lvm.lvcreate(None, None, None, 1, **extra_args) == {
                "Output from lvcreate": 'Logical volume "None" created.'
            }
    expected_args = ["--{}".format(arg) for arg in extra_args]
    processed_extra_args = mock.call_args.args[0][-(len(extra_args) + 1) : -1]
    assert all([arg in expected_args for arg in processed_extra_args])


def test_lvcreate_invalid_extra_parameter():
    invalid_parameter = {"foo": "bar"}
    mock = MagicMock(return_value={"retcode": 0, "stderr": ""})
    with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
        with patch.object(linux_lvm, "lvdisplay", return_value={}):
            assert linux_lvm.lvcreate(None, None, None, 1, **invalid_parameter) == {
                "Output from lvcreate": 'Logical volume "None" created.'
            }
    processed_command = mock.call_args.args[0]
    assert "--foo" not in processed_command


def test_vgremove():
    """
    Tests to remove an LVM volume group
    """
    mock = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": '  Volume group "fakevg" successfully removed',
        }
    )
    with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
        assert (
            linux_lvm.vgremove("fakevg") == 'Volume group "fakevg" successfully removed'
        )


def test_lvremove():
    """
    Test to remove a given existing logical volume
    from a named existing volume group
    """
    mock = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": '  Logical volume "lvtest" successfully removed',
        }
    )
    with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
        assert (
            linux_lvm.lvremove("fakelv", "fakevg")
            == 'Logical volume "fakelv" successfully removed'
        )


def test_lvresize():
    """
    Tests to resize an LVM logical volume
    """
    assert linux_lvm.lvresize(1, None, 1) == {}

    assert linux_lvm.lvresize(None, None, None) == {}

    mock = MagicMock(return_value={"retcode": 0, "stderr": ""})
    with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
        assert linux_lvm.lvresize(12, "/dev/fakevg/fakelv") == {
            "Output from lvresize": (
                'Logical volume "/dev/fakevg/fakelv" successfully resized.'
            )
        }


def test_lvextend():
    """
    Tests to extend an LVM logical volume
    """
    assert linux_lvm.lvextend(1, None, 1) == {}

    assert linux_lvm.lvextend(None, None, None) == {}

    mock = MagicMock(return_value={"retcode": 0, "stderr": ""})
    with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
        assert linux_lvm.lvextend(12, "/dev/fakevg/fakelv") == {
            "Output from lvextend": (
                'Logical volume "/dev/fakevg/fakelv" successfully extended.'
            )
        }
