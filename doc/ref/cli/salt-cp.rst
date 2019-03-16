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

.. versionchanged:: 2016.11.7,2017.7.2
    Reverted back to the old copy mode to preserve backward compatibility. The
    new functionality added in 2016.6.6 and 2017.7.0 is now available using the
    ``-C`` or ``--chunked`` CLI arguments. Note that compression, recursive
    copying, and support for copying large files is only available in chunked
    mode.

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


.. option:: -C, --chunked

    Use new chunked mode to copy files. This mode supports large files, recursive
    directories copying and compression.

    .. versionadded:: 2016.11.7,2017.7.2

.. option:: -n, --no-compression

    Disable gzip compression in chunked mode.

    .. versionadded:: 2016.3.7,2016.11.6,2017.7.0

See also
========

:manpage:`salt(1)`
:manpage:`salt-master(1)`
:manpage:`salt-minion(1)`
