===============
``salt-syndic``
===============

The Salt syndic daemon, a special minion that passes through commands from a
higher master

Synopsis
========

.. code-block:: bash

    salt-syndic [ options ]

Description
===========

The Salt syndic daemon, a special minion that passes through commands from a
higher master.

Options
=======

.. program:: salt-syndic

.. include:: _includes/common-options.rst

.. include:: _includes/daemon-options.rst
.. |salt-daemon| replace:: salt-syndic

.. include:: _includes/logging-options.rst
.. |logfile| replace:: /var/log/salt/master
.. |loglevel| replace:: ``warning``


See also
========

:manpage:`salt(1)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
