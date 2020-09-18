"""
This test checks mysql_database salt state
"""
# Import Salt Libs
import salt.states.mysql_database as mysql_database

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class MysqlDatabaseTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.mysql_database
    """

    def setup_loader_modules(self):
        return {mysql_database: {}}

    # 'present' function tests: 1
    def test_present(self):
        """
        Test to ensure that the named user is present with
         the specified properties.
        """
        dbname = "my_test"
        charset = "utf8"
        collate = "utf8_unicode_ci"

        ret = {"name": dbname, "result": False, "comment": "", "changes": {}}

        mock_result = {
            "character_set": charset,
            "collate": collate,
            "name": dbname,
        }
        mock_result_charset_updated = {
            "character_set": "ascii",
            "collate": "utf8_unicode_ci",
            "name": dbname,
        }

        mock_result_alter_db = {True}

        mock = MagicMock(return_value=mock_result)
        mock_a = MagicMock(return_value=mock_result_alter_db)
        mock_b = MagicMock(return_value=mock_result_charset_updated)
        mock_failed = MagicMock(return_value=False)
        mock_err = MagicMock(return_value="salt")
        mock_no_err = MagicMock(return_value=None)
        mock_create = MagicMock(return_value=True)
        mock_create_failed = MagicMock(return_value=False)
        with patch.dict(
            mysql_database.__salt__, {"mysql.db_get": mock, "mysql.alter_db": mock_a}
        ):
            mod_charset = "ascii"
            mod_collate = "ascii_general_ci"
            with patch.dict(mysql_database.__opts__, {"test": True}):
                comt = [
                    "Database character set {} != {} needs to be updated".format(
                        mod_charset, charset
                    ),
                    "Database {} is going to be updated".format(dbname),
                ]
                ret.update({"comment": "\n".join(comt)})
                ret.update({"result": None})
                self.assertDictEqual(
                    mysql_database.present(dbname, character_set=mod_charset), ret
                )

            with patch.dict(mysql_database.__opts__, {"test": True}):
                comt = [
                    "Database {} is already present".format(dbname),
                    "Database collate {} != {} needs to be updated".format(
                        mod_collate, collate
                    ),
                ]
                ret.update({"comment": "\n".join(comt)})
                ret.update({"result": None})
                self.assertDictEqual(
                    mysql_database.present(
                        dbname, character_set=charset, collate=mod_collate
                    ),
                    ret,
                )

            with patch.dict(mysql_database.__opts__, {}):
                comt = [
                    "Database character set {} != {} needs to be updated".format(
                        mod_charset, charset
                    ),
                    "Database collate {} != {} needs to be updated".format(
                        mod_collate, collate
                    ),
                ]
                ret.update({"comment": "\n".join(comt)})
                ret.update({"result": True})
                self.assertDictEqual(
                    mysql_database.present(
                        dbname, character_set=mod_charset, collate=mod_collate
                    ),
                    ret,
                )

            with patch.dict(mysql_database.__opts__, {"test": False}):
                comt = "Database {} is already present".format(dbname)
                ret.update({"comment": comt})
                ret.update({"result": True})
                self.assertDictEqual(
                    mysql_database.present(
                        dbname, character_set=charset, collate=collate
                    ),
                    ret,
                )

        with patch.dict(mysql_database.__salt__, {"mysql.db_get": mock_failed}):
            with patch.dict(mysql_database.__salt__, {"mysql.db_create": mock_create}):
                with patch.object(mysql_database, "_get_mysql_error", mock_err):
                    ret.update({"comment": "salt", "result": False})
                    self.assertDictEqual(mysql_database.present(dbname), ret)

                with patch.object(mysql_database, "_get_mysql_error", mock_no_err):
                    comt = "The database {} has been created".format(dbname)

                    ret.update({"comment": comt, "result": True})
                    ret.update({"changes": {dbname: "Present"}})
                    self.assertDictEqual(mysql_database.present(dbname), ret)

            with patch.dict(
                mysql_database.__salt__, {"mysql.db_create": mock_create_failed}
            ):
                ret["comment"] = ""
                with patch.object(mysql_database, "_get_mysql_error", mock_no_err):
                    ret.update({"changes": {}})
                    comt = "Failed to create database {}".format(dbname)
                    ret.update({"comment": comt, "result": False})
                    self.assertDictEqual(mysql_database.present(dbname), ret)

    # 'absent' function tests: 1
    def test_absent(self):
        """
        Test to ensure that the named user is absent.
        """
        dbname = "my_test"

        ret = {"name": dbname, "result": True, "comment": "", "changes": {}}

        mock_db_exists = MagicMock(return_value=True)
        mock_db_no_exists = MagicMock(return_value=False)
        mock_remove = MagicMock(return_value=True)
        mock_remove_fail = MagicMock(return_value=False)
        mock_err = MagicMock(return_value="salt")
        mock_no_err = MagicMock(return_value=None)

        with patch.dict(
            mysql_database.__salt__,
            {"mysql.db_exists": mock_db_exists, "mysql.db_remove": mock_remove},
        ):
            with patch.dict(mysql_database.__opts__, {"test": True}):
                comt = "Database {} is present and needs to be removed".format(dbname)
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(mysql_database.absent(dbname), ret)

            with patch.dict(mysql_database.__opts__, {}):
                comt = "Database {} has been removed".format(dbname)
                ret.update({"comment": comt, "result": True})
                ret.update({"changes": {dbname: "Absent"}})
                self.assertDictEqual(mysql_database.absent(dbname), ret)

        with patch.dict(
            mysql_database.__salt__,
            {"mysql.db_exists": mock_db_exists, "mysql.db_remove": mock_remove_fail},
        ):
            with patch.dict(mysql_database.__opts__, {}):
                with patch.object(mysql_database, "_get_mysql_error", mock_err):
                    ret["changes"] = {}
                    comt = "Unable to remove database {} ({})".format(dbname, "salt")
                    ret.update({"comment": comt, "result": False})
                    self.assertDictEqual(mysql_database.absent(dbname), ret)
