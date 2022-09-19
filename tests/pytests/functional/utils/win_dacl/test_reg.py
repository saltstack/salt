import pytest
from saltfactories.utils import random_string

import salt.utils.win_dacl as win_dacl
import salt.utils.win_reg as win_reg
from tests.support.mock import patch

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


@pytest.fixture(scope="module")
def fake_key():
    return "SOFTWARE\\{}".format(random_string("SaltTesting-", lowercase=False))


@pytest.fixture(scope="function")
def reg_key(fake_key):
    win_reg.set_value(hive="HKLM", key=fake_key, vname="fake_name", vdata="fake_data")
    yield "HKLM\\{}".format(fake_key)
    win_reg.delete_key_recursive(hive="HKLM", key=fake_key)


def test_get_set_owner(reg_key):
    result = win_dacl.set_owner(
        obj_name=reg_key, principal="Backup Operators", obj_type="registry"
    )
    assert result is True
    result = win_dacl.get_owner(obj_name=reg_key, obj_type="registry")
    assert result == "Backup Operators"


def test_get_set_primary_group(reg_key):
    result = win_dacl.set_primary_group(
        obj_name=reg_key, principal="Backup Operators", obj_type="registry"
    )
    assert result is True
    result = win_dacl.get_primary_group(obj_name=reg_key, obj_type="registry")
    assert result == "Backup Operators"


