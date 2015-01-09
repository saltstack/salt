===========
``salt-cp``
===========

Copy a file to a set of systems

Synopsis
========

.. code-block:: bash

    salt-cp '*' [ options ] SOURCE DEST

    salt-cp -E '.*' [ options ] SOURCE DEST

    salt-cp -G 'os:Arch.*' [ options ] SOURCE DEST

Description
===========

Salt copy copies a local file out to all of the Salt minions matched by the
given target.

Options
=======

.. program:: salt-cp

.. include:: _includes/common-options.rst

.. include:: _includes/timeout-option.rst
.. |timeout| replace:: 5

.. include:: _includes/logging-options.rst
.. |logfile| replace:: /var/log/salt/master
.. |loglevel| replace:: ``warning``

.. include:: _includes/target-selection.rst


See also
========

:manpage:`salt(1)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`