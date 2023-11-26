import pytest

import salt.utils.win_dacl as win_dacl

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
]


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {
        win_dacl: {
            "__opts__": minion_opts,
        },
    }


@pytest.fixture(scope="function")
def test_file():
    with pytest.helpers.temp_file("dacl_test.file") as test_file:
        yield test_file


@pytest.fixture(scope="function")
def test_dir(tmp_path_factory):
    test_dir = tmp_path_factory.mktemp("test_dir")
    yield str(test_dir)
    test_dir.rmdir()


def test_get_set_owner(test_file):
    result = win_dacl.set_owner(
        obj_name=str(test_file), principal="Backup Operators", obj_type="file"
    )
    assert result is True
    result = win_dacl.get_owner(obj_name=str(test_file), obj_type="file")
    assert result == "Backup Operators"


def test_get_set_primary_group(test_file):
    result = win_dacl.set_primary_group(
        obj_name=str(test_file), principal="Backup Operators", obj_type="file"
    )
    assert result is True
    result = win_dacl.get_primary_group(obj_name=str(test_file), obj_type="file")
    assert result == "Backup Operators"


def test_get_set_permissions(test_file):
    result = win_dacl.set_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    expected = {
        "Not Inherited": {
            "Backup Operators": {
                "grant": {
                    "applies to": "This folder only",
                    "permissions": "Full control",
                }
            }
        }
    }
    result = win_dacl.get_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        obj_type="file",
    )
    assert result == expected


