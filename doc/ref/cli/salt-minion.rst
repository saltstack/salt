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

.. include:: _includes/common-options.rst

.. option:: -d, --daemon

    Run the Salt minion as a daemon

.. option:: -u USER, --user=USER

    Specify user to run minion

.. option:: --pid-file PIDFILE

    Specify the location of the pidfile

.. include:: _includes/logging-options.rst
.. |logfile| replace:: /var/log/salt/minion
.. |loglevel| replace:: ``warning``


See also
========

:manpage:`salt(1)`
:manpage:`salt(7)`
:manpage:`salt-master(1)`
