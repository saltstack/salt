#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''This custom salt module makes it easy to test salt states and highstates.
   Author: William Cannon  william period cannon at gmail dot com'''
import os
import os.path
import yaml
import salt.client
import salt.minion
import salt.config


class SaltCheck(object):
    '''
    This class implements the salt_check
    '''

    def __init__(self):
        self.__opts__ = salt.config.minion_config('/etc/salt/minion')
        self.salt_lc = salt.client.Caller(mopts=self.__opts__)
        self.results_dict = {}
        self.results_dict_summary = {}
        self.assertions_list = '''assertEqual assertNotEqual
                                  assertTrue assertFalse
                                  assertIn assertGreater
                                  assertGreaterEqual
                                  assertLess assertLessEqual'''.split()
        self.modules = self.populate_salt_modules_list()

    def cache_master_files(self):
        ''' equivalent to a salt cli: salt web cp.cache_master
        note: should do this for each env in file_root'''
        # This does not get rid of previous files from a prior cache
        # should change this to be a 'real-time' representation of 
        # master cache
        try:
            returned = self.call_salt_command(fun='cp.cache_master',
                                              args=None,
                                              kwargs=None)
        except:
            pass
        return returned

    def get_top_states(self):
        ''' equivalent to a salt cli: salt web state.show_top'''
        try:
            returned = self.call_salt_command(fun='state.show_top',
                                              args=None,
                                              kwargs=None)
        except:
            pass
        return returned['base']

    def populate_salt_modules_list(self):
        '''return a list of all modules available on minion'''
        valid_modules = self.call_salt_command(fun='sys.list_modules',
                                               args=None,
                                               kwargs=None)
        return valid_modules

    def is_valid_module(self, module_name):
        '''Determines if a module is valid on a minion'''
        if module_name not in self.modules:
            val = False
        else:
            val = True
        return val

    def is_valid_function(self, module_name, function):
        '''Determine if a function is valid for a module'''
        try:
            functions = self.call_salt_command(fun='sys.list_functions',
                                               args=[module_name],
                                               kwargs=None)
        except Exception:
            functions = ["unable to look up functions"]
        return "{0}.{1}".format(module_name, function) in functions

    def is_valid_test(self, test_dict):
        '''Determine if a test contains:
             a test name,
             a valid module and function,
             a valid assertion,
             an expected return value'''
        tots = 0  # need 6 to pass test
        m_and_f = test_dict.get('module_and_function', None)
        assertion = test_dict.get('assertion', None)
        expected_return = test_dict.get('expected-return', None)
        if m_and_f:
            tots += 1
            module, function = m_and_f.split('.')
            if self.is_valid_module(module):
                tots += 1
            if self.is_valid_function(module, function):
                tots += 1
        if assertion:
            tots += 1
            if assertion in self.assertions_list:
                tots += 1
        if expected_return:
            tots += 1
        return tots >= 6
        #return True

    def call_salt_command(self,
                          fun,
                          args=None,
                          kwargs=None):
        '''Generic call of salt Caller command'''
        value = False
        try:
            if args and kwargs:
                value = self.salt_lc.function(fun, *args, **kwargs)
            elif args and not kwargs:
                value = self.salt_lc.function(fun, *args)
            elif not args and kwargs:
                value = self.salt_lc.function(fun, **kwargs)
            else:
                value = self.salt_lc.function(fun)

        except Exception as err:
            value = err
        return value

    def call_salt_command_test(self,
                               fun
                               ):
        '''Generic call of salt Caller command'''
        value = False
        try:
            value = self.salt_lc.function(fun)
        except Exception as err:
            value = err
        return value

    def run_test(self, test_dict):
        '''Run a single salt_check test'''
        if self.is_valid_test(test_dict):
            mod_and_func = test_dict['module_and_function']
            args = test_dict.get('args', None)
            assertion = test_dict['assertion']
            expected_return = test_dict['expected-return']
            kwargs = test_dict.get('kwargs', None)
            actual_return = self.call_salt_command(mod_and_func, args, kwargs)
            if assertion == "assertEqual":
                value = self.assert_equal(expected_return, actual_return)
            elif assertion == "assertNotEqual":
                value = self.assert_not_equal(expected_return, actual_return)
            elif assertion == "assertTrue":
                value = self.assert_true(expected_return)
            elif assertion == "assertFalse":
                value = self.assert_false(expected_return)
            elif assertion == "assertIn":
                value = self.assert_in(expected_return, actual_return)
            elif assertion == "assertNotIn":
                value = self.assert_not_in(expected_return, actual_return)
            elif assertion == "assertGreater":
                value = self.assert_greater(expected_return, actual_return)
            elif assertion == "assertGreaterEqual":
                value = self.assert_greater_equal(expected_return, actual_return)
            elif assertion == "assertLess":
                value = self.assert_less(expected_return, actual_return)
            elif assertion == "assertLessEqual":
                value = self.assert_less_equal(expected_return, actual_return)
            else:
                value = False
        else:
            value = "False: Invalid test"
        return value

    @staticmethod
    def assert_equal(expected, returned):
        '''
        Test if two objects are equal
        '''
        result = True
        try:
            assert (expected == returned), "{0} is not equal to {1}".format(expected, returned)
        except AssertionError as err:
            result = "False: " + str(err)
        return result

    @staticmethod
    def assert_not_equal(expected, returned):
        '''
        Test if two objects are not equal
        '''
        result = (True)
        try:
            assert (expected != returned), "{0} is equal to {1}".format(expected, returned)
        except AssertionError as err:
            result = "False: " + str(err)
        return result

    @staticmethod
    def assert_true(returned):
        '''
        Test if an boolean is True
        '''
        result = (True)
        try:
            assert (returned is True), "{0} not True".format(returned)
        except AssertionError as err:
            result = "False: " + str(err)
        return result

    @staticmethod
    def assert_false(returned):
        '''
        Test if an boolean is False
        '''
        result = (True)
        try:
            assert (returned is False), "{0} not False".format(returned)
        except AssertionError as err:
            result = "False: " + str(err)
        return result

    @staticmethod
    def assert_in(expected, returned):
        '''
        Test if a value is in the list of returned values
        '''
        result = (True)
        try:
            assert (expected in returned), "{0} not False".format(returned)
        except AssertionError as err:
            result = "False: " + str(err)
        return result

    @staticmethod
    def assert_not_in(expected, returned):
        '''
        Test if a value is in the list of returned values
        '''
        result = (True)
        try:
            assert (expected not in returned), "{0} not False".format(returned)
        except AssertionError as err:
            result = "False: " + str(err)
        return result

    @staticmethod
    def assert_greater(expected, returned):
        '''
        Test if a value is in the list of returned values
        '''
        result = (True)
        try:
            assert (expected > returned), "{0} not False".format(returned)
        except AssertionError as err:
            result = "False: " + str(err)
        return result

    @staticmethod
    def assert_greater_equal(expected, returned):
        '''
        Test if a value is in the list of returned values
        '''
        result = (True)
        try:
            assert (expected >= returned), "{0} not False".format(returned)
        except AssertionError as err:
            result = "False: " + str(err)
        return result

    @staticmethod
    def assert_less(expected, returned):
        '''
        Test if a value is in the list of returned values
        '''
        result = (True)
        try:
            assert (expected < returned), "{0} not False".format(returned)
        except AssertionError as err:
            result = "False: " + str(err)
        return result

    @staticmethod
    def assert_less_equal(expected, returned):
        '''
        Test if a value is in the list of returned values
        '''
        result = (True)
        try:
            assert (expected <= returned), "{0} not False".format(returned)
        except AssertionError as err:
            result = "False: " + str(err)
        return result

    def show_minion_options(self):
        '''gather and return minion config options'''
        cachedir = self.__opts__['cachedir']
        root_dir = self.__opts__['root_dir']
        states_dirs = self.__opts__['states_dirs']
        environment = self.__opts__['environment']
        file_roots = self.__opts__['file_roots']
        return {'cachedir':cachedir,
                'root_dir':root_dir,
                'states_dirs':states_dirs,
                'environment':environment,
                'file_roots':file_roots}

    def get_state_search_path_list(self):
        '''For the state file system, return a
           list of paths to search for states'''
        # state cache should be updated before running this method
        search_list = []
        cachedir = self.__opts__.get('cachedir', None)
        environment = self.__opts__['environment']
        if environment:
            path = cachedir + os.sep + "files" + os.sep + environment
            search_list.append(path)
        path = cachedir + os.sep + "files" + os.sep + "base"
        search_list.append(path)
        return search_list

    def get_state_dir(self):
        ''''return the path of the state dir'''
        paths = self.get_state_search_path_list()
        return paths


