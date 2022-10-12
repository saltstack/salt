import pytest

pytest_plugins = [
    "tests.support.pytest.ldap",
]
pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_if_binaries_missing("docker"),
    pytest.mark.slow_test,
]


# These tests assume OpenLDAP returns attribute values in insertion order, which
# is not guaranteed but is the current behavior.  We could define a custom
# X-ORDERED attribute to enforce this, but that adds a lot of complexity and
# there are several awkward corner cases that make it impractical.


def test_managed_add_new_entry(openldap_minion_run, openldap_minion_apply, subtree):
    u1dn = f"cn=u1,{subtree}"
    entries = [
        {
            u1dn: [
                {
                    "add": {
                        "objectClass": ["person"],
                        # Note that this is not a list.  It should behave as if
                        # we passed the list ["u1"].
                        "cn": "u1",
                        # Note that this is not a list, nor is it a string.  It
                        # should behave as if we passed the list ["1234"]
                        # (numbers are stringified and then put in a list).
                        "sn": 1234,
                        # List of values of various types.
                        "description": [
                            "Non-ASCII characters should be supported: 🙂",
                            4567,
                            b"abcd",
                        ],
                        # Non-list iterable to exercise support for arbitrary
                        # iterables of values, not just lists.  Note that tuples
                        # are currently (as of 2022-10-23) serialized as lists,
                        # but this value is not serialized before it is
                        # processed by the minion.  (The state SLS file
                        # generated from this object by the
                        # openldap_minion_apply fixture is loaded on the minion
                        # and processed directly, not loaded on the master and
                        # sent to the minion in serialized form).
                        "userPassword": (
                            "password",
                            # Intentionally invalid UTF-8.  The syntax for
                            # userPassword is Octet String, not Directory String
                            # (like description), so this is acceptable.
                            b"\x00\x01\x02\x03\x80",
                        ),
                        # Empty list should be a no-op.
                        "telephoneNumber": [],
                        # None should be equivalent to an empty list.
                        "seeAlso": None,
                    },
                },
            ],
        },
    ]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {
            u1dn: {
                "old": None,
                "new": {
                    "objectClass": ["person"],
                    "cn": ["u1"],
                    "sn": ["1234"],
                    "description": [
                        "4567",
                        "Non-ASCII characters should be supported: 🙂",
                        "abcd",
                    ],
                    "userPassword": [
                        b"\x00\x01\x02\x03\x80",
                        "password",
                    ],
                },
            },
        },
        "comment": "Successfully updated LDAP entries",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u1dn) == {
        u1dn: {
            "objectClass": ["person"],
            "cn": ["u1"],
            "sn": ["1234"],
            "description": [
                "Non-ASCII characters should be supported: 🙂",
                "4567",
                "abcd",
            ],
            "userPassword": [
                "password",
                b"\x00\x01\x02\x03\x80",
            ],
        },
    }


