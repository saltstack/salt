import logging
import os
import pathlib

import pytest

import salt.states.file as filestate
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {filestate: {"__salt__": {}, "__opts__": {}, "__env__": "base"}}


def test__gen_recurse_managed_files():
    """
    Test _gen_recurse_managed_files to make sure it puts symlinks at the end of the list of files.
    """
    target_dir = pathlib.Path(f"{os.sep}some{os.sep}path{os.sep}target")
    cp_list_master = MagicMock(
        return_value=[
            "target/symlink",
            "target/just_a_file.txt",
            "target/not_a_symlink/symlink",
            "target/notasymlink",
        ],
    )
    cp_list_master_symlinks = MagicMock(
        return_value={
            "target/symlink": f"{target_dir}{os.sep}not_a_symlink{os.sep}symlink"
        }
    )
    patch_salt = {
        "cp.list_master": cp_list_master,
        "cp.list_master_symlinks": cp_list_master_symlinks,
    }
    with patch.dict(filestate.__salt__, patch_salt):
        files, dirs, links, keep = filestate._gen_recurse_managed_files(
            name=str(target_dir), source=f"salt://{target_dir.name}", keep_symlinks=True
        )
    expected = (
        f"{os.sep}some{os.sep}path{os.sep}target{os.sep}symlink",
        "salt://target/symlink?saltenv=base",
    )
    assert files[-1] == expected