class StateTestLoader(object):
    '''
    Class loads in test files for a state
    e.g.  state_dir/salt-check-tests/[1.tst, 2.tst, 3.tst]
    '''

    def __init__(self, search_paths):
        self.search_paths = search_paths
        self.path_type = None
        self.test_files = []  # list of file paths
        self.test_dict = {}

    def load_test_suite(self):
        '''load tests either from one file, or a set of files'''
        for myfile in self.test_files:
            self.load_file(myfile)

    def load_file(self, filepath):
        '''
        loads in one test file
        '''
        try:
            myfile = open(filepath, 'r')
            contents_yaml = yaml.load(myfile)
            for key, value in contents_yaml.items():
                self.test_dict[key] = value
        except:
            raise
        return

    def gather_files(self, filepath):
        '''gather files for a test suite'''
        filepath = filepath + os.sep + 'salt-check-tests'
        rootDir = filepath
        for dirName, subdirList, fileList in os.walk(rootDir):
            for fname in fileList:
                if fname.endswith('.tst'):
                    start_path = dirName + os.sep + fname
                    full_path = os.path.abspath(start_path)
                    self.test_files.append(full_path)
        return

    def find_state_dir(self, state_name):
        '''find and return the path to the state dir'''
        state_path = None
        for path in self.search_paths:
            rootDir = path
            for dirName, subdirList, fileList in os.walk(rootDir):
                mydir = dirName.split(os.sep)[-1]
                if state_name == mydir:
                    state_path = dirName
                    return state_path
        return state_path


