===========
``salt-cp``
===========

Copy a file or files to one or more minions

Synopsis
========

.. code-block:: bash

    salt-cp '*' [ options ] SOURCE [SOURCE2 SOURCE3 ...] DEST

    salt-cp -E '.*' [ options ] SOURCE [SOURCE2 SOURCE3 ...] DEST

    salt-cp -G 'os:Arch.*' [ options ] SOURCE [SOURCE2 SOURCE3 ...] DEST

Description
===========

salt-cp copies files from the master to all of the Salt minions matched by the
specified target expression.

.. note::
    salt-cp uses Salt's publishing mechanism. This means the privacy of the
    contents of the file on the wire is completely dependent upon the transport
    in use. In addition, if the master or minion is running with debug logging,
    the contents of the file will be logged to disk.

    In addition, this tool is less efficient than the Salt fileserver when
    copying larger files. It is recommended to instead use
    :py:func:`cp.get_file <salt.modules.cp.get_file>` to copy larger files to
    minions. However, this requires the file to be located within one of the
    fileserver directories.

.. versionchanged:: 2016.3.7,2016.11.6,2017.7.0
    Compression support added, disable with ``-n``. Also, if the destination
    path ends in a path separator (i.e. ``/``,  or ``\`` on Windows, the
    desitination will be assumed to be a directory. Finally, recursion is now
    supported, allowing for entire directories to be copied.

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


.. option:: -n, --no-compression

    Disable gzip compression.

    .. versionadded:: 2016.3.7,2016.11.6,2017.7.0

See also
========

:manpage:`salt(1)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
