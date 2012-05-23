==================================
Fedora & CentOS / Enterprise Linux
==================================

Beginning with version 0.9.4, Salt has been available in the primary Fedora
repositories and `EPEL`_. It is installable using yum. Fedora will have more
up to date versions of Salt than other members of the Red Hat family, which
makes it a great place to help improve Salt!

.. admonition:: CentOS / RHEL 5

    Salt and all dependencies have been *finally* accepted into the yum
    reposities for EPEL5 and EPEL6. Currently, the latest is in epel-testing
    while awaiting promotion to epel proper. You can install it via:

    .. code-block:: bash

        yum --enablerepo=epel-testing install salt

    On RHEL6, the proper jinja packages were moved from EPEL to the
    "RHEL Server Optional Channel". Verify this repository is enabled before
    installing salt on RHEL6.

.. _`EPEL`: http://fedoraproject.org/wiki/EPEL

Installation
============

Salt can be installed using ``yum`` and is available in the standard Fedora
repositories.

Stable Release
--------------

Salt is packaged separately for the minion and the master. You'll only need to
install the appropriate package for the role you need the machine to play. This
means you're going to want one master and a whole bunch of minions!

.. code-block:: bash

    yum install salt-master
    yum install salt-minion

Configuration
=============

Below, we'll cover Salt Master and Minion configuration options.

Master Configuration
====================

This section outlines configuration of a Salt Master, which is used to control
other machines known as "minions" (see "Minion Configuration" for instructions
on configuring a minion). This will outline IP configuration, and a few key
configuration paths.

**Interface**

By default the Salt master listens on TCP ports ``4505`` and ``4506`` on all interfaces
(0.0.0.0). If you have a need to bind Salt to a specific IP, redefine the
"interface" directive as seen here:

.. code-block:: diff

   - #interface: 0.0.0.0
   + interface: 10.0.0.1

**Enable the Master**

You'll also likely want to activate the Salt Master in *systemd*, configuring the
Salt Master to start automatically at boot.

.. code-block:: bash

    systemctl enable salt-master.service

**Start the Master**

Once you've completed all of these steps you're ready to start your Salt
Master. You should be able to start your Salt Master now using the command
seen here:

.. code-block:: bash

    systemctl start salt-master.service

If your Salt Master doesn't start successfully, go back through each step and
see if anything was missed. Salt doesn't take much configuration (part of its
beauty!), and errors are usually simple mistakes.

Minion Configuration
====================

Configuring a Salt Minion is surprisingly simple. Unless you have a real need
for customizing your minion configuration (which there are plenty of options if
you are so inclined!), there is one simple directive that needs to be updated.
That option is the location of the master.

By default a Salt Minion will try to connect to the dns name "salt". If you
have the ability to update DNS records for your domain you might create an A or
CNAME record for "salt" that points to your Salt Master. If you are able to do
this you likely can do without any minion configuration at all.

If you are not able to update DNS, you'll simply need to update one entry in
the configuration file. Using your favorite editor, open the minion
configuration file and update the "master" entry as seen here:

.. code-block:: diff

   - #master: salt
   + master: 10.0.0.1

Simply update the master directive to the IP or hostname of your Salt Master.
Save your changes and you're ready to start your Salt Minion. Advanced
configuration options are covered in another chapter.

**Enable the Minion**

You'll need to configure the minion to auto-start at boot. You can toggle
that option through systemd.

.. code-block:: bash

    systemctl enable salt-minion.service

**Start the Minion**

Once you've completed all of these steps, start the Minion. This command
should do the trick:

.. code-block:: bash

    systemctl start salt-minion.service

If your Salt Minion doesn't start successfully, go back through each step and
see if anything was missed. Salt doesn't take much configuration (part of its
beauty!), and errors are usually simple mistakes.

Tying It All Together
=====================

If you've successfully completed each of the steps above you should have a
running Salt Master and a running Salt Minion. The Minion should be configured
to point to the Master. To verify that there is communication flowing between
the Minion and Master we'll run a few initial ``salt`` commands. These commands
will validate the Minions RSA encryption key, and then send a test command to
the Minion to ensure that commands and responses are flowing as expected.

**Key Management**

Salt uses AES encryption for all communication between the Master and the
Minion. This ensures that the commands you send to your Minions (your cloud)
can not be tampered with, and that communication between Master and Minion is
only done through trusted, accepted keys.

Before you'll be able to do any remote execution or configuration management
you'll need to accept any pending keys on the Master. Run the ``salt-key``
command to list the keys known to the Salt Master:

.. code-block:: bash

   [root@master ~]# salt-key -L
   Unaccepted Keys:
   alpha
   bravo
   charlie
   delta
   Accepted Keys:

This example shows that the Salt Master is aware of four Minions, but none of
the keys have been accepted. To accept the keys and allow the Minions to be
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

Sending Commands
================

Everything should be set for you to begin remote management of your Minions.
Whether you have a few or a few-dozen, Salt can help you manage them easily!

For final verification, send a test function from your Salt Master to your
minions. If all of your minions are properly communicating with your Master,
you should "True" responses from each of them. See the example below to send
the ``test.ping`` remote command:

.. code-block:: bash

   [root@master ~]# salt '*' test.ping
   {'alpha': True}

Where Do I Go From Here
=======================

Congratulations! You've successfully configured your first Salt Minions and are
able to send remote commands. I'm sure you're eager to learn more about what
Salt can do. Depending on the primary way you want to manage your machines you
may either want to visit the section regarding Salt States, or the section on
Modules.
