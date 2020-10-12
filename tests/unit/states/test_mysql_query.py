"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import logging
import os

import salt.modules.mysql as mysql_mod
import salt.states.mysql_query as mysql_query
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

log = logging.getLogger(__name__)
NO_MYSQL = False
NO_PyMYSQL = False
try:
    import MySQLdb  # pylint: disable=W0611
except ImportError:
    NO_MYSQL = True

try:
    # MySQLdb import failed, try to import PyMySQL
    import pymysql

    pymysql.install_as_MySQLdb()
    import MySQLdb
except ImportError:
    NO_PyMYSQL = True


class MockMySQLConnect:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def autocommit(self, *args, **kwards):
        return True

    def cursor(self, *args, **kwards):
        return MagicMock()


class MysqlQueryTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.mysql_query
    """

    def setup_loader_modules(self):
        return {mysql_query: {}, mysql_mod: {}}

    # 'run' function tests: 1

    def test_run(self):
        """
        Test to execute an arbitrary query on the specified database.
        """
        name = "query_id"
        database = "my_database"
        query = "SELECT * FROM table;"

        ret = {"name": name, "result": True, "comment": "", "changes": {}}

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        mock_str = MagicMock(return_value="salt")
        mock_none = MagicMock(return_value=None)
        mock_dict = MagicMock(return_value={"salt": "SALT"})
        mock_lst = MagicMock(return_value=["grain"])
        with patch.dict(mysql_query.__salt__, {"mysql.db_exists": mock_f}):
            with patch.object(mysql_query, "_get_mysql_error", mock_str):
                ret.update({"comment": "salt", "result": False})
                self.assertDictEqual(mysql_query.run(name, database, query), ret)

            with patch.object(mysql_query, "_get_mysql_error", mock_none):
                comt = "Database {} is not present".format(name)
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(mysql_query.run(name, database, query), ret)

        with patch.dict(
            mysql_query.__salt__,
            {
                "mysql.db_exists": mock_t,
                "grains.ls": mock_lst,
                "grains.get": mock_dict,
                "mysql.query": mock_str,
            },
        ):
            comt = "No execution needed. Grain grain already set"
            ret.update({"comment": comt, "result": True})
            self.assertDictEqual(
                mysql_query.run(
                    name,
                    database,
                    query,
                    output="grain",
                    grain="grain",
                    overwrite=False,
                ),
                ret,
            )

            with patch.dict(mysql_query.__opts__, {"test": True}):
                comt = "Query would execute, storing result in grain: grain"
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(
                    mysql_query.run(
                        name, database, query, output="grain", grain="grain"
                    ),
                    ret,
                )

                comt = "Query would execute, storing result" " in grain: grain:salt"
                ret.update({"comment": comt})
                self.assertDictEqual(
                    mysql_query.run(
                        name, database, query, output="grain", grain="grain", key="salt"
                    ),
                    ret,
                )

                comt = "Query would execute, storing result in file: salt"
                ret.update({"comment": comt})
                self.assertDictEqual(
                    mysql_query.run(
                        name, database, query, output="salt", grain="grain"
                    ),
                    ret,
                )

                comt = "Query would execute, not storing result"
                ret.update({"comment": comt})
                self.assertDictEqual(mysql_query.run(name, database, query), ret)

            comt = "No execution needed. Grain grain:salt already set"
            ret.update({"comment": comt, "result": True})
            self.assertDictEqual(
                mysql_query.run(
                    name,
                    database,
                    query,
                    output="grain",
                    grain="grain",
                    key="salt",
                    overwrite=False,
                ),
                ret,
            )

            comt = "Error: output type 'grain' needs the grain parameter\n"
            ret.update({"comment": comt, "result": False})
            self.assertDictEqual(
                mysql_query.run(name, database, query, output="grain"), ret
            )

            with patch.object(os.path, "isfile", mock_t):
                comt = "No execution needed. File salt already set"
                ret.update({"comment": comt, "result": True})
                self.assertDictEqual(
                    mysql_query.run(
                        name,
                        database,
                        query,
                        output="salt",
                        grain="grain",
                        overwrite=False,
                    ),
                    ret,
                )

            with patch.dict(mysql_query.__opts__, {"test": False}):
                ret.update({"comment": "salt", "changes": {"query": "Executed"}})
                self.assertDictEqual(mysql_query.run(name, database, query), ret)

    @skipIf(
        NO_MYSQL and NO_PyMYSQL,
        "Install MySQL bindings before running MySQL unit tests.",
    )
    def test_run_multiple_statements(self):
        """
        Test to execute an arbitrary query on the specified database
        and ensure that the correct multi_statements flag is passed along
        to MySQLdb.connect.
        """
        name = "query_id"
        database = "my_database"
        query = "SELECT * FROM table; SELECT * from another_table;"

        mock_t = MagicMock(return_value=True)

        with patch.dict(mysql_query.__salt__, {"mysql.db_exists": mock_t}), patch.dict(
            mysql_query.__opts__, {"test": False}
        ), patch.dict(
            mysql_query.__salt__, {"mysql.query": mysql_mod.query}
        ), patch.dict(
            mysql_query.__salt__, {"mysql._execute": MagicMock()}
        ), patch.dict(
            mysql_mod.__salt__, {"config.option": MagicMock()}
        ), patch(
            "MySQLdb.connect", return_value=MockMySQLConnect()
        ) as mock_connect:
            ret = mysql_query.run(
                name, database, query, client_flags=["multi_statements"]
            )
            self.assertEqual(1, len(mock_connect.mock_calls))
            self.assertIn("client_flag=65536", str(mock_connect.mock_calls[0]))
