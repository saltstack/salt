===============
``salt-minion``
===============

The salt minion daemon, recieves commands from a remote salt master.

Synopsis
========

salt-minion [ options ]

Description
===========

The salt minion recieves commands from the central salt master and replies with
the results of said commands.

Options
=======

.. program:: salt-minion

.. option:: -h, --help

    Print a usage message briefly summarizing these command-line options.

.. option:: -d, --daemon

    Run the salt minion as a daemon

.. option:: -c CONFIG, --config=CONFIG

    The minion configuration file to use, the default is /etc/salt/minion
