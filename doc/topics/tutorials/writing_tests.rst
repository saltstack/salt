==================
Writing Salt Tests
==================

.. note::

    THIS TUTORIAL IS A WORK IN PROGRESS

Salt comes with a powerful integration and unit test suite. The test suite
allows for the fully automated run of integration and/or unit tests from a
single interface. The integration tests are surprisingly easy to write and can
be written to be either destructive or non-destructive.

Getting Set Up For Tests
========================

To walk through adding an integration test, start by getting the latest
development code and the test system from GitHub:

.. note::

    The develop branch often has failing tests and should always be considered
    a staging area. For a checkout that tests should be running perfectly on,
    please check out a specific release tag (such as v2014.1.4).

.. code-block:: bash

    git clone git@github.com:saltstack/salt.git
    pip install git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting

Now that a fresh checkout is available run the test suite

Destructive vs Non-destructive
==============================

Since Salt is used to change the settings and behavior of systems, often, the
best approach to run tests is to make actual changes to an underlying system.
This is where the concept of destructive integration tests comes into play.
Tests can be written to alter the system they are running on. This capability
is what fills in the gap needed to properly test aspects of system management
like package installation.

To write a destructive test import and use the `destructiveTest` decorator for
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

Automated Test Runs
===================

SaltStack maintains a Jenkins server which can be viewed at
http://jenkins.saltstack.com. The tests executed from this Jenkins server
create fresh virtual machines for each test run, then execute the destructive
tests on the new clean virtual machine. This allows for the execution of tests
across supported platforms.