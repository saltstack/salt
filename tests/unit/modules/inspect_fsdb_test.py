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

'''
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
'''

# Import Python Libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath
from salt.modules.inspectlib.fsdb import CsvDB
from salt.modules.inspectlib.entities import CsvDBEntity

from StringIO import StringIO

ensure_in_syspath('../../')


def mock_open(data=None):
    '''
    Mock "open" function in a simple way.

    :param data:
    :return:
    '''
    data = StringIO(data)
    mock = MagicMock(spec=file)
    handle = MagicMock(spec=file)
    handle.write.return_value = None
    handle.__enter__.return_value = data or handle
    mock.return_value = handle

    return mock



class FoobarEntity(CsvDBEntity):
    '''
    Entity for test purposes.
    '''
    _TABLE = 'some_table'

    def __init__(self):
        self.foo = 0
        self.bar = ''
        self.spam = 0.


@skipIf(NO_MOCK, NO_MOCK_REASON)
class InspectorFSDBTestCase(TestCase):
    '''
    Test case for the FSDB: FileSystem Database.

    FSDB is a very simple object-to-CSV storage with a very inefficient
    update/delete operations (nice to have at some point) and efficient
    storing/reading the objects (what is exactly needed for the functionality).

    Main advantage of FSDB is to store Python objects in just a CSV files,
    and have a very small code base.
    '''

    @patch("os.makedirs", MagicMock())
    @patch("os.listdir", MagicMock(return_value=['test_db']))
    @patch("gzip.open", mock_open("foo:int,bar:str"))
    def test_open(self):
        '''
        Test opening the database.
        :return:
        '''
        csvdb = CsvDB('/foobar')
        csvdb.open()
        assert csvdb.list_tables() == ['test_db']
        assert csvdb.is_closed() == False

    @patch("os.makedirs", MagicMock())
    @patch("os.listdir", MagicMock(return_value=['test_db']))
    @patch("gzip.open", mock_open("foo:int,bar:str"))
    def test_close(self):
        '''
        Test closing the database.
        :return:
        '''
        csvdb = CsvDB('/foobar')
        csvdb.open()
        csvdb.close()
        assert csvdb.is_closed() == True

    @patch("os.makedirs", MagicMock())
    @patch("os.path.exists", MagicMock(return_value=False))
    @patch("os.listdir", MagicMock(return_value=['some_table']))
    def test_create_table(self):
        '''
        Test creating table.
        :return:
        '''
        class Writer(StringIO):
            data = []
            def __exit__(self, exc_type, exc_val, exc_tb):
                return self
            def __enter__(self):
                return self
            def read(self, n = -1):
                return ""
            def write(self, s):
                self.data.append(s)

        writer = Writer()
        with patch("gzip.open", MagicMock(return_value=writer)):
            csvdb = CsvDB('/foobar')
            csvdb.open()
            csvdb.create_table_from_object(FoobarEntity())

        assert writer.data[0].strip() == "foo:int,bar:str,spam:float"


    @patch("os.makedirs", MagicMock())
    @patch("os.listdir", MagicMock(return_value=['test_db']))
    def test_list_databases(self):
        '''
        Test storing object into the database.

        :return:
        '''
        csvdb = CsvDB('/foobar')
        assert csvdb.list() == ['test_db']
