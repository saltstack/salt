# -*- coding: utf-8 -*-
'''
This module should be saved as salt/modules/saltcheck.py
'''
from __future__ import absolute_import
import logging
import os
import time
import yaml
try:
    import salt.utils
    import salt.client
    import salt.exceptions
except ImportError:
    pass

log = logging.getLogger(__name__)

__virtualname__ = 'saltcheck'


def __virtual__():
    '''
    Check dependencies
    '''
    return __virtualname__


def update_master_cache():
    '''
    Updates the master cache onto the minion - to transfer all salt-check-tests
    Should be done one time before running tests, and if tests are updated

    CLI Example:
        salt '*' salt_check.update_master_cache
    '''
    __salt__['cp.cache_master'](args=None, kwargs=None)
    return True


def run_test(**kwargs):
    '''
    Enables running one salt_check test via cli
    CLI Example::
        salt '*' salt_check.run_test
          test='{"module_and_function": "test.echo",
            "assertion": "assertEqual",
            "expected-return": "This works!",
            "args":["This works!"] }'
    '''
    # salt converts the string to a dictionary auto-magically
    scheck = SaltCheck()
    test = kwargs.get('test', None)
    if test and isinstance(test, dict):
        return scheck.run_test(test)
    else:
        return "test must be dictionary"


def run_state_tests(state):
    '''
    Returns the output of running all salt check test for a state
    CLI Example::
      salt '*' salt_check.run_state_tests postfix_ubuntu_16_04
    '''
    scheck = SaltCheck()
    paths = scheck.get_state_search_path_list()
    stl = StateTestLoader(search_paths=paths)
    sls_list = scheck.get_state_sls(state)
    sls_paths = stl.convert_sls_to_paths(sls_list)
    for mypath in sls_paths:
        stl.add_test_files_for_sls(mypath)
    stl.load_test_suite()
    results_dict = {}
    for key, value in stl.test_dict.items():
        result = scheck.run_test(value)
        results_dict[key] = result
    return {state: results_dict}