def test_managed_add_new_attribute(openldap_minion_run, openldap_minion_apply, u0dn):
    entries = [{u0dn: [{"add": {"userPassword": ["p"]}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {u0dn: {"old": {}, "new": {"userPassword": ["p"]}}},
        "comment": "Successfully updated LDAP entries",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["desc", "another desc"],
            "userPassword": ["p"],
        },
    }


def test_managed_add_no_values_to_existing_attribute(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [{u0dn: [{"add": {"description": []}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {},
        "comment": "LDAP entries already set",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["desc", "another desc"],
        },
    }


def test_managed_add_no_values_to_new_attribute(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [{u0dn: [{"add": {"telephoneNumber": []}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {},
        "comment": "LDAP entries already set",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["desc", "another desc"],
        },
    }


def test_managed_add_new_value_to_existing_attribute(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [{u0dn: [{"add": {"description": ["and another"]}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {
            u0dn: {
                "old": {"description": ["another desc", "desc"]},
                "new": {"description": ["and another", "another desc", "desc"]},
            },
        },
        "comment": "Successfully updated LDAP entries",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["and another", "desc", "another desc"],
        },
    }


def test_managed_add_same_values_to_existing_attribute(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [{u0dn: [{"add": {"description": ["desc", "another desc"]}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {},
        "comment": "LDAP entries already set",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["desc", "another desc"],
        },
    }


def test_managed_add_overlapping_values(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [{u0dn: [{"add": {"description": ["desc", "and another"]}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {
            u0dn: {
                "old": {"description": ["another desc", "desc"]},
                "new": {"description": ["and another", "another desc", "desc"]},
            },
        },
        "comment": "Successfully updated LDAP entries",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["desc", "and another", "another desc"],
        },
    }


def test_managed_add_overlapping_values_different_order(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [{u0dn: [{"add": {"description": ["and another", "desc"]}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {
            u0dn: {
                "old": {"description": ["another desc", "desc"]},
                "new": {"description": ["and another", "another desc", "desc"]},
            },
        },
        "comment": "Successfully updated LDAP entries",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["and another", "desc", "another desc"],
        },
    }


def test_managed_add_repeated_values(openldap_minion_run, openldap_minion_apply, u0dn):
    entries = [{u0dn: [{"add": {"description": ["val", "val"]}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {
            u0dn: {
                "old": {"description": ["another desc", "desc"]},
                "new": {"description": ["another desc", "desc", "val"]},
            },
        },
        "comment": "Successfully updated LDAP entries",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["val", "desc", "another desc"],
        },
    }


def test_managed_replace_new_entry(openldap_minion_run, openldap_minion_apply, subtree):
    u1dn = f"cn=u1,{subtree}"
    entries = [
        {
            u1dn: [
                {
                    "replace": {
                        "objectClass": ["person"],
                        "cn": "u1",
                        "sn": "surname",
                    },
                },
            ],
        },
    ]
    want = {
        "objectClass": ["person"],
        "cn": ["u1"],
        "sn": ["surname"],
    }
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {u1dn: {"old": None, "new": want}},
        "comment": "Successfully updated LDAP entries",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u1dn) == {u1dn: want}


def test_managed_replace_new_attribute(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [{u0dn: [{"replace": {"userPassword": ["p"]}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {
            u0dn: {
                "old": {},
                "new": {"userPassword": ["p"]},
            },
        },
        "comment": "Successfully updated LDAP entries",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["desc", "another desc"],
            "userPassword": ["p"],
        },
    }


def test_managed_replace_no_value_for_one_attribute(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [{u0dn: [{"replace": {"description": []}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {
            u0dn: {
                "old": {"description": ["another desc", "desc"]},
                "new": {},
            },
        },
        "comment": "Successfully updated LDAP entries",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
        },
    }


def test_managed_replace_no_values_for_all_attributes(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [
        {
            u0dn: [
                {
                    "replace": {
                        "objectClass": [],
                        "cn": [],
                        "sn": [],
                        "description": [],
                    },
                },
            ],
        },
    ]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {
            u0dn: {
                "old": {
                    "objectClass": ["person"],
                    "cn": ["u0"],
                    "sn": ["Lastname"],
                    "description": ["another desc", "desc"],
                },
                "new": None,
            },
        },
        "comment": "Successfully updated LDAP entries",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {}


def test_managed_replace_no_values_for_new_attribute(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [{u0dn: [{"replace": {"userPassword": []}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {},
        "comment": "LDAP entries already set",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["desc", "another desc"],
        },
    }


def test_managed_replace_new_values(openldap_minion_run, openldap_minion_apply, u0dn):
    entries = [{u0dn: [{"replace": {"description": ["new desc"]}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {
            u0dn: {
                "old": {"description": ["another desc", "desc"]},
                "new": {"description": ["new desc"]},
            },
        },
        "comment": "Successfully updated LDAP entries",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["new desc"],
        },
    }


def test_managed_replace_same_values(openldap_minion_run, openldap_minion_apply, u0dn):
    entries = [{u0dn: [{"replace": {"description": ["desc", "another desc"]}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {},
        "comment": "LDAP entries already set",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["desc", "another desc"],
        },
    }


def test_managed_replace_overlapping_values(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [{u0dn: [{"replace": {"description": ["desc", "new desc"]}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {
            u0dn: {
                "old": {"description": ["another desc", "desc"]},
                "new": {"description": ["desc", "new desc"]},
            },
        },
        "comment": "Successfully updated LDAP entries",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["desc", "new desc"],
        },
    }


def test_managed_replace_overlapping_values_different_order(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [{u0dn: [{"replace": {"description": ["new desc", "desc"]}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {
            u0dn: {
                "old": {"description": ["another desc", "desc"]},
                "new": {"description": ["desc", "new desc"]},
            },
        },
        "comment": "Successfully updated LDAP entries",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["new desc", "desc"],
        },
    }


def test_managed_delete_value_from_nonexistent_entry(
    openldap_minion_run, openldap_minion_apply, subtree
):
    u1dn = f"cn=u1,{subtree}"
    entries = [{u1dn: [{"delete": {"description": ["foo"]}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {},
        "comment": "LDAP entries already set",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u1dn) == {}


def test_managed_delete_value_from_nonexistent_attribute(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [{u0dn: [{"delete": {"userPassword": ["foo"]}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {},
        "comment": "LDAP entries already set",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["desc", "another desc"],
        },
    }


def test_managed_delete_nonexistent_value(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [{u0dn: [{"delete": {"description": ["foo"]}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {},
        "comment": "LDAP entries already set",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["desc", "another desc"],
        },
    }


def test_managed_delete_all_values_from_nonexistent_entry(
    openldap_minion_run, openldap_minion_apply, subtree
):
    u1dn = f"cn=u1,{subtree}"
    entries = [{u1dn: [{"delete": {"description": []}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {},
        "comment": "LDAP entries already set",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u1dn) == {}


def test_managed_delete_all_values_from_nonexistent_attribute(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [{u0dn: [{"delete": {"userPassword": []}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {},
        "comment": "LDAP entries already set",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["desc", "another desc"],
        },
    }


def test_managed_delete_remaining_attribute_values(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [{u0dn: [{"delete": {"description": ["desc", "another desc"]}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {
            u0dn: {
                "old": {"description": ["another desc", "desc"]},
                "new": {},
            },
        },
        "comment": "Successfully updated LDAP entries",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
        },
    }


def test_managed_delete_all_attribute_values(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [{u0dn: [{"delete": {"description": []}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {
            u0dn: {
                "old": {"description": ["another desc", "desc"]},
                "new": {},
            },
        },
        "comment": "Successfully updated LDAP entries",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
        },
    }


def test_managed_delete_all_values_all_attributes(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [
        {
            u0dn: [
                {
                    "delete": {
                        "objectClass": [],
                        "cn": [],
                        "sn": [],
                        "description": [],
                    },
                },
            ],
        },
    ]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {
            u0dn: {
                "old": {
                    "objectClass": ["person"],
                    "cn": ["u0"],
                    "sn": ["Lastname"],
                    "description": ["another desc", "desc"],
                },
                "new": None,
            },
        },
        "comment": "Successfully updated LDAP entries",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {}


def test_managed_delete_remaining_values_all_attributes(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [
        {
            u0dn: [
                {
                    "delete": {
                        "objectClass": ["person"],
                        "cn": ["u0"],
                        "sn": ["Lastname"],
                        "description": ["desc", "another desc"],
                    },
                },
            ],
        },
    ]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {
            u0dn: {
                "old": {
                    "objectClass": ["person"],
                    "cn": ["u0"],
                    "sn": ["Lastname"],
                    "description": ["another desc", "desc"],
                },
                "new": None,
            },
        },
        "comment": "Successfully updated LDAP entries",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {}


def test_managed_delete_not_all_values(
    openldap_minion_run, openldap_minion_apply, u0dn
):
    entries = [{u0dn: [{"delete": {"description": ["another desc"]}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {
            u0dn: {
                "old": {"description": ["another desc", "desc"]},
                "new": {"description": ["desc"]},
            },
        },
        "comment": "Successfully updated LDAP entries",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["desc"],
        },
    }


def test_managed_delete_empty_dict(openldap_minion_run, openldap_minion_apply, u0dn):
    entries = [{u0dn: [{"delete": {}}]}]
    assert openldap_minion_apply("ldap.managed", entries=entries) == {
        "changes": {},
        "comment": "LDAP entries already set",
        "result": True,
    }
    assert openldap_minion_run("ldap3.search", base=u0dn) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["desc", "another desc"],
        },
    }