def test_get_set_permissions(reg_key):
    result = win_dacl.set_permissions(
        obj_name=reg_key,
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        obj_type="registry",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    expected = {
        "Not Inherited": {
            "Backup Operators": {
                "grant": {
                    "applies to": "This key and subkeys",
                    "permissions": "Full Control",
                }
            }
        }
    }
    result = win_dacl.get_permissions(
        obj_name=reg_key,
        principal="Backup Operators",
        obj_type="registry",
    )
    assert result == expected


def test_applies_to_this_key_only(reg_key):
    """
    #60103
    """
    result = win_dacl.set_permissions(
        obj_name=reg_key,
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        applies_to="this_key_only",
        obj_type="registry",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    expected = {
        "Not Inherited": {
            "Backup Operators": {
                "grant": {
                    "applies to": "This key only",
                    "permissions": "Full Control",
                }
            }
        }
    }
    result = win_dacl.get_permissions(
        obj_name=reg_key,
        principal="Backup Operators",
        obj_type="registry",
    )
    assert result == expected


def test_applies_to_this_key_subkeys(reg_key):
    """
    #60103
    """
    result = win_dacl.set_permissions(
        obj_name=reg_key,
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        applies_to="this_key_subkeys",
        obj_type="registry",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    expected = {
        "Not Inherited": {
            "Backup Operators": {
                "grant": {
                    "applies to": "This key and subkeys",
                    "permissions": "Full Control",
                }
            }
        }
    }
    result = win_dacl.get_permissions(
        obj_name=reg_key,
        principal="Backup Operators",
        obj_type="registry",
    )
    assert result == expected


def test_applies_to_subkeys_only(reg_key):
    """
    #60103
    """
    result = win_dacl.set_permissions(
        obj_name=reg_key,
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        applies_to="subkeys_only",
        obj_type="registry",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    expected = {
        "Not Inherited": {
            "Backup Operators": {
                "grant": {
                    "applies to": "Subkeys only",
                    "permissions": "Full Control",
                }
            }
        }
    }
    result = win_dacl.get_permissions(
        obj_name=reg_key,
        principal="Backup Operators",
        obj_type="registry",
    )
    assert result == expected


def test_has_permission_exact_true(reg_key):
    result = win_dacl.set_permissions(
        obj_name=reg_key,
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        obj_type="registry",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    # Test has_permission exact
    result = win_dacl.has_permission(
        obj_name=reg_key,
        principal="Backup Operators",
        permission="full_control",
        access_mode="grant",
        obj_type="registry",
        exact=True,
    )
    assert result is True


def test_has_permission_exact_false(reg_key):
    result = win_dacl.set_permissions(
        obj_name=reg_key,
        principal="Backup Operators",
        permissions="read",
        access_mode="grant",
        obj_type="registry",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    # Test has_permission exact
    result = win_dacl.has_permission(
        obj_name=reg_key,
        principal="Backup Operators",
        permission="full_control",
        access_mode="grant",
        obj_type="registry",
        exact=True,
    )
    assert result is False


def test_has_permission_contains_true(reg_key):
    result = win_dacl.set_permissions(
        obj_name=reg_key,
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        obj_type="registry",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    # Test has_permission exact
    result = win_dacl.has_permission(
        obj_name=reg_key,
        principal="Backup Operators",
        permission="read",
        access_mode="grant",
        obj_type="registry",
        exact=False,
    )
    assert result is True


def test_has_permission_contains_false(reg_key):
    result = win_dacl.set_permissions(
        obj_name=reg_key,
        principal="Backup Operators",
        permissions="read",
        access_mode="grant",
        obj_type="registry",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    # Test has_permission exact
    result = win_dacl.has_permission(
        obj_name=reg_key,
        principal="Backup Operators",
        permission="write",
        access_mode="grant",
        obj_type="registry",
        exact=False,
    )
    assert result is False


def test_rm_permissions(reg_key):
    result = win_dacl.set_permissions(
        obj_name=reg_key,
        principal="Backup Operators",
        permissions="full_control",
        access_mode="grant",
        obj_type="registry",
        reset_perms=False,
        protected=None,
    )
    assert result is True

    expected = {
        "Not Inherited": {
            "Backup Operators": {
                "grant": {
                    "applies to": "This key and subkeys",
                    "permissions": "Full Control",
                }
            }
        }
    }
    result = win_dacl.get_permissions(
        obj_name=reg_key,
        principal="Backup Operators",
        obj_type="registry",
    )
    assert result == expected

    result = win_dacl.rm_permissions(
        obj_name=reg_key,
        principal="Backup Operators",
        obj_type="registry",
    )
    assert result is True
    result = win_dacl.get_permissions(
        obj_name=reg_key,
        principal="Backup Operators",
        obj_type="registry",
    )
    assert result == {}


def test_get_set_inheritance(reg_key):
    result = win_dacl.set_inheritance(
        obj_name=reg_key,
        enabled=True,
        obj_type="registry",
        clear=False,
    )
    assert result is True

    result = win_dacl.get_inheritance(obj_name=reg_key, obj_type="registry")
    assert result is True

    result = win_dacl.set_inheritance(
        obj_name=reg_key,
        enabled=False,
        obj_type="registry",
        clear=False,
    )
    assert result is True

    result = win_dacl.get_inheritance(obj_name=reg_key, obj_type="registry")
    assert result is False


def test_check_perms(reg_key):
    result = win_dacl.check_perms(
        obj_name=reg_key,
        obj_type="registry",
        ret={},
        owner="Users",
        grant_perms={"Backup Operators": {"perms": "read"}},
        deny_perms={
            "Backup Operators": {"perms": ["delete"]},
            "NETWORK SERVICE": {
                "perms": ["delete", "set_value", "write_dac", "write_owner"]
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
                        "set_value",
                        "write_dac",
                        "write_owner",
                    ]
                },
            },
        },
        "comment": "",
        "name": reg_key,
        "result": True,
    }
    assert result == expected

    expected = {
        "Not Inherited": {
            "Backup Operators": {
                "grant": {
                    "applies to": "This key and subkeys",
                    "permissions": "Read",
                },
                "deny": {
                    "applies to": "This key and subkeys",
                    "permissions": ["Delete"],
                },
            }
        }
    }
    result = win_dacl.get_permissions(
        obj_name=reg_key,
        principal="Backup Operators",
        obj_type="registry",
    )
    assert result == expected

    expected = {
        "Not Inherited": {
            "NETWORK SERVICE": {
                "deny": {
                    "applies to": "This key and subkeys",
                    "permissions": [
                        "Delete",
                        "Set Value",
                        "Write DAC",
                        "Write Owner",
                    ],
                }
            }
        }
    }
    result = win_dacl.get_permissions(
        obj_name=reg_key,
        principal="NETWORK SERVICE",
        obj_type="registry",
    )
    assert result == expected

    result = win_dacl.get_owner(obj_name=reg_key, obj_type="registry")
    assert result == "Users"


def test_check_perms_test_true(reg_key):
    with patch.dict(win_dacl.__opts__, {"test": True}):
        result = win_dacl.check_perms(
            obj_name=reg_key,
            obj_type="registry",
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
        "name": reg_key,
        "result": None,
    }
    assert result == expected

    result = win_dacl.get_owner(obj_name=reg_key, obj_type="registry")
    assert result != "Users"

    result = win_dacl.get_permissions(
        obj_name=reg_key,
        principal="Backup Operators",
        obj_type="registry",
    )
    assert result == {}


def test_set_perms(reg_key):
    result = win_dacl.set_perms(
        obj_name=reg_key,
        obj_type="registry",
        grant_perms={"Backup Operators": {"perms": "read"}},
        deny_perms={
            "NETWORK SERVICE": {
                "perms": ["delete", "set_value", "write_dac", "write_owner"]
            }
        },
        inheritance=True,
        reset=False,
    )

    expected = {
        "deny": {
            "NETWORK SERVICE": {
                "perms": ["delete", "set_value", "write_dac", "write_owner"]
            }
        },
        "grant": {"Backup Operators": {"perms": "read"}},
    }
    assert result == expected
