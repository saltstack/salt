"""
A module for testing the logic of states and highstates on salt minions

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

.. versionadded:: 3000
    Multiple assertions can be run against the output of a single ``module_and_function`` call. The ``assertion``,
    ``expected_return``, ``assertion_section``, and ``assertion_section_delimiter`` keys can be placed in a list under an
    ``assertions`` key. See the multiple assertions example below.

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

Example with multiple assertions and output_details
---------------------------------------------------

.. code-block:: yaml

    multiple_validations:
      module_and_function: network.netstat
      assertions:
        - assertion: assertEqual
          assertion_section: "0:program"
          expected_return: "systemd-resolve"
        - assertion: assertEqual
          assertion_section: "0:proto"
          expected_return: "udp"
      output_details: True

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


import copy
import logging
import multiprocessing
import os
import time

import salt.client
import salt.exceptions
import salt.utils.data
import salt.utils.files
import salt.utils.functools
import salt.utils.path
import salt.utils.platform
import salt.utils.yaml
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.utils.decorators import memoize
from salt.utils.json import dumps, loads
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)

try:
    __context__
except NameError:
    __context__ = {}
__context__["global_scheck"] = None

__virtualname__ = "saltcheck"


def __virtual__():
    """
    Set the virtual pkg module if not running as a proxy
    """
    if not salt.utils.platform.is_proxy():
        return __virtualname__
    return (
        False,
        "The saltcheck execution module failed to load: only available on minions.",
    )


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


def run_state_tests(state, saltenv=None, check_all=False, only_fails=False):
    """
    Execute tests for a salt state and return results
    Nested states will also be tested

    :param str state: state name for which to run associated .tst test files
    :param str saltenv: optional saltenv. Defaults to base
    :param bool check_all: boolean to run all tests in state/saltcheck-tests directory
    :param bool only_fails: boolean to only print failure results

    CLI Example:

    .. code-block:: bash

        salt '*' saltcheck.run_state_tests postfix,common

    Tests will be run in parallel by adding "saltcheck_parallel: True" in minion config.
    When enabled, saltcheck will use up to the number of cores detected. This can be limited
    by setting the "saltcheck_processes" value to an integer to set the maximum number
    of parallel processes.
    """
    if not saltenv:
        if "saltenv" in __opts__ and __opts__["saltenv"]:
            saltenv = __opts__["saltenv"]
        else:
            saltenv = "base"

    # Use global scheck variable for reuse in each multiprocess
    __context__["global_scheck"] = SaltCheck(saltenv)

    parallel = __salt__["config.get"]("saltcheck_parallel")
    num_proc = __salt__["config.get"]("saltcheck_processes")

    stl = StateTestLoader(saltenv)
    results = OrderedDict()
    sls_list = salt.utils.args.split_input(state)
    for state_name in sls_list:
        stl.add_test_files_for_sls(state_name, check_all)
        stl.load_test_suite()
        results_dict = OrderedDict()

        # Check for situations to disable parallization
        if parallel:
            if type(num_proc) == float:
                num_proc = int(num_proc)

            if multiprocessing.cpu_count() < 2:
                parallel = False
                log.debug("Only 1 CPU. Disabling parallization.")
            elif num_proc == 1:
                # Don't bother with multiprocessing overhead
                parallel = False
                log.debug("Configuration limited to 1 CPU. Disabling parallization.")
            else:
                for items in stl.test_dict.values():
                    if "state.apply" in items.get("module_and_function", []):
                        # Multiprocessing doesn't ensure ordering, which state.apply
                        # might require
                        parallel = False
                        log.warning(
                            "Tests include state.apply. Disabling parallization."
                        )

        if parallel:
            if num_proc:
                pool_size = num_proc
            else:
                pool_size = min(len(stl.test_dict), multiprocessing.cpu_count())
            log.debug("Running tests in parallel with %s processes", pool_size)
            presults = multiprocessing.Pool(pool_size).map(
                func=parallel_scheck, iterable=stl.test_dict.items()
            )
            # Remove list and form expected data structure
            for item in presults:
                for key, value in item.items():
                    results_dict[key] = value
        else:
            for key, value in stl.test_dict.items():
                result = __context__["global_scheck"].run_test(value)
                results_dict[key] = result

        # If passed a duplicate state, don't overwrite with empty res
        if not results.get(state_name):
            results[state_name] = results_dict
    return _generate_out_list(results, only_fails=only_fails)


def parallel_scheck(data):
    """triggers salt-call in parallel"""
    key = data[0]
    value = data[1]
    results = {}
    results[key] = __context__["global_scheck"].run_test(value)
    return results


run_state_tests_ssh = salt.utils.functools.alias_function(
    run_state_tests, "run_state_tests_ssh"
)


def run_highstate_tests(saltenv=None, only_fails=False):
    """
    Execute all tests for states assigned to the minion through highstate and return results

    :param str saltenv: optional saltenv. Defaults to base
    :param bool only_fails: boolean to only print failure results

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

    return run_state_tests(all_states, saltenv=saltenv, only_fails=only_fails)


