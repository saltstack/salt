===============
``salt-syndic``
===============

The Salt syndic daemon, a special minion that passes through commands from a
higher master

Synopsis
========

salt-syndic [ options ]

Description
===========

The Salt syndic daemon, a special minion that passes through commands from a
higher master.

Options
=======

.. program:: salt-syndic

.. option:: -h, --help

    Print a usage message briefly summarizing these command-line options.

.. option:: -d, --daemon

    Run the Salt syndic as a daemon

.. option:: --pid-file PIDFILE

    Specify the location of the pidfile

.. option:: --version

    Show program's version number and exit

.. option:: --versions-report

    Show program's dependencies version number and exit

.. option:: -c CONFIG_DIR, --config-dir=CONFIG_dir

    The location of the Salt configuration directory, this directory contains
    the configuration files for Salt master and minions. The default location
    on most systems is /etc/salt.

See also
========

:manpage:`salt(1)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
