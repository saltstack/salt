.. _integration-tests:

=================
Integration Tests
=================

The Salt integration tests come with a number of classes and methods which
allow for components to be easily tested. These classes are generally inherited
from and provide specific methods for hooking into the running integration test
environment created by the integration tests.

It is noteworthy that since integration tests validate against a running
environment that they are generally the preferred means to write tests.

The integration system is all located under ``tests/integration`` in the Salt
source tree. Each directory within ``tests/integration`` corresponds to a
directory in Salt's tree structure. For example, the integration tests for the
``test.py`` Salt module that is located in ``salt/modules`` should also be
named ``test.py`` and reside in ``tests/integration/modules``.


Preparing to Write Integration Tests
====================================

This guide assumes that your Salt development environment is already configured
and that you have a basic understanding of contributing to the Salt codebase.
If you're unfamiliar with either of these topics, please refer to the
:ref:`Installing Salt for Development<installing-for-development>` and the
:ref:`Contributing<contributing>` pages, respectively.

This documentation also assumes that you have an understanding of how to
:ref:`run Salt's test suite<running-the-tests>`, including running the
:ref:`test subsections<running-test-subsections>`, and running a single
integration test file, class, or individual test.


Best Practices
==============

Integration tests should be written to the following specifications.


What to Test?
-------------

Since integration tests are used to validate against a running Salt environment,
integration tests should be written with the Salt components, and their various
interactions, in mind.

- Isolate testing functionality. Don't rely on the pass or failure of other,
  separate tests.
- Individual tests should test against a single behavior.
- Since it occasionally takes some effort to "set up" an individual test, it may
  be necessary to call several functions within a single test. However, be sure
  that once the work has been done to set up a test, make sure you are clear
  about the functionality that is being tested.


Naming Conventions
------------------

Test names and docstrings should indicate what functionality is being tested.
Test functions are named ``test_<fcn>_<test-name>`` where ``<fcn>`` is the
function being tested and ``<test-name>`` describes the behavior being tested.

In order for integration tests to get picked up during a run of the test suite,
each individual test must be prepended with the ``test_`` naming syntax, as
described above.

If a function does not start with ``test_``, then the function acts as a "normal"
function and is not considered a testing function. It will not be included in the
test run or testing output.


The setUp and tearDown Functions
--------------------------------

There are two special functions that can be utilized in the integration side of
Salt's test suite: ``setUp`` and ``tearDown``. While these functions are not
required in all test files, there are many examples in Salt's integration
test suite illustrating the broad usefulness of each function.

The ``setUp`` function is used to set up any repetitive or useful tasks that the
tests in a test class need before running. For example, any of the ``mac_*``
integration tests should only run on macOS machines. The ``setUp`` function can
be used to test for the presence of the ``Darwin`` kernel. If the ``Darwin``
kernel is not present, then the test should be skipped.

.. code-block:: python

    def setUp(self):
        '''
        Sets up test requirements
        '''
        os_grain = self.run_function('grains.item', ['kernel'])
        if os_grain['kernel'] not in 'Darwin':
            self.skipTest(
                'Test not applicable to \'{kernel}\' kernel'.format(
                    **os_grain
                )
            )

The ``setUp`` function can be used for many things. The above code snippet is
only one example. Another example might be to ensure that a particular setting
is present before running tests that would require the setting.

The ``tearDown`` function is used to clean up after any tests. This function is
useful for restoring any settings that might have been changed during the test
run.

.. note::

    The ``setUp`` and ``tearDown`` functions run before and after each test
    in the test class that the ``setUp`` and ``tearDown`` functions are defined.

Be sure to read the `Destructive vs Non-Destructive Tests`_ section when
using any kind of destructive functions that might alter the system running the
test suite in either the ``setUp`` or ``tearDown`` function definitions.


Testing Order
-------------

The test functions within a test class do not run in the order they were defined,
but instead run in lexicographical order.

Note that if any ``setUp`` or ``tearDown`` functions are defined in the class,
those functions will run before (for ``setUp``) or after (for ``tearDown``) each
test case.


Integration Classes
===================

The integration classes are located in ``tests/integration/__init__.py`` and
can be extended therein. There are four classes available to extend:

* `ModuleCase`_
* `ShellCase`_
* `SSHCase`_
* `SyndicCase`_


ModuleCase
----------

Used to define executions run via the master to minions and to call
single modules and states. The available testing functions are:

run_function
~~~~~~~~~~~~

