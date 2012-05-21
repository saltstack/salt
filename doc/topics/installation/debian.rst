===============
Debian & Ubuntu
===============

Ubuntu
======

Installation
============

To install Salt on Ubuntu, use the following command:

.. code-block:: bash

    add-aptrepository ppa:saltstack/salt
    apt-get install salt-master
    apt-get install salt-minion

After installation you'll need to make a few changes to the configuration files.

Configuration
=============

To configure your salt files we must modify both master and minion 
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
    sudo /etc/inti.d/salt-minion restart

Test
====

To test salt we must first sign the key of the minion to the master. To see the
pending keys type in the following command:

.. code-block:: bash

    sudo salt-key -L

From here you will should see a key name underneath the Unaccepted Keys 
portion. To sign the minion key to the master type in the following command:

.. code-block:: baash

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

To see if the master is running properly type in the following command:

.. code-block:: bash

    netstat -natp | grep 450

This should return ``192.168.0.10:4505`` and ``192.168.0.10:4506`` if the master was 
configured properly. If this does not return those values recheck your master 
and minion config files for mistakes.

To see if both master and minion are running properly type in the following 
command:

.. code-block:: bash

    ps -efH | grep sal[t]

This should return 8 salt masters and 1 salt minion if both are configured 
properly. If you are still having issues with your salt configuration please 
reference the trouble shooting page:

.. code-block:: bash

    vim salt/doc/topic/troubleshooting/index.rst

What Now?
=========

Congratulations you have just successfully setup salt on your Ubuntu machine 
and configured both the master and the minion. From this point you are now 
able to send remote commands. Depending on the primary way you want to 
manage your machines you may either want to visit the section regarding Salt 
States, or the section on Modules.

Debian
------

`A deb package is currently in testing`__ for inclusion in apt. Until that is
accepted you can install Salt by downloading the latest ``.deb`` in the
`downloads section on GitHub`__ and installing that manually using ``dpkg -i``.

.. __: http://mentors.debian.net/package/salt
.. __: https://github.com/saltstack/salt/downloads

.. admonition:: Installing ZeroMQ on Squeeze (Debian 6)

    There is a `python-zmq`__ package available in Debian \"wheezy (testing)\".
    If you don't have that repo enabled the best way to install Salt and pyzmq
    is by using ``pip`` (or ``easy_install``):

    .. code-block:: bash

        pip install pyzmq salt

.. __: http://packages.debian.org/search?keywords=python-zmq
