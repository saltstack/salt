import pytest

import salt.states.file as file
import salt.utils.win_dacl as win_dacl

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture
def configure_loader_modules():
    return {
        file: {"__opts__": {"test": False}},
    }


def test__check_directory_win_owner(tmp_path):
    path = str(tmp_path)
    _, comment, changes = file._check_directory_win(name=path, win_owner="Everyone")
    assert path in comment
    assert changes == {"owner": "Everyone"}


def test__check_directory_win_grant_perms_basic(tmp_path):
    path = str(tmp_path)
    perms = {
        "Guest": {
            "applies_to": "this_folder_subfolders_files",
            "perms": "full_control",
        }
    }
    expected = {
        "grant_perms": {
            "Guest": {
                "applies_to": "this_folder_subfolders_files",
                "permissions": "full_control",
            }
        }
    }
    _, comment, changes = file._check_directory_win(name=path, win_perms=perms)
    assert path in comment
    assert changes == expected


def test__check_directory_win_grant_perms_basic_existing_user(tmp_path):
    path = str(tmp_path)
    win_dacl.set_permissions(
        obj_name=path,
        principal="Guest",
        permissions=["write_data", "write_attributes"],
        access_mode="grant",
    )
    perms = {"Guest": {"perms": "full_control"}}
    expected = {"grant_perms": {"Guest": {"permissions": "full_control"}}}
    _, comment, changes = file._check_directory_win(name=path, win_perms=perms)
    assert path in comment
    assert changes == expected


def test__check_directory_win_grant_perms_advanced(tmp_path):
    path = str(tmp_path)
    perms = {
        "Guest": {
            "applies_to": "this_folder_subfolders_files",
            "perms": ["read_data", "write_data", "create_files"],
        }
    }
    expected = {
        "grant_perms": {
            "Guest": {
                "applies_to": "this_folder_subfolders_files",
                "permissions": ["read_data", "write_data", "create_files"],
            }
        }
    }
    _, comment, changes = file._check_directory_win(name=path, win_perms=perms)
    assert path in comment
    assert changes == expected


def test__check_directory_win_grant_perms_advanced_existing_user(tmp_path):
    path = str(tmp_path)
    win_dacl.set_permissions(
        obj_name=path,
        principal="Guest",
        permissions="full_control",
        access_mode="grant",
    )
    perms = {
        "Guest": {
            "applies_to": "this_folder_subfolders_files",
            "perms": ["read_data", "write_data", "create_files"],
        }
    }
    expected = {
        "grant_perms": {
            "Guest": {"permissions": ["read_data", "write_data", "create_files"]}
        }
    }
    _, comment, changes = file._check_directory_win(name=path, win_perms=perms)
    assert path in comment
    assert changes == expected


def test__check_directory_win_grant_perms_basic_no_applies_to(tmp_path):
    path = str(tmp_path)
    perms = {"Guest": {"perms": "full_control"}}
    expected = {"grant_perms": {"Guest": {"permissions": "full_control"}}}
    _, comment, changes = file._check_directory_win(name=path, win_perms=perms)
    assert path in comment
    assert changes == expected


def test__check_directory_win_deny_perms_basic(tmp_path):
    path = str(tmp_path)
    perms = {
        "Guest": {
            "applies_to": "this_folder_subfolders_files",
            "perms": "full_control",
        }
    }
    expected = {
        "deny_perms": {
            "Guest": {
                "applies_to": "this_folder_subfolders_files",
                "permissions": "full_control",
            }
        }
    }
    _, comment, changes = file._check_directory_win(name=path, win_deny_perms=perms)
    assert path in comment
    assert changes == expected


def test__check_directory_win_deny_perms_basic_existing_user(tmp_path):
    path = str(tmp_path)
    win_dacl.set_permissions(
        obj_name=path,
        principal="Guest",
        permissions=["write_data", "write_attributes"],
        access_mode="deny",
    )
    perms = {"Guest": {"perms": "full_control"}}
    expected = {"deny_perms": {"Guest": {"permissions": "full_control"}}}
    _, comment, changes = file._check_directory_win(name=path, win_deny_perms=perms)
    assert path in comment
    assert changes == expected


def test__check_directory_win_deny_perms_advanced(tmp_path):
    path = str(tmp_path)
    perms = {
        "Guest": {
            "applies_to": "this_folder_subfolders_files",
            "perms": ["read_data", "write_data", "create_files"],
        }
    }
    expected = {
        "deny_perms": {
            "Guest": {
                "applies_to": "this_folder_subfolders_files",
                "permissions": ["read_data", "write_data", "create_files"],
            }
        }
    }
    _, comment, changes = file._check_directory_win(name=path, win_deny_perms=perms)
    assert path in comment
    assert changes == expected


def test__check_directory_win_deny_perms_advanced_existing_user(tmp_path):
    path = str(tmp_path)
    win_dacl.set_permissions(
        obj_name=path,
        principal="Guest",
        permissions="full_control",
        access_mode="deny",
    )
    perms = {
        "Guest": {
            "applies_to": "this_folder_subfolders_files",
            "perms": ["read_data", "write_data", "create_files"],
        }
    }
    expected = {
        "deny_perms": {
            "Guest": {"permissions": ["read_data", "write_data", "create_files"]}
        }
    }
    _, comment, changes = file._check_directory_win(name=path, win_deny_perms=perms)
    assert path in comment
    assert changes == expected


def test__check_directory_win_deny_perms_basic_no_applies_to(tmp_path):
    path = str(tmp_path)
    perms = {"Guest": {"perms": "full_control"}}
    expected = {"deny_perms": {"Guest": {"permissions": "full_control"}}}
    _, comment, changes = file._check_directory_win(name=path, win_deny_perms=perms)
    assert path in comment
    assert changes == expected


def test__check_directory_win_inheritance(tmp_path):
    path = str(tmp_path)
    expected = {}
    _, comment, changes = file._check_directory_win(name=path, win_inheritance=True)
    assert path in comment
    assert changes == expected


def test__check_directory_win_inheritance_false(tmp_path):
    path = str(tmp_path)
    expected = {"inheritance": False}
    _, comment, changes = file._check_directory_win(name=path, win_inheritance=False)
    assert path in comment
    assert changes == expected


def test__check_directory_reset_no_non_inherited_users(tmp_path):
    path = str(tmp_path)
    expected = {}
    _, comment, changes = file._check_directory_win(name=path, win_perms_reset=True)
    assert path in comment
    assert changes == expected


def test__check_directory_reset_non_inherited_users_grant(tmp_path):
    path = str(tmp_path)
    win_dacl.set_permissions(
        obj_name=path,
        principal="Guest",
        permissions="full_control",
        access_mode="grant",
        reset_perms=True,
    )
    expected = {
        "remove_perms": {
            "Guest": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            }
        }
    }
    _, comment, changes = file._check_directory_win(name=path, win_perms_reset=True)
    assert path in comment
    assert changes == expected


def test__check_directory_reset_non_inherited_users_deny(tmp_path):
    path = str(tmp_path)
    win_dacl.set_permissions(
        obj_name=path,
        principal="Guest",
        permissions="full_control",
        access_mode="deny",
        reset_perms=True,
    )
    expected = {
        "remove_perms": {
            "Guest": {
                "deny": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            }
        }
    }
    _, comment, changes = file._check_directory_win(name=path, win_perms_reset=True)
    assert path in comment
    assert changes == expected
