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

Runners have several options for controlling output.

Any ``print`` statement in a runner is automatically also
fired onto the master event bus where. For example:

.. code-block:: python

    def a_runner(outputter=None, display_progress=False):
        print('Hello world')
        ...

The above would result in an event fired as follows:

.. code-block:: bash

    Event fired at Tue Jan 13 15:26:45 2015
    *************************
    Tag: salt/run/20150113152644070246/print
    Data:
    {'_stamp': '2015-01-13T15:26:45.078707',
     'data': 'hello',
      'outputter': 'pprint'}


A runner may also send a progress event, which is displayed to the user during
runner execution and is also passed across the event bus if the ``display_progress``
argument to a runner is set to True.

A custom runner may send its own progress event by using the
``__jid_event_.fire_event()`` method as shown here:

.. code-block:: python

    if display_progress:
        __jid_event__.fire_event({'message': 'A progress message', 'progress')

The above would produce output on the console reading: ``A progress message``
as well as an event on the event similar to:

.. code-block:: bash

    Event fired at Tue Jan 13 15:21:20 2015
    *************************
    Tag: salt/run/20150113152118341421/progress
    Data:
    {'_stamp': '2015-01-13T15:21:20.390053',
     'message': "A progress message"}

A runner could use the same approach to send an event with a customized tag
onto the event bus by replacing the second argument (``progress``) with
whatever tag is desired. However, this will not be shown on the command-line
and will only be fired onto the event bus.

Synchronous vs. Asynchronous
----------------------------

A runner may be fired asychronously which will immediately return control. In
this case, no output will be display to the user if ``salt-run`` is being used
from the command-line. If used programatically, no results will be returned.
If results are desired, they must be gathered either by firing events on the
bus from the runner and then watching for them or by some other means.

.. note::

    When running a runner in asyncronous mode, the ``--progress`` flag will
    not deliver output to the salt-run CLI. However, progress events will
    still be fired on the bus.

In synchronous mode, which is the default, control will not be returned until
the runner has finished executing.





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
