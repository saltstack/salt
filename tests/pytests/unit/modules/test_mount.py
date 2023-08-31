"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

import logging
import os
import shutil
import textwrap

import pytest

import salt.modules.mount as mount
import salt.utils.files
import salt.utils.path
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, mock_open, patch

log = logging.getLogger(__name__)


@pytest.fixture
def mock_shell_file():
    return "A B C D F G\n"


@pytest.fixture
def config_initial_file():
    inital_fsystem = [
        "/:\n",
        "\tdev\t\t= /dev/hd4\n",
        "\tvfs\t\t= jfs2\n",
        "\tlog\t\t= /dev/hd8\n",
        "\tmount \t\t= automatic\n",
        "\tcheck\t\t= false\n",
        "\ttype\t\t= bootfs\n",
        "\tvol\t\t= root\n",
        "\tfree\t\t= true\n",
        "\n",
        "/home:\n",
        "\tdev\t\t= /dev/hd1\n",
        "\tvfs\t\t= jfs2\n",
        "\tlog\t\t= /dev/hd8\n",
        "\tmount\t\t= true\n",
        "\tcheck\t\t= true\n",
        "\tvol\t\t= /home\n",
        "\tfree\t\t= false\n",
        "\n",
    ]
    return inital_fsystem


@pytest.fixture
def configure_loader_modules():
    return {mount: {}}


@pytest.fixture
def tmp_sub_dir(tmp_path):
    directory = tmp_path / "filesystems-dir"
    directory.mkdir()

    yield directory

    shutil.rmtree(str(directory))


@pytest.fixture
def config_file(tmp_sub_dir, config_initial_file):
    filename = str(tmp_sub_dir / "filesystems")

    with salt.utils.files.fopen(filename, "wb") as fp:
        fp.writelines(salt.utils.data.encode(config_initial_file))

    yield filename

    os.remove(filename)


def test_active():
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
            assert mount.active() == {
                "B": {
                    "device": "A",
                    "opts": ["D", "E", "F", "uid=100", "gid=100"],
                    "fstype": "C",
                }
            }

    with patch.dict(mount.__grains__, {"os": "Solaris", "kernel": "SunOS"}):
        mock = MagicMock(return_value="A * B * C D/E/F")
        with patch.dict(mount.__salt__, {"cmd.run_stdout": mock}):
            assert mount.active() == {
                "B": {"device": "A", "opts": ["D", "E", "F"], "fstype": "C"}
            }

    with patch.dict(mount.__grains__, {"os": "AIX", "kernel": "AIX"}):
        mock = MagicMock(return_value="A * B * C D/E/F")
        with patch.dict(mount.__salt__, {"cmd.run_stdout": mock}):
            assert mount.active() == {"B": {"node": "A", "device": "*", "fstype": "*"}}

    with patch.dict(mount.__grains__, {"os": "OpenBSD", "kernel": "OpenBSD"}):
        mock = MagicMock(return_value={})
        with patch.object(mount, "_active_mounts_openbsd", mock):
            assert mount.active() == {}

    with patch.dict(mount.__grains__, {"os": "MacOS", "kernel": "Darwin"}):
        mock = MagicMock(return_value={})
        with patch.object(mount, "_active_mounts_darwin", mock):
            assert mount.active() == {}

    with patch.dict(mount.__grains__, {"os": "MacOS", "kernel": "Darwin"}):
        mock = MagicMock(return_value={})
        with patch.object(mount, "_active_mountinfo", mock):
            with patch.object(mount, "_active_mounts_darwin", mock):
                assert mount.active(extended=True) == {}

    with patch.dict(mount.__grains__, {"os": "AIX", "kernel": "AIX"}):
        mock = MagicMock(return_value={})
        with patch.object(mount, "_active_mounts_aix", mock):
            assert mount.active() == {}


