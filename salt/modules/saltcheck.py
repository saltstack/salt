# -*- coding: utf-8 -*-
'''
A module for testing the logic of states and highstates

:codeauthor:    William Cannon <william.cannon@gmail.com>
:maturity:      new

Saltcheck provides unittest like functionality requiring only the knowledge of
salt module execution and yaml.

In order to run state and highstate saltcheck tests a sub-folder of a state must
be created and named ``saltcheck-tests``.

Tests for a state should be created in files ending in ``*.tst`` and placed in
the ``saltcheck-tests`` folder.

Multiple tests can be specified in a file. Multiple ``*.tst`` files can be
created in the ``saltcheck-tests`` folder. Salt rendering is supported in test
files (e.g. ``yaml + jinja``). The ``id`` of a test works in the same manner as
in salt state files. They should be unique and descriptive.

Example file system layout:

.. code-block:: txt

    /srv/salt/apache/
        init.sls
        config.sls
        saltcheck-tests/
            init.tst
            config.tst

Tests can be run for each state, or all apache tests

.. code-block:: bash

    salt '*' saltcheck.run_state_tests apache,apache.config
    salt '*' saltcheck.run_state_tests apache check_all=True
    salt '*' saltcheck.run_highstate_tests

Example 1:

.. code-block:: yaml

    echo_test_hello:
      module_and_function: test.echo
      args:
        - "hello"
      kwargs:
      assertion: assertEqual
      expected-return:  'hello'

Example 2:

.. code-block:: jinja

    {% for package in ["apache2", "openssh"] %}
    {# or another example #}
    {# for package in salt['pillar.get']("packages") #}
    test_{{ package }}_latest:
      module_and_function: pkg.upgrade_available
      args:
        - {{ package }}
      assertion: assertFalse
    {% endfor %}

Supported assertions:
assertEqual assertNotEqual assertTrue assertFalse assertIn assertNotIn assertGreater
assertGreaterEqual assertLess assertLessEqual assertEmpty assertNotEmpty
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import logging
import os
import time
from json import loads, dumps

# Import Salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.yaml
import salt.client
import salt.exceptions
from salt.utils.decorators import memoize
from salt.ext import six

log = logging.getLogger(__name__)

__virtualname__ = 'saltcheck'


def __virtual__():
    '''
    Check dependencies - may be useful in future
    '''
    return __virtualname__


def update_master_cache(saltenv='base'):
    '''
    Updates the master cache onto the minion - transfers all salt-check-tests
    Should be done one time before running tests, and if tests are updated
    Can be automated by setting "auto_update_master_cache: True" in minion config

    CLI Example:

    .. code-block:: bash

        salt '*' saltcheck.update_master_cache
    '''
    log.info("Updating files for environment: %s", saltenv)
    __salt__['cp.cache_master'](saltenv)
    return True


def run_test(**kwargs):
    '''
    Execute one saltcheck test and return result

    :param keyword arg test:

    CLI Example:

    .. code-block:: bash

        salt '*' saltcheck.run_test
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
        return "Test must be a dictionary"


def run_state_tests(state, saltenv=None, check_all=False):
    '''
    Execute all tests for a salt state and return results
    Nested states will also be tested

    :param str state: the name of a user defined state
    :param bool check_all: boolean to run all tests in state/saltcheck-tests directory

    CLI Example:

    .. code-block:: bash

        salt '*' saltcheck.run_state_tests postfix,common
    '''
    if not saltenv:
        saltenv = __opts__['saltenv']
    if not saltenv:
        saltenv = 'base'
    scheck = SaltCheck(saltenv)
    paths = scheck.get_state_search_path_list(saltenv)
    stl = StateTestLoader(search_paths=paths)
    results = {}
    sls_list = state.split(',')
    for state_name in sls_list:
        stl.add_test_files_for_sls(state_name, check_all)
        stl.load_test_suite()
        results_dict = {}
        for key, value in stl.test_dict.items():
            result = scheck.run_test(value)
            results_dict[key] = result
        results[state_name] = results_dict
    return _generate_out_list(results)


