# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.mock import NO_MOCK, NO_MOCK_REASON
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.pillar import mysql


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MysqlPillarTestCase(TestCase):
    maxDiff = None

    def test_001_extract_queries_legacy(self):
        return_data = mysql.MySQLExtPillar()
        args, kwargs = ['SELECT blah'], {}
        qbuffer = return_data.extract_queries(args, kwargs)
        self.assertEqual([
            [None, {'query': 'SELECT blah', 'depth': 0, 'as_list': False,
                    'with_lists': None, 'ignore_null': False}]
        ], qbuffer)

    def test_002_extract_queries_list(self):
        return_data = mysql.MySQLExtPillar()
        args, kwargs = [
            'SELECT blah',
            'SELECT blah2',
            ('SELECT blah3',),
            ('SELECT blah4', 2),
            {'query': 'SELECT blah5'},
            {'query': 'SELECT blah6', 'depth': 2},
            {'query': 'SELECT blah7', 'as_list': True},
            {'query': 'SELECT blah8', 'with_lists': '1'},
            {'query': 'SELECT blah9', 'with_lists': '1,2'}
        ], {}
        qbuffer = return_data.extract_queries(args, kwargs)
        self.assertEqual([
            [None, {'query': 'SELECT blah', 'depth': 0, 'as_list': False,
                    'with_lists': None, 'ignore_null': False}],
            [None, {'query': 'SELECT blah2', 'depth': 0, 'as_list': False,
                    'with_lists': None, 'ignore_null': False}],
            [None, {'query': 'SELECT blah3', 'depth': 0, 'as_list': False,
                    'with_lists': None, 'ignore_null': False}],
            [None, {'query': 'SELECT blah4', 'depth': 2, 'as_list': False,
                    'with_lists': None, 'ignore_null': False}],
            [None, {'query': 'SELECT blah5', 'depth': 0, 'as_list': False,
                    'with_lists': None, 'ignore_null': False}],
            [None, {'query': 'SELECT blah6', 'depth': 2, 'as_list': False,
                    'with_lists': None, 'ignore_null': False}],
            [None, {'query': 'SELECT blah7', 'depth': 0, 'as_list': True,
                    'with_lists': None, 'ignore_null': False}],
            [None, {'query': 'SELECT blah8', 'depth': 0, 'as_list': False,
                    'with_lists': [1], 'ignore_null': False}],
            [None, {'query': 'SELECT blah9', 'depth': 0, 'as_list': False,
                    'with_lists': [1, 2], 'ignore_null': False}]
        ], qbuffer)

    def test_003_extract_queries_kwarg(self):
        return_data = mysql.MySQLExtPillar()
        args, kwargs = [], {
            '1': 'SELECT blah',
            '2': 'SELECT blah2',
            '3': ('SELECT blah3',),
            '4': ('SELECT blah4', 2),
            '5': {'query': 'SELECT blah5'},
            '6': {'query': 'SELECT blah6', 'depth': 2},
            '7': {'query': 'SELECT blah7', 'as_list': True},
        }
        qbuffer = return_data.extract_queries(args, kwargs)
        self.assertEqual([
            ['1', {'query': 'SELECT blah', 'depth': 0, 'as_list': False,
                   'with_lists': None, 'ignore_null': False}],
            ['2', {'query': 'SELECT blah2', 'depth': 0, 'as_list': False,
                   'with_lists': None, 'ignore_null': False}],
            ['3', {'query': 'SELECT blah3', 'depth': 0, 'as_list': False,
                   'with_lists': None, 'ignore_null': False}],
            ['4', {'query': 'SELECT blah4', 'depth': 2, 'as_list': False,
                   'with_lists': None, 'ignore_null': False}],
            ['5', {'query': 'SELECT blah5', 'depth': 0, 'as_list': False,
                   'with_lists': None, 'ignore_null': False}],
            ['6', {'query': 'SELECT blah6', 'depth': 2, 'as_list': False,
                   'with_lists': None, 'ignore_null': False}],
            ['7', {'query': 'SELECT blah7', 'depth': 0, 'as_list': True,
                   'with_lists': None, 'ignore_null': False}]
        ], qbuffer)

    def test_004_extract_queries_mixed(self):
        return_data = mysql.MySQLExtPillar()
        args, kwargs = [
            'SELECT blah1',
            ('SELECT blah2', 2),
            {'query': 'SELECT blah3', 'as_list': True},
        ], {
            '1': 'SELECT blah1',
            '2': ('SELECT blah2', 2),
            '3': {'query': 'SELECT blah3', 'as_list': True},
        }
        qbuffer = return_data.extract_queries(args, kwargs)
        self.assertEqual([
            [None, {'query': 'SELECT blah1', 'depth': 0, 'as_list': False,
                    'with_lists': None, 'ignore_null': False}],
            [None, {'query': 'SELECT blah2', 'depth': 2, 'as_list': False,
                    'with_lists': None, 'ignore_null': False}],
            [None, {'query': 'SELECT blah3', 'depth': 0, 'as_list': True,
                    'with_lists': None, 'ignore_null': False}],
            ['1', {'query': 'SELECT blah1', 'depth': 0, 'as_list': False,
                   'with_lists': None, 'ignore_null': False}],
            ['2', {'query': 'SELECT blah2', 'depth': 2, 'as_list': False,
                   'with_lists': None, 'ignore_null': False}],
            ['3', {'query': 'SELECT blah3', 'depth': 0, 'as_list': True,
                   'with_lists': None, 'ignore_null': False}]
        ], qbuffer)

    def test_005_extract_queries_bogus_list(self):
        # This test is specifically checking that empty queries are dropped
        return_data = mysql.MySQLExtPillar()
        args, kwargs = [
            'SELECT blah',
            '',
            'SELECT blah2',
            ('SELECT blah3',),
            ('',),
            ('SELECT blah4', 2),
            tuple(),
            ('SELECT blah5',),
            {'query': 'SELECT blah6'},
            {'query': ''},
            {'query': 'SELECT blah7', 'depth': 2},
            {'not_a_query': 'in sight!'},
            {'query': 'SELECT blah8', 'as_list': True},
        ], {}
        qbuffer = return_data.extract_queries(args, kwargs)
        self.assertEqual([
            [None, {'query': 'SELECT blah', 'depth': 0, 'as_list': False,
                    'with_lists': None, 'ignore_null': False}],
            [None, {'query': 'SELECT blah2', 'depth': 0, 'as_list': False,
                    'with_lists': None, 'ignore_null': False}],
            [None, {'query': 'SELECT blah3', 'depth': 0, 'as_list': False,
                    'with_lists': None, 'ignore_null': False}],
            [None, {'query': 'SELECT blah4', 'depth': 2, 'as_list': False,
                    'with_lists': None, 'ignore_null': False}],
            [None, {'query': 'SELECT blah5', 'depth': 0, 'as_list': False,
                    'with_lists': None, 'ignore_null': False}],
            [None, {'query': 'SELECT blah6', 'depth': 0, 'as_list': False,
                    'with_lists': None, 'ignore_null': False}],
            [None, {'query': 'SELECT blah7', 'depth': 2, 'as_list': False,
                    'with_lists': None, 'ignore_null': False}],
            [None, {'query': 'SELECT blah8', 'depth': 0, 'as_list': True,
                    'with_lists': None, 'ignore_null': False}]
        ], qbuffer)

    def test_006_extract_queries_bogus_kwargs(self):
        # this test is cut down as most of the path matches test_*_bogus_list
        return_data = mysql.MySQLExtPillar()
        args, kwargs = [], {
            '1': 'SELECT blah',
            '2': '',
            '3': 'SELECT blah2'
        }
        qbuffer = return_data.extract_queries(args, kwargs)
        self.assertEqual([
            ['1', {'query': 'SELECT blah', 'depth': 0, 'as_list': False,
                   'with_lists': None, 'ignore_null': False}],
            ['3', {'query': 'SELECT blah2', 'depth': 0, 'as_list': False,
                   'with_lists': None, 'ignore_null': False}]
        ], qbuffer)

    def test_011_enter_root(self):
        return_data = mysql.MySQLExtPillar()
        return_data.enter_root("test")
        self.assertEqual(return_data.result["test"], return_data.focus)
        return_data.enter_root(None)
        self.assertEqual(return_data.result, return_data.focus)

    def test_021_process_fields(self):
        return_data = mysql.MySQLExtPillar()
        return_data.process_fields(['a', 'b'], 0)
        self.assertEqual(return_data.num_fields, 2)
        self.assertEqual(return_data.depth, 1)
        return_data.process_fields(['a', 'b'], 2)
        self.assertEqual(return_data.num_fields, 2)
        self.assertEqual(return_data.depth, 1)
        return_data.process_fields(['a', 'b', 'c', 'd'], 0)
        self.assertEqual(return_data.num_fields, 4)
        self.assertEqual(return_data.depth, 3)
        return_data.process_fields(['a', 'b', 'c', 'd'], 1)
        self.assertEqual(return_data.num_fields, 4)
        self.assertEqual(return_data.depth, 1)
        return_data.process_fields(['a', 'b', 'c', 'd'], 2)
        self.assertEqual(return_data.num_fields, 4)
        self.assertEqual(return_data.depth, 2)
        return_data.process_fields(['a', 'b', 'c', 'd'], 3)
        self.assertEqual(return_data.num_fields, 4)
        self.assertEqual(return_data.depth, 3)
        return_data.process_fields(['a', 'b', 'c', 'd'], 4)
        self.assertEqual(return_data.num_fields, 4)
        self.assertEqual(return_data.depth, 3)

    def test_111_process_results_legacy(self):
        return_data = mysql.MySQLExtPillar()
        return_data.process_fields(['a', 'b'], 0)
        return_data.with_lists = []
        return_data.process_results([[1, 2]])
        self.assertEqual(
             {1: 2},
             return_data.result
        )

    def test_112_process_results_legacy_multiple(self):
        return_data = mysql.MySQLExtPillar()
        return_data.process_fields(['a', 'b'], 0)
        return_data.with_lists = []
        return_data.process_results([[1, 2], [3, 4], [5, 6]])
        self.assertEqual(
             {1: 2, 3: 4, 5: 6},
             return_data.result
        )

    def test_121_process_results_depth_0(self):
        return_data = mysql.MySQLExtPillar()
        return_data.process_fields(['a', 'b', 'c', 'd'], 0)
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_results([[1, 2, 3, 4], [5, 6, 7, 8]])
        self.assertEqual(
             {1: {2: {3: 4}}, 5: {6: {7: 8}}},
             return_data.result
        )

    def test_122_process_results_depth_1(self):
        return_data = mysql.MySQLExtPillar()
        return_data.process_fields(['a', 'b', 'c', 'd'], 1)
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_results([[1, 2, 3, 4], [5, 6, 7, 8]])
        self.assertEqual(
             {1: {'b': 2, 'c': 3, 'd': 4}, 5: {'b': 6, 'c': 7, 'd': 8}},
             return_data.result
        )

    def test_123_process_results_depth_2(self):
        return_data = mysql.MySQLExtPillar()
        return_data.process_fields(['a', 'b', 'c', 'd'], 2)
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_results([[1, 2, 3, 4], [5, 6, 7, 8]])
        self.assertEqual(
             {1: {2: {'c': 3, 'd': 4}}, 5: {6: {'c': 7, 'd': 8}}},
             return_data.result
        )

    def test_124_process_results_depth_3(self):
        return_data = mysql.MySQLExtPillar()
        return_data.process_fields(['a', 'b', 'c', 'd'], 3)
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_results([[1, 2, 3, 4], [5, 6, 7, 8]])
        self.assertEqual(
             {1: {2: {3: 4}}, 5: {6: {7: 8}}},
             return_data.result
        )

    def test_125_process_results_depth_4(self):
        return_data = mysql.MySQLExtPillar()
        return_data.process_fields(['a', 'b', 'c', 'd'], 4)
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_results([[1, 2, 3, 4], [5, 6, 7, 8]])
        self.assertEqual(
             {1: {2: {3: 4}}, 5: {6: {7: 8}}},
             return_data.result
        )

    def test_131_process_results_overwrite_legacy_multiple(self):
        return_data = mysql.MySQLExtPillar()
        return_data.process_fields(['a', 'b'], 0)
        return_data.with_lists = []
        return_data.process_results([[1, 2], [3, 4], [1, 6]])
        self.assertEqual(
             {1: 6, 3: 4},
             return_data.result
        )

    def test_132_process_results_merge_depth_0(self):
        return_data = mysql.MySQLExtPillar()
        return_data.process_fields(['a', 'b', 'c', 'd'], 0)
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_results([[1, 2, 3, 4], [1, 6, 7, 8]])
        self.assertEqual(
             {1: {2: {3: 4}, 6: {7: 8}}},
             return_data.result
        )

    def test_133_process_results_overwrite_depth_0(self):
        return_data = mysql.MySQLExtPillar()
        return_data.process_fields(['a', 'b', 'c', 'd'], 0)
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_results([[1, 2, 3, 4], [1, 2, 3, 8]])
        self.assertEqual(
             {1: {2: {3: 8}}},
             return_data.result
        )

    def test_134_process_results_deepmerge_depth_0(self):
        return_data = mysql.MySQLExtPillar()
        return_data.process_fields(['a', 'b', 'c', 'd'], 0)
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_results([[1, 2, 3, 4], [1, 2, 7, 8]])
        self.assertEqual(
             {1: {2: {3: 4, 7: 8}}},
             return_data.result
        )

    def test_135_process_results_overwrite_depth_1(self):
        return_data = mysql.MySQLExtPillar()
        return_data.process_fields(['a', 'b', 'c', 'd'], 1)
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_results([[1, 2, 3, 4], [1, 6, 7, 8]])
        self.assertEqual(
             {1: {'b': 6, 'c': 7, 'd': 8}},
             return_data.result
        )

    def test_136_process_results_merge_depth_2(self):
        return_data = mysql.MySQLExtPillar()
        return_data.process_fields(['a', 'b', 'c', 'd'], 2)
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_results([[1, 2, 3, 4], [1, 6, 7, 8]])
        self.assertEqual(
             {1: {2: {'c': 3, 'd': 4}, 6: {'c': 7, 'd': 8}}},
             return_data.result
        )

    def test_137_process_results_overwrite_depth_2(self):
        return_data = mysql.MySQLExtPillar()
        return_data.process_fields(['a', 'b', 'c', 'd'], 2)
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_results([[1, 2, 3, 4], [1, 2, 7, 8]])
        self.assertEqual(
             {1: {2: {'c': 7, 'd': 8}}},
             return_data.result
        )

    def test_201_process_results_complexity_multiresults(self):
        return_data = mysql.MySQLExtPillar()
        return_data.process_fields(['a', 'b', 'c', 'd'], 2)
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_results([[1, 2, 3, 4]])
        return_data.process_results([[1, 2, 7, 8]])
        self.assertEqual(
             {1: {2: {'c': 7, 'd': 8}}},
             return_data.result
        )

    def test_202_process_results_complexity_as_list(self):
        return_data = mysql.MySQLExtPillar()
        return_data.process_fields(['a', 'b', 'c', 'd'], 2)
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.as_list = True
        return_data.process_results([[1, 2, 3, 4]])
        return_data.process_results([[1, 2, 7, 8]])
        self.assertEqual(
             {1: {2: {'c': [3, 7], 'd': [4, 8]}}},
             return_data.result
        )

    def test_203_process_results_complexity_as_list_deeper(self):
        return_data = mysql.MySQLExtPillar()
        return_data.process_fields(['a', 'b', 'c', 'd'], 0)
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.as_list = True
        return_data.process_results([[1, 2, 3, 4]])
        return_data.process_results([[1, 2, 3, 8]])
        self.assertEqual(
             {1: {2: {3: [4, 8]}}},
             return_data.result
        )

    def test_204_process_results_complexity_as_list_mismatch_depth(self):
        return_data = mysql.MySQLExtPillar()
        return_data.as_list = True
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_fields(['a', 'b', 'c', 'd'], 0)
        return_data.process_results([[1, 2, 3, 4]])
        return_data.process_results([[1, 2, 3, 5]])
        return_data.process_fields(['a', 'b', 'c', 'd', 'e'], 0)
        return_data.process_results([[1, 2, 3, 6, 7]])
        self.assertEqual(
             {1: {2: {3: [4, 5, {6: 7}]}}},
             return_data.result
        )

    def test_205_process_results_complexity_as_list_mismatch_depth_reversed(self):
        return_data = mysql.MySQLExtPillar()
        return_data.as_list = True
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_fields(['a', 'b', 'c', 'd', 'e'], 0)
        return_data.process_results([[1, 2, 3, 6, 7]])
        return_data.process_results([[1, 2, 3, 8, 9]])
        return_data.process_fields(['a', 'b', 'c', 'd'], 0)
        return_data.process_results([[1, 2, 3, 4]])
        return_data.process_results([[1, 2, 3, 5]])
        self.assertEqual(
             {1: {2: {3: [{6: 7, 8: 9}, 4, 5]}}},
             return_data.result
        )

    def test_206_process_results_complexity_as_list_mismatch_depth_weird_order(self):
        return_data = mysql.MySQLExtPillar()
        return_data.as_list = True
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_fields(['a', 'b', 'c', 'd', 'e'], 0)
        return_data.process_results([[1, 2, 3, 6, 7]])
        return_data.process_fields(['a', 'b', 'c', 'd'], 0)
        return_data.process_results([[1, 2, 3, 4]])
        return_data.process_fields(['a', 'b', 'c', 'd', 'e'], 0)
        return_data.process_results([[1, 2, 3, 8, 9]])
        return_data.process_fields(['a', 'b', 'c', 'd'], 0)
        return_data.process_results([[1, 2, 3, 5]])
        self.assertEqual(
             {1: {2: {3: [{6: 7, }, 4, {8: 9}, 5]}}},
             return_data.result
        )

    def test_207_process_results_complexity_collision_mismatch_depth(self):
        return_data = mysql.MySQLExtPillar()
        return_data.as_list = False
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_fields(['a', 'b', 'c', 'd'], 0)
        return_data.process_results([[1, 2, 3, 4]])
        return_data.process_results([[1, 2, 3, 5]])
        return_data.process_fields(['a', 'b', 'c', 'd', 'e'], 0)
        return_data.process_results([[1, 2, 3, 6, 7]])
        self.assertEqual(
             {1: {2: {3: {6: 7}}}},
             return_data.result
        )

    def test_208_process_results_complexity_collision_mismatch_depth_reversed(self):
        return_data = mysql.MySQLExtPillar()
        return_data.as_list = False
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_fields(['a', 'b', 'c', 'd', 'e'], 0)
        return_data.process_results([[1, 2, 3, 6, 7]])
        return_data.process_results([[1, 2, 3, 8, 9]])
        return_data.process_fields(['a', 'b', 'c', 'd'], 0)
        return_data.process_results([[1, 2, 3, 4]])
        return_data.process_results([[1, 2, 3, 5]])
        self.assertEqual(
             {1: {2: {3: 5}}},
             return_data.result
        )

    def test_209_process_results_complexity_collision_mismatch_depth_weird_order(self):
        return_data = mysql.MySQLExtPillar()
        return_data.as_list = False
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_fields(['a', 'b', 'c', 'd', 'e'], 0)
        return_data.process_results([[1, 2, 3, 6, 7]])
        return_data.process_fields(['a', 'b', 'c', 'd'], 0)
        return_data.process_results([[1, 2, 3, 4]])
        return_data.process_fields(['a', 'b', 'c', 'd', 'e'], 0)
        return_data.process_results([[1, 2, 3, 8, 9]])
        return_data.process_fields(['a', 'b', 'c', 'd'], 0)
        return_data.process_results([[1, 2, 3, 5]])
        self.assertEqual(
             {1: {2: {3: 5}}},
             return_data.result
        )

    def test_20A_process_results_complexity_as_list_vary(self):
        return_data = mysql.MySQLExtPillar()
        return_data.as_list = True
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_fields(['a', 'b', 'c', 'd', 'e'], 0)
        return_data.process_results([[1, 2, 3, 6, 7]])
        return_data.process_results([[1, 2, 3, 8, 9]])
        return_data.process_fields(['a', 'b', 'c', 'd'], 0)
        return_data.process_results([[1, 2, 3, 4]])
        return_data.as_list = False
        return_data.process_results([[1, 2, 3, 5]])
        self.assertEqual(
             {1: {2: {3: 5}}},
             return_data.result
        )

    def test_207_process_results_complexity_roots_collision(self):
        return_data = mysql.MySQLExtPillar()
        return_data.as_list = False
        return_data.with_lists = []
        return_data.enter_root(None)
        return_data.process_fields(['a', 'b', 'c', 'd'], 0)
        return_data.process_results([[1, 2, 3, 4]])
        return_data.enter_root(1)
        return_data.process_results([[5, 6, 7, 8]])
        self.assertEqual(
             {1: {5: {6: {7: 8}}}},
             return_data.result
        )

    def test_301_process_results_with_lists(self):
        return_data = mysql.MySQLExtPillar()
        return_data.as_list = False
        return_data.with_lists = [1, 3]
        return_data.enter_root(None)
        return_data.process_fields(['a', 'b', 'c', 'd', 'e', 'v'], 0)
        return_data.process_results([['a', 'b', 'c', 'd', 'e', 1],
                                     ['a', 'b', 'c', 'f', 'g', 2],
                                     ['a', 'z', 'h', 'y', 'j', 3],
                                     ['a', 'z', 'h', 'y', 'k', 4]])
        self.assertEqual(
            {'a': [
                  {'c': [
                      {'e': 1},
                      {'g': 2}
                      ]
                  },
                  {'h': [
                      {'j': 3, 'k': 4}
                      ]
                  }
            ]},
             return_data.result
        )

    def test_302_process_results_with_lists_consecutive(self):
        return_data = mysql.MySQLExtPillar()
        return_data.as_list = False
        return_data.with_lists = [1, 2, 3]
        return_data.enter_root(None)
        return_data.process_fields(['a', 'b', 'c', 'd', 'e', 'v'], 0)
        return_data.process_results([['a', 'b', 'c', 'd', 'e', 1],
                                     ['a', 'b', 'c', 'f', 'g', 2],
                                     ['a', 'z', 'h', 'y', 'j', 3],
                                     ['a', 'z', 'h', 'y', 'k', 4]])
        self.assertEqual(
            {'a': [
                  [[
                      {'e': 1},
                      {'g': 2}
                      ]
                  ],
                  [[
                      {'j': 3, 'k': 4}
                      ]
                  ]
            ]},
             return_data.result
        )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MysqlPillarTestCase, needs_daemon=False)
