==========
Arch Linux
==========

Salt has primarily been developed on Arch Linux, meaning it is known to
work very well on that distribution. The lead developer, Thomas S. Hatch
(thatch45) has been a TU (Trusted User) for the Arch Linux distribution,
and has written a number of Arch-specific tools in the past.

Salt, while not Arch-specific, is packaged for and works well on Arch Linux.

Installation
============

Salt is currently available via the Arch User Repository (AUR). There are
currently stable and -git packages available.

Stable Release
--------------

To install Salt stable releases from the Arch Linux AUR, use the commands:

.. code-block:: bash

    wget https://aur.archlinux.org/packages/sa/salt/salt.tar.gz
    tar xf salt.tar.gz
    cd salt/
    makepkg -is

A few of Salt's dependencies are currently only found within the AUR, so you'll
need to download and run ``makepkg -is`` on these as well. As a reference, Salt
currently relies on the following packages only available via the AUR:

* https://aur.archlinux.org/packages/py/python2-msgpack/python2-msgpack.tar.gz
* https://aur.archlinux.org/packages/py/python2-psutil/python2-psutil.tar.gz

.. note:: yaourt

    If you chose to use a tool such as Yaourt_ the dependencies will be
    gathered and built for you automatically.

    The command to install salt using the yaourt tool is:

    .. code-block:: bash

        yaourt salt

.. _Yaourt: https://aur.archlinux.org/packages.php?ID=5863

Tracking develop
----------------

To install the bleeding edge version of Salt (**may include bugs!**),
you can use the -git package. Installing the -git package can be done
using the commands:

.. code-block:: bash

    wget https://aur.archlinux.org/packages/sa/salt-git/salt-git.tar.gz
    tar xf salt-git.tar.gz
    cd salt-git/
    makepkg -is

A few of Salt's dependencies are currently only found within the AUR, so you'll
need to download and run ``makepkg -is`` on these as well. As a reference, Salt
currently relies on the following packages only available via the AUR:

* https://aur.archlinux.org/packages/py/python2-msgpack/python2-msgpack.tar.gz
* https://aur.archlinux.org/packages/py/python2-psutil/python2-psutil.tar.gz

.. note:: yaourt

    If you chose to use a tool such as Yaourt_ the dependencies will be
    gathered and built for you automatically.

    The command to install salt using the yaourt tool is:

    .. code-block:: bash

        yaourt salt-git

.. _Yaourt: https://aur.archlinux.org/packages.php?ID=5863

Configuration
=============

In the sections below I'll outline configuration options for both the Salt
Master and Salt Minions.

The Salt package installs two template configuration files,
``/etc/salt/master.template`` and ``/etc/salt/minion.template``. You'll need
to copy these .template files into place and make a few edits. First, copy
them into place as seen here:

.. code-block:: bash

   cp /etc/salt/master.template /etc/salt/master
   cp /etc/salt/minion.template /etc/salt/minion

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

By default the Salt master listens on TCP ports 4505 and 4506 on all interfaces
(0.0.0.0). If you have a need to bind Salt to a specific IP, redefine the
"interface" directive as seen here:

.. code-block:: diff

   - #interface: 0.0.0.0
   + interface: 10.0.0.1

**rc.conf**

You'll need to activate the Salt Master in your *rc.conf* file. Using your
favorite editor, open ``/etc/rc.conf`` and add the  salt-master.

.. code-block:: diff

    -DAEMONS=(syslog-ng network crond)
    +DAEMONS=(syslog-ng network crond @salt-master)

**Start the Master**

Once you've completed all of these steps you're ready to start your Salt
Master. You should be able to start your Salt Master now using the command
seen here:

.. code-block:: bash

    rc.d start salt-master

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
file. Using your favorite editor open ``/etc/rc.conf`` and add this line:

.. code-block:: diff

    -DAEMONS=(syslog-ng network crond)
    +DAEMONS=(syslog-ng network crond @salt-minion)

**Start the Minion**

Once you've completed all of these steps you're ready to start your Salt
Minion. You should be able to start your Salt Minion now using the command
seen here:

.. code-block:: bash

    rc.d start salt-minion

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

Before you'll be able to do any remote execution or configuration management you'll
need to accept any pending keys on the Master. Run the ``salt-key`` command to
list the keys known to the Salt Master.

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
