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

    def _label(self):
        '''
        Create label of the database, based on the date-time.

        :return:
        '''

    def new(self):
        '''
        Create a new database.

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
        List all the databases.

        :return:
        '''

    def open(self):
        '''
        Open database.

        :return:
        '''

    def close(self):
        '''
        Close the database.

        :return:
        '''

    def is_closed(self):
        '''
        Return if the database is closed.

        :return:
        '''