"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.states.linux_acl
"""

import pytest

import salt.states.linux_acl as linux_acl
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skip_unless_on_linux(
        reason="Only run on Linux",
    )
]


@pytest.fixture
def configure_loader_modules():
    return {linux_acl: {}}


def test_present():
    """
    Test to ensure a Linux ACL is present
    """
    maxDiff = None
    name = "/root"
    acl_type = "users"
    acl_name = "damian"
    perms = "rwx"

    mock = MagicMock(
        side_effect=[
            {name: {acl_type: [{acl_name: {"octal": 5}}]}},
            {name: {acl_type: [{acl_name: {"octal": 5}}]}},
            {name: {acl_type: [{acl_name: {"octal": 5}}]}},
            {name: {acl_type: [{}]}},
            {name: {acl_type: [{}]}},
            {name: {acl_type: [{}]}},
            {
                name: {acl_type: [{acl_name: {"octal": 7}}]},
                name + "/foo": {acl_type: [{acl_name: {"octal": 5}}]},
            },
            {
                name: {acl_type: [{acl_name: {"octal": 7}}]},
                name + "/foo": {acl_type: [{acl_name: {"octal": 7}}]},
            },
            {name: {acl_type: ""}},
            {
                name: {"defaults": {"users": [{acl_name: {"octal": 7}}]}},
                name + "/foo": {"defaults": {"users": [{acl_name: {"octal": 7}}]}},
            },
            {
                name: {"defaults": {"users": [{acl_name: {"octal": 7}}]}},
                name + "/foo": {"defaults": {"users": [{acl_name: {"octal": 7}}]}},
            },
            {
                name: {"defaults": {"users": [{acl_name: {"octal": 7}}]}},
                name + "/foo": {"defaults": {"users": [{acl_name: {"octal": 7}}]}},
            },
        ]
    )
    mock_modfacl = MagicMock(return_value=True)

    with patch.dict(linux_acl.__salt__, {"acl.getfacl": mock}):
        # Update - test=True
        with patch.dict(linux_acl.__opts__, {"test": True}):
            comt = "Updated permissions will be applied for {}: r-x -> {}".format(
                acl_name, perms
            )
            ret = {
                "name": name,
                "comment": comt,
                "changes": {
                    "new": {
                        "acl_name": acl_name,
                        "acl_type": acl_type,
                        "perms": perms,
                    },
                    "old": {
                        "acl_name": acl_name,
                        "acl_type": acl_type,
                        "perms": "r-x",
                    },
                },
                "result": None,
            }

            assert linux_acl.present(name, acl_type, acl_name, perms) == ret
        # Update - test=False
        with patch.dict(linux_acl.__salt__, {"acl.modfacl": mock_modfacl}):
            with patch.dict(linux_acl.__opts__, {"test": False}):
                comt = f"Updated permissions for {acl_name}"
                ret = {
                    "name": name,
                    "comment": comt,
                    "changes": {
                        "new": {
                            "acl_name": acl_name,
                            "acl_type": acl_type,
                            "perms": perms,
                        },
                        "old": {
                            "acl_name": acl_name,
                            "acl_type": acl_type,
                            "perms": "r-x",
                        },
                    },
                    "result": True,
                }
                assert linux_acl.present(name, acl_type, acl_name, perms) == ret
        # Update - modfacl error
        with patch.dict(
            linux_acl.__salt__,
            {"acl.modfacl": MagicMock(side_effect=CommandExecutionError("Custom err"))},
        ):
            with patch.dict(linux_acl.__opts__, {"test": False}):
                comt = f"Error updating permissions for {acl_name}: Custom err"
                ret = {
                    "name": name,
                    "comment": comt,
                    "changes": {},
                    "result": False,
                }
                assert linux_acl.present(name, acl_type, acl_name, perms) == ret
        # New - test=True
        with patch.dict(linux_acl.__salt__, {"acl.modfacl": mock_modfacl}):
            with patch.dict(linux_acl.__opts__, {"test": True}):
                comt = "New permissions will be applied for {}: {}".format(
                    acl_name, perms
                )
                ret = {
                    "name": name,
                    "comment": comt,
                    "changes": {
                        "new": {
                            "acl_name": acl_name,
                            "acl_type": acl_type,
                            "perms": perms,
                        }
                    },
                    "result": None,
                }
                assert linux_acl.present(name, acl_type, acl_name, perms) == ret
        # New - test=False
        with patch.dict(linux_acl.__salt__, {"acl.modfacl": mock_modfacl}):
            with patch.dict(linux_acl.__opts__, {"test": False}):
                comt = f"Applied new permissions for {acl_name}"
                ret = {
                    "name": name,
                    "comment": comt,
                    "changes": {
                        "new": {
                            "acl_name": acl_name,
                            "acl_type": acl_type,
                            "perms": perms,
                        }
                    },
                    "result": True,
                }
                assert linux_acl.present(name, acl_type, acl_name, perms) == ret
        # New - modfacl error
        with patch.dict(
            linux_acl.__salt__,
            {"acl.modfacl": MagicMock(side_effect=CommandExecutionError("Custom err"))},
        ):
            with patch.dict(linux_acl.__opts__, {"test": False}):
                comt = f"Error updating permissions for {acl_name}: Custom err"
                ret = {
                    "name": name,
                    "comment": comt,
                    "changes": {},
                    "result": False,
                }
                assert linux_acl.present(name, acl_type, acl_name, perms) == ret

        # New - recurse true
        with patch.dict(linux_acl.__salt__, {"acl.getfacl": mock}):
            # Update - test=True
            with patch.dict(linux_acl.__opts__, {"test": True}):
                comt = "Updated permissions will be applied for {}: rwx -> {}".format(
                    acl_name, perms
                )
                ret = {
                    "name": name,
                    "comment": comt,
                    "changes": {
                        "new": {
                            "acl_name": acl_name,
                            "acl_type": acl_type,
                            "perms": perms,
                        },
                        "old": {
                            "acl_name": acl_name,
                            "acl_type": acl_type,
                            "perms": "rwx",
                        },
                    },
                    "result": None,
                }

                assert (
                    linux_acl.present(name, acl_type, acl_name, perms, recurse=True)
                    == ret
                )

        # New - recurse true - nothing to do
        with patch.dict(linux_acl.__salt__, {"acl.getfacl": mock}):
            # Update - test=True
            with patch.dict(linux_acl.__opts__, {"test": True}):
                comt = "Permissions are in the desired state"
                ret = {"name": name, "comment": comt, "changes": {}, "result": True}

                assert (
                    linux_acl.present(name, acl_type, acl_name, perms, recurse=True)
                    == ret
                )

        # No acl type
        comt = "ACL Type does not exist"
        ret = {"name": name, "comment": comt, "result": False, "changes": {}}
        assert linux_acl.present(name, acl_type, acl_name, perms) == ret

        # default recurse false - nothing to do
        with patch.dict(linux_acl.__salt__, {"acl.getfacl": mock}):
            # Update - test=True
            with patch.dict(linux_acl.__opts__, {"test": True}):
                comt = "Permissions are in the desired state"
                ret = {"name": name, "comment": comt, "changes": {}, "result": True}

                assert (
                    linux_acl.present(
                        name, "d:" + acl_type, acl_name, perms, recurse=False
                    )
                    == ret
                )

        # default recurse false - nothing to do
        with patch.dict(linux_acl.__salt__, {"acl.getfacl": mock}):
            # Update - test=True
            with patch.dict(linux_acl.__opts__, {"test": True}):
                comt = "Permissions are in the desired state"
                ret = {"name": name, "comment": comt, "changes": {}, "result": True}

                assert (
                    linux_acl.present(
                        name, "d:" + acl_type, acl_name, perms, recurse=False
                    )
                    == ret
                )

        # default recurse true - nothing to do
        with patch.dict(linux_acl.__salt__, {"acl.getfacl": mock}):
            # Update - test=True
            with patch.dict(linux_acl.__opts__, {"test": True}):
                comt = "Permissions are in the desired state"
                ret = {"name": name, "comment": comt, "changes": {}, "result": True}

                assert (
                    linux_acl.present(
                        name, "d:" + acl_type, acl_name, perms, recurse=True
                    )
                    == ret
                )


def test_absent():
    """
    Test to ensure a Linux ACL does not exist
    """
    name = "/root"
    acl_type = "users"
    acl_name = "damian"
    perms = "rwx"

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    mock = MagicMock(
        side_effect=[
            {name: {acl_type: [{acl_name: {"octal": "A"}}]}},
            {name: {acl_type: ""}},
        ]
    )
    with patch.dict(linux_acl.__salt__, {"acl.getfacl": mock}):
        with patch.dict(linux_acl.__opts__, {"test": True}):
            comt = "Removing permissions"
            ret.update({"comment": comt})
            assert linux_acl.absent(name, acl_type, acl_name, perms) == ret

        comt = "ACL Type does not exist"
        ret.update({"comment": comt, "result": False})
        assert linux_acl.absent(name, acl_type, acl_name, perms) == ret


def test_list_present():
    """
    Test to ensure a Linux ACL is present
    """
    name = "/root"
    acl_type = "user"
    acl_names = ["root", "damian", "homer"]
    acl_comment = {"owner": "root", "group": "root", "file": "/root"}
    perms = "rwx"

    mock = MagicMock(
        side_effect=[
            {
                name: {
                    acl_type: [
                        {acl_names[0]: {"octal": "A"}},
                        {acl_names[1]: {"octal": "A"}},
                        {acl_names[2]: {"octal": "A"}},
                    ],
                    "comment": acl_comment,
                }
            },
            {
                name: {
                    acl_type: [
                        {acl_names[0]: {"octal": "A"}},
                        {acl_names[1]: {"octal": "A"}},
                    ],
                    "comment": acl_comment,
                }
            },
            {
                name: {
                    acl_type: [
                        {acl_names[0]: {"octal": "A"}},
                        {acl_names[1]: {"octal": "A"}},
                    ]
                }
            },
            {name: {acl_type: [{}]}},
            {name: {acl_type: [{}]}},
            {name: {acl_type: [{}]}},
            {name: {acl_type: ""}},
        ]
    )
    mock_modfacl = MagicMock(return_value=True)

    with patch.dict(linux_acl.__salt__, {"acl.getfacl": mock}):
        # Update - test=True
        with patch.dict(linux_acl.__opts__, {"test": True}):
            comt = "Updated permissions will be applied for {}: A -> {}".format(
                acl_names, perms
            )
            expected = {
                "name": name,
                "comment": comt,
                "changes": {
                    "new": {
                        "acl_name": ", ".join(acl_names),
                        "acl_type": acl_type,
                        "perms": 7,
                    },
                    "old": {
                        "acl_name": ", ".join(acl_names),
                        "acl_type": acl_type,
                        "perms": "A",
                    },
                },
                "result": None,
            }

            ret = linux_acl.list_present(name, acl_type, acl_names, perms)
            assert ret == expected

        # Update - test=False
        with patch.dict(linux_acl.__salt__, {"acl.modfacl": mock_modfacl}):
            with patch.dict(linux_acl.__opts__, {"test": False}):
                comt = "Applied new permissions for {}".format(", ".join(acl_names))
                expected = {
                    "name": name,
                    "comment": comt,
                    "changes": {
                        "new": {
                            "acl_name": ", ".join(acl_names),
                            "acl_type": acl_type,
                            "perms": "rwx",
                        }
                    },
                    "result": True,
                }

                ret = linux_acl.list_present(name, acl_type, acl_names, perms)
                assert expected == ret

        # Update - modfacl error
        with patch.dict(
            linux_acl.__salt__,
            {"acl.modfacl": MagicMock(side_effect=CommandExecutionError("Custom err"))},
        ):
            with patch.dict(linux_acl.__opts__, {"test": False}):
                comt = f"Error updating permissions for {acl_names}: Custom err"
                expected = {
                    "name": name,
                    "comment": comt,
                    "changes": {},
                    "result": False,
                }

                ret = linux_acl.list_present(name, acl_type, acl_names, perms)
                assert expected == ret

        # New - test=True
        with patch.dict(linux_acl.__salt__, {"acl.modfacl": mock_modfacl}):
            with patch.dict(linux_acl.__opts__, {"test": True}):
                comt = "New permissions will be applied for {}: {}".format(
                    acl_names, perms
                )
                expected = {
                    "name": name,
                    "comment": comt,
                    "changes": {
                        "new": {
                            "acl_name": ", ".join(acl_names),
                            "acl_type": acl_type,
                            "perms": perms,
                        }
                    },
                    "result": None,
                }

                ret = linux_acl.list_present(name, acl_type, acl_names, perms)
                assert expected == ret

        # New - test=False
        with patch.dict(linux_acl.__salt__, {"acl.modfacl": mock_modfacl}):
            with patch.dict(linux_acl.__opts__, {"test": False}):
                comt = "Applied new permissions for {}".format(", ".join(acl_names))
                expected = {
                    "name": name,
                    "comment": comt,
                    "changes": {
                        "new": {
                            "acl_name": ", ".join(acl_names),
                            "acl_type": acl_type,
                            "perms": perms,
                        }
                    },
                    "result": True,
                }
                ret = linux_acl.list_present(name, acl_type, acl_names, perms)
                assert expected == ret

        # New - modfacl error
        with patch.dict(
            linux_acl.__salt__,
            {"acl.modfacl": MagicMock(side_effect=CommandExecutionError("Custom err"))},
        ):
            with patch.dict(linux_acl.__opts__, {"test": False}):
                comt = f"Error updating permissions for {acl_names}: Custom err"
                expected = {
                    "name": name,
                    "comment": comt,
                    "changes": {},
                    "result": False,
                }

                ret = linux_acl.list_present(name, acl_type, acl_names, perms)
                assert expected == ret

        # No acl type
        comt = "ACL Type does not exist"
        expected = {
            "name": name,
            "comment": comt,
            "result": False,
            "changes": {},
        }
        ret = linux_acl.list_present(name, acl_type, acl_names, perms)
        assert expected == ret


def test_list_absent():
    """
    Test to ensure a Linux ACL does not exist
    """
    name = "/root"
    acl_type = "users"
    acl_names = ["damian", "homer"]
    perms = "rwx"

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    mock = MagicMock(
        side_effect=[
            {
                name: {
                    acl_type: [
                        {acl_names[0]: {"octal": "A"}, acl_names[1]: {"octal": "A"}}
                    ]
                }
            },
            {name: {acl_type: ""}},
        ]
    )
    with patch.dict(linux_acl.__salt__, {"acl.getfacl": mock}):
        with patch.dict(linux_acl.__opts__, {"test": True}):
            comt = "Removing permissions"
            ret.update({"comment": comt})
            assert linux_acl.list_absent(name, acl_type, acl_names, perms) == ret

        comt = "ACL Type does not exist"
        ret.update({"comment": comt, "result": False})
        assert linux_acl.list_absent(name, acl_type, acl_names) == ret


def test_absent_recursive():
    """
    Test to ensure a Linux ACL does not exist
    """
    name = "/root"
    acl_type = "users"
    acl_name = "damian"
    perms = "rwx"

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    mock = MagicMock(
        side_effect=[
            {
                name: {acl_type: [{acl_name: {"octal": 7}}]},
                name + "/foo": {acl_type: [{acl_name: {"octal": "A"}}]},
            }
        ]
    )
    with patch.dict(linux_acl.__salt__, {"acl.getfacl": mock}):
        with patch.dict(linux_acl.__opts__, {"test": True}):
            comt = "Removing permissions"
            ret.update({"comment": comt})
            assert (
                linux_acl.absent(name, acl_type, acl_name, perms, recurse=True) == ret
            )
