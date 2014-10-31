========
Salt SSH
========

.. note::

    Salt ssh is considered production ready in version 2014.7.0

.. note::

    On many systems, the ``salt-ssh`` executable will be in its own package, usually named
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

.. note::

    The Salt SSH eventually is supposed to support the same set of commands and 
    functionality as standard ``salt`` command. 
    
    At the moment fileserver operations must be wrapped to ensure that the 
    relevant files are delivered with the ``salt-ssh`` commands. 
    The state module is an exception, which compiles the state run on the 
    master, and in the process finds all the references to ``salt://`` paths and 
    copies those files down in the same tarball as the state run. 
    However, needed fileserver wrappers are still under development.

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
      
.. note::

    sudo works only if NOPASSWD is set for user in /etc/sudoers:
    ``fred ALL=(ALL) NOPASSWD: ALL`` 

Calling Salt SSH
================

The ``salt-ssh`` command can be easily executed in the same way as a salt
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

Configuring Salt SSH
====================

Salt SSH takes its configuration from a master configuration file. Normally, this
file is in ``/etc/salt/master``. If one wishes to use a customized configuration file,
the ``-c`` option to Salt SSH facilitates passing in a directory to look inside for a 
configuration file named ``master``.

Running Salt SSH as non-root user
=================================

By default, Salt read all the configuration from /etc/salt/. If you are running
Salt SSH with a regular user you have to modify some paths or you will get
"Permission denied" messages. You have to modify two parameters: ``pki_dir``
and ``cachedir``. Those should point to a full path writable for the user.

It's recommed not to modify /etc/salt for this purpose. Create a private copy
of /etc/salt for the user and run the command with ``-c /new/config/path``.

Define CLI Options with Saltfile
================================

If you are commonly passing in CLI options to ``salt-ssh``, you can create
a ``Saltfile`` to automatically use these options. This is common if you're
managing several different salt projects on the same server.

So if you ``cd`` into a directory with a Saltfile with the following
contents:

.. code-block:: yaml

    salt-ssh:
      config_dir: path/to/config/dir
      max_prox: 30

Instead of having to call
``salt-ssh --config-dir=path/to/config/dir --max-procs=30 \* test.ping`` you
can call ``salt-ssh \* test.ping``.

