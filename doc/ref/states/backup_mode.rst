==================
File State Backups
==================

In 0.10.2 a new feature was added for backing up files that are replaced by
the file.managed and file.recurse states. The new feature is called the backup
mode. Setting the backup mode is easy, but it can be set in a number of
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

Backed-up Files
===============

The files will be saved in the minion cachedir under the directory named
``file_backup``. The files will be in the location relative to where they
were under the root filesystem and be appended with a timestamp. This should
make them easy to browse.

Interacting with Backups
========================

Starting with version 0.17.0, it will be possible to list, restore, and delete
previously-created backups.

Listing
-------

The backups for a given file can be listed using :mod:`file.list_backups
<salt.modules.file.list_backups>`:

.. code-block:: bash

    # salt foo.bar.com file.list_backups /tmp/foo.txt
    foo.bar.com:
        ----------
        0:
            ----------
            Backup Time:
                Sat Jul 27 2013 17:48:41.738027
            Location:
                /var/cache/salt/minion/file_backup/tmp/foo.txt_Sat_Jul_27_17:48:41_738027_2013
            Size:
                13
        1:
            ----------
            Backup Time:
                Sat Jul 27 2013 17:48:28.369804
            Location:
                /var/cache/salt/minion/file_backup/tmp/foo.txt_Sat_Jul_27_17:48:28_369804_2013
            Size:
                35

Restoring
---------

Restoring is easy using :mod:`file.restore_backup
<salt.modules.file.restore_backup>`, just pass the path and the numeric id
found with :mod:`file.list_backups <salt.modules.file.list_backups>`:

.. code-block:: bash

    # salt foo.bar.com file.restore_backup /tmp/foo.txt 1
    foo.bar.com:
        ----------
        comment:
            Successfully restored /var/cache/salt/minion/file_backup/tmp/foo.txt_Sat_Jul_27_17:48:28_369804_2013 to /tmp/foo.txt
        result:
            True

The existing file will be backed up, just in case, as can be seen if
:mod:`file.list_backups <salt.modules.file.list_backups>` is run again:

.. code-block:: bash

    # salt foo.bar.com file.list_backups /tmp/foo.txt
    foo.bar.com:
        ----------
        0:
            ----------
            Backup Time:
                Sat Jul 27 2013 18:00:19.822550
            Location:
                /var/cache/salt/minion/file_backup/tmp/foo.txt_Sat_Jul_27_18:00:19_822550_2013
            Size:
                53
        1:
            ----------
            Backup Time:
                Sat Jul 27 2013 17:48:41.738027
            Location:
                /var/cache/salt/minion/file_backup/tmp/foo.txt_Sat_Jul_27_17:48:41_738027_2013
            Size:
                13
        2:
            ----------
            Backup Time:
                Sat Jul 27 2013 17:48:28.369804
            Location:
                /var/cache/salt/minion/file_backup/tmp/foo.txt_Sat_Jul_27_17:48:28_369804_2013
            Size:
                35

.. note::
    Since no state is being run, restoring a file will not trigger any watches
    for the file. So, if you are restoring a config file for a service, it will
    likely still be necessary to run a ``service.restart``.

Deleting
--------

Deleting backups can be done using :mod:`file.delete_backup
<salt.modules.file.delete_backup>`:

.. code-block:: bash

    # salt foo.bar.com file.delete_backup /tmp/foo.txt 0
    foo.bar.com:
        ----------
        comment:
            Successfully removed /var/cache/salt/minion/file_backup/tmp/foo.txt_Sat_Jul_27_18:00:19_822550_2013
        result:
            True