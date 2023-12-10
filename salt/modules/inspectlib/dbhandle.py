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

from salt.modules.inspectlib.entities import (
    AllowedDir,
    IgnoredDir,
    Package,
    PackageCfgFile,
    PayloadFile,
)
from salt.modules.inspectlib.fsdb import CsvDB


class DBHandleBase:
    """
    Handle for the *volatile* database, which serves the purpose of caching
    the inspected data. This database can be destroyed or corrupted, so it should
    be simply re-created from scratch.
    """

    def __init__(self, path):
        """
        Constructor.
        """
        self._path = path
        self.init_queries = list()
        self._db = CsvDB(self._path)

    def open(self, new=False):
        """
        Init the database, if required.
        """
        self._db.new() if new else self._db.open()  # pylint: disable=W0106
        self._run_init_queries()

    def _run_init_queries(self):
        """
        Initialization queries
        """
        for obj in (Package, PackageCfgFile, PayloadFile, IgnoredDir, AllowedDir):
            self._db.create_table_from_object(obj())

    def purge(self):
        """
        Purge whole database.
        """
        for table_name in self._db.list_tables():
            self._db.flush(table_name)

        self._run_init_queries()

    def flush(self, table):
        """
        Flush the table.
        """
        self._db.flush(table)

    def close(self):
        """
        Close the database connection.
        """
        self._db.close()

    def __getattr__(self, item):
        """
        Proxy methods from the Database instance.

        :param item:
        :return:
        """
        return getattr(self._db, item)


class DBHandle(DBHandleBase):
    __instance = None

    def __new__(cls, *args, **kwargs):
        """
        Keep singleton.
        """
        if not cls.__instance:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self, path):
        """
        Database handle for the specific

        :param path:
        :return:
        """
        DBHandleBase.__init__(self, path)