def _eval_failure_only_print(state_name, results, only_fails):
    """
    For given results, only return failures if desired
    """
    if only_fails:
        failed_tests = {}
        for test in results[state_name]:
            if results[state_name][test]["status"].startswith("Fail"):
                if failed_tests.get(state_name):
                    failed_tests[state_name].update({test: results[state_name][test]})
                else:
                    failed_tests[state_name] = {test: results[state_name][test]}
        return failed_tests
    else:
        # Show all test results
        return {state_name: results[state_name]}


def _generate_out_list(results, only_fails=False):
    """
    generate test results output list
    """
    passed = 0
    failed = 0
    skipped = 0
    missing_tests = 0
    total_time = 0.0
    out_list = []
    for state in results:
        if not results[state].items():
            missing_tests = missing_tests + 1
        else:
            for _, val in results[state].items():
                if val["status"].startswith("Pass"):
                    passed = passed + 1
                if val["status"].startswith("Fail"):
                    failed = failed + 1
                if val["status"].startswith("Skip"):
                    skipped = skipped + 1
                total_time = total_time + float(val["duration"])
        out_list.append(_eval_failure_only_print(state, results, only_fails))
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
    rendered = __salt__["slsutil.renderer"](
        file_path, saltenv=__context__["global_scheck"].saltenv
    )
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
    return "{}.{}".format(module_name, function) in functions


def _get_top_states(saltenv="base"):
    """
    Equivalent to a salt cli: salt web state.show_top
    """
    top_states = []
    top_states = __salt__["state.show_top"](saltenv=saltenv)[saltenv]
    log.debug("saltcheck for saltenv: %s found top states: %s", saltenv, top_states)
    return top_states


