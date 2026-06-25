=========================
File Server Configuration
=========================

The Salt file server is a high performance file server written in ZeroMQ. It
manages large files quickly and with little overhead, and has been optimized
to handle small files in an extremely efficient manner.

The Salt file server is an environment aware file server. This means that
files can be allocated within many root directories and accessed by
specifying both the file path and the environment to search. The
individual environments can span across multiple directory roots
to create overlays and to allow for files to be organized in many flexible
ways.

.. _file-roots-default-location:

Where should ``file_roots`` live?
=================================

The Salt default is:

.. code-block:: yaml

    file_roots:
      base:
        - /srv/salt

``/srv/salt`` is the recommended location because it follows the
`Filesystem Hierarchy Standard`_ ("``/srv`` contains site-specific data which
is served by this system") and keeps state content cleanly separated from
master configuration in ``/etc/salt``. Both pillar (``/srv/pillar``) and the
salt-ssh roster default to the same ``/srv/...`` parent, which makes backups
and version control straightforward.

Other layouts work, but each has trade-offs:

* **Putting ``file_roots`` inside ``/etc/salt``** mixes Salt's package-managed
  configuration with operator-managed state files. A package upgrade will
  not delete the directory, but auditing what changed and excluding it from
  configuration management is harder. Use a sibling directory if you need
  to keep states under ``/etc``.
* **A path under ``/opt`` or ``/var/lib``** is fine for hand-rolled
  deployments. ``/var/lib/salt`` is what you get with ``salt-call --local``
  on a system where ``/srv`` is not writable, and is the default the
  minionless installer uses on macOS.
* **Multiple roots** — list more than one directory per environment to
  layer files (see :ref:`Directory Overlay <file-roots-directory-overlay>`).

Some examples in the Salt documentation (notably the
:py:func:`netconfig.managed <salt.states.netconfig.managed>` state) show
``/etc/salt/states`` purely so the example fits in a single directory tree.
That is illustrative, not a recommendation — production deployments should
prefer ``/srv/salt``.

.. _Filesystem Hierarchy Standard: https://refspecs.linuxfoundation.org/FHS_3.0/fhs/ch03s17.html

Periodic Restarts
=================

The file server will restart periodically. The reason for this is to prevent any
files erver backends which may not properly handle resources from endlessly
consuming memory. A notable example of this is using a git backend with the
pygit2 library. How often the file server restarts can be controlled with the
``fileserver_interval`` in your master's config file.

Environments
============

The Salt file server defaults to the mandatory ``base`` environment. This
environment **MUST** be defined and is used to download files when no
environment is specified.

Environments allow for files and sls data to be logically separated, but
environments are not isolated from each other. This allows for logical
isolation of environments by the engineer using Salt, but also allows
for information to be used in multiple environments.

.. _file-roots-directory-overlay:

Directory Overlay
=================

The ``environment`` setting is a list of directories to publish files from.
These directories are searched in order to find the specified file and the
first file found is returned.

This means that directory data is prioritized based on the order in which they
are listed. In the case of this ``file_roots`` configuration:

.. code-block:: yaml

    file_roots:
      base:
        - /srv/salt/base
        - /srv/salt/failover

If a file's URI is ``salt://httpd/httpd.conf``, it will first search for the
file at ``/srv/salt/base/httpd/httpd.conf``. If the file is found there it
will be returned. If the file is not found there, then
``/srv/salt/failover/httpd/httpd.conf`` will be used for the source.

This allows for directories to be overlaid and prioritized based on the order
they are defined in the configuration.

It is also possible to have ``file_roots`` which supports multiple
environments:

.. code-block:: yaml

    file_roots:
      base:
        - /srv/salt/base
      dev:
        - /srv/salt/dev
        - /srv/salt/base
      prod:
        - /srv/salt/prod
        - /srv/salt/base

This example ensures that each environment will check the associated
environment directory for files first. If a file is not found in the
appropriate directory, the system will default to using the base directory.

Local File Server
=================

.. versionadded:: 0.9.8


The file server can be rerouted to run from the minion. This is primarily to
enable running Salt states without a Salt master. To use the local file server
interface, copy the file server data to the minion and set the file_roots
option on the minion to point to the directories copied from the master.
Once the minion ``file_roots`` option has been set, change the ``file_client``
option to local to make sure that the local file server interface is used.
