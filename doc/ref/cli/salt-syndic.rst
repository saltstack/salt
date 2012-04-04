===============
``salt-syndic``
===============

The salt syndic daemon, a special minion that passes through commands from a
higher master

Synopsis
========

salt-syndic [ options ]

Description
===========

The salt syndic daemon, a special minion that passes through commands from a
higher master.

Options
=======

.. program:: salt-syndic

.. option:: -h, --help

    Print a usage message briefly summarizing these command-line options.

.. option:: -d, --daemon

    Run the salt syndic as a daemon

.. option:: --pid-file PIDFILE

    Specify the location of the pidfile

.. option:: --master-config=MASTER_CONFIG

    The master configuration file to use, the default is /etc/salt/master

.. option:: --minion-config=MINION_CONFIG

    The minion configuration file to use, the default is /etc/salt/minion
