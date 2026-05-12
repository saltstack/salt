===============
``salt-minion``
===============

The Salt minion daemon, receives commands from a remote Salt master.

Synopsis
========

.. code-block:: bash

    salt-minion [ options ]

Description
===========

The Salt minion receives commands from the central Salt master and replies with
the results of said commands.

Options
=======

.. program:: salt-minion

.. include:: _includes/common-options.rst

.. include:: _includes/daemon-options.rst
.. |salt-daemon| replace:: salt-minion

.. include:: _includes/logging-options.rst
.. |logfile| replace:: /var/log/salt/minion
.. |loglevel| replace:: ``warning``


See also
========

:manpage:`salt(1)`
:manpage:`salt(7)`
:manpage:`salt-master(1)`
