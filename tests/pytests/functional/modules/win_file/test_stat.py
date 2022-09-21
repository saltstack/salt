"""
Tests for win_file execution module
"""
import pytest

import salt.modules.win_file as win_file
import salt.utils.files
import salt.utils.path
import salt.utils.win_dacl
from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture
def configure_loader_modules():
    return {
        win_file: {
            "__utils__": {
                "dacl.get_name": salt.utils.win_dacl.get_name,
                "dacl.get_owner": salt.utils.win_dacl.get_owner,
                "dacl.get_primary_group": salt.utils.win_dacl.get_primary_group,
                "dacl.get_sid_string": salt.utils.win_dacl.get_sid_string,
                "files.normalize_mode": salt.utils.files.normalize_mode,
                "path.islink": salt.utils.path.islink,
            }
        }
    }


@pytest.fixture(scope="function")
def test_file():
    with pytest.helpers.temp_file("win_file_test.file") as test_file:
        yield test_file


def test_stat(test_file):
    ret = win_file.stats(str(test_file), None, True)
    assert ret["mode"] == "0666"
    assert ret["type"] == "file"


def test_stats_issue_43328(test_file):
    """
    Make sure that a CommandExecutionError is raised if the file does NOT
    exist
    """
    fake_file = test_file.parent / "fake.file"
    with pytest.raises(CommandExecutionError):
        win_file.stats(fake_file)
