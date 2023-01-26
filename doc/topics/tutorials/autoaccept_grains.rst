.. _tutorial-autoaccept-grains:

==============================
Autoaccept minions from Grains
==============================

.. versionadded:: 2018.3.0

To automatically accept minions based on certain characteristics, e.g. the ``uuid``
you can specify certain grain values on the salt master. Minions with matching grains
will have their keys automatically accepted.

1. Configure the autosign_grains_dir in the master config file:

.. code-block:: yaml

    autosign_grains_dir: /etc/salt/autosign_grains


2. Configure the grain values to be accepted

Place a file named like the grain in the autosign_grains_dir and write the values that
should be accepted automatically inside that file. For example to automatically
accept minions based on their ``uuid`` create a file named ``/etc/salt/autosign_grains/uuid``:

.. code-block:: none

    8f7d68e2-30c5-40c6-b84a-df7e978a03ee
    1d3c5473-1fbc-479e-b0c7-877705a0730f

If already running, the master must be restarted for these config changes to take effect.

The master is now setup to accept minions with either of the two specified uuids.
Multiple values must always be written into separate lines.
Lines starting with a ``#`` are ignored.


3. Configure the minion to send the specific grains to the master in the minion config file:

.. code-block:: yaml

    autosign_grains:
      - uuid

Now you should be able to start salt-minion and run ``salt-call
state.apply`` or any other salt commands that require master authentication.
