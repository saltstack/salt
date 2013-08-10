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

.. option:: -t TIMEOUT, --timeout=TIMEOUT

    The timeout in seconds to wait for replies from the Salt minions. The
    timeout number specifies how long the command line client will wait to
    query the minions and check on running jobs.

.. include:: _includes/target-selection.rst

.. option:: --return

    Chose an alternative returner to call on the minion, if an alternative
    returner is used then the return will not come back to the command line
    but will be sent to the specified return system.

.. include:: _includes/logging-options.rst
.. |logfile| replace:: /var/log/salt/ssh
.. |loglevel| replace:: ``warning``

.. include:: _includes/output-options.rst


See also
========

:manpage:`salt(7)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
