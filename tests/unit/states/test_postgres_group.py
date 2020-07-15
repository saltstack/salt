# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.postgres_group as postgres_group

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class PostgresGroupTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.postgres_group
    """

    def setup_loader_modules(self):
        return {postgres_group: {}}

    # 'present' function tests: 1

    def test_present(self):
        """
        Test to ensure that the named group is present
        with the specified privileges.
        """
        name = "frank"

        ret = {"name": name, "changes": {}, "result": False, "comment": ""}

        mock_t = MagicMock(return_value=True)
        mock = MagicMock(return_value=None)
        with patch.dict(
            postgres_group.__salt__,
            {"postgres.role_get": mock, "postgres.group_create": mock_t},
        ):
            with patch.dict(postgres_group.__opts__, {"test": True}):
                comt = "Group {0} is set to be created".format(name)
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(postgres_group.present(name), ret)

            with patch.dict(postgres_group.__opts__, {"test": False}):
                comt = "The group {0} has been created".format(name)
                ret.update({"comment": comt, "result": True})
                self.assertDictEqual(postgres_group.present(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        """
        Test to ensure that the named group is absent.
        """
        name = "frank"

        ret = {"name": name, "changes": {}, "result": False, "comment": ""}

        mock_t = MagicMock(return_value=True)
        mock = MagicMock(side_effect=[True, True, False])
        with patch.dict(
            postgres_group.__salt__,
            {"postgres.user_exists": mock, "postgres.group_remove": mock_t},
        ):
            with patch.dict(postgres_group.__opts__, {"test": True}):
                comt = "Group {0} is set to be removed".format(name)
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(postgres_group.absent(name), ret)

            with patch.dict(postgres_group.__opts__, {"test": False}):
                comt = "Group {0} has been removed".format(name)
                ret.update(
                    {"comment": comt, "result": True, "changes": {name: "Absent"}}
                )
                self.assertDictEqual(postgres_group.absent(name), ret)

            comt = "Group {0} is not present, so it cannot be removed".format(name)
            ret.update({"comment": comt, "result": True, "changes": {}})
            self.assertDictEqual(postgres_group.absent(name), ret)
