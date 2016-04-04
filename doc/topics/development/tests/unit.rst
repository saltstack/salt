==================
Writing Unit Tests
==================

Introduction
============

Like many software projects, Salt has two broad-based testing approaches --
integration testing and unit testing. While integration testing focuses on the
interaction between components in a sandboxed environment, unit testing focuses
on the singular implementation of individual functions.

Preparing to Write a Unit Test
==============================

This guide assumes you've followed the `directions for setting up salt testing`__.

Unit tests should be written to the following specifications:

- Each ``raise`` and ``return`` statement needs to be independently tested.

- Unit tests for ``salt/.../<module>.py`` are contained in a file called
  ``tests/unit/.../<module>_test.py``, e.g. the tests for
  ``salt/modules/fib.py`` are in ``tests/unit/modules/fib_test.py``.

- Test functions are named ``test_<fcn>_<test-name>`` where ``<fcn>`` is the
  function being tested and ``<test-name>`` describes the ``raise`` or
  ``return`` being tested.

- A reasonable effort needs to be made to mock external resources used in the
  code being tested, such as APIs, function calls, external data either
  globally available or passed in through function arguments, file data, etc.

- Test functions should contain only one assertion and all necessary mock code
  and data for that assertion.

.. __: http://docs.saltstack.com/topics/installation/index.html

Most commonly, the following imports are necessary to create a unit test:

.. code-block:: python

    # Import Salt Testing libs
    from salttesting import skipIf, TestCase
    from salttesting.helpers import ensure_in_syspath

If you need mock support to your tests, please also import:

.. code-block:: python

    from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch, call

A Simple Example
================

Let's assume that we're testing a very basic function in an imaginary Salt
execution module. Given a module called ``fib.py`` that has a function called
``calculate(num_of_results)``, which given a ``num_of_results``, produces a list of
sequential Fibonacci numbers of that length.

A unit test to test this function might be commonly placed in a file called
``tests/unit/modules/fib_test.py``. The convention is to place unit tests for
Salt execution modules in ``test/unit/modules/`` and to name the tests module
suffixed with ``_test.py``.

Tests are grouped around test cases, which are logically grouped sets of tests
against a piece of functionality in the tested software. Test cases are created
as Python classes in the unit test module. To return to our example, here's how
we might write the skeleton for testing ``fib.py``:

.. code-block:: python

    # Import Salt Testing libs
    from salttesting import TestCase

    # Import Salt execution module to test
    from salt.modules import fib

    # Create test case class and inherit from Salt's customized TestCase
    class FibTestCase(TestCase):
        '''
        This class contains a set of functions that test salt.modules.fib.
        '''
        def test_fib(self):
            '''
            To create a unit test, we should prefix the name with `test_' so
            that it's recognized by the test runner.
            '''
            fib_five = (0, 1, 1, 2, 3)
            self.assertEqual(fib.calculate(5), fib_five)

At this point, the test can now be run, either individually or as a part of a
full run of the test runner. To ease development, a single test can be
executed:

.. code-block:: bash

    tests/runtests.py -v -n unit.modules.fib_test

This will report the status of the test: success, failure, or error.  The
``-v`` flag increases output verbosity.

.. code-block:: bash

    tests/runtests.py -n unit.modules.fib_test -v

To review the results of a particular run, take a note of the log location
given in the output for each test:

.. code-block:: text

    Logging tests on /var/folders/nl/d809xbq577l3qrbj3ymtpbq80000gn/T/salt-runtests.log

Evaluating Truth
================

A longer discussion on the types of assertions one can make can be found by
reading `Python's documentation on unit testing`__.

.. __: http://docs.python.org/2/library/unittest.html#unittest.TestCase

Tests Using Mock Objects
========================

In many cases, the purpose of a Salt module is to interact with some external
system, whether it be to control a database, manipulate files on a filesystem
or something else. In these varied cases, it's necessary to design a unit test
which can test the function whilst replacing functions which might actually
call out to external systems. One might think of this as "blocking the exits"
for code under tests and redirecting the calls to external systems with our own
code which produces known results during the duration of the test.

To achieve this behavior, Salt makes heavy use of the `MagicMock package`__.

To understand how one might integrate Mock into writing a unit test for Salt,
let's imagine a scenario in which we're testing an execution module that's
designed to operate on a database. Furthermore, let's imagine two separate
methods, here presented in pseduo-code in an imaginary execution module called
'db.py.

.. code-block:: python

    def create_user(username):
        qry = 'CREATE USER {0}'.format(username)
        execute_query(qry)

    def execute_query(qry):
        # Connect to a database and actually do the query...

