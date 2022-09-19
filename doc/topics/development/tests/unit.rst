.. _unit-tests:

==================
Writing Unit Tests
==================

Introduction
============

Like many software projects, Salt has two broad-based testing approaches --
integration testing and unit testing. While integration testing focuses on the
interaction between components in a sandboxed environment, unit testing focuses
on the singular implementation of individual functions.

Unit tests should be used specifically to test a function's logic. Unit tests
rely on mocking external resources.

While unit tests are good for ensuring consistent results, they are most
useful when they do not require more than a few mocks. Effort should be
made to mock as many external resources as possible. This effort is encouraged,
but not required. Sometimes the isolation provided by completely mocking the
external dependencies is not worth the effort of mocking those dependencies.

In these cases, requiring an external library to be installed on the
system before running the test file is a useful way to strike this balance.
For example, the unit tests for the MySQL execution module require the
presence of the MySQL python bindings on the system running the test file
before proceeding to run the tests.

Overly detailed mocking can also result in decreased test readability and
brittleness as the tests are more likely to fail when the code or its
dependencies legitimately change. In these cases, it is better to add
dependencies to the test runner dependency state.


Preparing to Write a Unit Test
==============================

This guide assumes that your Salt development environment is already configured
and that you have a basic understanding of contributing to the Salt codebase.
If you're unfamiliar with either of these topics, please refer to the
:ref:`Installing Salt for Development<installing-for-development>` and the
:ref:`Contributing<contributing>` pages, respectively.

This documentation also assumes that you have an understanding of how to
:ref:`run Salt's test suite<running-the-tests>`, including running the
:ref:`unit test subsection<running-test-subsections>`, running the unit tests
:ref:`without testing daemons<running-unit-tests-no-daemons>` to speed up
development wait times, and running a unit test file, class, or individual test.


Best Practices
==============

Unit tests should be written to the following specifications.


What to Test?
-------------

Since unit testing focuses on the singular implementation of individual functions,
unit tests should be used specifically to test a function's logic. The following
guidelines should be followed when writing unit tests for Salt's test suite:

- Each ``raise`` and ``return`` statement needs to be independently tested.
- Isolate testing functionality. Don't rely on the pass or failure of other,
  separate tests.
- Test functions should contain only one assertion, at most, multiple
  assertions can be made, but against the same outcome.
- Many Salt execution modules are merely wrappers for distribution-specific
  functionality. If there isn't any logic present in a simple execution module,
  consider writing an :ref:`integration test<integration-tests>` instead of
  heavily mocking a call to an external dependency.


Mocking Test Data
-----------------

A reasonable effort needs to be made to mock external resources used in the
code being tested, such as APIs, function calls, external data either
globally available or passed in through function arguments, file data, etc.

- Test functions should contain only one assertion and all necessary mock code
  and data for that assertion.
- External resources should be mocked in order to "block all of the exits". If a
  test function fails because something in an external library wasn't mocked
  properly (or at all), this test is not addressing all of the "exits" a function
  may experience. We want the Salt code and logic to be tested, specifically.
- Consider the fragility and longevity of a test. If the test is so tightly coupled
  to the code being tested, this makes a test unnecessarily fragile.
- Make sure you are not mocking the function to be tested so vigorously that the
  test return merely tests the mocked output. The test should always be testing
  a function's logic.


Mocking Loader Modules
----------------------

Salt loader modules use a series of globally available dunder variables,
``__salt__``, ``__opts__``, ``__pillar__``, etc. To facilitate testing these
modules `pytest-salt-factories`_ has a plugin which will prepare the module globals
by patching and mocking the dunders prior to running each test, as long as the test module
defines a fixture named ``configure_loader_modules``. Check out the code for the
`pytest-salt-factories plugin` to know how it's internals work.

The reason for the existence of this plugin is because historically one would add these dunder
variables directly on the imported module. This, however, introduces unexpected behavior when
running the full test suite since those attributes would not be removed once we were done testing
the module and would therefore leak to other modules being tested with unpredictable results. This
is the kind of work that should be deferred to mock, and that's exactly what this plugin provides.

