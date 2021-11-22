"""
:maintainer:    Alberto Planas <aplanas@suse.com>
:platform:      Linux
"""

import pytest
import salt.states.btrfs as btrfs
import salt.utils.platform
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

pytestmark = pytest.mark.skipif(
    salt.utils.platform.is_windows(), reason="Not supported on Windows"
)


@pytest.fixture
def configure_loader_modules():
    return {btrfs: {"__salt__": {}, "__states__": {}, "__utils__": {}}}


@patch("salt.states.btrfs._umount")
@patch("tempfile.mkdtemp")
def test__mount_fails(mkdtemp, umount):
    """
    Test mounting a device in a temporary place.
    """
    mkdtemp.return_value = "/tmp/xxx"
    states_mock = {
        "mount.mounted": MagicMock(return_value={"result": False}),
    }
    with patch.dict(btrfs.__states__, states_mock):
        assert btrfs._mount("/dev/sda1", use_default=False) is None
        mkdtemp.assert_called_once()
        states_mock["mount.mounted"].assert_called_with(
            "/tmp/xxx",
            device="/dev/sda1",
            fstype="btrfs",
            opts="subvol=/",
            persist=False,
        )
        umount.assert_called_with("/tmp/xxx")


@patch("salt.states.btrfs._umount")
@patch("tempfile.mkdtemp")
def test__mount(mkdtemp, umount):
    """
    Test mounting a device in a temporary place.
    """
    mkdtemp.return_value = "/tmp/xxx"
    states_mock = {
        "mount.mounted": MagicMock(return_value={"result": True}),
    }
    with patch.dict(btrfs.__states__, states_mock):
        assert btrfs._mount("/dev/sda1", use_default=False) == "/tmp/xxx"
        mkdtemp.assert_called_once()
        states_mock["mount.mounted"].assert_called_with(
            "/tmp/xxx",
            device="/dev/sda1",
            fstype="btrfs",
            opts="subvol=/",
            persist=False,
        )
        umount.assert_not_called()


@patch("salt.states.btrfs._umount")
@patch("tempfile.mkdtemp")
def test__mount_use_default(mkdtemp, umount):
    """
    Test mounting a device in a temporary place.
    """
    mkdtemp.return_value = "/tmp/xxx"
    states_mock = {
        "mount.mounted": MagicMock(return_value={"result": True}),
    }
    with patch.dict(btrfs.__states__, states_mock):
        assert btrfs._mount("/dev/sda1", use_default=True) == "/tmp/xxx"
        mkdtemp.assert_called_once()
        states_mock["mount.mounted"].assert_called_with(
            "/tmp/xxx",
            device="/dev/sda1",
            fstype="btrfs",
            opts="defaults",
            persist=False,
        )
        umount.assert_not_called()


def test__umount():
    """
    Test umounting and cleanning temporary place.
    """
    states_mock = {
        "mount.unmounted": MagicMock(),
    }
    utils_mock = {
        "files.rm_rf": MagicMock(),
    }
    with patch.dict(btrfs.__states__, states_mock), patch.dict(
        btrfs.__utils__, utils_mock
    ):
        btrfs._umount("/tmp/xxx")
        states_mock["mount.unmounted"].assert_called_with("/tmp/xxx")
        utils_mock["files.rm_rf"].assert_called_with("/tmp/xxx")


def test__is_default_not_default():
    """
    Test if the subvolume is the current default.
    """
    salt_mock = {
        "btrfs.subvolume_show": MagicMock(
            return_value={"@/var": {"subvolume id": "256"}}
        ),
        "btrfs.subvolume_get_default": MagicMock(return_value={"id": "5"}),
    }
    with patch.dict(btrfs.__salt__, salt_mock):
        assert not btrfs._is_default("/tmp/xxx/@/var", "/tmp/xxx", "@/var")
        salt_mock["btrfs.subvolume_show"].assert_called_with("/tmp/xxx/@/var")
        salt_mock["btrfs.subvolume_get_default"].assert_called_with("/tmp/xxx")


