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

.. program:: salt-run

.. option:: -h, --help

    Print a usage message briefly summarizing these command-line options

.. option:: --version

    Show program's version number and exit

.. option:: --versions-report

    Show program's dependencies version number and exit

.. option:: -c CONFIG_DIR, --config-dir=CONFIG_dir

    The location of the Salt configuration directory, this directory contains
    the configuration files for Salt master and minions. The default location
    on most systems is /etc/salt.


.. include:: _includes/logging-options.rst
.. |logfile| replace:: /var/log/salt/master
.. |loglevel| replace:: ``warning``


See also
========

:manpage:`salt(1)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