.. _`pytest-salt-factories`: https://github.com/saltstack/pytest-salt-factories
.. _`pytest-salt-factories plugin`: https://github.com/saltstack/pytest-salt-factories/blob/master/saltfactories/plugins/loader.py

As an example, if one needs to specify some options which should be available
to the module being tested one should do:

.. code-block:: python

   import pytest
   import salt.modules.somemodule as somemodule


   @pytest.fixture
   def configure_loader_modules():
       """
       This fixture should return a dictionary which is what's going to be used to
       patch and mock Salt's loader
       """
       return {somemodule: {"__opts__": {"test": True}}}


Consider this more extensive example from ``tests/pytests/unit/beacons/test_sensehat.py``:

.. code-block:: python

   import pytest
   import salt.beacons.sensehat as sensehat
   from tests.support.mock import MagicMock


   @pytest.fixture
   def configure_loader_modules():
       return {
           sensehat: {
               "__salt__": {
                   "sensehat.get_humidity": MagicMock(return_value=80),
                   "sensehat.get_temperature": MagicMock(return_value=30),
                   "sensehat.get_pressure": MagicMock(return_value=1500),
               },
           }
       }


   def test_non_list_config():
       config = {}

       ret = sensehat.validate(config)

       assert ret == (False, "Configuration for sensehat beacon must be a list.")


   def test_empty_config():
       config = [{}]

       ret = sensehat.validate(config)

       assert ret == (False, "Configuration for sensehat beacon requires sensors.")


   def test_sensehat_humidity_match():

       config = [{"sensors": {"humidity": "70%"}}]

       ret = sensehat.validate(config)
       assert ret == (True, "Valid beacon configuration")

       ret = sensehat.beacon(config)
       assert ret == [{"tag": "sensehat/humidity", "humidity": 80}]


   def test_sensehat_temperature_match():

       config = [{"sensors": {"temperature": 20}}]

       ret = sensehat.validate(config)
       assert ret == (True, "Valid beacon configuration")

       ret = sensehat.beacon(config)
       assert ret == [{"tag": "sensehat/temperature", "temperature": 30}]


   def test_sensehat_temperature_match_range():

       config = [{"sensors": {"temperature": [20, 29]}}]

       ret = sensehat.validate(config)
       assert ret == (True, "Valid beacon configuration")

       ret = sensehat.beacon(config)
       assert ret == [{"tag": "sensehat/temperature", "temperature": 30}]


   def test_sensehat_pressure_match():

       config = [{"sensors": {"pressure": "1400"}}]

       ret = sensehat.validate(config)
       assert ret == (True, "Valid beacon configuration")

       ret = sensehat.beacon(config)
       assert ret == [{"tag": "sensehat/pressure", "pressure": 1500}]


   def test_sensehat_no_match():

       config = [{"sensors": {"pressure": "1600"}}]

       ret = sensehat.validate(config)
       assert ret == (True, "Valid beacon configuration")

       ret = sensehat.beacon(config)
       assert ret == []


What happens in the above example is we mock several calls of the ``sensehat``
module to return known expected values to assert against.

Mocking Filehandles
-------------------

.. note::
    This documentation applies to the 2018.3 release cycle and newer. The
    extended functionality for ``mock_open`` described below does not exist in
    the 2017.7 and older release branches.

Opening files in Salt is done using ``salt.utils.files.fopen()``. When testing
code that reads from files, the ``mock_open`` helper can be used to mock
filehandles. Note that is not the same ``mock_open`` as
:py:func:`unittest.mock.mock_open` from the Python standard library, but rather
a separate implementation which has additional functionality.

.. code-block:: python

    from tests.support.mock import patch, mock_open

    import salt.modules.mymod as mymod


    def test_something():
        fopen_mock = mock_open(read_data="foo\nbar\nbaz\n")
        with patch("salt.utils.files.fopen", fopen_mock):
            result = mymod.myfunc()
            assert result is True

This will force any filehandle opened to mimic a filehandle which, when read,
produces the specified contents.

