import pytest

import salt.states.file as file
import salt.utils.win_dacl as win_dacl

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
]


@pytest.fixture
def configure_loader_modules():
    return {
        file: {"__opts__": {"test": False}},
    }


@pytest.fixture
def temp_path(tmp_path):

    # Ownership is not inherited but permissions are, so we shouldn't have to
    # set ownership. Ownership is determined by the user creating the directory.
    # An administrator account will set the owner as the Administrators group.
    # A non-administrator account will set the user itself as the owner.

    # Create a directory and set the permissions to make sure they're the only
    # ones (reset_perms=True) and not inherited (protected=True)
    tmp_path.mkdir(parents=True, exist_ok=True)
    win_dacl.set_permissions(
        obj_name=str(tmp_path),
        principal="Administrators",
        permissions="full_control",
        access_mode="grant",
        reset_perms=True,
        protected=True,
    )
    perms = {
        "Inherited": {},
        "Not Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            }
        },
    }
    # Verify perms and inheritance
    assert win_dacl.get_permissions(obj_name=str(tmp_path)) == perms
    assert not win_dacl.get_inheritance(obj_name=str(tmp_path))

    # Now we create a directory for testing that does inherit those permissions
    # from the above, new parent directory
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()

    # We want to make sure inheritance is enabled
    assert win_dacl.get_inheritance(obj_name=str(test_dir))

    # We want to make sure the test directory inherited permissions from the
    # parent directory
    perms = {
        "Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            }
        },
        "Not Inherited": {},
    }
    assert win_dacl.get_permissions(obj_name=str(test_dir)) == perms
    yield test_dir


def test__check_directory_win_owner(temp_path):
    path = str(temp_path)
    _, comment, changes = file._check_directory_win(name=path, win_owner="Everyone")
    assert path in comment
    assert changes == {"owner": "Everyone"}


def test__check_directory_win_grant_perms_basic(temp_path):
    path = str(temp_path)
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


def test__check_directory_win_grant_perms_basic_existing_user(temp_path):
    path = str(temp_path)
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


def test__check_directory_win_grant_perms_advanced(temp_path):
    path = str(temp_path)
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


def test__check_directory_win_grant_perms_advanced_existing_user(temp_path):
    path = str(temp_path)
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


def test__check_directory_win_grant_perms_basic_no_applies_to(temp_path):
    path = str(temp_path)
    perms = {"Guest": {"perms": "full_control"}}
    expected = {"grant_perms": {"Guest": {"permissions": "full_control"}}}
    _, comment, changes = file._check_directory_win(name=path, win_perms=perms)
    assert path in comment
    assert changes == expected


def test__check_directory_win_deny_perms_basic(temp_path):
    path = str(temp_path)
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


def test__check_directory_win_deny_perms_basic_existing_user(temp_path):
    path = str(temp_path)
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


def test__check_directory_win_deny_perms_advanced(temp_path):
    path = str(temp_path)
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


def test__check_directory_win_deny_perms_advanced_existing_user(temp_path):
    path = str(temp_path)
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


def test__check_directory_win_deny_perms_basic_no_applies_to(temp_path):
    path = str(temp_path)
    perms = {"Guest": {"perms": "full_control"}}
    expected = {"deny_perms": {"Guest": {"permissions": "full_control"}}}
    _, comment, changes = file._check_directory_win(name=path, win_deny_perms=perms)
    assert path in comment
    assert changes == expected


def test__check_directory_win_inheritance(temp_path):
    path = str(temp_path)
    expected = {}
    _, comment, changes = file._check_directory_win(name=path, win_inheritance=True)
    assert path in comment
    assert changes == expected


def test__check_directory_win_inheritance_false(temp_path):
    path = str(temp_path)
    expected = {"inheritance": False}
    _, comment, changes = file._check_directory_win(name=path, win_inheritance=False)
    assert path in comment
    assert changes == expected


def test__check_directory_reset_no_non_inherited_users(temp_path):
    path = str(temp_path)
    expected = {}
    _, comment, changes = file._check_directory_win(name=path, win_perms_reset=True)
    assert path in comment
    assert changes == expected


def test__check_directory_reset_non_inherited_users_grant(temp_path):
    path = str(temp_path)
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


def test__check_directory_reset_non_inherited_users_deny(temp_path):
    path = str(temp_path)
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
