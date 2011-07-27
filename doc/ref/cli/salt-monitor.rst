===============
``salt-monitor``
===============

The salt monitor daemon periodically runs commands and reacts to their output

Synopsis
========

salt-monitor [ options ]

Description
===========

The salt monitor daemon periodically runs salt commands configured in /etc/salt/minion and reacts to their output.

Options
=======

.. program:: salt-monitor

.. option:: -h, --help

    Print a usage message briefly summarizing these command-line options.

.. option:: -d, --daemon

    Run the salt monitor as a daemon

.. option:: -c CONFIG, --config=CONFIG

    The monitor configuration file to use, the default is /etc/salt/minion
