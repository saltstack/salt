# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import sys

# Import Salt Libs
import salt.states.linux_acl as linux_acl
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf


@skipIf(not sys.platform.startswith("linux"), "Test for Linux only")
class LinuxAclTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.linux_acl
    """

    def setup_loader_modules(self):
        return {linux_acl: {}}

    # 'present' function tests: 1

    def test_present(self):
        """
        Test to ensure a Linux ACL is present
        """
        self.maxDiff = None
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
            ]
        )
        mock_modfacl = MagicMock(return_value=True)

        with patch.dict(linux_acl.__salt__, {"acl.getfacl": mock}):
            # Update - test=True
            with patch.dict(linux_acl.__opts__, {"test": True}):
                comt = (
                    "Updated permissions will be applied for {0}: r-x -> {1}"
                    "".format(acl_name, perms)
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

                self.assertDictEqual(
                    linux_acl.present(name, acl_type, acl_name, perms), ret
                )
            # Update - test=False
            with patch.dict(linux_acl.__salt__, {"acl.modfacl": mock_modfacl}):
                with patch.dict(linux_acl.__opts__, {"test": False}):
                    comt = "Updated permissions for {0}".format(acl_name)
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
                    self.assertDictEqual(
                        linux_acl.present(name, acl_type, acl_name, perms), ret
                    )
            # Update - modfacl error
            with patch.dict(
                linux_acl.__salt__,
                {
                    "acl.modfacl": MagicMock(
                        side_effect=CommandExecutionError("Custom err")
                    )
                },
            ):
                with patch.dict(linux_acl.__opts__, {"test": False}):
                    comt = "Error updating permissions for {0}: Custom err" "".format(
                        acl_name
                    )
                    ret = {
                        "name": name,
                        "comment": comt,
                        "changes": {},
                        "result": False,
                    }
                    self.assertDictEqual(
                        linux_acl.present(name, acl_type, acl_name, perms), ret
                    )
            # New - test=True
            with patch.dict(linux_acl.__salt__, {"acl.modfacl": mock_modfacl}):
                with patch.dict(linux_acl.__opts__, {"test": True}):
                    comt = "New permissions will be applied " "for {0}: {1}".format(
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
                    self.assertDictEqual(
                        linux_acl.present(name, acl_type, acl_name, perms), ret
                    )
            # New - test=False
            with patch.dict(linux_acl.__salt__, {"acl.modfacl": mock_modfacl}):
                with patch.dict(linux_acl.__opts__, {"test": False}):
                    comt = "Applied new permissions for {0}".format(acl_name)
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
                    self.assertDictEqual(
                        linux_acl.present(name, acl_type, acl_name, perms), ret
                    )
            # New - modfacl error
            with patch.dict(
                linux_acl.__salt__,
                {
                    "acl.modfacl": MagicMock(
                        side_effect=CommandExecutionError("Custom err")
                    )
                },
            ):
                with patch.dict(linux_acl.__opts__, {"test": False}):
                    comt = "Error updating permissions for {0}: Custom err" "".format(
                        acl_name
                    )
                    ret = {
                        "name": name,
                        "comment": comt,
                        "changes": {},
                        "result": False,
                    }
                    self.assertDictEqual(
                        linux_acl.present(name, acl_type, acl_name, perms), ret
                    )

            # New - recurse true
            with patch.dict(linux_acl.__salt__, {"acl.getfacl": mock}):
                # Update - test=True
                with patch.dict(linux_acl.__opts__, {"test": True}):
                    comt = (
                        "Updated permissions will be applied for {0}: rwx -> {1}"
                        "".format(acl_name, perms)
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

                    self.assertDictEqual(
                        linux_acl.present(
                            name, acl_type, acl_name, perms, recurse=False
                        ),
                        ret,
                    )

            # New - recurse true - nothing to do
            with patch.dict(linux_acl.__salt__, {"acl.getfacl": mock}):
                # Update - test=True
                with patch.dict(linux_acl.__opts__, {"test": True}):
                    comt = "Permissions are in the desired state"
                    ret = {"name": name, "comment": comt, "changes": {}, "result": True}

                    self.assertDictEqual(
                        linux_acl.present(
                            name, acl_type, acl_name, perms, recurse=True
                        ),
                        ret,
                    )

            # No acl type
            comt = "ACL Type does not exist"
            ret = {"name": name, "comment": comt, "result": False, "changes": {}}
            self.assertDictEqual(
                linux_acl.present(name, acl_type, acl_name, perms), ret
            )

    # 'absent' function tests: 2

    def test_absent(self):
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
                self.assertDictEqual(
                    linux_acl.absent(name, acl_type, acl_name, perms), ret
                )

            comt = "ACL Type does not exist"
            ret.update({"comment": comt, "result": False})
            self.assertDictEqual(linux_acl.absent(name, acl_type, acl_name, perms), ret)

    # 'list_present' function tests: 1

    def test_list_present(self):
        """
        Test to ensure a Linux ACL is present
        """
        self.maxDiff = None
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
                comt = (
                    "Updated permissions will be applied for {0}: A -> {1}"
                    "".format(acl_names, perms)
                )
                expected = {
                    "name": name,
                    "comment": comt,
                    "changes": {},
                    "pchanges": {
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
                self.assertDictEqual(ret, expected)

            # Update - test=False
            with patch.dict(linux_acl.__salt__, {"acl.modfacl": mock_modfacl}):
                with patch.dict(linux_acl.__opts__, {"test": False}):
                    comt = "Applied new permissions for {0}".format(
                        ", ".join(acl_names)
                    )
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
                        "pchanges": {},
                        "result": True,
                    }

                    ret = linux_acl.list_present(name, acl_type, acl_names, perms)
                    self.assertDictEqual(expected, ret)

            # Update - modfacl error
            with patch.dict(
                linux_acl.__salt__,
                {
                    "acl.modfacl": MagicMock(
                        side_effect=CommandExecutionError("Custom err")
                    )
                },
            ):
                with patch.dict(linux_acl.__opts__, {"test": False}):
                    comt = "Error updating permissions for {0}: Custom err" "".format(
                        acl_names
                    )
                    expected = {
                        "name": name,
                        "comment": comt,
                        "changes": {},
                        "pchanges": {},
                        "result": False,
                    }

                    ret = linux_acl.list_present(name, acl_type, acl_names, perms)
                    self.assertDictEqual(expected, ret)

            # New - test=True
            with patch.dict(linux_acl.__salt__, {"acl.modfacl": mock_modfacl}):
                with patch.dict(linux_acl.__opts__, {"test": True}):
                    comt = "New permissions will be applied " "for {0}: {1}".format(
                        acl_names, perms
                    )
                    expected = {
                        "name": name,
                        "comment": comt,
                        "changes": {},
                        "pchanges": {
                            "new": {
                                "acl_name": ", ".join(acl_names),
                                "acl_type": acl_type,
                                "perms": perms,
                            }
                        },
                        "result": None,
                    }

                    ret = linux_acl.list_present(name, acl_type, acl_names, perms)
                    self.assertDictEqual(expected, ret)

            # New - test=False
            with patch.dict(linux_acl.__salt__, {"acl.modfacl": mock_modfacl}):
                with patch.dict(linux_acl.__opts__, {"test": False}):
                    comt = "Applied new permissions for {0}".format(
                        ", ".join(acl_names)
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
                        "pchanges": {},
                        "result": True,
                    }
                    ret = linux_acl.list_present(name, acl_type, acl_names, perms)
                    self.assertDictEqual(expected, ret)

            # New - modfacl error
            with patch.dict(
                linux_acl.__salt__,
                {
                    "acl.modfacl": MagicMock(
                        side_effect=CommandExecutionError("Custom err")
                    )
                },
            ):
                with patch.dict(linux_acl.__opts__, {"test": False}):
                    comt = "Error updating permissions for {0}: Custom err" "".format(
                        acl_names
                    )
                    expected = {
                        "name": name,
                        "comment": comt,
                        "changes": {},
                        "pchanges": {},
                        "result": False,
                    }

                    ret = linux_acl.list_present(name, acl_type, acl_names, perms)
                    self.assertDictEqual(expected, ret)

            # No acl type
            comt = "ACL Type does not exist"
            expected = {
                "name": name,
                "comment": comt,
                "result": False,
                "changes": {},
                "pchanges": {},
            }
            ret = linux_acl.list_present(name, acl_type, acl_names, perms)
            self.assertDictEqual(expected, ret)

    # 'list_absent' function tests: 2

    def test_list_absent(self):
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
                self.assertDictEqual(
                    linux_acl.list_absent(name, acl_type, acl_names, perms), ret
                )

            comt = "ACL Type does not exist"
            ret.update({"comment": comt, "result": False})
            self.assertDictEqual(linux_acl.list_absent(name, acl_type, acl_names), ret)

    def test_absent_recursive(self):
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
                self.assertDictEqual(
                    linux_acl.absent(name, acl_type, acl_name, perms, recurse=True), ret
                )
