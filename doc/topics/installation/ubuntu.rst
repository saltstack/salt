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

Some core components are packaged separately in the Ubuntu repositories.  These should be installed as well: salt-cloud, salt-ssh, salt-api

.. code-block:: bash

    sudo apt-get install salt-cloud
    
.. code-block:: bash

    sudo apt-get install salt-ssh
    
.. code-block:: bash

    sudo apt-get install salt-api

.. _ubuntu-config:


ZeroMQ 4
========

We recommend using ZeroMQ 4 where available. ZeroMQ 4 is already available for
Ubuntu 14.04 and Ubuntu 14.10 and nothing additional needs to be done. However,
the **chris-lea/zeromq** PPA can be used to provide ZeroMQ 4 on Ubuntu 12.04 LTS.
Adding this PPA can be done with a :mod:`pkgrepo.managed <salt.states.pkgrepo.managed>`
state.

.. code-block:: yaml

    zeromq-ppa:
      pkgrepo.managed:
        - ppa: chris-lea/zeromq

The following states can be used to upgrade ZeroMQ and pyzmq, and then restart
the minion:

.. code-block:: yaml

    update_zmq:
      pkg.latest:
        - pkgs:
          - zeromq
          - python-zmq
        - order: last
      cmd.wait:
        - name: |
            echo service salt-minion restart | at now + 1 minute
        - watch:
          - pkg: update_zmq

.. note::

    This example assumes that atd is installed and running, see here_ for a more
    detailed explanation.

.. _here: http://docs.saltstack.com/en/latest/faq.html#what-is-the-best-way-to-restart-a-salt-daemon-using-salt

If this repo is added *before* Salt is installed, then installing either
``salt-master`` or ``salt-minion`` will automatically pull in ZeroMQ 4.0.4, and
additional states to upgrade ZeroMQ and pyzmq are unnecessary.


Post-installation tasks
=======================

Now go to the :doc:`Configuring Salt</ref/configuration/index>` page.
