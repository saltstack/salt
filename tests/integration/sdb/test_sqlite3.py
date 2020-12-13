"""
A test case for the SQLite3 SDB module.

Why are the tests below named the way they're named?

Because Pytest orders test in lexical order. There's no specific
reason for the tests to be run in any particular order, but I do
like the tidiness of having the tests run in the same order they're
defined in a file.

You could argue against such a practice, but why would you? Since
Pytest doesn't randomize the order, any order is as good as any other.
So, why not just run with this? It's quite reasonable and takes little
or no effort from your part to tolerate.

"""

import os
import sqlite3

from tests.support.case import ShellCase


class Sqlite3TestCase(ShellCase):
    # Why do we think the file "sdb.sqlite3" is in the current working
    # directory of the process running the tests? Well, because that is what
    # is specified in the file "tests/integration/files/conf/master".
    sdb_file = "sdb.sqlite3"

    # Ensure a) the tests' order is of no significance, and b) that we don't
    # leave behind any unnecessary cruft.
    def tearDown(self):
        os.remove(self.sdb_file)

    # Is this absolutely necessary? No. We could live without it. However,
    # it does give us some finer sense of what goes wrong and helps us to
    # differentiate between the database file simply not being created
    # because of insufficient file permissions, e.g., and other errors.
    def table_exists(self, filename, tablename):
        con = sqlite3.connect(filename)
        cur = con.cursor()

        try:
            # This raises sqlite3.OperationalError for a missing table.
            q = "SELECT {} FROM {} WHERE type=\"{}\" AND name=\"{}\";".format(
                "name", "sqlite_master", "table", tablename
            )
            cur.execute(q)
            ret = cur.fetchall()
            con.close()

            return len(ret) > 0
        except sqlite3.OperationalError:
            con.close()

            return False

    def test_aaaa(self):
        """
        When the keyword argument "create" for the SQLite3 SDB driver
        is present and its value is True, any call to SDB will create
        the database.
        """
        data = self.run_run_plus("sdb.get",
                                 "sdb://sdbsqlite3createtrue/foo")

        self.assertTrue(os.path.exists(self.sdb_file))
        self.assertTrue(data["return"] is None)
        self.assertTrue(self.table_exists(self.sdb_file, "sdb"))

    def test_aaab(self):
        """
        When the keyword argument "create" for the SQLite3 SDB driver is
        not present, the default value True is honoured and any call to
        SDB will create the database.
        """
        data = self.run_run_plus("sdb.get",
                                 "sdb://sdbsqlite3createdefault/foo")

        self.assertTrue(os.path.exists(self.sdb_file))
        self.assertTrue(data["return"] is None)
        self.assertTrue(self.table_exists(self.sdb_file, "sdb"))

    def test_aaac(self):
        """
        When the keyword argument "create" for the SQLite3 SDB driver is
        present and its value is False, a call to SDB will not create the
        database tables.

        Note: Because SQLite3 creates a database file with every
        "connection", the database table list has to be consulted.
        """
        data = self.run_run_plus("sdb.get",
                                 "sdb://sdbsqlite3createfalse/foo")

        self.assertTrue(os.path.exists(self.sdb_file))
        self.assertTrue(data["return"] is None)
        self.assertFalse(self.table_exists(self.sdb_file, "sdb"))

    def set_aaad(self):
        """
        When the keyword argument "table" doesn't use the default value,
        the value specified is honoured.
        """
        data = self.run_run_plus("sdb.get",
                                 "sdb://sdbsqlite3funnytablename/foo")

        self.assertTrue(os.path.exists(self.sdb_file))
        self.assertFalse(data["return"])
        self.assertTrue(self.table_exists(self.sdb_file,
                                          "sdbsqlite3funnytablename"))

    def test_bbbb(self):
        """
        When a key-value pair is set in SDB, that same key-value pair
        is accessible later.
        """
        data = self.run_run_plus("sdb.set",
                                 "sdb://sdbsqlite3createtrue/foo",
                                 value = "bar")
        self.assertTrue(os.path.exists(self.sdb_file))
        self.assertTrue(data["return"])

        data = self.run_run_plus("sdb.get",
                                 "sdb://sdbsqlite3createtrue/foo")
        self.assertEqual(data["out"], ["bar"])

    def test_cccc(self):
        """
        When a key-value has been deleted from SDB, the key-value is
        is not accessible later.
        """
        data = self.run_run_plus("sdb.set",
                                 "sdb://sdbsqlite3createtrue/foo",
                                 value = "bar")
        self.assertTrue(data["return"])

        data = self.run_run_plus("sdb.get",
                                 "sdb://sdbsqlite3createtrue/foo")
        self.assertTrue(data["return"])
        self.assertEqual(data["out"], ["bar"])

        data = self.run_run_plus("sdb.delete",
                                 "sdb://sdbsqlite3createtrue/foo")
        self.assertTrue(data["return"])

        data = self.run_run_plus("sdb.get",
                                 "sdb://sdbsqlite3createtrue/foo")
        self.assertTrue(data["return"] is None)

    def test_cccd(self):
        """
        When a key-value is deleted from SDB, they key-value and nothing
        else is deleted.
        """
        data = self.run_run_plus("sdb.set",
                                 "sdb://sdbsqlite3createtrue/foo",
                                 value = "bar")
        self.assertTrue(data["return"])
        data = self.run_run_plus("sdb.set",
                                 "sdb://sdbsqlite3createtrue/bar",
                                 value = "foo")
        self.assertTrue(data["return"])

        data = self.run_run_plus("sdb.get",
                                 "sdb://sdbsqlite3createtrue/foo")
        self.assertTrue(data["return"])
        self.assertEqual(data["out"], ["bar"])

        data = self.run_run_plus("sdb.get",
                                 "sdb://sdbsqlite3createtrue/bar")
        self.assertTrue(data["return"])
        self.assertEqual(data["out"], ["foo"])

        data = self.run_run_plus("sdb.delete",
                                 "sdb://sdbsqlite3createtrue/foo")
        self.assertTrue(data["return"])

        data = self.run_run_plus("sdb.get",
                                 "sdb://sdbsqlite3createtrue/foo")
        self.assertTrue(data["return"] is None)

        data = self.run_run_plus("sdb.get",
                                 "sdb://sdbsqlite3createtrue/bar")
        self.assertTrue(data["return"])
        self.assertEqual(data["out"], ["foo"])

# end of file.
