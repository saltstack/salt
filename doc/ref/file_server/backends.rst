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

Just as the order of the values in :conf_master:`fileserver_backend` matters,
so too does the order in which different sources are defined within a
fileserver environment. For example, given the below :conf_master:`file_roots`
configuration, if both ``/srv/salt/dev/foo.txt`` and ``/srv/salt/prod/foo.txt``
exist on the Master, then ``salt://foo.txt`` would point to
``/srv/salt/dev/foo.txt`` in the ``dev`` environment, but it would point to
``/srv/salt/prod/foo.txt`` in the ``base`` environment.

.. code-block:: yaml

    file_roots:
      base:
        - /srv/salt/prod
      qa:
        - /srv/salt/qa
        - /srv/salt/prod
      dev:
        - /srv/salt/dev
        - /srv/salt/qa
        - /srv/salt/prod

Similarly, when using the :mod:`git <salt.fileserver.gitfs>` backend, if both
repositories defined below have a ``hotfix23`` branch/tag, and both of them
also contain the file ``bar.txt`` in the root of the repository at that
branch/tag, then ``salt://bar.txt`` in the ``hotfix23`` environment would be
served from the ``first`` repository.

.. code-block:: yaml

    gitfs_remotes:
      - https://mydomain.tld/repos/first.git
      - https://mydomain.tld/repos/second.git

.. note::

    Environments map differently based on the fileserver backend. For instance,
    the mappings are explicitly defined in :mod:`roots <salt.fileserver.roots>`
    backend, while in the VCS backends (:mod:`git <salt.fileserver.gitfs>`,
    :mod:`hg <salt.fileserver.hgfs>`, :mod:`svn <salt.fileserver.svnfs>`) the
    environments are created from branches/tags/bookmarks/etc. For the
    :mod:`minion <salt.fileserver.minionfs>` backend, the files are all in a
    single environment, which is specified by the :conf_master:`minionfs_env`
    option.

    See the documentation for each backend for a more detailed explanation of
    how environments are mapped.
