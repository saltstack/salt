# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.mongodb_database as mongodb_database

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class MongodbDatabaseTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.mongodb_database
    """

    def setup_loader_modules(self):
        return {mongodb_database: {}}

    # 'absent' function tests: 1

    def test_absent(self):
        """
        Test to ensure that the named database is absent.
        """
        name = "mydb"

        ret = {"name": name, "result": None, "comment": "", "changes": {}}

        mock = MagicMock(side_effect=[True, True, False])
        mock_t = MagicMock(return_value=True)
        with patch.dict(
            mongodb_database.__salt__,
            {"mongodb.db_exists": mock, "mongodb.db_remove": mock_t},
        ):
            with patch.dict(mongodb_database.__opts__, {"test": True}):
                comt = "Database {0} is present and needs to be removed".format(name)
                ret.update({"comment": comt})
                self.assertDictEqual(mongodb_database.absent(name), ret)

            with patch.dict(mongodb_database.__opts__, {"test": False}):
                comt = "Database {0} has been removed".format(name)
                ret.update(
                    {"comment": comt, "result": True, "changes": {"mydb": "Absent"}}
                )
                self.assertDictEqual(mongodb_database.absent(name), ret)

                comt = "Database {0} is not present".format(name)
                ret.update({"comment": comt, "changes": {}})
                self.assertDictEqual(mongodb_database.absent(name), ret)
