.. _tutorial-minionfs:

============================
MinionFS Backend Walkthrough
============================

.. versionadded:: 2014.1.0

.. note::

    This walkthrough assumes basic knowledge of Salt and :mod:`cp.push
    <salt.modules.cp.push>`. To get up to speed, check out the
    :ref:`Salt Walkthrough <tutorial-salt-walk-through>`.

Sometimes it is desirable to deploy a file located on one minion to one or more
other minions. This is supported in Salt, and can be accomplished in two parts:

#. Minion support for pushing files to the master (using :py:func:`cp.push
   <salt.modules.cp.push>`)

#. The :mod:`minionfs <salt.fileserver.minionfs>` fileserver backend


This walkthrough will show how to use both of these features.


Enabling File Push
==================

To set the master to accept files pushed from minions, the
:conf_master:`file_recv` option in the master config file must be set to
``True`` (the default is ``False``).

.. code-block:: yaml

    file_recv: True

.. note::
    This change requires a restart of the salt-master service.

Pushing Files
=============

Once this has been done, files can be pushed to the master using the
:py:func:`cp.push <salt.modules.cp.push>` function:

.. code-block:: bash

    salt 'minion-id' cp.push /path/to/the/file

This command will store the file in a subdirectory named ``minions`` under the
master's :conf_master:`cachedir`. On most masters, this path will be
``/var/cache/salt/master/minions``. Within this directory will be one directory
for each minion which has pushed a file to the master, and underneath that the
full path to the file on the minion. So, for example, if a minion with an ID of
``dev1`` pushed a file ``/var/log/myapp.log`` to the master, it would be saved
to ``/var/cache/salt/master/minions/dev1/var/log/myapp.log``.

Serving Pushed Files Using MinionFS
===================================

While it is certainly possible to add ``/var/cache/salt/master/minions`` to the
master's :conf_master:`file_roots` and serve these files, it may only be
desirable to expose files pushed from certain minions. Adding
``/var/cache/salt/master/minions/<minion-id>`` for each minion that needs to be
exposed can be cumbersome and prone to errors.

Enter :mod:`minionfs <salt.fileserver.minionfs>`. This fileserver backend will
make files pushed using :py:func:`cp.push <salt.modules.cp.push>` available to
the Salt fileserver, and provides an easy mechanism to restrict which minions'
pushed files are made available.

Simple Configuration
--------------------

To use the :mod:`minionfs <salt.fileserver.minionfs>` backend, add ``minionfs``
to the list of backends in the :conf_master:`fileserver_backend` configuration
option on the master:

.. code-block:: yaml

    file_recv: True

    fileserver_backend:
      - roots
      - minionfs

.. note::
    ``minion`` also works here. Prior to the 2018.3.0 release, *only*
    ``minion`` would work.

    Also, as described earlier, ``file_recv: True`` is needed to enable the
    master to receive files pushed from minions. As always, changes to the
    master configuration require a restart of the ``salt-master`` service.

Files made available via :mod:`minionfs <salt.fileserver.minionfs>` are by
default located at ``salt://<minion-id>/path/to/file``. Think back to the
earlier example, in which ``dev1`` pushed a file ``/var/log/myapp.log`` to the
master. With :mod:`minionfs <salt.fileserver.minionfs>` enabled, this file
would be addressable in Salt at ``salt://dev1/var/log/myapp.log``.

If many minions have pushed to the master, this will result in many directories
in the root of the Salt fileserver. For this reason, it is recommended to use
the :conf_master:`minionfs_mountpoint` config option to organize these files
underneath a subdirectory:

.. code-block:: yaml

    minionfs_mountpoint: salt://minionfs

Using the above mountpoint, the file in the example would be located at
``salt://minionfs/dev1/var/log/myapp.log``.


Restricting Certain Minions' Files from Being Available Via MinionFS
--------------------------------------------------------------------

A whitelist and blacklist can be used to restrict the minions whose pushed
files are available via :mod:`minionfs <salt.fileserver.minionfs>`. These lists
can be managed using the :conf_master:`minionfs_whitelist` and
:conf_master:`minionfs_blacklist` config options. Click the links for both of
them for a detailed explanation of how to use them.

A more complex configuration example, which uses both a whitelist and
blacklist, can be found below:

.. code-block:: yaml

    file_recv: True

    fileserver_backend:
      - roots
      - minionfs

    minionfs_mountpoint: salt://minionfs

    minionfs_whitelist:
      - host04
      - web*
      - 'mail\d+\.domain\.tld'

    minionfs_blacklist:
      - web21

Potential Concerns
------------------

* There is no access control in place to restrict which minions have access to
  files served up by :mod:`minionfs <salt.fileserver.minionfs>`. All minions
  will have access to these files.

* Unless the :conf_master:`minionfs_whitelist` and/or
  :conf_master:`minionfs_blacklist` config options are used, all minions which
  push files to the master will have their files made available via
  :mod:`minionfs <salt.fileserver.minionfs>`.