def test_applies_to_this_folder_only(test_dir):
    """
    #60103
    """
    result = win_dacl.set_permissions(
        obj_name=test_dir,
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        applies_to="this_folder_only",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    expected = {
        "Not Inherited": {
            "Backup Operators": {
                "grant": {
                    "applies to": "This folder only",
                    "permissions": "Full control",
                }
            }
        }
    }
    result = win_dacl.get_permissions(
        obj_name=test_dir,
        principal="Backup Operators",
        obj_type="file",
    )
    assert result == expected


def test_applies_to_this_folder_files(test_dir):
    """
    #60103
    """
    result = win_dacl.set_permissions(
        obj_name=test_dir,
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        applies_to="this_folder_files",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    expected = {
        "Not Inherited": {
            "Backup Operators": {
                "grant": {
                    "applies to": "This folder and files",
                    "permissions": "Full control",
                }
            }
        }
    }
    result = win_dacl.get_permissions(
        obj_name=test_dir,
        principal="Backup Operators",
        obj_type="file",
    )
    assert result == expected


def test_applies_to_this_folder_subfolders(test_dir):
    """
    #60103
    """
    result = win_dacl.set_permissions(
        obj_name=test_dir,
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        applies_to="this_folder_subfolders",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    expected = {
        "Not Inherited": {
            "Backup Operators": {
                "grant": {
                    "applies to": "This folder and subfolders",
                    "permissions": "Full control",
                }
            }
        }
    }
    result = win_dacl.get_permissions(
        obj_name=test_dir,
        principal="Backup Operators",
        obj_type="file",
    )
    assert result == expected


def test_applies_to_this_folder_subfolders_files(test_dir):
    """
    #60103
    """
    result = win_dacl.set_permissions(
        obj_name=test_dir,
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        applies_to="this_folder_subfolders_files",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    expected = {
        "Not Inherited": {
            "Backup Operators": {
                "grant": {
                    "applies to": "This folder, subfolders and files",
                    "permissions": "Full control",
                }
            }
        }
    }
    result = win_dacl.get_permissions(
        obj_name=test_dir,
        principal="Backup Operators",
        obj_type="file",
    )
    assert result == expected


def test_applies_to_files_only(test_dir):
    """
    #60103
    """
    result = win_dacl.set_permissions(
        obj_name=test_dir,
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        applies_to="files_only",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    expected = {
        "Not Inherited": {
            "Backup Operators": {
                "grant": {
                    "applies to": "Files only",
                    "permissions": "Full control",
                }
            }
        }
    }
    result = win_dacl.get_permissions(
        obj_name=test_dir,
        principal="Backup Operators",
        obj_type="file",
    )
    assert result == expected


def test_applies_to_subfolders_only(test_dir):
    """
    #60103
    """
    result = win_dacl.set_permissions(
        obj_name=test_dir,
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        applies_to="subfolders_only",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    expected = {
        "Not Inherited": {
            "Backup Operators": {
                "grant": {
                    "applies to": "Subfolders only",
                    "permissions": "Full control",
                }
            }
        }
    }
    result = win_dacl.get_permissions(
        obj_name=test_dir,
        principal="Backup Operators",
        obj_type="file",
    )
    assert result == expected


def test_applies_to_subfolders_files(test_dir):
    """
    #60103
    """
    result = win_dacl.set_permissions(
        obj_name=test_dir,
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        applies_to="subfolders_files",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    expected = {
        "Not Inherited": {
            "Backup Operators": {
                "grant": {
                    "applies to": "Subfolders and files only",
                    "permissions": "Full control",
                }
            }
        }
    }
    result = win_dacl.get_permissions(
        obj_name=test_dir,
        principal="Backup Operators",
        obj_type="file",
    )
    assert result == expected


def test_has_permission_exact_match(test_file):
    result = win_dacl.set_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    # Test has_permission exact
    result = win_dacl.has_permission(
        obj_name=str(test_file),
        principal="Backup Operators",
        permission="full_control",
        access_mode="grant",
        obj_type="file",
        exact=True,
    )
    assert result is True


def test_has_permission_exact_no_match(test_file):
    result = win_dacl.set_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    # Test has_permission exact
    result = win_dacl.has_permission(
        obj_name=str(test_file),
        principal="Backup Operators",
        permission="read",
        access_mode="grant",
        obj_type="file",
        exact=True,
    )
    assert result is False


def test_has_permission_contains(test_file):
    result = win_dacl.set_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    # Test has_permission exact
    result = win_dacl.has_permission(
        obj_name=str(test_file),
        principal="Backup Operators",
        permission="read",
        access_mode="grant",
        obj_type="file",
        exact=False,
    )
    assert result is True


def test_has_permission_contains_advanced(test_file):
    result = win_dacl.set_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    # Test has_permission exact
    result = win_dacl.has_permission(
        obj_name=str(test_file),
        principal="Backup Operators",
        permission="read_data",
        access_mode="grant",
        obj_type="file",
        exact=False,
    )
    assert result is True


def test_has_permission_missing(test_file):
    result = win_dacl.set_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions="read_execute",
        access_mode="grant",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    # Test has_permission not exact
    result = win_dacl.has_permission(
        obj_name=str(test_file),
        principal="Backup Operators",
        permission="write",
        access_mode="grant",
        obj_type="file",
        exact=False,
    )
    assert result is False


def test_has_permission_missing_advanced(test_file):
    result = win_dacl.set_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions="read_execute",
        access_mode="grant",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    # Test has_permission not exact
    result = win_dacl.has_permission(
        obj_name=str(test_file),
        principal="Backup Operators",
        permission="write_data",
        access_mode="grant",
        obj_type="file",
        exact=False,
    )


def test_has_permissions_contains(test_file):
    result = win_dacl.set_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    # Test has_permissions exact
    result = win_dacl.has_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions=["read", "write"],
        access_mode="grant",
        obj_type="file",
        exact=False,
    )
    assert result is True


def test_has_permissions_contains_advanced(test_file):
    result = win_dacl.set_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    # Test has_permissions exact
    result = win_dacl.has_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions=["read_data", "write_data"],
        access_mode="grant",
        obj_type="file",
        exact=False,
    )
    assert result is True


def test_has_permissions_missing(test_file):
    result = win_dacl.set_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions="read_execute",
        access_mode="grant",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    # Test has_permissions exact
    result = win_dacl.has_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions=["read_data", "write_data"],
        access_mode="grant",
        obj_type="file",
        exact=False,
    )
    assert result is False


def test_has_permissions_exact_contains(test_file):
    result = win_dacl.set_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions=["read_data", "write_data"],
        access_mode="grant",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    # Test has_permissions exact
    result = win_dacl.has_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions=["read_data", "write_data"],
        access_mode="grant",
        obj_type="file",
        exact=True,
    )
    assert result is True


def test_has_permissions_exact_has_extra(test_file):
    result = win_dacl.set_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions=["read_data", "write_data", "create_folders"],
        access_mode="grant",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    # Test has_permissions exact
    result = win_dacl.has_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions=["read_data", "write_data"],
        access_mode="grant",
        obj_type="file",
        exact=True,
    )
    assert result is False


def test_has_permissions_exact_missing(test_file):
    result = win_dacl.set_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions=["read_data", "write_data"],
        access_mode="grant",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    # Test has_permissions exact
    result = win_dacl.has_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions=["read_data", "write_data", "create_folders"],
        access_mode="grant",
        obj_type="file",
        exact=True,
    )
    assert result is False


def test_rm_permissions(test_file):
    result = win_dacl.set_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        obj_type="file",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    expected = {
        "Not Inherited": {
            "Backup Operators": {
                "grant": {
                    "applies to": "This folder only",
                    "permissions": "Full control",
                }
            }
        }
    }
    result = win_dacl.get_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        obj_type="file",
    )
    assert result == expected

    result = win_dacl.rm_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        obj_type="file",
    )
    assert result is True
    result = win_dacl.get_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        obj_type="file",
    )
    assert result == {}


