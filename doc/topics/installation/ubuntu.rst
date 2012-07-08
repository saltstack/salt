======
Ubuntu
======

Installation
============

To install Salt on Ubuntu, use the following command:

.. code-block:: bash

    sudo apt-get install python-software-properties
    sudo add-apt-repository ppa:saltstack/salt
    sudo apt-get update
    sudo apt-get install salt-master
    sudo apt-get install salt-minion

.. admonition:: Installing on Ubuntu 11.04

    There is a conflict with `msgpack-python` on Ubuntu 11.04 and the current 
    saltstack PPA.  You can work around the conflict by installing
    `msgpack-python` from Oneiric:
    
    .. code-block:: bash

        sudo add-apt-repository 'deb http://us.archive.ubuntu.com/ubuntu/ oneiric universe'
        sudo add-apt-repository ppa:saltstack/salt
        sudo apt-get update
        sudo apt-get install msgpack-python
        sudo apt-get install salt-master
        sudo apt-get install salt-minion
        sudo add-apt-repository --remove 'deb http://us.archive.ubuntu.com/ubuntu/ oneiric universe'

After installation you'll need to make a few changes to the configuration files.

Configuration
=============

To configure your Salt files we must modify both master and minion 
configuration files. We need to set where the master binds, by default salt 
listens on all interfaces. If you have a need to bind to a specific local IP, 
make the change as needed. To edit the master type in the following command:

.. code-block:: bash

    sudo vim /etc/salt/master

From here make the following changes:

.. code-block:: diff

    - interface: 0.0.0.0
    + interface: 192.168.0.10

To configure the minion type in the following command:

.. code-block:: bash

    sudo vim /etc/salt/minion

Once inside the editor make the following changes:

.. code-block:: diff

    - master: salt
    + master: 192.168.0.10

After making the following changes you need to restart both the master and the 
minion. To do so type in the following commands:

.. code-block:: bash

    sudo /etc/init.d/salt-master restart
    sudo /etc/init.d/salt-minion restart

Test
====

To test Salt we must first sign the key of the minion to the master. To see the
pending keys type in the following command:

.. code-block:: bash

    sudo salt-key -L

From here you will should see a key name underneath the Unaccepted Keys 
portion. To sign the minion key to the master type in the following command:

.. code-block:: bash

    sudo salt-key -a $minion

Where ``$minion`` is the unaccepted key.


Now that you have signed the key we need to see if the key was accepted and 
that we can ping the minion and get a response. To do this you can type in one 
of the previous commands ``sudo salt-key -L`` and see if the key has been 
accepted, then also ping the minion to see if it's working by typing in the 
following command:

.. code-block:: bash

    sudo salt \* test.ping

If it is working properly you should see this result:

.. code-block:: bash

    {'$minion': True}

Troubleshooting
===============

To see if the Salt master is running properly type in the following command:

.. code-block:: bash

    netstat -natp | grep 450

This should return ``192.168.0.10:4505`` and ``192.168.0.10:4506`` if the master was 
configured properly. If this does not return those values recheck your master 
and minion config files for mistakes.

To see if both master and minion are running properly type in the following 
command:

.. code-block:: bash

    ps -efH | grep sal[t]

This should return 8 Salt masters and 1 Salt minion if both are configured 
properly. If you are still having issues with your Salt configuration please 
reference the trouble shooting page :doc:`Troubleshooting</topics/troubleshooting/index>`.

What Now?
=========

Congratulations you have just successfully installed Salt on your Ubuntu machine 
and configured both the master and the minion. From this point you are now 
able to send remote commands. Depending on the primary way you want to 
manage your machines you may either want to visit the section regarding Salt 
States, or the section on Modules.

