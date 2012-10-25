===================
Ubuntu Installation
===================

Add repository
--------------

The latest packages for Ubuntu are published in the saltstack PPA. Add the repository 
to your system and refresh the package data with the following commands:

.. code-block:: bash

    echo deb http://ppa.launchpad.net/saltstack/salt/ubuntu `lsb_release -sc` main | sudo tee /etc/apt/sources.list.d/saltstack.list
    sudo apt-get update

Install packages
----------------

Install the Salt master, minion, or syndic from the repository with the apt-get 
command. These examples each install one daemon, but more than one package name 
may be given at a time:

.. code-block:: bash

    sudo apt-get install salt-master 

.. code-block:: bash

    sudo apt-get install salt-minion

.. code-block:: bash

    sudo apt-get install salt-syndic

.. _ubuntu-config:

Configuration
-------------

Debian based systems will launch the daemons right after package install, but you 
may need to make changes to the configuration files in /etc/salt (see the configuration
files), such as:

- set the minion id and salt master name in /etc/salt/minion
- enable the file_roots and pillar_roots options in /etc/salt/master
- configure syndic to relay commands from another master

After making any configuration changes, re-start the affected daemons:

.. code-block:: bash

    sudo restart salt-master

.. code-block:: bash

    sudo restart salt-minion

.. code-block:: bash

    sudo restart salt-syndic

