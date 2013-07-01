=========================
GitFS Backend Walkthrough
=========================

While the default location of the salt state tree is on the Salt master,
in /srv/salt, the master can create a bridge to external resources for files.
One of these resources is the ability for the master to directly pull files
from a git repository and serve them to minions.

.. note::

    This walkthrough assumes basic knowledge of Salt:

        :doc:`Walkthrough </topics/tutorials/walkthrough>`

    And a basic knowledge of file roots:

        :doc:`File Roots </ref/file_server/file_roots>`

The gitfs backend hooks into any number of remote git repositories and caches
the data from the repository on the master. This makes distributing a state
tree to multiple masters seamless and automated.

Salt's file server also has a concept of environments, when using the gitfs
backend, Salt translates git branches and tags into environments, making
environment management very simple. Just merging a QA or staging branch up
to a production branch can be all that is required to make those file changes
available to Salt.

Simple Configuration
====================

To use the gitfs backend only two configuration changes are required on the
master. The ``fileserver_backend`` option needs to be set with `git`:

.. code-block:: yaml

    fileserver_backend:
      - git

To configure what fileserver backends will be searched for requested files.

Now the gitfs system needs to be configured with a remote:

.. code-block:: yaml

    gitfs_remotes:
      - git://github.com/saltstack/salt-states.git

These changes require a restart of the master, then the git repo will be cached
on the master and new requests for the `salt://` protocol will send files found
in the remote git repository via the master.

.. note::

    The master caches the files from the git server and serves them out,
    minions do not connect directly to the git server meaning that only
    requested files are delivered to minions.

Multiple Remotes
================

The ``gitfs_remotes`` option can accept a list of git remotes, the remotes are
then searched in order for the requested file. A simple scenario can illustrate
this behavior.

Assuming that the ``gitfs_remotes`` option specifies three remotes:

.. code-block:: yaml

    gitfs_remotes:
      - git://github.com/example/first.git
      - git://github.com/example/second.git
      - file:///root/third

.. note::

    This example is purposefully contrived to illustrate the behavior of the
    gitfs backend. This example should not be read as a recommended way to lay
    out files and git repos.

.. note::

    The ``file://`` prefix denotes a git repository in a local directory.
    However, it will still use the given ``file://`` URL as a remote, rather
    than copying the git repo to the salt cache.  This means that any refs you
    want accessible must exist as *local* refs in the specified repo.

Assume that each repository contains some files:

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

The repositories will be searched for files by the master in the order in which
they are defined in the configuration, Therefore the remote
`git://github.com/example/first.git` will be searched first, if the requested
file is found then it is served and no further searching is executed. This
means that if the file `salt://haproxy/init.sls` is requested then it will be
pulled from the `git://github.com/example/second.git` git repo. If
`salt://haproxy/haproxy.conf` is requested then it will be pulled from the
third repo.

Multiple Backends
=================

Sometimes it may make sense to use multiple backends. For instance, if sls
files are stored in git, but larger files need to be stored directly on the
master.

The logic used for multiple remotes is also used for multiple backends. If
the ``fileserver_backend`` option contains multiple backends:

.. code-block:: yaml

    fileserver_backend:
      - roots
      - git

Then the `roots` backend (the default backend of files in /srv/salt) will be
searched first for the requested file, then if it is not found on the master
the git remotes will be searched.

GitFS Remotes over SSH
======================

In order to configure a ``gitfs_remotes`` repository over SSH transport the 
``git+ssh`` URL form must be used.

.. code-block:: yaml
    
    gitfs_remotes:
      - git+ssh://git@github.com/example/salt-states.git
      
The private key used to connect to the repository must be located in ``~/.ssh/id_rsa``
for the user running the salt-master.

.. note::

    GitFS requires library ``gitpython`` > 0.3.0.
