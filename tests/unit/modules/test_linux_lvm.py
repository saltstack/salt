"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

# Import Python libs

import os.path

# Import Salt Libs
import salt.modules.linux_lvm as linux_lvm

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class LinuxLVMTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for the salt.modules.linux_lvm module
    """

    def setup_loader_modules(self):
        return {linux_lvm: {}}

    def test_version(self):
        """
        Tests LVM version info from lvm version
        """
        mock = MagicMock(
            return_value="  LVM version:     2.02.168(2) (2016-11-30)\n"
            "  Library version: 1.03.01 (2016-11-30)\n"
            "  Driver version:  4.35.0\n"
        )
        with patch.dict(linux_lvm.__salt__, {"cmd.run": mock}):
            self.assertEqual(linux_lvm.version(), "2.02.168(2) (2016-11-30)")

    def test_fullversion(self):
        """
        Tests all version info from lvm version
        """
        mock = MagicMock(
            return_value="  LVM version:     2.02.168(2) (2016-11-30)\n"
            "  Library version: 1.03.01 (2016-11-30)\n"
            "  Driver version:  4.35.0\n"
        )
        with patch.dict(linux_lvm.__salt__, {"cmd.run": mock}):
            self.assertDictEqual(
                linux_lvm.fullversion(),
                {
                    "LVM version": "2.02.168(2) (2016-11-30)",
                    "Library version": "1.03.01 (2016-11-30)",
                    "Driver version": "4.35.0",
                },
            )

    def test_pvdisplay(self):
        """
        Tests information about the physical volume(s)
        """
        mock = MagicMock(return_value={"retcode": 1})
        with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
            self.assertDictEqual(linux_lvm.pvdisplay(), {})

        mock = MagicMock(return_value={"retcode": 1})
        with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
            self.assertDictEqual(linux_lvm.pvdisplay(quiet=True), {})
            mock.assert_called_with(
                ["pvdisplay", "-c"], ignore_retcode=True, python_shell=False
            )

        mock = MagicMock(return_value={"retcode": 0, "stdout": "A:B:C:D:E:F:G:H:I:J:K"})
        with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
            self.assertDictEqual(
                linux_lvm.pvdisplay(),
                {
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
                },
            )

            mockpath = MagicMock(return_value="Z")
            with patch.object(os.path, "realpath", mockpath):
                self.assertDictEqual(
                    linux_lvm.pvdisplay(real=True),
                    {
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
                    },
                )

    def test_vgdisplay(self):
        """
        Tests information about the volume group(s)
        """
        mock = MagicMock(return_value={"retcode": 1})
        with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
            self.assertDictEqual(linux_lvm.vgdisplay(), {})

        mock = MagicMock(return_value={"retcode": 1})
        with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
            self.assertDictEqual(linux_lvm.vgdisplay(quiet=True), {})
            mock.assert_called_with(
                ["vgdisplay", "-c"], ignore_retcode=True, python_shell=False
            )

        mock = MagicMock(
            return_value={"retcode": 0, "stdout": "A:B:C:D:E:F:G:H:I:J:K:L:M:N:O:P:Q"}
        )
        with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
            self.assertDictEqual(
                linux_lvm.vgdisplay(),
                {
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
                },
            )

    def test_lvdisplay(self):
        """
        Return information about the logical volume(s)
        """
        mock = MagicMock(return_value={"retcode": 1})
        with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
            self.assertDictEqual(linux_lvm.lvdisplay(), {})

        mock = MagicMock(
            return_value={"retcode": 0, "stdout": "A:B:C:D:E:F:G:H:I:J:K:L:M"}
        )
        with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
            self.assertDictEqual(
                linux_lvm.lvdisplay(),
                {
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
                },
            )

    def test_pvcreate(self):
        """
        Tests for set a physical device to be used as an LVM physical volume
        """
        self.assertEqual(
            linux_lvm.pvcreate(""), "Error: at least one device is required"
        )

        self.assertEqual(linux_lvm.pvcreate("A"), "A does not exist")

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
                    self.assertEqual(linux_lvm.pvcreate("A", metadatasize=1000), True)

    def test_pvcreate_existing_pvs(self):
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
                    self.assertEqual(linux_lvm.pvcreate("A", metadatasize=1000), True)
                    self.assertTrue(cmd_mock.call_count == 0)

    def test_pvremove_not_pv(self):
        """
        Tests for remove a physical device not being used as an LVM physical volume
        """
        pvdisplay = MagicMock(return_value=False)
        with patch("salt.modules.linux_lvm.pvdisplay", pvdisplay):
            self.assertEqual(
                linux_lvm.pvremove("A", override=False), "A is not a physical volume"
            )

        pvdisplay = MagicMock(return_value=False)
        with patch("salt.modules.linux_lvm.pvdisplay", pvdisplay):
            self.assertEqual(linux_lvm.pvremove("A"), True)

    def test_pvremove(self):
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
                    self.assertEqual(linux_lvm.pvremove("A"), True)

    def test_pvresize_not_pv(self):
        """
        Tests for resize a physical device not being used as an LVM physical volume
        """
        pvdisplay = MagicMock(return_value=False)
        with patch("salt.modules.linux_lvm.pvdisplay", pvdisplay):
            self.assertEqual(
                linux_lvm.pvresize("A", override=False), "A is not a physical volume"
            )

        pvdisplay = MagicMock(return_value=False)
        with patch("salt.modules.linux_lvm.pvdisplay", pvdisplay):
            self.assertEqual(linux_lvm.pvresize("A"), True)

    def test_pvresize(self):
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
                    self.assertEqual(linux_lvm.pvresize("A"), True)

    def test_vgcreate(self):
        """
        Tests create an LVM volume group
        """
        self.assertEqual(
            linux_lvm.vgcreate("", ""), "Error: vgname and device(s) are both required"
        )

        mock = MagicMock(return_value={"retcode": 0, "stderr": ""})
        with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
            with patch.object(linux_lvm, "vgdisplay", return_value={}):
                self.assertDictEqual(
                    linux_lvm.vgcreate("fakevg", "B"),
                    {
                        "Output from vgcreate": 'Volume group "fakevg" successfully created'
                    },
                )

    def test_vgextend(self):
        """
        Tests add physical volumes to an LVM volume group
        """
        self.assertEqual(
            linux_lvm.vgextend("", ""), "Error: vgname and device(s) are both required"
        )

        mock = MagicMock(return_value={"retcode": 0, "stderr": ""})
        with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
            with patch.object(linux_lvm, "vgdisplay", return_value={}):
                self.assertDictEqual(
                    linux_lvm.vgextend("fakevg", "B"),
                    {
                        "Output from vgextend": 'Volume group "fakevg" successfully extended'
                    },
                )

    def test_lvcreate(self):
        """
        Test create a new logical volume, with option
        for which physical volume to be used
        """
        self.assertEqual(
            linux_lvm.lvcreate(None, None, 1, 1),
            "Error: Please specify only one of size or extents",
        )

        self.assertEqual(
            linux_lvm.lvcreate(None, None, None, None),
            "Error: Either size or extents must be specified",
        )

        self.assertEqual(
            linux_lvm.lvcreate(None, None, thinvolume=True, thinpool=True),
            "Error: Please set only one of thinvolume or thinpool to True",
        )

        self.assertEqual(
            linux_lvm.lvcreate(None, None, thinvolume=True, extents=1),
            "Error: Thin volume size cannot be specified as extents",
        )

        mock = MagicMock(return_value={"retcode": 0, "stderr": ""})
        with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
            with patch.object(linux_lvm, "lvdisplay", return_value={}):
                self.assertDictEqual(
                    linux_lvm.lvcreate(None, None, None, 1),
                    {"Output from lvcreate": 'Logical volume "None" created.'},
                )

    def test_lvcreate_with_force(self):
        """
        Test create a new logical volume, with option
        for which physical volume to be used
        """
        mock = MagicMock(return_value={"retcode": 0, "stderr": ""})
        with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
            with patch.object(linux_lvm, "lvdisplay", return_value={}):
                self.assertDictEqual(
                    linux_lvm.lvcreate(None, None, None, 1, force=True),
                    {"Output from lvcreate": 'Logical volume "None" created.'},
                )

    def test_vgremove(self):
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
            self.assertEqual(
                linux_lvm.vgremove("fakevg"),
                'Volume group "fakevg" successfully removed',
            )

    def test_lvremove(self):
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
            self.assertEqual(
                linux_lvm.lvremove("fakelv", "fakevg"),
                'Logical volume "fakelv" successfully removed',
            )

    def test_lvresize(self):
        """
        Tests to resize an LVM logical volume
        """
        self.assertEqual(linux_lvm.lvresize(1, None, 1), {})

        self.assertEqual(linux_lvm.lvresize(None, None, None), {})

        mock = MagicMock(return_value={"retcode": 0, "stderr": ""})
        with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
            self.assertDictEqual(
                linux_lvm.lvresize(12, "/dev/fakevg/fakelv"),
                {
                    "Output from lvresize": 'Logical volume "/dev/fakevg/fakelv" successfully resized.'
                },
            )

    def test_lvextend(self):
        """
        Tests to extend an LVM logical volume
        """
        self.assertEqual(linux_lvm.lvextend(1, None, 1), {})

        self.assertEqual(linux_lvm.lvextend(None, None, None), {})

        mock = MagicMock(return_value={"retcode": 0, "stderr": ""})
        with patch.dict(linux_lvm.__salt__, {"cmd.run_all": mock}):
            self.assertDictEqual(
                linux_lvm.lvextend(12, "/dev/fakevg/fakelv"),
                {
                    "Output from lvextend": 'Logical volume "/dev/fakevg/fakelv" successfully extended.'
                },
            )
