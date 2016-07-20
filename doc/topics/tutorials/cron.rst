Using cron with Salt
====================

The Salt Minion can initiate its own :ref:`highstate <running-highstate>` using
the ``salt-call`` command.

.. code-block:: bash

    $ salt-call state.apply


This will cause the minion to check in with the master and ensure it is in the
correct "state".


Use cron to initiate a highstate
================================

If you would like the Salt Minion to regularly check in with the master you can
use cron to run the ``salt-call`` command:

.. code-block:: bash

    0 0 * * * salt-call state.apply

The above cron entry will run a :ref:`highstate <running-highstate>` every day
at midnight.

.. note::
    When executing Salt using cron, keep in mind that the default PATH for cron
    may not include the path for any scripts or commands used by Salt, and it
    may be necessary to set the PATH accordingly in the crontab:

    .. code-block:: cron

        PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:/opt/bin

        0 0 * * * salt-call state.apply
