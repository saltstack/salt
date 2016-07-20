.. _salt-proxy-cli:

==============
``salt-proxy``
==============

Receives commands from a Salt master and proxies these commands to
devices that are unable to run a full minion.

Synopsis
========

.. code-block:: bash

    salt-proxy [ options ]

Description
===========

The Salt proxy minion receives commands from a Salt master, transmits
appropriate commands to devices that are unable to run a minion, and replies
with the results of said commands.

Options
=======

.. program:: salt-proxy

.. option:: --proxyid

    The minion id that this proxy will assume.  This is required.

.. option:: --version

    Print the version of Salt that is running.

.. option:: --versions-report

    Show program's dependencies and version number, and then exit

.. option:: -h, --help

   Show the help message and exit

.. option:: -c CONFIG_DIR, --config-dir=CONFIG_dir

   The location of the Salt configuration directory. This directory
   contains  the  configuration  files for Salt master and minions.
   The default location on most systems is ``/etc/salt``.

.. option:: -u USER, --user=USER

   Specify user to run salt-proxy

.. option:: -d, --daemon

   Run salt-proxy as a daemon

.. option:: --pid-file PIDFILE

   Specify the location of the pidfile. Default: ``/var/run/salt-proxy-<id>.pid``

.. include:: _includes/logging-options.rst
.. |logfile| replace:: /var/log/salt/minion
.. |loglevel| replace:: ``warning``

See also
========

:manpage:`salt(1)`
:manpage:`salt(7)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
