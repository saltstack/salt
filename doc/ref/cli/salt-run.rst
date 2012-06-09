============
``salt-run``
============

Execute a Salt runner

Synopsis
========

::

    salt-run RUNNER

Description
===========

salt-run is the frontend command for executing ``Salt Runners``.
Salt runners are simple modules used to execute convenience functions on the
master

Options
=======

.. program:: salt-cp

.. option:: -h, --help

    Print a usage message briefly summarizing these command-line options

.. option:: -c CONFIG, --config=CONFIG

    The location of the Salt master configuration file, the Salt master
    settings are required to know where the connections are;
    default=/etc/salt/master

See also
========

:manpage:`salt(1)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
