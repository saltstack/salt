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
    Test _gen_recurse_managed_files to make sure it does not include
    symlinks in the list of files that is passed to file.managed.
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
    cp_list_master_dirs = MagicMock(
        return_value=[
            "target",
            "target/not_a_symlink",
        ],
    )
    cp_list_master_symlinks = MagicMock(
        return_value={
            "target/symlink": f"{target_dir}{os.sep}not_a_symlink{os.sep}symlink"
        }
    )
    patch_salt = {
        "cp.list_master": cp_list_master,
        "cp.list_master_dirs": cp_list_master_dirs,
        "cp.list_master_symlinks": cp_list_master_symlinks,
    }
    with patch.dict(filestate.__salt__, patch_salt):
        files, dirs, links, keep = filestate._gen_recurse_managed_files(
            name=str(target_dir),
            sources=[f"salt://{target_dir.name}"],
            keep_symlinks=True,
        )
    unexpected = (
        f"{os.sep}some{os.sep}path{os.sep}target{os.sep}symlink",
        "salt://target/symlink?saltenv=base",
    )
    assert unexpected not in files
    expected_dest = f"{os.sep}some{os.sep}path{os.sep}target{os.sep}symlink"
    expected = (
        f"{os.sep}some{os.sep}path{os.sep}target{os.sep}not_a_symlink{os.sep}symlink",
        f"{os.sep}some{os.sep}path{os.sep}target{os.sep}not_a_symlink{os.sep}symlink",
    )
    assert expected_dest in links
    assert links[expected_dest] == expected
