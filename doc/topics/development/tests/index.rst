.. _salt-test-suite:

=================
Salt's Test Suite
=================

Salt comes with a powerful integration and unit test suite allowing for
the fully automated run of integration and/or unit tests from a single
interface. It uses the combination of pytest, nox and `Kitchen Salt`_ to
run these tests. Nox is used to manage all of the test python dependencies.
When you run the test runner with nox, you will be installing the same
python dependencies that we use to run our test suite on PRs and branch tests.
`Kitchen Salt`_ is used to spin up our virtual machines based off of golden
images. These virtual machines use the `salt-jenkins`_ sls states to configure
any system dependencies.

To learn the basics of how Salt's test suite works, be sure to check
out the :ref:`Salt's Test Suite: An Introduction <tutorial-salt-testing>`
tutorial.

Nox
===
Nox is used to manage all of the python dependencies used in the test suite
and spins up the different nox sessions. You can look at the ``noxfile.py``
in the salt repo to view all of the current nox configurations. In that file
you will notice various nox sessions. When creating each of these sessions,
nox will create a virtualenv with the specified interpreter. Once the virtualenv
is created it will also install all of the required python dependencies
required for that session and run the tests.

For example if you want to run all of the tests using the zeromq transport on
python3 you would need to specify the zeromq transport and python3.

.. code-block:: bash

    nox -e 'test-zeromq-3(coverage=False)'

And because zeromq is the default transport, the following nox session can also be used:

.. code-block:: bash

    nox -e 'test-zeromq-3(coverage=False)'


To run all the tests but on the tcp transport, you would need to specify the tcp session.

.. code-block:: bash

    nox -e 'test-tcp-3(coverage=False)'

As a contrast, when using the deprecated ``runtests.py`` test runner, the
command would be:

.. code-block:: bash

    nox -e 'runtests-tcp-3(coverage=False)'

You can view all available sessions by running:

.. code-block:: bash

    nox --list-sessions

For the most part you will only need nox to run the test suite, as this tool
will install the exact same python dependencies we use to run on our test runs.
The exception to this is when a system dependency is required, for example ``mysql``.
These system dependencies are installed with sls states managed in the `salt-jenkins`_
repo or you can manually install the dependency yourself.

System Dependencies
===================
The system dependencies are installed from the `salt-jenkins`_ repo. The
``golden-images-provision`` state is what is run to determine what dependencies
to install on which platform.
We run this state only when we want to update our current VM images with new
dependencies.

Kitchen Salt
============
We also use `Kitchen Salt`_ to spin up the VM's used for testing. You can view the
kitchen-salt `getting started`_ for instructions on how to install and set it up.
`Kitchen Salt`_ uses Test Kitchen to spin up the VM or container in the configured
provider. Once the VM is spun up, `Kitchen Salt`_ can install salt and run a particular
set of states. In the case of our branch and PR tests we create "Golden Images" which
run the `salt-jenkins`_ states and install salt system dependencies beforehand. We only
update these "Golden Images" when we need to upgrade or install a system dependency. You can
view the `kitchen-salt jenkins setup`_ docs for instructions on how to set up `Kitchen Salt`_
similar to the jenkins environment we use to run branch and PR tests.

Test Directory Structure
========================

Salt's test suite is located in the ``tests/`` directory in the root of
Salt's codebase.

With the migration to PyTest, Salt has created a separate directory for tests
that are written taking advantage of the full potential of PyTest. These are
located under ``tests/pytests``.

As for the old test suite, it is divided into two main groups:

* :ref:`Integration Tests <integration-tests>`
* :ref:`Unit Tests <unit-tests>`

Within each of these groups, the directory structure roughly mirrors the
structure of Salt's own codebase. Notice that there are directories for
``states``, ``modules``, ``runners``, ``output``, and more in each testing
group.

The files that are housed in the ``modules`` directory of either the unit
or the integration testing factions contain respective integration or unit
test files for Salt execution modules.

The PyTest only tests under ``tests/pytests`` should, more or less, follow the
same grouping as the old test suite.


Integration Tests
-----------------

The Integration section of Salt's test suite start up a number of Salt
daemons to test functionality in a live environment. These daemons
include two Salt Masters, one Syndic, and two Minions. This allows the
Syndic interface to be tested and Master/Minion communication to be
verified. All of the integration tests are executed as live Salt commands
sent through the started daemons.

