# -*- coding: utf-8 -*-
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

import os
import csv
import datetime


class CsvDBEntity(object):
    '''
    Serializable object for the table.
    '''
    def bind_table(self, table):
        self.__table = table

    def serialize(self):
        '''
        Serialize the object to a row for CSV.

        :return:
        '''


class CsvDB(object):
    '''
    File-based CSV database.
    This database is in-memory operating plain text csv files.
    '''
    def __init__(self, path):
        '''
        Constructor to store the database files.

        :param path:
        '''
        self._prepare(path)
        self._opened = False
        self.db_path = None
        self._opened = False

    def _prepare(self, path):
        self.path = path
        if not os.path.exists(self.path):
            os.makedirs(self.path)

    def _label(self):
        '''
        Create label of the database, based on the date-time.

        :return:
        '''
        return datetime.datetime.utcnow().strftime('%Y%m%d.%H%M%S')

    def new(self):
        '''
        Create a new database and opens it.

        :return:
        '''
        dbname = self._label()
        self.db_path = os.path.join(self.path, dbname)
        if not os.path.exists(self.db_path):
            os.makedirs(self.db_path)
        self._opened = True

        return dbname

    def get_tables(self):
        '''
        Get a list of existin tables in this database.

        :return:
        '''

    def purge(self, dbid):
        '''
        Purge the database.

        :param dbid:
        :return:
        '''

    def list(self):
        '''
        List all the databases on the given path.

        :return:
        '''
        databases = []
        for dbname in os.listdir(self.path):
            databases.append(dbname)
        return list(reversed(sorted(databases)))

    def open(self, dbname=None):
        '''
        Open database from the path with the name or latest.
        If there are no yet databases, create a new implicitly.

        :return:
        '''
        databases = self.list()
        if self.is_closed():
            self.db_path = os.path.join(self.path, dbname or (databases and databases[0] or self.new()))

    def close(self):
        '''
        Close the database.

        :return:
        '''
        self._opened = False

    def is_closed(self):
        '''
        Return if the database is closed.

        :return:
        '''
        return not self._opened

    def table_from_object(self, obj):
        '''
        Create a table from the object.
        NOTE: This method doesn't stores anything.

        :param obj:
        :return:
        '''
        get_type = lambda item: str(type(item)).split("'")[1]
        if not os.path.exists(os.path.join(self.db_path, obj._TABLE)):
            with open(os.path.join(self.db_path, obj._TABLE), 'wb') as table_file:
                csv.writer(table_file).writerow(['{col}:{type}'.format(col=elm[0], type=get_type(elm[1]))
                                                 for elm in tuple(obj.__dict__.items())])

    def store(self, obj):
        '''
        Store an object in the table.

        :param obj:
        :return:
        '''

    def get(self, table_name, matches=None, mt=None, lt=None, eq=None):
        '''
        Get objects from the table.

        :param table_name:
        :param matches: Regexp.
        :param mt: More than.
        :param lt: Less than.
        :param eq: Equals.
        :return:
        '''
        objects = []
        return objects