.. important::
    **String Types**

    When configuring your read_data, make sure that you are using
    bytestrings (e.g. ``b"foo\nbar\nbaz\n"``) when the code you are testing is
    opening a file for binary reading, otherwise the tests will fail.  The
    mocked filehandles produced by ``mock_open`` will raise a
    :py:obj:`TypeError` if you attempt to read a bytestring when opening for
    non-binary reading, and similarly will not let you read a string when
    opening a file for binary reading. They will also not permit bytestrings to
    be "written" if the mocked filehandle was opened for non-binary writing,
    and vice-versa when opened for non-binary writing. These enhancements force
    test writers to write more accurate tests.

More Complex Scenarios
**********************

.. _unit-tests-multiple-file-paths:

Multiple File Paths
+++++++++++++++++++

What happens when the code being tested reads from more than one file? For
those cases, you can pass ``read_data`` as a dictionary:

.. code-block:: python

    import textwrap

    from tests.support.mock import patch, mock_open

    import salt.modules.mymod as mymod


    def test_something():
        contents = {
            "/etc/foo.conf": textwrap.dedent(
                """\
                foo
                bar
                baz
                """
            ),
            "/etc/b*.conf": textwrap.dedent(
                """\
                one
                two
                three
                """
            ),
        }
        fopen_mock = mock_open(read_data=contents)
        with patch("salt.utils.files.fopen", fopen_mock):
            result = mymod.myfunc()
            assert result is True

This would make ``salt.utils.files.fopen()`` produce filehandles with different
contents depending on which file was being opened by the code being tested.
``/etc/foo.conf`` and any file matching the pattern ``/etc/b*.conf`` would
work, while opening any other path would result in a
:py:obj:`FileNotFoundError` being raised.

Since file patterns are supported, it is possible to use a pattern of ``'*'``
to define a fallback if no other patterns match the filename being opened. The
below two ``mock_open`` calls would produce identical results:

.. code-block:: python

    mock_open(read_data="foo\n")
    mock_open(read_data={"*": "foo\n"})

.. note::
    Take care when specifying the ``read_data`` as a dictionary, in cases where
    the patterns overlap (e.g. when both ``/etc/b*.conf`` and ``/etc/bar.conf``
    are in the ``read_data``). Dictionary iteration order will determine which
    pattern is attempted first, second, etc., with the exception of ``*`` which
    is used when no other pattern matches. If your test case calls for
    specifying overlapping patterns, and you are not running Python 3.6 or
    newer, then an ``OrderedDict`` can be used to ensure matching is handled in
    the desired way:

    .. code-block:: python

        contents = OrderedDict()
        contents["/etc/bar.conf"] = "foo\nbar\nbaz\n"
        contents["/etc/b*.conf"] = IOError(errno.EACCES, "Permission denied")
        contents["*"] = 'This is a fallback for files not beginning with "/etc/b"\n'
        fopen_mock = mock_open(read_data=contents)

Raising Exceptions
++++++++++++++++++

Instead of a string, an exception can also be used as the ``read_data``:

.. code-block:: python

    import errno

    from tests.support.mock import patch, mock_open

    import salt.modules.mymod as mymod


    def test_something():
        exc = IOError(errno.EACCES, "Permission denied")
        fopen_mock = mock_open(read_data=exc)
        with patch("salt.utils.files.fopen", fopen_mock):
            mymod.myfunc()

The above example would raise the specified exception when any file is opened.
The expectation would be that ``mymod.myfunc()`` would gracefully handle the
IOError, so a failure to do that would result in it being raised and causing
the test to fail.

Multiple File Contents
++++++++++++++++++++++

For cases in which a file is being read more than once, and it is necessary to
test a function's behavior based on what the file looks like the second (or
third, etc.) time it is read, just specify the contents for that file as a
list. Each time the file is opened, ``mock_open`` will cycle through the list
and produce a mocked filehandle with the specified contents. For example:

.. code-block:: python

    import errno
    import textwrap

    from tests.support.mock import patch, mock_open

    import salt.modules.mymod as mymod


    def test_something():
        contents = {
            "/etc/foo.conf": [
                textwrap.dedent(
                    """\
                    foo
                    bar
                    """
                ),
                textwrap.dedent(
                    """\
                    foo
                    bar
                    baz
                    """
                ),
            ],
            "/etc/b*.conf": [
                IOError(errno.ENOENT, "No such file or directory"),
                textwrap.dedent(
                    """\
                    one
                    two
                    three
                    """
                ),
            ],
        }
        fopen_mock = mock_open(read_data=contents)
        with patch("salt.utils.files.fopen", fopen_mock):
            result = mymod.myfunc()
            assert result is True