Integration tests are particularly good at testing modules, states, and
shell commands, among other segments of Salt's ecosystem. By utilizing
the integration test daemons, integration tests are easy to write. They
are also SaltStack's generally preferred method of adding new tests.

The discussion in the :ref:`Integration vs. Unit <integration-vs-unit>`
section of the :ref:`testing tutorial <tutorial-salt-testing>` is
beneficial in learning why you might want to write integration tests
vs. unit tests. Both testing arenas add value to Salt's test suite and
you should consider adding both types of tests if possible and appropriate
when contributing to Salt.

* :ref:`Integration Test Documentation <integration-tests>`


Unit Tests
----------

Unit tests do not spin up any Salt daemons, but instead find their value
in testing singular implementations of individual functions. Instead of
testing against specific interactions, unit tests should be used to test
a function's logic as well as any ``return`` or ``raises`` statements.
Unit tests also rely heavily on mocking external resources.

The discussion in the :ref:`Integration vs. Unit <integration-vs-unit>`
section of the :ref:`testing tutorial <tutorial-salt-testing>` is useful
in determining when you should consider writing unit tests instead of,
or in addition to, integration tests when contributing to Salt.

* :ref:`Unit Test Documentation <unit-tests>`


.. _running-the-tests:

Running The Tests
=================

There is only one requirement to install, to quickly get started
running salt's test suite: ``nox``.

.. code-block:: bash

    pip install nox

Once this requirement is installed, you can use the ``nox`` binary to run
all of the tests included in Salt's test suite:

.. code-block:: bash

    nox -e 'test-3(coverage=False)'

For more information about options you can pass the test runner, see the
``--help`` option:

.. code-block:: bash

    nox -e 'test-3(coverage=False)' -- --help

.. _running-test-subsections:

Running Test Subsections
------------------------

Instead of running the entire test suite all at once, which can take a long time,
there are several ways to run only specific groups of tests or individual tests:

* Run :ref:`unit tests only<running-unit-tests-no-daemons>`: ``nox -e
  'test-3(coverage=False)' -- tests/unit/``.
* Run unit and integration tests for states: ``nox -e
  'test-3(coverage=False)' -- tests/unit/states/ tests/integration/states/``.
* Run integration tests for an individual module: ``nox -e 'test-3(coverage=False)' --
  tests/pytests/integration/modules/test_virt.py``.
* Run unit tests for an individual module: ``nox -e 'test-3(coverage=False)' --
  tests/unit/modules/test_virt.py``.
* Run an individual test by using the class and test name (this example is for the
  ``test_default_kvm_profile`` test in the ``tests/pytests/integration/module/test_virt.py``):
  ``nox -e 'test-3(coverage=False)' --
  tests/pytests/integration/modules/test_virt.py::VirtTest::test_default_kvm_profile``.


For more specific examples of how to run various test subsections or individual
tests, please see the `pytest`_ documentation on how to run specific tests or
the :ref:`Running Specific Tests <running-specific-tests>`
section of the :ref:`Salt's Test Suite: An Introduction <tutorial-salt-testing>`
tutorial.


.. _running-unit-tests-no-daemons:

Running Unit Tests Without Integration Test Daemons
---------------------------------------------------

Since the unit tests do not require a master or minion to execute, it is often useful to be able to
run unit tests individually, or as a whole group, without having to start up the integration testing
daemons. Starting up the master, minion, and syndic daemons takes a lot of time before the tests can
even start running and is unnecessary to run unit tests. To run unit tests without invoking the
integration test daemons, simply add the unit directory as an argument:

.. code-block:: bash

    nox -e 'test-3(coverage=False)' -- tests/unit/

All of the other options to run individual tests, entire classes of tests, or
entire test modules still apply.


Running Destructive Integration Tests
-------------------------------------

Salt is used to change the settings and behavior of systems. In order to
effectively test Salt's functionality, some integration tests are written to
make actual changes to the underlying system. These tests are referred to as
"destructive tests". Some examples of destructive tests are changes may be
testing the addition of a user or installing packages. By default,
destructive tests are disabled and will be skipped.

Generally, destructive tests should clean up after themselves by attempting to
restore the system to its original state. For instance, if a new user is created
during a test, the user should be deleted after the related test(s) have
completed. However, no guarantees are made that test clean-up will complete
successfully. Therefore, running destructive tests should be done with caution.

