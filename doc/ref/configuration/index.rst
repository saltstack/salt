================
Configuring Salt
================

Salt configuration is very simple. The default configuration for the
:term:`master` will work for most installations and the only requirement for
setting up a :term:`minion` is to set the location of the master in the minion
configuration file.

The configuration files will be installed to :file:`/etc/salt` and are named
after the respective components, :file:`/etc/salt/master`, and
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
    :option:`-d flag <salt-master -d>`):

    .. code-block:: bash

        salt-master

2.  Start the minion in the foreground (to daemonize the process, pass the
    :option:`-d flag <salt-minion -d>`):

    .. code-block:: bash

        salt-minion


.. admonition:: Having trouble?

    The simplest way to troubleshoot Salt is to run the master and minion in
    the foreground with :option:`log level <salt-master -l>` set to ``debug``:

    .. code-block:: bash

        salt-master --log-level=debug

    For information on salt's logging system please see the :doc:`logging
    document</ref/configuration/logging/index>`.


.. admonition:: Run as an unprivileged (non-root) user

    To run Salt as another user, set the :conf_master:`user` parameter in the
    master config file.

    Additionally, ownership, and permissions need to be set such that the
    desired user can read from and write to the following directories (and
    their subdirectories, where applicable):

    * /etc/salt
    * /var/cache/salt
    * /var/log/salt
    * /var/run/salt

    More information about running salt as a non-privileged user can be found
    :doc:`here </ref/configuration/nonroot>`.


There is also a full :doc:`troubleshooting guide</topics/troubleshooting/index>`
available.

.. _key-identity:

Key Identity
============

Salt provides commands to validate the identity of your Salt master
and Salt minions before the initial key exchange. Validating key identity helps
avoid inadvertently connecting to the wrong Salt master, and helps prevent
a potential MiTM attack when establishing the initial connection.

Master Key Fingerprint
----------------------

Print the master key fingerprint by running the following command on the Salt master:

.. code-block:: bash

   salt-key -F master

Copy the ``master.pub`` fingerprint from the *Local Keys* section, and then set this value
as the :conf_minion:`master_finger` in the minion configuration file. Save the configuration
file and then restart the Salt minion.

Minion Key Fingerprint
----------------------

Run the following command on each Salt minion to view the minion key fingerprint:

.. code-block:: bash

   salt-call --local key.finger

Compare this value to the value that is displayed when you run the
``salt-key --finger <MINION_ID>`` command on the Salt master.


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
the ``test.ping`` command:

.. code-block:: bash

   [root@master ~]# salt alpha test.ping
   alpha:
       True

Communication between the Master and all Minions may be tested in a
similar way:

.. code-block:: bash

   [root@master ~]# salt '*' test.ping
   alpha:
       True
   bravo:
       True
   charlie:
       True
   delta:
       True

Each of the Minions should send a ``True`` response as shown above.

What's Next?
============

Understanding :doc:`targeting </topics/targeting/index>` is important. From there,
depending on the way you wish to use Salt, you should also proceed to learn
about :doc:`States </topics/tutorials/starting_states>` and :doc:`Execution Modules
</ref/modules/index>`.
