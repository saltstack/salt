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

.. option:: -d, --daemon

    Run the Salt master as a daemon

.. option:: -c CONFIG, --config=CONFIG

    The master configuration file to use, the default is /etc/salt/master

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
