"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import os

import salt.states.mount as mount
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class MountTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.mount
    """

    def setup_loader_modules(self):
        return {mount: {}}

    # 'mounted' function tests: 1

    def test_mounted(self):
        """
        Test to verify that a device is mounted.
        """
        name = os.path.realpath("/mnt/sdb")
        device = os.path.realpath("/dev/sdb5")
        fstype = "xfs"

        name2 = os.path.realpath("/mnt/cifs")
        device2 = "//SERVER/SHARE/"
        fstype2 = "cifs"
        opts2 = ["noowners"]
        superopts2 = ["uid=510", "gid=100", "username=cifsuser", "domain=cifsdomain"]

        name3 = os.path.realpath("/mnt/jfs2")
        device3 = "/dev/hd1"
        fstype3 = "jfs2"
        opts3 = [""]
        superopts3 = ["uid=510", "gid=100", "username=jfs2user", "domain=jfs2sdomain"]

        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        mock = MagicMock(
            side_effect=["new", "present", "new", "change", "bad config", "salt"]
        )
        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        mock_ret = MagicMock(return_value={"retcode": 1})
        mock_mnt = MagicMock(
            return_value={
                name: {"device": device, "opts": [], "superopts": []},
                name2: {"device": device2, "opts": opts2, "superopts": superopts2},
                name3: {"device": device3, "opts": opts3, "superopts": superopts3},
            }
        )
        mock_aixfs_retn = MagicMock(return_value="present")

        mock_emt = MagicMock(return_value={})
        mock_str = MagicMock(return_value="salt")
        mock_user = MagicMock(return_value={"uid": 510})
        mock_group = MagicMock(return_value={"gid": 100})
        mock_read_cache = MagicMock(return_value={})
        mock_write_cache = MagicMock(return_value=True)
        with patch.dict(mount.__grains__, {"os": "Darwin"}):
            with patch.dict(
                mount.__salt__,
                {
                    "mount.active": mock_mnt,
                    "cmd.run_all": mock_ret,
                    "mount.umount": mock_f,
                },
            ), patch("os.path.exists", MagicMock(return_value=True)):
                comt = "Unable to find device with label /dev/sdb5."
                ret.update({"comment": comt})
                self.assertDictEqual(
                    mount.mounted(name, "LABEL=/dev/sdb5", fstype), ret
                )

                with patch.dict(mount.__opts__, {"test": True}):
                    comt = "Remount would be forced because options (noowners) changed"
                    ret.update({"comment": comt, "result": None})
                    self.assertDictEqual(mount.mounted(name, device, fstype), ret)

                with patch.dict(mount.__opts__, {"test": False}):
                    comt = "Unable to unmount {}: False.".format(name)
                    umount = (
                        "Forced unmount and mount because options (noowners) changed"
                    )
                    ret.update(
                        {
                            "comment": comt,
                            "result": False,
                            "changes": {"umount": umount},
                        }
                    )
                    self.assertDictEqual(mount.mounted(name, device, "nfs"), ret)

                    umount1 = (
                        "Forced unmount because devices don't match. "
                        "Wanted: {0}, current: {1}, {1}".format(
                            os.path.realpath("/dev/sdb6"), device
                        )
                    )
                    comt = "Unable to unmount"
                    ret.update(
                        {
                            "comment": comt,
                            "result": None,
                            "changes": {"umount": umount1},
                        }
                    )
                    self.assertDictEqual(
                        mount.mounted(
                            name, os.path.realpath("/dev/sdb6"), fstype, opts=[]
                        ),
                        ret,
                    )

                with patch.dict(
                    mount.__salt__,
                    {
                        "mount.active": mock_emt,
                        "mount.mount": mock_str,
                        "mount.set_automaster": mock,
                    },
                ):
                    with patch.dict(mount.__opts__, {"test": True}), patch(
                        "os.path.exists", MagicMock(return_value=False)
                    ):
                        comt = "{} does not exist and would not be created".format(name)
                        ret.update({"comment": comt, "changes": {}})
                        self.assertDictEqual(mount.mounted(name, device, fstype), ret)

                    with patch.dict(mount.__opts__, {"test": False}):
                        with patch.object(os.path, "exists", mock_f):
                            comt = "Mount directory is not present"
                            ret.update({"comment": comt, "result": False})
                            self.assertDictEqual(
                                mount.mounted(name, device, fstype), ret
                            )

                        with patch.object(os.path, "exists", mock_t):
                            comt = "Mount directory is not present"
                            ret.update({"comment": "salt", "result": False})
                            self.assertDictEqual(
                                mount.mounted(name, device, fstype), ret
                            )

                    with patch.dict(mount.__opts__, {"test": True}), patch(
                        "os.path.exists", MagicMock(return_value=False)
                    ):
                        comt = (
                            "{0} does not exist and would neither be created nor"
                            " mounted. {0} needs to be written to the fstab in order to"
                            " be made persistent.".format(name)
                        )
                        ret.update({"comment": comt, "result": None})
                        self.assertDictEqual(
                            mount.mounted(name, device, fstype, mount=False), ret
                        )

                    with patch.dict(mount.__opts__, {"test": False}), patch(
                        "os.path.exists", MagicMock(return_value=False)
                    ):
                        comt = (
                            "{} not present and not mounted. "
                            "Entry already exists in the fstab.".format(name)
                        )
                        ret.update({"comment": comt, "result": True})
                        self.assertDictEqual(
                            mount.mounted(name, device, fstype, mount=False), ret
                        )

                        comt = (
                            "{} not present and not mounted. "
                            "Added new entry to the fstab.".format(name)
                        )
                        ret.update(
                            {
                                "comment": comt,
                                "result": True,
                                "changes": {"persist": "new"},
                            }
                        )
                        self.assertDictEqual(
                            mount.mounted(name, device, fstype, mount=False), ret
                        )

                        comt = (
                            "{} not present and not mounted. "
                            "Updated the entry in the fstab.".format(name)
                        )
                        ret.update(
                            {
                                "comment": comt,
                                "result": True,
                                "changes": {"persist": "update"},
                            }
                        )
                        self.assertDictEqual(
                            mount.mounted(name, device, fstype, mount=False), ret
                        )

                        comt = (
                            "{} not present and not mounted. "
                            "However, the fstab was not found.".format(name)
                        )
                        ret.update({"comment": comt, "result": False, "changes": {}})
                        self.assertDictEqual(
                            mount.mounted(name, device, fstype, mount=False), ret
                        )

                        comt = "{} not present and not mounted".format(name)
                        ret.update({"comment": comt, "result": True, "changes": {}})
                        self.assertDictEqual(
                            mount.mounted(name, device, fstype, mount=False), ret
                        )

        # Test no change for uid provided as a name #25293
        with patch.dict(mount.__grains__, {"os": "CentOS"}):
            set_fstab_mock = MagicMock(autospec=True, return_value="present")
            with patch.dict(
                mount.__salt__,
                {
                    "mount.active": mock_mnt,
                    "mount.mount": mock_str,
                    "mount.umount": mock_f,
                    "mount.read_mount_cache": mock_read_cache,
                    "mount.write_mount_cache": mock_write_cache,
                    "mount.set_fstab": set_fstab_mock,
                    "user.info": mock_user,
                    "group.info": mock_group,
                },
            ):
                with patch.dict(mount.__opts__, {"test": True}), patch.object(
                    os.path, "exists", mock_t
                ):
                    # Starting with Python 3.8 the os.path.realpath function attempts to resolve
                    # symbolic links and junctions on Windows. So, since were using a share
                    # that doesn't exist, we need to mock
                    # https://docs.python.org/3/library/os.path.html?highlight=ntpath%20realpath#os.path.realpath
                    with patch.object(
                        os.path,
                        "realpath",
                        MagicMock(side_effect=[name2, device2, device2]),
                    ):
                        comt = "Target was already mounted. Entry already exists in the fstab."
                        ret.update({"name": name2, "result": True})
                        ret.update({"comment": comt, "changes": {}})
                        self.assertDictEqual(
                            mount.mounted(
                                name2,
                                device2,
                                fstype2,
                                opts=["uid=user1", "gid=group1"],
                            ),
                            ret,
                        )
                        # Test to check the options order #57520
                        set_fstab_mock.assert_called_with(
                            name2,
                            "//SERVER/SHARE/",
                            "cifs",
                            ["gid=group1", "uid=user1"],
                            0,
                            0,
                            "/etc/fstab",
                            test=True,
                            match_on="auto",
                        )

        with patch.dict(mount.__grains__, {"os": "AIX"}):
            with patch.dict(
                mount.__salt__,
                {
                    "mount.active": mock_mnt,
                    "mount.mount": mock_str,
                    "mount.umount": mock_f,
                    "mount.read_mount_cache": mock_read_cache,
                    "mount.write_mount_cache": mock_write_cache,
                    "mount.set_filesystems": mock_aixfs_retn,
                    "user.info": mock_user,
                    "group.info": mock_group,
                },
            ):
                with patch.dict(mount.__opts__, {"test": True}):
                    with patch.object(os.path, "exists", mock_t):
                        comt = (
                            "Target was already mounted. Entry already exists in the"
                            " fstab."
                        )
                        ret.update({"name": name3, "result": True})
                        ret.update({"comment": comt, "changes": {}})
                        self.assertDictEqual(
                            mount.mounted(
                                name3,
                                device3,
                                fstype3,
                                opts=["uid=user1", "gid=group1"],
                            ),
                            ret,
                        )

    # 'swap' function tests: 1

    def test_swap(self):
        """
        Test to activates a swap device.
        """
        name = "/mnt/sdb"

        ret = {"name": name, "result": None, "comment": "", "changes": {}}

        mock = MagicMock(side_effect=["present", "new", "change", "bad config"])
        mock_f = MagicMock(return_value=False)
        mock_swp = MagicMock(return_value=[name])
        mock_fs = MagicMock(return_value={"none": {"device": name, "fstype": "xfs"}})
        mock_fs_diff = MagicMock(
            return_value={"none": {"device": "something_else", "fstype": "xfs"}}
        )
        mock_aixfs = MagicMock(return_value={name: {"dev": name, "fstype": "jfs2"}})
        mock_emt = MagicMock(return_value={})
        with patch.dict(mount.__grains__, {"os": "test"}):
            with patch.dict(
                mount.__salt__,
                {
                    "mount.swaps": mock_swp,
                    "mount.fstab": mock_fs_diff,
                    "file.is_link": mock_f,
                },
            ):
                with patch.dict(mount.__opts__, {"test": True}):
                    comt = (
                        "Swap {} is set to be added to the "
                        "fstab and to be activated".format(name)
                    )
                    ret.update({"comment": comt})
                    self.assertDictEqual(mount.swap(name), ret)

                with patch.dict(mount.__opts__, {"test": False}):
                    comt = "Swap {} already active".format(name)
                    ret.update({"comment": comt, "result": True})
                    self.assertDictEqual(mount.swap(name, persist=False), ret)

                    with patch.dict(
                        mount.__salt__,
                        {"mount.fstab": mock_emt, "mount.set_fstab": mock},
                    ):
                        comt = "Swap {} already active".format(name)
                        ret.update({"comment": comt, "result": True})
                        self.assertDictEqual(mount.swap(name), ret)

                        comt = (
                            "Swap /mnt/sdb already active. "
                            "Added new entry to the fstab."
                        )
                        ret.update(
                            {
                                "comment": comt,
                                "result": True,
                                "changes": {"persist": "new"},
                            }
                        )
                        self.assertDictEqual(mount.swap(name), ret)

                        comt = (
                            "Swap /mnt/sdb already active. "
                            "Updated the entry in the fstab."
                        )
                        ret.update(
                            {
                                "comment": comt,
                                "result": True,
                                "changes": {"persist": "update"},
                            }
                        )
                        self.assertDictEqual(mount.swap(name), ret)

                        comt = (
                            "Swap /mnt/sdb already active. "
                            "However, the fstab was not found."
                        )
                        ret.update({"comment": comt, "result": False, "changes": {}})
                        self.assertDictEqual(mount.swap(name), ret)

        ret = {"name": name, "result": None, "comment": "", "changes": {}}

        mock = MagicMock(side_effect=["present", "new", "change", "bad config"])
        mock_emt = MagicMock(return_value={})
        with patch.dict(mount.__grains__, {"os": "test"}):
            with patch.dict(
                mount.__salt__,
                {
                    "mount.swaps": mock_swp,
                    "mount.fstab": mock_fs,
                    "file.is_link": mock_f,
                },
            ):
                with patch.dict(mount.__opts__, {"test": True}):
                    comt = "Swap {} already active".format(name)
                    ret.update({"comment": comt, "result": True})
                    self.assertDictEqual(mount.swap(name), ret)

                with patch.dict(mount.__opts__, {"test": False}):
                    comt = "Swap {} already active".format(name)
                    ret.update({"comment": comt, "result": True})
                    self.assertDictEqual(mount.swap(name), ret)

                    with patch.dict(
                        mount.__salt__,
                        {"mount.fstab": mock_emt, "mount.set_fstab": mock},
                    ):
                        comt = "Swap {} already active".format(name)
                        ret.update({"comment": comt, "result": True})
                        self.assertDictEqual(mount.swap(name), ret)

                        comt = (
                            "Swap /mnt/sdb already active. "
                            "Added new entry to the fstab."
                        )
                        ret.update(
                            {
                                "comment": comt,
                                "result": True,
                                "changes": {"persist": "new"},
                            }
                        )
                        self.assertDictEqual(mount.swap(name), ret)

                        comt = (
                            "Swap /mnt/sdb already active. "
                            "Updated the entry in the fstab."
                        )
                        ret.update(
                            {
                                "comment": comt,
                                "result": True,
                                "changes": {"persist": "update"},
                            }
                        )
                        self.assertDictEqual(mount.swap(name), ret)

                        comt = (
                            "Swap /mnt/sdb already active. "
                            "However, the fstab was not found."
                        )
                        ret.update({"comment": comt, "result": False, "changes": {}})
                        self.assertDictEqual(mount.swap(name), ret)

        with patch.dict(mount.__grains__, {"os": "AIX"}):
            with patch.dict(
                mount.__salt__,
                {
                    "mount.swaps": mock_swp,
                    "mount.filesystems": mock_aixfs,
                    "file.is_link": mock_f,
                },
            ):
                with patch.dict(mount.__opts__, {"test": True}):
                    comt = "Swap {} already active".format(name)
                    ret.update({"comment": comt, "result": True})
                    self.assertDictEqual(mount.swap(name), ret)

                with patch.dict(mount.__opts__, {"test": False}):
                    comt = (
                        "Swap {} already active. swap not present"
                        " in /etc/filesystems on AIX.".format(name)
                    )
                    ret.update({"comment": comt, "result": False})
                    self.assertDictEqual(mount.swap(name), ret)

                    with patch.dict(
                        mount.__salt__,
                        {"mount.filesystems": mock_emt, "mount.set_filesystems": mock},
                    ):
                        comt = (
                            "Swap {} already active. swap not present"
                            " in /etc/filesystems on AIX.".format(name)
                        )
                        ret.update({"comment": comt, "result": False})
                        self.assertDictEqual(mount.swap(name), ret)

    # 'unmounted' function tests: 1

    def test_unmounted(self):
        """
        Test to verify that a device is not mounted
        """
        name = "/mnt/sdb"
        device = "/dev/sdb5"

        ret = {"name": name, "result": None, "comment": "", "changes": {}}

        mock_f = MagicMock(return_value=False)
        mock_t = MagicMock(return_value=True)
        mock_dev = MagicMock(return_value={name: {"device": device}})
        mock_fs = MagicMock(return_value={name: {"device": name}})
        mock_mnt = MagicMock(side_effect=[{name: {}}, {}, {}, {}])

        name3 = os.path.realpath("/mnt/jfs2")
        device3 = "/dev/hd1"
        fstype3 = "jfs2"
        opts3 = [""]
        mock_mnta = MagicMock(return_value={name3: {"device": device3, "opts": opts3}})
        mock_aixfs = MagicMock(return_value={name: {"dev": name3, "fstype": fstype3}})
        mock_delete_cache = MagicMock(return_value=True)

        comt3 = (
            "Mount point /mnt/sdb is unmounted but needs to be purged "
            "from /etc/auto_salt to be made persistent"
        )

        with patch.dict(mount.__grains__, {"os": "Darwin"}):
            with patch.dict(
                mount.__salt__,
                {
                    "mount.active": mock_mnt,
                    "mount.automaster": mock_fs,
                    "file.is_link": mock_f,
                },
            ):
                with patch.dict(mount.__opts__, {"test": True}):
                    comt = "Mount point {} is mounted but should not be".format(name)
                    ret.update({"comment": comt})
                    self.assertDictEqual(mount.unmounted(name, device), ret)

                    comt = (
                        "Target was already unmounted. "
                        "fstab entry for device {} not found".format(device)
                    )
                    ret.update({"comment": comt, "result": True})
                    self.assertDictEqual(
                        mount.unmounted(name, device, persist=True), ret
                    )

                    with patch.dict(mount.__salt__, {"mount.automaster": mock_dev}):
                        ret.update({"comment": comt3, "result": None})
                        self.assertDictEqual(
                            mount.unmounted(name, device, persist=True), ret
                        )

                    comt = "Target was already unmounted"
                    ret.update({"comment": comt, "result": True})
                    self.assertDictEqual(mount.unmounted(name, device), ret)

        with patch.dict(mount.__grains__, {"os": "AIX"}):
            with patch.dict(
                mount.__salt__,
                {
                    "mount.active": mock_mnta,
                    "mount.filesystems": mock_aixfs,
                    "file.is_link": mock_f,
                },
            ):
                with patch.dict(mount.__opts__, {"test": True}):
                    comt = "Target was already unmounted"
                    ret.update({"comment": comt, "result": True})
                    self.assertDictEqual(mount.unmounted(name, device), ret)

                    comt = (
                        "Target was already unmounted. "
                        "fstab entry for device /dev/sdb5 not found"
                    )
                    ret.update({"comment": comt, "result": True})
                    self.assertDictEqual(
                        mount.unmounted(name, device, persist=True), ret
                    )

                    with patch.dict(mount.__salt__, {"mount.filesystems": mock_dev}):
                        comt = "Mount point {} is mounted but should not be".format(
                            name3
                        )
                        ret.update({"comment": comt, "result": None, "name": name3})
                        self.assertDictEqual(
                            mount.unmounted(name3, device3, persist=True), ret
                        )

                        with patch.dict(mount.__opts__, {"test": False}), patch.dict(
                            mount.__salt__,
                            {
                                "mount.umount": mock_t,
                                "mount.delete_mount_cache": mock_delete_cache,
                            },
                        ):
                            comt = "Target was successfully unmounted"
                            ret.update(
                                {
                                    "comment": comt,
                                    "result": True,
                                    "name": name3,
                                    "changes": {"umount": True},
                                }
                            )
                            self.assertDictEqual(mount.unmounted(name3, device3), ret)

    # 'mod_watch' function tests: 1

    def test_mod_watch(self):
        """
        Test the mounted watcher, called to invoke the watch command.
        """
        name = "/mnt/sdb"

        ret = {
            "name": name,
            "result": True,
            "comment": "Watch not supported in unmount at this time",
            "changes": {},
        }

        self.assertDictEqual(mount.mod_watch(name, sfun="unmount"), ret)

    def test_mounted_multiple_mounts(self):
        """
        Test to verify that a device is mounted.
        """
        name = "/mnt/nfs1"
        device = "localhost:/mnt/nfsshare"
        fstype = "nfs4"

        name2 = "/mnt/nfs2"
        device2 = "localhost:/mnt/nfsshare"
        fstype2 = "nfs4"

        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        mock = MagicMock(
            side_effect=[
                "new",
                "present",
                "new",
                "change",
                "bad config",
                "salt",
                "present",
            ]
        )
        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        mock_ret = MagicMock(return_value={"retcode": 1})
        mock_mnt = MagicMock(
            return_value={name: {"device": device, "opts": [], "superopts": []}}
        )
        mock_read_cache = MagicMock(return_value={})
        mock_write_cache = MagicMock(return_value=True)
        mock_user = MagicMock(return_value={"uid": 510})
        mock_group = MagicMock(return_value={"gid": 100})
        mock_str = MagicMock(return_value="salt")
        mock_fstab_config = ["localhost:/mnt/nfsshare		/mnt/nfs1	nfs	defaults	0 0"]

        # Test no change for uid provided as a name #25293
        with patch.dict(mount.__grains__, {"os": "CentOS"}):
            with patch.dict(mount.__opts__, {"test": True}):
                with patch.dict(
                    mount.__salt__,
                    {
                        "mount.active": mock_mnt,
                        "mount.mount": mock_str,
                        "mount.umount": mock_f,
                        "mount.read_mount_cache": mock_read_cache,
                        "mount.write_mount_cache": mock_write_cache,
                        "user.info": mock_user,
                        "group.info": mock_group,
                    },
                ):
                    with patch.object(os.path, "exists", mock_t):
                        comt = "/mnt/nfs2 would be mounted"
                        ret.update({"name": name2, "result": None})
                        ret.update({"comment": comt, "changes": {}})
                        self.assertDictEqual(
                            mount.mounted(name2, device2, fstype2, opts=[]), ret
                        )

    def test__convert_to_fast_none(self):
        """
        Test the device name conversor
        """
        assert mount._convert_to("/dev/sda1", None) == "/dev/sda1"

    def test__convert_to_fast_device(self):
        """
        Test the device name conversor
        """
        assert mount._convert_to("/dev/sda1", "device") == "/dev/sda1"

    def test__convert_to_fast_token(self):
        """
        Test the device name conversor
        """
        assert mount._convert_to("LABEL=home", "label") == "LABEL=home"

    def test__convert_to_device_none(self):
        """
        Test the device name conversor
        """
        salt_mock = {
            "disk.blkid": MagicMock(return_value={}),
        }
        with patch.dict(mount.__salt__, salt_mock):
            assert mount._convert_to("/dev/sda1", "uuid") is None
            salt_mock["disk.blkid"].assert_called_with("/dev/sda1")

    def test__convert_to_device_token(self):
        """
        Test the device name conversor
        """
        uuid = "988c663d-74a2-432b-ba52-3eea34015f22"
        salt_mock = {
            "disk.blkid": MagicMock(return_value={"/dev/sda1": {"UUID": uuid}}),
        }
        with patch.dict(mount.__salt__, salt_mock):
            uuid = "UUID={}".format(uuid)
            assert mount._convert_to("/dev/sda1", "uuid") == uuid
            salt_mock["disk.blkid"].assert_called_with("/dev/sda1")

    def test__convert_to_token_device(self):
        """
        Test the device name conversor
        """
        uuid = "988c663d-74a2-432b-ba52-3eea34015f22"
        salt_mock = {
            "disk.blkid": MagicMock(return_value={"/dev/sda1": {"UUID": uuid}}),
        }
        with patch.dict(mount.__salt__, salt_mock):
            uuid = "UUID={}".format(uuid)
            assert mount._convert_to(uuid, "device") == "/dev/sda1"
            salt_mock["disk.blkid"].assert_called_with(token=uuid)

    def test_fstab_present_macos_test_present(self):
        """
        Test fstab_present
        """
        ret = {
            "name": "/dev/sda1",
            "result": None,
            "changes": {},
            "comment": ["/home entry is already in /etc/auto_salt."],
        }

        grains_mock = {"os": "MacOS"}
        opts_mock = {"test": True}
        salt_mock = {"mount.set_automaster": MagicMock(return_value="present")}
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_present("/dev/sda1", "/home", "ext2") == ret
            salt_mock["mount.set_automaster"].assert_called_with(
                name="/home",
                device="/dev/sda1",
                fstype="ext2",
                opts="noowners",
                config="/etc/auto_salt",
                test=True,
                not_change=False,
            )

    def test_fstab_present_aix_test_present(self):
        """
        Test fstab_present
        """
        ret = {
            "name": "/dev/sda1",
            "result": None,
            "changes": {},
            "comment": ["/home entry is already in /etc/filesystems."],
        }

        grains_mock = {"os": "AIX"}
        opts_mock = {"test": True}
        salt_mock = {"mount.set_filesystems": MagicMock(return_value="present")}
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_present("/dev/sda1", "/home", "ext2") == ret
            salt_mock["mount.set_filesystems"].assert_called_with(
                name="/home",
                device="/dev/sda1",
                fstype="ext2",
                mount=True,
                opts="",
                config="/etc/filesystems",
                test=True,
                match_on="auto",
                not_change=False,
            )

    def test_fstab_present_test_present(self):
        """
        Test fstab_present
        """
        ret = {
            "name": "/dev/sda1",
            "result": None,
            "changes": {},
            "comment": ["/home entry is already in /etc/fstab."],
        }

        grains_mock = {"os": "Linux"}
        opts_mock = {"test": True}
        salt_mock = {"mount.set_fstab": MagicMock(return_value="present")}
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_present("/dev/sda1", "/home", "ext2") == ret
            salt_mock["mount.set_fstab"].assert_called_with(
                name="/home",
                device="/dev/sda1",
                fstype="ext2",
                opts="defaults",
                dump=0,
                pass_num=0,
                config="/etc/fstab",
                test=True,
                match_on="auto",
                not_change=False,
            )

    def test_fstab_present_test_new(self):
        """
        Test fstab_present
        """
        ret = {
            "name": "/dev/sda1",
            "result": None,
            "changes": {},
            "comment": [
                "/home entry will be written in /etc/fstab.",
                "Will mount /dev/sda1 on /home",
            ],
        }

        grains_mock = {"os": "Linux"}
        opts_mock = {"test": True}
        salt_mock = {"mount.set_fstab": MagicMock(return_value="new")}
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_present("/dev/sda1", "/home", "ext2") == ret
            salt_mock["mount.set_fstab"].assert_called_with(
                name="/home",
                device="/dev/sda1",
                fstype="ext2",
                opts="defaults",
                dump=0,
                pass_num=0,
                config="/etc/fstab",
                test=True,
                match_on="auto",
                not_change=False,
            )

    def test_fstab_present_test_change(self):
        """
        Test fstab_present
        """
        ret = {
            "name": "/dev/sda1",
            "result": None,
            "changes": {},
            "comment": ["/home entry will be updated in /etc/fstab."],
        }

        grains_mock = {"os": "Linux"}
        opts_mock = {"test": True}
        salt_mock = {"mount.set_fstab": MagicMock(return_value="change")}
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_present("/dev/sda1", "/home", "ext2") == ret
            salt_mock["mount.set_fstab"].assert_called_with(
                name="/home",
                device="/dev/sda1",
                fstype="ext2",
                opts="defaults",
                dump=0,
                pass_num=0,
                config="/etc/fstab",
                test=True,
                match_on="auto",
                not_change=False,
            )

    def test_fstab_present_test_error(self):
        """
        Test fstab_present
        """
        ret = {
            "name": "/dev/sda1",
            "result": False,
            "changes": {},
            "comment": ["/home entry cannot be created in /etc/fstab: error."],
        }

        grains_mock = {"os": "Linux"}
        opts_mock = {"test": True}
        salt_mock = {"mount.set_fstab": MagicMock(return_value="error")}
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_present("/dev/sda1", "/home", "ext2") == ret
            salt_mock["mount.set_fstab"].assert_called_with(
                name="/home",
                device="/dev/sda1",
                fstype="ext2",
                opts="defaults",
                dump=0,
                pass_num=0,
                config="/etc/fstab",
                test=True,
                match_on="auto",
                not_change=False,
            )

    def test_fstab_present_macos_present(self):
        """
        Test fstab_present
        """
        ret = {
            "name": "/dev/sda1",
            "result": True,
            "changes": {},
            "comment": ["/home entry was already in /etc/auto_salt."],
        }

        grains_mock = {"os": "MacOS"}
        opts_mock = {"test": False}
        salt_mock = {"mount.set_automaster": MagicMock(return_value="present")}
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_present("/dev/sda1", "/home", "ext2") == ret
            salt_mock["mount.set_automaster"].assert_called_with(
                name="/home",
                device="/dev/sda1",
                fstype="ext2",
                opts="noowners",
                config="/etc/auto_salt",
                not_change=False,
            )

    def test_fstab_present_aix_present(self):
        """
        Test fstab_present
        """
        ret = {
            "name": "/dev/sda1",
            "result": True,
            "changes": {},
            "comment": ["/home entry was already in /etc/filesystems."],
        }

        grains_mock = {"os": "AIX"}
        opts_mock = {"test": False}
        salt_mock = {"mount.set_filesystems": MagicMock(return_value="present")}
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_present("/dev/sda1", "/home", "ext2") == ret
            salt_mock["mount.set_filesystems"].assert_called_with(
                name="/home",
                device="/dev/sda1",
                fstype="ext2",
                mount=True,
                opts="",
                config="/etc/filesystems",
                match_on="auto",
                not_change=False,
            )

    def test_fstab_present_present(self):
        """
        Test fstab_present
        """
        ret = {
            "name": "/dev/sda1",
            "result": True,
            "changes": {},
            "comment": ["/home entry was already in /etc/fstab."],
        }

        grains_mock = {"os": "Linux"}
        opts_mock = {"test": False}
        salt_mock = {"mount.set_fstab": MagicMock(return_value="present")}
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_present("/dev/sda1", "/home", "ext2") == ret
            salt_mock["mount.set_fstab"].assert_called_with(
                name="/home",
                device="/dev/sda1",
                fstype="ext2",
                opts="defaults",
                dump=0,
                pass_num=0,
                config="/etc/fstab",
                match_on="auto",
                not_change=False,
            )

    def test_fstab_present_new(self):
        """
        Test fstab_present
        """
        ret = {
            "name": "/dev/sda1",
            "result": True,
            "changes": {"persist": "new"},
            "comment": [
                "/home entry added in /etc/fstab.",
                "Mounted /dev/sda1 on /home",
            ],
        }

        grains_mock = {"os": "Linux"}
        opts_mock = {"test": False}
        set_fstab_mock = {"mount.set_fstab": MagicMock(return_value="new")}
        mount_mock = {"mount.mount": MagicMock(return_value=True)}
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, mount_mock), patch.dict(
            mount.__salt__, set_fstab_mock
        ):
            assert mount.fstab_present("/dev/sda1", "/home", "ext2") == ret
            set_fstab_mock["mount.set_fstab"].assert_called_with(
                name="/home",
                device="/dev/sda1",
                fstype="ext2",
                opts="defaults",
                dump=0,
                pass_num=0,
                config="/etc/fstab",
                match_on="auto",
                not_change=False,
            )

    def test_fstab_present_new_no_mount(self):
        """
        Test fstab_present with mount=false option
        """
        ret = {
            "name": "/dev/sda1",
            "result": True,
            "changes": {"persist": "new"},
            "comment": ["/home entry added in /etc/fstab."],
        }

        grains_mock = {"os": "Linux"}
        opts_mock = {"test": False}
        salt_mock = {"mount.set_fstab": MagicMock(return_value="new")}
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_present("/dev/sda1", "/home", "ext2", mount=False) == ret
            salt_mock["mount.set_fstab"].assert_called_with(
                name="/home",
                device="/dev/sda1",
                fstype="ext2",
                opts="defaults",
                dump=0,
                pass_num=0,
                config="/etc/fstab",
                match_on="auto",
                not_change=False,
            )

    def test_fstab_present_change(self):
        """
        Test fstab_present
        """
        ret = {
            "name": "/dev/sda1",
            "result": True,
            "changes": {"persist": "change"},
            "comment": ["/home entry updated in /etc/fstab."],
        }

        grains_mock = {"os": "Linux"}
        opts_mock = {"test": False}
        salt_mock = {"mount.set_fstab": MagicMock(return_value="change")}
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_present("/dev/sda1", "/home", "ext2") == ret
            salt_mock["mount.set_fstab"].assert_called_with(
                name="/home",
                device="/dev/sda1",
                fstype="ext2",
                opts="defaults",
                dump=0,
                pass_num=0,
                config="/etc/fstab",
                match_on="auto",
                not_change=False,
            )

    def test_fstab_present_fail(self):
        """
        Test fstab_present
        """
        ret = {
            "name": "/dev/sda1",
            "result": False,
            "changes": {},
            "comment": ["/home entry cannot be changed in /etc/fstab: error."],
        }

        grains_mock = {"os": "Linux"}
        opts_mock = {"test": False}
        salt_mock = {"mount.set_fstab": MagicMock(return_value="error")}
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_present("/dev/sda1", "/home", "ext2") == ret
            salt_mock["mount.set_fstab"].assert_called_with(
                name="/home",
                device="/dev/sda1",
                fstype="ext2",
                opts="defaults",
                dump=0,
                pass_num=0,
                config="/etc/fstab",
                match_on="auto",
                not_change=False,
            )

    def test_fstab_absent_macos_test_absent(self):
        """
        Test fstab_absent
        """
        ret = {
            "name": "/dev/sda1",
            "result": None,
            "changes": {},
            "comment": ["/home entry is already missing in /etc/auto_salt."],
        }

        grains_mock = {"os": "MacOS"}
        opts_mock = {"test": True}
        salt_mock = {"mount.automaster": MagicMock(return_value={})}
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_absent("/dev/sda1", "/home") == ret
            salt_mock["mount.automaster"].assert_called_with("/etc/auto_salt")

    def test_fstab_absent_aix_test_absent(self):
        """
        Test fstab_absent
        """
        ret = {
            "name": "/dev/sda1",
            "result": None,
            "changes": {},
            "comment": ["/home entry is already missing in /etc/filesystems."],
        }

        grains_mock = {"os": "AIX"}
        opts_mock = {"test": True}
        salt_mock = {"mount.filesystems": MagicMock(return_value={})}
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_absent("/dev/sda1", "/home") == ret
            salt_mock["mount.filesystems"].assert_called_with("/etc/filesystems")

    def test_fstab_absent_test_absent(self):
        """
        Test fstab_absent
        """
        ret = {
            "name": "/dev/sda1",
            "result": None,
            "changes": {},
            "comment": ["/home entry is already missing in /etc/fstab."],
        }

        grains_mock = {"os": "Linux"}
        opts_mock = {"test": True}
        salt_mock = {"mount.fstab": MagicMock(return_value={})}
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_absent("/dev/sda1", "/home") == ret
            salt_mock["mount.fstab"].assert_called_with("/etc/fstab")

    def test_fstab_absent_test_present(self):
        """
        Test fstab_absent
        """
        ret = {
            "name": "/dev/sda1",
            "result": None,
            "changes": {},
            "comment": ["/home entry will be removed from /etc/fstab."],
        }

        grains_mock = {"os": "Linux"}
        opts_mock = {"test": True}
        salt_mock = {"mount.fstab": MagicMock(return_value={"/home": {}})}
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_absent("/dev/sda1", "/home") == ret
            salt_mock["mount.fstab"].assert_called_with("/etc/fstab")

    def test_fstab_absent_macos_present(self):
        """
        Test fstab_absent
        """
        ret = {
            "name": "/dev/sda1",
            "result": True,
            "changes": {"persist": "removed"},
            "comment": ["/home entry removed from /etc/auto_salt."],
        }

        grains_mock = {"os": "MacOS"}
        opts_mock = {"test": False}
        salt_mock = {
            "mount.automaster": MagicMock(return_value={"/home": {}}),
            "mount.rm_automaster": MagicMock(return_value=True),
        }
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_absent("/dev/sda1", "/home") == ret
            salt_mock["mount.automaster"].assert_called_with("/etc/auto_salt")
            salt_mock["mount.rm_automaster"].assert_called_with(
                name="/home", device="/dev/sda1", config="/etc/auto_salt"
            )

    def test_fstab_absent_aix_present(self):
        """
        Test fstab_absent
        """
        ret = {
            "name": "/dev/sda1",
            "result": True,
            "changes": {"persist": "removed"},
            "comment": ["/home entry removed from /etc/filesystems."],
        }

        grains_mock = {"os": "AIX"}
        opts_mock = {"test": False}
        salt_mock = {
            "mount.filesystems": MagicMock(return_value={"/home": {}}),
            "mount.rm_filesystems": MagicMock(return_value=True),
        }
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_absent("/dev/sda1", "/home") == ret
            salt_mock["mount.filesystems"].assert_called_with("/etc/filesystems")
            salt_mock["mount.rm_filesystems"].assert_called_with(
                name="/home", device="/dev/sda1", config="/etc/filesystems"
            )

    def test_fstab_absent_present(self):
        """
        Test fstab_absent
        """
        ret = {
            "name": "/dev/sda1",
            "result": True,
            "changes": {"persist": "removed"},
            "comment": ["/home entry removed from /etc/fstab."],
        }

        grains_mock = {"os": "Linux"}
        opts_mock = {"test": False}
        salt_mock = {
            "mount.fstab": MagicMock(return_value={"/home": {}}),
            "mount.rm_fstab": MagicMock(return_value=True),
        }
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_absent("/dev/sda1", "/home") == ret
            salt_mock["mount.fstab"].assert_called_with("/etc/fstab")
            salt_mock["mount.rm_fstab"].assert_called_with(
                name="/home", device="/dev/sda1", config="/etc/fstab"
            )

    def test_fstab_absent_absent(self):
        """
        Test fstab_absent
        """
        ret = {
            "name": "/dev/sda1",
            "result": True,
            "changes": {},
            "comment": ["/home entry is already missing in /etc/fstab."],
        }

        grains_mock = {"os": "Linux"}
        opts_mock = {"test": False}
        salt_mock = {"mount.fstab": MagicMock(return_value={})}
        with patch.dict(mount.__grains__, grains_mock), patch.dict(
            mount.__opts__, opts_mock
        ), patch.dict(mount.__salt__, salt_mock):
            assert mount.fstab_absent("/dev/sda1", "/home") == ret
            salt_mock["mount.fstab"].assert_called_with("/etc/fstab")
