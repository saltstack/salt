import os

import pytest

import salt.modules.file as filemod
import salt.states.file as file
from tests.support.mock import call, create_autospec, patch


@pytest.fixture(autouse=True)
def setup_loader(request):
    setup_loader_modules = {file: {"__opts__": {"test": False}}}
    with pytest.helpers.loader_mock(request, setup_loader_modules) as loader_mock:
        yield loader_mock


@pytest.fixture()
def fake_remove():
    fake_remove_mod = create_autospec(filemod.remove)
    with patch.dict(file.__salt__, {"file.remove": fake_remove_mod}):
        yield fake_remove_mod


# TODO: This file.absent test should be a functional test instead. For now this is probably good enough -W. Werner, 2020-09-15
@pytest.mark.parametrize("mock_mod", ["os.path.isfile", "os.path.isdir"])
def test_file_absent_should_use_force_mode_for_file_remove(fake_remove, mock_mod):
    expected_path = "/some/abspath/foo"
    with patch(mock_mod, autospec=True, return_value=True):
        file.absent(expected_path)

    fake_remove.assert_called_with(expected_path, force=True)


# TODO: This file.matches test should be a functional test instead. For now this is probably good enough -W. Werner, 2020-09-15
def test_file_tidied_for_file_remove(fake_remove):
    patch_is_dir = patch("os.path.isdir", autospec=True, return_value=True)
    patch_os_walk = patch(
        "os.walk",
        autospec=True,
        return_value=[("some root", ("dirs",), ("file1", "file2"))],
    )
    patch_stat = patch("os.stat", autospec=True)
    with patch_os_walk, patch_is_dir, patch_stat as fake_stat:
        fake_stat.return_value.st_atime = 1600356711.1166897
        fake_stat.return_value.st_mode = 33188
        fake_stat.return_value.st_size = 9001  # It's over 9000!

        file.tidied("/some/directory/tree")

    call_root_file1 = "some root{}file1".format(os.sep)
    call_root_file2 = "some root{}file2".format(os.sep)
    fake_remove.assert_has_calls([call(call_root_file1), call(call_root_file2)])


# TODO: This file.copy test should be a functional test instead. For now this is probably good enough -W. Werner, 2020-09-15
def test_file_copy_should_use_provided_force_mode_for_file_remove(fake_remove):

    with patch("os.path.lexists", autospec=True, return_value=True), patch(
        "os.path.isfile", autospec=True, return_value=True
    ), patch("os.path.exists", autospec=True, return_value=True), patch.dict(
        file.__opts__, {"user": "somefakeouser"}
    ), patch(
        "salt.states.file._check_user", autospec=True, return_value=False
    ), patch(
        "salt.utils.hashutils.get_hash", autospec=True, return_value=["12345", "54321"]
    ):
        file.copy_("/tmp/foo", source="/tmp/bar", group="fnord", force=True, mode=777)

    fake_remove.assert_called_with("/tmp/foo", force=True)
