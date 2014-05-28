=================
Running The Tests
=================

There are requirements, in addition to Salt's requirements, which
need to be installed in order to run the test suite. Install one of
the lines below, depending on the relevant Python version:

.. code-block:: bash

    pip install -r dev_requirements_python26.txt
    pip install -r dev_requirements_python27.txt

.. note::

    In Salt 0.17, testing libraries were migrated into their own repo. To install them:

    .. code-block:: bash

        pip install git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting


    Failure to install SaltTesting will result in import errors similar to the following:

    .. code-block:: bash

        ImportError: No module named salttesting

Once all require requirements are set, use ``tests/runtests.py`` to
run all of the tests included in Salt's test suite. For more information,
see ``--help``.

An alternative way of invoking the test suite is available in ``setup.py``:

.. code-block:: bash

    ./setup.py test

Instead of running the entire test suite, there are several ways to run only
specific groups of tests or individual tests:

* Run unit tests only: ``./tests/runtests.py --unit-tests``
* Run unit and integration tests for states: ``./tests/runtests.py --state``
* Run integration tests for an individual module: ``./tests/runtests.py -n integration.modules.virt -vv``
* Run unit tests for an individual module: ``./tests/runtests.py -n unit.modules.virt_test -vv``


Running Destructive Integration Tests
=====================================

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

    Running destructive tests will change the underlying system. Use caution when running destructive tests.

To run tests marked as destructive, set the ``--run-destructive`` flag:

.. code-block:: bash

    ./tests/runtests.py --run-destructive


Running The Tests In A Docker Container
=======================================

The test suite can be executed under a `docker`_ container using the
``--docked`` option flag. The `docker`_ container must be properly configured
on the system invoking the tests and the container must have access to the
internet.

Here's a simple usage example:

.. code-block:: bash

    tests/runtests.py --docked=ubuntu-12.04 -v

The full `docker`_ container repository can also be provided:

.. code-block:: bash

    tests/runtests.py --docked=salttest/ubuntu-12.04 -v


The SaltStack team is creating some containers which will have the necessary
dependencies pre-installed. Running the test suite on a container allows
destructive tests to run without making changes to the main system. It also
enables the test suite to run under a different distribution than the one
the main system is currently using.

The current list of test suite images is on Salt's `docker repository`_.

Custom `docker`_ containers can be provided by submitting a pull request
against Salt's `docker Salt test containers`_ repository.

.. _`docker`: https://www.docker.io/
.. _`docker repository`: https://index.docker.io/u/salttest/
.. _`docker Salt test containers`: https://github.com/saltstack/docker-containers


===================
Automated Test Runs
===================

SaltStack maintains a Jenkins server to allow for the execution of tests
across supported platforms. The tests executed from Salt's Jenkins server
create fresh virtual machines for each test run, then execute destructive
tests on the new, clean virtual machine.

When a pull request is submitted to Salt's repository on GitHub, Jenkins
runs Salt's test suite on a couple of virtual machines to gauge the pull
request's viability to merge into Salt's develop branch. If these initial
tests pass, the pull request can then merged into Salt's develop branch
by one of Salt's core developers, pending their discretion. If the initial
tests fail, core developers may request changes to the pull request. If the
failure is unrelated to the changes in question, core developers may merge
the pull request despite the initial failure.

Once the pull request is merged into Salt's develop branch, a new set of
Jenkins virtual machines will begin executing the test suite. The develop
branch tests have many more virtual machines to provide more comprehensive
results.

There are a few other groups of virtual machines that Jenkins tests against,
including past and current release branches. For a full list of currently
running test environments, go to http://jenkins.saltstack.com.


Using Salt-Cloud on Jenkins
===========================

For testing Salt on Jenkins, SaltStack uses :ref:`Salt-Cloud<salt-cloud>` to
spin up virtual machines. The script using Salt-Cloud to accomplish this is
open source and can be found here: :blob:`tests/jenkins.py`


=============
Writing Tests
=============

Salt uses a test platform to verify functionality of components in a simple
way. Two testing systems exist to enable testing salt functions in somewhat
real environments. The two subsystems available are integration tests and
unit tests.

Salt uses the python standard library unittest2 system for testing.

Naming Conventions
==================

Any function in either integration test files or unit test files that is
doing the actual testing, such as functions containing assertions, must
start with ``test_``:

.. code-block:: python

    def test_user_present(self):

When functions in test files are not prepended with ``test_``,
the function acts as a normal, helper function and is not run as a test
by the test suite.

Integration Tests
=================

The integration tests start up a number of salt daemons to test functionality
in a live environment. These daemons include 2 salt masters, 1 syndic, and 2
minions. This allows the syndic interface to be tested and master/minion
communication to be verified. All of the integration tests are executed as
live salt commands sent through the started daemons.

Integration tests are particularly good at testing modules, states and shell
commands.

* :doc:`Writing integration tests <integration>`

Unit Tests
==========

Direct unit tests are also available. These tests are good for testing internal
functions.

* :doc:`Writing unit tests <unit>`


.. toctree::
    :hidden:

    integration
    unit
