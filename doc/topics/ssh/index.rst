========
Salt SSH
========

.. note::

    SALT-SSH IS ALPHA SOFTWARE AND MAY NOT BE READY FOR PRODUCTION USE

.. note::

    On many systems, ``salt-ssh`` will be in its own package, usually named
    ``salt-ssh``.

In version 0.17.0 of Salt a new transport system was introduced, the ability
to use SSH for Salt communication. This addition allows for Salt routines to
be executed on remote systems entirely through ssh, bypassing the need for
a Salt Minion to be running on the remote systems and the need for a Salt
Master.

.. note::

    The Salt SSH system does not supercede the standard Salt communication
    systems, it simply offers an SSH based alternative that does not require
    ZeroMQ and a remote agent. Be aware that since all communication with Salt SSH is
    executed via SSH it is substantially slower than standard Salt with ZeroMQ.

Salt SSH is very easy to use, simply set up a basic `roster` file of the
systems to connect to and run ``salt-ssh`` commands in a similar way as
standard ``salt`` commands.

Salt SSH Roster
===============

The roster system in Salt allows for remote minions to be easily defined.

.. note::

    See the :doc:`Roster documentation </topics/ssh/roster>` for more details.

Simply create the roster file, the default location is `/etc/salt/roster`:

.. code-block:: yaml

    web1: 192.168.42.1

This is a very basic roster file where a Salt ID is being assigned to an IP
address. A more elaborate roster can be created:

.. code-block:: yaml

    web1:
      host: 192.168.42.1 # The IP addr or DNS hostname
      user: fred         # Remote executions will be executed as user fred
      passwd: foobarbaz  # The password to use for login, if omitted, keys are used
      sudo: True         # Whether to sudo to root, not enabled by default
    web2:
      host: 192.168.42.2

Calling Salt SSH
================

The ``salt-ssh`` command can be easily executed in the same was as a salt
command:

.. code-block:: bash

    salt-ssh '*' test.ping

Commands with ``salt-ssh`` follow the same syntax as the ``salt`` command.

The standard salt functions are available! The output is the same as ``salt``
and many of the same flags are available. Please see 
http://docs.saltstack.com/ref/cli/salt-ssh.html for all of the available
options.

Raw Shell Calls
---------------

By default ``salt-ssh`` runs Salt execution modules on the remote system,
but ``salt-ssh`` can also execute raw shell commands:

.. code-block:: bash

    salt-ssh '*' -r 'ifconfig'

States Via Salt SSH
===================

The Salt State system can also be used with ``salt-ssh``. The state system
abstracts the same interface to the user in ``salt-ssh`` as it does when using
standard ``salt``. The intent is that Salt Formulas defined for standard
``salt`` will work seamlessly with ``salt-ssh`` and vice-versa.

The standard Salt States walkthroughs function by simply replacing ``salt``
commands with ``salt-ssh``.

Targeting with Salt SSH
=======================

Due to the fact that the targeting approach differs in salt-ssh, only glob
and regex targets are supported as of this writing, the remaining target
systems still need to be implemented.

Running Salt SSH as non-root user
=================================

By default, Salt read all the configuration from /etc/salt/. If you are running
Salt SSH with a regular user you have to modify some paths or you will get
"Permission denied" messages. You have to modify two parameters: ``pki_dir``
and ``cachedir``. Those should point to a full path writable for the user.

It's recommed not to modify /etc/salt for this purpose. Create a private copy
of /etc/salt for the user and run the command with ``-c /new/config/path``.

