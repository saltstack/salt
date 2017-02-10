.. _tutorial-salt-testing:

==================================
Salt's Test Suite: An Introduction
==================================

.. note::

    This tutorial makes a couple of assumptions. The first assumption is that
    you have a basic knowledge of Salt. To get up to speed, check out the
    :ref:`Salt Walkthrough </topics/tutorials/walkthrough>`.

    The second assumption is that your Salt development environment is already
    configured and that you have a basic understanding of contributing to the
    Salt codebase. If you're unfamiliar with either of these topics, please refer
    to the :ref:`Installing Salt for Development<installing-for-development>`
    and the :ref:`Contributing<contributing>` pages, respectively.

Salt comes with a powerful integration and unit test suite. The test suite
allows for the fully automated run of integration and/or unit tests from a
single interface.

Salt's test suite is located under the ``tests`` directory in the root of Salt's
code base and is divided into two main types of tests:
:ref:`unit tests and integration tests <integration-vs-unit>`. The ``unit`` and
``integration`` sub-test-suites are located in the ``tests`` directory, which is
where the majority of Salt's test cases are housed.


.. _getting_set_up_for_tests:

Getting Set Up For Tests
========================

There are a couple of requirements, in addition to Salt's requirements, that need
to be installed in order to run Salt's test suite. You can install these additional
requirements using the files located in the ``salt/requirements`` directory,
depending on your relevant version of Python:

.. code-block:: bash

    pip install -r requirements/dev_python26.txt
    pip install -r requirements/dev_python27.txt

To be able to run integration tests which utilizes ZeroMQ transport, you also
need to install additional requirements for it. Make sure you have installed
the C/C++ compiler and development libraries and header files needed for your
Python version.

This is an example for RedHat-based operating systems:

.. code-block:: bash

    yum install gcc gcc-c++ python-devel
    pip install -r requirements/zeromq.txt

On Debian, Ubuntu or their derivatives run the following commands:

.. code-block:: bash

    apt-get install build-essential python-dev
    pip install -r requirements/zeromq.txt

This will install the latest ``pycrypto`` and ``pyzmq`` (with bundled
``libzmq``) Python modules required for running integration tests suite.


Test Directory Structure
========================

As noted in the introduction to this tutorial, Salt's test suite is located in the
``tests`` directory in the root of Salt's code base. From there, the tests are divided
into two groups ``integration`` and ``unit``. Within each of these directories, the
directory structure roughly mirrors the directory structure of Salt's own codebase.
For example, the files inside ``tests/integration/modules`` contains tests for the
files located within ``salt/modules``.

.. note::

    ``tests/integration`` and ``tests/unit`` are the only directories discussed in
    this tutorial. With the exception of the ``tests/runtests.py`` file, which is
    used below in the `Running the Test Suite`_ section, the other directories and
    files located in ``tests`` are outside the scope of this tutorial.


.. _integration-vs-unit:

Integration vs. Unit
--------------------

Given that Salt's test suite contains two powerful, though very different, testing
approaches, when should you write integration tests and when should you write unit
tests?

Integration tests use Salt masters, minions, and a syndic to test salt functionality
directly and focus on testing the interaction of these components. Salt's integration
test runner includes functionality to run Salt execution modules, runners, states,
shell commands, salt-ssh commands, salt-api commands, and more. This provides a
tremendous ability to use Salt to test itself and makes writing such tests a breeze.
Integration tests are the preferred method of testing Salt functionality when
possible.

Unit tests do not spin up any Salt daemons, but instead find their value in testing
singular implementations of individual functions. Instead of testing against specific
interactions, unit tests should be used to test a function's logic. Unit tests should
be used to test a function's exit point(s) such as any ``return`` or ``raises``
statements.

Unit tests are also useful in cases where writing an integration test might not be
possible. While the integration test suite is extremely powerful, unfortunately at
this time, it does not cover all functional areas of Salt's ecosystem. For example,
at the time of this writing, there is not a way to write integration tests for Proxy
Minions. Since the test runner will need to be adjusted to account for Proxy Minion
processes, unit tests can still provide some testing support in the interim by
testing the logic contained inside Proxy Minion functions.