Here, let's imagine that we want to create a unit test for the `create_user`
function. In doing so, we want to avoid any calls out to an external system and
so while we are running our unit tests, we want to replace the actual
interaction with a database with a function that can capture the parameters
sent to it and return pre-defined values. Therefore, our task is clear -- to
write a unit test which tests the functionality of `create_user` while also
replacing 'execute_query' with a mocked function.

To begin, we set up the skeleton of our class much like we did before, but with
additional imports for MagicMock:

.. code-block:: python

    # Import Salt Testing libs
    from salttesting import TestCase

    # Import Salt execution module to test
    from salt.modules import db

    # Import Mock libraries
    from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch, call

    # Create test case class and inherit from Salt's customized TestCase
    # Skip this test case if we don't have access to mock!
    @skipIf(NO_MOCK, NO_MOCK_REASON)
    class DbTestCase(TestCase):
        def test_create_user(self):
            # First, we replace 'execute_query' with our own mock function
            db.execute_query = MagicMock()

            # Now that the exits are blocked, we can run the function under test.
            db.create_user('testuser')

            # We could now query our mock object to see which calls were made
            # to it.
            ## print db.execute_query.mock_calls

            # Construct a call object that simulates the way we expected
            # execute_query to have been called.
            expected_call = call('CREATE USER testuser')

            # Compare the expected call with the list of actual calls.  The
            # test will succeed or fail depending on the output of this
            # assertion.
            db.execute_query.assert_has_calls(expected_call)

.. __: http://www.voidspace.org.uk/python/mock/index.html

Modifying ``__salt__`` In Place
===============================

At times, it becomes necessary to make modifications to a module's view of
functions in its own ``__salt__`` dictionary.  Luckily, this process is quite
easy.

Below is an example that uses MagicMock's ``patch`` functionality to insert a
function into ``__salt__`` that's actually a MagicMock instance.

