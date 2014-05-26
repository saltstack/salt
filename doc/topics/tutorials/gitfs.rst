.. _tutorial-gitfs:

=========================
GitFS Backend Walkthrough
=========================

Salt can retrieve states and pillars from local and remote Git repositories
configured as GitFS remotes.

.. note::

    This walkthrough assumes basic knowledge of Salt. To get up to speed, check
    out the :doc:`walkthrough </topics/tutorials/walkthrough>`.

By default, Salt state trees and pillars are served from
``/srv/salt`` and ``/srv/pillar``, as configured by the
``roots`` :conf_master:`fileserver_backend`, :conf_master:`file_roots`,
and :conf_master:`pillar_roots` configuration settings in
``/etc/salt/master`` or ``/etc/salt/minion``.

GitFS support is enabled by configuring the ``git``
:conf_master:`fileserver_backend`, :conf_master:`gitfs_remotes`,
and/or :conf_master:`ext_pillar` settings.

Git branches in GitFS remotes are mapped to Salt environments. 
Merging a QA or staging branch up to a production branch
can be all that is required to make state and pillar changes available to Salt
minions.


Simple Configuration
====================

.. note::

    GitFS requires ``GitPython`` version 0.3.0 or newer. 
    If your OS does not have version 0.3.0 or newer
    (such as Ubuntu 12.04 LTS), you can install ``GitPython`` with `pip`_:

    .. code-block:: bash

        # pip install GitPython

.. _`pip`: http://www.pip-installer.org/

To use the gitfs backend, only two configuration changes are required on the
master:

1. Include ``git`` in the :conf_master:`fileserver_backend`
   option to enable the GitFS backend:

.. code-block:: yaml

    fileserver_backend:
      - git

2. Specify one or more ``git://``, ``git+ssh://``, ``https://``, or ``file://``
   URLs in :conf_master:`gitfs_remotes`
   to configure which repositories to cache and search for requested files:

.. code-block:: yaml

    gitfs_remotes:
      - https://github.com/saltstack-formulas/salt-formula.git

3. *Restart the master* so that the git repository cache on the master
   is updated, and
   new ``salt://`` requests will send the latest files from
   the remote git repository.
   This step is not necessary with a standalone minion configuration.

.. note::

    In a master/minion setup, files from a GitFS remote are cached once by
    the master; so minions do not need direct access 
    to the git repository. In a standalone minion configuration, files from
    each GitFS remote are cached by the minion.


Multiple Remotes
================

The ``gitfs_remotes`` option accepts an ordered list of git remotes to
cache and search, in listed order, for requested files.

A simple scenario illustrates this cascading lookup behavior:

If the ``gitfs_remotes`` option specifies three remotes:

.. code-block:: yaml

    gitfs_remotes:
      - git://github.com/example/first.git
      - https://github.com/example/second.git
      - file:///root/third

.. note::

    This example is purposefully contrived to illustrate the behavior of the
    gitfs backend. This example should not be read as a recommended way to lay
    out files and git repos.

    The :strong:`file://` prefix denotes a git repository in a local directory.
    However, it will still use the given :strong:`file://` URL as a remote,
    rather than copying the git repo to the salt cache.  This means that any
    refs you want accessible must exist as *local* refs in the specified repo.

.. warning::

    Salt versions prior to 2014.1.0 (Hydrogen) are not tolerant of changing the
    order of remotes or modifying the URI of existing remotes. In those
    versions, when modifying remotes it is a good idea to remove the gitfs
    cache directory (``/var/cache/salt/master/gitfs``) before restarting the
    salt-master service.

And each repository contains some files:

.. code-block:: yaml

    first.git:
        top.sls
        edit/vim.sls
        edit/vimrc
        nginx/init.sls

    second.git:
        edit/dev_vimrc
        haproxy/init.sls

    third:
        haproxy/haproxy.conf
        edit/dev_vimrc

Salt will attempt to lookup the requested file from each GitFS remote
repository in the order in which they are defined in the configuration. The
:strong:`git://github.com/example/first.git` remote will be searched first.
If the requested file is found, then it is served and no further searching
is executed. For example:

* A request for :strong:`salt://haproxy/init.sls` will be pulled from the
  :strong:`https://github.com/example/second.git` git repo.
* A request for :strong:`salt://haproxy/haproxy.conf` will be pulled from the
  :strong:`file:///root/third` repo.


Serving from a Subdirectory
===========================

The :conf_master:`gitfs_root` parameter allows files to be served from a
subdirectory within the repository. This allows for only part of a repository
to be exposed to the Salt fileserver.

Assume the below layout::

    .gitignore
    README.txt
    foo/
    foo/bar/
    foo/bar/one.txt
    foo/bar/two.txt
    foo/bar/three.txt
    foo/baz/
    foo/baz/top.sls
    foo/baz/edit/vim.sls
    foo/baz/edit/vimrc
    foo/baz/nginx/init.sls

The below configuration would serve only the files from ``foo/baz``, ignoring
the other files in the repository:

.. code-block:: yaml

    gitfs_remotes:
      - git://mydomain.com/stuff.git

    gitfs_root: foo/baz


