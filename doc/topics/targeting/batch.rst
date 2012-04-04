Batch Size
----------

The batch size option allows commands to be executed while maintaining that
only so many hosts are executing the command at one time. This option can
take a percentage or a finite number:

.. code-block:: bash

    salt \* -b 10 test.ping

    salt -G 'os:RedHat' --batch-size 25% apache.signal restart

This will only run test.ping on 10 of the targeted minions at a time and then
restart apache on 25% of the minions matching ``os:RedHat`` at a time and work
through them all until the task is complete. This makes jobs like rolling web
server restarts behind a load balancer or doing maintenance on BSD firewalls
using carp much easier with salt.

The batch system maintains a window of running minions, so, if there are a
total of 150 minions targeted and the batch size is 10, then the command is
sent to 10 minions, when one minion returns then the command is sent to one
additional minion, so that the job is constantly running on 10 minions.