def test_fstab_entry_ignores_opt_ordering():
    entry = mount._fstab_entry(
        name="/tmp",
        device="tmpfs",
        fstype="tmpfs",
        opts="defaults,nodev,noexec",
        dump=0,
        pass_num=0,
    )
    assert entry.match("tmpfs\t\t/tmp\ttmpfs\tnodev,defaults,noexec\t0 0\n")


def test_fstab():
    """
    List the content of the fstab
    """
    mock = MagicMock(return_value=False)
    with patch.object(os.path, "isfile", mock):
        assert mount.fstab() == {}

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


def test_vfstab():
    """
    List the content of the vfstab
    """
    mock = MagicMock(return_value=False)
    with patch.object(os.path, "isfile", mock):
        assert mount.vfstab() == {}

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


def test_filesystems():
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
        assert mount.filesystems() == {}

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
        assert test_fsyst == fsyst


def test_rm_fstab():
    """
    Remove the mount point from the fstab
    """
    mock_fstab = MagicMock(return_value={})
    with patch.dict(mount.__grains__, {"kernel": ""}):
        with patch.object(mount, "fstab", mock_fstab):
            with patch("salt.utils.files.fopen", mock_open()):
                assert mount.rm_fstab("name", "device")


def test_set_fstab(mock_shell_file):
    """
    Tests to verify that this mount is represented in the fstab,
    change the mount to match the data passed, or add the mount
    if it is not present.
    """
    mock = MagicMock(return_value=False)
    with patch.object(os.path, "isfile", mock):
        pytest.raises(CommandExecutionError, mount.set_fstab, "A", "B", "C")

    mock = MagicMock(return_value=True)
    mock_read = MagicMock(side_effect=OSError)
    with patch.object(os.path, "isfile", mock):
        with patch.object(salt.utils.files, "fopen", mock_read):
            pytest.raises(CommandExecutionError, mount.set_fstab, "A", "B", "C")

    mock = MagicMock(return_value=True)
    with patch.object(os.path, "isfile", mock):
        with patch("salt.utils.files.fopen", mock_open(read_data=mock_shell_file)):
            assert mount.set_fstab("A", "B", "C") == "new"

    mock = MagicMock(return_value=True)
    with patch.object(os.path, "isfile", mock):
        with patch("salt.utils.files.fopen", mock_open(read_data=mock_shell_file)):
            assert mount.set_fstab("B", "A", "C", "D", "F", "G") == "present"

    mock = MagicMock(return_value=True)
    with patch.object(os.path, "isfile", mock):
        with patch("salt.utils.files.fopen", mock_open(read_data=mock_shell_file)):
            assert mount.set_fstab("B", "A", "C", not_change=True) == "present"


def test_rm_automaster():
    """
    Remove the mount point from the auto_master
    """
    mock = MagicMock(return_value={})
    with patch.object(mount, "automaster", mock):
        assert mount.rm_automaster("name", "device")

    mock = MagicMock(return_value={"name": "name"})
    with patch.object(mount, "fstab", mock):
        assert mount.rm_automaster("name", "device")


def test_set_automaster(mock_shell_file):
    """
    Verify that this mount is represented in the auto_salt, change the mount
    to match the data passed, or add the mount if it is not present.
    """
    mock = MagicMock(return_value=True)
    with patch.object(os.path, "isfile", mock):
        pytest.raises(CommandExecutionError, mount.set_automaster, "A", "B", "C")

    mock = MagicMock(return_value=True)
    mock_read = MagicMock(side_effect=OSError)
    with patch.object(os.path, "isfile", mock):
        with patch.object(salt.utils.files, "fopen", mock_read):
            pytest.raises(CommandExecutionError, mount.set_automaster, "A", "B", "C")

    mock = MagicMock(return_value=True)
    with patch.object(os.path, "isfile", mock):
        with patch("salt.utils.files.fopen", mock_open(read_data=mock_shell_file)):
            assert mount.set_automaster("A", "B", "C") == "new"

    mock = MagicMock(return_value=True)
    with patch.object(os.path, "isfile", mock):
        with patch(
            "salt.utils.files.fopen", mock_open(read_data="/..A -fstype=C,D C:B")
        ):
            assert mount.set_automaster("A", "B", "C", "D") == "present"

    mock = MagicMock(return_value=True)
    with patch.object(os.path, "isfile", mock):
        with patch(
            "salt.utils.files.fopen", mock_open(read_data="/..A -fstype=XX C:B")
        ):
            assert (
                mount.set_automaster("A", "B", "C", "D", not_change=True) == "present"
            )


