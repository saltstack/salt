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
to crate overlays and to allow for files to be organized in many flexible
ways.

Environments
============

The Salt file server defaults to the mandatory ``base`` environment. This
environment **MUST** be defined and is used to download files when no
environment is specified.

Environments allow for files and sls data to be logically separated, but
environments are not isolated from each other. This allows for logical
isolation of environments by the engineer using Salt, but also allows
for information to be used in multiple environments.


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

Local File Server
=================

.. versionadded:: 0.9.8


The file server can be rerouted to run from the minion. This is primarily to
enable running Salt states without a Salt master. To use the local file server
interface, copy the file server data to the minion and set the file_roots
option on the minion to point to the directories copied from the master.
Once the minion ``file_roots`` option has been set, change the ``file_client``
option to local to make sure that the local file server interface is used.