.. note::

    Running destructive tests will change the underlying system.
    Use caution when running destructive tests.

To run tests marked as destructive, set the ``--run-destructive`` flag:

.. code-block:: bash

    nox -e 'test-3(coverage=False)' -- --run-destructive


Running Cloud Provider Tests
----------------------------

Salt's testing suite also includes integration tests to assess the successful
creation and deletion of cloud instances using :ref:`Salt-Cloud<salt-cloud>` for
providers supported by Salt-Cloud.

The cloud provider tests are off by default and run on sample configuration files
provided in ``tests/integration/files/conf/cloud.providers.d/``. In order to run
the cloud provider tests, valid credentials, which differ per provider, must be
supplied. Each credential item that must be supplied is indicated by an empty
string value and should be edited by the user before running the tests. For
example, DigitalOcean requires a client key and an api key to operate. Therefore,
the default cloud provider configuration file for DigitalOcean looks like this:

.. code-block:: yaml

    digitalocean-config:
      driver: digitalocean
      client_key: ''
      api_key: ''
      location: New York 1

As indicated by the empty string values, the ``client_key`` and the ``api_key``
must be provided:

.. code-block:: yaml

    digitalocean-config:
      driver: digitalocean
      client_key: wFGEwgregeqw3435gDger
      api_key: GDE43t43REGTrkilg43934t34qT43t4dgegerGEgg
      location: New York 1

.. note::

    When providing credential information in cloud provider configuration files,
    do not include the single quotes.

Once all of the valid credentials for the cloud provider have been supplied, the
cloud provider tests can be run like:

.. code-block:: bash

    nox -e 'test-cloud-3(coverage=False)'


Automated Test Runs
===================

SaltStack maintains a Jenkins server to allow for the execution of tests
across supported platforms. The tests executed from Salt's Jenkins server
create fresh virtual machines for each test run, then execute destructive
tests on the new, clean virtual machine.

SaltStack's Jenkins server continuously runs the entire test suite,
including destructive tests, on an array of various supported operating
systems throughout the day. Each actively supported branch of Salt's
repository runs the tests located in the respective branch's code. Each set
of branch tests also includes a pylint run. These branch tests help ensure
the viability of Salt code at any given point in time as pull requests
are merged into branches throughout the day.

In addition to branch tests, SaltStack's Jenkins server also runs tests
on pull requests. These pull request tests include a smaller set of
virtual machines that run on the branch tests. The pull request tests,
like the branch tests, include a pylint test as well.

When a pull request is submitted to Salt's repository on GitHub, the suite
of pull request tests are started by Jenkins. These tests are used to
gauge the pull request's viability to merge into Salt's codebase. If these
initial tests pass, the pull request can then merged into the Salt branch
by one of Salt's core developers, pending their discretion. If the initial
tests fail, core developers may request changes to the pull request. If the
failure is unrelated to the changes in question, core developers may merge
the pull request despite the initial failure.

As soon as the pull request is merged, the changes will be added to the
next branch test run on Jenkins.

For a full list of currently running test environments, go to
https://jenkins.saltproject.io.


Using Salt-Cloud on Jenkins
---------------------------

For testing Salt on Jenkins, SaltStack uses :ref:`Salt-Cloud<salt-cloud>` to
spin up virtual machines. The script using Salt-Cloud to accomplish this is
open source and can be found here: :blob:`tests/jenkins.py`


Writing Tests
=============

The salt testing infrastructure is divided into two classes of tests,
integration tests and unit tests. These terms may be defined differently in
other contexts, but for Salt they are defined this way:

- Unit Test: Tests which validate isolated code blocks and do not require
  external interfaces such as ``salt-call`` or any of the salt daemons.

- Integration Test: Tests which validate externally accessible features.

Salt testing uses unittest2 from the python standard library and MagicMock.

* :ref:`Writing integration tests <integration-tests>`
* :ref:`Writing unit tests <unit-tests>`


Naming Conventions
------------------

Any function in either integration test files or unit test files that is doing
the actual testing, such as functions containing assertions, must start with
``test_``:

.. code-block:: python

    def test_user_present(self):
        ...

When functions in test files are not prepended with ``test_``, the function
acts as a normal, helper function and is not run as a test by the test suite.


Submitting New Tests
--------------------

Which branch of the Salt codebase should new tests be written against? The location
of where new tests should be submitted depends largely on the reason you're writing
the tests.


