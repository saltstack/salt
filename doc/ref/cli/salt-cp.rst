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

Note: salt-cp uses salt's publishing mechanism. This means the privacy of the
contents of the file on the wire is completely dependent upon the transport
in use. In addition, if the salt-master is running with debug logging it is
possible that the contents of the file will be logged to disk.

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
