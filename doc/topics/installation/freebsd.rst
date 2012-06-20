=======
FreeBSD
=======

Salt was added to the FreeBSD ports tree Dec 26th, 2011 by Christer Edwards
<christer.edwards@gmail.com>. It has been tested on FreeBSD 7.4, 8.2 and 9.0
releases.

Salt is dependent on the following additional ports. These will be installed as
dependencies of the ``sysutils/salt`` port. ::

   /devel/py-yaml
   /devel/py-pyzmq
   /devel/py-Jinja2
   /devel/py-msgpack
   /security/py-pycrypto
   /security/py-m2crypto

Installation
============

To install Salt from the FreeBSD ports tree, use the command:

.. code-block:: bash

   cd /usr/ports/sysutils/salt && make install clean

Once the port is installed you'll need to make a few configuration changes.
These include defining the IP to bind to (optional), and some configuration
path changes to make salt fit more natively into the FreeBSD filesystem tree.

Configuration
=============

In the sections below I'll outline configuration options for both the Salt
Master and Salt Minions.

The Salt port installs two sample configuration files, ``salt/master.sample``
and ``salt/minion.sample`` (these should be installed in ``/usr/local/etc/``,
unless you use a different ``%%PREFIX%%``). You'll need to copy these
.sample files into place and make a few edits. First, copy them into place
as seen here:

.. code-block:: bash

   cp /usr/local/etc/salt/master.sample /usr/local/etc/salt/master
   cp /usr/local/etc/salt/minion.sample /usr/local/etc/salt/minion

Note: You'll only need to copy the config for the service you're going to run.

Once you've copied the config into place you'll need to make changes specific
to your setup. Below I'll outline suggested configuration changes to the
Master, after which I'll outline configuring the Minion.

Master Configuration
====================

This section outlines configuration of a Salt Master, which is used to control
other machines known as "minions" (see "Minion Configuration" for instructions
on configuring a minion). This will outline IP configuration, and a few key
configuration paths.

**Interface**

By default the Salt master listens on ports 4505 and 4506 on all interfaces
(0.0.0.0). If you have a need to bind Salt to a specific IP, redefine the
"interface" directive as seen here.

.. code-block:: diff

   - #interface: 0.0.0.0
   + interface: 10.0.0.1

**rc.conf**

Last but not least you'll need to activate the Salt Master in your rc.conf
file. Using your favorite editor, open ``/etc/rc.conf`` or
``/etc/rc.conf.local`` and add this line.

.. code-block:: diff

   + salt_master_enable="YES"

**Start the Master**

Once you've completed all of these steps you're ready to start your Salt
Master. The Salt port installs an rc script which should be used to manage your
Salt Master. You should be able to start your Salt Master now using the command
seen here:

.. code-block:: bash

   service salt_master start

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
configuration file and update the "master" entry as seen here.

.. code-block:: diff

   - #master: salt
   + master: 10.0.0.1

Simply update the master directive to the IP or hostname of your Salt Master.
Save your changes and you're ready to start your Salt Minion. Advanced
configuration options are covered in another chapter.

**rc.conf**

Before you're able to start the Salt Minion you'll need to update your rc.conf
file. Using your favorite editor open ``/etc/rc.conf`` or
``/etc/rc.conf.local`` and add this line.

.. code-block:: diff

   + salt_minion_enable="YES"

Once you've completed all of these steps you're ready to start your Salt
Minion. The Salt port installs an *rc* script which should be used to manage your
Salt Minion. You should be able to start your Salt Minion now using the command
seen here.

.. code-block:: bash

   service salt_minion start

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

Before you'll be able to do any remote execution or state management you'll
need to accept any pending keys on the Master. Run the ``salt-key`` command to
list the keys known to the Salt Master:

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
the ``test.ping`` remote command. ::

   [root@master ~]# salt 'alpha' test.ping
   {'alpha': True}

Where Do I Go From Here
=======================

Congratulations! You've successfully configured your first Salt Minions and are
able to send remote commands. I'm sure you're eager to learn more about what
Salt can do. Depending on the primary way you want to manage your machines you
may either want to visit the section regarding Salt States, or the section on
Modules.

