===============
``salt-minion``
===============

The Salt minion daemon, receives commands from a remote Salt master.

Synopsis
========

salt-minion [ options ]

Description
===========

The Salt minion receives commands from the central Salt master and replies with
the results of said commands.

Options
=======

.. program:: salt-minion

.. option:: -h, --help

    Print a usage message briefly summarizing these command-line options.

.. option:: -d, --daemon

    Run the Salt minion as a daemon

.. option:: -c CONFIG_DIR, --config-dir=CONFIG_dir

    The location of the Salt configuration directory, this directory contains
    the configuration files for Salt master and minions. The default location
    on most systems is /etc/salt.

.. option:: -u USER, --user=USER

    Specify user to run minion

.. option:: --pid-file PIDFILE

    Specify the location of the pidfile

.. option:: -l LOG_LEVEL, --log-level=LOG_LEVEL

    Console log level. One of ``info``, ``none``, ``garbage``,
    ``trace``, ``warning``, ``error``, ``debug``. For the logfile
    settings see the config file. Default: ``warning``.

.. option:: --version

    Show program's version number and exit

.. option:: --versions-report

    Show program's dependencies version number and exit

See also
========

:manpage:`salt(1)`
:manpage:`salt(7)`
:manpage:`salt-master(1)`
