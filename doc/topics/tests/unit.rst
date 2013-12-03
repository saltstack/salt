==================
Writing Unit Tests
==================

Introduction
============

Like many software projects, Salt has two broad-based testing approaches -- integration testing and unit testing.
While integration testing focuses on the interaction between components in a sandboxed environment, unit testing focuses
on the singular implementation of individual functions.

Preparing to Write a Unit Test
==============================

Unit tests live in: `tests/unit/`__.

.. __: https://github.com/saltstack/salt/tree/develop/tests/unit

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

Let's assume that we're testing a very basic function in an imaginary Salt execution module. Given a module called
``fib.py`` that has a function called 'calculate(num_of_results)', which given a 'num_of_results', produces a list of 
sequential Fibonacci numbers of that length.

A unit test to test this function might be commonly placed in a file called ``tests/unit/modules/fib_test.py``. The 
convention is to place unit tests for Salt execution modules in ``test/unit/modules/`` and to name the tests module 
suffixed with ``_test.py``.

Tests are grouped around test cases, which are logically grouped sets of tests against a piece of functionality in the 
tested software. Test cases are created as Python classes in the unit test module. To return to our example, here's
how we might write the skeleton for testing ``fib.py``:

.. code-block:: python

    # Import Salt Testing libs
    from salttesting import TestCase

    # Import Salt execution module to test
    from salt.modules import fib

    # Create test case class and inherit from Salt's customized TestCase
    class FibTestCase(TestCase):

        '''
        If we want to set up variables common to all unit tests, we can do so
        by defining a setUp method, which will be run automatically before
        tests begin.
        '''
        def setUp(self):
            # Declare a simple set of five Fibonacci numbers starting at zero that we know are correct.
            self.fib_five = [0, 1, 1, 2, 3]

        def test_fib(self):
            '''
            To create a unit test, we should prefix the name with `test_' so that it's recognized by the test runner.
            '''
            self.assertEqual(fib.calculate(5), self.fib_five)


At this point, the test can now be run, either individually or as a part of a full run of the test runner. To ease 
development, a single test can be executed:

.. code-block:: bash

    tests/runtests.py -n unit.modules.fib_test

This will produce output indicating the success or failure of the tests in given test case. For more detailed results,
one can also include a flag to increase verbosity:

.. code-block:: bash

    tests/runtests.py -n unit.modules.fib_test -v

To review the results of a particular run, take a note of the log location given in the output for each test:

    **Logging tests on /var/folders/nl/d809xbq577l3qrbj3ymtpbq80000gn/T/salt-runtests.log**

Evaluating Truth
================

A longer discussion on the types of assertions one can make can be found by reading `Python's documentation on unit
testing`__.

.. __: http://docs.python.org/2/library/unittest.html#unittest.TestCase

Tests Using Mock Objects
========================

In many cases, the very purpose of a Salt module is to interact with some external system, whether it be to control a
database, manipulate files on a filesystem or many other examples. In these varied cases, it's necessary to design a
unit test which can test the function whilst replacing functions which might actually call out to external systems. One
might think of this as "blocking the exits" for code under tests and redirecting the calls to external systems with our
own code which produces known results during the duration of the test.

To achieve this behavior, Salt makes heavy use of the `MagicMock package`__.

To understand how one might integrate Mock into writing a unit test for Salt, let's imagine a scenario in which we're
testing an execution module that's designed to operate on a database. Furthermore, let's imagine two separate methods,
here presented in pseduo-code in an imaginary execution module called 'db.py.

.. code-block:: python

    def create_user(username):
        qry = 'CREATE USER {0}'.format(username)
        execute_query(qry)

    def execute_query(qry):
        # Connect to a database and actually do the query...

Here, let's imagine that we want to create a unit test for the `create_user` function. In doing so, we want to avoid any
calls out to an external system and so while we are running our unit tests, we want to replace the actual interaction
with a database with a function that can capture the parameters sent to it and return pre-defined values. Therefore, our
task is clear -- to write a unit test which tests the functionality of `create_user` while also replacing
'execute_query' with a mocked function.

To begin, we set up the skeleton of our class much like we did before, but with additional imports for MagicMock:

.. code-block:: python

    # Import Salt Testing libs
    from salttesting import TestCase

    # Import Salt execution module to test
    from salt.modules import db

    # NEW! -- Import Mock libraries
    from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch, call

    # Create test case class and inherit from Salt's customized TestCase

    @skipIf(NO_MOCK, NO_MOCK_REASON) #  Skip this test case if we don't have access to mock!
    class DbTestCase(TestCase):
        def test_create_user(self):
            # First, we replace 'execute_query' with our own mock function
            db.execute_query = MagicMock()

            # Now that the exits are blocked, we can run the function under test.

            db.create_user('testuser')

            # We could now query our mock object to see which calls were made to it.
            ## print db.execute_query.mock_calls

            '''
            We want to test to ensure that the correct query was formed.
            This is a contrived example, just designed to illustrate the concepts at hand.

            We're going to first contruct a call() object that represents the way we expect
            our mocked execute_query() function to have been called.
            Then, we'll examine the list of calls that were actually made to to execute_function().

            By comparing our expected call to execute_query() with create_user()'s call to
            execute_query(), we can determine the success or failure of our unit test.
            '''

            expected_call = call('CREATE USER testuser')

            # Do the comparison! Will assert False if execute_query() was not called with the given call

            db.execute_query.assert_has_calls(expected_call)


.. __: http://www.voidspace.org.uk/python/mock/index.html


Modifying ``__salt__`` In Place
===============================

At times, it becomes necessary to make modifications to a module's view of functions in its own ``__salt__`` dictionary.
Luckily, this process is quite easy.

Below is an example that uses MagicMock's ``patch`` functionality to insert a function into ``__salt__`` that's actually 
a MagicMock instance.

.. code-block:: python

    def show_patch(self):
        with patch.dict(my_module.__salt__, {'function.to_replace': MagicMock()}:
            # From this scope, carry on with testing, with a modified __salt__!
