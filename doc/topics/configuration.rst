================
Configuring Salt
================

Salt configuration is very simple. The default configuration for the
:term:`master` will work for most installations and the only requirement for
setting up a :term:`minion` is to set the location of the master in the minion
configuration file.

.. glossary::

    master
        The Salt master is the central server that all minions connect to. 
        Commands are run on the minions through the master, and minions send data
        back to the master (unless otherwise redirected with a :doc:`returner
        </ref/returners/index>`). It is started with the
        :command:`salt-master` program.

    minion
        Salt minions are the potentially hundreds or thousands of servers that
        may be queried and controlled from the master.

The configuration files will be installed to :file:`/etc/salt` and are named
after the respective components, :file:`/etc/salt/master` and
:file:`/etc/salt/minion`.

Master Configuration
====================

By default the Salt master listens on ports 4505 and 4506 on all
interfaces (0.0.0.0). To bind Salt to a specific IP, redefine the
"interface" directive in the master configuration file, typically
``/etc/salt/master``, as follows:

.. code-block:: diff

   - #interface: 0.0.0.0
   + interface: 10.0.0.1

After updating the configuration file, restart the Salt master.
See the :doc:`master configuration reference </ref/configuration/master>`
for more details about other configurable options.

Minion Configuration
====================

Although there are many Salt Minion configuration options, configuring
a Salt Minion is very simple. By default a Salt Minion will
try to connect to the DNS name "salt"; if the Minion is able to
resolve that name correctly, no configuration is needed.

If the DNS name "salt" does not resolve to point to the correct
location of the Master, redefine the "master" directive in the minion
configuration file, typically ``/etc/salt/minion``, as follows:

.. code-block:: diff

   - #master: salt
   + master: 10.0.0.1

After updating the configuration file, restart the Salt minion.
See the :doc:`minion configuration reference </ref/configuration/minion>`
for more details about other configurable options.

Running Salt
============

1.  Start the master in the foreground (to daemonize the process, pass the
    :option:`-d flag <salt-master -d>`)::

        # salt-master

2.  Start the minion in the foreground (to daemonize the process, pass the
    :option:`-d flag <salt-minion -d>`)::

        # salt-minion

.. admonition:: Having trouble?

    The simplest way to troubleshoot Salt is to run the master and minion in
    the foreground with :option:`log level <salt-master -l>` set to ``debug``::

        salt-master --log-level=debug

.. admonition:: Run as an unprivileged (non-root) user

    To run Salt as another user, specify ``--user`` in the command
    line or assign ``user`` in the
    :doc:`configuration file</ref/configuration/master>`.


There is also a full :doc:`troubleshooting guide</topics/troubleshooting/index>`
available.

Key Management
==============

Salt uses AES encryption for all communication between the Master and
the Minion. This ensures that the commands sent to the Minions cannot
be tampered with, and that communication between Master and Minion is
authenticated through trusted, accepted keys.

Before commands can be sent to a Minion, its key must be accepted on
the Master. Run the ``salt-key`` command to list the keys known to
the Salt Master:

.. code-block:: bash

   [root@master ~]# salt-key -L
   Unaccepted Keys:
   alpha
   bravo
   charlie
   delta
   Accepted Keys:

This example shows that the Salt Master is aware of four Minions, but none of
the keys has been accepted. To accept the keys and allow the Minions to be
controlled by the Master, again use the ``salt-key`` command:

.. code-block:: bash

   [root@master ~]# salt-key -A
   [root@master ~]# salt-key -L
   Unaccepted Keys:
   Accepted Keys:
   alpha
   bravo
   charlie
   delta

The ``salt-key`` command allows for signing keys individually or in bulk. The
example above, using ``-A`` bulk-accepts all pending keys. To accept keys
individually use the lowercase of the same option, ``-a keyname``.

.. seealso:: :doc:`salt-key manpage </ref/cli/salt-key>`

Sending Commands
================

Communication between the Master and a Minion may be verified by running
the ``test.ping`` remote command. ::


   [root@master ~]# salt 'alpha' test.ping
   alpha:
       True

Communication between the Master and all Minions may be tested in a
similar way. ::

   [root@master ~]# salt '*' test.ping
   alpha:
       True
   bravo:
       True
   charlie:
       True
   delta:
       True

Each of the Minions should send a "True" response as shown above.

What's Next?
============

Depending on the primary way you want to manage your machines you may
either want to visit the section regarding Salt States, or the section
on Modules.

