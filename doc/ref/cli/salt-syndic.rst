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

.. option:: --master-config=MASTER_CONFIG

    The master configuration file to use, the default is /etc/salt/master

.. option:: --minion-config=MINION_CONFIG

    The minion configuration file to use, the default is /etc/salt/minion

See also
========

:manpage:`salt(1)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
