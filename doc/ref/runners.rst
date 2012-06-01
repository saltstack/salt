============
Salt Runners
============

Salt runners are convenience applications executed with the salt-run command.

A Salt runner can be a simple client call, or a complex application.

The use for a Salt runner is to build a frontend hook for running sets of
commands via Salt or creating special formatted output.

Writing Salt Runners
--------------------

Salt runners can be easily written, the work in a similar way to Salt modules
except they run on the server side.

A runner is a Python module that contains functions, each public function is
a runner that can be executed via the *salt-run* command.

If a Python module named test.py is created in the runners directory and
contains a function called ``foo`` then the function could be called with:

.. code-block:: bash

    # salt '*' test.foo

Examples
--------

The best examples of runners can be found in the Salt source:

:blob:`salt/runners`

A simple runner that returns a well-formatted list of the minions that are
responding to Salt calls would look like this:

.. code-block:: python

    # Import salt modules
    import salt.client

    def up():
        '''
        Print a list of all of the minions that are up
        '''
        client = salt.client.LocalClient(__opts__['config'])
        minions = client.cmd('*', 'test.ping', timeout=1)
        for minion in sorted(minions):
            print minion

