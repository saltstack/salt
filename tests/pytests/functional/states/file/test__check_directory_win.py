import pytest

import salt.states.file as file
import salt.utils.win_dacl as win_dacl
import salt.utils.win_functions as win_functions

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
    # We need to create a directory that doesn't inherit permissions from the test suite
    tmp_path.mkdir(parents=True, exist_ok=True)
    win_dacl.set_owner(obj_name=str(tmp_path), principal="Administrators")
    assert win_dacl.get_owner(obj_name=str(tmp_path)) == "Administrators"
    # We don't want the parent test directory to inherit permissions
    win_dacl.set_inheritance(obj_name=str(tmp_path), enabled=False)
    assert not win_dacl.get_inheritance(obj_name=str(tmp_path))
    # Set these permissions and make sure they're the only ones
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
    assert win_dacl.get_permissions(obj_name=str(tmp_path)) == perms

    # Now we create a directory for testing that does inherit those permissions from the above, new parent directory
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    current_user = win_functions.get_current_user(with_domain=False)
    assert win_dacl.get_owner(obj_name=str(test_dir)) == current_user
    # We do want the test directory to inherit permissions from the parent directory
    assert win_dacl.get_inheritance(obj_name=str(test_dir))
    # Make sure the permissions are inherited from the parent
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