def run_highstate_tests(saltenv=None):
    '''
    Execute all tests for a salt highstate and return results

    CLI Example:

    .. code-block:: bash

        salt '*' saltcheck.run_highstate_tests
    '''
    if not saltenv:
        saltenv = __opts__['saltenv']
    if not saltenv:
        saltenv = 'base'
    scheck = SaltCheck(saltenv)
    paths = scheck.get_state_search_path_list(saltenv)
    stl = StateTestLoader(search_paths=paths)
    results = {}
    sls_list = _get_top_states(saltenv)
    all_states = []
    for state in sls_list:
        if state not in all_states:
            all_states.append(state)

    for state_name in all_states:
        stl.add_test_files_for_sls(state_name)
        stl.load_test_suite()
        results_dict = {}
        for key, value in stl.test_dict.items():
            result = scheck.run_test(value)
            results_dict[key] = result
        results[state_name] = results_dict
    return _generate_out_list(results)


def _generate_out_list(results):
    '''
    generate test results output list
    '''
    passed = 0
    failed = 0
    skipped = 0
    missing_tests = 0
    total_time = 0.0
    for state in results:
        if not results[state].items():
            missing_tests = missing_tests + 1
        else:
            for dummy, val in results[state].items():
                log.info("dummy=%s, val=%s", dummy, val)
                if val['status'].startswith('Pass'):
                    passed = passed + 1
                if val['status'].startswith('Fail'):
                    failed = failed + 1
                if val['status'].startswith('Skip'):
                    skipped = skipped + 1
                total_time = total_time + float(val['duration'])
    out_list = []
    for key, value in results.items():
        out_list.append({key: value})
    out_list.sort()
    out_list.append({'TEST RESULTS': {'Execution Time': round(total_time, 4),
                     'Passed': passed, 'Failed': failed, 'Skipped': skipped,
                     'Missing Tests': missing_tests}})
    return out_list


def _render_file(file_path):
    '''
    call the salt utility to render a file
    '''
    # salt-call slsutil.renderer /srv/salt/jinjatest/saltcheck-tests/test1.tst
    rendered = __salt__['slsutil.renderer'](file_path)
    log.info("rendered: %s", rendered)
    return rendered


@memoize
def _is_valid_module(module):
    '''
    Return a list of all modules available on minion
    '''
    modules = __salt__['sys.list_modules']()
    return bool(module in modules)


def _get_auto_update_cache_value():
    '''
    Return the config value of auto_update_master_cache
    '''
    __salt__['config.get']('auto_update_master_cache')
    return True


@memoize
def _is_valid_function(module_name, function):
    '''
    Determine if a function is valid for a module
    '''
    try:
        functions = __salt__['sys.list_functions'](module_name)
    except salt.exceptions.SaltException:
        functions = ["unable to look up functions"]
    return "{0}.{1}".format(module_name, function) in functions


def _get_top_states(saltenv='base'):
    '''
    Equivalent to a salt cli: salt web state.show_top
    '''
    alt_states = []
    try:
        returned = __salt__['state.show_top']()
        for i in returned[saltenv]:
            alt_states.append(i)
    except Exception:
        raise
    # log.info("top states: %s", alt_states)
    return alt_states


