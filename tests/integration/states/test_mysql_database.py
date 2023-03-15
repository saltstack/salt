"""
Tests for the MySQL states
"""

import pytest

import salt.utils.path
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin

NO_MYSQL = False
try:
    import MySQLdb  # pylint: disable=import-error,unused-import
except ImportError:
    NO_MYSQL = True

if not salt.utils.path.which("mysqladmin"):
    NO_MYSQL = True


@pytest.mark.skipif(
    NO_MYSQL,
    reason="Please install MySQL bindings and a MySQL Server before running "
    "MySQL integration tests.",
)
class MysqlDatabaseStateTest(ModuleCase, SaltReturnAssertsMixin):
    """
    Validate the mysql_database state
    """

    user = "root"
    password = "poney"

    @pytest.mark.destructive_test
    def setUp(self):
        """
        Test presence of MySQL server, enforce a root password
        """
        super().setUp()
        NO_MYSQL_SERVER = True
        # now ensure we know the mysql root password
        # one of theses two at least should work
        ret1 = self.run_state(
            "cmd.run",
            name='mysqladmin --host="localhost" -u '
            + self.user
            + ' flush-privileges password "'
            + self.password
            + '"',
        )
        ret2 = self.run_state(
            "cmd.run",
            name='mysqladmin --host="localhost" -u '
            + self.user
            + ' --password="'
            + self.password
            + '" flush-privileges password "'
            + self.password
            + '"',
        )
        key, value = ret2.popitem()
        if value["result"]:
            NO_MYSQL_SERVER = False
        else:
            self.skipTest("No MySQL Server running, or no root access on it.")

    def _test_database(self, db_name, second_db_name, test_conn, **kwargs):
        """
        Create db two times, test conn, remove it two times
        """
        # In case of...
        ret = self.run_state("mysql_database.absent", name=db_name, **kwargs)
        ret = self.run_state("mysql_database.present", name=db_name, **kwargs)
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment("The database " + db_name + " has been created", ret)
        # 2nd run
        ret = self.run_state("mysql_database.present", name=second_db_name, **kwargs)
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment("Database " + db_name + " is already present", ret)
        if test_conn:
            # test root connection
            ret = self.run_function(
                "mysql.query", database=db_name, query="SELECT 1", **kwargs
            )
            if not isinstance(ret, dict) or "results" not in ret:
                raise AssertionError(
                    (
                        "Unexpected result while testing connection on db '{}': {}"
                    ).format(db_name, repr(ret))
                )
            self.assertEqual([["1"]], ret["results"])

        # Now removing databases
        kwargs.pop("character_set")
        kwargs.pop("collate")
        ret = self.run_state("mysql_database.absent", name=db_name, **kwargs)
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment("Database " + db_name + " has been removed", ret)
        # 2nd run
        ret = self.run_state("mysql_database.absent", name=second_db_name, **kwargs)
        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(
            "Database " + db_name + " is not present, so it cannot be removed", ret
        )
        self.assertSaltStateChangesEqual(ret, {})

    @pytest.mark.destructive_test
    def test_present_absent(self):
        """
        mysql_database.present
        """
        self._test_database(
            "testdb1",
            "testdb1",
            test_conn=True,
            character_set="utf8",
            collate="utf8_general_ci",
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset="utf8",
        )

    # TODO: test with variations on collate and charset, check for db alter
    # once it will be done in mysql_database.present state

    @pytest.mark.destructive_test
    def test_present_absent_fuzzy(self):
        """
        mysql_database.present with utf-8 andf fuzzy db name
        """
        # this is : ":() ;,?@=`&'\
        dbname_fuzzy = "\":() ;,?@=`&/'\\"
        # \xe6\xa8\x99\ = \u6a19 = 標
        # this is : "();,?:@=`&/標'\
        dbname_utf8 = "\"();,?@=`&//\xe6\xa8\x99'\\"
        dbname_unicode = "\"();,?@=`&//\u6a19'\\"

        self._test_database(
            dbname_fuzzy,
            dbname_fuzzy,
            test_conn=True,
            character_set="utf8",
            collate="utf8_general_ci",
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset="utf8",
        )

        # FIXME: MySQLdb bugs on dbnames with utf-8?
        self._test_database(
            dbname_utf8,
            dbname_unicode,
            test_conn=False,
            character_set="utf8",
            collate="utf8_general_ci",
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset="utf8",
            # saltenv={"LC_ALL": "en_US.utf8"}
        )

    @pytest.mark.destructive_test
    @pytest.mark.skip(reason="This tests needs issue #8947 to be fixed first")
    def test_utf8_from_sls_file(self):
        """
        Try to create/destroy an utf-8 database name from an sls file #8947
        """
        expected_result = {
            "mysql_database_|-A_|-foo \xe6\xba\x96`bar_|-present": {
                "__run_num__": 0,
                "comment": "The database foo \xe6\xba\x96`bar has been created",
                "result": True,
            },
            "mysql_database_|-B_|-foo \xe6\xba\x96`bar_|-absent": {
                "__run_num__": 1,
                "comment": "Database foo \xe6\xba\x96`bar has been removed",
                "result": True,
            },
        }
        result = {}
        ret = self.run_function("state.sls", mods="mysql_utf8")
        if not isinstance(ret, dict):
            raise AssertionError(
                ("Unexpected result while testing external mysql utf8 sls: {}").format(
                    repr(ret)
                )
            )
        for item, descr in ret.items():
            result[item] = {
                "__run_num__": descr["__run_num__"],
                "comment": descr["comment"],
                "result": descr["result"],
            }
        self.assertEqual(expected_result, result)
