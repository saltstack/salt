# -*- coding: utf-8 -*-
"""
A module for testing the logic of states and highstates

:codeauthor:    William Cannon <william.cannon@gmail.com>
:maturity:      new

Saltcheck provides unittest like functionality requiring only the knowledge of
salt module execution and yaml. Saltcheck uses salt modules to return data, then
runs an assertion against that return. This allows for testing with all the
features included in salt modules.

In order to run state and highstate saltcheck tests, a sub-folder in the state directory
must be created and named ``saltcheck-tests``. Tests for a state should be created in files
ending in ``*.tst`` and placed in the ``saltcheck-tests`` folder. ``tst`` files are run
through the salt rendering system, enabling tests to be written in yaml (or renderer of choice),
and include jinja, as well as the usual grain and pillar information. Like states, multiple tests can
be specified in a ``tst`` file. Multiple ``tst`` files can be created in the ``saltcheck-tests``
folder, and should be named the same as the associated state. The ``id`` of a test works in the
same manner as in salt state files and should be unique and descriptive.


.. versionadded:: 3000
    The ``saltcheck-tests`` folder can be customized using the ``saltcheck_test_location`` minion
    configuration setting.  This setting is a relative path from the formula's ``salt://`` path
    to the test files.

Usage
=====

Example Default file system layout:

.. code-block:: text

    /srv/salt/apache/
        init.sls
        config.sls
        saltcheck-tests/
            init.tst
            config.tst
            deployment_validation.tst

Alternative example file system layout with custom saltcheck_test_location:

Minion configuration:
---------------------

.. code-block:: yaml

    saltcheck_test_location: tests/integration/saltcheck

Filesystem layout:
------------------

.. code-block:: text

    /srv/salt/apache/
        init.sls
        config.sls
        tests/integration/saltcheck/
            init.tst
            config.tst
            deployment_validation.tst

Tests can be run for each state by name, for all ``apache/saltcheck/*.tst``
files, or for all states assigned to the minion in top.sls. Tests may also be
created with no associated state. These tests will be run through the use of
``saltcheck.run_state_tests``, but will not be automatically run by
``saltcheck.run_highstate_tests``.

.. code-block:: bash

    salt '*' saltcheck.run_state_tests apache,apache.config
    salt '*' saltcheck.run_state_tests apache check_all=True
    salt '*' saltcheck.run_highstate_tests
    salt '*' saltcheck.run_state_tests apache.deployment_validation

Saltcheck Keywords
==================

**module_and_function:**
    (str) This is the salt module which will be run locally,
    the same as ``salt-call --local <module>``. The ``saltcheck.state_apply`` module name is
    special as it bypasses the local option in order to resolve state names when run in
    a master/minion environment.
**args:**
    (list) Optional arguments passed to the salt module
**kwargs:**
    (dict) Optional keyword arguments to be passed to the salt module
**assertion:**
    (str) One of the supported assertions and required except for ``saltcheck.state_apply``
    Tests which fail the assertion and expected_return, cause saltcheck to exit which a non-zero exit code.
**expected_return:**
    (str) Required except by ``assertEmpty``, ``assertNotEmpty``, ``assertTrue``,
    ``assertFalse``. The return of module_and_function is compared to this value in the assertion.
**assertion_section:**
    (str) Optional keyword used to parse the module_and_function return. If a salt module
    returns a dictionary as a result, the ``assertion_section`` value is used to lookup a specific value
    in that return for the assertion comparison.
**assertion_section_delimiter:**
    (str) Optional delimiter to use when splitting a nested structure.
    Defaults to ':'
**print_result:**
    (bool) Optional keyword to show results in the ``assertEqual``, ``assertNotEqual``,
    ``assertIn``, and ``assertNotIn`` output. Defaults to True.
**output_details:**
    (bool) Optional keyword to display ``module_and_function``, ``args``, ``assertion_section``,
    and assertion results text in the output. If print_result is False, assertion results will be hidden.
    This is a per test setting, but can be set globally for all tests by adding ``saltcheck_output_details: True``
    in the minion configuration file.
    Defaults to False
**pillar_data:**
    (dict) Optional keyword for passing in pillar data. Intended for use in potential test
    setup or teardown with the ``saltcheck.state_apply`` function.
**skip:**
    (bool) Optional keyword to skip running the individual test

Sample Cases/Examples
=====================

Basic Example
-------------

.. code-block:: yaml

    echo_test_hello:
      module_and_function: test.echo
      args:
        - "hello"
      kwargs:
      assertion: assertEqual
      expected_return:  'hello'

Example with jinja
------------------

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

Example with setup state including pillar
-----------------------------------------

.. code-block:: yaml

    setup_test_environment:
      module_and_function: saltcheck.state_apply
      args:
        - common
      pillar_data:
        data: value

    verify_vim:
      module_and_function: pkg.version
      args:
        - vim
      assertion: assertNotEmpty

Example with jinja
------------------

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

Example with setup state including pillar
-----------------------------------------

.. code-block:: yaml

    setup_test_environment:
      module_and_function: saltcheck.state_apply
      args:
        - common
      pillar-data:
        data: value

    verify_vim:
      module_and_function: pkg.version
      args:
        - vim
      assertion: assertNotEmpty

Example with skip
-----------------

.. code-block:: yaml

    package_latest:
      module_and_function: pkg.upgrade_available
      args:
        - apache2
      assertion: assertFalse
      skip: True

Example with assertion_section
------------------------------

.. code-block:: yaml

    validate_shell:
      module_and_function: user.info
      args:
        - root
      assertion: assertEqual
      expected_return: /bin/bash
      assertion_section: shell

Example with a nested assertion_section
---------------------------------------

.. code-block:: yaml

    validate_smb_signing:
      module_and_function: lgpo.get
      args:
        - 'Machine'
      kwargs:
        return_full_policy_names: True
      assertion: assertEqual
      expected_return: Enabled
      assertion_section: 'Computer Configuration|Microsoft network client: Digitally sign communications (always)'
      assertion_section_delimiter: '|'

Example suppressing print results
---------------------------------

.. code-block:: yaml

    validate_env_nameNode:
      module_and_function: hadoop.dfs
      args:
        - text
        - /oozie/common/env.properties
      expected_return: nameNode = hdfs://nameservice2
      assertion: assertNotIn
      print_result: False

Supported assertions
====================

* assertEqual
* assertNotEqual
* assertTrue
* assertFalse
* assertIn
* assertNotIn
* assertGreater
* assertGreaterEqual
* assertLess
* assertLessEqual
* assertEmpty
* assertNotEmpty

.. warning::

  The saltcheck.state_apply function is an alias for
  :py:func:`state.apply <salt.modules.state.apply>`. If using the
  :ref:`ACL system <acl-eauth>` ``saltcheck.*`` might provide more capability
  than intended if only ``saltcheck.run_state_tests`` and
  ``saltcheck.run_highstate_tests`` are needed.
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import copy
import logging
import os
import time

import salt.client
import salt.exceptions
import salt.utils.data

# Import Salt libs
import salt.utils.files
import salt.utils.functools
import salt.utils.path
import salt.utils.yaml
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.ext import six
from salt.utils.decorators import memoize
from salt.utils.json import dumps, loads
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)

__virtualname__ = "saltcheck"


def __virtual__():
    """
    Check dependencies
    """
    return __virtualname__


def run_test(**kwargs):
    """
    Execute one saltcheck test and return result

    :param keyword arg test:

    CLI Example:

    .. code-block:: bash

        salt '*' saltcheck.run_test
            test='{"module_and_function": "test.echo",
                   "assertion": "assertEqual",
                   "expected_return": "This works!",
                   "args":["This works!"] }'
    """
    # salt converts the string to a dictionary auto-magically
    scheck = SaltCheck()
    test = kwargs.get("test", None)
    if test and isinstance(test, dict):
        return scheck.run_test(test)
    else:
        return "Test argument must be a dictionary"


def state_apply(state_name, **kwargs):
    """
    Runs :py:func:`state.apply <salt.modules.state.apply>` with given options to set up test data.
    Intended to be used for optional test setup or teardown

    Reference the :py:func:`state.apply <salt.modules.state.apply>` module documentation for arguments and usage options

    CLI Example:

    .. code-block:: bash

        salt '*' saltcheck.state_apply postfix
    """
    # A new salt client is instantiated with the default configuration because the main module's
    #   client is hardcoded to local
    # minion is running with a master, a potentially non-local client is needed to lookup states
    conf_file = copy.deepcopy(__opts__["conf_file"])
    local_opts = salt.config.minion_config(conf_file)
    if "running_data/var/run/salt-minion.pid" in __opts__.get("pidfile", False):
        # Force salt-ssh minions to use local
        local_opts["file_client"] = "local"
        log.debug("Detected salt-ssh, running as local")
    caller = salt.client.Caller(mopts=local_opts)
    if kwargs:
        return caller.cmd("state.apply", state_name, **kwargs)
    else:
        return caller.cmd("state.apply", state_name)


def report_highstate_tests(saltenv=None):
    """
    Report on tests for states assigned to the minion through highstate.
    Quits with the exit code for the number of missing tests.

    CLI Example:

    .. code-block:: bash

        salt '*' saltcheck.report_highstate_tests

    .. versionadded:: 3000
    """
    if not saltenv:
        if "saltenv" in __opts__ and __opts__["saltenv"]:
            saltenv = __opts__["saltenv"]
        else:
            saltenv = "base"

    sls_list = []
    sls_list = _get_top_states(saltenv)
    stl = StateTestLoader(saltenv)
    missing_tests = 0
    states_missing_tests = []
    for state_name in sls_list:
        stl.add_test_files_for_sls(state_name, False)
        if state_name not in stl.found_states:
            missing_tests = missing_tests + 1
            states_missing_tests.append(state_name)
    __context__["retcode"] = missing_tests
    return {
        "TEST REPORT RESULTS": {
            "Missing Tests": missing_tests,
            "States missing tests": states_missing_tests,
            "States with tests": stl.found_states,
        }
    }


def run_state_tests(state, saltenv=None, check_all=False):
    """
    Execute tests for a salt state and return results
    Nested states will also be tested

    :param str state: state name for which to run associated .tst test files
    :param str saltenv: optional saltenv. Defaults to base
    :param bool check_all: boolean to run all tests in state/saltcheck-tests directory

    CLI Example:

    .. code-block:: bash

        salt '*' saltcheck.run_state_tests postfix,common
    """
    if not saltenv:
        if "saltenv" in __opts__ and __opts__["saltenv"]:
            saltenv = __opts__["saltenv"]
        else:
            saltenv = "base"
    scheck = SaltCheck(saltenv)
    stl = StateTestLoader(saltenv)
    results = OrderedDict()
    sls_list = salt.utils.args.split_input(state)
    for state_name in sls_list:
        stl.add_test_files_for_sls(state_name, check_all)
        stl.load_test_suite()
        results_dict = OrderedDict()
        for key, value in stl.test_dict.items():
            result = scheck.run_test(value)
            results_dict[key] = result
        if not results.get(state_name):
            # If passed a duplicate state, don't overwrite with empty res
            results[state_name] = results_dict
    return _generate_out_list(results)


run_state_tests_ssh = salt.utils.functools.alias_function(
    run_state_tests, "run_state_tests_ssh"
)


def run_highstate_tests(saltenv=None):
    """
    Execute all tests for states assigned to the minion through highstate and return results

    CLI Example:

    .. code-block:: bash

        salt '*' saltcheck.run_highstate_tests
    """
    if not saltenv:
        if "saltenv" in __opts__ and __opts__["saltenv"]:
            saltenv = __opts__["saltenv"]
        else:
            saltenv = "base"
    sls_list = []
    sls_list = _get_top_states(saltenv)
    all_states = ",".join(sls_list)

    return run_state_tests(all_states, saltenv=saltenv)


def _generate_out_list(results):
    """
    generate test results output list
    """
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
                if val["status"].startswith("Pass"):
                    passed = passed + 1
                if val["status"].startswith("Fail"):
                    failed = failed + 1
                if val["status"].startswith("Skip"):
                    skipped = skipped + 1
                total_time = total_time + float(val["duration"])
    out_list = []
    for key, value in results.items():
        out_list.append({key: value})
    out_list = sorted(out_list, key=lambda x: sorted(x.keys()))
    out_list.append(
        {
            "TEST RESULTS": {
                "Execution Time": round(total_time, 4),
                "Passed": passed,
                "Failed": failed,
                "Skipped": skipped,
                "Missing Tests": missing_tests,
            }
        }
    )
    # Set exist code to 1 if failed tests
    # Use-cases for exist code handling of missing or skipped?
    __context__["retcode"] = 1 if failed else 0
    return out_list


def _render_file(file_path):
    """
    call the salt utility to render a file
    """
    # salt-call slsutil.renderer /srv/salt/jinjatest/saltcheck-tests/test1.tst
    rendered = __salt__["slsutil.renderer"](file_path)
    log.info("rendered: %s", rendered)
    return rendered


@memoize
def _is_valid_module(module):
    """
    Return a list of all modules available on minion
    """
    modules = __salt__["sys.list_modules"]()
    return bool(module in modules)


@memoize
def _is_valid_function(module_name, function):
    """
    Determine if a function is valid for a module
    """
    try:
        functions = __salt__["sys.list_functions"](module_name)
    except salt.exceptions.SaltException:
        functions = ["unable to look up functions"]
    return "{0}.{1}".format(module_name, function) in functions


def _get_top_states(saltenv="base"):
    """
    Equivalent to a salt cli: salt web state.show_top
    """
    top_states = []
    top_states = __salt__["state.show_top"]()[saltenv]
    log.debug("saltcheck for saltenv: %s found top states: %s", saltenv, top_states)
    return top_states


class SaltCheck(object):
    """
    This class validates and runs the saltchecks
    """

    def __init__(self, saltenv="base"):
        self.sls_list_state = []
        self.modules = []
        self.results_dict = {}
        self.results_dict_summary = {}
        self.saltenv = saltenv
        self.assertions_list = """assertEqual assertNotEqual
                                  assertTrue assertFalse
                                  assertIn assertNotIn
                                  assertGreater
                                  assertGreaterEqual
                                  assertLess assertLessEqual
                                  assertEmpty assertNotEmpty""".split()

    def __is_valid_test(self, test_dict):
        """
        Determine if a test contains:

        - a test name
        - a valid module and function
        - a valid assertion
        - an expected return value - if assertion type requires it

        6 points needed for standard test
        4 points needed for test with assertion not requiring expected return
        """
        test_errors = []
        tots = 0  # need total of >= 6 to be a valid test
        skip = test_dict.get("skip", False)
        m_and_f = test_dict.get("module_and_function", None)
        assertion = test_dict.get("assertion", None)
        # support old expected-return and newer name normalized expected_return
        exp_ret_key = any(
            key in test_dict.keys() for key in ["expected_return", "expected-return"]
        )
        exp_ret_val = test_dict.get(
            "expected_return", test_dict.get("expected-return", None)
        )
        log.info("__is_valid_test has test: %s", test_dict)
        if skip:
            required_total = 0
        elif m_and_f in ["saltcheck.state_apply"]:
            required_total = 2
        elif assertion in [
            "assertEmpty",
            "assertNotEmpty",
            "assertTrue",
            "assertFalse",
        ]:
            required_total = 4
        else:
            required_total = 6

        if m_and_f:
            tots += 1
            module, function = m_and_f.split(".")
            if _is_valid_module(module):
                tots += 1
            else:
                test_errors.append("{0} is not a valid module".format(module))
            if _is_valid_function(module, function):
                tots += 1
            else:
                test_errors.append("{0} is not a valid function".format(function))
            log.info("__is_valid_test has valid m_and_f")
        if assertion in self.assertions_list:
            log.info("__is_valid_test has valid_assertion")
            tots += 1
        else:
            test_errors.append("{0} is not in the assertions list".format(assertion))

        if exp_ret_key:
            tots += 1
        else:
            test_errors.append("No expected return key")

        if exp_ret_val is not None:
            tots += 1
        else:
            test_errors.append("expected_return does not have a value")

        # log the test score for debug purposes
        log.info("__test score: %s and required: %s", tots, required_total)
        if not tots >= required_total:
            log.error(
                "Test failed with the following test verifications: %s",
                ", ".join(test_errors),
            )
        return tots >= required_total

    def _call_salt_command(
        self,
        fun,
        args,
        kwargs,
        assertion_section=None,
        assertion_section_delimiter=DEFAULT_TARGET_DELIM,
    ):
        """
        Generic call of salt Caller command
        """
        conf_file = __opts__["conf_file"]
        local_opts = salt.config.minion_config(conf_file)
        # Save orginal file_client to restore after salt.client.Caller run
        orig_file_client = local_opts["file_client"]
        mlocal_opts = copy.deepcopy(local_opts)
        mlocal_opts["file_client"] = "local"
        value = False
        if args and kwargs:
            value = salt.client.Caller(mopts=mlocal_opts).cmd(fun, *args, **kwargs)
        elif args and not kwargs:
            value = salt.client.Caller(mopts=mlocal_opts).cmd(fun, *args)
        elif not args and kwargs:
            value = salt.client.Caller(mopts=mlocal_opts).cmd(fun, **kwargs)
        else:
            value = salt.client.Caller(mopts=mlocal_opts).cmd(fun)
        __opts__["file_client"] = orig_file_client
        if isinstance(value, dict) and assertion_section:
            return_value = salt.utils.data.traverse_dict_and_list(
                value,
                assertion_section,
                default=False,
                delimiter=assertion_section_delimiter,
            )
            return return_value
        else:
            return value

    def run_test(self, test_dict):
        """
        Run a single saltcheck test
        """
        start = time.time()
        global_output_details = __salt__["config.get"](
            "saltcheck_output_details", False
        )
        output_details = test_dict.get("output_details", global_output_details)
        if self.__is_valid_test(test_dict):
            skip = test_dict.get("skip", False)
            if skip:
                return {"status": "Skip", "duration": 0.0}
            mod_and_func = test_dict["module_and_function"]
            assertion_section = test_dict.get("assertion_section", None)
            assertion_section_delimiter = test_dict.get(
                "assertion_section_delimiter", DEFAULT_TARGET_DELIM
            )
            args = test_dict.get("args", None)
            kwargs = test_dict.get("kwargs", None)
            pillar_data = test_dict.get(
                "pillar_data", test_dict.get("pillar-data", None)
            )
            if pillar_data:
                if not kwargs:
                    kwargs = {}
                kwargs["pillar"] = pillar_data
            else:
                # make sure we clean pillar from previous test
                if kwargs:
                    kwargs.pop("pillar", None)

            if mod_and_func in ["saltcheck.state_apply"]:
                assertion = "assertNotEmpty"
            else:
                assertion = test_dict["assertion"]
            expected_return = test_dict.get(
                "expected_return", test_dict.get("expected-return", None)
            )
            assert_print_result = test_dict.get("print_result", True)

            actual_return = self._call_salt_command(
                mod_and_func,
                args,
                kwargs,
                assertion_section,
                assertion_section_delimiter,
            )
            if assertion not in [
                "assertIn",
                "assertNotIn",
                "assertEmpty",
                "assertNotEmpty",
                "assertTrue",
                "assertFalse",
            ]:
                expected_return = self._cast_expected_to_returned_type(
                    expected_return, actual_return
                )
            if assertion == "assertEqual":
                assertion_desc = "=="
                value = self.__assert_equal(
                    expected_return, actual_return, assert_print_result
                )
            elif assertion == "assertNotEqual":
                assertion_desc = "!="
                value = self.__assert_not_equal(
                    expected_return, actual_return, assert_print_result
                )
            elif assertion == "assertTrue":
                assertion_desc = "True is"
                value = self.__assert_true(actual_return)
            elif assertion == "assertFalse":
                assertion_desc = "False is"
                value = self.__assert_false(actual_return)
            elif assertion == "assertIn":
                assertion_desc = "IN"
                value = self.__assert_in(
                    expected_return, actual_return, assert_print_result
                )
            elif assertion == "assertNotIn":
                assertion_desc = "NOT IN"
                value = self.__assert_not_in(
                    expected_return, actual_return, assert_print_result
                )
            elif assertion == "assertGreater":
                assertion_desc = ">"
                value = self.__assert_greater(expected_return, actual_return)
            elif assertion == "assertGreaterEqual":
                assertion_desc = ">="
                value = self.__assert_greater_equal(expected_return, actual_return)
            elif assertion == "assertLess":
                assertion_desc = "<"
                value = self.__assert_less(expected_return, actual_return)
            elif assertion == "assertLessEqual":
                assertion_desc = "<="
                value = self.__assert_less_equal(expected_return, actual_return)
            elif assertion == "assertEmpty":
                assertion_desc = "IS EMPTY"
                value = self.__assert_empty(actual_return)
            elif assertion == "assertNotEmpty":
                assertion_desc = "IS NOT EMPTY"
                value = self.__assert_not_empty(actual_return)
            else:
                value = "Fail - bad assertion"
        else:
            value = "Fail - invalid test"
        end = time.time()
        result = {}
        result["status"] = value

        if output_details:
            if assertion_section:
                assertion_section_repr_title = ".{0}".format("assertion_section")
                assertion_section_repr_value = ".{0}".format(assertion_section)
            else:
                assertion_section_repr_title = ""
                assertion_section_repr_value = ""
            result[
                "module.function [args]{0}".format(assertion_section_repr_title)
            ] = "{0} {1}{2}".format(
                mod_and_func, dumps(args), assertion_section_repr_value,
            )
            result["saltcheck assertion"] = "{0}{1} {2}".format(
                ("" if expected_return is None else "{0} ".format(expected_return)),
                assertion_desc,
                ("hidden" if not assert_print_result else actual_return),
            )

        result["duration"] = round(end - start, 4)
        return result

    @staticmethod
    def _cast_expected_to_returned_type(expected, returned):
        """
        Determine the type of variable returned
        Cast the expected to the type of variable returned
        """
        new_expected = expected
        if returned is not None:
            ret_type = type(returned)
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
    def __assert_equal(expected, returned, assert_print_result=True):
        """
        Test if two objects are equal
        """
        result = "Pass"

        try:
            if assert_print_result:
                assert expected == returned, "{0} is not equal to {1}".format(
                    expected, returned
                )
            else:
                assert expected == returned, "Result is not equal"
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_not_equal(expected, returned, assert_print_result=True):
        """
        Test if two objects are not equal
        """
        result = "Pass"
        try:
            if assert_print_result:
                assert expected != returned, "{0} is equal to {1}".format(
                    expected, returned
                )
            else:
                assert expected != returned, "Result is equal"
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_true(returned):
        """
        Test if an boolean is True
        """
        result = "Pass"
        try:
            assert returned is True, "{0} not True".format(returned)
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_false(returned):
        """
        Test if an boolean is False
        """
        result = "Pass"
        if isinstance(returned, str):
            returned = bool(returned)
        try:
            assert returned is False, "{0} not False".format(returned)
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_in(expected, returned, assert_print_result=True):
        """
        Test if a value is in the list of returned values
        """
        result = "Pass"
        try:
            if assert_print_result:
                assert expected in returned, "{0} not found in {1}".format(
                    expected, returned
                )
            else:
                assert expected in returned, "Result not found"
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_not_in(expected, returned, assert_print_result=True):
        """
        Test if a value is not in the list of returned values
        """
        result = "Pass"
        try:
            if assert_print_result:
                assert expected not in returned, "{0} was found in {1}".format(
                    expected, returned
                )
            else:
                assert expected not in returned, "Result was found"
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_greater(expected, returned):
        """
        Test if a value is greater than the returned value
        """
        result = "Pass"
        try:
            assert expected > returned, "{0} not False".format(returned)
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_greater_equal(expected, returned):
        """
        Test if a value is greater than or equal to the returned value
        """
        result = "Pass"
        try:
            assert expected >= returned, "{0} not False".format(returned)
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_less(expected, returned):
        """
        Test if a value is less than the returned value
        """
        result = "Pass"
        try:
            assert expected < returned, "{0} not False".format(returned)
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_less_equal(expected, returned):
        """
        Test if a value is less than or equal to the returned value
        """
        result = "Pass"
        try:
            assert expected <= returned, "{0} not False".format(returned)
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_empty(returned):
        """
        Test if a returned value is empty
        """
        result = "Pass"
        try:
            assert not returned, "{0} is not empty".format(returned)
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result

    @staticmethod
    def __assert_not_empty(returned):
        """
        Test if a returned value is not empty
        """
        result = "Pass"
        try:
            assert returned, "value is empty"
        except AssertionError as err:
            result = "Fail: " + six.text_type(err)
        return result


class StateTestLoader(object):
    """
    Class loads in test files for a state
    e.g. state_dir/saltcheck-tests/[1.tst, 2.tst, 3.tst]
    """

    def __init__(self, saltenv="base"):
        self.path_type = None
        self.test_files = set([])  # list of file paths
        self.test_dict = OrderedDict()
        self.saltenv = saltenv
        self.saltcheck_test_location = __salt__["config.get"](
            "saltcheck_test_location", "saltcheck-tests"
        )
        self.found_states = []

    def load_test_suite(self):
        """
        Load tests either from one file, or a set of files
        """
        self.test_dict = OrderedDict()
        for myfile in self.test_files:
            self._load_file_salt_rendered(myfile)
        self.test_files = set([])

    def _load_file_salt_rendered(self, filepath):
        """
        loads in one test file
        """
        # use the salt renderer module to interpret jinja and etc
        tests = _render_file(filepath)
        # use json as a convenient way to convert the OrderedDicts from salt renderer
        mydict = loads(dumps(tests), object_pairs_hook=OrderedDict)
        for key, value in mydict.items():
            self.test_dict[key] = value
        return

    def _copy_state_files(self, sls_path, state_name, check_all):
        """
        Copy tst files for a given path and return results of the copy.
        If check_all is enabled, also add all tests found
        """
        cache_ret = []
        if state_name not in self.found_states:
            log.debug("looking in %s to cache tests", sls_path)
            cache_ret = __salt__["cp.cache_dir"](
                sls_path, saltenv=self.saltenv, include_pat="*.tst"
            )
            if cache_ret:
                if check_all:
                    log.debug("Adding all found test files: %s", cache_ret)
                    self.test_files.update(cache_ret)
                else:
                    log.debug("Marking found_state: %s", state_name)
                    self.found_states.append(state_name)
        else:
            log.debug("Not copying already found_state: %s", self.found_states)

        return cache_ret

    def _generate_sls_path(self, state_name):
        """
        For a given state_name, return list of paths to search for .tst files

        possible formula paths are then
         path/to/formula.sls
           with tests of
             path/to/saltcheck-tests/formula.tst
         path/to/formula/init.sls
           with tests of
              path/to/formula/saltcheck-tests/init.tst
         or if a custom saltcheck_test_location is used
         path/to/forumla.sls
           with tests of
              path/saltcheck_test_location/init.tst
        """

        all_sls_paths = []

        # process /patch/to/formula/saltcheck_test_location
        test_path = "salt://{0}/{1}".format(
            state_name.replace(".", "/"), self.saltcheck_test_location
        )
        all_sls_paths.append(test_path)

        # process /path/to/saltcheck_test_location
        sls_split = state_name.split(".")
        sls_split.pop()
        test_path = "salt://{0}/{1}".format(
            "/".join(sls_split), self.saltcheck_test_location
        )
        all_sls_paths.append(test_path)

        state_name_base = state_name.split(".")[0]
        test_path = "salt://{0}/{1}".format(
            state_name_base, self.saltcheck_test_location
        )
        all_sls_paths.append(test_path)

        unique_paths = set(all_sls_paths)
        # Try longer (more complicated) paths before shorter simpler ones. Ensures that
        # thing/sub/saltcheck-tests/testname will be found before thing/saltcheck-tests/testname
        return list(sorted(unique_paths, key=len, reverse=True))

    @memoize
    def _get_states(self):
        """
        Returns (cached) list of states for the minion
        """
        return __salt__["cp.list_states"](saltenv=self.saltenv)

    def add_test_files_for_sls(self, sls_name, check_all=False):
        """
        Detects states used, caches needed files, and adds to test list
        """
        salt_ssh = False
        if "running_data/var/run/salt-minion.pid" in __opts__.get("pidfile", False):
            salt_ssh = True
            log.debug("Running on salt-ssh minion. Reading file %s", sls_name)
            cp_output_file = os.path.join(
                __opts__["cachedir"], "files", self.saltenv, "cp_output.txt"
            )
            with salt.utils.files.fopen(cp_output_file, "r") as fp:
                all_states = loads(salt.utils.stringutils.to_unicode(fp.read()))
        else:
            all_states = self._get_states()

        ret = []
        cached_copied_files = []
        if salt_ssh:
            # populate cached_copied_files from sent over file rather than attempting to run cp.cache_dir later
            log.debug("Running on salt-ssh minion. Populating test file results")
            state_copy_file = os.path.join(
                __opts__["cachedir"], "files", self.saltenv, sls_name + ".copy"
            )
            try:
                with salt.utils.files.fopen(state_copy_file, "r") as fp:
                    cached_copied_files.extend(
                        loads(salt.utils.stringutils.to_unicode(fp.read()))
                    )
            except IOError:
                # likely attempting to find state.nested.copy when file was sent as just state.copy
                sls_name_list = sls_name.split(".")
                sls_root_name = ".".join(sls_name_list[:-1])
                state_copy_file = os.path.join(
                    __opts__["cachedir"], "files", self.saltenv, sls_root_name + ".copy"
                )
                with salt.utils.files.fopen(state_copy_file, "r") as fp:
                    cached_copied_files.extend(
                        loads(salt.utils.stringutils.to_unicode(fp.read()))
                    )

        if sls_name in all_states:
            if salt_ssh:
                log.debug(
                    "Running on salt-ssh minion. Reading file %s", sls_name + ".low"
                )
                state_low_file = os.path.join(
                    __opts__["cachedir"], "files", self.saltenv, sls_name + ".low"
                )
                with salt.utils.files.fopen(state_low_file, "r") as fp:
                    ret = loads(salt.utils.stringutils.to_unicode(fp.read()))
            else:
                ret = __salt__["state.show_low_sls"](
                    sls_name, saltenv=self.saltenv, test=True
                )
        else:
            # passed name isn't a state, so we'll assume it is a test definition
            ret = [{"__sls__": sls_name}]

        for low_data in ret:
            if not isinstance(low_data, dict):
                log.error(
                    "low data from show_low_sls is not formed as a dict: %s", low_data
                )
                return
            this_cache_ret = None
            if "__sls__" in low_data:
                # this low data has an SLS path in it

                state_name = low_data["__sls__"]

                for sls_path in self._generate_sls_path(state_name):
                    this_cache_ret = self._copy_state_files(
                        sls_path, state_name, check_all
                    )
                    if this_cache_ret:
                        log.debug("found tests: %s", this_cache_ret)
                        cached_copied_files.extend(this_cache_ret)

                if salt_ssh:
                    if check_all:
                        # load all tests for this state on ssh minion
                        tst_files = [
                            file_string
                            for file_string in cached_copied_files
                            if file_string.endswith(".tst")
                        ]
                        self.test_files.update(tst_files)

                if not check_all:
                    # in check_all case, tests already added
                    split_sls = low_data["__sls__"].split(".")
                    sls_path_names = set(
                        [
                            os.path.join(
                                os.sep.join(split_sls),
                                os.path.normpath(self.saltcheck_test_location),
                                "init.tst",
                            ),
                            os.path.join(
                                os.sep.join(split_sls[: len(split_sls) - 1]),
                                os.path.normpath(self.saltcheck_test_location),
                                "{0}.tst".format(split_sls[-1]),
                            ),
                            os.path.join(
                                split_sls[0],
                                os.path.normpath(self.saltcheck_test_location),
                                os.sep.join(split_sls[1:-1]),
                                "{0}.tst".format(split_sls[-1]),
                            ),
                        ]
                    )
                    # for this state, find matching test files and load them
                    cached_copied_files = list(set(cached_copied_files))
                    for this_cached_test_file in cached_copied_files:
                        if this_cached_test_file.endswith(tuple(sls_path_names)):
                            self.test_files.add(this_cached_test_file)
                            cached_copied_files.remove(this_cached_test_file)
                            log.debug("Adding .tst file: %s", this_cached_test_file)