class SaltCheck(object):
    '''
    This class validates and runs the saltchecks
    '''

    def __init__(self, saltenv='base'):
        self.sls_list_state = []
        self.modules = []
        self.results_dict = {}
        self.results_dict_summary = {}
        self.saltenv = saltenv
        self.assertions_list = '''assertEqual assertNotEqual
                                  assertTrue assertFalse
                                  assertIn assertNotIn
                                  assertGreater
                                  assertGreaterEqual
                                  assertLess assertLessEqual
                                  assertEmpty assertNotEmpty'''.split()
        self.auto_update_master_cache = _get_auto_update_cache_value
        local_opts = salt.config.minion_config(__opts__['conf_file'])
        local_opts['file_client'] = 'local'
        self.salt_lc = salt.client.Caller(mopts=local_opts)
        if self.auto_update_master_cache:
            update_master_cache(saltenv)

    def __is_valid_test(self, test_dict):
        '''
        Determine if a test contains:

        - a test name
        - a valid module and function
        - a valid assertion
        - an expected return value - if assertion type requires it

        6 points needed for standard test
        4 points needed for test with assertion not requiring expected return
        '''
        tots = 0  # need total of >= 6 to be a valid test
        skip = test_dict.get('skip', False)
        m_and_f = test_dict.get('module_and_function', None)
        assertion = test_dict.get('assertion', None)
        exp_ret_key = 'expected-return' in test_dict.keys()
        exp_ret_val = test_dict.get('expected-return', None)
        log.info("__is_valid_test has test: %s", test_dict)
        if skip:
            required_total = 0
        if assertion in ["assertEmpty",
                         "assertNotEmpty",
                         "assertTrue",
                         "assertFalse"]:
            required_total = 4
        else:
            required_total = 6

        if m_and_f:
            tots += 1
            module, function = m_and_f.split('.')
            if _is_valid_module(module):
                tots += 1
            if _is_valid_function(module, function):
                tots += 1
            log.info("__is_valid_test has valid m_and_f")
        if assertion in self.assertions_list:
            log.info("__is_valid_test has valid_assertion")
            tots += 1

        if exp_ret_key:
            tots += 1

        if exp_ret_val is not None:
            tots += 1

        # log the test score for debug purposes
        log.info("__test score: %s and required: %s", tots, required_total)
        return tots >= required_total

    def _call_salt_command(self,
                           fun,
                           args,
                           kwargs):
        '''
        Generic call of salt Caller command
        '''
        value = False
        try:
            if args and kwargs:
                value = self.salt_lc.cmd(fun, *args, **kwargs)
            elif args and not kwargs:
                value = self.salt_lc.cmd(fun, *args)
            elif not args and kwargs:
                value = self.salt_lc.cmd(fun, **kwargs)
            else:
                value = self.salt_lc.cmd(fun)
        except salt.exceptions.SaltException:
            raise
        except Exception:
            raise
        return value

    def run_test(self, test_dict):
        '''
        Run a single saltcheck test
        '''
        start = time.time()
        if self.__is_valid_test(test_dict):
            skip = test_dict.get('skip', False)
            if skip:
                return {'status': 'Skip', 'duration': 0.0}
            mod_and_func = test_dict['module_and_function']
            args = test_dict.get('args', None)
            kwargs = test_dict.get('kwargs', None)
            pillar_data = test_dict.get('pillar-data', None)
            if pillar_data:
                if not kwargs:
                    kwargs = {}
                kwargs['pillar'] = pillar_data
            else:
                # make sure we clean pillar from previous test
                if kwargs:
                    kwargs.pop('pillar')

            assertion = test_dict['assertion']
            expected_return = test_dict.get('expected-return', None)
            actual_return = self._call_salt_command(mod_and_func, args, kwargs)
            if assertion not in ["assertIn", "assertNotIn", "assertEmpty", "assertNotEmpty",
                                 "assertTrue", "assertFalse"]:
                expected_return = self._cast_expected_to_returned_type(expected_return, actual_return)
            if assertion == "assertEqual":
                value = self.__assert_equal(expected_return, actual_return)
            elif assertion == "assertNotEqual":
                value = self.__assert_not_equal(expected_return, actual_return)
            elif assertion == "assertTrue":
                value = self.__assert_true(actual_return)
            elif assertion == "assertFalse":
                value = self.__assert_false(actual_return)
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
            elif assertion == "assertEmpty":
                value = self.__assert_empty(actual_return)
            elif assertion == "assertNotEmpty":
                value = self.__assert_not_empty(actual_return)
            else:
                value = "Fail - bad assertion"
        else:
            value = "Fail - invalid test"
        end = time.time()
        result = {}
        result['status'] = value
        result['duration'] = round(end - start, 4)
        return result

    @staticmethod
    def _cast_expected_to_returned_type(expected, returned):
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
            log.info("returned = %s", returned)
            log.info("type of returned = %s", type(returned))
            log.info("expected = %s", expected)
            log.info("type of expected = %s", type(expected))
        return new_expected

    @staticmethod
    def __assert_equal(expected, returned):
        '''
        Test if two objects are equal
        '''
        result = "Pass"

        try:
            assert (expected == returned), "{0} is not equal to {1}".format(expected, returned)
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_not_equal(expected, returned):
        '''
        Test if two objects are not equal
        '''
        result = "Pass"
        try:
            assert (expected != returned), "{0} is equal to {1}".format(expected, returned)
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_true(returned):
        '''
        Test if an boolean is True
        '''
        result = "Pass"
        try:
            assert (returned is True), "{0} not True".format(returned)
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_false(returned):
        '''
        Test if an boolean is False
        '''
        result = "Pass"
        if isinstance(returned, str):
            try:
                returned = bool(returned)
            except ValueError:
                raise
        try:
            assert (returned is False), "{0} not False".format(returned)
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_in(expected, returned):
        '''
        Test if a value is in the list of returned values
        '''
        result = "Pass"
        try:
            assert (expected in returned), "{0} not found in {1}".format(expected, returned)
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_not_in(expected, returned):
        '''
        Test if a value is not in the list of returned values
        '''
        result = "Pass"
        try:
            assert (expected not in returned), "{0} was found in {1}".format(expected, returned)
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_greater(expected, returned):
        '''
        Test if a value is greater than the returned value
        '''
        result = "Pass"
        try:
            assert (expected > returned), "{0} not False".format(returned)
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_greater_equal(expected, returned):
        '''
        Test if a value is greater than or equal to the returned value
        '''
        result = "Pass"
        try:
            assert (expected >= returned), "{0} not False".format(returned)
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_less(expected, returned):
        '''
        Test if a value is less than the returned value
        '''
        result = "Pass"
        try:
            assert (expected < returned), "{0} not False".format(returned)
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_less_equal(expected, returned):
        '''
        Test if a value is less than or equal to the returned value
        '''
        result = "Pass"
        try:
            assert (expected <= returned), "{0} not False".format(returned)
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_empty(returned):
        '''
        Test if a returned value is empty
        '''
        result = "Pass"
        try:
            assert (not returned), "{0} is not empty".format(returned)
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_not_empty(returned):
        '''
        Test if a returned value is not empty
        '''
        result = "Pass"
        try:
            assert (returned), "value is empty"
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def get_state_search_path_list(saltenv='base'):
        '''
        For the state file system, return a list of paths to search for states
        '''
        # state cache should be updated before running this method
        search_list = []
        cachedir = __opts__.get('cachedir', None)
        log.info("Searching for files in saltenv: %s", saltenv)
        path = cachedir + os.sep + "files" + os.sep + saltenv
        search_list.append(path)
        return search_list


