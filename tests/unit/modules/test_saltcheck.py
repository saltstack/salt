# -*- coding: utf-8 -*-
'''Unit test for saltcheck execution module'''

# Import python libs
from __future__ import absolute_import, print_function

# Import Salt Testing libs
# from tests.support.mixins import LoaderModuleMockMixin
# from tests.support.unit import skipIf, TestCase
from tests.support.unit import TestCase
# from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
from tests.support.mock import MagicMock, patch

# Import salt libs
# from salt.exceptions import CommandExecutionError
import salt.modules.saltcheck as saltcheck

saltcheck.__salt__ = {}


class SaltCheckTestCase(TestCase):
    ''' SaltCheckTestCase'''

    def test_update_master_cache(self):
        '''test master cache'''
        self.assertTrue(saltcheck.update_master_cache)

    def test_call_salt_command(self):
        '''test simple test.echo module'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'sys.list_modules': MagicMock(return_value=['module1']),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            returned = sc.call_salt_command(fun="test.echo", args=['hello'], kwargs=None)
            self.assertEqual(returned, 'hello')

    def test_call_salt_command2(self):
        '''test simple test.echo module again'''
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'sys.list_modules': MagicMock(return_value=['module1']),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            returned = sc.call_salt_command(fun="test.echo", args=['hello'], kwargs=None)
            self.assertNotEqual(returned, 'not-hello')

    def test__assert_equal1(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = {'a': 1, 'b': 2}
            b = {'a': 1, 'b': 2}
            mybool = sc._SaltCheck__assert_equal(a, b)
            self.assertTrue(mybool)

    def test__assert_equal2(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = {'a': 1, 'b': 2}
            b = {'a': 1, 'b': 2, 'c': 3}
            mybool = sc._SaltCheck__assert_equal(False, True)
            self.assertNotEqual(mybool, True)

    def test__assert_not_equal1(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = {'a': 1, 'b': 2}
            b = {'a': 1, 'b': 2, 'c': 3}
            mybool = sc._SaltCheck__assert_not_equal(a, b)
            self.assertTrue(mybool)

    def test__assert_not_equal2(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = {'a': 1, 'b': 2}
            b = {'a': 1, 'b': 2}
            mybool = sc._SaltCheck__assert_not_equal(a, b)
            self.assertNotEqual(mybool, True)

    def test__assert_true1(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            mybool = sc._SaltCheck__assert_equal(True, True)
            self.assertTrue(mybool)

    def test__assert_true2(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            mybool = sc._SaltCheck__assert_equal(False, True)
            self.assertNotEqual(mybool, True)

    def test__assert_false1(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            mybool = sc._SaltCheck__assert_false(False)
            self.assertTrue(mybool)

    def test__assert_false2(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            mybool = sc._SaltCheck__assert_false(True)
            self.assertNotEqual(mybool, True)

    def test__assert_in1(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = "bob"
            mylist = ['alice', 'bob', 'charles', 'dana']
            mybool = sc._SaltCheck__assert_in(a, mylist)
            self.assertTrue(mybool, True)

    def test__assert_in2(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = "elaine"
            mylist = ['alice', 'bob', 'charles', 'dana']
            mybool = sc._SaltCheck__assert_in(a, mylist)
            self.assertNotEqual(mybool, True)

    def test__assert_not_in1(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = "elaine"
            mylist = ['alice', 'bob', 'charles', 'dana']
            mybool = sc._SaltCheck__assert_not_in(a, mylist)
            self.assertTrue(mybool, True)

    def test__assert_not_in2(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = "bob"
            mylist = ['alice', 'bob', 'charles', 'dana']
            mybool = sc._SaltCheck__assert_not_in(a, mylist)
            self.assertNotEqual(mybool, True)

    def test__assert_greater1(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = 110
            b = 100
            mybool = sc._SaltCheck__assert_greater(a, b)
            self.assertTrue(mybool, True)

    def test__assert_greater2(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = 100
            b = 110
            mybool = sc._SaltCheck__assert_greater(a, b)
            self.assertNotEqual(mybool, True)

    def test__assert_greater3(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = 100
            b = 100
            mybool = sc._SaltCheck__assert_greater(a, b)
            self.assertNotEqual(mybool, True)

    def test__assert_greater_equal_equal1(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = 110
            b = 100
            mybool = sc._SaltCheck__assert_greater_equal(a, b)
            self.assertTrue(mybool, True)

    def test__assert_greater_equal2(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = 100
            b = 110
            mybool = sc._SaltCheck__assert_greater_equal(a, b)
            self.assertNotEqual(mybool, True)

    def test__assert_greater_equal3(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = 100
            b = 100
            mybool = sc._SaltCheck__assert_greater_equal(a, b)
            self.assertEqual(mybool, 'Pass')

    def test__assert_less1(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = 99
            b = 100
            mybool = sc._SaltCheck__assert_less(a, b)
            self.assertTrue(mybool, True)

    def test__assert_less2(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = 110
            b = 99
            mybool = sc._SaltCheck__assert_less(a, b)
            self.assertNotEqual(mybool, True)

    def test__assert_less3(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = 100
            b = 100
            mybool = sc._SaltCheck__assert_less(a, b)
            self.assertNotEqual(mybool, True)

    def test__assert_less_equal1(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = 99
            b = 100
            mybool = sc._SaltCheck__assert_less_equal(a, b)
            self.assertTrue(mybool, True)

    def test__assert_less_equal2(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = 110
            b = 99
            mybool = sc._SaltCheck__assert_less_equal(a, b)
            self.assertNotEqual(mybool, True)

    def test__assert_less_equal3(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'cp.cache_master': MagicMock(return_value=[True])
                                             }):
            sc = saltcheck.SaltCheck()
            a = 100
            b = 100
            mybool = sc._SaltCheck__assert_less_equal(a, b)
            self.assertEqual(mybool, 'Pass')

    def test_run_test_1(self):
        with patch.dict(saltcheck.__salt__, {'config.get': MagicMock(return_value=True),
                                             'sys.list_modules': MagicMock(return_value=['test']),
                                             'sys.list_functions': MagicMock(return_value=['test.echo']),
                                             'cp.cache_master': MagicMock(return_value=[True])}):
            returned = saltcheck.run_test(test={"module_and_function": "test.echo",
                                                "assertion": "assertEqual",
                                                "expected-return": "This works!",
                                                "args": ["This works!"]
                                                })
            self.assertEqual(returned, 'Pass')
