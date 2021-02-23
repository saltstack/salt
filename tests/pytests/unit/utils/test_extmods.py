import os

import pytest
import salt.utils.extmods as extmods
from tests.support.mock import patch


@pytest.mark.parametrize(
    "utils_dirs",
    [["blerp"], ["/bang/fnord/blerp", "d/bang/fnord/blerp", "bang/fnord/blerp"]],
)
def test_when_utils_dirs_in_opts_and_mod_dir_ends_with_any_dir_in_utils_and_mod_dir_not_on_sys_path_then_mod_dir_should_be_added_to_sys_path(
    utils_dirs,
):

    dir_to_sync = "blerp"
    extension_modules = "fnord/bang/fnord"
    expected_path = [os.path.join(extension_modules, dir_to_sync)]
    fake_path = []

    with patch(
        "salt.fileclient.get_file_client", autospec=True
    ) as fake_fileclient, patch("shutil.copyfile", autospec=True), patch(
        "sys.path", fake_path
    ):
        fake_fileclient.return_value.cache_dir.return_value = ["something_good"]
        extmods.sync(
            opts={
                "utils_dirs": utils_dirs,
                "extension_modules": extension_modules,
                "extmod_whitelist": None,
                "extmod_blacklist": None,
                "cachedir": "",
                "clean_dynamic_modules": False,
            },
            form=dir_to_sync,
        )

        assert fake_path == expected_path


def test_when_utils_dirs_is_empty_then_mod_dir_should_not_be_added_to_path():
    expected_path = []
    fake_path = []
    empty_utils_dirs = []

    with patch(
        "salt.fileclient.get_file_client", autospec=True
    ) as fake_fileclient, patch("shutil.copyfile", autospec=True), patch(
        "sys.path", fake_path
    ):
        fake_fileclient.return_value.cache_dir.return_value = ["something_good"]
        extmods.sync(
            opts={
                "utils_dirs": empty_utils_dirs,
                "extmod_whitelist": None,
                "extmod_blacklist": None,
                "extension_modules": "fnord",
                "cachedir": "",
                "clean_dynamic_modules": False,
            },
            form="blerp",
        )

        assert (
            fake_path == expected_path
        ), "mod_dir was added to sys.path when it should not have been."


@pytest.mark.parametrize(
    "utils_dirs",
    [
        ["mid"],
        ["start/mid"],
        ["start/m/end", "id/end", "d/end", "/end", "/mid/end", "t/mid/end"],
    ],
)
def test_when_utils_dirs_but_mod_dir_is_not_parent_of_any_util_dir_then_mod_dir_should_not_be_added_to_path(
    utils_dirs,
):
    dir_to_sync = "end"
    extension_modules = "start/mid"
    expected_path = []
    fake_path = []

    with patch(
        "salt.fileclient.get_file_client", autospec=True
    ) as fake_fileclient, patch("shutil.copyfile", autospec=True), patch(
        "sys.path", fake_path
    ):
        fake_fileclient.return_value.cache_dir.return_value = ["something_good"]
        extmods.sync(
            opts={
                "utils_dirs": utils_dirs,
                "extension_modules": extension_modules,
                "extmod_whitelist": None,
                "extmod_blacklist": None,
                "cachedir": "",
                "clean_dynamic_modules": False,
            },
            form=dir_to_sync,
        )

        assert fake_path == expected_path


def test_when_mod_dir_already_on_path_it_should_not_be_added_to_path():
    dir_to_sync = "blerp"
    extension_modules = "fnord/bang/fnord"
    expected_path = [os.path.join(extension_modules, dir_to_sync)]
    fake_path = expected_path[:]

    with patch(
        "salt.fileclient.get_file_client", autospec=True
    ) as fake_fileclient, patch("shutil.copyfile", autospec=True), patch(
        "sys.path", fake_path
    ):
        fake_fileclient.return_value.cache_dir.return_value = ["something_good"]
        extmods.sync(
            opts={
                "utils_dirs": ["blerp", "blerp", "blerp"],
                "extension_modules": extension_modules,
                "extmod_whitelist": None,
                "extmod_blacklist": None,
                "cachedir": "",
                "clean_dynamic_modules": False,
            },
            form=dir_to_sync,
        )

        assert fake_path == expected_path