Using this example, the first time ``/etc/foo.conf`` is opened, it will
simulate a file with the first string in the list as its contents, while the
second time it is opened, the simulated file's contents will be the second
string in the list.

If no more items remain in the list, then attempting to open the file will
raise a :py:obj:`RuntimeError`. In the example above, if ``/etc/foo.conf`` were
to be opened a third time, a :py:obj:`RuntimeError` would be raised.

Note that exceptions can also be mixed in with strings when using this
technique. In the above example, if ``/etc/bar.conf`` were to be opened twice,
the first time would simulate the file not existing, while the second time
would simulate a file with string defined in the second element of the list.

.. note::
    Notice that the second path in the ``contents`` dictionary above
    (``/etc/b*.conf``) contains an asterisk. The items in the list are cycled
    through for each match of a given pattern (*not* separately for each
    individual file path), so this means that only two files matching that
    pattern could be opened before the next one would raise a
    :py:obj:`RuntimeError`.

Accessing the Mocked Filehandles in a Test
******************************************

.. note::
    The code for the ``MockOpen``, ``MockCall``, and ``MockFH`` classes
    (referenced below) can be found in ``tests/support/mock.py``. There are
    extensive unit tests for them located in ``tests/unit/test_mock.py``.

The above examples simply show how to mock ``salt.utils.files.fopen()`` to
simulate files with the contents you desire, but you can also access the mocked
filehandles (and more), and use them to craft assertions in your tests. To do
so, just add an ``as`` clause to the end of the ``patch`` statement:

.. code-block:: python

    fopen_mock = mock_open(read_data="foo\nbar\nbaz\n")
    with patch("salt.utils.files.fopen", fopen_mock) as m_open:
        # do testing here
        ...
        ...

When doing this, ``m_open`` will be a ``MockOpen`` instance. It will contain
several useful attributes:

- **read_data** - A dictionary containing the ``read_data`` passed when
  ``mock_open`` was invoked. In the event that :ref:`multiple file paths
  <unit-tests-multiple-file-paths>` are not used, then this will be a
  dictionary mapping ``*`` to the ``read_data`` passed to ``mock_open``.

- **call_count** - An integer representing how many times
  ``salt.utils.files.fopen()`` was called to open a file.

- **calls** - A list of ``MockCall`` objects. A ``MockCall`` object is a simple
  class which stores the arguments passed to it, making the positional
  arguments available via its ``args`` attribute, and the keyword arguments
  available via its ``kwargs`` attribute.

  .. code-block:: python

      from tests.support.mock import patch, mock_open, MockCall

      import salt.modules.mymod as mymod


      def test_something():

          with patch("salt.utils.files.fopen", mock_open(read_data=b"foo\n")) as m_open:
              mymod.myfunc()
              # Assert that only two opens attempted
              assert m_open.call_count == 2
              # Assert that only /etc/foo.conf was opened
              assert all(call.args[0] == "/etc/foo.conf" for call in m_open.calls)
              # Asser that the first open was for binary read, and the
              # second was for binary write.
              assert m_open.calls == [
                  MockCall("/etc/foo.conf", "rb"),
                  MockCall("/etc/foo.conf", "wb"),
              ]

  Note that ``MockCall`` is imported from ``tests.support.mock`` in the above
  example. Also, the second assert above is redundant since it is covered in
  the final assert, but both are included simply as an example.

