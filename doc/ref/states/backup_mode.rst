==================
State File Backups
==================

In 0.10.2 a new feature was added for backing up files that are replaced by
the file.managed and file.recurse states. The new feature is called the backup
mode. Setting the backup mode is easy, but is can be set in a number of
places.

The backup_mode can be set in the minion config file:

.. code-block:: yaml

    backup_mode: minion

Or it can be set for each file:

.. code-block:: yaml

    /etc/ssh/sshd_config:
      file.managed:
        - source: salt://ssh/sshd_config
        - backup: minion

Backed up Files
===============

The files will be saved in the minion cachedir under the directory named
``file_backup``. The files will be in the location relative to where they
were under the root filesystem and be appended with a timestamp. This should
make them easy to browse.