def test__is_default():
    """
    Test if the subvolume is the current default.
    """
    salt_mock = {
        "btrfs.subvolume_show": MagicMock(
            return_value={"@/var": {"subvolume id": "256"}}
        ),
        "btrfs.subvolume_get_default": MagicMock(return_value={"id": "256"}),
    }
    with patch.dict(btrfs.__salt__, salt_mock):
        assert btrfs._is_default("/tmp/xxx/@/var", "/tmp/xxx", "@/var")
        salt_mock["btrfs.subvolume_show"].assert_called_with("/tmp/xxx/@/var")
        salt_mock["btrfs.subvolume_get_default"].assert_called_with("/tmp/xxx")


def test__set_default():
    """
    Test setting a subvolume as the current default.
    """
    salt_mock = {
        "btrfs.subvolume_show": MagicMock(
            return_value={"@/var": {"subvolume id": "256"}}
        ),
        "btrfs.subvolume_set_default": MagicMock(return_value=True),
    }
    with patch.dict(btrfs.__salt__, salt_mock):
        assert btrfs._set_default("/tmp/xxx/@/var", "/tmp/xxx", "@/var")
        salt_mock["btrfs.subvolume_show"].assert_called_with("/tmp/xxx/@/var")
        salt_mock["btrfs.subvolume_set_default"].assert_called_with("256", "/tmp/xxx")


def test__is_cow_not_cow():
    """
    Test if the subvolume is copy on write.
    """
    salt_mock = {
        "file.lsattr": MagicMock(return_value={"/tmp/xxx/@/var": ["C"]}),
    }
    with patch.dict(btrfs.__salt__, salt_mock):
        assert not btrfs._is_cow("/tmp/xxx/@/var")
        salt_mock["file.lsattr"].assert_called_with("/tmp/xxx/@")


def test__is_cow():
    """
    Test if the subvolume is copy on write.
    """
    salt_mock = {
        "file.lsattr": MagicMock(return_value={"/tmp/xxx/@/var": []}),
    }
    with patch.dict(btrfs.__salt__, salt_mock):
        assert btrfs._is_cow("/tmp/xxx/@/var")
        salt_mock["file.lsattr"].assert_called_with("/tmp/xxx/@")


def test__unset_cow():
    """
    Test disabling the subvolume as copy on write.
    """
    salt_mock = {
        "file.chattr": MagicMock(return_value=True),
    }
    with patch.dict(btrfs.__salt__, salt_mock):
        assert btrfs._unset_cow("/tmp/xxx/@/var")
        salt_mock["file.chattr"].assert_called_with(
            "/tmp/xxx/@/var", operator="add", attributes="C"
        )


@patch("salt.states.btrfs._umount")
@patch("salt.states.btrfs._mount")
def test_subvolume_created_exists(mount, umount):
    """
    Test creating a subvolume.
    """
    mount.return_value = "/tmp/xxx"
    salt_mock = {
        "btrfs.subvolume_exists": MagicMock(return_value=True),
    }
    opts_mock = {
        "test": False,
    }
    with patch.dict(btrfs.__salt__, salt_mock), patch.dict(btrfs.__opts__, opts_mock):
        assert btrfs.subvolume_created(name="@/var", device="/dev/sda1") == {
            "name": "@/var",
            "result": True,
            "changes": {},
            "comment": ["Subvolume @/var already present"],
        }
        salt_mock["btrfs.subvolume_exists"].assert_called_with("/tmp/xxx/@/var")
        mount.assert_called_once()
        umount.assert_called_once()


@patch("salt.states.btrfs._umount")
@patch("salt.states.btrfs._mount")
def test_subvolume_created_exists_decorator(mount, umount):
    """
    Test creating a subvolume using a non-kwargs call
    """
    mount.return_value = "/tmp/xxx"
    salt_mock = {
        "btrfs.subvolume_exists": MagicMock(return_value=True),
    }
    opts_mock = {
        "test": False,
    }
    with patch.dict(btrfs.__salt__, salt_mock), patch.dict(btrfs.__opts__, opts_mock):
        assert btrfs.subvolume_created("@/var", "/dev/sda1") == {
            "name": "@/var",
            "result": True,
            "changes": {},
            "comment": ["Subvolume @/var already present"],
        }
        salt_mock["btrfs.subvolume_exists"].assert_called_with("/tmp/xxx/@/var")
        mount.assert_called_once()
        umount.assert_called_once()


