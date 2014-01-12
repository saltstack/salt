.. _tutorial-gitfs:

=========================
GitFS Backend Walkthrough
=========================

While the default location of the salt state tree is on the Salt master,
in /srv/salt, the master can create a bridge to external resources for files.
One of these resources is the ability for the master to directly pull files
from a git repository and serve them to minions.

.. note::

    This walkthrough assumes basic knowledge of Salt. To get up to speed, check
    out the :doc:`walkthrough </topics/tutorials/walkthrough>`.

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
master. The ``fileserver_backend`` option needs to be set with a value of
``git``:

.. code-block:: yaml

    fileserver_backend:
      - git

To configure what fileserver backends will be searched for requested files.

Now the gitfs system needs to be configured with a remote:

.. code-block:: yaml

    gitfs_remotes:
      - git://github.com/saltstack/salt-states.git

.. note::

    The salt-states repo is not currently updated with the latest versions
    of the available states. Please review
    https://github.com/saltstack-formulas for the latest versions.


These changes require a restart of the master, then the git repo will be cached
on the master and new requests for the ``salt://`` protocol will send files
found in the remote git repository via the master.

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

    The :strong:`file://` prefix denotes a git repository in a local directory.
    However, it will still use the given :strong:`file://` URL as a remote,
    rather than copying the git repo to the salt cache.  This means that any
    refs you want accessible must exist as *local* refs in the specified repo.

Assume that each repository contains some files:

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

The repositories will be searched for files by the master in the order in which
they are defined in the configuration, Therefore the remote
:strong:`git://github.com/example/first.git` will be searched first, if the
requested file is found then it is served and no further searching is executed.
This means that if the file :strong:`salt://haproxy/init.sls` is requested then
it will be pulled from the :strong:`git://github.com/example/second.git` git
repo. If :strong:`salt://haproxy/haproxy.conf` is requested then it will be
pulled from the third repo.

Serving from a Subdirectory
===========================

The ``gitfs_root`` option gives the ability to serve files from a subdirectory
within the repository. The path is defined relative to the root of the
repository.

With this repository structure:

.. code-block:: yaml

    repository.git:
        somefolder
            otherfolder
                top.sls
                edit/vim.sls
                edit/vimrc
                nginx/init.sls

Configuration and files can be accessed normally with:

.. code-block:: yaml

    gitfs_root: somefolder/otherfolder

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

Then the ``roots`` backend (the default backend of files in ``/srv/salt``) will
be searched first for the requested file, then if it is not found on the master
the git remotes will be searched.

Branches, environments and top.sls files
========================================

As stated above, when using the ``gitfs`` backend, branches will be mapped
to environments using the branch name as identifier.
There is an exception to this rule thought: the ``master`` branch is implicitly
mapped to the ``base`` environment.
Therefore, for a typical ``base``, ``qa``, ``dev`` setup, you'll have to
create the following branches:

.. code-block:: yaml

    master
    qa
    dev

Also, ``top.sls`` files from different branches will be merged into one big
file at runtime. Since this could lead to hardly manageable configurations,
the recommended setup is to have the ``top.sls`` file only in your master branch,
and use environment-specific branches for states definitions.


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

    GitFS requires the Python module ``GitPython``, version 0.3.0 or newer.
    If your Master runs Ubuntu 12.04 LTS, you will likely need to install
    GitPython using `pip`_.

    .. code-block:: bash

        # pip install GitPython

.. _`pip`: http://www.pip-installer.org/


Using Git as an External Pillar Source
======================================

Git repositories can also be used to provide :doc:`Pillar </topics/pillar/index>`
data, using the :doc:`External Pillar </topics/development/external_pillars>`
system. To define a git external pillar, you can add a section like the
following to your master config file:

.. code-block:: yaml

    ext_pillar:
      - git: <branch> <repo>


The ``<branch>`` param is the branch containing the pillar SLS tree, and the
``<repo>`` param is the URI for the repository. The below example would add the
``master`` branch of the specified repo as an external pillar source.

.. code-block:: yaml

    ext_pillar:
      - git: master https://domain.com/pillar.git

More information on the git external pillar can be found :mod:`here
<salt.pillar.git_pillar>`.


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
