"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import os
import shutil
import uuid

import pytest

import salt.modules.seed as seed
import salt.utils.files
import salt.utils.odict
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {seed: {}}


@pytest.mark.slow_test
def test_mkconfig_odict():
    with patch.dict(seed.__opts__, {"master": "foo"}):
        ddd = salt.utils.odict.OrderedDict()
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