class StateTestLoader(object):
    '''
    Class loads in test files for a state
    e.g. state_dir/saltcheck-tests/[1.tst, 2.tst, 3.tst]
    '''

    def __init__(self, search_paths):
        self.search_paths = search_paths
        self.path_type = None
        self.test_files = []  # list of file paths
        self.test_dict = {}

    def load_test_suite(self):
        '''
        Load tests either from one file, or a set of files
        '''
        self.test_dict = {}
        for myfile in self.test_files:
            self._load_file_salt_rendered(myfile)
        self.test_files = []

    def _load_file_salt_rendered(self, filepath):
        '''
        loads in one test file
        '''
        # use the salt renderer module to interpret jinja and etc
        tests = _render_file(filepath)
        # use json as a convenient way to convert the OrderedDicts from salt renderer
        mydict = loads(dumps(tests))
        for key, value in mydict.items():
            self.test_dict[key] = value
        return

    def _gather_files(self, filepath):
        '''
        Gather files for a test suite
        '''
        self.test_files = []
        filepath = filepath + os.sep + 'saltcheck-tests'
        for dirname, dummy, filelist in salt.utils.path.os_walk(filepath):
            for fname in filelist:
                if fname.endswith('.tst'):
                    start_path = dirname + os.sep + fname
                    full_path = os.path.abspath(start_path)
                    log.info("Found test: %s", full_path)
                    self.test_files.append(full_path)
        return

    @staticmethod
    def _convert_sls_to_path(sls):
        '''
        Converting sls to paths
        '''
        sls = sls.replace(".", os.sep)
        return sls

    def add_test_files_for_sls(self, sls_name, check_all=False):
        '''
        Adding test files
        '''
        sls_split = sls_name.rpartition('.')
        for path in self.search_paths:
            if sls_split[0]:
                base_path = path + os.sep + self._convert_sls_to_path(sls_split[0])
            else:
                base_path = path
            if os.path.isdir(base_path):
                log.info("searching path: %s", base_path)
                if check_all:
                    # Find and run all tests in the state/saltcheck-tests directory
                    self._gather_files(base_path + os.sep + sls_split[2])
                    return
                init_path = base_path + os.sep + sls_split[2] + os.sep + 'saltcheck-tests' + os.sep + 'init.tst'
                name_path = base_path + os.sep + 'saltcheck-tests' + os.sep + sls_split[2] + '.tst'
                if os.path.isfile(init_path):
                    self.test_files.append(init_path)
                    log.info("Found test init: %s", init_path)
                if os.path.isfile(name_path):
                    self.test_files.append(name_path)
                    log.info("Found test named: %s", name_path)
            else:
                log.info("path is not a directory: %s", base_path)
        return