Multiple Backends
=================

Sometimes it may make sense to use multiple backends; for instance, if ``sls``
files are stored in git but larger files are stored directly on the master.

The cascading lookup logic used for multiple remotes is also used with
multiple backends. If the ``fileserver_backend`` option contains
multiple backends:

.. code-block:: yaml

    fileserver_backend:
      - roots
      - git

Then the ``roots`` backend (the default backend of files in ``/srv/salt``) will
be searched first for the requested file; then, if it is not found on the
master, each configured git remote will be searched.


Branches, Environments and Top Files
====================================

When using the ``gitfs`` backend, branches and tags will be mapped to
environments using the branch/tag name as an identifier.

There is one exception to this rule: the ``master`` branch is implicitly mapped
to the ``base`` environment.

So, for a typical ``base``, ``qa``, ``dev`` setup, the following branches could
be used:

.. code-block:: yaml

    master
    qa
    dev

``top.sls`` files from different branches will be merged into one at runtime.
Since this can lead to overly complex configurations, the recommended setup is
to have the ``top.sls`` file only in the master branch and use
environment-specific branches for state definitions.

To map a branch other than ``master`` as the ``base`` environment, use the
:conf_master:`gitfs_base` parameter.

.. code-block:: yaml

    gitfs_base: salt-base


GitFS Remotes over SSH
======================

To configure a ``gitfs_remotes`` repository over SSH transport, use the
``git+ssh`` URL form:

.. code-block:: yaml

    gitfs_remotes:
      - git+ssh://git@github.com/example/salt-states.git

The private key used to connect to the repository must be located in
``~/.ssh/id_rsa`` for the user running the salt-master.


Upcoming Features
=================

The upcoming feature release will bring a number of new features to gitfs:

1. **Environment Blacklist/Whitelist**

   Two new configuration parameters, :conf_master:`gitfs_env_whitelist` and
   :conf_master:`gitfs_env_blacklist`, allow greater control over which
   branches/tags are exposed as fileserver environments.

2. **Mountpoint**

   Prior to the addition of this feature, to serve a file from the URI
   ``salt://webapps/foo/files/foo.conf``, it was necessary to ensure that the
   git repository contained the parent directories (i.e.
   ``webapps/foo/files/``). The :conf_master:`gitfs_mountpoint` parameter
   will prepend the specified path to the files served from gitfs, allowing you
   to use an existing repository rather than reorganizing it to fit your Salt
   fileserver layout.

3. **Per-remote Configuration Parameters**

   :conf_master:`gitfs_base`, :conf_master:`gitfs_root`, and
   :conf_master:`gitfs_mountpoint` are all global parameters. That is, they
   affect *all* of your gitfs remotes. The upcoming feature release allows for
   these parameters to be overridden on a per-remote basis. This allows for a
   tremendous amount of customization. See :conf_master:`here <gitfs_remotes>`
   for an example of how use per-remote configuration.

4. **Support for pygit2 and dulwich**

   GitPython_ is no longer being actively developed, so support has been added
   for both pygit2_ and dulwich_ as a Python interface for git. Neither is yet
   as full-featured as GitPython, for instance authentication via public key
   is not yet supported. Salt will default to using GitPython, but the
   :conf_master:`gitfs_provider` parameter can be used to specify one of the
   other providers.

.. _GitPython: https://github.com/gitpython-developers/GitPython
.. _pygit2: https://github.com/libgit2/pygit2
.. _dulwich: https://www.samba.org/~jelmer/dulwich/

Using Git as an External Pillar Source
======================================

Git repositories can also be used to provide :doc:`Pillar
</topics/pillar/index>` data, using the :doc:`External Pillar
</topics/development/external_pillars>` system. To define a git external
pillar, add a section like the following to the salt master config file:

.. code-block:: yaml

    ext_pillar:
      - git: <branch> <repo> [root=<gitroot>]

.. versionchanged:: Helium
    The optional ``root`` parameter will be added.

The ``<branch>`` param is the branch containing the pillar SLS tree. The
``<repo>`` param is the URI for the repository. To add the
``master`` branch of the specified repo as an external pillar source:

.. code-block:: yaml

    ext_pillar:
      - git: master https://domain.com/pillar.git

Use the ``root`` parameter to use pillars from a subdirectory of a git
repository:

.. code-block:: yaml

    ext_pillar:
      - git: master https://domain.com/pillar.git root=subdirectory

More information on the git external pillar can be found in the
:mod:`salt.pillar.get_pillar docs <salt.pillar.git_pillar>`.


.. _faq-gitfs-bug:

Why aren't my custom modules/states/etc. syncing to my Minions?
===============================================================

In versions 0.16.3 and older, when using the :doc:`git fileserver backend
</topics/tutorials/gitfs>`, certain versions of GitPython may generate errors
when fetching, which Salt fails to catch. While not fatal to the fetch process,
these interrupt the fileserver update that takes place before custom types are
synced, and thus interrupt the sync itself. Try disabling the git fileserver
backend in the master config, restarting the master, and attempting the sync
again.

This issue is worked around in Salt 0.16.4 and newer.