Running the Test Suite
======================

Once all of the :ref:`requirements <getting_set_up_for_tests>` are installed, the
``runtests.py`` file in the ``salt/tests`` directory is used to instantiate
Salt's test suite:

.. code-block:: bash

    python tests/runtests.py [OPTIONS]

The command above, if executed without any options, will run the entire suite of
integration and unit tests. Some tests require certain flags to run, such as
destructive tests. If these flags are not included, then the test suite will only
perform the tests that don't require special attention.

At the end of the test run, you will see a summary output of the tests that passed,
failed, or were skipped.

The test runner also includes a ``--help`` option that lists all of the various
command line options:

.. code-block:: bash

    python tests/runtests.py --help

You can also call the test runner as an executable:

.. code-block:: bash

    ./tests/runtests.py --help


Running Integration Tests
-------------------------

Salt's set of integration tests use Salt to test itself. The integration portion
of the test suite includes some built-in Salt daemons that will spin up in preparation
of the test run. This list of Salt daemon processes includes:

* 2 Salt Masters
* 2 Salt Minions
* 1 Salt Syndic

These various daemons are used to execute Salt commands and functionality within
the test suite, allowing you to write tests to assert against expected or
unexpected behaviors.

A simple example of a test utilizing a typical master/minion execution module command
is the test for the ``test_ping`` function in the ``tests/integration/modules/test.py``
file:

.. code-block:: python

    def test_ping(self):
        '''
        test.ping
        '''
        self.assertTrue(self.run_function('test.ping'))

The test above is a very simple example where the ``test.ping`` function is
executed by Salt's test suite runner and is asserting that the minion returned
with a ``True`` response.


.. _test-selection-options:

Test Selection Options
~~~~~~~~~~~~~~~~~~~~~~

If you look in the output of the ``--help`` command of the test runner, you will
see a section called ``Tests Selection Options``. The options under this section
contain various subsections of the integration test suite such as ``--modules``,
``--ssh``, or ``--states``. By selecting any one of these options, the test daemons
will spin up and the integration tests in the named subsection will run.

.. code-block:: bash

    ./tests/runtests.py --modules

.. note::

    The testing subsections listed in the ``Tests Selection Options`` of the
    ``--help`` output *only* apply to the integration tests. They do not run unit
    tests.


Running Unit Tests
------------------

While ``./tests/runtests.py`` executes the *entire* test suite (barring any tests
requiring special flags), the ``--unit`` flag can be used to run *only* Salt's
unit tests. Salt's unit tests include the tests located in the ``tests/unit``
directory.

The unit tests do not spin up any Salt testing daemons as the integration tests
do and execute very quickly compared to the integration tests.

.. code-block:: bash

    ./tests/runtests.py --unit


.. _running-specific-tests:

Running Specific Tests
----------------------

There are times when a specific test file, test class, or even a single,
individual test need to be executed, such as when writing new tests. In these
situations, the ``--name`` option should be used.

For running a single test file, such as the pillar module test file in the
integration test directory, you must provide the file path using ``.`` instead
of ``/`` as separators and no file extension:

.. code-block:: bash

    ./tests/runtests.py --name=integration.modules.pillar
    ./tests/runtests.py -n integration.modules.pillar

Some test files contain only one test class while other test files contain multiple
test classes. To run a specific test class within the file, append the name of
the test class to the end of the file path:

.. code-block:: bash

    ./tests/runtests.py --name=integration.modules.pillar.PillarModuleTest
    ./tests/runtests.py -n integration.modules.pillar.PillarModuleTest

To run a single test within a file, append both the name of the test class the
individual test belongs to, as well as the name of the test itself:

.. code-block:: bash

    ./tests/runtests.py --name=integration.modules.pillar.PillarModuleTest.test_data
    ./tests/runtests.py -n integration.modules.pillar.PillarModuleTest.test_data

