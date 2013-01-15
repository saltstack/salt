====================
File Server Backends
====================

Salt version 0.12.0 introduced the ability for the Salt Master to integrate
different file server backends. File server backends allows the Salt file
server to act as a transparent bridge to external resources. The primary
example of this is the git backend which allows for all of the Salt formulas
and files to be maintained in a remote git repository.

The fileserver backend system can accept multiple backends as well. This makes
it possible to have the environments listed in the file_roots configuration
available in addition to other backends, or the ability to mix multiple
backends.

This feature is managed by the `fileserver_backend` option in the master
config. The desired backend systems are listed in order of search priority:

.. code-block:: yaml

    fileserver_backend:
      - roots
      - git

If this configuration the environments and files defined in the `file_roots`
configuration will be searched first, if the referenced environment and file
is not found then the git backend will be searched.

Environments
------------

The concept of environments is followed in all backend systems. The
environments in the classic `roots` backend are defined in the `file_roots`
option. Environments map differently based on the backend, for instance the
git backend translated branches and tags in git to environments. This makes
it easy to define environments in git by just setting a tag or forking a
branch.
