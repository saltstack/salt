"""
Tests for win_file execution module
"""
import pytest

import salt.modules.win_file as win_file
import salt.utils.path

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture
def configure_loader_modules():
    return {win_file: {"__utils__": {"path.islink": salt.utils.path.islink}}}


@pytest.fixture(scope="function")
def test_dir(tmp_path_factory):
    test_dir = tmp_path_factory.mktemp("test_dir")
    yield test_dir
    if test_dir.exists():
        test_dir.rmdir()


def test_issue_52002_check_file_remove_symlink(test_dir):
    """
    Make sure that directories including symlinks or symlinks can be removed
    """
    # Create environment
    target = test_dir / "child 1" / "target"
    target.mkdir(parents=True)

    symlink = test_dir / "child 2" / "link"
    symlink.parent.mkdir(parents=True)
    symlink.symlink_to(target, target_is_directory=True)

    # Test removal of directory containing symlink
    win_file.remove(test_dir)
    assert test_dir.exists() is False
