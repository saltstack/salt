==========================
Salt Masterless Quickstart
==========================

.. _`Vagrant`: http://www.vagrantup.com/
.. _`salty-vagrant`: https://github.com/saltstack/salty-vagrant
.. _`salt-bootstrap`: https://github.com/saltstack/salt-bootstrap

Running a master-less salt-minion lets you use Salt's configuration management
for a single machine without calling out to a Salt master on another machine.

It is also useful for testing out state trees before  deploying to a production setup.

The only real difference in using a standalone minion is that instead of issuing 
commands with ``salt``, the ``salt-call`` command is used instead:

.. code-block:: bash

    salt-call --local state.highstate

Bootstrap Salt Minion
=====================

The `salt-bootstrap`_ script makes boostrapping a server with Salt simple
for any OS with a Bourne shell:

.. code-block:: bash

    wget -O - http://bootstrap.saltstack.org | sudo sh

See the `salt-bootstrap`_ documentation for other one liners. When using `Vagrant`_
to test out salt, the `salty-vagrant`_ tool will  provision the VM for you.

Create State Tree
=================

Following the successful installation of a salt-minion, the next step is to create
a state tree, which is where the SLS files that comprise the possible states of the
minion are stored.

The following example walks through the steps necessary to create a state tree that
ensures that the server has the Apache webserver installed.

.. note:::
    For a complete explanation on Salt States, see the `tutorial
    <http://docs.saltstack.org/en/latest/topics/tutorials/states_pt1.html>`_.

1. Create the ``top.sls`` file:

``/srv/salt/top.sls:``

.. code-block:: yaml

    base:
      '*':
        - webserver

2. Create the webserver state tree:

``/srv/salt/webserver.sls:``

.. code-block:: yaml

    apache:               # ID declaration
      pkg:                # state declaration
        - installed       # function declaration

The only thing left is to provision our minion using the highstate command.
To initiate a highstate run, use the ``salt-call`` command:

.. code-block:: bash

    salt-call --local state.highstate -l debug

The ``--local`` flag tells the salt-minion to look for the state tree in the
local file system and not to contact a Salt Master for instructions.

To provide verbose output, used ``-l debug``.

The minion first examines the ``top.sls`` file and determines that it is a part
of the group matched by ``*`` glob and that the ``webserver`` SLS should be applied.

It then examines the ``webserver.sls`` file and finds the ``apache`` state, which
installs the Apache package.