The ``--name`` and ``-n`` options can be used for unit tests as well as integration
tests. The following command is an example of how to execute a single test found in
the ``tests/unit/modules/cp_test.py`` file:

.. code-block:: bash

    ./tests/runtests.py -n unit.modules.cp_test.CpTestCase.test_get_template_success


Writing Tests for Salt
======================

Once you're comfortable running tests, you can now start writing them! Be sure
to review the `Integration vs. Unit`_ section of this tutorial to determine what
type of test makes the most sense for the code you're testing.

.. note::

    There are many decorators, naming conventions, and code specifications
    required for Salt test files. We will not be covering all of the these specifics
    in this tutorial. Please refer to the testing documentation links listed below
    in the `Additional Testing Documentation`_ section to learn more about these
    requirements.

    In the following sections, the test examples assume the "new" test is added to
    a test file that is already present and regularly running in the test suite and
    is written with the correct requirements.


Writing Integration Tests
-------------------------

Since integration tests validate against a running environment, as explained in the
`Running Integration Tests`_ section of this tutorial, integration tests are very
easy to write and are generally the preferred method of writing Salt tests.

The following integration test is an example taken from the ``test.py`` file in the
``tests/integration/modules`` directory. This test uses the ``run_function`` method
to test the functionality of a traditional execution module command.

The ``run_function`` method uses the integration test daemons to execute a
``module.function`` command as you would with Salt. The minion runs the function and
returns. The test also uses `Python's Assert Functions`_ to test that the
minion's return is expected.

.. code-block:: python

    def test_ping(self):
        '''
        test.ping
        '''
        self.assertTrue(self.run_function('test.ping'))

Args can be passed in to the ``run_function`` method as well:

.. code-block:: python

    def test_echo(self):
        '''
        test.echo
        '''
        self.assertEqual(self.run_function('test.echo', ['text']), 'text')

The next example is taken from the ``tests/integration/modules/aliases.py`` file and
demonstrates how to pass kwargs to the ``run_function`` call. Also note that this
test uses another salt function to ensure the correct data is present (via the
``aliases.set_target`` call) before attempting to assert what the ``aliases.get_target``
call should return.

.. code-block:: python

    def test_set_target(self):
        '''
        aliases.set_target and aliases.get_target
        '''
        set_ret = self.run_function(
                'aliases.set_target',
                alias='fred',
                target='bob')
        self.assertTrue(set_ret)
        tgt_ret = self.run_function(
                'aliases.get_target',
                alias='fred')
        self.assertEqual(tgt_ret, 'bob')

Using multiple Salt commands in this manner provides two useful benefits. The first is
that it provides some additional coverage for the ``aliases.set_target`` function.
The second benefit is the call to ``aliases.get_target`` is not dependent on the
presence of any aliases set outside of this test. Tests should not be dependent on
the previous execution, success, or failure of other tests. They should be isolated
from other tests as much as possible.

While it might be tempting to build out a test file where tests depend on one another
before running, this should be avoided. SaltStack recommends that each test should
test a single functionality and not rely on other tests. Therefore, when possible,
individual tests should also be broken up into singular pieces. These are not
hard-and-fast rules, but serve more as recommendations to keep the test suite simple.
This helps with debugging code and related tests when failures occur and problems
are exposed. There may be instances where large tests use many asserts to set up a
use case that protects against potential regressions.

.. note::

    The examples above all use the ``run_function`` option to test execution module
    functions in a traditional master/minion environment. To see examples of how to
    test other common Salt components such as runners, salt-api, and more, please
    refer to the :ref:`Integration Test Class Examples<integration-class-examples>`
    documentation.


Destructive vs Non-destructive Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Since Salt is used to change the settings and behavior of systems, often, the
best approach to run tests is to make actual changes to an underlying system.
This is where the concept of destructive integration tests comes into play.
Tests can be written to alter the system they are running on. This capability
is what fills in the gap needed to properly test aspects of system management
like package installation.

To write a destructive test, import and use the ``destructiveTest`` decorator for
the test method:

