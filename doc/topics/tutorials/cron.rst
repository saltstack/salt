===============================================
Using cron with Salt
===============================================

The Salt Minion can initiate its own highstate using the ``salt-call`` command.

.. code-block:: bash

    $ salt-call state.highstate


This will cause the minion to check in with the master and ensure it is in the
correct 'state'.


Use cron to initiate a highstate
================================

If you would like the Salt Minion to regularly check in with the master you can
use the venerable cron to run the ``salt-call`` command.

.. code-block:: bash

    # PATH=/bin:/sbin:/usr/bin:/usr/sbin

    00 00 * * * salt-call state.highstate

The above cron entry will run a highstate every day at midnight.

.. note::
    Be aware that you may need to ensure the PATH for cron includes any
    scripts or commands that need to be executed.