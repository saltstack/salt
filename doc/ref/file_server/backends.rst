.. _file-server-backends:

====================
File Server Backends
====================

In Salt 0.12.0, the modular fileserver was introduced. This feature added the
ability for the Salt Master to integrate different file server backends. File
server backends allow the Salt file server to act as a transparent bridge to
external resources. A good example of this is the :mod:`git
<salt.fileserver.git>` backend, which allows Salt to serve files sourced from
one or more git repositories, but there are several others as well. Click
:ref:`here <all-salt.fileserver>` for a full list of Salt's fileserver
backends.

Enabling a Fileserver Backend
-----------------------------

Fileserver backends can be enabled with the :conf_master:`fileserver_backend`
option.

.. code-block:: yaml

    fileserver_backend:
      - git

See the :ref:`documentation <all-salt.fileserver>` for each backend to find the
correct value to add to :conf_master:`fileserver_backend` in order to enable
them.

Using Multiple Backends
-----------------------

If :conf_master:`fileserver_backend` is not defined in the Master config file,
Salt will use the :mod:`roots <salt.fileserver.roots>` backend, but the
:conf_master:`fileserver_backend` option supports multiple backends. When more
than one backend is in use, the files from the enabled backends are merged into a
single virtual filesystem. When a file is requested, the backends will be
searched in order for that file, and the first backend to match will be the one
which returns the file.

.. code-block:: yaml

    fileserver_backend:
      - roots
      - git

With this configuration, the environments and files defined in the
:conf_master:`file_roots` parameter will be searched first, and if the file is
not found then the git repositories defined in :conf_master:`gitfs_remotes`
will be searched.

Environments
------------

The concept of environments is followed in all backend systems. The
environments in the classic :mod:`roots <salt.fileserver.roots>` backend are
defined in the :conf_master:`file_roots` option. Environments map differently
based on the backend, for instance the git backend translated branches and tags
in git to environments. This makes it easy to define environments in git by
just setting a tag or forking a branch.