def test_get_set_inheritance(test_file):
    result = win_dacl.set_inheritance(
        obj_name=str(test_file),
        enabled=True,
        obj_type="file",
        clear=False,
    )
    assert result is True

    result = win_dacl.get_inheritance(obj_name=str(test_file), obj_type="file")
    assert result is True

    result = win_dacl.set_inheritance(
        obj_name=str(test_file),
        enabled=False,
        obj_type="file",
        clear=False,
    )
    assert result is True

    result = win_dacl.get_inheritance(obj_name=str(test_file), obj_type="file")
    assert result is False


def test_copy_security():
    with pytest.helpers.temp_file("source_test.file") as source:
        # Set permissions on Source
        result = win_dacl.set_permissions(
            obj_name=str(source),
            principal="Backup Operators",
            permissions="full_control",
            access_mode="grant",
            obj_type="file",
            reset_perms=False,
            protected=None,
        )
        assert result is True

        # Set owner on Source
        result = win_dacl.set_owner(
            obj_name=str(source), principal="Backup Operators", obj_type="file"
        )
        assert result is True

        # Set group on Source
        result = win_dacl.set_primary_group(
            obj_name=str(source), principal="Backup Operators", obj_type="file"
        )
        assert result is True

        with pytest.helpers.temp_file("target_test.file") as target:
            # Copy security from Source to Target
            result = win_dacl.copy_security(source=str(source), target=str(target))
            assert result is True

            # Verify permissions on Target
            expected = {
                "Not Inherited": {
                    "Backup Operators": {
                        "grant": {
                            "applies to": "This folder only",
                            "permissions": "Full control",
                        }
                    }
                }
            }
            result = win_dacl.get_permissions(
                obj_name=str(target),
                principal="Backup Operators",
                obj_type="file",
            )
            assert result == expected

            # Verify owner on Target
            result = win_dacl.get_owner(obj_name=str(target), obj_type="file")
            assert result == "Backup Operators"

            # Verify group on Target
            result = win_dacl.get_primary_group(obj_name=str(target), obj_type="file")
            assert result == "Backup Operators"