.. code-block:: python

    def show_patch(self):
        with patch.dict(my_module.__salt__,
                        {'function.to_replace': MagicMock()}:
            # From this scope, carry on with testing, with a modified __salt__!

A More Complete Example
=======================

Consider the following function from salt/modules/linux_sysctl.py.

.. code-block:: python

    def get(name):
        '''
        Return a single sysctl parameter for this minion

        CLI Example:

        .. code-block:: bash

            salt '*' sysctl.get net.ipv4.ip_forward
        '''
        cmd = 'sysctl -n {0}'.format(name)
        out = __salt__['cmd.run'](cmd)
        return out

This function is very simple, comprising only four source lines of code and
having only one return statement, so we know only one test is needed.  There
are also two inputs to the function, the ``name`` function argument and the call
to ``__salt__['cmd.run']()``, both of which need to be appropriately mocked.

Mocking a function parameter is straightforward, whereas mocking a function
call will require, in this case, the use of MagicMock.  For added isolation, we
will also redefine the ``__salt__`` dictionary such that it only contains
``'cmd.run'``.

.. code-block:: python

    # Import Salt Libs
    from salt.modules import linux_sysctl

    # Import Salt Testing Libs
    from salttesting import skipIf, TestCase
    from salttesting.helpers import ensure_in_syspath
    from salttesting.mock import (
        MagicMock,
        patch,
        NO_MOCK,
        NO_MOCK_REASON
    )

    ensure_in_syspath('../../')

    # Globals
    linux_sysctl.__salt__ = {}


    @skipIf(NO_MOCK, NO_MOCK_REASON)
    class LinuxSysctlTestCase(TestCase):
        '''
        TestCase for salt.modules.linux_sysctl module
        '''

        def test_get(self):
            '''
            Tests the return of get function
            '''
            mock_cmd = MagicMock(return_value=1)
            with patch.dict(linux_sysctl.__salt__, {'cmd.run': mock_cmd}):
                self.assertEqual(linux_sysctl.get('net.ipv4.ip_forward'), 1)


    if __name__ == '__main__':
        from integration import run_tests
        run_tests(LinuxSysctlTestCase, needs_daemon=False)

Since ``get()`` has only one raise or return statement and that statement is a
success condition, the test function is simply named ``test_get()``.  As
described, the single function call parameter, ``name`` is mocked with
``net.ipv4.ip_forward`` and ``__salt__['cmd.run']`` is replaced by a MagicMock
function object.  We are only interested in the return value of
``__salt__['cmd.run']``, which MagicMock allows us by specifying via
``return_value=1``.  Finally, the test itself tests for equality between the
return value of ``get()`` and the expected return of ``1``.  This assertion is
expected to succeed because ``get()`` will determine its return value from
``__salt__['cmd.run']``, which we have mocked to return ``1``.

A Complex Example
=================

Now consider the ``assign()`` function from the same
salt/modules/linux_sysctl.py source file.

.. code-block:: python

    def assign(name, value):
        '''
        Assign a single sysctl parameter for this minion

        CLI Example:

        .. code-block:: bash

            salt '*' sysctl.assign net.ipv4.ip_forward 1
        '''
        value = str(value)
        sysctl_file = '/proc/sys/{0}'.format(name.replace('.', '/'))
        if not os.path.exists(sysctl_file):
            raise CommandExecutionError('sysctl {0} does not exist'.format(name))

        ret = {}
        cmd = 'sysctl -w {0}="{1}"'.format(name, value)
        data = __salt__['cmd.run_all'](cmd)
        out = data['stdout']
        err = data['stderr']

        # Example:
        #    # sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"
        #    net.ipv4.tcp_rmem = 4096 87380 16777216
        regex = re.compile(r'^{0}\s+=\s+{1}$'.format(re.escape(name),
                                                     re.escape(value)))

        if not regex.match(out) or 'Invalid argument' in str(err):
            if data['retcode'] != 0 and err:
                error = err
            else:
                error = out
            raise CommandExecutionError('sysctl -w failed: {0}'.format(error))
        new_name, new_value = out.split(' = ', 1)
        ret[new_name] = new_value
        return ret

This function contains two raise statements and one return statement, so we
know that we will need (at least) three tests.  It has two function arguments
and many references to non-builtin functions.  In the tests below you will see
that MagicMock's ``patch()`` method may be used as a context manager or as a
decorator.

There are three test functions, one for each raise and return statement in the
source function.  Each function is self-contained and contains all and only the
mocks and data needed to test the raise or return statement it is concerned
with.

.. code-block:: python

    # Import Salt Libs
    from salt.modules import linux_sysctl
    from salt.exceptions import CommandExecutionError

    # Import Salt Testing Libs
    from salttesting import skipIf, TestCase
    from salttesting.helpers import ensure_in_syspath
    from salttesting.mock import (
        MagicMock,
        patch,
        NO_MOCK,
        NO_MOCK_REASON
    )

    ensure_in_syspath('../../')

    # Globals
    linux_sysctl.__salt__ = {}


    @skipIf(NO_MOCK, NO_MOCK_REASON)
    class LinuxSysctlTestCase(TestCase):
        '''
        TestCase for salt.modules.linux_sysctl module
        '''

        @patch('os.path.exists', MagicMock(return_value=False))
        def test_assign_proc_sys_failed(self):
            '''
            Tests if /proc/sys/<kernel-subsystem> exists or not
            '''
            cmd = {'pid': 1337, 'retcode': 0, 'stderr': '',
                   'stdout': 'net.ipv4.ip_forward = 1'}
            mock_cmd = MagicMock(return_value=cmd)
            with patch.dict(linux_sysctl.__salt__, {'cmd.run_all': mock_cmd}):
                self.assertRaises(CommandExecutionError,
                                  linux_sysctl.assign,
                                  'net.ipv4.ip_forward', 1)

        @patch('os.path.exists', MagicMock(return_value=True))
        def test_assign_cmd_failed(self):
            '''
            Tests if the assignment was successful or not
            '''
            cmd = {'pid': 1337, 'retcode': 0, 'stderr':
                   'sysctl: setting key "net.ipv4.ip_forward": Invalid argument',
                   'stdout': 'net.ipv4.ip_forward = backward'}
            mock_cmd = MagicMock(return_value=cmd)
            with patch.dict(linux_sysctl.__salt__, {'cmd.run_all': mock_cmd}):
                self.assertRaises(CommandExecutionError,
                                  linux_sysctl.assign,
                                  'net.ipv4.ip_forward', 'backward')

        @patch('os.path.exists', MagicMock(return_value=True))
        def test_assign_success(self):
            '''
            Tests the return of successful assign function
            '''
            cmd = {'pid': 1337, 'retcode': 0, 'stderr': '',
                   'stdout': 'net.ipv4.ip_forward = 1'}
            ret = {'net.ipv4.ip_forward': '1'}
            mock_cmd = MagicMock(return_value=cmd)
            with patch.dict(linux_sysctl.__salt__, {'cmd.run_all': mock_cmd}):
                self.assertEqual(linux_sysctl.assign(
                    'net.ipv4.ip_forward', 1), ret)

    if __name__ == '__main__':
        from integration import run_tests
        run_tests(LinuxSysctlTestCase, needs_daemon=False)
