#!/usr/bin/env python
import unittest
import sys, os, os.path
import yaml
#sys.path.append(os.path.abspath(sys.path[0]) + '/../')
from salt_check import SaltCheck
from salt_check import StateTestLoader

# Note: the order tests are run is arbitrary!

class MyClass2(unittest.TestCase):

    def setUp(self):
        self.st = StateTestLoader("/tmp")

    def tearDown(self):
        pass

    #def test_load_file_1(self):
    #    val = self.st.load_file("/tmp/testfile.tst")
    #    self.assertNotEqual(val, None) 

class MyClass(unittest.TestCase):

    def setUp(self):
        self.mt = SaltCheck()

    def tearDown(self):
        pass

    def test_get_state_dir_1(self):
        val = self.mt.get_state_dir()
        self.assertNotEqual(val, None) 

    def test_get_state_search_path_list_1(self):
        val = self.mt.get_state_search_path_list()
        self.assertNotEqual(val, None) 

    def test_show_minion_options_1(self):
        val = self.mt.show_minion_options()
        self.assertNotEqual(val, None) 

    def test_show_minion_options_2(self):
        val = self.mt.show_minion_options()
        cache = val.get('cachedir', None)
        root_dir = val.get('root_dir', None)
        states_dir = val.get('states_dir', None)
        environment = val.get('environment', None)
        file_roots = val.get('file_roots', None)
        #if cache and root_dir and states_dir and environment and file_roots:
        if cache and root_dir and file_roots:
            all_good = True
        else:
            all_good = False
        self.assertEqual(all_good, True) 

    def test_run_test_1(self):
        mydict = {"module_and_function": "test.echo",
                  "assertion": "assertEqual",
                  "expected-return": "This works!",
                  "args": ["This works!"] }
        val = self.mt.run_test(mydict)
        self.assertEqual(val, True) 

    def test_run_test_2(self):
        mydict = {"module_and_function": "invalidmod.invalidfunc",
                  "assertion": "assertEqual",
                  "expected-return": "This works!",
                  "args":["This works!"] }
        val = self.mt.run_test(mydict)
        self.assertEqual(val, "False: Invalid test") 

    def test_run_test_3(self):
        mydict = {"module_and_function": "test.echo",
                  "assertion": "assertEqual",
                  "expected-rotten": "This works!",
                  "arrgs":["This works!"] }
        val = self.mt.run_test(mydict)
        self.assertEqual(val, "False: Invalid test") 

    def test_populate_salt_modules_list_1(self):
        val = self.mt.populate_salt_modules_list()
        length = len(val)
        self.assertGreater(length, 10) 

    def test_is_valid_test_1(self):
        test_dict = {'module_and_function':'test.ping',
                     'assertion':'assertTrue',
                     'expected-return':'True'}
        val = self.mt.is_valid_test(test_dict)
        self.assertEqual(val, True) 

    def test_is_valid_test_2(self):
        test_dict = {'module_and_function':'test.ping-a-ring',
                     'assertion':'assertTrue',
                     'expected-return':'True'}
        val = self.mt.is_valid_test(test_dict)
        self.assertEqual(val, False) 

    def test_is_valid_test_3(self):
        test_dict = {'module_and_function':'toast.ping',
                     'assertion':'assertTrue',
                     'expected-return':'True'}
        val = self.mt.is_valid_test(test_dict)
        self.assertEqual(val, False) 

    def test_is_valid_test_4(self):
        test_dict = {'module_and_function':'toast.ping',
                     'assertion':'assertAbort',
                     'expected-return':'True'}
        val = self.mt.is_valid_test(test_dict)
        self.assertEqual(val, False) 

    def test_is_valid_test_5(self):
        test_dict = {'module_and_function':'toast.ping',
                     'absorbtion':'assertTrue',
                     'expected-return':'True'}
        val = self.mt.is_valid_test(test_dict)
        self.assertEqual(val, False) 

    def test_is_valid_test_6(self):
        test_dict = {'module_and_function':'toast.ping',
                     'assertion':'assertTrue',
                     'expected-rotunda':'True'}
        val = self.mt.is_valid_test(test_dict)
        self.assertEqual(val, False) 

    def test_is_valid_test_7(self):
        test_dict = {}
        val = self.mt.is_valid_test(test_dict)
        self.assertEqual(val, False) 

    def test_call_salt_command_1(self):
        val = self.mt.call_salt_command('test.ping')
        self.assertEqual(val, True) 

    def test_call_salt_command_2(self):
        val = self.mt.call_salt_command('test.ping', 'bad-arg')
        self.assertNotEqual(val, True) 

    def test_valid_module_1(self):
        val = self.mt.is_valid_module('invalid-name')
        self.assertEqual(val, False) 

    def test_valid_module_2(self):
        val = self.mt.is_valid_module('test')
        self.assertEqual(val, True) 

    def test_valid_function_1(self):
        val = self.mt.is_valid_function('test', 'ping')
        self.assertEqual(val, True) 

    def test_valid_function_2(self):
        val = self.mt.is_valid_function('test', 'invalid-function')
        self.assertEqual(val, False) 

    def test_1_assert_equal(self):
        val = SaltCheck.assert_equal(True, True)
        self.assertEqual(True, val)

    def test_2_assert_equal(self):
        val = SaltCheck.assert_equal(True, False)
        #fin_val = val[0]
        #self.assertEqual(False, fin_val)
        fin_val = val.startswith('False')
        self.assertEqual(True, fin_val)

    def test_3_assert_equal(self):
        val = SaltCheck.assert_equal(False, False)
        self.assertEqual(True, val)

    def test_1_assert_not_equal(self):
        val = SaltCheck.assert_not_equal(True, False)
        self.assertEqual(True, val)

    def test_2_assert_not_equal(self):
        val = SaltCheck.assert_not_equal(True, True)
        #fin_val = val[0]
        #self.assertEqual(False, fin_val)
        fin_val = val.startswith('False')
        self.assertEqual(True, fin_val)

    def test_3_assert_not_equal(self):
        val = SaltCheck.assert_not_equal(False, False)
        #fin_val = val[0]
        fin_val = val.startswith('False')
        self.assertEqual(True, fin_val)

    def test_1_assert_true(self):
        val = SaltCheck.assert_true(True)
        self.assertEqual(True, val)

    def test_2_assert_true(self):
        val = SaltCheck.assert_true(False)
        #fin_val = val[0]
        #self.assertEqual(False, fin_val)
        fin_val = val.startswith('False')
        self.assertEqual(True, fin_val)

    def test_3_assert_true(self):
        val = SaltCheck.assert_true(None)
        #fin_val = val[0]
        fin_val = val.startswith('False')
        self.assertEqual(True, fin_val)

    def test_1_assert_false(self):
        val = SaltCheck.assert_false(False)
        self.assertEqual(True, val)
        #fin_val = val[0].startswith('False')
        #self.assertEqual(True, fin_val)

    def test_2_assert_false(self):
        val = SaltCheck.assert_false(True)
        #fin_val = val[0]
        #self.assertEqual(False, fin_val)
        fin_val = val.startswith('False')
        self.assertEqual(True, fin_val)

    def test_3_assert_false(self):
        val = SaltCheck.assert_false(None)
        #fin_val = val[0]
        #self.assertEqual(False, fin_val)
        fin_val = val.startswith('False')
        self.assertEqual(True, fin_val)

    def test_1_assert_in(self):
        val = SaltCheck.assert_in(1, [1,2,3])
        self.assertEqual(True, val)

    def test_2_assert_in(self):
        val = SaltCheck.assert_in('a', "abcde")
        self.assertEqual(True, val)

    def test_3_assert_in(self):
        val = SaltCheck.assert_in('f', "abcde")
        #fin_val = val[0]
        #self.assertEqual(False, fin_val)
        fin_val = val.startswith('False')
        self.assertEqual(True, fin_val)

    def test_1_assert_not_in(self):
        val = SaltCheck.assert_not_in(0, [1,2,3,4])
        self.assertEqual(True, val)

    def test_2_assert_not_in(self):
        val = SaltCheck.assert_not_in('a', "abcde")
        #fin_val = val[0]
        #self.assertEqual(False, fin_val)
        fin_val = val.startswith('False')
        self.assertEqual(True, fin_val)

    def test_1_assert_greater(self):
        val = SaltCheck.assert_greater(100, 1)
        self.assertEqual(True, val)

    def test_2_assert_greater(self):
        val = SaltCheck.assert_greater(100, -1)
        self.assertEqual(True, val)

    def test_3_assert_greater(self):
        val = SaltCheck.assert_greater(-1, 0)
        #fin_val = val[0]
        #self.assertEqual(False, fin_val)
        fin_val = val.startswith('False')
        self.assertEqual(True, fin_val)

    def test_4_assert_greater(self):
        val = SaltCheck.assert_greater(0, 0)
        fin_val = val.startswith('False')
        self.assertEqual(True, fin_val)

    def test_1_assert_greater_equal(self):
        val = SaltCheck.assert_greater_equal(0, 0)
        self.assertEqual(True, val)

    def test_2_assert_greater_equal(self):
        val = SaltCheck.assert_greater_equal(1, 0)
        self.assertEqual(True, val)

    def test_3_assert_greater_equal(self):
        val = SaltCheck.assert_greater_equal(-1, 0)
        #fin_val = val[0]
        #self.assertEqual(False, fin_val)
        fin_val = val.startswith('False')
        self.assertEqual(True, fin_val)

    def test_1_assert_less(self):
        val = SaltCheck.assert_less(-1, 0)
        self.assertEqual(True, val)

    def test_2_assert_less(self):
        val = SaltCheck.assert_less(1, 100)
        self.assertEqual(True, val)

    def test_3_assert_less(self):
        val = SaltCheck.assert_less(0, 0)
        #fin_val = val[0]
        #self.assertEqual(False, fin_val)
        fin_val = val.startswith('False')
        self.assertEqual(True, fin_val)

    def test_4_assert_less(self):
        val = SaltCheck.assert_less(100, 0)
        #fin_val = val[0]
        fin_val = val.startswith('False')
        self.assertEqual(True, fin_val)

if __name__ == '__main__':
    unittest.main()
