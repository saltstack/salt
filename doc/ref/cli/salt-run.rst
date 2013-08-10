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

.. include:: _includes/common-options.rst

.. include:: _includes/logging-options.rst
.. |logfile| replace:: /var/log/salt/master
.. |loglevel| replace:: ``warning``


See also
========

:manpage:`salt(1)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
