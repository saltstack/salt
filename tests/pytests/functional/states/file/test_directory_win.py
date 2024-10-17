import pytest

import salt.utils.win_dacl as win_dacl

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
]


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


def test_directory_new(file, temp_path):
    """
    Test file.directory when the directory does not exist
    Should just return "New Dir"
    """
    path = str(temp_path / "test")
    ret = file.directory(
        name=path,
        makedirs=True,
        win_perms={"Administrators": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": "full_control"}},
    )
    expected = {path: {"directory": "new"}}
    assert ret["changes"] == expected
    permissions = win_dacl.get_permissions(path)
    expected = {
        "Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
        },
        "Not Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "Guest": {
                "deny": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
        },
    }
    assert permissions == expected


def test_directory_new_no_inherit(file, temp_path):
    """
    Test file.directory when the directory does not exist
    Should just return "New Dir"
    """
    path = str(temp_path / "test")
    ret = file.directory(
        name=path,
        makedirs=True,
        win_perms={"Administrators": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": "full_control"}},
        win_inheritance=False,
    )
    expected = {path: {"directory": "new"}}
    assert ret["changes"] == expected
    assert not win_dacl.get_inheritance(path)
    permissions = win_dacl.get_permissions(path)
    assert permissions["Inherited"] == {}


def test_directory_new_reset(file, temp_path):
    """
    Test file.directory when the directory does not exist
    Should just return "New Dir"
    """
    path = str(temp_path / "test")
    ret = file.directory(
        name=path,
        makedirs=True,
        win_perms={"Administrators": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": "full_control"}},
        win_perms_reset=True,
    )
    expected = {path: {"directory": "new"}}
    assert ret["changes"] == expected
    permissions = win_dacl.get_permissions(path)
    expected = {
        "Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
        },
        "Not Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "Guest": {
                "deny": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
        },
    }
    assert permissions == expected


def test_directory_new_reset_no_inherit(file, temp_path):
    """
    Test file.directory when the directory does not exist
    Should just return "New Dir"
    """
    path = str(temp_path / "test")
    ret = file.directory(
        name=path,
        makedirs=True,
        win_perms={"Administrators": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": "full_control"}},
        win_inheritance=False,
        win_perms_reset=True,
    )
    expected = {path: {"directory": "new"}}
    assert ret["changes"] == expected
    permissions = win_dacl.get_permissions(path)
    expected = {
        "Inherited": {},
        "Not Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "Guest": {
                "deny": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
        },
    }
    assert permissions == expected


def test_directory_existing(file, temp_path):
    path = str(temp_path)
    ret = file.directory(
        name=path,
        makedirs=True,
        win_perms={"Everyone": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": ["write_data", "write_attributes"]}},
    )
    expected = {
        "deny_perms": {"Guest": {"permissions": ["write_data", "write_attributes"]}},
        "grant_perms": {"Everyone": {"permissions": "full_control"}},
    }
    # Sometimes an owner will be set, we don't care about the owner
    ret["changes"].pop("owner", None)
    assert ret["changes"] == expected
    permissions = win_dacl.get_permissions(path)
    expected = {
        "Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
        },
        "Not Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "Everyone": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "Guest": {
                "deny": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": ["Create files / write data", "Write attributes"],
                }
            },
        },
    }
    assert permissions == expected


def test_directory_existing_existing_user(file, temp_path):
    path = str(temp_path)
    win_dacl.set_permissions(
        obj_name=path,
        principal="Everyone",
        permissions=["write_data", "write_attributes"],
        access_mode="grant",
        reset_perms=True,
    )
    ret = file.directory(
        name=path,
        makedirs=True,
        win_perms={"Everyone": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": ["write_data", "write_attributes"]}},
    )
    expected = {
        "deny_perms": {"Guest": {"permissions": ["write_data", "write_attributes"]}},
        "grant_perms": {"Everyone": {"permissions": "full_control"}},
    }
    # Sometimes an owner will be set, we don't care about the owner
    ret["changes"].pop("owner", None)
    assert ret["changes"] == expected
    permissions = win_dacl.get_permissions(path)
    expected = {
        "Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
        },
        "Not Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "Everyone": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "Guest": {
                "deny": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": ["Create files / write data", "Write attributes"],
                }
            },
        },
    }
    assert permissions == expected


def test_directory_existing_no_inherit(file, temp_path):
    path = str(temp_path)
    ret = file.directory(
        name=path,
        makedirs=True,
        win_perms={"Everyone": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": ["write_data", "write_attributes"]}},
        win_inheritance=False,
    )
    expected = {
        "deny_perms": {"Guest": {"permissions": ["write_data", "write_attributes"]}},
        "grant_perms": {"Everyone": {"permissions": "full_control"}},
        "inheritance": False,
    }
    # Sometimes an owner will be set, we don't care about the owner
    ret["changes"].pop("owner", None)
    assert ret["changes"] == expected
    assert not win_dacl.get_inheritance(path)
    permissions = win_dacl.get_permissions(path)
    assert permissions["Inherited"] == {}


def test_directory_existing_reset(file, temp_path):
    path = str(temp_path)
    win_dacl.set_permissions(
        obj_name=path,
        principal="Guest",
        permissions=["write_data", "write_attributes"],
        access_mode="deny",
        reset_perms=True,
    )
    ret = file.directory(
        name=path,
        makedirs=True,
        win_perms={"Everyone": {"perms": "full_control"}},
        win_perms_reset=True,
    )
    expected = {
        "grant_perms": {"Everyone": {"permissions": "full_control"}},
        "remove_perms": {
            "Guest": {
                "deny": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": ["Create files / write data", "Write attributes"],
                }
            }
        },
    }
    # Sometimes an owner will be set, we don't care about the owner
    ret["changes"].pop("owner", None)
    assert ret["changes"] == expected
    permissions = win_dacl.get_permissions(path)
    expected = {
        "Inherited": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
        },
        "Not Inherited": {
            "Everyone": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
        },
    }
    assert permissions == expected


def test_directory_existing_reset_no_inherit(file, temp_path):
    path = str(temp_path)
    ret = file.directory(
        name=path,
        makedirs=True,
        win_perms={"Everyone": {"perms": "full_control"}},
        win_deny_perms={"Guest": {"perms": ["write_data", "write_attributes"]}},
        win_perms_reset=True,
        win_inheritance=False,
    )

    expected = {
        "deny_perms": {"Guest": {"permissions": ["write_data", "write_attributes"]}},
        "grant_perms": {"Everyone": {"permissions": "full_control"}},
        "inheritance": False,
        "remove_perms": {
            "Administrators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                },
            },
        },
    }
    # Sometimes an owner will be set, we don't care about the owner
    ret["changes"].pop("owner", None)
    assert ret["changes"] == expected

    permissions = win_dacl.get_permissions(path)
    expected = {
        "Inherited": {},
        "Not Inherited": {
            "Everyone": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            },
            "Guest": {
                "deny": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": ["Create files / write data", "Write attributes"],
                }
            },
        },
    }
    assert permissions == expected
