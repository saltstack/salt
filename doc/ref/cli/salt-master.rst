===============
``salt-master``
===============

The Salt master daemon, used to control the Salt minions

Synopsis
========

.. code-block:: bash

    salt-master [ options ]

Description
===========

The master daemon controls the Salt minions

Options
=======

.. program:: salt-master

.. include:: _includes/common-options.rst

.. include:: _includes/daemon-options.rst
.. |salt-daemon| replace:: salt-master

.. include:: _includes/logging-options.rst
.. |logfile| replace:: /var/log/salt/master
.. |loglevel| replace:: ``warning``


See also
========

:manpage:`salt(1)`
:manpage:`salt(7)`
:manpage:`salt-minion(1)`