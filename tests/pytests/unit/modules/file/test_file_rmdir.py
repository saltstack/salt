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