@patch("salt.states.btrfs._umount")
@patch("salt.states.btrfs._mount")
def test_subvolume_created_exists_test(mount, umount):
    """
    Test creating a subvolume.
    """
    mount.return_value = "/tmp/xxx"
    salt_mock = {
        "btrfs.subvolume_exists": MagicMock(return_value=True),
    }
    opts_mock = {
        "test": True,
    }
    with patch.dict(btrfs.__salt__, salt_mock), patch.dict(btrfs.__opts__, opts_mock):
        assert btrfs.subvolume_created(name="@/var", device="/dev/sda1") == {
            "name": "@/var",
            "result": None,
            "changes": {},
            "comment": ["Subvolume @/var already present"],
        }
        salt_mock["btrfs.subvolume_exists"].assert_called_with("/tmp/xxx/@/var")
        mount.assert_called_once()
        umount.assert_called_once()


@patch("salt.states.btrfs._is_default")
@patch("salt.states.btrfs._umount")
@patch("salt.states.btrfs._mount")
def test_subvolume_created_exists_was_default(mount, umount, is_default):
    """
    Test creating a subvolume.
    """
    mount.return_value = "/tmp/xxx"
    is_default.return_value = True
    salt_mock = {
        "btrfs.subvolume_exists": MagicMock(return_value=True),
    }
    opts_mock = {
        "test": False,
    }
    with patch.dict(btrfs.__salt__, salt_mock), patch.dict(btrfs.__opts__, opts_mock):
        assert btrfs.subvolume_created(
            name="@/var", device="/dev/sda1", set_default=True
        ) == {
            "name": "@/var",
            "result": True,
            "changes": {},
            "comment": ["Subvolume @/var already present"],
        }
        salt_mock["btrfs.subvolume_exists"].assert_called_with("/tmp/xxx/@/var")
        mount.assert_called_once()
        umount.assert_called_once()


@patch("salt.states.btrfs._set_default")
@patch("salt.states.btrfs._is_default")
@patch("salt.states.btrfs._umount")
@patch("salt.states.btrfs._mount")
def test_subvolume_created_exists_set_default(mount, umount, is_default, set_default):
    """
    Test creating a subvolume.
    """
    mount.return_value = "/tmp/xxx"
    is_default.return_value = False
    set_default.return_value = True
    salt_mock = {
        "btrfs.subvolume_exists": MagicMock(return_value=True),
    }
    opts_mock = {
        "test": False,
    }
    with patch.dict(btrfs.__salt__, salt_mock), patch.dict(btrfs.__opts__, opts_mock):
        assert btrfs.subvolume_created(
            name="@/var", device="/dev/sda1", set_default=True
        ) == {
            "name": "@/var",
            "result": True,
            "changes": {"@/var_default": True},
            "comment": ["Subvolume @/var already present"],
        }
        salt_mock["btrfs.subvolume_exists"].assert_called_with("/tmp/xxx/@/var")
        mount.assert_called_once()
        umount.assert_called_once()


@patch("salt.states.btrfs._set_default")
@patch("salt.states.btrfs._is_default")
@patch("salt.states.btrfs._umount")
@patch("salt.states.btrfs._mount")
def test_subvolume_created_exists_set_default_no_force(
    mount, umount, is_default, set_default
):
    """
    Test creating a subvolume.
    """
    mount.return_value = "/tmp/xxx"
    is_default.return_value = False
    set_default.return_value = True
    salt_mock = {
        "btrfs.subvolume_exists": MagicMock(return_value=True),
    }
    opts_mock = {
        "test": False,
    }
    with patch.dict(btrfs.__salt__, salt_mock), patch.dict(btrfs.__opts__, opts_mock):
        assert btrfs.subvolume_created(
            name="@/var",
            device="/dev/sda1",
            set_default=True,
            force_set_default=False,
        ) == {
            "name": "@/var",
            "result": True,
            "changes": {},
            "comment": ["Subvolume @/var already present"],
        }
        salt_mock["btrfs.subvolume_exists"].assert_called_with("/tmp/xxx/@/var")
        mount.assert_called_once()
        umount.assert_called_once()


