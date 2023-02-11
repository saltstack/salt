============
``salt-api``
============

Start interfaces used to remotely connect to the salt master

Synopsis
========

.. code-block:: bash

    salt-api

Description
===========

The Salt API system manages network api connectors for the Salt Master

Options
=======

.. program:: salt-api

.. include:: _includes/common-options.rst

.. option:: -d, --daemon

    Run the salt-api as a daemon

.. option:: --pid-file=PIDFILE

    Specify the location of the pidfile. Default: /var/run/salt-api.pid

.. include:: _includes/logging-options.rst
.. |logfile| replace:: /var/log/salt/api
.. |loglevel| replace:: ``warning``

See also
========

:manpage:`salt-api(7)`
:manpage:`salt(7)`
:manpage:`salt-master(1)`
