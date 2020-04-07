# -*- coding: utf-8 -*-
"""
Tests for the MySQL states
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import salt libs
import salt.utils.path
from salt.ext import six
from salt.modules import mysql as mysqlmod

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.unit import skipIf

log = logging.getLogger(__name__)

NO_MYSQL = False
try:
    import MySQLdb  # pylint: disable=import-error,unused-import
except ImportError:
    NO_MYSQL = True

if not salt.utils.path.which("mysqladmin"):
    NO_MYSQL = True


@skipIf(
    NO_MYSQL,
    "Please install MySQL bindings and a MySQL Server before running"
    "MySQL integration tests.",
)
class MysqlGrantsStateTest(ModuleCase, SaltReturnAssertsMixin):
    """
    Validate the mysql_grants states
    """

    user = "root"
    password = "poney"
    # yep, theses are valid MySQL db names
    # very special chars are _ % and .
    testdb1 = "tes.t'\"saltdb"
    testdb2 = "t_st `(:=salt%b)"
    testdb3 = "test `(:=salteeb)"
    table1 = "foo"
    table2 = "foo `'%_bar"
    users = {
        "user1": {"name": "foo", "pwd": "bar"},
        "user2": {"name": 'user ";--,?:&/\\', "pwd": '";--(),?:@=&/\\'},
        # this is : passwd 標標
        "user3": {"name": "user( @ )=foobar", "pwd": "\xe6\xa8\x99\xe6\xa8\x99"},
        # this is : user/password containing 標標
        "user4": {"name": "user \xe6\xa8\x99", "pwd": "\xe6\xa8\x99\xe6\xa8\x99"},
    }

    @destructiveTest
    def setUp(self):
        """
        Test presence of MySQL server, enforce a root password
        """
        super(MysqlGrantsStateTest, self).setUp()
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
        # Create some users and a test db
        for user, userdef in six.iteritems(self.users):
            self._userCreation(uname=userdef["name"], password=userdef["pwd"])
        self.run_state(
            "mysql_database.present",
            name=self.testdb1,
            character_set="utf8",
            collate="utf8_general_ci",
            connection_user=self.user,
            connection_pass=self.password,
        )
        self.run_state(
            "mysql_database.present",
            name=self.testdb2,
            character_set="utf8",
            collate="utf8_general_ci",
            connection_user=self.user,
            connection_pass=self.password,
        )
        create_query = (
            "CREATE TABLE {tblname} ("
            " id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,"
            " data VARCHAR(100)) ENGINE={engine};".format(
                tblname=mysqlmod.quote_identifier(self.table1), engine="MYISAM",
            )
        )
        log.info("Adding table '%s'", self.table1)
        self.run_function(
            "mysql.query",
            database=self.testdb2,
            query=create_query,
            connection_user=self.user,
            connection_pass=self.password,
        )
        create_query = (
            "CREATE TABLE {tblname} ("
            " id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,"
            " data VARCHAR(100)) ENGINE={engine};".format(
                tblname=mysqlmod.quote_identifier(self.table2), engine="MYISAM",
            )
        )
        log.info("Adding table '%s'", self.table2)
        self.run_function(
            "mysql.query",
            database=self.testdb2,
            query=create_query,
            connection_user=self.user,
            connection_pass=self.password,
        )

    @destructiveTest
    def tearDown(self):
        """
        Removes created users and db
        """
        for user, userdef in six.iteritems(self.users):
            self._userRemoval(uname=userdef["name"], password=userdef["pwd"])
        self.run_state(
            "mysql_database.absent",
            name=self.testdb1,
            connection_user=self.user,
            connection_pass=self.password,
        )
        self.run_function(
            "mysql_database.absent",
            name=self.testdb2,
            connection_user=self.user,
            connection_pass=self.password,
        )

    def _userCreation(self, uname, password=None):
        """
        Create a test user
        """
        self.run_state(
            "mysql_user.present",
            name=uname,
            host="localhost",
            password=password,
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset="utf8",
            saltenv={"LC_ALL": "en_US.utf8"},
        )

    def _userRemoval(self, uname, password=None):
        """
        Removes a test user
        """
        self.run_state(
            "mysql_user.absent",
            name=uname,
            host="localhost",
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset="utf8",
            saltenv={"LC_ALL": "en_US.utf8"},
        )

    @destructiveTest
    def test_grant_present_absent(self):
        """
        mysql_database.present
        """
        ret = self.run_state(
            "mysql_grants.present",
            name="grant test 1",
            grant="SELECT, INSERT",
            database=self.testdb1 + ".*",
            user=self.users["user1"]["name"],
            host="localhost",
            grant_option=True,
            revoke_first=True,
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset="utf8",
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_state(
            "mysql_grants.present",
            name="grant test 2",
            grant="SELECT, ALTER,CREATE TEMPORARY tables, execute",
            database=self.testdb1 + ".*",
            user=self.users["user1"]["name"],
            host="localhost",
            grant_option=True,
            revoke_first=True,
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset="utf8",
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_state(
            "mysql_grants.present",
            name="grant test 3",
            grant="SELECT, INSERT",
            database=self.testdb2 + "." + self.table2,
            user=self.users["user2"]["name"],
            host="localhost",
            grant_option=True,
            revoke_first=True,
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset="utf8",
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_state(
            "mysql_grants.present",
            name="grant test 4",
            grant="SELECT, INSERT",
            database=self.testdb2 + "." + self.table2,
            user=self.users["user2"]["name"],
            host="localhost",
            grant_option=True,
            revoke_first=True,
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset="utf8",
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_state(
            "mysql_grants.present",
            name="grant test 5",
            grant="SELECT, UPDATE",
            database=self.testdb2 + ".*",
            user=self.users["user1"]["name"],
            host="localhost",
            grant_option=True,
            revoke_first=False,
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset="utf8",
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_state(
            "mysql_grants.absent",
            name="grant test 6",
            grant="SELECT,update",
            database=self.testdb2 + ".*",
            user=self.users["user1"]["name"],
            host="localhost",
            grant_option=True,
            revoke_first=False,
            connection_user=self.user,
            connection_pass=self.password,
            connection_charset="utf8",
        )
        self.assertSaltTrueReturn(ret)