@patch("salt.states.btrfs._is_cow")
@patch("salt.states.btrfs._umount")
@patch("salt.states.btrfs._mount")
def test_subvolume_created_exists_no_cow(mount, umount, is_cow):
    """
    Test creating a subvolume.
    """
    mount.return_value = "/tmp/xxx"
    is_cow.return_value = False
    salt_mock = {
        "btrfs.subvolume_exists": MagicMock(return_value=True),
    }
    opts_mock = {
        "test": False,
    }
    with patch.dict(btrfs.__salt__, salt_mock), patch.dict(btrfs.__opts__, opts_mock):
        assert btrfs.subvolume_created(
            name="@/var", device="/dev/sda1", copy_on_write=False
        ) == {
            "name": "@/var",
            "result": True,
            "changes": {},
            "comment": ["Subvolume @/var already present"],
        }
        salt_mock["btrfs.subvolume_exists"].assert_called_with("/tmp/xxx/@/var")
        mount.assert_called_once()
        umount.assert_called_once()


@patch("salt.states.btrfs._unset_cow")
@patch("salt.states.btrfs._is_cow")
@patch("salt.states.btrfs._umount")
@patch("salt.states.btrfs._mount")
def test_subvolume_created_exists_unset_cow(mount, umount, is_cow, unset_cow):
    """
    Test creating a subvolume.
    """
    mount.return_value = "/tmp/xxx"
    is_cow.return_value = True
    unset_cow.return_value = True
    salt_mock = {
        "btrfs.subvolume_exists": MagicMock(return_value=True),
    }
    opts_mock = {
        "test": False,
    }
    with patch.dict(btrfs.__salt__, salt_mock), patch.dict(btrfs.__opts__, opts_mock):
        assert btrfs.subvolume_created(
            name="@/var", device="/dev/sda1", copy_on_write=False
        ) == {
            "name": "@/var",
            "result": True,
            "changes": {"@/var_no_cow": True},
            "comment": ["Subvolume @/var already present"],
        }
        salt_mock["btrfs.subvolume_exists"].assert_called_with("/tmp/xxx/@/var")
        mount.assert_called_once()
        umount.assert_called_once()


@patch("salt.states.btrfs._umount")
@patch("salt.states.btrfs._mount")
def test_subvolume_created(mount, umount):
    """
    Test creating a subvolume.
    """
    mount.return_value = "/tmp/xxx"
    salt_mock = {
        "btrfs.subvolume_exists": MagicMock(return_value=False),
        "btrfs.subvolume_create": MagicMock(),
    }
    states_mock = {
        "file.directory": MagicMock(return_value={"result": True}),
    }
    opts_mock = {
        "test": False,
    }
    with patch.dict(btrfs.__salt__, salt_mock), patch.dict(
        btrfs.__states__, states_mock
    ), patch.dict(btrfs.__opts__, opts_mock):
        assert btrfs.subvolume_created(name="@/var", device="/dev/sda1") == {
            "name": "@/var",
            "result": True,
            "changes": {"@/var": "Created subvolume @/var"},
            "comment": [],
        }
        salt_mock["btrfs.subvolume_exists"].assert_called_with("/tmp/xxx/@/var")
        salt_mock["btrfs.subvolume_create"].assert_called_once()
        mount.assert_called_once()
        umount.assert_called_once()


@patch("salt.states.btrfs._umount")
@patch("salt.states.btrfs._mount")
def test_subvolume_created_fails_directory(mount, umount):
    """
    Test creating a subvolume.
    """
    mount.return_value = "/tmp/xxx"
    salt_mock = {
        "btrfs.subvolume_exists": MagicMock(return_value=False),
    }
    states_mock = {
        "file.directory": MagicMock(return_value={"result": False}),
    }
    opts_mock = {
        "test": False,
    }
    with patch.dict(btrfs.__salt__, salt_mock), patch.dict(
        btrfs.__states__, states_mock
    ), patch.dict(btrfs.__opts__, opts_mock):
        assert btrfs.subvolume_created(name="@/var", device="/dev/sda1") == {
            "name": "@/var",
            "result": False,
            "changes": {},
            "comment": ["Error creating /tmp/xxx/@ directory"],
        }
        salt_mock["btrfs.subvolume_exists"].assert_called_with("/tmp/xxx/@/var")
        mount.assert_called_once()
        umount.assert_called_once()