def test_automaster():
    """
    Test the list the contents of the fstab
    """
    assert mount.automaster() == {}


def test_rm_filesystems():
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
        assert not mount.rm_filesystems("name", "device")

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
        assert mount.rm_filesystems("/name", "device")


def test_set_filesystems():
    """
    Tests to verify that this mount is represented in the filesystems,
    change the mount to match the data passed, or add the mount
    if it is not present.
    """
    mock = MagicMock(return_value=False)
    with patch.dict(mount.__grains__, {"os": "AIX", "kernel": "AIX"}):
        with patch.object(os.path, "isfile", mock):
            pytest.raises(CommandExecutionError, mount.set_filesystems, "A", "B", "C")

        mock_read = MagicMock(side_effect=OSError)
        with patch.object(os.path, "isfile", mock):
            with patch.object(salt.utils.files, "fopen", mock_read):
                pytest.raises(
                    CommandExecutionError, mount.set_filesystems, "A", "B", "C"
                )


@pytest.mark.skip_on_windows(
    reason="Not supported on Windows, does not handle tabs well"
)
def test_set_filesystems_with_data(tmp_sub_dir, config_file):
    """
    Tests to verify set_filesystems reads and adjusts file /etc/filesystems correctly
    """
    # Note AIX uses tabs in filesystems files, hence disable warings and errors for tabs and spaces
    # pylint: disable=W8191
    # pylint: disable=E8101
    config_filepath = str(tmp_sub_dir / "filesystems")
    with patch.dict(mount.__grains__, {"os": "AIX", "kernel": "AIX"}):
        mount.set_filesystems(
            "/test_mount", "/dev/hd3", "jsf2", "-", "true", config_filepath
        )
        with salt.utils.files.fopen(config_filepath, "r") as fp:
            fsys_content = fp.read()

        test_fsyst = """/:
	dev		= /dev/hd4
	vfs		= jfs2
	log		= /dev/hd8
	mount		= automatic
	check		= false
	type		= bootfs
	vol		= root
	free		= true

/home:
	dev		= /dev/hd1
	vfs		= jfs2
	log		= /dev/hd8
	mount		= true
	check		= true
	vol		= /home
	free		= false

/test_mount:
	dev		= /dev/hd3
	vfstype		= jsf2
	opts		= -
	mount		= true

"""
    assert test_fsyst == fsys_content


def test_mount():
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
                    assert mount.mount("name", "device")
                    mock.assert_called_with(
                        "mount  'device' 'name' ", python_shell=False, runas=None
                    )

                with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                    assert mount.mount("name", "device", fstype="fstype")
                    mock.assert_called_with(
                        "mount  -t fstype 'device' 'name' ",
                        python_shell=False,
                        runas=None,
                    )

                mock = MagicMock(return_value={"retcode": False, "stderr": False})
                with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                    assert mount.mount("name", "device")

    with patch.dict(mount.__grains__, {"os": "AIX"}):
        mock = MagicMock(return_value=True)
        with patch.object(os.path, "exists", mock):
            mock = MagicMock(return_value=None)
            with patch.dict(mount.__salt__, {"file.mkdir": None}):
                mock = MagicMock(return_value={"retcode": True, "stderr": True})
                with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                    assert mount.mount("name", "device")
                    mock.assert_called_with(
                        "mount  'device' 'name' ", python_shell=False, runas=None
                    )

                with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                    assert mount.mount("name", "device", fstype="fstype")
                    mock.assert_called_with(
                        "mount  -v fstype 'device' 'name' ",
                        python_shell=False,
                        runas=None,
                    )

                mock = MagicMock(return_value={"retcode": False, "stderr": False})
                with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                    assert mount.mount("name", "device")

    with patch.dict(mount.__grains__, {"os": "Linux"}):
        mock = MagicMock(return_value=True)
        with patch.object(os.path, "exists", mock):
            mock = MagicMock(return_value=None)
            with patch.dict(mount.__salt__, {"file.mkdir": None}):
                mock = MagicMock(return_value={"retcode": True, "stderr": True})
                with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                    assert mount.mount("name", "device")
                    mock.assert_called_with(
                        "mount -o defaults 'device' 'name' ",
                        python_shell=False,
                        runas=None,
                    )

                with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                    assert mount.mount("name", "device", fstype="fstype")
                    mock.assert_called_with(
                        "mount -o defaults -t fstype 'device' 'name' ",
                        python_shell=False,
                        runas=None,
                    )

                mock = MagicMock(return_value={"retcode": False, "stderr": False})
                with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                    assert mount.mount("name", "device")


