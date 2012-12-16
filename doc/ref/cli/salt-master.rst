===============
``salt-master``
===============

The Salt master daemon, used to control the Salt minions

Synopsis
========

salt-master [ options ]

Description
===========

The master daemon controls the Salt minions

Options
=======

.. program:: salt-master

.. option:: -h, --help

    Print a usage message briefly summarizing these command-line options.

.. option:: --version

    Show program's version number and exit

.. option:: --versions-report

    Show program's dependencies version number and exit

.. option:: -d, --daemon

    Run the Salt master as a daemon

.. option:: -c CONFIG_DIR, --config-dir=CONFIG_dir

    The location of the Salt configuration directory, this directory contains
    the configuration files for Salt master and minions. The default location
    on most systems is /etc/salt.

.. option:: -u USER, --user=USER

    Specify user to run minion

.. option:: --pid-file PIDFILE

    Specify the location of the pidfile.

.. option:: -l LOG_LEVEL, --log-level=LOG_LEVEL

    Console log level. One of ``info``, ``none``, ``garbage``,
    ``trace``, ``warning``, ``error``, ``debug``. For the logfile
    settings see the config file. Default: ``warning``.

See also
========

:manpage:`salt(1)`
:manpage:`salt(7)`
:manpage:`salt-minion(1)`
