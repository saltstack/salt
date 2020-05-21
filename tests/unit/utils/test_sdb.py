# -*- coding: utf-8 -*-
"""
    :codeauthor: :email:`Vernon Cole <vernondcole@gmail.com>`
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import os

# Import Salt Libs
import salt.utils.sdb as sdb
from tests.support.mixins import LoaderModuleMockMixin

# Import Salt Testing Libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase


class SdbTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.sdb
    """

    @classmethod
    def setUpClass(cls):
        cls.TEMP_DATABASE_FILE = os.path.join(RUNTIME_VARS.TMP, "test_sdb.sqlite")
        cls.sdb_opts = {
            "extension_modules": "",
            "optimization_order": [0, 1, 2],
            "test_sdb_data": {
                "driver": "sqlite3",
                "database": cls.TEMP_DATABASE_FILE,
                "table": "sdb",
                "create_table": True,
            },
        }

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls.TEMP_DATABASE_FILE)
        except OSError:
            pass

    def setup_loader_modules(self):
        return {sdb: {}}

    # test with SQLite database key not presest

    def test_sqlite_get_not_found(self):
        what = sdb.sdb_get("sdb://test_sdb_data/thisKeyDoesNotExist", self.sdb_opts)
        self.assertEqual(what, None)

    # test with SQLite database write and read

    def test_sqlite_get_found(self):
        expected = {b"name": b"testone", b"number": 46}
        sdb.sdb_set("sdb://test_sdb_data/test1", expected, self.sdb_opts)
        resp = sdb.sdb_get("sdb://test_sdb_data/test1", self.sdb_opts)
        self.assertEqual(resp, expected)