def test_check_perms(test_file):
    result = win_dacl.check_perms(
        obj_name=str(test_file),
        obj_type="file",
        ret={},
        owner="Users",
        grant_perms={"Backup Operators": {"perms": "read"}},
        deny_perms={
            "Backup Operators": {"perms": ["delete"]},
            "NETWORK SERVICE": {
                "perms": [
                    "delete",
                    "change_permissions",
                    "write_attributes",
                    "write_data",
                ]
            },
        },
        inheritance=True,
        reset=False,
    )

    expected = {
        "changes": {
            "owner": "Users",
            "grant_perms": {"Backup Operators": {"permissions": "read"}},
            "deny_perms": {
                "Backup Operators": {"permissions": ["delete"]},
                "NETWORK SERVICE": {
                    "permissions": [
                        "delete",
                        "change_permissions",
                        "write_attributes",
                        "write_data",
                    ]
                },
            },
        },
        "comment": "",
        "name": str(test_file),
        "result": True,
    }
    assert result == expected

    expected = {
        "Not Inherited": {
            "Backup Operators": {
                "deny": {
                    "applies to": "This folder only",
                    "permissions": ["Delete"],
                },
                "grant": {"applies to": "This folder only", "permissions": "Read"},
            }
        }
    }
    result = win_dacl.get_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        obj_type="file",
    )
    assert result == expected

    expected = {
        "Not Inherited": {
            "NETWORK SERVICE": {
                "deny": {
                    "applies to": "This folder only",
                    "permissions": [
                        "Change permissions",
                        "Create files / write data",
                        "Delete",
                        "Write attributes",
                    ],
                }
            }
        }
    }
    result = win_dacl.get_permissions(
        obj_name=str(test_file),
        principal="NETWORK SERVICE",
        obj_type="file",
    )
    assert result == expected

    result = win_dacl.get_owner(obj_name=str(test_file), obj_type="file")
    assert result == "Users"


def test_check_perms_test_true(test_file):
    result = win_dacl.check_perms(
        obj_name=str(test_file),
        obj_type="file",
        ret=None,
        owner="Users",
        grant_perms={"Backup Operators": {"perms": "read"}},
        deny_perms={
            "NETWORK SERVICE": {
                "perms": ["delete", "set_value", "write_dac", "write_owner"]
            },
            "Backup Operators": {"perms": ["delete"]},
        },
        inheritance=True,
        reset=False,
        test_mode=True,
    )

    expected = {
        "changes": {
            "owner": "Users",
            "grant_perms": {"Backup Operators": {"permissions": "read"}},
            "deny_perms": {
                "Backup Operators": {"permissions": ["delete"]},
                "NETWORK SERVICE": {
                    "permissions": [
                        "delete",
                        "set_value",
                        "write_dac",
                        "write_owner",
                    ]
                },
            },
        },
        "comment": "",
        "name": str(test_file),
        "result": None,
    }
    assert result == expected

    result = win_dacl.get_owner(obj_name=str(test_file), obj_type="file")
    assert result != "Users"

    result = win_dacl.get_permissions(
        obj_name=str(test_file),
        principal="Backup Operators",
        obj_type="file",
    )
    assert result == {}


def test_set_perms(test_file):
    result = win_dacl.set_perms(
        obj_name=str(test_file),
        obj_type="file",
        grant_perms={"Backup Operators": {"perms": "read"}},
        deny_perms={
            "NETWORK SERVICE": {
                "perms": [
                    "delete",
                    "change_permissions",
                    "write_attributes",
                    "write_data",
                ]
            }
        },
        inheritance=True,
        reset=False,
    )

    expected = {
        "deny": {
            "NETWORK SERVICE": {
                "perms": [
                    "delete",
                    "change_permissions",
                    "write_attributes",
                    "write_data",
                ]
            }
        },
        "grant": {"Backup Operators": {"perms": "read"}},
    }
    assert result == expected
