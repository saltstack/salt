import logging

import pytest

import salt.modules.file as filemod
from salt.exceptions import SaltInvocationError
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {
        filemod: {
            "__salt__": {},
            "__opts__": {
                "test": False,
                "file_roots": {"base": "tmp"},
                "pillar_roots": {"base": "tmp"},
                "cachedir": "tmp",
                "grains": {},
            },
            "__grains__": {},
            "__utils__": {},
        }
    }


def test_file_rmdir_not_absolute_path_exception():
    with pytest.raises(SaltInvocationError):
        filemod.rmdir("not_absolute")


def test_file_rmdir_not_found_exception():
    with pytest.raises(SaltInvocationError):
        filemod.rmdir("/tmp/not_there")


def test_file_rmdir_not_found_exception_includes_path():
    with pytest.raises(SaltInvocationError, match="/tmp/not_there"):
        filemod.rmdir("/tmp/not_there")


def test_file_readdir_not_found_exception_includes_path():
    with pytest.raises(SaltInvocationError, match="/tmp/not_there"):
        filemod.readdir("/tmp/not_there")


def test_file_rmdir_not_found_includes_path_with_state_args_47707():
    # The file.rmdir state (salt/states/file.py) calls this as
    # rmdir(name, recurse=recurse, verbose=True, older_than=older_than).
    # verbose=True is the decisive flag: with it, removal failures are
    # normally collected into the returned dict's "errors" list instead of
    # raised, but an invalid directory must still raise, and the message
    # must include the offending path.
    with pytest.raises(SaltInvocationError, match="/tmp/not_there"):
        filemod.rmdir("/tmp/not_there", recurse=True, verbose=True, older_than=None)


def test_file_rmdir_relative_path_error_unchanged_47707():
    """
    Guard against overcorrection: a relative path must still fail the
    absolute-path check, not the valid-directory check changed for #47707.
    """
    with pytest.raises(SaltInvocationError, match="must be absolute"):
        filemod.rmdir("not_absolute")


def test_file_readdir_relative_path_error_unchanged_47707():
    """
    Guard against overcorrection: a relative path must still fail readdir's
    absolute-path check, not the valid-directory check changed for #47707.
    """
    with pytest.raises(SaltInvocationError, match="must be absolute"):
        filemod.readdir("not_absolute")


def test_file_readdir_valid_directory_47707(tmp_path):
    """
    Guard against overcorrection: readdir on an existing directory must
    still return the directory listing without raising.
    """
    (tmp_path / "afile").write_text("data")
    assert filemod.readdir(str(tmp_path)) == [".", "..", "afile"]


def test_file_rmdir_success_return():
    with patch("os.rmdir", MagicMock(return_value=True)), patch(
        "os.path.isdir", MagicMock(return_value=True)
    ):
        assert filemod.rmdir("/tmp/salt_test_return") is True


def test_file_rmdir_failure_return():
    with patch(
        "os.rmdir", MagicMock(side_effect=OSError(39, "Directory not empty"))
    ), patch("os.path.isdir", MagicMock(return_value=True)):
        assert filemod.rmdir("/tmp/salt_test_return") is False