- **filehandles** - A dictionary mapping the unique file paths opened, to lists
  of ``MockFH`` objects. Each open creates a unique ``MockFH`` object. Each
  ``MockFH`` object itself has a number of useful attributes:

  - **filename** - The path to the file which was opened using
    ``salt.utils.files.fopen()``

  - **call** - A ``MockCall`` object representing the arguments passed to
    ``salt.utils.files.fopen()``. Note that this ``MockCall`` is also available
    in the parent ``MockOpen`` instance's **calls** list.

  - The following methods are mocked using :py:class:`unittest.mock.Mock`
    objects, and Mock's built-in asserts (as well as the call data) can be used
    as you would with any other Mock object:

    - **.read()**

    - **.readlines()**

    - **.readline()**

    - **.close()**

    - **.write()**

    - **.writelines()**

    - **.seek()**

  - The read functions (**.read()**, **.readlines()**, **.readline()**) all
    work as expected, as does iterating through the file line by line (i.e.
    ``for line in fh:``).

  - The **.tell()** method is also implemented in such a way that it updates
    after each time the mocked filehandle is read, and will report the correct
    position. The one caveat here is that **.seek()** doesn't actually work
    (it's simply mocked), and will not change the position. Additionally,
    neither **.write()** or **.writelines()** will modify the mocked
    filehandle's contents.

  - The attributes **.write_calls** and **.writelines_calls** (no parenthesis)
    are available as shorthands and correspond to lists containing the contents
    passed for all calls to **.write()** and **.writelines()**, respectively.

Examples
++++++++

.. code-block:: python

    with patch("salt.utils.files.fopen", mock_open(read_data=contents)) as m_open:
        # Run the code you are unit testing
        mymod.myfunc()
        # Check that only the expected file was opened, and that it was opened
        # only once.
        assert m_open.call_count == 1
        assert list(m_open.filehandles) == ["/etc/foo.conf"]
        # "opens" will be a list of all the mocked filehandles opened
        opens = m_open.filehandles["/etc/foo.conf"]
        # Check that we wrote the expected lines ("expected" here is assumed to
        # be a list of strings)
        assert opens[0].write_calls == expected

.. code-block:: python

    with patch("salt.utils.files.fopen", mock_open(read_data=contents)) as m_open:
        # Run the code you are unit testing
        mymod.myfunc()
        # Check that .readlines() was called (remember, it's a Mock)
        m_open.filehandles["/etc/foo.conf"][0].readlines.assert_called()

.. code-block:: python

    with patch("salt.utils.files.fopen", mock_open(read_data=contents)) as m_open:
        # Run the code you are unit testing
        mymod.myfunc()
        # Check that we read the file and also wrote to it
        m_open.filehandles["/etc/foo.conf"][0].read.assert_called_once()
        m_open.filehandles["/etc/foo.conf"][1].writelines.assert_called_once()

.. _`Mock()`: https://github.com/testing-cabal/mock


Naming Conventions
------------------

Test names and docstrings should indicate what functionality is being tested.
Test functions are named ``test_<fcn>_<test-name>`` where ``<fcn>`` is the function
being tested and ``<test-name>`` describes the ``raise`` or ``return`` being tested.

Unit tests for ``salt/.../<module>.py`` are contained in a file called
``tests/pytests/unit/.../test_<module>.py``, e.g. the tests for
``salt/modules/alternatives.py``
are in ``tests/pytests/unit/modules/test_alternatives.py``.

In order for unit tests to get picked up during a run of the unit test suite, each
unit test file must be prefixed with ``test_`` and each individual test must
also be
prefixed with the ``test_`` naming syntax, as described above.

If a function does not start with ``test_``, then the function acts as a "normal"
function and is not considered a testing function. It will not be included in the
test run or testing output. The same principle applies to unit test files that
do not have the ``test_*.py`` naming syntax. This test file naming convention
is how the test runner recognizes that a test file contains tests.


Imports
-------

Most commonly, the following imports are necessary to create a unit test:

.. code-block:: python

    import pytest

If you need mock support to your tests, please also import:

.. code-block:: python

    from tests.support.mock import MagicMock, patch, call


Evaluating Truth
================

A longer discussion on the types of assertions one can make can be found by
reading `PyTest's documentation on assertions`__.

.. __: https://docs.pytest.org/en/latest/assert.html


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
'db.py'.

.. code-block:: python

    def create_user(username):
        qry = "CREATE USER {0}".format(username)
        execute_query(qry)


    def execute_query(qry):
        # Connect to a database and actually do the query...
        ...

Here, let's imagine that we want to create a unit test for the `create_user`
function. In doing so, we want to avoid any calls out to an external system and
so while we are running our unit tests, we want to replace the actual
interaction with a database with a function that can capture the parameters
sent to it and return pre-defined values. Therefore, our task is clear -- to
write a unit test which tests the functionality of `create_user` while also
replacing 'execute_query' with a mocked function.

To begin, we set up the skeleton of our test much like we did before, but with
additional imports for MagicMock:

.. code-block:: python

    from salt.modules import db
    from tests.support.mock import MagicMock, patch, call


    def test_create_user():
        """
        Test creating a user
        """
        # First, we replace 'execute_query' with our own mock function
        with patch.object(db, "execute_query", MagicMock()) as db_exq:

            # Now that the exits are blocked, we can run the function under test.
            db.create_user("testuser")

            # We could now query our mock object to see which calls were made
            # to it.
            ## print db_exq.mock_calls

            # Construct a call object that simulates the way we expected
            # execute_query to have been called.
            expected_call = call("CREATE USER testuser")

            # Compare the expected call with the list of actual calls.  The
            # test will succeed or fail depending on the output of this
            # assertion.
            db_exq.assert_has_calls(expected_call)

.. __: https://docs.python.org/3/library/unittest.mock.html


Modifying ``__salt__`` In Place
===============================

At times, it becomes necessary to make modifications to a module's view of
functions in its own ``__salt__`` dictionary.  Luckily, this process is quite
easy.

Below is an example that uses MagicMock's ``patch`` functionality to insert a
function into ``__salt__`` that's actually a MagicMock instance.

.. code-block:: python

    import pytest
    import salt.modules.my_module as my_module


    @pytest.fixture
    def configure_loader_modules():
        """
        This fixture should return a dictionary which is what's going to be used to
        patch and mock Salt's loader
        """
        return {my_module: {}}


    def show_patch(self):
        with patch.dict(my_module.__salt__, {"function.to_replace": MagicMock()}):
            # From this scope, carry on with testing, with a modified __salt__!
            ...


.. _simple-unit-example:

A Simple Example
================

Let's assume that we're testing a very basic function in an imaginary Salt
execution module. Given a module called ``fib.py`` that has a function called
``calculate(num_of_results)``, which given a ``num_of_results``, produces a list of
sequential Fibonacci numbers of that length.

A unit test to test this function might be commonly placed in a file called
``tests/pytests/unit/modules/test_fib.py``. The convention is to place unit tests for
Salt execution modules in ``test/pytests/unit/modules/`` and to name the tests module
prefixed with ``test_*.py``.

Tests are grouped around test cases, which are logically grouped sets of tests
against a piece of functionality in the tested software. To return to our example, here's how
we might write the skeleton for testing ``fib.py``:

.. code-block:: python

    import salt.modules.fib as fib


    def test_fib():
        """
        To create a unit test, we should prefix the name with `test_' so
        that it's recognized by the test runner.
        """
        fib_five = (0, 1, 1, 2, 3)
        assert fib.calculate(5) == fib_five

At this point, the test can now be run, either individually or as a part of a
full run of the test runner. To ease development, a single test can be
executed:

.. code-block:: bash

    nox -e 'test-3(coverage=False)' -- -v tests/pytests/unit/modules/test_fib.py

This will report the status of the test: success, failure, or error.  The
``-v`` flag increases output verbosity.

To review the results of a particular run, take a note of the log location
given in the output for each test run:

.. code-block:: text

   ...etc... --log-file=artifacts/logs/runtests-20210106103414.685791.log ...etc...


.. _complete-unit-example:

A More Complete Example
=======================

Consider the following function from salt/modules/linux_sysctl.py.

.. code-block:: python

    def get(name):
        """
        Return a single sysctl parameter for this minion

        CLI Example:

        .. code-block:: bash

            salt '*' sysctl.get net.ipv4.ip_forward
        """
        cmd = "sysctl -n {}".format(name)
        out = __salt__["cmd.run"](cmd, python_shell=False)
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

    import pytest
    import salt.modules.linux_sysictl as linux_sysctl
    from tests.support.mock import MagicMock, patch


    @pytest.fixture
    def configure_loader_modules():
        return {linux_sysctl: {}}


    def test_get():
        """
        Tests the return of get function
        """
        mock_cmd = MagicMock(return_value=1)
        with patch.dict(linux_sysctl.__salt__, {"cmd.run": mock_cmd}):
            assert linux_sysctl.get("net.ipv4.ip_forward") == 1


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


.. _complex-unit-example:

A Complex Example
=================

Now consider the ``assign()`` function from the same
salt/modules/linux_sysctl.py source file.

.. code-block:: python

    def assign(name, value):
        """
        Assign a single sysctl parameter for this minion

        CLI Example:

        .. code-block:: bash

            salt '*' sysctl.assign net.ipv4.ip_forward 1
        """
        value = str(value)

        tran_tab = name.translate("".maketrans("./", "/."))

        sysctl_file = "/proc/sys/{}".format(tran_tab)
        if not os.path.exists(sysctl_file):
            raise CommandExecutionError("sysctl {} does not exist".format(name))

        ret = {}
        cmd = 'sysctl -w {}="{}"'.format(name, value)
        data = __salt__["cmd.run_all"](cmd, python_shell=False)
        out = data["stdout"]
        err = data["stderr"]

        # Example:
        #    # sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"
        #    net.ipv4.tcp_rmem = 4096 87380 16777216
        regex = re.compile(r"^{}\s+=\s+{}$".format(re.escape(name), re.escape(value)))

        if not regex.match(out) or "Invalid argument" in str(err):
            if data["retcode"] != 0 and err:
                error = err
            else:
                error = out
            raise CommandExecutionError("sysctl -w failed: {}".format(error))
        new_name, new_value = out.split(" = ", 1)
        ret[new_name] = new_value
        return ret


This function contains two raise statements and one return statement, so we
know that we will need (at least) three tests.  It has two function arguments
and many references to non-builtin functions.  In the tests below you will see
that MagicMock's ``patch()`` method may be used as a context manager or as a
decorator. When patching the salt dunders however, please use the context
manager approach.

There are three test functions, one for each raise and return statement in the
source function.  Each function is self-contained and contains all and only the
mocks and data needed to test the raise or return statement it is concerned
with.

.. code-block:: python

    import pytest
    import salt.modules.linux_sysctl as linux_sysctl
    from salt.exceptions import CommandExecutionError
    from tests.support.mock import MagicMock, patch


    @pytest.fixture
    def configure_loader_modules():
        return {linux_sysctl: {}}


    def test_assign_proc_sys_failed():
        """
        Tests if /proc/sys/<kernel-subsystem> exists or not
        """
        with patch("os.path.exists", MagicMock(return_value=False)):
            cmd = {
                "pid": 1337,
                "retcode": 0,
                "stderr": "",
                "stdout": "net.ipv4.ip_forward = 1",
            }
            mock_cmd = MagicMock(return_value=cmd)
            with patch.dict(linux_sysctl.__salt__, {"cmd.run_all": mock_cmd}):
                with pytest.raises(CommandExecutionError):
                    linux_sysctl.assign("net.ipv4.ip_forward", 1)


    def test_assign_cmd_failed():
        """
        Tests if the assignment was successful or not
        """
        with patch("os.path.exists", MagicMock(return_value=True)):
            cmd = {
                "pid": 1337,
                "retcode": 0,
                "stderr": 'sysctl: setting key "net.ipv4.ip_forward": Invalid argument',
                "stdout": "net.ipv4.ip_forward = backward",
            }
            mock_cmd = MagicMock(return_value=cmd)
            with patch.dict(linux_sysctl.__salt__, {"cmd.run_all": mock_cmd}):
                with pytest.raises(CommandExecutionError):
                    linux_sysctl.assign("net.ipv4.ip_forward", "backward")


    def test_assign_success():
        """
        Tests the return of successful assign function
        """
        with patch("os.path.exists", MagicMock(return_value=True)):
            cmd = {
                "pid": 1337,
                "retcode": 0,
                "stderr": "",
                "stdout": "net.ipv4.ip_forward = 1",
            }
            ret = {"net.ipv4.ip_forward": "1"}
            mock_cmd = MagicMock(return_value=cmd)
            with patch.dict(linux_sysctl.__salt__, {"cmd.run_all": mock_cmd}):
                assert linux_sysctl.assign("net.ipv4.ip_forward", 1) == ret
