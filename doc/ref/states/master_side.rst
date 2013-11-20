=====================
Remote Control States
=====================

.. versionadded:: 0.17.0

Remote Control States is the capability to organize routines on minions from the
master, using state files.

This allows for the use of the Salt state system to execute state runs and
function runs in a way more powerful than the overstate, will full command of
the requisite and ordering systems inside of states.

.. note::

    Remote Control States was added in 0.17.0 with the intent to eventually
    deprecate the overstate system in favor of this new, substantially more
    powerful system.

    The Overstate will still be maintained for the foreseeable future.

Creating States Trigger Remote Executions
=========================================

The new `salt` state module allows for these new states to be defined in
such a way to call out to the `salt` and/or the `salt-ssh` remote execution
systems, this also supports the addition of states to connect to remote
embedded devices.

To create a state that calls out to minions simple specify the `salt.state`
or `salt.function` states:

.. code-block:: yaml

    webserver_setup:
      salt.state:
        - tgt: 'web*'
        - highstate: True

This sls file can now be referenced by the `state.sls` runner the same way
an sls is normally referenced, assuming the default configuration with /srv/salt
as the root of the state tree and the above file being saved as
/srv/salt/webserver.sls, the state can be run from the master with the salt-run
command:

.. code-block:: bash

    salt-run state.sls webserver

This will execute the defined state to fire up the webserver routine.

Calling Multiple State Runs
===========================

All of the concepts of states exist so building something more complex is
easy:

.. note::

    As of Salt 0.17.0 states are run in the order in which they are defined,
    so the cmd.run defined below will always execute first

.. code-block:: yaml

    cmd.run:
      salt.function:
        - roster: scan
        - tgt: 10.0.0.0/24
        - arg:
          - 'bootstrap'

    storage_setup:
      salt.state:
        - tgt: 'role:storage'
        - tgt_type: grain
        - sls: ceph

    webserver_setup:
      salt.state:
        - tgt: 'web*'
        - highstate: True
    

