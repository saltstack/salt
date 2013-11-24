============
``salt-ssh``
============

Synopsis
========

    salt-ssh '*' [ options ] sys.doc

    salt-ssh -E '.*' [ options ] sys.doc cmd

Description
===========

Salt SSH allows for salt routines to be executed using only SSH for transport

Options
=======

.. option:: -r, --raw, --raw-shell

    Execute a raw shell command.

.. option:: --roster-file

    Define which roster system to use, this defines if a database backend,
    scanner, or custom roster system is used. Default is the flat file roster.

.. option:: --refresh, --refresh-cache

    Force a refresh of the master side data cache of the target's data. This
    is needed if a target's grains have been changed and the auto refresh
    timeframe has not been reached.

.. option:: --max-procs

    Set the number of concurrent minions to communicate with. This value
    defines how many processes are opened up at a time to manage connections,
    the more running process the faster communication should be, default
    is 25.

.. option:: --passwd

    Set te default password to attempt to use when authenticating.

.. option:: --key-deploy

   Set this flag to attempt to deploy the authorized ssh key with all
   minions. This combined with --passwd can make initial deployment of keys
   very fast and easy.

.. program:: salt

.. include:: _includes/common-options.rst

.. include:: _includes/target-selection.rst

.. include:: _includes/logging-options.rst
.. |logfile| replace:: /var/log/salt/ssh
.. |loglevel| replace:: ``warning``

.. include:: _includes/output-options.rst


See also
========

:manpage:`salt(7)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
