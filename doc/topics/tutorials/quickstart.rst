==========================
Salt Masterless Quickstart
==========================

.. _`Vagrant`: http://www.vagrantup.com/
.. _`salty-vagrant`: https://github.com/saltstack/salty-vagrant
.. _`salt-bootstrap`: https://github.com/saltstack/salt-bootstrap

Running a masterless salt-minion lets you use salt's configuration management 
for a single machine. It is also useful for testing out state trees before 
deploying to a production setup.

The only real difference in using a standalone minion is that instead of issuing 
commands with ``salt``, we use the ``salt-call`` command, like this::

    salt-call --local state.highstate

Bootstrap Salt Minion
=====================

First we need to install the salt minion. The `salt-bootstrap`_ script makes
this incredibly easy for any OS with a Bourne shell. You can use it like this::

    wget -O - http://bootstrap.saltstack.org | sudo sh

Or see the `salt-bootstrap`_ documentation for other one liners. Additionally, 
if you are using `Vagrant`_ to test out salt, the `salty-vagrant`_ tool will 
provision the VM for you.

Create State Tree
=================

Now we build an example state tree. This is where the configuration 
is defined. For more in depth directions, see the `tutorial <http://docs.saltstack.org/en/latest/topics/tutorials/states_pt1.html>`_. 

1. Create the top.sls file
::
  # /srv/salt/top.sls
  base:
    '*':
      - webserver

2. Create our webserver state tree
::
  # /srv/salt/webserver.sls
  apache:                 # ID declaration
    pkg:                  # state declaration
      - installed         # function declaration

The only thing left is to provision our minion using the highstate command.
Salt-call also gives us an easy way to give us verbose output::

    salt-call --local state.highstate -l debug

The ``--local`` flag tells the salt-minion to look for the state tree in the local file system.
Normally the minion copies the state tree from the master and executes it from there.

That's it, good luck!


