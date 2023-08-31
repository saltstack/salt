#
# Copyright 2016 SUSE LLC
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

"""
    :codeauthor: Bo Maryniuk <bo@suse.de>
"""


import csv
import datetime
import gzip
import os
import re
import shutil
import sys

from salt.utils.odict import OrderedDict


class CsvDBEntity:
    """
    Serializable object for the table.
    """

    def _serialize(self, description):
        """
        Serialize the object to a row for CSV according to the table description.

        :return:
        """
        return [getattr(self, attr) for attr in description]


class CsvDB:
    """
    File-based CSV database.
    This database is in-memory operating relatively small plain text csv files.
    """

    def __init__(self, path):
        """
        Constructor to store the database files.

        :param path:
        """
        self._prepare(path)
        self._opened = False
        self.db_path = None
        self._opened = False
        self._tables = {}

    def _prepare(self, path):
        self.path = path
        if not os.path.exists(self.path):
            os.makedirs(self.path)

    def _label(self):
        """
        Create label of the database, based on the date-time.

        :return:
        """
        return datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")

    def new(self):
        """
        Create a new database and opens it.

        :return:
        """
        dbname = self._label()
        self.db_path = os.path.join(self.path, dbname)
        if not os.path.exists(self.db_path):
            os.makedirs(self.db_path)
        self._opened = True
        self.list_tables()

        return dbname

    def purge(self, dbid):
        """
        Purge the database.

        :param dbid:
        :return:
        """
        db_path = os.path.join(self.path, dbid)
        if os.path.exists(db_path):
            shutil.rmtree(db_path, ignore_errors=True)
            return True
        return False

    def flush(self, table):
        """
        Flush table.

        :param table:
        :return:
        """
        table_path = os.path.join(self.db_path, table)
        if os.path.exists(table_path):
            os.unlink(table_path)

    def list(self):
        """
        List all the databases on the given path.

        :return:
        """
        databases = []
        for dbname in os.listdir(self.path):
            databases.append(dbname)
        return list(reversed(sorted(databases)))

    def list_tables(self):
        """
        Load existing tables and their descriptions.

        :return:
        """
        if not self._tables:
            for table_name in os.listdir(self.db_path):
                self._tables[table_name] = self._load_table(table_name)

        return self._tables.keys()

    def _load_table(self, table_name):
        with gzip.open(os.path.join(self.db_path, table_name), "rt") as table:
            return OrderedDict(
                [tuple(elm.split(":")) for elm in next(csv.reader(table))]
            )

    def open(self, dbname=None):
        """
        Open database from the path with the name or latest.
        If there are no yet databases, create a new implicitly.

        :return:
        """
        databases = self.list()
        if self.is_closed():
            self.db_path = os.path.join(
                self.path, dbname or (databases and databases[0] or self.new())
            )
            if not self._opened:
                self.list_tables()
                self._opened = True

    def close(self):
        """
        Close the database.

        :return:
        """
        self._opened = False

    def is_closed(self):
        """
        Return if the database is closed.

        :return:
        """
        return not self._opened

    def create_table_from_object(self, obj):
        """
        Create a table from the object.
        NOTE: This method doesn't stores anything.

        :param obj:
        :return:
        """
        get_type = lambda item: str(type(item)).split("'")[1]
        if not os.path.exists(os.path.join(self.db_path, obj._TABLE)):
            with gzip.open(os.path.join(self.db_path, obj._TABLE), "wt") as table_file:
                csv.writer(table_file).writerow(
                    [
                        "{col}:{type}".format(col=elm[0], type=get_type(elm[1]))
                        for elm in tuple(obj.__dict__.items())
                    ]
                )
            self._tables[obj._TABLE] = self._load_table(obj._TABLE)

    def store(self, obj, distinct=False):
        """
        Store an object in the table.

        :param obj: An object to store
        :param distinct: Store object only if there is none identical of such.
                          If at least one field is different, store it.
        :return:
        """
        if distinct:
            fields = dict(
                zip(
                    self._tables[obj._TABLE].keys(),
                    obj._serialize(self._tables[obj._TABLE]),
                )
            )
            db_obj = self.get(obj.__class__, eq=fields)
            if db_obj and distinct:
                raise Exception("Object already in the database.")
        with gzip.open(os.path.join(self.db_path, obj._TABLE), "at") as table:
            csv.writer(table).writerow(self._validate_object(obj))

    def update(self, obj, matches=None, mt=None, lt=None, eq=None):
        """
        Update object(s) in the database.

        :param obj:
        :param matches:
        :param mt:
        :param lt:
        :param eq:
        :return:
        """
        updated = False
        objects = list()
        for _obj in self.get(obj.__class__):
            if self.__criteria(_obj, matches=matches, mt=mt, lt=lt, eq=eq):
                objects.append(obj)
                updated = True
            else:
                objects.append(_obj)
        self.flush(obj._TABLE)
        self.create_table_from_object(obj)
        for obj in objects:
            self.store(obj)

        return updated

    def delete(self, obj, matches=None, mt=None, lt=None, eq=None):
        """
        Delete object from the database.

        :param obj:
        :param matches:
        :param mt:
        :param lt:
        :param eq:
        :return:
        """
        deleted = False
        objects = list()
        for _obj in self.get(obj):
            if not self.__criteria(_obj, matches=matches, mt=mt, lt=lt, eq=eq):
                objects.append(_obj)
            else:
                deleted = True

        self.flush(obj._TABLE)
        self.create_table_from_object(obj())
        for _obj in objects:
            self.store(_obj)

        return deleted

    def _validate_object(self, obj):
        descr = self._tables.get(obj._TABLE)
        if descr is None:
            raise Exception("Table {} not found.".format(obj._TABLE))
        return obj._serialize(self._tables[obj._TABLE])

    def __criteria(self, obj, matches=None, mt=None, lt=None, eq=None):
        """
        Returns True if object is aligned to the criteria.

        :param obj:
        :param matches:
        :param mt:
        :param lt:
        :param eq:
        :return: Boolean
        """
        # Fail matcher if "less than"
        for field, value in (mt or {}).items():
            if getattr(obj, field) <= value:
                return False

        # Fail matcher if "more than"
        for field, value in (lt or {}).items():
            if getattr(obj, field) >= value:
                return False

        # Fail matcher if "not equal"
        for field, value in (eq or {}).items():
            if getattr(obj, field) != value:
                return False

        # Fail matcher if "doesn't match"
        for field, value in (matches or {}).items():
            if not re.search(value, str(getattr(obj, field))):
                return False

        return True

    def get(self, obj, matches=None, mt=None, lt=None, eq=None):
        """
        Get objects from the table.

        :param table_name:
        :param matches: Regexp.
        :param mt: More than.
        :param lt: Less than.
        :param eq: Equals.
        :return:
        """
        objects = []
        with gzip.open(os.path.join(self.db_path, obj._TABLE), "rt") as table:
            header = None
            for data in csv.reader(table):
                if not header:
                    header = data
                    continue
                _obj = obj()
                for t_attr, t_data in zip(header, data):
                    t_attr, t_type = t_attr.split(":")
                    setattr(_obj, t_attr, self._to_type(t_data, t_type))
                if self.__criteria(_obj, matches=matches, mt=mt, lt=lt, eq=eq):
                    objects.append(_obj)
        return objects

    def _to_type(self, data, type):
        if type == "int":
            data = int(data)
        elif type == "float":
            data = float(data)
        elif type == "long":
            # pylint: disable=undefined-variable,incompatible-py3-code
            data = sys.version_info[0] == 2 and long(data) or int(data)
            # pylint: enable=undefined-variable,incompatible-py3-code
        else:
            data = str(data)
        return data
