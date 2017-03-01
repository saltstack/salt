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

# Import Salt Testing Libs
from tests.support.unit import TestCase
from tests.support.mock import MagicMock, patch

from salt.modules.inspectlib.fsdb import CsvDB
from salt.modules.inspectlib.entities import CsvDBEntity
from salt.utils.odict import OrderedDict

from salt.ext.six.moves import StringIO


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


class Writable(StringIO):
    def __init__(self, data=None):
        if data:
            StringIO.__init__(self, data)
        else:
            StringIO.__init__(self)
        self.data = []

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self

    def __enter__(self):
        return self

    def write(self, s):
        self.data.append(s)


class FoobarEntity(CsvDBEntity):
    '''
    Entity for test purposes.
    '''
    _TABLE = 'some_table'

    def __init__(self):
        self.foo = 0
        self.bar = ''
        self.spam = 0.


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
        assert csvdb.is_closed() is False

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
        assert csvdb.is_closed() is True

    @patch("os.makedirs", MagicMock())
    @patch("os.path.exists", MagicMock(return_value=False))
    @patch("os.listdir", MagicMock(return_value=['some_table']))
    def test_create_table(self):
        '''
        Test creating table.
        :return:
        '''
        writable = Writable()
        with patch("gzip.open", MagicMock(return_value=writable)):
            csvdb = CsvDB('/foobar')
            csvdb.open()
            csvdb.create_table_from_object(FoobarEntity())

        assert writable.data[0].strip() == "foo:int,bar:str,spam:float"

    @patch("os.makedirs", MagicMock())
    @patch("os.listdir", MagicMock(return_value=['test_db']))
    def test_list_databases(self):
        '''
        Test list databases.
        :return:
        '''
        csvdb = CsvDB('/foobar')
        assert csvdb.list() == ['test_db']

    @patch("os.makedirs", MagicMock())
    @patch("os.path.exists", MagicMock(return_value=False))
    @patch("os.listdir", MagicMock(return_value=['some_table']))
    def test_add_object(self):
        '''
        Test storing object into the database.
        :return:
        '''
        writable = Writable()
        with patch("gzip.open", MagicMock(return_value=writable)):
            obj = FoobarEntity()
            obj.foo = 123
            obj.bar = 'test entity'
            obj.spam = 0.123

            csvdb = CsvDB('/foobar')
            csvdb.open()
            csvdb._tables = {'some_table': OrderedDict([tuple(elm.split(':'))
                                                        for elm in ["foo:int", "bar:str", "spam:float"]])}
            csvdb.store(obj)
            assert writable.data[0].strip() == '123,test entity,0.123'

    @patch("os.makedirs", MagicMock())
    @patch("os.listdir", MagicMock(return_value=['test_db']))
    def test_delete_object(self):
        '''
        Deleting an object from the store.
        :return:
        '''
        with patch("gzip.open", MagicMock()):
            with patch("csv.reader", MagicMock(return_value=iter([[], ['foo:int', 'bar:str', 'spam:float'],
                                                                  ['123', 'test', '0.123'],
                                                                  ['234', 'another', '0.456']]))):
                class InterceptedCsvDB(CsvDB):
                    def __init__(self, path):
                        CsvDB.__init__(self, path)
                        self._remained = list()

                    def store(self, obj, distinct=False):
                        self._remained.append(obj)

                csvdb = InterceptedCsvDB('/foobar')
                csvdb.open()
                csvdb.create_table_from_object = MagicMock()
                csvdb.flush = MagicMock()

                assert csvdb.delete(FoobarEntity, eq={'foo': 123}) is True
                assert len(csvdb._remained) == 1

                assert csvdb._remained[0].foo == 234
                assert csvdb._remained[0].bar == 'another'
                assert csvdb._remained[0].spam == 0.456

    @patch("os.makedirs", MagicMock())
    @patch("os.listdir", MagicMock(return_value=['test_db']))
    def test_update_object(self):
        '''
        Updating an object from the store.
        :return:
        '''
        with patch("gzip.open", MagicMock()):
            with patch("csv.reader", MagicMock(return_value=iter([[], ['foo:int', 'bar:str', 'spam:float'],
                                                                  ['123', 'test', '0.123'],
                                                                  ['234', 'another', '0.456']]))):
                obj = FoobarEntity()
                obj.foo = 123
                obj.bar = 'updated'
                obj.spam = 0.5

                class InterceptedCsvDB(CsvDB):
                    def __init__(self, path):
                        CsvDB.__init__(self, path)
                        self._remained = list()

                    def store(self, obj, distinct=False):
                        self._remained.append(obj)

                csvdb = InterceptedCsvDB('/foobar')
                csvdb.open()
                csvdb.create_table_from_object = MagicMock()
                csvdb.flush = MagicMock()

                assert csvdb.update(obj, eq={'foo': 123}) is True
                assert len(csvdb._remained) == 2

                assert csvdb._remained[0].foo == 123
                assert csvdb._remained[0].bar == 'updated'
                assert csvdb._remained[0].spam == 0.5

                assert csvdb._remained[1].foo == 234
                assert csvdb._remained[1].bar == 'another'
                assert csvdb._remained[1].spam == 0.456

    @patch("os.makedirs", MagicMock())
    @patch("os.listdir", MagicMock(return_value=['test_db']))
    def test_get_object(self):
        '''
        Getting an object from the store.
        :return:
        '''
        with patch("gzip.open", MagicMock()):
            with patch("csv.reader", MagicMock(return_value=iter([[], ['foo:int', 'bar:str', 'spam:float'],
                                                                  ['123', 'test', '0.123'],
                                                                  ['234', 'another', '0.456']]))):
                csvdb = CsvDB('/foobar')
                csvdb.open()
                entities = csvdb.get(FoobarEntity)
                assert list == type(entities)
                assert len(entities) == 2

                assert entities[0].foo == 123
                assert entities[0].bar == 'test'
                assert entities[0].spam == 0.123

                assert entities[1].foo == 234
                assert entities[1].bar == 'another'
                assert entities[1].spam == 0.456

    @patch("os.makedirs", MagicMock())
    @patch("os.listdir", MagicMock(return_value=['test_db']))
    def test_get_obj_equals(self):
        '''
        Getting an object from the store with conditions
        :return:
        '''
        with patch("gzip.open", MagicMock()):
            with patch("csv.reader", MagicMock(return_value=iter([[], ['foo:int', 'bar:str', 'spam:float'],
                                                                  ['123', 'test', '0.123'],
                                                                  ['234', 'another', '0.456']]))):
                csvdb = CsvDB('/foobar')
                csvdb.open()

                entities = csvdb.get(FoobarEntity, eq={'foo': 123})
                assert list == type(entities)
                assert len(entities) == 1

                assert entities[0].foo == 123
                assert entities[0].bar == 'test'
                assert entities[0].spam == 0.123

    @patch("os.makedirs", MagicMock())
    @patch("os.listdir", MagicMock(return_value=['test_db']))
    def test_get_obj_more_than(self):
        '''
        Getting an object from the store with conditions
        :return:
        '''
        with patch("gzip.open", MagicMock()):
            with patch("csv.reader", MagicMock(return_value=iter([[], ['foo:int', 'bar:str', 'spam:float'],
                                                                  ['123', 'test', '0.123'],
                                                                  ['234', 'another', '0.456']]))):
                csvdb = CsvDB('/foobar')
                csvdb.open()

                entities = csvdb.get(FoobarEntity, mt={'foo': 123})
                assert list == type(entities)
                assert len(entities) == 1

                assert entities[0].foo == 234
                assert entities[0].bar == 'another'
                assert entities[0].spam == 0.456

    @patch("os.makedirs", MagicMock())
    @patch("os.listdir", MagicMock(return_value=['test_db']))
    def test_get_obj_less_than(self):
        '''
        Getting an object from the store with conditions
        :return:
        '''
        with patch("gzip.open", MagicMock()):
            with patch("csv.reader", MagicMock(return_value=iter([[], ['foo:int', 'bar:str', 'spam:float'],
                                                                  ['123', 'test', '0.123'],
                                                                  ['234', 'another', '0.456']]))):
                csvdb = CsvDB('/foobar')
                csvdb.open()

                entities = csvdb.get(FoobarEntity, lt={'foo': 234})
                assert list == type(entities)
                assert len(entities) == 1

                assert entities[0].foo == 123
                assert entities[0].bar == 'test'
                assert entities[0].spam == 0.123

    @patch("os.makedirs", MagicMock())
    @patch("os.listdir", MagicMock(return_value=['test_db']))
    def test_get_obj_matching(self):
        '''
        Getting an object from the store with conditions
        :return:
        '''
        with patch("gzip.open", MagicMock()):
            with patch("csv.reader", MagicMock(return_value=iter([[], ['foo:int', 'bar:str', 'spam:float'],
                                                                  ['123', 'this is test of something', '0.123'],
                                                                  ['234', 'another test of stuff', '0.456']]))):
                csvdb = CsvDB('/foobar')
                csvdb.open()

                entities = csvdb.get(FoobarEntity, matches={'bar': r'is\stest'})
                assert list == type(entities)
                assert len(entities) == 1

                assert entities[0].foo == 123
                assert entities[0].bar == 'this is test of something'
                assert entities[0].spam == 0.123

    def test_obj_serialization(self):
        '''
        Test object serialization.
        :return:
        '''
        obj = FoobarEntity()
        obj.foo = 123
        obj.bar = 'test entity'
        obj.spam = 0.123

        descr = OrderedDict([tuple(elm.split(':')) for elm in ["foo:int", "bar:str", "spam:float"]])
        assert obj._serialize(descr) == [123, 'test entity', 0.123]

    @patch("os.makedirs", MagicMock())
    @patch("os.path.exists", MagicMock(return_value=False))
    @patch("os.listdir", MagicMock(return_value=['some_table']))
    def test_obj_validation(self):
        '''
        Test object validation.

        :return:
        '''
        obj = FoobarEntity()
        obj.foo = 123
        obj.bar = 'test entity'
        obj.spam = 0.123

        csvdb = CsvDB('/foobar')
        csvdb._tables = {'some_table': OrderedDict([tuple(elm.split(':'))
                                                    for elm in ["foo:int", "bar:str", "spam:float"]])}
        assert csvdb._validate_object(obj) == [123, 'test entity', 0.123]

    @patch("os.makedirs", MagicMock())
    @patch("os.path.exists", MagicMock(return_value=False))
    @patch("os.listdir", MagicMock(return_value=['some_table']))
    def test_criteria(self):
        '''
        Test criteria selector.

        :return:
        '''
        obj = FoobarEntity()
        obj.foo = 123
        obj.bar = 'test entity'
        obj.spam = 0.123
        obj.pi = 3.14

        cmp = CsvDB('/foobar')._CsvDB__criteria

        # Single
        assert cmp(obj, eq={'foo': 123}) is True
        assert cmp(obj, lt={'foo': 124}) is True
        assert cmp(obj, mt={'foo': 122}) is True

        assert cmp(obj, eq={'foo': 0}) is False
        assert cmp(obj, lt={'foo': 123}) is False
        assert cmp(obj, mt={'foo': 123}) is False

        assert cmp(obj, matches={'bar': r't\se.*?'}) is True
        assert cmp(obj, matches={'bar': r'\s\sentity'}) is False

        # Combined
        assert cmp(obj, eq={'foo': 123, 'bar': r'test entity', 'spam': 0.123}) is True
        assert cmp(obj, eq={'foo': 123, 'bar': r'test', 'spam': 0.123}) is False

        assert cmp(obj, lt={'foo': 124, 'spam': 0.124}) is True
        assert cmp(obj, lt={'foo': 124, 'spam': 0.123}) is False

        assert cmp(obj, mt={'foo': 122, 'spam': 0.122}) is True
        assert cmp(obj, mt={'foo': 122, 'spam': 0.123}) is False

        assert cmp(obj, matches={'bar': r'test'}, mt={'foo': 122}, lt={'spam': 0.124}, eq={'pi': 3.14}) is True

        assert cmp(obj, matches={'bar': r'^test.*?y$'}, mt={'foo': 122}, lt={'spam': 0.124}, eq={'pi': 3.14}) is True
        assert cmp(obj, matches={'bar': r'^ent'}, mt={'foo': 122}, lt={'spam': 0.124}, eq={'pi': 3.14}) is False
        assert cmp(obj, matches={'bar': r'^test.*?y$'}, mt={'foo': 123}, lt={'spam': 0.124}, eq={'pi': 3.14}) is False
