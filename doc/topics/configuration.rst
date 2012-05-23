================
Configuring Salt
================

Salt configuration is very simple. The default configuration for the
:term:`master` will work for most installations and the only requirement for
setting up a :term:`minion` is to set the location of the master in the minion
configuration file.

.. glossary::

    master
        The Salt master is the central server that all minions connect to. You
        run commands on the minions through the master and minions send data
        back to the master (unless otherwise redirected with a :doc:`returner
        </ref/returners/index>`). It is started with the
        :command:`salt-master` program.

    minion
        Salt minions are the potentially hundreds or thousands of servers that
        you query and control from the master.

The configuration files will be installed to :file:`/etc/salt` and are named
after the respective components, :file:`/etc/salt/master` and
:file:`/etc/salt/minion`.

To make a minion check into the correct master simply edit the
:conf_minion:`master` variable in the minion configuration file to reference
the master DNS name or IPv4 address.

Running Salt
============

1.  Start the master in the foreground (to daemonize the process, pass the
    :option:`-d flag <salt-master -d>`)::

        # salt-master

2.  Start the minion in the foreground (to daemonize the process, pass the
    :option:`-d flag <salt-minion -d>`)::

        # salt-minion

.. admonition:: Having trouble?

    The simplest way to troubleshoot Salt is to run the master and minion in
    the foreground with :option:`log level <salt-master -l>` set to ``debug``::

        salt-master --log-level=debug

.. admonition:: Run as an unprivileged (non-root) user?

    To run Salt as another user, specify ``--user`` in the command
    line or assign ``user`` in the
    :doc:`configuration file</ref/configuration/master>`.


There is also a full :doc:`troubleshooting guide</topics/troubleshooting/index>`
available.

Manage Salt public keys
=======================

Salt manages authentication with RSA public keys. The keys are managed on the
:term:`master` via the :command:`salt-key` command. Once a :term:`minion`
checks into the master the master will save a copy of the minion key. Before
the master can send commands to the minion the key needs to be "accepted".

1.  List the accepted and unaccepted Salt keys::

        salt-key -L

2.  Accept a minion key::

        salt-key -a <minion id>

    or accept all unaccepted minion keys::

        salt-key -A

.. seealso:: :doc:`salt-key manpage </ref/cli/salt-key>`