class SaltCheck:
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

    def _check_assertions(self, dict):
        """Validate assertion keys"""
        is_valid = True
        assertion = dict.get("assertion", None)
        # support old expected-return and newer name normalized expected_return
        exp_ret_key = any(
            key in dict.keys() for key in ["expected_return", "expected-return"]
        )
        exp_ret_val = dict.get("expected_return", dict.get("expected-return", None))

        if assertion not in self.assertions_list:
            log.error("Saltcheck: %s is not in the assertions list", assertion)
            is_valid = False

        # Only check expected returns for assertions which require them
        if assertion not in [
            "assertEmpty",
            "assertNotEmpty",
            "assertTrue",
            "assertFalse",
        ]:
            if exp_ret_key is None:
                log.error("Saltcheck: missing expected_return")
                is_valid = False
            if exp_ret_val is None:
                log.error("Saltcheck: expected_return missing a value")
                is_valid = False

        return is_valid

    def __is_valid_test(self, test_dict):
        """
        Determine if a test contains:

        - a test name
        - a valid module and function
        - a valid assertion, or valid grouping under an assertions key
        - an expected return value - if assertion type requires it
        """
        log.info("Saltcheck: validating data: %s", test_dict)
        is_valid = True
        skip = test_dict.get("skip", False)
        m_and_f = test_dict.get("module_and_function", None)

        # Running a state does not require assertions or checks
        if m_and_f == "saltcheck.state_apply":
            return is_valid

        if test_dict.get("assertions"):
            for assertion_group in test_dict.get("assertions"):
                is_valid = self._check_assertions(assertion_group)
        else:
            is_valid = self._check_assertions(test_dict)

        if m_and_f:
            module, function = m_and_f.split(".")
            if not _is_valid_module(module):
                is_valid = False
                log.error("Saltcheck: %s is not a valid module", module)
            if not _is_valid_function(module, function):
                is_valid = False
                log.error("Saltcheck: %s is not a valid function", function)
        else:
            log.error("Saltcheck: missing module_and_function")
            is_valid = False

        return is_valid

    def _call_salt_command(self, fun, args, kwargs):
        """
        Generic call of salt Caller command
        """
        # remote functions and modules won't work with local file client
        # these aren't exhaustive lists, so add to them when a module or
        # function can't operate without the remote file client
        remote_functions = ["file.check_managed_changes"]
        remote_modules = ["cp"]
        mod = fun.split(".", maxsplit=1)[0]

        conf_file = __opts__["conf_file"]
        local_opts = salt.config.minion_config(conf_file)
        # Save orginal file_client to restore after salt.client.Caller run
        orig_file_client = local_opts["file_client"]
        mlocal_opts = copy.deepcopy(local_opts)
        if fun not in remote_functions and mod not in remote_modules:
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

        return value

    def _run_assertions(
        self,
        mod_and_func,
        args,
        data,
        module_output,
        output_details,
        assert_print_result,
    ):
        """
        Run assertion against input
        """
        value = {}

        assertion_section = data.get("assertion_section", None)
        assertion_section_delimiter = data.get(
            "assertion_section_delimiter", DEFAULT_TARGET_DELIM
        )

        if assertion_section:
            module_output = salt.utils.data.traverse_dict_and_list(
                module_output,
                assertion_section,
                default=False,
                delimiter=assertion_section_delimiter,
            )

        if mod_and_func in ["saltcheck.state_apply"]:
            assertion = "assertNotEmpty"
        else:
            assertion = data["assertion"]
        expected_return = data.get("expected_return", data.get("expected-return", None))

        if assertion not in [
            "assertIn",
            "assertNotIn",
            "assertEmpty",
            "assertNotEmpty",
            "assertTrue",
            "assertFalse",
        ]:
            expected_return = self._cast_expected_to_returned_type(
                expected_return, module_output
            )
        if assertion == "assertEqual":
            assertion_desc = "=="
            value["status"] = self.__assert_equal(
                expected_return, module_output, assert_print_result
            )
        elif assertion == "assertNotEqual":
            assertion_desc = "!="
            value["status"] = self.__assert_not_equal(
                expected_return, module_output, assert_print_result
            )
        elif assertion == "assertTrue":
            assertion_desc = "True is"
            value["status"] = self.__assert_true(module_output)
        elif assertion == "assertFalse":
            assertion_desc = "False is"
            value["status"] = self.__assert_false(module_output)
        elif assertion == "assertIn":
            assertion_desc = "IN"
            value["status"] = self.__assert_in(
                expected_return, module_output, assert_print_result
            )
        elif assertion == "assertNotIn":
            assertion_desc = "NOT IN"
            value["status"] = self.__assert_not_in(
                expected_return, module_output, assert_print_result
            )
        elif assertion == "assertGreater":
            assertion_desc = ">"
            value["status"] = self.__assert_greater(expected_return, module_output)
        elif assertion == "assertGreaterEqual":
            assertion_desc = ">="
            value["status"] = self.__assert_greater_equal(
                expected_return, module_output
            )
        elif assertion == "assertLess":
            assertion_desc = "<"
            value["status"] = self.__assert_less(expected_return, module_output)
        elif assertion == "assertLessEqual":
            assertion_desc = "<="
            value["status"] = self.__assert_less_equal(expected_return, module_output)
        elif assertion == "assertEmpty":
            assertion_desc = "IS EMPTY"
            value["status"] = self.__assert_empty(module_output)
        elif assertion == "assertNotEmpty":
            assertion_desc = "IS NOT EMPTY"
            value["status"] = self.__assert_not_empty(module_output)
        else:
            value["status"] = "Fail - bad assertion"

        if output_details:
            if assertion_section:
                assertion_section_repr_title = " {}".format("assertion_section")
                assertion_section_repr_value = " {}".format(assertion_section)
            else:
                assertion_section_repr_title = ""
                assertion_section_repr_value = ""
            value[
                "module.function [args]{}".format(assertion_section_repr_title)
            ] = "{} {}{}".format(
                mod_and_func,
                dumps(args),
                assertion_section_repr_value,
            )
            value["saltcheck assertion"] = "{}{} {}".format(
                ("" if expected_return is None else "{} ".format(expected_return)),
                assertion_desc,
                ("hidden" if not assert_print_result else module_output),
            )

        return value

    def run_test(self, test_dict):
        """
        Run a single saltcheck test
        """
        result = {}
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

            assert_print_result = test_dict.get("print_result", True)

            actual_return = self._call_salt_command(mod_and_func, args, kwargs)

            if test_dict.get("assertions"):
                for num, assert_group in enumerate(
                    test_dict.get("assertions"), start=1
                ):
                    result["assertion{}".format(num)] = self._run_assertions(
                        mod_and_func,
                        args,
                        assert_group,
                        actual_return,
                        output_details,
                        assert_print_result,
                    )
                # Walk individual assert status results to set the top level status
                # key as needed
                for k, v in copy.deepcopy(result).items():
                    if k.startswith("assertion"):
                        for assert_k, assert_v in result[k].items():
                            if assert_k.startswith("status"):
                                if result[k][assert_k] != "Pass":
                                    result["status"] = "Fail"
                if not result.get("status"):
                    result["status"] = "Pass"
            else:
                result.update(
                    self._run_assertions(
                        mod_and_func,
                        args,
                        test_dict,
                        actual_return,
                        output_details,
                        assert_print_result,
                    )
                )

        else:
            result["status"] = "Fail - invalid test"

        end = time.time()
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
                assert expected == returned, "{} is not equal to {}".format(
                    expected, returned
                )
            else:
                assert expected == returned, "Result is not equal"
        except AssertionError as err:
            result = "Fail: " + str(err)
        return result

    @staticmethod
    def __assert_not_equal(expected, returned, assert_print_result=True):
        """
        Test if two objects are not equal
        """
        result = "Pass"
        try:
            if assert_print_result:
                assert expected != returned, "{} is equal to {}".format(
                    expected, returned
                )
            else:
                assert expected != returned, "Result is equal"
        except AssertionError as err:
            result = "Fail: " + str(err)
        return result

    @staticmethod
    def __assert_true(returned):
        """
        Test if an boolean is True
        """
        result = "Pass"
        try:
            assert returned is True, "{} not True".format(returned)
        except AssertionError as err:
            result = "Fail: " + str(err)
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
            assert returned is False, "{} not False".format(returned)
        except AssertionError as err:
            result = "Fail: " + str(err)
        return result

    @staticmethod
    def __assert_in(expected, returned, assert_print_result=True):
        """
        Test if a value is in the list of returned values
        """
        result = "Pass"
        try:
            if assert_print_result:
                assert expected in returned, "{} not found in {}".format(
                    expected, returned
                )
            else:
                assert expected in returned, "Result not found"
        except AssertionError as err:
            result = "Fail: " + str(err)
        return result

    @staticmethod
    def __assert_not_in(expected, returned, assert_print_result=True):
        """
        Test if a value is not in the list of returned values
        """
        result = "Pass"
        try:
            if assert_print_result:
                assert expected not in returned, "{} was found in {}".format(
                    expected, returned
                )
            else:
                assert expected not in returned, "Result was found"
        except AssertionError as err:
            result = "Fail: " + str(err)
        return result

    @staticmethod
    def __assert_greater(expected, returned):
        """
        Test if a value is greater than the returned value
        """
        result = "Pass"
        try:
            assert expected > returned, "{} not False".format(returned)
        except AssertionError as err:
            result = "Fail: " + str(err)
        return result

    @staticmethod
    def __assert_greater_equal(expected, returned):
        """
        Test if a value is greater than or equal to the returned value
        """
        result = "Pass"
        try:
            assert expected >= returned, "{} not False".format(returned)
        except AssertionError as err:
            result = "Fail: " + str(err)
        return result

    @staticmethod
    def __assert_less(expected, returned):
        """
        Test if a value is less than the returned value
        """
        result = "Pass"
        try:
            assert expected < returned, "{} not False".format(returned)
        except AssertionError as err:
            result = "Fail: " + str(err)
        return result

    @staticmethod
    def __assert_less_equal(expected, returned):
        """
        Test if a value is less than or equal to the returned value
        """
        result = "Pass"
        try:
            assert expected <= returned, "{} not False".format(returned)
        except AssertionError as err:
            result = "Fail: " + str(err)
        return result

    @staticmethod
    def __assert_empty(returned):
        """
        Test if a returned value is empty
        """
        result = "Pass"
        try:
            assert not returned, "{} is not empty".format(returned)
        except AssertionError as err:
            result = "Fail: " + str(err)
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
            result = "Fail: " + str(err)
        return result


