"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import os
import shutil
import uuid
from collections import OrderedDict

import pytest

import salt.modules.seed as seed
import salt.utils.files
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {seed: {}}


@pytest.mark.slow_test
def test_mkconfig_odict():
    with patch.dict(seed.__opts__, {"master": "foo"}):
        ddd = OrderedDict()
        ddd["b"] = "b"
        ddd["a"] = "b"
        data = seed.mkconfig(ddd, approve_key=False)
        with salt.utils.files.fopen(data["config"]) as fic:
            fdata = fic.read()
            assert fdata == "b: b\na: b\nmaster: foo\n"


def test_prep_bootstrap():
    """
    Test to update and get the random script to a random place
    """
    with patch.dict(
        seed.__salt__,
        {
            "config.gather_bootstrap_script": MagicMock(
                return_value=os.path.join("BS_PATH", "BS")
            )
        },
    ), patch.object(uuid, "uuid4", return_value="UUID"), patch.object(
        os.path, "exists", return_value=True
    ), patch.object(
        os, "chmod", return_value=None
    ), patch.object(
        shutil, "copy", return_value=None
    ):

        expect = (
            os.path.join("MPT", "tmp", "UUID", "BS"),
            os.sep + os.path.join("tmp", "UUID"),
        )
        assert seed.prep_bootstrap("MPT") == expect

        expect = (
            os.sep + os.path.join("MPT", "tmp", "UUID", "BS"),
            os.sep + os.path.join("tmp", "UUID"),
        )
        assert seed.prep_bootstrap(os.sep + "MPT") == expect


def test_apply_():
    """
    Test to seed a location (disk image, directory, or block device)
    with the minion config, approve the minion's key, and/or install
    salt-minion.
    """
    mock = MagicMock(
        side_effect=[
            False,
            {"type": "type", "target": "target"},
            {"type": "type", "target": "target"},
            {"type": "type", "target": "target"},
        ]
    )
    with patch.dict(seed.__salt__, {"file.stats": mock}):
        assert seed.apply_("path") == "path does not exist"

        with patch.object(seed, "_mount", return_value=False):
            assert seed.apply_("path") == "target could not be mounted"

        with patch.object(seed, "_mount", return_value="/mountpoint"):
            with patch.object(os.path, "join", return_value="A"):
                with patch.object(os, "makedirs", MagicMock(side_effect=OSError("f"))):
                    with patch.object(os.path, "isdir", return_value=False):
                        pytest.raises(OSError, seed.apply_, "p")

                with patch.object(os, "makedirs", MagicMock()):
                    with patch.object(seed, "mkconfig", return_value="A"):
                        with patch.object(seed, "_check_install", return_value=False):
                            with patch.object(
                                seed, "_umount", return_value=None
                            ) as umount_mock:
                                assert not seed.apply_("path", install=False)
                                umount_mock.assert_called_once_with(
                                    "/mountpoint", "target", "type"
                                )


def test_apply_moves_config_and_keys_with_shutil_move_55348():
    """
    Issue #55348: when salt-minion is already installed on the image
    (``_check_install`` returns True), apply_() relocates the generated
    minion config and keys into place. It must use shutil.move -- which
    falls back to copy+unlink across filesystem boundaries -- rather than
    os.rename, which raises OSError EXDEV ("Invalid cross-device link")
    when the temp source and its destination live on different mounts.

    Drives the ``_check_install`` is True branch with apply_() called using
    its production defaults. os.rename is stubbed to raise EXDEV to prove the
    code path no longer depends on it.
    """
    cfg_files = {"config": "C", "privkey": "K", "pubkey": "P"}
    minion_config = {"pki_dir": "/etc/salt/pki/minion"}
    salt_mock = {
        "file.stats": MagicMock(return_value={"type": "dir", "target": "target"}),
        "file.makedirs": MagicMock(),
    }
    with patch.dict(seed.__salt__, salt_mock), patch.object(
        seed, "_mount", return_value="/mountpoint"
    ), patch.object(os, "makedirs", MagicMock()), patch.object(
        seed, "mkconfig", return_value=cfg_files
    ), patch.object(
        seed, "_check_install", return_value=True
    ), patch(
        "salt.config.minion_config", return_value=minion_config
    ), patch.object(
        os.path, "isdir", return_value=True
    ), patch.object(
        seed, "_umount", return_value=None
    ), patch.object(
        shutil, "move", MagicMock()
    ) as move_mock, patch.object(
        os, "rename", MagicMock(side_effect=OSError("Invalid cross-device link"))
    ) as rename_mock:
        assert seed.apply_("path") is True
        move_mock.assert_any_call(
            "K", os.path.join("/mountpoint", "etc/salt/pki/minion", "minion.pem")
        )
        move_mock.assert_any_call(
            "P", os.path.join("/mountpoint", "etc/salt/pki/minion", "minion.pub")
        )
        move_mock.assert_any_call("C", os.path.join("/mountpoint", "etc/salt/minion"))
        assert move_mock.call_count == 3
        rename_mock.assert_not_called()


