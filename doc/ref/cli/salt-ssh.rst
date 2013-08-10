============
``salt-ssh``
============

Synopsis
========

    salt-ssh '*' [ options ] sys.doc

    salt-ssh -E '.*' [ options ] sys.doc cmd

Description
===========

Salt ssh allows for salt routines to be executed using only ssh for transport

Options
=======

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