@patch("salt.states.btrfs._umount")
@patch("salt.states.btrfs._mount")
def test_subvolume_created_fails(mount, umount):
    """
    Test creating a subvolume.
    """
    mount.return_value = "/tmp/xxx"
    salt_mock = {
        "btrfs.subvolume_exists": MagicMock(return_value=False),
        "btrfs.subvolume_create": MagicMock(side_effect=CommandExecutionError),
    }
    states_mock = {
        "file.directory": MagicMock(return_value={"result": True}),
    }
    opts_mock = {
        "test": False,
    }
    with patch.dict(btrfs.__salt__, salt_mock), patch.dict(
        btrfs.__states__, states_mock
    ), patch.dict(btrfs.__opts__, opts_mock):
        assert btrfs.subvolume_created(name="@/var", device="/dev/sda1") == {
            "name": "@/var",
            "result": False,
            "changes": {},
            "comment": ["Error creating subvolume @/var"],
        }
        salt_mock["btrfs.subvolume_exists"].assert_called_with("/tmp/xxx/@/var")
        salt_mock["btrfs.subvolume_create"].assert_called_once()
        mount.assert_called_once()
        umount.assert_called_once()


def test_diff_properties_fails():
    """
    Test when diff_properties do not found a property
    """
    expected = {"wrong_property": True}
    current = {
        "compression": {
            "description": "Set/get compression for a file or directory",
            "value": "N/A",
        },
        "label": {"description": "Set/get label of device.", "value": "N/A"},
        "ro": {"description": "Set/get read-only flag or subvolume", "value": "N/A"},
    }
    with pytest.raises(Exception):
        btrfs._diff_properties(expected, current)


def test_diff_properties_enable_ro():
    """
    Test when diff_properties enable one single property
    """
    expected = {"ro": True}
    current = {
        "compression": {
            "description": "Set/get compression for a file or directory",
            "value": "N/A",
        },
        "label": {"description": "Set/get label of device.", "value": "N/A"},
        "ro": {"description": "Set/get read-only flag or subvolume", "value": "N/A"},
    }
    assert btrfs._diff_properties(expected, current) == {"ro": True}


def test_diff_properties_only_enable_ro():
    """
    Test when diff_properties is half ready
    """
    expected = {"ro": True, "label": "mylabel"}
    current = {
        "compression": {
            "description": "Set/get compression for a file or directory",
            "value": "N/A",
        },
        "label": {"description": "Set/get label of device.", "value": "mylabel"},
        "ro": {"description": "Set/get read-only flag or subvolume", "value": "N/A"},
    }
    assert btrfs._diff_properties(expected, current) == {"ro": True}


def test_diff_properties_disable_ro():
    """
    Test when diff_properties enable one single property
    """
    expected = {"ro": False}
    current = {
        "compression": {
            "description": "Set/get compression for a file or directory",
            "value": "N/A",
        },
        "label": {"description": "Set/get label of device.", "value": "N/A"},
        "ro": {"description": "Set/get read-only flag or subvolume", "value": True},
    }
    assert btrfs._diff_properties(expected, current) == {"ro": False}


def test_diff_properties_emty_na():
    """
    Test when diff_properties is already disabled as N/A
    """
    expected = {"ro": False}
    current = {
        "compression": {
            "description": "Set/get compression for a file or directory",
            "value": "N/A",
        },
        "label": {"description": "Set/get label of device.", "value": "N/A"},
        "ro": {"description": "Set/get read-only flag or subvolume", "value": "N/A"},
    }
    assert btrfs._diff_properties(expected, current) == {}


@patch("salt.states.btrfs._umount")
@patch("salt.states.btrfs._mount")
@patch("os.path.exists")
def test_properties_subvolume_not_exists(exists, mount, umount):
    """
    Test when subvolume is not present
    """
    exists.return_value = False
    mount.return_value = "/tmp/xxx"
    assert btrfs.properties(name="@/var", device="/dev/sda1") == {
        "name": "@/var",
        "result": False,
        "changes": {},
        "comment": ["Object @/var not found"],
    }
    mount.assert_called_once()
    umount.assert_called_once()