def _get_test_files(state_name):
    '''Given a path to the state files, gather the list of test files under
    the salt-check-test subdir'''
    salt_check = SaltCheck()
    paths = salt_check.get_state_search_path_list()
    stl = StateTestLoader(search_paths=paths)
    mydir = stl.find_state_dir(state_name)
    stl.gather_files(mydir)
    return stl.test_files


def _get_top_states():
    ''' Show the dirs for the top file used for a particular minion'''
    salt_check = SaltCheck()
    return salt_check.get_top_states()


def run_state_tests(state_name):
    '''
    Runs tests for one state
    CLI Example:
        salt '*' salt_check.run_state_tests STATE-NAME
    '''
    if not state_name:
        return "State name required"
    scheck = SaltCheck()
    scheck.cache_master_files()
    paths = scheck.get_state_search_path_list()
    stl = StateTestLoader(search_paths=paths)
    mydir = stl.find_state_dir(state_name)
    stl.gather_files(mydir)
    _get_test_files(state_name)
    stl.load_test_suite()
    results_dict = {}
    for key, value in stl.test_dict.items():
        result = scheck.run_test(value)
        results_dict[key] = result
    return {state_name: results_dict}


def run_highstate_tests():
    '''
    Runs tests for all states included in a highstate
    CLI Example:
        salt '*' salt_check.run_highstate_tests
    '''
    states = _get_top_states()
    return_dict = {}
    for state in states:
        ret_dict = run_state_tests(state)
        return_dict.update(ret_dict)
    return return_dict


def run_test(**kwargs):
    '''
    Enables running one salt_check test via cli
    CLI Example::
        salt '*' salt_check.run_test
          test='{"module_and_function": "test.echo",
            "assertion": "assertEqual",
            "expected-return": "This works!",
            "args":"This works!" }'
    '''
    # salt converts the string to a dictionary auto-magically
    scheck = SaltCheck()
    test = kwargs.get('test', None)
    if test and isinstance(test, dict):
        return scheck.run_test(test)
    else:
        return "test must be dictionary"
