import pytest
import salt.modules.opkg as opkg
from tests.support.mock import patch


@pytest.fixture(autouse=True)
def setup_loader():
    setup_loader_modules = {opkg: {}}
    with pytest.helpers.loader_mock(setup_loader_modules) as loader_mock:
        yield loader_mock


def test_when_os_is_NILinuxRT_and_creation_of_RESTART_CHECK_STATE_PATH_fails_virtual_should_be_False():
    expected_result = (
        False,
        "Error creating /var/lib/salt/restartcheck_state (-whatever): 42",
    )
    with patch.dict(opkg.__grains__, {"os_family": "NILinuxRT"}), patch(
        "os.makedirs", autospec=True, side_effect=OSError("whatever", 42, "boop")
    ):
        result = opkg.__virtual__()
        assert result == expected_result


def test_when_os_is_NILinuxRT_and_creation_is_OK_and_no_files_exist_then_files_should_be_updated():
    patch_grains = patch.dict(opkg.__grains__, {"os_family": "NILinuxRT"})
    patch_makedirs = patch("os.makedirs", autospec=True, return_value=None)
    patch_update_state = patch(
        "salt.modules.opkg._update_nilrt_restart_state", autospec=True
    )
    patch_listdir = patch("os.listdir", return_value=[], autospec=True)
    with patch_grains, patch_makedirs, patch_listdir, patch_update_state as fake_update:
        opkg.__virtual__()

        fake_update.assert_called_once()


def test_when_os_is_NILinuxRT_and_creation_is_OK_and_files_already_exist_then_files_should_not_be_updated():
    patch_grains = patch.dict(opkg.__grains__, {"os_family": "NILinuxRT"})
    patch_makedirs = patch("os.makedirs", autospec=True, return_value=None)
    patch_update_state = patch(
        "salt.modules.opkg._update_nilrt_restart_state", autospec=True
    )
    patch_listdir = patch(
        "os.listdir", return_value=["these", "are", "pretend", "files"], autospec=True
    )
    with patch_grains, patch_makedirs, patch_listdir, patch_update_state as fake_update:
        opkg.__virtual__()

        fake_update.assert_not_called()