class SaltCheck(object):
    '''
    This class implements the saltcheck
    '''

    def __init__(self):
        self.sls_list_top = []
        self.sls_list_state = []
        self.modules = []
        self.results_dict = {}
        self.results_dict_summary = {}
        self.assertions_list = '''assertEqual assertNotEqual
                                  assertTrue assertFalse
                                  assertIn assertGreater
                                  assertGreaterEqual
                                  assertLess assertLessEqual'''.split()
        # self.modules = self.populate_salt_modules_list()
        # call when needed self.populate_salt_modules_list()
        self.salt_lc = salt.client.Caller(mopts=__opts__)

    @staticmethod
    def update_master_cache():
        '''Easy way to update the master files on the minion'''
        __salt__['cp.cache_master'](args=None, kwargs=None)
        return

    def get_top_sls(self):
        ''' equivalent to a salt cli: salt web state.show_lowstate'''
        # sls_list = []
        try:
            returned = __salt__['state.show_lowstate']()
            for i in returned:
                if i['__sls__'] not in self.sls_list_top:
                    self.sls_list_top.append(i['__sls__'])
        except Exception:
            raise
        # self.sls_list = sls_list
        return self.sls_list_top

    def get_state_sls(self, state):
        ''' equivalent to a salt cli: salt web state.show_low_sls STATE'''
        try:
            returned = __salt__['state.show_low_sls'](state)
            for i in returned:
                if i['__sls__'] not in self.sls_list_state:
                    self.sls_list_state.append(i['__sls__'])
        except Exception:
            raise
        return self.sls_list_state

    def populate_salt_modules_list(self):
        '''return a list of all modules available on minion'''
        self.modules = __salt__['sys.list_modules']()
        return

    def __is_valid_module(self, module_name):
        '''Determines if a module is valid on a minion'''
        if module_name not in self.modules:
            return False
        else:
            return True

    @staticmethod
    def __is_valid_function(module_name, function):
        '''Determine if a function is valid for a module'''
        try:
            functions = __salt__['sys.list_functions'](module_name)
        except salt.exceptions.SaltException:
            functions = ["unable to look up functions"]
        return "{0}.{1}".format(module_name, function) in functions

    def __is_valid_test(self, test_dict):
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
            if self.__is_valid_module(module):
                tots += 1
            if self.__is_valid_function(module, function):
                tots += 1
        if assertion:
            tots += 1
            if assertion in self.assertions_list:
                tots += 1
        if expected_return:
            tots += 1
        return tots >= 6

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
        except salt.exceptions.SaltException:
            raise
        except Exception:
            raise
        return value

    def call_salt_command_test(self,
                               fun
                               ):
        '''Generic call of salt Caller command'''
        value = False
        try:
            value = self.salt_lc.function(fun)
        except salt.exceptions.SaltException:
            raise
        return value

    def run_test(self, test_dict):
        '''Run a single salt_check test'''
        if self.__is_valid_test(test_dict):
            mod_and_func = test_dict['module_and_function']
            args = test_dict.get('args', None)
            assertion = test_dict['assertion']
            expected_return = test_dict['expected-return']
            kwargs = test_dict.get('kwargs', None)
            actual_return = self.call_salt_command(mod_and_func, args, kwargs)
            # checking for membership in a list does not require a type cast
            if assertion != "assertIn":
                expected_return = self.cast_expected_to_returned_type(expected_return, actual_return)
            # return actual_return
            if assertion == "assertEqual":
                value = self.__assert_equal(expected_return, actual_return)
            elif assertion == "assertNotEqual":
                value = self.__assert_not_equal(expected_return, actual_return)
            elif assertion == "assertTrue":
                value = self.__assert_true(expected_return)
            elif assertion == "assertFalse":
                value = self.__assert_false(expected_return)
            elif assertion == "assertIn":
                value = self.__assert_in(expected_return, actual_return)
            elif assertion == "assertNotIn":
                value = self.__assert_not_in(expected_return, actual_return)
            elif assertion == "assertGreater":
                value = self.__assert_greater(expected_return, actual_return)
            elif assertion == "assertGreaterEqual":
                value = self.__assert_greater_equal(expected_return, actual_return)
            elif assertion == "assertLess":
                value = self.__assert_less(expected_return, actual_return)
            elif assertion == "assertLessEqual":
                value = self.__assert_less_equal(expected_return, actual_return)
            else:
                value = False
        else:
            return False
        return value

    @staticmethod
    def cast_expected_to_returned_type(expected, returned):
        '''
        Determine the type of variable returned
        Cast the expected to the type of variable returned
        '''
        ret_type = type(returned)
        new_expected = expected
        if expected == "False" and ret_type == bool:
            expected = False
        try:
            new_expected = ret_type(expected)
        except ValueError:
            log.info("Unable to cast expected into type of returned")
            log.info("returned = {}".format(returned))
            log.info("type of returned = {}".format(type(returned)))
            log.info("expected = {}".format(expected))
            log.info("type of expected = {}".format(type(expected)))
        return new_expected

    @staticmethod
    def __assert_equal(expected, returned):
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
    def __assert_not_equal(expected, returned):
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
    def __assert_true(returned):
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
    def __assert_false(returned):
        '''
        Test if an boolean is False
        '''
        result = (True)
        if isinstance(returned, str):
            try:
                returned = bool(returned)
            except ValueError:
                raise
        try:
            assert (returned is False), "{0} not False".format(returned)
        except AssertionError as err:
            result = "False: " + str(err)
        return result

    @staticmethod
    def __assert_in(expected, returned):
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
    def __assert_not_in(expected, returned):
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
    def __assert_greater(expected, returned):
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
    def __assert_greater_equal(expected, returned):
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
    def __assert_less(expected, returned):
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
    def __assert_less_equal(expected, returned):
        '''
        Test if a value is in the list of returned values
        '''
        result = (True)
        try:
            assert (expected <= returned), "{0} not False".format(returned)
        except AssertionError as err:
            result = "False: " + str(err)
        return result

    @staticmethod
    def __show_minion_options():
        '''gather and return minion config options'''
        cachedir = __opts__['cachedir']
        root_dir = __opts__['root_dir']
        states_dirs = __opts__['states_dirs']
        environment = __opts__['environment']
        file_roots = __opts__['file_roots']
        return {'cachedir': cachedir,
                'root_dir': root_dir,
                'states_dirs': states_dirs,
                'environment': environment,
                'file_roots': file_roots}

    @staticmethod
    def get_state_search_path_list():
        '''For the state file system, return a
           list of paths to search for states'''
        # state cache should be updated before running this method
        search_list = []
        cachedir = __opts__.get('cachedir', None)
        environment = __opts__['environment']
        if environment:
            path = cachedir + os.sep + "files" + os.sep + environment
            search_list.append(path)
        path = cachedir + os.sep + "files" + os.sep + "base"
        search_list.append(path)
        return search_list

    def __get_state_dir(self):
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
            with salt.utils.fopen(filepath, 'r') as myfile:
                # myfile = open(filepath, 'r')
                contents_yaml = yaml.load(myfile)
                for key, value in contents_yaml.items():
                    self.test_dict[key] = value
        except:
            raise
        return

    def gather_files(self, filepath):
        '''gather files for a test suite'''
        log.info("gather_files: {}".format(time.time()))
        filepath = filepath + os.sep + 'salt-check-tests'
        rootdir = filepath
        for dirname, filelist in os.walk(rootdir):
            for fname in filelist:
                if fname.endswith('.tst'):
                    start_path = dirname + os.sep + fname
                    full_path = os.path.abspath(start_path)
                    self.test_files.append(full_path)
        return

    @staticmethod
    def convert_sls_to_paths(sls_list):
        '''Converting sls to paths'''
        new_sls_list = []
        for sls in sls_list:
            sls = sls.replace(".", os.sep)
            new_sls_list.append(sls)
        return new_sls_list

    def add_test_files_for_sls(self, sls_path):
        '''Adding test files'''
        # state_path = None
        for path in self.search_paths:
            full_path = path + os.sep + sls_path
            rootdir = full_path
            if os.path.isdir(full_path):
                log.info("searching path= {}".format(full_path))
                for dirname, subdirlist in os.walk(rootdir, topdown=True):
                    if "salt-check-tests" in subdirlist:
                        self.gather_files(dirname)
                        log.info("test_files list: {}".format(self.test_files))
                        log.info("found subdir match in = {}".format(dirname))
                    else:
                        log.info("did not find subdir match in = {}".format(dirname))
                    del subdirlist[:]
            else:
                log.info("path is not a directory= {}".format(full_path))
        return
