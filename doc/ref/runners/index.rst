============
Salt Runners
============

Salt runners are convenience applications executed with the salt-run command.

Salt runners work similarly to Salt execution modules however they execute on the
Salt master itself instead of remote Salt minions.

A Salt runner can be a simple client call or a complex application.

.. seealso:: :ref:`The full list of runners <all-salt.runners>`

.. toctree::
    :hidden:

    all/index

Writing Salt Runners
--------------------

A Salt runner is written in a similar manner to a Salt execution module.
Both are Python modules which contain functions and each public function
is a runner which may be executed via the *salt-run* command.

For example, if a Python module named ``test.py`` is created in the runners
directory and contains a function called ``foo``, the ``test`` runner could be
invoked with the following command:

.. code-block:: bash

    # salt-run test.foo

To add custom runners, put them in a directory and add it to
:conf_master:`runner_dirs` in the master configuration file.

Examples
--------

Examples of runners can be found in the Salt distribution:

:blob:`salt/runners`

A simple runner that returns a well-formatted list of the minions that are
responding to Salt calls could look like this:

.. code-block:: python

    # Import salt modules
    import salt.client

    def up():
        '''
        Print a list of all of the minions that are up
        '''
        client = salt.client.LocalClient(__opts__['conf_file'])
        minions = client.cmd('*', 'test.ping', timeout=1)
        for minion in sorted(minions):
            print minion