class StateTestLoader:
    """
    Class loads in test files for a state
    e.g. state_dir/saltcheck-tests/[1.tst, 2.tst, 3.tst]
    """

    def __init__(self, saltenv="base"):
        self.path_type = None
        self.test_files = set()  # list of file paths
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
        self.test_files = set()

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
        test_path = "salt://{}/{}".format(
            state_name.replace(".", "/"), self.saltcheck_test_location
        )
        all_sls_paths.append(test_path)

        # process /path/to/saltcheck_test_location
        sls_split = state_name.split(".")
        sls_split.pop()
        test_path = "salt://{}/{}".format(
            "/".join(sls_split), self.saltcheck_test_location
        )
        all_sls_paths.append(test_path)

        state_name_base = state_name.split(".")[0]
        test_path = "salt://{}/{}".format(state_name_base, self.saltcheck_test_location)
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
            except OSError:
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
                    sls_path_names = {
                        os.path.join(
                            os.sep.join(split_sls),
                            os.path.normpath(self.saltcheck_test_location),
                            "init.tst",
                        ),
                        os.path.join(
                            os.sep.join(split_sls[: len(split_sls) - 1]),
                            os.path.normpath(self.saltcheck_test_location),
                            "{}.tst".format(split_sls[-1]),
                        ),
                        os.path.join(
                            split_sls[0],
                            os.path.normpath(self.saltcheck_test_location),
                            os.sep.join(split_sls[1:-1]),
                            "{}.tst".format(split_sls[-1]),
                        ),
                    }
                    # for this state, find matching test files and load them
                    cached_copied_files = list(set(cached_copied_files))
                    for this_cached_test_file in cached_copied_files:
                        if this_cached_test_file.endswith(tuple(sls_path_names)):
                            self.test_files.add(this_cached_test_file)
                            cached_copied_files.remove(this_cached_test_file)
                            log.debug("Adding .tst file: %s", this_cached_test_file)
