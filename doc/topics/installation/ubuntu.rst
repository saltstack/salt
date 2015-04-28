===================
Ubuntu Installation
===================

Add repository
==============

The latest packages for Ubuntu are published in the saltstack PPA. If you have
the ``add-apt-repository`` utility, you can add the repository and import the
key in one step:

.. code-block:: bash

    sudo add-apt-repository ppa:saltstack/salt

.. admonition:: add-apt-repository: command not found?

    The ``add-apt-repository`` command is not always present on Ubuntu systems.
    This can be fixed by installing `python-software-properties`:

    .. code-block:: bash

        sudo apt-get install python-software-properties

    The following may be required as well:

    .. code-block:: bash

        sudo apt-get install software-properties-common

    Note that since Ubuntu 12.10 (Raring Ringtail), ``add-apt-repository`` is
    found in the `software-properties-common` package, and is part of the base
    install. Thus, ``add-apt-repository`` should be able to be used
    out-of-the-box to add the PPA.

Alternately, manually add the repository and import the PPA key with these
commands:

.. code-block:: bash

    echo deb http://ppa.launchpad.net/saltstack/salt/ubuntu `lsb_release -sc` main | sudo tee /etc/apt/sources.list.d/saltstack.list
    wget -q -O- "http://keyserver.ubuntu.com:11371/pks/lookup?op=get&search=0x4759FA960E27C0A6" | sudo apt-key add -

After adding the repository, update the package management database:

.. code-block:: bash

    sudo apt-get update


Install packages
================

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


ZeroMQ 4
========

ZeroMQ 4 is available by default for Ubuntu 14.04 and newer. However, for Ubuntu
12.04 LTS, starting with Salt version ``2014.7.5``, ZeroMQ 4 is included with the
Salt installation package and nothing additional needs to be done.


Post-installation tasks
=======================

Now go to the :doc:`Configuring Salt</ref/configuration/index>` page.