Run a single salt function and condition the return down to match the
behavior of the raw function call. This will run the command and only
return the results from a single minion to verify.

run_state
~~~~~~~~~

Run the state.single command and return the state return structure.

minion_run
~~~~~~~~~~

Run a single salt function on the 'minion' target and condition the
return down to match the behavior of the raw function call.


ShellCase
---------

Shell out to the scripts which ship with Salt. The testing functions are:

run_cp
~~~~~~

Execute salt-cp. Pass in the argument string as it would be
passed on the command line.

run_call
~~~~~~~~

Execute salt-call, pass in the argument string as it would be
passed on the command line.

run_cloud
~~~~~~~~~

Execute the salt-cloud command. Pass in the argument string as
it would be passed on the command line.

run_key
~~~~~~~

Execute the salt-key command. Pass in the argument string as it
would be passed on the command line.

run_run
~~~~~~~

Execute the salt-run command. Pass in the argument string as it
would be passed on the command line.

run_run_plus
~~~~~~~~~~~~

Execute the runner function the and return the return data and output in a dict

run_salt
~~~~~~~~

Execute the salt command. Pass in the argument string as it would be
passed on the command line.

run_script
~~~~~~~~~~

Execute a salt script with the given argument string.

run_ssh
~~~~~~~

Execute the salt-ssh. Pass in the argument string as it would be
passed on the command line.


SSHCase
-------

Used to execute remote commands via salt-ssh. The available methods are
as follows:

run_function
~~~~~~~~~~~~

Run a single salt function via salt-ssh and condition the return down to
match the behavior of the raw function call. This will run the command
and only return the results from a single minion to verify.


SyndicCase
----------

Used to execute remote commands via a syndic and is only used to verify
the capabilities of the Salt Syndic. The available methods are as follows:

run_function
~~~~~~~~~~~~

Run a single salt function and condition the return down to match the
behavior of the raw function call. This will run the command and only
return the results from a single minion to verify.


.. _integration-class-examples:

Examples
========

The following sections define simple integration tests present in Salt's
integration test suite for each type of testing class.


Module Example via ModuleCase Class
-----------------------------------

Import the integration module, this module is already added to the python path
by the test execution. Inherit from the ``integration.ModuleCase`` class.

Now the workhorse method ``run_function`` can be used to test a module:

.. code-block:: python

    import os
    import integration


    class TestModuleTest(integration.ModuleCase):
        '''
        Validate the test module
        '''
        def test_ping(self):
            '''
            test.ping
            '''
            self.assertTrue(self.run_function('test.ping'))

        def test_echo(self):
            '''
            test.echo
            '''
            self.assertEqual(self.run_function('test.echo', ['text']), 'text')

The fist example illustrates the testing master issuing a ``test.ping`` call
to a testing minion. The test asserts that the minion returned with a ``True``
value to the master from the ``test.ping`` call.

The second example similarly verifies that the minion executed the
``test.echo`` command with the ``text`` argument. The ``assertEqual`` call
maintains that the minion ran the function and returned the data as expected
to the master.


Shell Example via ShellCase
---------------------------

Validating the shell commands can be done via shell tests:

.. code-block:: python

    import sys
    import shutil
    import tempfile

    import integration

    class KeyTest(integration.ShellCase):
        '''
        Test salt-key script
        '''

        _call_binary_ = 'salt-key'

        def test_list(self):
            '''
            test salt-key -L
            '''
            data = self.run_key('-L')
            expect = [
                    'Unaccepted Keys:',
                    'Accepted Keys:',
                    'minion',
                    'sub_minion',
                    'Rejected:', '']
            self.assertEqual(data, expect)

This example verifies that the ``salt-key`` command executes and returns as
expected by making use of the ``run_key`` method.


SSH Example via SSHCase
-----------------------

Testing salt-ssh functionality can be done using the SSHCase test class:

.. code-block:: python

    import integration

    class SSHGrainsTest(integration.SSHCase):
    '''
    Test salt-ssh grains functionality
    Depend on proper environment set by integration.SSHCase class
    '''

    def test_grains_id(self):
        '''
        Test salt-ssh grains id work for localhost.
        '''
        cmd = self.run_function('grains.get', ['id'])
        self.assertEqual(cmd, 'localhost')


Testing Event System via SaltMinionEventAssertsMixin
----------------------------------------------------