.. code-block:: python

    import integration
    from salttesting.helpers import destructiveTest

    class PkgTest(integration.ModuleCase):
        @destructiveTest
        def test_pkg_install(self):
            ret = self.run_function('pkg.install', name='finch')
            self.assertSaltTrueReturn(ret)
            ret = self.run_function('pkg.purge', name='finch')
            self.assertSaltTrueReturn(ret)


Writing Unit Tests
------------------

As explained in the `Integration vs. Unit`_ section above, unit tests should be
written to test the *logic* of a function. This includes focusing on testing
``return`` and ``raises`` statements. Substantial effort should be made to mock
external resources that are used in the code being tested.

External resources that should be mocked include, but are not limited to, APIs,
function calls, external data either globally available or passed in through
function arguments, file data, etc. This practice helps to isolate unit tests to
test Salt logic. One handy way to think about writing unit tests is to "block
all of the exits". More information about how to properly mock external resources
can be found in Salt's :ref:`Unit Test<unit-tests>` documentation.

Salt's unit tests utilize Python's mock class as well as `MagicMock`_. The
``@patch`` decorator is also heavily used when "blocking all the exits".

A simple example of a unit test currently in use in Salt is the
``test_get_file_not_found`` test in the ``tests/unit/modules/cp_test.py`` file.
This test uses the ``@patch`` decorator and ``MagicMock`` to mock the return
of the call to Salt's ``cp.hash_file`` execution module function. This ensures
that we're testing the ``cp.get_file`` function directly, instead of inadvertently
testing the call to ``cp.hash_file``, which is used in ``cp.get_file``.

.. code-block:: python

    @patch('salt.modules.cp.hash_file', MagicMock(return_value=False))
    def test_get_file_not_found(self):
        '''
        Test if get_file can't find the file.
        '''
        path = 'salt://saltines'
        dest = '/srv/salt/cheese'
        ret = ''
        self.assertEqual(cp.get_file(path, dest), ret)

Note that Salt's ``cp`` module is imported at the top of the file, along with all
of the other necessary testing imports. The ``get_file`` function is then called
directed in the testing function, instead of using the ``run_function`` method as
the integration test examples do above.

The call to ``cp.get_file`` returns an empty string when a ``hash_file`` isn't found.
Therefore, the example above is a good illustration of a unit test "blocking
the exits" via the ``@patch`` decorator, as well as testing logic via asserting
against the ``return`` statement in the ``if`` clause.

There are more examples of writing unit tests of varying complexities available
in the following docs:

* :ref:`Simple Unit Test Example<simple-unit-example>`
* :ref:`Complete Unit Test Example<complete-unit-example>`
* :ref:`Complex Unit Test Example<complex-unit-example>`

.. note::

    Considerable care should be made to ensure that you're testing something
    useful in your test functions. It is very easy to fall into a situation
    where you have mocked so much of the original function that the test
    results in only asserting against the data you have provided. This results
    in a poor and fragile unit test.


Automated Test Runs
===================

SaltStack maintains a Jenkins server which can be viewed at
https://jenkins.saltstack.com. The tests executed from this Jenkins server
create fresh virtual machines for each test run, then execute the destructive
tests on the new, clean virtual machine. This allows for the execution of tests
across supported platforms.


Additional Testing Documentation
================================

In addition to this tutorial, there are some other helpful resources and documentation
that go into more depth on Salt's test runner, writing tests for Salt code, and general
Python testing documentation. Please see the follow references for more information:

* :ref:`Salt's Test Suite Documentation<salt-test-suite>`
* :ref:`Integration Tests<integration-tests>`
* :ref:`Unit Tests<unit-tests>`
* `MagicMock`_
* `Python Unittest`_
* `Python's Assert Functions`_

.. _MagicMock: http://www.voidspace.org.uk/python/mock/index.html
.. _Python Unittest: https://docs.python.org/2/library/unittest.html
.. _Python's Assert Functions: https://docs.python.org/2/library/unittest.html#assert-methods
