# -*- coding: utf-8 -*-
"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.group as group
from salt.utils.odict import OrderedDict

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class GroupTestCase(TestCase, LoaderModuleMockMixin):
    """
        Validate the group state
    """

    def setup_loader_modules(self):
        return {group: {}}

    def test_present(self):
        """
            Test to ensure that a group is present
        """
        ret = {"name": "salt", "changes": {}, "result": True, "comment": {}}

        ret.update(
            {
                "comment": 'Error: Conflicting options "members" with'
                ' "addusers" and/or "delusers" can not be used together. ',
                "result": None,
            }
        )
        self.assertDictEqual(group.present("salt", delusers=True, members=True), ret)

        ret.update(
            {
                "comment": "Error. Same user(s) can not be"
                " added and deleted simultaneously"
            }
        )
        self.assertDictEqual(group.present("salt", addusers=["a"], delusers=["a"]), ret)

        ret.update(
            {
                "comment": "The following group attributes are set"
                " to be changed:\nkey0: value0\nkey1: value1\n"
            }
        )

        mock = MagicMock(
            side_effect=[
                OrderedDict((("key0", "value0"), ("key1", "value1"))),
                False,
                False,
                False,
            ]
        )
        with patch.object(group, "_changes", mock):
            with patch.dict(group.__opts__, {"test": True}):
                self.assertDictEqual(group.present("salt"), ret)

                ret.update({"comment": "Group salt set to be added"})
                self.assertDictEqual(group.present("salt"), ret)

            with patch.dict(group.__opts__, {"test": False}):
                mock = MagicMock(return_value=[{"gid": 1, "name": "stack"}])
                with patch.dict(group.__salt__, {"group.getent": mock}):
                    ret.update(
                        {
                            "result": False,
                            "comment": "Group salt is not present but"
                            " gid 1 is already taken by group stack",
                        }
                    )
                    self.assertDictEqual(group.present("salt", 1), ret)

                    mock = MagicMock(return_value=False)
                    with patch.dict(group.__salt__, {"group.add": mock}):
                        ret.update({"comment": "Failed to create new group salt"})
                        self.assertDictEqual(group.present("salt"), ret)

    def test_absent(self):
        """
            Test to ensure that the named group is absent
        """
        ret = {"name": "salt", "changes": {}, "result": True, "comment": {}}
        mock = MagicMock(side_effect=[True, True, True, False])
        with patch.dict(group.__salt__, {"group.info": mock}):
            with patch.dict(group.__opts__, {"test": True}):
                ret.update({"result": None, "comment": "Group salt is set for removal"})
                self.assertDictEqual(group.absent("salt"), ret)

            with patch.dict(group.__opts__, {"test": False}):
                mock = MagicMock(side_effect=[True, False])
                with patch.dict(group.__salt__, {"group.delete": mock}):
                    ret.update(
                        {
                            "result": True,
                            "changes": {"salt": ""},
                            "comment": "Removed group salt",
                        }
                    )
                    self.assertDictEqual(group.absent("salt"), ret)

                    ret.update(
                        {
                            "changes": {},
                            "result": False,
                            "comment": "Failed to remove group salt",
                        }
                    )
                    self.assertDictEqual(group.absent("salt"), ret)

            ret.update({"result": True, "comment": "Group not present"})
            self.assertDictEqual(group.absent("salt"), ret)
