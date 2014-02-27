=================
Integration Tests
=================

The Salt integration tests come with a number of classes and methods which
allow for components to be easily tested. These classes are generally inherited
from and provide specific methods for hooking into the running integration test
environment created by the integration tests.

It is noteworthy that since integration tests validate against a running
environment that they are generally the preferred means to write tests.

The integration system is all located under tests/integration in the Salt
source tree.

Integration Classes
===================

The integration classes are located in tests/integration/__init__.py and
can be extended therein. There are three classes available to extend:

ModuleCase
----------

Used to define executions run via the master to minions and to call
single modules and states.

The available methods are as follows:

run_function:
    Run a single salt function and condition the return down to match the
    behavior of the raw function call. This will run the command and only
    return the results from a single minion to verify.

state_result:
    Return the result data from a single state return

run_state:
    Run the state.single command and return the state return structure




SyndicCase
----------

Used to execute remote commands via a syndic, only used to verify the
capabilities of the Syndic.

The available methods are as follows:

run_function:
    Run a single salt function and condition the return down to match the
    behavior of the raw function call. This will run the command and only
    return the results from a single minion to verify.

ShellCase
---------

Shell out to the scripts which ship with Salt.

The available methods are as follows:

run_script:
    Execute a salt script with the given argument string

run_salt:
    Execute the salt command, pass in the argument string as it would be
    passed on the command line.

run_run:
    Execute the salt-run command, pass in the argument string as it would be
    passed on the command line.

run_run_plus:
    Execute Salt run and the salt run function and return the data from
    each in a dict

run_key:
    Execute the salt-key command, pass in the argument string as it would be
    passed on the command line.

run_cp:
    Execute salt-cp, pass in the argument string as it would be
    passed on the command line.

run_call:
    Execute salt-call, pass in the argument string as it would be
    passed on the command line.


Examples
========

Module Example via ModuleCase Class
-----------------------------------

Import the integration module, this module is already added to the python path
by the test execution. Inherit from the ``integration.ModuleCase`` class. The
tests that execute against salt modules should be placed in the
`tests/integration/modules` directory so that they will be detected by the test
system.

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

ModuleCase can also be used to test states, when testing states place the test
module in the `tests/integration/states` directory. The ``state_result`` and
the ``run_state`` methods are the workhorse here:

.. code-block:: python

    import os
    import shutil
    import integration

    HFILE = os.path.join(integration.TMP, 'hosts')

    class HostTest(integration.ModuleCase):
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
            result = self.state_result(ret)
            self.assertTrue(result)
            with open(HFILE) as fp_:
                output = fp_.read()
                self.assertIn('{0}\t\t{1}'.format(ip, name), output)

The above example also demonstrates using the integration files and the
integration state tree. The variable `integration.FILES` will point to the
directory used to store files that can be used or added to to help enable tests
that require files. The location `integration.TMP` can also be used to store
temporary files that the test system will clean up when the execution finishes.

The integration state tree can be found at `tests/integration/files/file/base`.
This is where the referenced `host.present` sls file resides.

Shell Example via ShellCase
---------------------------

Validating the shell commands can be done via shell tests. Here are some
examples:

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

All shell tests should be placed in the `tests/integraion/shell` directory.