The fundamentially asynchronous nature of Salt makes testing the event system a challenge.
The ``SaltMinionEventAssertsMixin`` provides a facility for testing that events were received
on a minion event bus.

.. code-block:: python

    import integration

    class TestEvent(integration.SaltEventAssertsMixin):
        '''
        Example test of firing an event and receiving it
        '''

        def test_event(self):
            e = salt.utils.event.get_event('minion', sock_dir=self.minion_opts['sock_dir'], opts=self.minion_opts)

            e.fire_event({'a': 'b'}, '/test_event')

            self.assertMinionEventReceived({'a': 'b'})


Syndic Example via SyndicCase
-----------------------------

Testing Salt's Syndic can be done via the SyndicCase test class:

.. code-block:: python

    import integration

    class TestSyndic(integration.SyndicCase):
        '''
        Validate the syndic interface by testing the test module
        '''
        def test_ping(self):
            '''
            test.ping
            '''
            self.assertTrue(self.run_function('test.ping'))

This example verifies that a ``test.ping`` command is issued from the testing
master, is passed through to the testing syndic, down to the minion, and back
up again by using the ``run_function`` located with in the ``SyndicCase`` test
class.


Integration Test Files
======================

Since using Salt largely involves configuring states, editing files, and changing
system data, the integration test suite contains a directory named ``files`` to
aid in testing functions that require files. Various Salt integration tests use
these example files to test against instead of altering system files and data.

Each directory within ``tests/integration/files`` contain files that accomplish
different tasks, based on the needs of the integration tests using those files.
For example, ``tests/integration/files/ssh`` is used to bootstrap the test runner
for salt-ssh testing, while ``tests/integration/files/pillar`` contains files
storing data needed to test various pillar functions.

The ``tests/integration/files`` directory also includes an integration state tree.
The integration state tree can be found at ``tests/integration/files/file/base``.

The following example demonstrates how integration files can be used with ModuleCase
to test states:

.. code-block:: python

    # Import python libs
    from __future__ import absolute_import
    import os
    import shutil

    # Import Salt Testing libs
    from salttesting.helpers import ensure_in_syspath
    ensure_in_syspath('../../')

    # Import salt libs
    import integration
    import salt.utils

    HFILE = os.path.join(integration.TMP, 'hosts')


    class HostTest(integration.ModuleCase, integration.SaltReturnAssertsMixIn):
        '''
        Validate the host state
        '''

        def setUp(self):
            shutil.copyfile(os.path.join(integration.FILES, 'hosts'), HFILE)
            super(HostTest, self).setUp()

        def tearDown(self):
            if os.path.exists(HFILE):
                os.remove(HFILE)
            super(HostTest, self).tearDown()

        def test_present(self):
            '''
            host.present
            '''
            name = 'spam.bacon'
            ip = '10.10.10.10'
            ret = self.run_state('host.present', name=name, ip=ip)
            self.assertSaltTrueReturn(ret)
            with salt.utils.fopen(HFILE) as fp_:
                output = fp_.read()
                self.assertIn('{0}\t\t{1}'.format(ip, name), output)

To access the integration files, a variable named ``integration.FILES``
points to the ``tests/integration/files`` directory. This is where the referenced
``host.present`` sls file resides.

In addition to the static files in the integration state tree, the location
``integration.TMP`` can also be used to store temporary files that the test system
will clean up when the execution finishes.


Destructive vs Non-Destructive Tests
====================================

Since Salt is used to change the settings and behavior of systems, one testing
approach is to run tests that make actual changes to the underlying system. This
is where the concept of destructive integration tests comes into play. Tests can
be written to alter the system they are running on. This capability is what fills
in the gap needed to properly test aspects of system management like package
installation.

Any test that changes the underlying system in any way, such as creating or
deleting users, installing packages, or changing permissions should include the
``@destructive`` decorator to signal system changes and should be written with
care. System changes executed within a destructive test should also be restored
once the related tests have completed. For example, if a new user is created to
test a module, the same user should be removed after the test is completed to
maintain system integrity.

To write a destructive test, import, and use the destructiveTest decorator for
the test method:

.. code-block:: python

    import integration
    from salttesting.helpers import destructiveTest

    class DestructiveExampleModuleTest(integration.ModuleCase):
        '''
        Demonstrate a destructive test
        '''

        @destructiveTest
        @skipIf(os.geteuid() != 0, 'you must be root to run this test')
        def test_user_not_present(self):
            '''
            This is a DESTRUCTIVE TEST it creates a new user on the minion.
            And then destroys that user.
            '''
            ret = self.run_state('user.present', name='salt_test')
            self.assertSaltTrueReturn(ret)
            ret = self.run_state('user.absent', name='salt_test')
            self.assertSaltTrueReturn(ret)