@patch("salt.states.btrfs._umount")
@patch("salt.states.btrfs._mount")
@patch("os.path.exists")
def test_properties_default_root_subvolume(exists, mount, umount):
    """
    Test when root subvolume resolves to another subvolume
    """
    exists.return_value = False
    mount.return_value = "/tmp/xxx"
    assert btrfs.properties(name="/", device="/dev/sda1") == {
        "name": "/",
        "result": False,
        "changes": {},
        "comment": ["Object / not found"],
    }
    exists.assert_called_with("/tmp/xxx/.")


@patch("os.path.exists")
def test_properties_device_fail(exists):
    """
    Test when we try to set a device that is not pressent
    """
    exists.return_value = False
    assert btrfs.properties(name="/dev/sda1", device=None) == {
        "name": "/dev/sda1",
        "result": False,
        "changes": {},
        "comment": ["Object /dev/sda1 not found"],
    }


@patch("salt.states.btrfs._umount")
@patch("salt.states.btrfs._mount")
@patch("os.path.exists")
def test_properties_subvolume_fail(exists, mount, umount):
    """
    Test setting a wrong property in a subvolume
    """
    exists.return_value = True
    mount.return_value = "/tmp/xxx"
    salt_mock = {
        "btrfs.properties": MagicMock(
            side_effect=[
                {
                    "ro": {
                        "description": "Set/get read-only flag or subvolume",
                        "value": "N/A",
                    },
                }
            ]
        ),
    }
    opts_mock = {
        "test": False,
    }
    with patch.dict(btrfs.__salt__, salt_mock), patch.dict(btrfs.__opts__, opts_mock):
        assert btrfs.properties(
            name="@/var", device="/dev/sda1", wrond_property=True
        ) == {
            "name": "@/var",
            "result": False,
            "changes": {},
            "comment": ["Some property not found in @/var"],
        }
        salt_mock["btrfs.properties"].assert_called_with("/tmp/xxx/@/var")
        mount.assert_called_once()
        umount.assert_called_once()


@patch("salt.states.btrfs._umount")
@patch("salt.states.btrfs._mount")
@patch("os.path.exists")
def test_properties_enable_ro_subvolume(exists, mount, umount):
    """
    Test setting a ro property in a subvolume
    """
    exists.return_value = True
    mount.return_value = "/tmp/xxx"
    salt_mock = {
        "btrfs.properties": MagicMock(
            side_effect=[
                {
                    "ro": {
                        "description": "Set/get read-only flag or subvolume",
                        "value": "N/A",
                    },
                },
                None,
                {
                    "ro": {
                        "description": "Set/get read-only flag or subvolume",
                        "value": "true",
                    },
                },
            ]
        ),
    }
    opts_mock = {
        "test": False,
    }
    with patch.dict(btrfs.__salt__, salt_mock), patch.dict(btrfs.__opts__, opts_mock):
        assert btrfs.properties(name="@/var", device="/dev/sda1", ro=True) == {
            "name": "@/var",
            "result": True,
            "changes": {"ro": "true"},
            "comment": ["Properties changed in @/var"],
        }
        salt_mock["btrfs.properties"].assert_any_call("/tmp/xxx/@/var")
        salt_mock["btrfs.properties"].assert_any_call("/tmp/xxx/@/var", set="ro=true")
        mount.assert_called_once()
        umount.assert_called_once()


@patch("salt.states.btrfs._umount")
@patch("salt.states.btrfs._mount")
@patch("os.path.exists")
def test_properties_test(exists, mount, umount):
    """
    Test setting a property in test mode.
    """
    exists.return_value = True
    mount.return_value = "/tmp/xxx"
    salt_mock = {
        "btrfs.properties": MagicMock(
            side_effect=[
                {
                    "ro": {
                        "description": "Set/get read-only flag or subvolume",
                        "value": "N/A",
                    },
                },
            ]
        ),
    }
    opts_mock = {
        "test": True,
    }
    with patch.dict(btrfs.__salt__, salt_mock), patch.dict(btrfs.__opts__, opts_mock):
        assert btrfs.properties(name="@/var", device="/dev/sda1", ro=True) == {
            "name": "@/var",
            "result": None,
            "changes": {"ro": "true"},
            "comment": [],
        }
        salt_mock["btrfs.properties"].assert_called_with("/tmp/xxx/@/var")
        mount.assert_called_once()
        umount.assert_called_once()