def test_remount_non_mounted():
    """
    Attempt to remount a device, if the device is not already mounted, mount
    is called
    """
    with patch.dict(mount.__grains__, {"os": "MacOS"}):
        mock = MagicMock(return_value=[])
        with patch.object(mount, "active", mock):
            mock = MagicMock(return_value=True)
            with patch.object(mount, "mount", mock):
                assert mount.remount("name", "device")

    with patch.dict(mount.__grains__, {"os": "AIX"}):
        mock = MagicMock(return_value=[])
        with patch.object(mount, "active", mock):
            mock = MagicMock(return_value=True)
            with patch.object(mount, "mount", mock):
                assert mount.remount("name", "device")

    with patch.dict(mount.__grains__, {"os": "Linux"}):
        mock = MagicMock(return_value=[])
        with patch.object(mount, "active", mock):
            mock = MagicMock(return_value=True)
            with patch.object(mount, "mount", mock):
                assert mount.remount("name", "device")


def test_remount_already_mounted_no_fstype():
    """
    Attempt to remount a device already mounted that do not provides
    fstype
    """
    with patch.dict(mount.__grains__, {"os": "MacOS"}):
        mock = MagicMock(return_value=["name"])
        with patch.object(mount, "active", mock):
            mock = MagicMock(return_value={"retcode": 0})
            with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                assert mount.remount("name", "device")
                mock.assert_called_with(
                    "mount -u -o noowners 'device' 'name' ",
                    python_shell=False,
                    runas=None,
                )

    with patch.dict(mount.__grains__, {"os": "AIX"}):
        mock = MagicMock(return_value=["name"])
        with patch.object(mount, "active", mock):
            mock = MagicMock(return_value={"retcode": 0})
            with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                assert mount.remount("name", "device")
                mock.assert_called_with(
                    "mount -o remount 'device' 'name' ", python_shell=False, runas=None
                )

    with patch.dict(mount.__grains__, {"os": "Linux"}):
        mock = MagicMock(return_value=["name"])
        with patch.object(mount, "active", mock):
            mock = MagicMock(return_value={"retcode": 0})
            with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                assert mount.remount("name", "device")
                mock.assert_called_with(
                    "mount -o defaults,remount 'device' 'name' ",
                    python_shell=False,
                    runas=None,
                )


def test_remount_already_mounted_with_fstype():
    """
    Attempt to remount a device already mounted that do not provides
    fstype
    """
    with patch.dict(mount.__grains__, {"os": "MacOS"}):
        mock = MagicMock(return_value=["name"])
        with patch.object(mount, "active", mock):
            mock = MagicMock(return_value={"retcode": 0})
            with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                assert mount.remount("name", "device", fstype="type")
                mock.assert_called_with(
                    "mount -u -o noowners -t type 'device' 'name' ",
                    python_shell=False,
                    runas=None,
                )

    with patch.dict(mount.__grains__, {"os": "AIX"}):
        mock = MagicMock(return_value=["name"])
        with patch.object(mount, "active", mock):
            mock = MagicMock(return_value={"retcode": 0})
            with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                assert mount.remount("name", "device", fstype="type")
                mock.assert_called_with(
                    "mount -o remount -v type 'device' 'name' ",
                    python_shell=False,
                    runas=None,
                )

    with patch.dict(mount.__grains__, {"os": "Linux"}):
        mock = MagicMock(return_value=["name"])
        with patch.object(mount, "active", mock):
            mock = MagicMock(return_value={"retcode": 0})
            with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
                assert mount.remount("name", "device", fstype="type")
                mock.assert_called_with(
                    "mount -o defaults,remount -t type 'device' 'name' ",
                    python_shell=False,
                    runas=None,
                )


