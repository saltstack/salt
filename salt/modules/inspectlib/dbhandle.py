# -*- coding: utf-8 -*-
#
# Copyright 2015 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Import Python LIbs
from __future__ import absolute_import
import sqlite3
import os


class DBHandleBase(object):
    '''
    Handle for the *volatile* database, which serves the purpose of caching
    the inspected data. This database can be destroyed or corrupted, so it should
    be simply re-created from scratch.
    '''

    def __init__(self, path):
        '''
        Constructor.
        '''
        self._path = path
        self.connection = None
        self.cursor = None
        self.init_queries = list()

    def open(self, new=False):
        '''
        Init the database, if required.
        '''
        if self.connection and self.cursor:
            return

        if new and os.path.exists(self._path):
            os.unlink(self._path)  # As simple as that

        self.connection = sqlite3.connect(self._path)
        self.connection.text_factory = str
        self.cursor = self.connection.cursor()

        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        if self.cursor.fetchall():
            return

        self._run_init_queries()
        self.connection.commit()

    def _run_init_queries(self):
        '''
        Initialization queries
        '''
        for query in self.init_queries:
            self.cursor.execute(query)

    def purge(self):
        '''
        Purge whole database.
        '''
        if self.connection and self.cursor:
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            for table_name in self.cursor.fetchall():
                self.cursor.execute("DROP TABLE {0}".format(table_name[0]))
            self.connection.commit()
        self._run_init_queries()

    def flush(self, table):
        '''
        Flush the table.
        '''
        self.cursor.execute("DELETE FROM " + table)
        self.connection.commit()

    def close(self):
        '''
        Close the database connection.
        '''
        if self.cursor is not None and self.connection is not None:
            self.connection.close()
            self.cursor = self.connection = None


class DBHandle(DBHandleBase):
    __instance = None

    def __new__(cls, *args, **kwargs):
        '''
        Keep singleton.
        '''
        if not cls.__instance:
            cls.__instance = super(DBHandle, cls).__new__(cls, *args, **kwargs)
        return cls.__instance

    def __init__(self, path):
        '''
        Database handle for the specific

        :param path:
        :return:
        '''
        DBHandleBase.__init__(self, path)

        self.init_queries.append("CREATE TABLE inspector_pkg "
                                 "(id INTEGER PRIMARY KEY, name CHAR(255))")
        self.init_queries.append("CREATE TABLE inspector_pkg_cfg_files "
                                 "(id INTEGER PRIMARY KEY, pkgid INTEGER, path CHAR(4096))")
        self.init_queries.append("CREATE TABLE inspector_pkg_cfg_diffs "
                                 "(id INTEGER PRIMARY KEY, cfgid INTEGER, diff TEXT)")
        self.init_queries.append("CREATE TABLE inspector_payload "
                                 "(id INTEGER PRIMARY KEY, path CHAR(4096), "
                                 "p_type char(1), mode INTEGER, uid INTEGER, gid INTEGER, p_size INTEGER, "
                                 "atime FLOAT, mtime FLOAT, ctime FLOAT)")

        # inspector_allowed overrides inspector_ignored.
        # I.e. if allowed is not empty, then inspector_ignored is completely omitted.
        self.init_queries.append("CREATE TABLE inspector_ignored (path CHAR(4096))")
        self.init_queries.append("CREATE TABLE inspector_allowed (path CHAR(4096))")
