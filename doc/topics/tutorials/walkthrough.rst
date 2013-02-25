======================
Salt Stack Walkthrough
======================

Welcome!
========

Welcome to Salt Stack! I am excited that you are interested in Salt and
starting down the path to better infrastructure management. I developed
(and am continuing to develop) Salt with the goal of making the best
software available to manage computers of almost any kind. I hope you enjoy
working with Salt and that the software can solve your real world needs!

- Thomas S Hatch
  Salt creator and chief developer
  CTO of Salt Stack, Inc.


Getting Started
===============

What is Salt?
-------------

Salt is a different approach to infrastructure management, it is founded on
the idea that high speed communication with large numbers of systems can open
up new capabilities. This approach makes Salt a powerful multitasking system
that can solve many specific problems in an infrastructure. The backbone of
Salt is the remote execution engine, which creates a high speed, secure,
bi-directional communication net for groups of systems. On top of this
communication system Salt provides an extremely fast, flexible, easy to use
configuration management system called ``Salt States``.

This unique approach to management makes for a transparent control system that
is not only amazingly easy to set up and use, but also capable of solving very
complex problems in infrastructures, as will be explored in this walk through.

Salt is being used today by some of the largest infrastructures in the world
and has proven an ability to scale to astounding proportions without
modification. With the proven ability to scale out well beyond many tens of
thousands of servers, Salt has also proven to be an excellent choice for small
deployments as well, lowering compute and management overhead for
infrastructures as small as just a few systems.

Installing Salt
---------------

Salt Stack has been made to be very easy to install and get started. Setting
up Salt should be as easy as installing Salt via distribution packages on Linux
or via the Windows installer. The installation documents covers specific platform
installation in depth:

:doc:`Instalation </topics/instilation>`

Starting Salt
-------------

Salt functions on a master/minion topology. A master server serves as a
central control bus for the clients (called minions), and the minions connect
back to the master.

Setting Up the Salt Master
~~~~~~~~~~~~~~~~~~~~~~~~~~

Turning on the Salt Master is easy, just turn it on! The default configuration
is suitable for the vast majority of installations. The Salt master can be
controlled by the local Linux/Unix service manager:

On Systemd based platforms (OpenSuse, Fedora):

    # systemctl start salt-master

On Upstart based systems (Ubuntu, older Fedora/RHEL):

    # service salt-master start

On SysV Init systems (Debian, Gentoo etc.):

    # /etc/init.d/salt-master start

Or the master can be started directly on the command line:

    # salt-master -d

The Salt Master can also be started in the foreground in debug mode, this
greatly increases the command output:

    # salt-master -l debug

The Salt Master needs to bind to 2 tcp network ports on the system, these ports
are 4505 and 4506. For more in depth information on fire walling these ports
the firewall tutorial is available:

    :doc:`Firewalling the Salt Master </topics/tutorials/firewall>`

Setting up a Salt Minion
~~~~~~~~~~~~~~~~~~~~~~~~

.. note::

    The Salt Minion can operate with or without a Salt Master. This walkthrough
    assumes that the minion will be connected to the master, for information on
    how to run a masterless minion please see the masterless quickstart guide:

        :doc:`Masterless Minon Quickstart </topics/tutorials/quickstart>`

The Salt Minion only needs to be aware of one piece of information to run, the
network location of the master. By default the minion will look for the DNS
name `salt` for the master, making the easiest approach to set internal DNS to
resolve the name `salt` back to the Salt Master IP. Otherwise the minion
configuration file will need to be edited, edit the configuration option
``master`` to point to the DNS name or the IP of the Salt Master:

.. note::

    The default location of the configuration files is /etc/salt, most
    platforms adhere to this convention, but platforms such as FreeBSD and
    Microsoft Windows place this file in different locations.

/etc/salt/minion
.. code-block:: yaml

    master: saltmaster.example.com

Now that the master can be found start up the minion in the same way as the
master, with the platform init system, or via the command line directly:

As a daemon:

    # salt-minion -d

In the foreground in debug mode:

    # salt-minion -l debug

Now that the minion is started it will generate cryptographic keys and attempt
to connect to the master. The next step is to venture back to the master server
and accept the new minion's public key.

Using Salt Key
~~~~~~~~~~~~~~

Salt authenticates minions using public key encryption and authentication. For
a minion to start accepting commands from the master the minion keys need to be
accepted. The ``salt-key`` command is used manage all of the keys on the
master. To list the keys that are on the master run a salt-key list command:

    # salt-key -L

The keys that have been rejected, accepted and pending acceptance are listed.
The easiest way to accept the minion key is to just accept all pending keys:

    # salt-key -A

.. note::

    Keys should be verified!! The secure thing to do is to run salt-key -P to
    verify that the keys on the master match the generated keys on the
    minions.

Sending the First Commands
--------------------------

Now that the minion is connected to the master and authenticated, the master 
can start to command the minion. Salt commands allow for a vast set of
functions to be executed and for specific minions and groups of minions to be
targeted for execution. This makes the ``salt`` command very powerful, but
the command is also very usable, and easy to understand.

The ``salt`` command is comprised of command options, target specification,
the function to execute, and arguments to the function. A simple command to
start with looks like this:

    # salt \* test.ping

The `\*` is the target, which specifies all minions, and `test.ping` tells the
minion to run the test.ping function. This ``salt`` command will tell all of
the minions to execute the `test.ping` in parallel and return the result.

.. note::

    All of the minions register themselves with a unique minion `id`, these
    ids default to the minion hostname, but can be explicitly defined in the
    minion config as well.

Getting to Know the Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Salt comes with a vast library of functions available for execution, and Salt
functions are self documenting. To see what functions are available on the
minions execute the `sys.doc` function:

    # salt \* sys.doc

This will display a very large list of available functions and documentation
on them, this documentation is also available online:

    :doc:`Full List of Execution Modules</ref/modules>`

These functions cover everything from shelling out to package management to
manipulating database servers. These functions comprise a powerful system
management API which is the backbone to Salt configuration management and many
other aspects of Salt.

.. note::

    Salt comes with many plugin systems, the functions that are available
    via the salt command are called `Execution Modules`.

Some Functions to Know
~~~~~~~~~~~~~~~~~~~~~~

Some functions to be familiar with are around basic system management. Functions
to shell out on minions such as ``cmd.run`` and ``cmd.run_all``:

    # salt \* cmd.run 'ls -l /etc'

The pkg functions will automatically map local system package managers to the
same salt functions. This means that ``pkg.install`` will wrap to installing
packages via yum on Red Hat based systems and apt on Debian systems etc.

    # salt \* pkg.install vim