Tests for New Features
~~~~~~~~~~~~~~~~~~~~~~

If you are adding new functionality to Salt, please write the tests for this new
feature in the same pull request as the new feature. New features should always be
submitted to the ``|repo_primary_branch|`` branch.

If you have already submitted the new feature, but did not write tests in the original
pull request that has already been merged, please feel free to submit a new pull
request containing tests. If the feature was recently added to Salt's ``|repo_primary_branch|``
branch, then the tests should be added there as well. However, if the feature was
added to ``|repo_primary_branch|`` some time ago and is already present in one or more release
branches, please refer to the `Tests for Entire Files or Functions`_ section below
for more details about where to submit tests for functions or files that do not
already have tests.


Tests to Accompany a Bugfix
~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are writing tests for code that fixes a bug in Salt, tests will be
required before merging the PR. A great option for most bugfixes is to adopt a
TDD style approach:

- reproduce the issue
- write a test that exhibits the behavior
- write the bugfix

This helps ensure that known issues are not reintroduced into the codebase.

Tests for Entire Files or Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sometimes entire files in Salt are completely untested. If you are writing tests for
a file that doesn't have any tests written for it, write your test against the
earliest supported release branch that contains the file or function you're testing.

Once your tests are submitted in a pull request and is merged into the branch in
question, the tests you wrote will be merged-forward by SaltStack core engineers and
the new tests will propagate to the newer release branches. That way the tests you
wrote will apply to all current and relevant release branches, and not just the ``|repo_primary_branch|``
branch, for example. This methodology will help protect against regressions on older
files in Salt's codebase.

There may be times when the tests you write against an older branch fail in the
merge-forward process because functionality has changed in newer release branches.
In these cases, a Salt core developer may reach out to you for advice on the tests in
question if the path forward is unclear.

.. note::

    If tests are written against a file in an older release branch and then merged forward,
    there may be new functionality in the file that is present in the new release branch
    that is untested.It would be wise to see if new functionality could use additional
    testing once the test file has propagated to newer release branches.

Module/Global Level Variables
-----------------------------

If you need access to module or global level variables, please use a pytest fixture. The
use of module and global variables can introduce mutable global objects and increases
processing time because all globals are evaluated when collecting tests. If there is a use
case where you cannot use a fixture and you are using a type of string, integer, or tuple
you can use global/module level variables. Any mutable types such as lists and dictionaries must
use pytest fixtures. For an example, if all of your tests need access to a string variable:

.. code-block:: python

    FOO = "bar"


    def test_foo_bar():
        assert FOO == "bar"


    def test_foo_not():
        assert not FOO == "foo"

We recommend using a pytest fixture:

.. code-block:: python

    import pytest


    @pytest.fixture()
    def foo():
        return "bar"


    def test_foo_bar(foo):
        assert foo == "bar"


    def test_foo_not(foo):
        assert not foo == "foo"


If you need a class to mock something, it can be defined at the global scope,
but it should only be initialized on the fixture:

.. code-block:: python

    class Foo:
        def __init__(self):
            self.bar = True


    @pytest.fixture
    def foo():
        return Foo()

Test Helpers
------------

Several Salt-specific helpers are available. A full list is available by inspecting
functions exported under `tests/support/*.py`.

Test Markers
------------

`@pytest.mark.expensive_test` -- Designates a test which typically requires a
relatively costly external resource, like a cloud virtual machine. This decorator
is not normally used by developers outside of the Salt core team.

`@pytest.mark.destructive_test` -- Marks a test as potentially destructive. It
will not be run unless the ``--run-destructive`` flag is expressly passed.

`@pytest.mark.requires_network` -- Requires a network connection for the test to
operate successfully. If a network connection is not detected, the test will not run.

These are just a small preview of the supported marker. For a full listing, please
run:

.. code-block:: bash

    nox -e 'test-3(coverage=False)' -- --markers


.. _kitchen-salt jenkins setup: https://kitchen.saltproject.io/docs/file/docs/jenkins.md
.. _getting started: https://kitchen.saltproject.io/docs/file/docs/gettingstarted.md
.. _salt-jenkins: https://github.com/saltstack/salt-jenkins
.. _Kitchen Salt: https://kitchen.saltproject.io/
.. _pytest: https://docs.pytest.org/en/latest/usage.html#specifying-tests-selecting-tests
