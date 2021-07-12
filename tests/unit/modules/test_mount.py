"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

import os
import textwrap

import salt.modules.mount as mount
import salt.utils.files
import salt.utils.path
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, mock_open, patch
from tests.support.unit import TestCase

MOCK_SHELL_FILE = "A B C D F G\n"


class MountTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.mount
    """

    def setup_loader_modules(self):
        return {mount: {}}

    def test_active(self):
        """
        List the active mounts.
        """
        with patch.dict(mount.__grains__, {"os": "FreeBSD", "kernel": "FreeBSD"}):
            # uid=user1 tests the improbable case where a OS returns a name
            # instead of a numeric id, for #25293
            mock = MagicMock(return_value="A B C D,E,F,uid=user1,gid=grp1")
            mock_user = MagicMock(return_value={"uid": "100"})
            mock_group = MagicMock(return_value={"gid": "100"})
            with patch.dict(
                mount.__salt__,
                {
                    "cmd.run_stdout": mock,
                    "user.info": mock_user,
                    "group.info": mock_group,
                },
            ):
                self.assertEqual(
                    mount.active(),
                    {
                        "B": {
                            "device": "A",
                            "opts": ["D", "E", "F", "uid=100", "gid=100"],
                            "fstype": "C",
                        }
                    },
                )

        with patch.dict(mount.__grains__, {"os": "Solaris", "kernel": "SunOS"}):
            mock = MagicMock(return_value="A * B * C D/E/F")
            with patch.dict(mount.__salt__, {"cmd.run_stdout": mock}):
                self.assertEqual(
                    mount.active(),
                    {"B": {"device": "A", "opts": ["D", "E", "F"], "fstype": "C"}},
                )

        with patch.dict(mount.__grains__, {"os": "AIX", "kernel": "AIX"}):
            mock = MagicMock(return_value="A * B * C D/E/F")
            with patch.dict(mount.__salt__, {"cmd.run_stdout": mock}):
                self.assertEqual(
                    mount.active(), {"B": {"node": "A", "device": "*", "fstype": "*"}}
                )

        with patch.dict(mount.__grains__, {"os": "OpenBSD", "kernel": "OpenBSD"}):
            mock = MagicMock(return_value={})
            with patch.object(mount, "_active_mounts_openbsd", mock):
                self.assertEqual(mount.active(), {})

        with patch.dict(mount.__grains__, {"os": "MacOS", "kernel": "Darwin"}):
            mock = MagicMock(return_value={})
            with patch.object(mount, "_active_mounts_darwin", mock):
                self.assertEqual(mount.active(), {})

        with patch.dict(mount.__grains__, {"os": "MacOS", "kernel": "Darwin"}):
            mock = MagicMock(return_value={})
            with patch.object(mount, "_active_mountinfo", mock):
                with patch.object(mount, "_active_mounts_darwin", mock):
                    self.assertEqual(mount.active(extended=True), {})

        with patch.dict(mount.__grains__, {"os": "AIX", "kernel": "AIX"}):
            mock = MagicMock(return_value={})
            with patch.object(mount, "_active_mounts_aix", mock):
                self.assertEqual(mount.active(), {})

    def test_fstab(self):
        """
        List the content of the fstab
        """
        mock = MagicMock(return_value=False)
        with patch.object(os.path, "isfile", mock):
            self.assertEqual(mount.fstab(), {})

        file_data = "\n".join(["#", "A B C D,E,F G H"])
        mock = MagicMock(return_value=True)
        with patch.dict(mount.__grains__, {"kernel": ""}), patch.object(
            os.path, "isfile", mock
        ), patch("salt.utils.files.fopen", mock_open(read_data=file_data)):
            fstab = mount.fstab()
            assert fstab == {
                "B": {
                    "device": "A",
                    "dump": "G",
                    "fstype": "C",
                    "opts": ["D", "E", "F"],
                    "pass": "H",
                }
            }, fstab

    def test_vfstab(self):
        """
        List the content of the vfstab
        """
        mock = MagicMock(return_value=False)
        with patch.object(os.path, "isfile", mock):
            self.assertEqual(mount.vfstab(), {})

        file_data = textwrap.dedent(
            """\
            #
            swap        -   /tmp                tmpfs    -   yes    size=2048m
            """
        )
        mock = MagicMock(return_value=True)
        with patch.dict(mount.__grains__, {"kernel": "SunOS"}), patch.object(
            os.path, "isfile", mock
        ), patch("salt.utils.files.fopen", mock_open(read_data=file_data)):
            vfstab = mount.vfstab()
            assert vfstab == {
                "/tmp": {
                    "device": "swap",
                    "device_fsck": "-",
                    "fstype": "tmpfs",
                    "mount_at_boot": "yes",
                    "opts": ["size=2048m"],
                    "pass_fsck": "-",
                }
            }, vfstab

    def test_filesystems(self):
        """
        List the content of the filesystems
        """
        file_data = textwrap.dedent(
            """\
            #

            """
        )
        mock = MagicMock(return_value=True)
        with patch.dict(mount.__grains__, {"os": "AIX", "kernel": "AIX"}), patch.object(
            os.path, "isfile", mock
        ), patch("salt.utils.files.fopen", mock_open(read_data=file_data)):
            self.assertEqual(mount.filesystems(), {})

        file_data = textwrap.dedent(
            """\
            #
            /home:
                    dev             = /dev/hd1
                    vfs             = jfs2
                    log             = /dev/hd8
                    mount           = true
                    check           = true
                    vol             = /home
                    free            = false
                    quota           = no

            """
        )
        mock = MagicMock(return_value=True)
        with patch.dict(mount.__grains__, {"os": "AIX", "kernel": "AIX"}), patch.object(
            os.path, "isfile", mock
        ), patch("salt.utils.files.fopen", mock_open(read_data=file_data)):
            fsyst = mount.filesystems()
            test_fsyst = {
                "/home": {
                    "dev": "/dev/hd1",
                    "vfs": "jfs2",
                    "log": "/dev/hd8",
                    "mount": "true",
                    "check": "true",
                    "vol": "/home",
                    "free": "false",
                    "quota": "no",
                }
            }
            self.assertEqual(test_fsyst, fsyst)

    def test_rm_fstab(self):
        """
        Remove the mount point from the fstab
        """
        mock_fstab = MagicMock(return_value={})
        with patch.dict(mount.__grains__, {"kernel": ""}):
            with patch.object(mount, "fstab", mock_fstab):
                with patch("salt.utils.files.fopen", mock_open()):
                    self.assertTrue(mount.rm_fstab("name", "device"))

    def test_set_fstab(self):
        """
        Tests to verify that this mount is represented in the fstab,
        change the mount to match the data passed, or add the mount
        if it is not present.
        """
        mock = MagicMock(return_value=False)
        with patch.object(os.path, "isfile", mock):
            self.assertRaises(CommandExecutionError, mount.set_fstab, "A", "B", "C")

        mock = MagicMock(return_value=True)
        mock_read = MagicMock(side_effect=OSError)
        with patch.object(os.path, "isfile", mock):
            with patch.object(salt.utils.files, "fopen", mock_read):
                self.assertRaises(CommandExecutionError, mount.set_fstab, "A", "B", "C")

        mock = MagicMock(return_value=True)
        with patch.object(os.path, "isfile", mock):
            with patch("salt.utils.files.fopen", mock_open(read_data=MOCK_SHELL_FILE)):
                self.assertEqual(mount.set_fstab("A", "B", "C"), "new")

        mock = MagicMock(return_value=True)
        with patch.object(os.path, "isfile", mock):
            with patch("salt.utils.files.fopen", mock_open(read_data=MOCK_SHELL_FILE)):
                self.assertEqual(
                    mount.set_fstab("B", "A", "C", "D", "F", "G"), "present"
                )

        mock = MagicMock(return_value=True)
        with patch.object(os.path, "isfile", mock):
            with patch("salt.utils.files.fopen", mock_open(read_data=MOCK_SHELL_FILE)):
                self.assertEqual(
                    mount.set_fstab("B", "A", "C", not_change=True), "present"
                )

    def test_rm_automaster(self):
        """
        Remove the mount point from the auto_master
        """
        mock = MagicMock(return_value={})
        with patch.object(mount, "automaster", mock):
            self.assertTrue(mount.rm_automaster("name", "device"))

        mock = MagicMock(return_value={"name": "name"})
        with patch.object(mount, "fstab", mock):
            self.assertTrue(mount.rm_automaster("name", "device"))

    def test_set_automaster(self):
        """
        Verify that this mount is represented in the auto_salt, change the mount
        to match the data passed, or add the mount if it is not present.
        """
        mock = MagicMock(return_value=True)
        with patch.object(os.path, "isfile", mock):
            self.assertRaises(
                CommandExecutionError, mount.set_automaster, "A", "B", "C"
            )

        mock = MagicMock(return_value=True)
        mock_read = MagicMock(side_effect=OSError)
        with patch.object(os.path, "isfile", mock):
            with patch.object(salt.utils.files, "fopen", mock_read):
                self.assertRaises(
                    CommandExecutionError, mount.set_automaster, "A", "B", "C"
                )

        mock = MagicMock(return_value=True)
        with patch.object(os.path, "isfile", mock):
            with patch("salt.utils.files.fopen", mock_open(read_data=MOCK_SHELL_FILE)):
                self.assertEqual(mount.set_automaster("A", "B", "C"), "new")

        mock = MagicMock(return_value=True)
        with patch.object(os.path, "isfile", mock):
            with patch(
                "salt.utils.files.fopen", mock_open(read_data="/..A -fstype=C,D C:B")
            ):
                self.assertEqual(mount.set_automaster("A", "B", "C", "D"), "present")

        mock = MagicMock(return_value=True)
        with patch.object(os.path, "isfile", mock):
            with patch(
                "salt.utils.files.fopen", mock_open(read_data="/..A -fstype=XX C:B")
            ):
                self.assertEqual(
                    mount.set_automaster("A", "B", "C", "D", not_change=True), "present"
                )

    def test_automaster(self):
        """
        Test the list the contents of the fstab
        """
        self.assertDictEqual(mount.automaster(), {})

    def test_rm_filesystems(self):
        """
        Remove the mount point from the filesystems
        """
        file_data = textwrap.dedent(
            """\
            #

            """
        )
        mock = MagicMock(return_value=True)
        with patch.dict(mount.__grains__, {"os": "AIX", "kernel": "AIX"}), patch.object(
            os.path, "isfile", mock
        ), patch("salt.utils.files.fopen", mock_open(read_data=file_data)):
            self.assertFalse(mount.rm_filesystems("name", "device"))

        file_data = textwrap.dedent(
            """\
            #
            /name:
                    dev             = device
                    vol             = /name

            """
        )

        mock = MagicMock(return_value=True)
        mock_fsyst = MagicMock(return_value=True)
        with patch.dict(mount.__grains__, {"os": "AIX", "kernel": "AIX"}), patch.object(
            os.path, "isfile", mock
        ), patch("salt.utils.files.fopen", mock_open(read_data=file_data)):
            self.assertTrue(mount.rm_filesystems("/name", "device"))

    def test_set_filesystems(self):
        """
        Tests to verify that this mount is represented in the filesystems,
        change the mount to match the data passed, or add the mount
        if it is not present.
        """
        mock = MagicMock(return_value=False)
        with patch.dict(mount.__grains__, {"os": "AIX", "kernel": "AIX"}):
            with patch.object(os.path, "isfile", mock):
                self.assertRaises(
                    CommandExecutionError, mount.set_filesystems, "A", "B", "C"
                )

            mock_read = MagicMock(side_effect=OSError)
            with patch.object(os.path, "isfile", mock):
                with patch.object(salt.utils.files, "fopen", mock_read):
                    self.assertRaises(
                        CommandExecutionError, mount.set_filesystems, "A", "B", "C"
                    )

    def test_mount(self):
        """
        Mount a device
        """
        with patch.dict(mount.__grains__, {"os": "MacOS"}):
            mock = MagicMock(return_value=True)
            with patch.object(os.path, "exists", mock):
                mock = MagicMock(return_value=None)
                with patch.dict(mount.__salt__, {"file.mkdir": None}):
                    mock = MagicMock(return_value={"retcode": True, "stderr": True})
                    with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                        self.assertTrue(mount.mount("name", "device"))
                        mock.assert_called_with(
                            "mount  device name ", python_shell=False, runas=None
                        )

                    with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                        self.assertTrue(mount.mount("name", "device", fstype="fstype"))
                        mock.assert_called_with(
                            "mount  -t fstype device name ",
                            python_shell=False,
                            runas=None,
                        )

                    mock = MagicMock(return_value={"retcode": False, "stderr": False})
                    with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                        self.assertTrue(mount.mount("name", "device"))

        with patch.dict(mount.__grains__, {"os": "AIX"}):
            mock = MagicMock(return_value=True)
            with patch.object(os.path, "exists", mock):
                mock = MagicMock(return_value=None)
                with patch.dict(mount.__salt__, {"file.mkdir": None}):
                    mock = MagicMock(return_value={"retcode": True, "stderr": True})
                    with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                        self.assertTrue(mount.mount("name", "device"))
                        mock.assert_called_with(
                            "mount  device name ", python_shell=False, runas=None
                        )

                    with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                        self.assertTrue(mount.mount("name", "device", fstype="fstype"))
                        mock.assert_called_with(
                            "mount  -v fstype device name ",
                            python_shell=False,
                            runas=None,
                        )

                    mock = MagicMock(return_value={"retcode": False, "stderr": False})
                    with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                        self.assertTrue(mount.mount("name", "device"))

        with patch.dict(mount.__grains__, {"os": "Linux"}):
            mock = MagicMock(return_value=True)
            with patch.object(os.path, "exists", mock):
                mock = MagicMock(return_value=None)
                with patch.dict(mount.__salt__, {"file.mkdir": None}):
                    mock = MagicMock(return_value={"retcode": True, "stderr": True})
                    with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                        self.assertTrue(mount.mount("name", "device"))
                        mock.assert_called_with(
                            "mount -o defaults device name ",
                            python_shell=False,
                            runas=None,
                        )

                    with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                        self.assertTrue(mount.mount("name", "device", fstype="fstype"))
                        mock.assert_called_with(
                            "mount -o defaults -t fstype device name ",
                            python_shell=False,
                            runas=None,
                        )

                    mock = MagicMock(return_value={"retcode": False, "stderr": False})
                    with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                        self.assertTrue(mount.mount("name", "device"))

    def test_remount_non_mounted(self):
        """
        Attempt to remount a device, if the device is not already mounted, mount
        is called
        """
        with patch.dict(mount.__grains__, {"os": "MacOS"}):
            mock = MagicMock(return_value=[])
            with patch.object(mount, "active", mock):
                mock = MagicMock(return_value=True)
                with patch.object(mount, "mount", mock):
                    self.assertTrue(mount.remount("name", "device"))

        with patch.dict(mount.__grains__, {"os": "AIX"}):
            mock = MagicMock(return_value=[])
            with patch.object(mount, "active", mock):
                mock = MagicMock(return_value=True)
                with patch.object(mount, "mount", mock):
                    self.assertTrue(mount.remount("name", "device"))

        with patch.dict(mount.__grains__, {"os": "Linux"}):
            mock = MagicMock(return_value=[])
            with patch.object(mount, "active", mock):
                mock = MagicMock(return_value=True)
                with patch.object(mount, "mount", mock):
                    self.assertTrue(mount.remount("name", "device"))

    def test_remount_already_mounted_no_fstype(self):
        """
        Attempt to remount a device already mounted that do not provides
        fstype
        """
        with patch.dict(mount.__grains__, {"os": "MacOS"}):
            mock = MagicMock(return_value=["name"])
            with patch.object(mount, "active", mock):
                mock = MagicMock(return_value={"retcode": 0})
                with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                    self.assertTrue(mount.remount("name", "device"))
                    mock.assert_called_with(
                        "mount -u -o noowners device name ",
                        python_shell=False,
                        runas=None,
                    )

        with patch.dict(mount.__grains__, {"os": "AIX"}):
            mock = MagicMock(return_value=["name"])
            with patch.object(mount, "active", mock):
                mock = MagicMock(return_value={"retcode": 0})
                with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                    self.assertTrue(mount.remount("name", "device"))
                    mock.assert_called_with(
                        "mount -o remount device name ", python_shell=False, runas=None
                    )

        with patch.dict(mount.__grains__, {"os": "Linux"}):
            mock = MagicMock(return_value=["name"])
            with patch.object(mount, "active", mock):
                mock = MagicMock(return_value={"retcode": 0})
                with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                    self.assertTrue(mount.remount("name", "device"))
                    mock.assert_called_with(
                        "mount -o defaults,remount device name ",
                        python_shell=False,
                        runas=None,
                    )

    def test_remount_already_mounted_with_fstype(self):
        """
        Attempt to remount a device already mounted that do not provides
        fstype
        """
        with patch.dict(mount.__grains__, {"os": "MacOS"}):
            mock = MagicMock(return_value=["name"])
            with patch.object(mount, "active", mock):
                mock = MagicMock(return_value={"retcode": 0})
                with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                    self.assertTrue(mount.remount("name", "device", fstype="type"))
                    mock.assert_called_with(
                        "mount -u -o noowners -t type device name ",
                        python_shell=False,
                        runas=None,
                    )

        with patch.dict(mount.__grains__, {"os": "AIX"}):
            mock = MagicMock(return_value=["name"])
            with patch.object(mount, "active", mock):
                mock = MagicMock(return_value={"retcode": 0})
                with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                    self.assertTrue(mount.remount("name", "device", fstype="type"))
                    mock.assert_called_with(
                        "mount -o remount -v type device name ",
                        python_shell=False,
                        runas=None,
                    )

        with patch.dict(mount.__grains__, {"os": "Linux"}):
            mock = MagicMock(return_value=["name"])
            with patch.object(mount, "active", mock):
                mock = MagicMock(return_value={"retcode": 0})
                with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                    self.assertTrue(mount.remount("name", "device", fstype="type"))
                    mock.assert_called_with(
                        "mount -o defaults,remount -t type device name ",
                        python_shell=False,
                        runas=None,
                    )

    def test_umount(self):
        """
        Attempt to unmount a device by specifying the directory it is
        mounted on
        """
        mock = MagicMock(return_value={})
        with patch.object(mount, "active", mock):
            self.assertEqual(
                mount.umount("name"), "name does not have anything mounted"
            )

        mock = MagicMock(return_value={"name": "name"})
        with patch.object(mount, "active", mock):
            mock = MagicMock(return_value={"retcode": True, "stderr": True})
            with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                self.assertTrue(mount.umount("name"))

            mock = MagicMock(return_value={"retcode": False})
            with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                self.assertTrue(mount.umount("name"))

        # Test unmounting with guestfs util
        mock = MagicMock()
        with patch.dict(mount.__salt__, {"guestfs.umount": mock}):
            mount.umount("/mountpoint", device="/path/to/my.qcow", util="guestfs")
            mock.assert_called_once_with("/mountpoint", disk="/path/to/my.qcow")

    def test_is_fuse_exec(self):
        """
        Returns true if the command passed is a fuse mountable application
        """
        with patch.object(salt.utils.path, "which", return_value=None):
            self.assertFalse(mount.is_fuse_exec("cmd"))

        def _ldd_side_effect(cmd, *args, **kwargs):
            """
            Neither of these are full ldd output, but what is_fuse_exec is
            looking for is 'libfuse' in the ldd output, so these examples
            should be sufficient enough to test both the True and False cases.
            """
            return {
                "ldd cmd1": textwrap.dedent(
                    """\
                    linux-vdso.so.1 (0x00007ffeaf5fb000)
                    libfuse3.so.3 => /usr/lib/libfuse3.so.3 (0x00007f91e66ac000)
                    """
                ),
                "ldd cmd2": textwrap.dedent(
                    """\
                    linux-vdso.so.1 (0x00007ffeaf5fb000)
                    """
                ),
            }[cmd]

        which_mock = MagicMock(side_effect=lambda x: x)
        ldd_mock = MagicMock(side_effect=_ldd_side_effect)
        with patch.object(salt.utils.path, "which", which_mock):
            with patch.dict(mount.__salt__, {"cmd.run": _ldd_side_effect}):
                self.assertTrue(mount.is_fuse_exec("cmd1"))
                self.assertFalse(mount.is_fuse_exec("cmd2"))

    def test_swaps(self):
        """
        Return a dict containing information on active swap
        """
        file_data = textwrap.dedent(
            """\
            Filename Type Size Used Priority
            /dev/sda1 partition 31249404 4100 -1
            """
        )
        with patch.dict(mount.__grains__, {"os": "", "kernel": ""}):
            with patch("salt.utils.files.fopen", mock_open(read_data=file_data)):
                swaps = mount.swaps()
                assert swaps == {
                    "/dev/sda1": {
                        "priority": "-1",
                        "size": "31249404",
                        "type": "partition",
                        "used": "4100",
                    }
                }, swaps

        file_data = textwrap.dedent(
            """\
            Device Size Used Unknown Unknown Priority
            /dev/sda1 31249404 4100 unknown unknown -1
            """
        )
        mock = MagicMock(return_value=file_data)
        with patch.dict(
            mount.__grains__, {"os": "OpenBSD", "kernel": "OpenBSD"}
        ), patch.dict(mount.__salt__, {"cmd.run_stdout": mock}):
            swaps = mount.swaps()
            assert swaps == {
                "/dev/sda1": {
                    "priority": "-1",
                    "size": "31249404",
                    "type": "partition",
                    "used": "4100",
                }
            }, swaps

        file_data = textwrap.dedent(
            """\
            device              maj,min        total       free
            /dev/hd6              10,  2     11776MB     11765MB
            """
        )
        mock = MagicMock(return_value=file_data)
        with patch.dict(mount.__grains__, {"os": "AIX", "kernel": "AIX"}), patch.dict(
            mount.__salt__, {"cmd.run_stdout": mock}
        ):
            swaps = mount.swaps()
            assert swaps == {
                "/dev/hd6": {
                    "priority": "-",
                    "size": 12058624,
                    "type": "device",
                    "used": 11264,
                }
            }, swaps

    def test_swapon(self):
        """
        Activate a swap disk
        """
        mock = MagicMock(return_value={"name": "name"})
        with patch.dict(mount.__grains__, {"kernel": ""}):
            with patch.object(mount, "swaps", mock):
                self.assertEqual(mount.swapon("name"), {"stats": "name", "new": False})

        mock = MagicMock(return_value={})
        with patch.dict(mount.__grains__, {"kernel": ""}):
            with patch.object(mount, "swaps", mock):
                mock = MagicMock(return_value=None)
                with patch.dict(mount.__salt__, {"cmd.run": mock}):
                    self.assertEqual(mount.swapon("name", False), {})

        mock = MagicMock(side_effect=[{}, {"name": "name"}])
        with patch.dict(mount.__grains__, {"kernel": ""}):
            with patch.object(mount, "swaps", mock):
                mock = MagicMock(return_value=None)
                with patch.dict(mount.__salt__, {"cmd.run": mock}):
                    self.assertEqual(
                        mount.swapon("name"), {"stats": "name", "new": True}
                    )
        ## effects of AIX
        mock = MagicMock(return_value={"name": "name"})
        with patch.dict(mount.__grains__, {"kernel": "AIX"}):
            with patch.object(mount, "swaps", mock):
                self.assertEqual(mount.swapon("name"), {"stats": "name", "new": False})

        mock = MagicMock(return_value={})
        with patch.dict(mount.__grains__, {"kernel": "AIX"}):
            with patch.object(mount, "swaps", mock):
                mock = MagicMock(return_value=None)
                with patch.dict(mount.__salt__, {"cmd.run": mock}):
                    self.assertEqual(mount.swapon("name", False), {})

        mock = MagicMock(side_effect=[{}, {"name": "name"}])
        with patch.dict(mount.__grains__, {"kernel": "AIX"}):
            with patch.object(mount, "swaps", mock):
                mock = MagicMock(return_value=None)
                with patch.dict(mount.__salt__, {"cmd.run": mock}):
                    self.assertEqual(
                        mount.swapon("name"), {"stats": "name", "new": True}
                    )

    def test_swapoff(self):
        """
        Deactivate a named swap mount
        """
        mock = MagicMock(return_value={})
        with patch.dict(mount.__grains__, {"kernel": ""}):
            with patch.object(mount, "swaps", mock):
                self.assertEqual(mount.swapoff("name"), None)

        mock = MagicMock(return_value={"name": "name"})
        with patch.dict(mount.__grains__, {"kernel": ""}):
            with patch.object(mount, "swaps", mock):
                with patch.dict(mount.__grains__, {"os": "test"}):
                    mock = MagicMock(return_value=None)
                    with patch.dict(mount.__salt__, {"cmd.run": mock}):
                        self.assertFalse(mount.swapoff("name"))

        mock = MagicMock(side_effect=[{"name": "name"}, {}])
        with patch.dict(mount.__grains__, {"kernel": ""}):
            with patch.object(mount, "swaps", mock):
                with patch.dict(mount.__grains__, {"os": "test"}):
                    mock = MagicMock(return_value=None)
                    with patch.dict(mount.__salt__, {"cmd.run": mock}):
                        self.assertTrue(mount.swapoff("name"))

        # check on AIX
        mock = MagicMock(return_value={})
        with patch.dict(mount.__grains__, {"kernel": "AIX"}):
            with patch.object(mount, "swaps", mock):
                self.assertEqual(mount.swapoff("name"), None)

        mock = MagicMock(return_value={"name": "name"})
        with patch.dict(mount.__grains__, {"kernel": "AIX"}):
            with patch.object(mount, "swaps", mock):
                with patch.dict(mount.__grains__, {"os": "test"}):
                    mock = MagicMock(return_value=None)
                    with patch.dict(mount.__salt__, {"cmd.run": mock}):
                        self.assertFalse(mount.swapoff("name"))

        mock = MagicMock(side_effect=[{"name": "name"}, {}])
        with patch.dict(mount.__grains__, {"kernel": "AIX"}):
            with patch.object(mount, "swaps", mock):
                with patch.dict(mount.__grains__, {"os": "test"}):
                    mock = MagicMock(return_value=None)
                    with patch.dict(mount.__salt__, {"cmd.run": mock}):
                        self.assertTrue(mount.swapoff("name"))

    def test_is_mounted(self):
        """
        Provide information if the path is mounted
        """
        mock = MagicMock(return_value={})
        with patch.object(mount, "active", mock), patch.dict(
            mount.__grains__, {"kernel": ""}
        ):
            self.assertFalse(mount.is_mounted("name"))

        mock = MagicMock(return_value={"name": "name"})
        with patch.object(mount, "active", mock), patch.dict(
            mount.__grains__, {"kernel": ""}
        ):
            self.assertTrue(mount.is_mounted("name"))
