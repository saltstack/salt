"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs

# Import Salt Libs
import salt.states.lvm as lvm

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

STUB_LVDISPLAY_LV01 = {
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

STUB_LVDISPLAY_LV02 = {
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


class LvmTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.lvm
    """

    def setup_loader_modules(self):
        return {lvm: {}}

    # 'pv_present' function tests: 1

    def test_pv_present(self):
        """
        Test to set a physical device to be used as an LVM physical volume
        """
        name = "/dev/sda5"

        comt = "Physical Volume {} already present".format(name)

        ret = {"name": name, "changes": {}, "result": True, "comment": comt}

        mock = MagicMock(side_effect=[True, False])
        with patch.dict(lvm.__salt__, {"lvm.pvdisplay": mock}):
            self.assertDictEqual(lvm.pv_present(name), ret)

            comt = "Physical Volume {} is set to be created".format(name)
            ret.update({"comment": comt, "result": None})
            with patch.dict(lvm.__opts__, {"test": True}):
                self.assertDictEqual(lvm.pv_present(name), ret)

    # 'pv_absent' function tests: 1

    def test_pv_absent(self):
        """
        Test to ensure that a Physical Device is not being used by lvm
        """
        name = "/dev/sda5"

        comt = "Physical Volume {} does not exist".format(name)

        ret = {"name": name, "changes": {}, "result": True, "comment": comt}

        mock = MagicMock(side_effect=[False, True])
        with patch.dict(lvm.__salt__, {"lvm.pvdisplay": mock}):
            self.assertDictEqual(lvm.pv_absent(name), ret)

            comt = "Physical Volume {} is set to be removed".format(name)
            ret.update({"comment": comt, "result": None})
            with patch.dict(lvm.__opts__, {"test": True}):
                self.assertDictEqual(lvm.pv_absent(name), ret)

    # 'vg_present' function tests: 1

    def test_vg_present(self):
        """
        Test to create an LVM volume group
        """
        name = "testvg00"

        comt = "Failed to create Volume Group {}".format(name)

        ret = {"name": name, "changes": {}, "result": False, "comment": comt}

        mock = MagicMock(return_value=False)
        with patch.dict(lvm.__salt__, {"lvm.vgdisplay": mock, "lvm.vgcreate": mock}):
            with patch.dict(lvm.__opts__, {"test": False}):
                self.assertDictEqual(lvm.vg_present(name), ret)

            comt = "Volume Group {} is set to be created".format(name)
            ret.update({"comment": comt, "result": None})
            with patch.dict(lvm.__opts__, {"test": True}):
                self.assertDictEqual(lvm.vg_present(name), ret)

    # 'vg_absent' function tests: 1

    def test_vg_absent(self):
        """
        Test to remove an LVM volume group
        """
        name = "testvg00"

        comt = "Volume Group {} already absent".format(name)

        ret = {"name": name, "changes": {}, "result": True, "comment": comt}

        mock = MagicMock(side_effect=[False, True])
        with patch.dict(lvm.__salt__, {"lvm.vgdisplay": mock}):
            self.assertDictEqual(lvm.vg_absent(name), ret)

            comt = "Volume Group {} is set to be removed".format(name)
            ret.update({"comment": comt, "result": None})
            with patch.dict(lvm.__opts__, {"test": True}):
                self.assertDictEqual(lvm.vg_absent(name), ret)

    # 'lv_present' function tests: 6

    def test_lv_present(self):
        """
        Test to create a new logical volume
        """
        name = "testlv01"
        vgname = "testvg01"
        comt = "Logical Volume {} already present".format(name)
        ret = {"name": name, "changes": {}, "result": True, "comment": comt}

        mock = MagicMock(return_value=STUB_LVDISPLAY_LV01)
        with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
            self.assertDictEqual(lvm.lv_present(name, vgname=vgname), ret)

        mock = MagicMock(return_value=STUB_LVDISPLAY_LV02)
        with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
            comt = "Logical Volume {} is set to be created".format(name)
            ret.update({"comment": comt, "result": None})
            with patch.dict(lvm.__opts__, {"test": True}):
                self.assertDictEqual(lvm.lv_present(name, vgname=vgname), ret)

    def test_lv_present_with_force(self):
        """
        Test to create a new logical volume with force=True
        """
        name = "testlv01"
        vgname = "testvg01"
        comt = "Logical Volume {} already present".format(name)
        ret = {"name": name, "changes": {}, "result": True, "comment": comt}

        mock = MagicMock(return_value=STUB_LVDISPLAY_LV01)
        with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
            self.assertDictEqual(lvm.lv_present(name, vgname=vgname, force=True), ret)

        mock = MagicMock(return_value=STUB_LVDISPLAY_LV02)
        with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
            comt = "Logical Volume {} is set to be created".format(name)
            ret.update({"comment": comt, "result": None})
            with patch.dict(lvm.__opts__, {"test": True}):
                self.assertDictEqual(
                    lvm.lv_present(name, vgname=vgname, force=True), ret
                )

    def test_lv_present_with_same_size(self):
        """
        Test to specify the same volume size as parameter
        """
        name = "testlv01"
        vgname = "testvg01"
        comt = "Logical Volume {} already present".format(name)
        ret = {"name": name, "changes": {}, "result": True, "comment": comt}

        mock = MagicMock(return_value=STUB_LVDISPLAY_LV01)
        with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
            self.assertDictEqual(lvm.lv_present(name, vgname=vgname, size="2G"), ret)

    def test_lv_present_with_increase(self):
        """
        Test to increase a logical volume
        """
        name = "testlv01"
        vgname = "testvg01"
        comt = "Logical Volume {} is set to be resized".format(name)
        ret = {"name": name, "changes": {}, "result": None, "comment": comt}

        mock = MagicMock(return_value=STUB_LVDISPLAY_LV01)
        with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
            with patch.dict(lvm.__opts__, {"test": True}):
                self.assertDictEqual(
                    lvm.lv_present(name, vgname=vgname, size="10G"), ret
                )

    def test_lv_present_with_reduce_without_force(self):
        """
        Test to reduce a logical volume
        """
        name = "testlv01"
        vgname = "testvg01"
        comt = "To reduce a Logical Volume option 'force' must be True."
        ret = {"name": name, "changes": {}, "result": False, "comment": comt}

        mock = MagicMock(return_value=STUB_LVDISPLAY_LV01)
        with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
            self.assertDictEqual(lvm.lv_present(name, vgname=vgname, size="1G"), ret)

    def test_lv_present_with_reduce_with_force(self):
        """
        Test to reduce a logical volume
        """
        name = "testlv01"
        vgname = "testvg01"
        comt = "Logical Volume {} is set to be resized".format(name)
        ret = {"name": name, "changes": {}, "result": None, "comment": comt}

        mock = MagicMock(return_value=STUB_LVDISPLAY_LV01)
        with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
            with patch.dict(lvm.__opts__, {"test": True}):
                self.assertDictEqual(
                    lvm.lv_present(name, vgname=vgname, size="1G", force=True), ret
                )

    # 'lv_absent' function tests: 1

    def test_lv_absent(self):
        """
        Test to remove a given existing logical volume
        from a named existing volume group
        """
        name = "testlv00"

        comt = "Logical Volume {} already absent".format(name)

        ret = {"name": name, "changes": {}, "result": True, "comment": comt}

        mock = MagicMock(side_effect=[False, True])
        with patch.dict(lvm.__salt__, {"lvm.lvdisplay": mock}):
            self.assertDictEqual(lvm.lv_absent(name), ret)

            comt = "Logical Volume {} is set to be removed".format(name)
            ret.update({"comment": comt, "result": None})
            with patch.dict(lvm.__opts__, {"test": True}):
                self.assertDictEqual(lvm.lv_absent(name), ret)