def test_umount():
    """
    Attempt to unmount a device by specifying the directory it is
    mounted on
    """
    mock = MagicMock(return_value={})
    with patch.object(mount, "active", mock):
        assert mount.umount("name") == "name does not have anything mounted"

    mock = MagicMock(return_value={"name": "name"})
    with patch.object(mount, "active", mock):
        mock = MagicMock(return_value={"retcode": True, "stderr": True})
        with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
            assert mount.umount("name")

        mock = MagicMock(return_value={"retcode": False})
        with patch.dict(mount.__salt__, {"cmd.run_all": mock}):
            assert mount.umount("name")

    # Test unmounting with guestfs util
    mock = MagicMock()
    with patch.dict(mount.__salt__, {"guestfs.umount": mock}):
        mount.umount("/mountpoint", device="/path/to/my.qcow", util="guestfs")
        mock.assert_called_once_with("/mountpoint", disk="/path/to/my.qcow")


def test_is_fuse_exec():
    """
    Returns true if the command passed is a fuse mountable application
    """
    with patch.object(salt.utils.path, "which", return_value=None):
        assert not mount.is_fuse_exec("cmd")

    which_mock = MagicMock(side_effect=lambda x: x)
    ldd_mock = MagicMock(
        side_effect=[
            textwrap.dedent(
                """\
                linux-vdso.so.1 (0x00007ffeaf5fb000)
                libfuse3.so.3 => /usr/lib/libfuse3.so.3 (0x00007f91e66ac000)
                """
            ),
            textwrap.dedent(
                """\
                linux-vdso.so.1 (0x00007ffeaf5fb000)
                """
            ),
        ]
    )
    with patch.object(salt.utils.path, "which", which_mock):
        with patch.dict(mount.__salt__, {"cmd.run": ldd_mock}):
            assert mount.is_fuse_exec("cmd1")
            assert not mount.is_fuse_exec("cmd2")


def test_swaps():
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


def test_swapon():
    """
    Activate a swap disk
    """
    mock = MagicMock(return_value={"name": "name"})
    with patch.dict(mount.__grains__, {"kernel": ""}):
        with patch.object(mount, "swaps", mock):
            assert mount.swapon("name") == {"stats": "name", "new": False}

    mock = MagicMock(return_value={})
    with patch.dict(mount.__grains__, {"kernel": ""}):
        with patch.object(mount, "swaps", mock):
            mock = MagicMock(return_value=None)
            with patch.dict(mount.__salt__, {"cmd.run": mock}):
                assert mount.swapon("name", False) == {}

    mock = MagicMock(side_effect=[{}, {"name": "name"}])
    with patch.dict(mount.__grains__, {"kernel": ""}):
        with patch.object(mount, "swaps", mock):
            mock = MagicMock(return_value=None)
            with patch.dict(mount.__salt__, {"cmd.run": mock}):
                assert mount.swapon("name") == {"stats": "name", "new": True}
    ## effects of AIX
    mock = MagicMock(return_value={"name": "name"})
    with patch.dict(mount.__grains__, {"kernel": "AIX"}):
        with patch.object(mount, "swaps", mock):
            assert mount.swapon("name") == {"stats": "name", "new": False}

    mock = MagicMock(return_value={})
    with patch.dict(mount.__grains__, {"kernel": "AIX"}):
        with patch.object(mount, "swaps", mock):
            mock = MagicMock(return_value=None)
            with patch.dict(mount.__salt__, {"cmd.run": mock}):
                assert mount.swapon("name", False) == {}

    mock = MagicMock(side_effect=[{}, {"name": "name"}])
    with patch.dict(mount.__grains__, {"kernel": "AIX"}):
        with patch.object(mount, "swaps", mock):
            mock = MagicMock(return_value=None)
            with patch.dict(mount.__salt__, {"cmd.run": mock}):
                assert mount.swapon("name") == {"stats": "name", "new": True}