Cloud Provider Tests
====================

Cloud provider integration tests are used to assess :ref:`Salt-Cloud<salt-cloud>`'s
ability to create and destroy cloud instances for various supported cloud providers.
Cloud provider tests inherit from the ShellCase Integration Class.

Any new cloud provider test files should be added to the ``tests/integration/cloud/providers/``
directory. Each cloud provider test file also requires a sample cloud profile and cloud
provider configuration file in the integration test file directory located at
``tests/integration/files/conf/cloud.*.d/``.

The following is an example of the default profile configuration file for Digital
Ocean, located at: ``tests/integration/files/conf/cloud.profiles.d/digital_ocean.conf``:

.. code-block:: yaml

    digitalocean-test:
      provider: digitalocean-config
      image: Ubuntu 14.04 x64
      size: 512MB

Each cloud provider requires different configuration credentials. Therefore, sensitive
information such as API keys or passwords should be omitted from the cloud provider
configuration file and replaced with an empty string. The necessary credentials can
be provided by the user by editing the provider configuration file before running the
tests.

The following is an example of the default provider configuration file for Digital
Ocean, located at: ``tests/integration/files/conf/cloud.providers.d/digital_ocean.conf``:

.. code-block:: yaml

    digitalocean-config:
      driver: digital_ocean
      client_key: ''
      api_key: ''
      location: New York 1

In addition to providing the necessary cloud profile and provider files in the integration
test suite file structure, appropriate checks for if the configuration files exist and
contain valid information are also required in the test class's ``setUp`` function:

.. code-block:: python

    class LinodeTest(integration.ShellCase):
    '''
    Integration tests for the Linode cloud provider in Salt-Cloud
    '''

    def setUp(self):
        '''
        Sets up the test requirements
        '''
        super(LinodeTest, self).setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = 'linode-config:'
        provider = 'linode'
        providers = self.run_cloud('--list-providers')
        if profile_str not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                .format(provider)
            )

        # check if apikey and password are present
        path = os.path.join(integration.FILES,
                            'conf',
                            'cloud.providers.d',
                            provider + '.conf')
        config = cloud_providers_config(path)
        api = config['linode-config']['linode']['apikey']
        password = config['linode-config']['linode']['password']
        if api == '' or password == '':
            self.skipTest(
                'An api key and password must be provided to run these tests. Check '
                'tests/integration/files/conf/cloud.providers.d/{0}.conf'.format(
                    provider
                )
            )

Repeatedly creating and destroying instances on cloud providers can be costly.
Therefore, cloud provider tests are off by default and do not run automatically. To
run the cloud provider tests, the ``--cloud-provider-tests`` flag must be provided:

.. code-block:: bash

    ./tests/runtests.py --cloud-provider-tests

Since cloud provider tests do not run automatically, all provider tests must be
preceded with the ``@expensiveTest`` decorator. The expensive test decorator is
necessary because it signals to the test suite that the
``--cloud-provider-tests`` flag is required to run the cloud provider tests.

To write a cloud provider test, import, and use the expensiveTest decorator for
the test function:

.. code-block:: python

    from salttesting.helpers import expensiveTest

    @expensiveTest
    def test_instance(self):
        '''
        Test creating an instance on Linode
        '''
        name = 'linode-testing'

        # create the instance
        instance = self.run_cloud('-p linode-test {0}'.format(name))
        str = '        {0}'.format(name)

        # check if instance with salt installed returned as expected
        try:
            self.assertIn(str, instance)
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(name))
            raise

        # delete the instance
        delete = self.run_cloud('-d {0} --assume-yes'.format(name))
        str = '            True'
        try:
            self.assertIn(str, delete)
        except AssertionError:
            raise


Adding New Directories
======================

If the corresponding Salt directory does not exist within
``tests/integration``, the new directory must be created along with the
appropriate test file to maintain Salt's testing directory structure.

In order for Salt's test suite to recognize tests within the newly
created directory, options to run the new integration tests must be added to
``tests/runtests.py``. Examples of the necessary options that must be added
can be found here: :blob:`tests/runtests.py`. The functions that need to be
edited are ``setup_additional_options``, ``validate_options``, and
``run_integration_tests``.
