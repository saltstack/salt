# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.states.mysql_query as mysql_query


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MysqlQueryTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.mysql_query
    '''
    def setup_loader_modules(self):
        return {mysql_query: {}}

    # 'run' function tests: 1

    def test_run(self):
        '''
        Test to execute an arbitrary query on the specified database.
        '''
        name = 'query_id'
        database = 'my_database'
        query = "SELECT * FROM table;"

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        mock_str = MagicMock(return_value='salt')
        mock_none = MagicMock(return_value=None)
        mock_dict = MagicMock(return_value={'salt': 'SALT'})
        mock_lst = MagicMock(return_value=['grain'])
        with patch.dict(mysql_query.__salt__, {'mysql.db_exists': mock_f}):
            with patch.object(mysql_query, '_get_mysql_error', mock_str):
                ret.update({'comment': 'salt', 'result': False})
                self.assertDictEqual(mysql_query.run(name, database, query),
                                     ret)

            with patch.object(mysql_query, '_get_mysql_error', mock_none):
                comt = ('Database {0} is not present'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(mysql_query.run(name, database, query),
                                     ret)

        with patch.dict(mysql_query.__salt__, {'mysql.db_exists': mock_t,
                                               'grains.ls': mock_lst,
                                               'grains.get': mock_dict,
                                               'mysql.query': mock_str}):
            comt = ('No execution needed. Grain grain already set')
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(mysql_query.run(name, database, query,
                                                 output='grain', grain='grain',
                                                 overwrite=False), ret)

            with patch.dict(mysql_query.__opts__, {'test': True}):
                comt = ('Query would execute, storing result in grain: grain')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(mysql_query.run(name, database, query,
                                                     output='grain',
                                                     grain='grain'), ret)

                comt = ('Query would execute, storing result'
                        ' in grain: grain:salt')
                ret.update({'comment': comt})
                self.assertDictEqual(mysql_query.run(name, database, query,
                                                     output='grain',
                                                     grain='grain',
                                                     key='salt'), ret)

                comt = ('Query would execute, storing result in file: salt')
                ret.update({'comment': comt})
                self.assertDictEqual(mysql_query.run(name, database, query,
                                                     output='salt',
                                                     grain='grain'), ret)

                comt = ('Query would execute, not storing result')
                ret.update({'comment': comt})
                self.assertDictEqual(mysql_query.run(name, database, query),
                                     ret)

            comt = ('No execution needed. Grain grain:salt already set')
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(mysql_query.run(name, database, query,
                                                 output='grain', grain='grain',
                                                 key='salt', overwrite=False),
                                 ret)

            comt = ("Error: output type 'grain' needs the grain parameter\n")
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(mysql_query.run(name, database, query,
                                                 output='grain'), ret)

            with patch.object(os.path, 'isfile', mock_t):
                comt = ('No execution needed. File salt already set')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(mysql_query.run(name, database, query,
                                                     output='salt',
                                                     grain='grain',
                                                     overwrite=False), ret)

            with patch.dict(mysql_query.__opts__, {'test': False}):
                ret.update({'comment': 'salt',
                            'changes': {'query': 'Executed'}})
                self.assertDictEqual(mysql_query.run(name, database, query),
                                     ret)