def test_swapoff():
    """
    Deactivate a named swap mount
    """
    mock = MagicMock(return_value={})
    with patch.dict(mount.__grains__, {"kernel": ""}):
        with patch.object(mount, "swaps", mock):
            assert mount.swapoff("name") is None

    mock = MagicMock(return_value={"name": "name"})
    with patch.dict(mount.__grains__, {"kernel": ""}):
        with patch.object(mount, "swaps", mock):
            with patch.dict(mount.__grains__, {"os": "test"}):
                mock = MagicMock(return_value=None)
                with patch.dict(mount.__salt__, {"cmd.run": mock}):
                    assert not mount.swapoff("name")

    mock = MagicMock(side_effect=[{"name": "name"}, {}])
    with patch.dict(mount.__grains__, {"kernel": ""}):
        with patch.object(mount, "swaps", mock):
            with patch.dict(mount.__grains__, {"os": "test"}):
                mock = MagicMock(return_value=None)
                with patch.dict(mount.__salt__, {"cmd.run": mock}):
                    assert mount.swapoff("name")

    # check on AIX
    mock = MagicMock(return_value={})
    with patch.dict(mount.__grains__, {"kernel": "AIX"}):
        with patch.object(mount, "swaps", mock):
            assert mount.swapoff("name") is None

    mock = MagicMock(return_value={"name": "name"})
    with patch.dict(mount.__grains__, {"kernel": "AIX"}):
        with patch.object(mount, "swaps", mock):
            with patch.dict(mount.__grains__, {"os": "test"}):
                mock = MagicMock(return_value=None)
                with patch.dict(mount.__salt__, {"cmd.run": mock}):
                    assert not mount.swapoff("name")

    mock = MagicMock(side_effect=[{"name": "name"}, {}])
    with patch.dict(mount.__grains__, {"kernel": "AIX"}):
        with patch.object(mount, "swaps", mock):
            with patch.dict(mount.__grains__, {"os": "test"}):
                mock = MagicMock(return_value=None)
                with patch.dict(mount.__salt__, {"cmd.run": mock}):
                    assert mount.swapoff("name")


def test_is_mounted():
    """
    Provide information if the path is mounted
    """
    mock = MagicMock(return_value={})
    with patch.object(mount, "active", mock), patch.dict(
        mount.__grains__, {"kernel": ""}
    ):
        assert not mount.is_mounted("name")

    mock = MagicMock(return_value={"name": "name"})
    with patch.object(mount, "active", mock), patch.dict(
        mount.__grains__, {"kernel": ""}
    ):
        assert mount.is_mounted("name")


def test_get_mount_from_path(tmp_path):
    expected = tmp_path
    while not os.path.ismount(expected):
        expected = expected.parent
    path = str(tmp_path)
    ret = mount.get_mount_from_path(path)
    assert ret == str(expected)


def test_get_device_from_path(tmp_path):
    expected = tmp_path
    while not os.path.ismount(expected):
        expected = expected.parent
    mock_active = [
        {},
        {str(expected): {"device": "mydevice"}},
    ]
    path = str(tmp_path)
    with patch("salt.modules.mount.active", MagicMock(side_effect=mock_active)):
        with patch.dict(mount.__grains__, {"kernel": ""}):
            with patch.dict(mount.__grains__, {"os": "test"}):
                ret = mount.get_device_from_path(path)
                assert ret is None
                ret = mount.get_device_from_path(path)
                assert ret == "mydevice"