def test_apply_pre_installed_branch_returns_true_55348():
    """
    Inverse / must-not-regress guard for issue #55348. With the file move
    stubbed to succeed, the pre-installed branch must return True and unmount
    the image. This passes both WITH and WITHOUT the fix because os.rename and
    shutil.move are both stubbed to succeed -- it asserts only the branch's
    success/unmount contract, not which primitive performs the move (that is
    the direct test's job), so it guards the happy path against regression.
    """
    cfg_files = {"config": "C", "privkey": "K", "pubkey": "P"}
    minion_config = {"pki_dir": "/etc/salt/pki/minion"}
    salt_mock = {
        "file.stats": MagicMock(return_value={"type": "dir", "target": "target"}),
        "file.makedirs": MagicMock(),
    }
    with patch.dict(seed.__salt__, salt_mock), patch.object(
        seed, "_mount", return_value="/mountpoint"
    ), patch.object(os, "makedirs", MagicMock()), patch.object(
        seed, "mkconfig", return_value=cfg_files
    ), patch.object(
        seed, "_check_install", return_value=True
    ), patch(
        "salt.config.minion_config", return_value=minion_config
    ), patch.object(
        os.path, "isdir", return_value=True
    ), patch.object(
        seed, "_umount", return_value=None
    ) as umount_mock, patch.object(
        shutil, "move", MagicMock()
    ), patch.object(
        os, "rename", MagicMock()
    ):
        assert seed.apply_("path") is True
        umount_mock.assert_called_once_with("/mountpoint", "target", "dir")


def test_apply_creates_pki_dir_when_missing_55348():
    """
    Peripheral coverage of the touched _check_install branch: when the pki
    directory does not yet exist on the image, apply_() creates it via
    file.makedirs before moving the keys into place.
    """
    cfg_files = {"config": "C", "privkey": "K", "pubkey": "P"}
    minion_config = {"pki_dir": "/etc/salt/pki/minion"}
    makedirs_mock = MagicMock()
    salt_mock = {
        "file.stats": MagicMock(return_value={"type": "dir", "target": "target"}),
        "file.makedirs": makedirs_mock,
    }
    with patch.dict(seed.__salt__, salt_mock), patch.object(
        seed, "_mount", return_value="/mountpoint"
    ), patch.object(os, "makedirs", MagicMock()), patch.object(
        seed, "mkconfig", return_value=cfg_files
    ), patch.object(
        seed, "_check_install", return_value=True
    ), patch(
        "salt.config.minion_config", return_value=minion_config
    ), patch.object(
        os.path, "isdir", return_value=False
    ), patch.object(
        seed, "_umount", return_value=None
    ), patch.object(
        shutil, "move", MagicMock()
    ), patch.object(
        os, "rename", MagicMock()
    ):
        assert seed.apply_("path") is True
        makedirs_mock.assert_called_once_with(
            os.path.join("/mountpoint", "etc/salt/pki/minion", "")
        )
