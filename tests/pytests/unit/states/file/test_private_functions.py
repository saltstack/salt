import logging
import os

import pytest
import salt.modules.file as filemod
import salt.states.file as filestate
import salt.utils.files
import salt.utils.json
import salt.utils.platform
import salt.utils.win_functions
import salt.utils.yaml

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {filestate: {"__salt__": {"file.stats": filemod.stats}}}


@pytest.mark.destructive_test
@pytest.mark.skip_on_windows(reason="File modes do not exist on windows")
def test__check_directory(tmp_path):
    """
    Test the _check_directory function
    Make sure that recursive file permission checks return correctly
    """
    # set file permissions
    # Run _check_directory function
    # Verify that it returns correctly
    # Delete tmp directory structure
    root_tmp_dir = str(tmp_path / "test__check_dir")
    expected_mode = 0o770
    changed_mode = 0o755
    depth = 3

    def create_files(tmp_dir):
        for f in range(depth):
            path = os.path.join(tmp_dir, "file_{:03}.txt".format(f))
            with salt.utils.files.fopen(path, "w+"):
                os.chmod(path, expected_mode)

    # Create tmp directory structure
    os.mkdir(root_tmp_dir)
    os.chmod(root_tmp_dir, expected_mode)
    create_files(root_tmp_dir)

    for d in range(depth):
        dir_name = os.path.join(root_tmp_dir, "dir{:03}".format(d))
        os.mkdir(dir_name)
        os.chmod(dir_name, expected_mode)
        create_files(dir_name)
        for s in range(depth):
            sub_dir_name = os.path.join(dir_name, "dir{:03}".format(s))
            os.mkdir(sub_dir_name)
            os.chmod(sub_dir_name, expected_mode)
            create_files(sub_dir_name)
    # Symlinks on linux systems always have 0o777 permissions.
    # Ensure we are not treating them as modified files.
    target_dir = os.path.join(root_tmp_dir, "link_target_dir")
    target_file = os.path.join(target_dir, "link_target_file")
    link_dir = os.path.join(root_tmp_dir, "link_dir")
    link_to_dir = os.path.join(link_dir, "link_to_dir")
    link_to_file = os.path.join(link_dir, "link_to_file")

    os.mkdir(target_dir)
    os.mkdir(link_dir)
    with salt.utils.files.fopen(target_file, "w+"):
        pass
    os.symlink(target_dir, link_to_dir)
    os.symlink(target_file, link_to_file)
    for path in (target_dir, target_file, link_dir, link_to_dir, link_to_file):
        try:
            os.chmod(path, expected_mode, follow_symlinks=False)
        except (NotImplementedError, SystemError, OSError):
            os.chmod(path, expected_mode)

    # Set some bad permissions
    changed_files = {
        os.path.join(root_tmp_dir, "file_000.txt"),
        os.path.join(root_tmp_dir, "dir002", "file_000.txt"),
        os.path.join(root_tmp_dir, "dir000", "dir001", "file_002.txt"),
        os.path.join(root_tmp_dir, "dir001", "dir002"),
        os.path.join(root_tmp_dir, "dir002", "dir000"),
        os.path.join(root_tmp_dir, "dir001"),
    }
    for c in changed_files:
        os.chmod(c, changed_mode)

    ret = filestate._check_directory(
        root_tmp_dir,
        dir_mode=oct(expected_mode),
        file_mode=oct(expected_mode),
        recurse=["mode"],
    )
    assert changed_files == set(ret[-1].keys())
