===============================================
Using cron with Salt
===============================================

The Salt Minion can initiate its own highstate using the :term:`salt-call`
command.

.. code-block:: bash
    $ salt-call state.highstate


This will cause the minion to check in with the master and ensure it is in the
correct 'state'.


Use cron to initiate a highstate
================================

If you would like the Salt Minion to regularly check in with the master you can
use the venerable cron to run the :term:`salt-call` command.


