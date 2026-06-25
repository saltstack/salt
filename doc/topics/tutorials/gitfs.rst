.. _tutorial-gitfs:


==================================
Git Fileserver Backend Walkthrough
==================================

.. note::

    This walkthrough assumes basic knowledge of Salt. To get up to speed, check
    out the :ref:`Salt Walkthrough <tutorial-salt-walk-through>`.

The gitfs backend allows Salt to serve files from git repositories. It can be
enabled by adding ``git`` to the :conf_master:`fileserver_backend` list, and
configuring one or more repositories in :conf_master:`gitfs_remotes`.

Branches and tags become Salt fileserver environments.

.. note::
    Branching and tagging can result in a lot of potentially-conflicting
    :ref:`top files <states-top>`, for this reason it may be useful to set
    :conf_minion:`top_file_merging_strategy` to ``same`` in the minions' config
    files if the top files are being managed in a GitFS repo.

.. _gitfs-dependencies:

Installing Dependencies
=======================

Both pygit2_ and GitPython_ are supported Python interfaces to git. If
compatible versions of both are installed, pygit2_ will be preferred. In these
cases, GitPython_ can be forced using the :conf_master:`gitfs_provider`
parameter in the master config file.

The versions tested in CI and shipped with the Salt onedir packages are:

* pygit2_ ``>= 1.13.1`` (on Python 3.11+, ``pygit2 >= 1.19.2``), built against
  libgit2_ ``>= 1.5``.
* GitPython_ ``>= 3.1.50`` together with the system ``git`` binary.

These pins live in ``requirements/base.txt`` and ``requirements/static/ci/``.
Salt's import-time check still accepts the very old floor of pygit2_ ``0.20.3``
and GitPython_ ``0.3`` (see ``GITPYTHON_MINVER`` / ``PYGIT2_MINVER`` in
``salt/utils/gitfs.py``), but only the combinations above are exercised by the
test suite. Older releases are missing fixes for SSH authentication, refspec
handling, and credential helpers, and should not be used in production.

.. note::
    Run the most recent compatible release of whichever provider you choose.

.. _pygit2: https://github.com/libgit2/pygit2
.. _GitPython: https://github.com/gitpython-developers/GitPython
.. _libgit2: https://libgit2.org/
.. _libssh2: https://www.libssh2.org/

pygit2
------

The Salt onedir packages already include a working pygit2_/libgit2_ pair, so on
a onedir install no extra steps are required. For source installs, install the
distro packages where available:

.. code-block:: bash

    # RHEL / Fedora / Alma / Rocky 8+ (EPEL provides libgit2/python3-pygit2)
    # dnf install python3-pygit2

    # Debian 11+ / Ubuntu 22.04+
    # apt-get install python3-pygit2

If the distro packages are too old, ``pygit2`` can be installed from PyPI.
``pygit2`` is tightly coupled to libgit2_ — the pygit2_ release notes list the
exact libgit2_ ABI it links against, and a mismatch produces import errors at
salt-master start. The simplest recipe on a onedir install is:

.. code-block:: bash

    # apt-get install libgit2-1.5    # or whatever libgit2-N your distro ships
    # salt-pip install 'pygit2>=1.13.1,<1.18' --no-deps

``--no-deps`` keeps ``salt-pip`` from upgrading the bundled cffi.

.. note::
    SSH authentication in pygit2 (see :ref:`pygit2-authentication-ssh`)
    requires libssh2_ (*not* libssh) to be linked into the libgit2_ build.
    Distro libgit2 packages already include libssh2 support. If you are
    rebuilding libgit2 from source and see "Unsupported URL Protocol" errors
    against ``ssh://`` remotes in the master log, the libgit2 build was made
    without libssh2 headers.

.. warning::
    pygit2_ is actively developed and `frequently makes non-backwards-compatible
    API changes`_, even in minor releases.  Pin pygit2_ in production, watch
    the changelog_ when upgrading, and report breakage on the
    `SaltStack issue tracker`_.

.. _frequently makes non-backwards-compatible API changes: https://www.pygit2.org/install.html#version-numbers
.. _changelog: https://github.com/libgit2/pygit2/blob/master/CHANGELOG.rst
.. _SaltStack issue tracker: https://github.com/saltstack/salt/issues

GitPython
---------

GitPython_ ``>= 3.1.50`` is recommended, matching ``requirements/base.txt`` and
the lockfiles under ``requirements/static/ci/``. Install from distro packages
or from PyPI:

.. code-block:: bash

    # RHEL / Fedora
    # dnf install python3-GitPython

    # Debian / Ubuntu
    # apt-get install python3-git

    # Onedir install (any platform)
    # salt-pip install 'GitPython>=3.1.50'

GitPython_ shells out to the ``git`` CLI, so the system ``git`` binary must
also be installed. On macOS, install Xcode_ command-line tools or use Homebrew.

.. _Xcode: https://developer.apple.com/xcode/

.. warning::
    GitPython advises against the use of its library for long-running processes
    (such as a salt-master). See their warning on potential leaks of system
    resources:
    https://github.com/gitpython-developers/GitPython#leakage-of-system-resources.
    The Salt fileserver mitigates this by restarting the fileserver worker on
    a configurable interval (see :conf_master:`fileserver_interval`).

Simple Configuration
====================

To use the gitfs backend, only two configuration changes are required on the
master:

1. Include ``gitfs`` in the :conf_master:`fileserver_backend` list in the
   master config file:

   .. code-block:: yaml

       fileserver_backend:
         - gitfs

   .. note::
       ``git`` also works here. Prior to the 2018.3.0 release, *only* ``git``
       would work.

2. Specify one or more ``git://``, ``https://``, ``file://``, or ``ssh://``
   URLs in :conf_master:`gitfs_remotes` to configure which repositories to
   cache and search for requested files:

   .. code-block:: yaml

       gitfs_remotes:
         - https://github.com/saltstack-formulas/salt-formula.git

   SSH remotes can also be configured using scp-like syntax:

   .. code-block:: yaml

       gitfs_remotes:
         - git@github.com:user/repo.git
         - ssh://user@domain.tld/path/to/repo.git

   Information on how to authenticate to SSH remotes can be found :ref:`here
   <gitfs-authentication>`.

3. Restart the master to load the new configuration.


.. note::

    In a master/minion setup, files from a gitfs remote are cached once by the
    master, so minions do not need direct access to the git repository.


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

And each repository contains some files:

.. code-block:: yaml

    first.git:
        top.sls
        edit/vim.sls
        edit/vimrc
        nginx/init.sls
        shell/init.sls

    second.git:
        edit/dev_vimrc
        haproxy/init.sls
        shell.sls

    third:
        haproxy/haproxy.conf
        edit/dev_vimrc

Salt will attempt to lookup the requested file from each gitfs remote
repository in the order in which they are defined in the configuration. The
:strong:`git://github.com/example/first.git` remote will be searched first.
If the requested file is found, then it is served and no further searching
is executed. For example:

* A request for the file :strong:`salt://haproxy/init.sls` will be served from
  the :strong:`https://github.com/example/second.git` git repo.
* A request for the file :strong:`salt://haproxy/haproxy.conf` will be served from the
  :strong:`file:///root/third` repo.

Also a requested state file overrules a directory with an `init.sls`-file.
For example:

* A request for :strong:`state.apply shell` will be served from the
  :strong:`https://github.com/example/second.git` git repo.

.. note::

    This example is purposefully contrived to illustrate the behavior of the
    gitfs backend. This example should not be read as a recommended way to lay
    out files and git repos.

    The :strong:`file://` prefix denotes a git repository in a local directory.
    However, it will still use the given :strong:`file://` URL as a remote,
    rather than copying the git repo to the salt cache.  This means that any
    refs you want accessible must exist as *local* refs in the specified repo.

.. warning::

    Salt versions prior to 2014.1.0 are not tolerant of changing the
    order of remotes or modifying the URI of existing remotes. In those
    versions, when modifying remotes it is a good idea to remove the gitfs
    cache directory (``/var/cache/salt/master/gitfs``) before restarting the
    salt-master service.

.. _gitfs-per-remote-config:

Per-remote Configuration Parameters
===================================

.. versionadded:: 2014.7.0

The following master config parameters are global (that is, they apply to all
configured gitfs remotes):

* :conf_master:`gitfs_base`
* :conf_master:`gitfs_root`
* :conf_master:`gitfs_ssl_verify`
* :conf_master:`gitfs_mountpoint` (new in 2014.7.0)
* :conf_master:`gitfs_user` (**pygit2 only**, new in 2014.7.0)
* :conf_master:`gitfs_password` (**pygit2 only**, new in 2014.7.0)
* :conf_master:`gitfs_insecure_auth` (**pygit2 only**, new in 2014.7.0)
* :conf_master:`gitfs_pubkey` (**pygit2 only**, new in 2014.7.0)
* :conf_master:`gitfs_privkey` (**pygit2 only**, new in 2014.7.0)
* :conf_master:`gitfs_passphrase` (**pygit2 only**, new in 2014.7.0)
* :conf_master:`gitfs_refspecs` (new in 2017.7.0)
* :conf_master:`gitfs_disable_saltenv_mapping` (new in 2018.3.0)
* :conf_master:`gitfs_ref_types` (new in 2018.3.0)
* :conf_master:`gitfs_update_interval` (new in 2018.3.0)

.. note::
    pygit2 only supports disabling SSL verification in versions 0.23.2 and
    newer.

These parameters can now be overridden on a per-remote basis. This allows for a
tremendous amount of customization. Here's some example usage:

.. code-block:: yaml

    gitfs_provider: pygit2
    gitfs_base: develop

    gitfs_remotes:
      - https://foo.com/foo.git
      - https://foo.com/bar.git:
        - root: salt
        - mountpoint: salt://bar
        - base: salt-base
        - ssl_verify: False
        - update_interval: 120
      - https://foo.com/bar.git:
        - name: second_bar_repo
        - root: other/salt
        - mountpoint: salt://other/bar
        - base: salt-base
        - ref_types:
          - branch
      - http://foo.com/baz.git:
        - root: salt/states
        - user: joe
        - password: mysupersecretpassword
        - insecure_auth: True
        - disable_saltenv_mapping: True
        - saltenv:
          - foo:
            - ref: foo
      - http://foo.com/quux.git:
        - all_saltenvs: master

.. important::

    There are two important distinctions which should be noted for per-remote
    configuration:

    1. The URL of a remote which has per-remote configuration must be suffixed
       with a colon.

    2. Per-remote configuration parameters are named like the global versions,
       with the ``gitfs_`` removed from the beginning. The exception being the
       ``name``, ``saltenv``, and ``all_saltenvs`` parameters, which are only
       available to per-remote configurations.

    The ``all_saltenvs`` parameter is new in the 2018.3.0 release.

In the example configuration above, the following is true:

1. The first and fourth gitfs remotes will use the ``develop`` branch/tag as the
   ``base`` environment, while the second and third will use the ``salt-base``
   branch/tag as the ``base`` environment.

2. The first remote will serve all files in the repository. The second
   remote will only serve files from the ``salt`` directory (and its
   subdirectories). The third remote will only server files from the
   ``other/salt`` directory (and its subdirectories), while the fourth remote
   will only serve files from the ``salt/states`` directory (and its
   subdirectories).

3. The third remote will only serve files from branches, and not from tags or
   SHAs.

4. The fourth remote will only have two saltenvs available: ``base`` (pointed
   at ``develop``), and ``foo`` (pointed at ``foo``).

5. The first and fourth remotes will have files located under the root of the
   Salt fileserver namespace (``salt://``). The files from the second remote
   will be located under ``salt://bar``, while the files from the third remote
   will be located under ``salt://other/bar``.

6. The second and third remotes reference the same repository and unique names
   need to be declared for duplicate gitfs remotes.

7. The fourth remote overrides the default behavior of :ref:`not authenticating
   to insecure (non-HTTPS) remotes <gitfs-insecure-auth>`.

8. Because ``all_saltenvs`` is configured for the fifth remote, files from the
   branch/tag ``master`` will appear in every fileserver environment.

   .. note::
       The use of ``http://`` (instead of ``https://``) is permitted here
       *only* because authentication is not being used. Otherwise, the
       ``insecure_auth`` parameter must be used (as in the fourth remote) to
       force Salt to authenticate to an ``http://`` remote.

9. The first remote will wait 120 seconds between updates instead of 60.

.. _gitfs-per-saltenv-config:

Per-Saltenv Configuration Parameters
====================================

.. versionadded:: 2016.11.0

For more granular control, Salt allows the following three things to be
overridden for individual saltenvs within a given repo:

- The :ref:`mountpoint <gitfs-walkthrough-mountpoint>`
- The :ref:`root <gitfs-walkthrough-root>`
- The branch/tag to be used for a given saltenv

Here is an example:

.. code-block:: yaml

    gitfs_root: salt

    gitfs_saltenv:
      - dev:
        - mountpoint: salt://gitfs-dev
        - ref: develop

    gitfs_remotes:
      - https://foo.com/bar.git:
        - saltenv:
          - staging:
            - ref: qa
            - mountpoint: salt://bar-staging
          - dev:
            - ref: development
      - https://foo.com/baz.git:
        - saltenv:
          - staging:
            - mountpoint: salt://baz-staging

Given the above configuration, the following is true:

1. For all gitfs remotes, files for the ``dev`` saltenv will be located under
   ``salt://gitfs-dev``.

2. For the ``dev`` saltenv, files from the first remote will be sourced from
   the ``development`` branch, while files from the second remote will be
   sourced from the ``develop`` branch.

3. For the ``staging`` saltenv, files from the first remote will be located
   under ``salt://bar-staging``, while files from the second remote will be
   located under ``salt://baz-staging``.

4. For all gitfs remotes, and in all saltenvs, files will be served from the
   ``salt`` directory (and its subdirectories).


.. _gitfs-custom-refspecs:

Custom Refspecs
===============

.. versionadded:: 2017.7.0

GitFS will by default fetch remote branches and tags. However, sometimes it can
be useful to fetch custom refs (such as those created for `GitHub pull
requests`__). To change the refspecs GitFS fetches, use the
:conf_master:`gitfs_refspecs` config option:

.. __: https://help.github.com/en/github/collaborating-with-issues-and-pull-requests/checking-out-pull-requests-locally

.. code-block:: yaml

    gitfs_refspecs:
      - '+refs/heads/*:refs/remotes/origin/*'
      - '+refs/tags/*:refs/tags/*'
      - '+refs/pull/*/head:refs/remotes/origin/pr/*'
      - '+refs/pull/*/merge:refs/remotes/origin/merge/*'

In the above example, in addition to fetching remote branches and tags,
GitHub's custom refs for pull requests and merged pull requests will also be
fetched. These special ``head`` refs represent the head of the branch which is
requesting to be merged, and the ``merge`` refs represent the result of the
base branch after the merge.

.. important::
    When using custom refspecs, the destination of the fetched refs *must* be
    under ``refs/remotes/origin/``, preferably in a subdirectory like in the
    example above. These custom refspecs will map as environment names using
    their relative path underneath ``refs/remotes/origin/``. For example,
    assuming the configuration above, the head branch for pull request 12345
    would map to fileserver environment ``pr/12345`` (slash included).

Refspecs can be configured on a :ref:`per-remote basis
<gitfs-per-remote-config>`. For example, the below configuration would only
alter the default refspecs for the *second* GitFS remote. The first remote
would only fetch branches and tags (the default).

.. code-block:: yaml

    gitfs_remotes:
      - https://domain.tld/foo.git
      - https://domain.tld/bar.git:
        - refspecs:
          - '+refs/heads/*:refs/remotes/origin/*'
          - '+refs/tags/*:refs/tags/*'
          - '+refs/pull/*/head:refs/remotes/origin/pr/*'
          - '+refs/pull/*/merge:refs/remotes/origin/merge/*'


.. _gitfs-global-remotes:

Global Remotes
==============

.. versionadded:: 2018.3.0 for all_saltenvs, 3001 for fallback

The ``all_saltenvs`` per-remote configuration parameter overrides the logic
Salt uses to map branches/tags to fileserver environments (i.e. saltenvs). This
allows a single branch/tag to appear in *all* GitFS saltenvs.

.. note::
   ``all_saltenvs`` only works *within* GitFS. That is, files in a branch
   configured using ``all_saltenvs`` will *not* show up in a fileserver
   environment defined via some other fileserver backend (e.g.
   :conf_master:`file_roots`).

The ``fallback`` global or per-remote configuration can also be used.

This is very useful in particular when working with :ref:`salt formulas
<conventions-formula>`. Prior to the addition of this feature, it was necessary
to push a branch/tag to the remote repo for each saltenv in which that formula
was to be used. If the formula needed to be updated, this update would need to
be reflected in all of the other branches/tags. This is both inconvenient and
not scalable.

With ``all_saltenvs``, it is now possible to define your formula once, in a
single branch.

.. code-block:: yaml

    gitfs_remotes:
      - http://foo.com/quux.git:
        - all_saltenvs: anything

If you want to also test working branches of the formula repository, use
``fallback``:

.. code-block:: yaml

    gitfs_remotes:
      - http://foo.com/quux.git:
        - fallback: anything

.. _gitfs-update-intervals:

Update Intervals
================

Prior to the 2018.3.0 release, GitFS would update its fileserver backends as part
of a dedicated "maintenance" process, in which various routine maintenance
tasks were performed. This tied the update interval to the
:conf_master:`loop_interval` config option, and also forced all fileservers to
update at the same interval.

Now it is possible to make GitFS update at its own interval, using
:conf_master:`gitfs_update_interval`:

.. code-block:: yaml

    gitfs_update_interval: 180

    gitfs_remotes:
      - https://foo.com/foo.git
      - https://foo.com/bar.git:
        - update_interval: 120

Using the above configuration, the first remote would update every three
minutes, while the second remote would update every two minutes.

Configuration Order of Precedence
=================================

The order of precedence for GitFS configuration is as follows (each level
overrides all levels below it):

1. Per-saltenv configuration (defined under a per-remote ``saltenv``
   param)

   .. code-block:: yaml

       gitfs_remotes:
         - https://foo.com/bar.git:
           - saltenv:
             - dev:
               - mountpoint: salt://bar

2. Global per-saltenv configuration (defined in :conf_master:`gitfs_saltenv`)

   .. code-block:: yaml

       gitfs_saltenv:
         - dev:
           - mountpoint: salt://bar

3. Per-remote configuration parameter

   .. code-block:: yaml

       gitfs_remotes:
         - https://foo.com/bar.git:
           - mountpoint: salt://bar

4. Global configuration parameter

   .. code-block:: yaml

       gitfs_mountpoint: salt://bar

.. note::
    The one exception to the above is when :ref:`all_saltenvs
    <gitfs-global-remotes>` is used. This value overrides all logic for mapping
    branches/tags to fileserver environments. So, even if
    :conf_master:`gitfs_saltenv` is used to globally override the mapping for a
    given saltenv, :ref:`all_saltenvs <gitfs-global-remotes>` would take
    precedence for any remote which uses it.

    It's important to note however that any ``root`` and ``mountpoint`` values
    configured in :conf_master:`gitfs_saltenv` (or :ref:`per-saltenv
    configuration <gitfs-per-saltenv-config>`) would be unaffected by this.

.. _gitfs-walkthrough-root:

Serving from a Subdirectory
===========================

The :conf_master:`gitfs_root` parameter allows files to be served from a
subdirectory within the repository. This allows for only part of a repository
to be exposed to the Salt fileserver.

Assume the below layout:

.. code-block:: text

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

The below configuration would serve only the files under ``foo/baz``, ignoring
the other files in the repository:

.. code-block:: yaml

    gitfs_remotes:
      - git://mydomain.com/stuff.git

    gitfs_root: foo/baz

The root can also be configured on a :ref:`per-remote basis
<gitfs-per-remote-config>`.


.. _gitfs-walkthrough-mountpoint:

Mountpoints
===========

.. versionadded:: 2014.7.0

The :conf_master:`gitfs_mountpoint` parameter will prepend the specified path
to the files served from gitfs. This allows an existing repository to be used,
rather than needing to reorganize a repository or design it around the layout
of the Salt fileserver.

Before the addition of this feature, if a file being served up via gitfs was
deeply nested within the root directory (for example,
``salt://webapps/foo/files/foo.conf``, it would be necessary to ensure that the
file was properly located in the remote repository, and that all of the
parent directories were present (for example, the directories
``webapps/foo/files/`` would need to exist at the root of the repository).

The below example would allow for a file ``foo.conf`` at the root of the
repository to be served up from the Salt fileserver path
``salt://webapps/foo/files/foo.conf``.

.. code-block:: yaml

    gitfs_remotes:
      - https://mydomain.com/stuff.git

    gitfs_mountpoint: salt://webapps/foo/files

Mountpoints can also be configured on a :ref:`per-remote basis
<gitfs-per-remote-config>`.


Using gitfs in Masterless Mode
==============================

Since 2014.7.0, gitfs can be used in masterless mode. To do so, simply add the
gitfs configuration parameters (and set :conf_master:`fileserver_backend`) in
the _minion_ config file instead of the master config file.


Using gitfs Alongside Other Backends
====================================

Sometimes it may make sense to use multiple backends; for instance, if ``sls``
files are stored in git but larger files are stored directly on the master.

The cascading lookup logic used for multiple remotes is also used with multiple
backends. If the :conf_master:`fileserver_backend` option contains multiple
backends:

.. code-block:: yaml

    fileserver_backend:
      - roots
      - git

Then the ``roots`` backend (the default backend of files in ``/srv/salt``) will
be searched first for the requested file; then, if it is not found on the
master, each configured git remote will be searched.

.. note::

    This can be used together with `file_roots` accepting `__env__` as a catch-all
    environment, since 2018.3.5 and 2019.2.1:

    .. code-block:: yaml

        file_roots:
          base:
            - /srv/salt
          __env__:
            - /srv/salt

Branches, Environments, and Top Files
=====================================

When using the GitFS backend, branches, and tags will be mapped to environments
using the branch/tag name as an identifier.

There is one exception to this rule: the ``master`` branch is implicitly mapped
to the ``base`` environment.

So, for a typical ``base``, ``qa``, ``dev`` setup, the following branches could
be used:

.. code-block:: yaml

    master
    qa
    dev

To map a branch other than ``master`` as the ``base`` environment, use the
:conf_master:`gitfs_base` parameter.

.. code-block:: yaml

    gitfs_base: salt-base

The base can also be configured on a :ref:`per-remote basis
<gitfs-per-remote-config>`.

Use Case: Code Promotion (dev -> qa -> base)
--------------------------------------------

When running a :ref:`highstate <running-highstate>`, the ``top.sls`` files from
all of the different branches and tags will be merged into one. This does not
work well with the use case where changes are tested in development branches
before being merged upstream towards production, because if the same SLS file
from multiple environments is part of the :ref:`highstate <running-highstate>`,
it can result in non-unique state IDs, which will cause an error in the state
compiler and not allow the :ref:`highstate <running-highstate>` to proceed.

To accomplish this use case, you should do three things:

1. Use ``{{ saltenv }}`` in place of your environment in your **top.sls**. This
   will let you use the same top file in all branches, because ``{{ saltenv
   }}`` gets replaced with the effective saltenv of the environment being
   processed.

2. Set :conf_minion:`top_file_merging_strategy` to ``same`` in the minion
   configuration. This will keep the ``base`` environment from looking at the
   **top.sls** from the ``dev`` or ``qa`` branches, etc.

3. Explicitly define your :conf_minion:`saltenv`. (More on this below.)


Consider the following example top file and SLS file:

**top.sls**

.. code-block:: yaml

    {{ saltenv }}:
      '*':
        - mystuff

**mystuff.sls**

.. code-block:: yaml

    manage_mystuff:
      pkg.installed:
        - name: mystuff
      file.managed:
        - name: /etc/mystuff.conf
        - source: salt://mystuff/files/mystuff.conf
      service.running:
        - name: mystuffd
        - enable: True
        - watch:
          - file: /etc/mystuff.conf

Imagine for a moment that you need to change your ``mystuff.conf``. So, you go
to your ``dev`` branch, edit ``mystuff/files/mystuff.conf``, and commit and
push.

If you have only done the first two steps recommended above, and you run your
:ref:`highstate <running-highstate>`, you will end up with conflicting IDs:

.. code-block:: text

    myminion:
        Data failed to compile:
    ----------
        Detected conflicting IDs, SLS IDs need to be globally unique.
        The conflicting ID is 'manage_mystuff' and is found in SLS 'base:mystuff' and SLS 'dev:mystuff'
    ----------
        Detected conflicting IDs, SLS IDs need to be globally unique.
        The conflicting ID is 'manage_mystuff' and is found in SLS 'dev:mystuff' and SLS 'qa:mystuff'

This is because, in the absence of an explicit :conf_minion:`saltenv`, all
environments' top files are considered. Each environment looks at only its own
**top.sls**, but because the **mystuff.sls** exists in each branch, they all
get pulled into the highstate, resulting in these conflicting IDs. This is why
explicitly setting your :conf_minion:`saltenv` is important for this use case.

There are two ways of explicitly defining the :conf_minion:`saltenv`:

1. Set the :conf_minion:`saltenv` in your minion configuration file. This
   allows you to isolate which states are run to a specific branch/tag on a
   given minion. This also works nicely if you have different salt deployments
   for dev, qa, and prod. Boxes in dev can have :conf_minion:`saltenv` set to
   ``dev``, boxes in ``qa`` can have the :conf_minion:`saltenv` set to ``qa``,
   and boxes in prod can have the :conf_minion:`saltenv` set to ``base``.

2. At runtime, you can set the ``saltenv`` like so:

   .. code-block:: bash

       salt myminion state.apply saltenv=dev

   A couple notes about setting the saltenv at runtime:

   - It will take precedence over the :conf_minion:`saltenv` setting from the
     minion config file, and pairs nicely with cases where you do not have
     separate salt deployments for dev/qa/prod. You can have a box with
     :conf_minion:`saltenv` set to ``base``, which you can test your dev
     changes on by running your ``state.apply`` with ``saltenv=dev``.

   - If you don't set :conf_minion:`saltenv` in the minion config file, you
     _must_ specify it at runtime to avoid conflicting IDs.


If you branched ``qa`` off of ``master``, and ``dev`` off of ``qa``, you can
merge changes from ``dev`` into ``qa``, and then merge ``qa`` into master to
promote your changes to from dev to qa to prod.


.. _gitfs-whitelist-blacklist:

Environment Whitelist/Blacklist
===============================

.. versionadded:: 2014.7.0

The :conf_master:`gitfs_saltenv_whitelist` and
:conf_master:`gitfs_saltenv_blacklist` parameters allow for greater control
over which branches/tags are exposed as fileserver environments. Exact matches,
globs, and regular expressions are supported, and are evaluated in that order.
If using a regular expression, ``^`` and ``$`` must be omitted, and the
expression must match the entire branch/tag.

.. code-block:: yaml

    gitfs_saltenv_whitelist:
      - base
      - v1.*
      - 'mybranch\d+'

.. note::

    ``v1.*``, in this example, will match as both a glob and a regular
    expression (though it will have been matched as a glob, since globs are
    evaluated before regular expressions).

The behavior of the blacklist/whitelist will differ depending on which
combination of the two options is used:

* If only :conf_master:`gitfs_saltenv_whitelist` is used, then **only**
  branches/tags which match the whitelist will be available as environments

* If only :conf_master:`gitfs_saltenv_blacklist` is used, then the
  branches/tags which match the blacklist will **not** be available as
  environments

* If both are used, then the branches/tags which match the whitelist, but do
  **not** match the blacklist, will be available as environments.

.. _gitfs-authentication:

Authentication
==============

pygit2
------

.. versionadded:: 2014.7.0

Both HTTPS and SSH authentication are supported as of version 0.20.3, which is
the earliest version of pygit2_ supported by Salt for gitfs.

.. note::

    The examples below make use of per-remote configuration parameters, a
    feature new to Salt 2014.7.0. More information on these can be found
    :ref:`here <gitfs-per-remote-config>`.

HTTPS
~~~~~

For HTTPS repositories which require authentication, the username and password
can be provided like so:

.. code-block:: yaml

    gitfs_remotes:
      - https://domain.tld/myrepo.git:
        - user: git
        - password: mypassword

.. _gitfs-insecure-auth:

If the repository is served over HTTP instead of HTTPS, then Salt will by
default refuse to authenticate to it. This behavior can be overridden by adding
an ``insecure_auth`` parameter:

.. code-block:: yaml

    gitfs_remotes:
      - http://domain.tld/insecure_repo.git:
        - user: git
        - password: mypassword
        - insecure_auth: True

.. _pygit2-authentication-ssh:

SSH
~~~

SSH repositories can be configured using the ``ssh://`` protocol designation,
or using scp-like syntax. So, the following two configurations are equivalent:

* ``ssh://git@github.com/user/repo.git``
* ``git@github.com:user/repo.git``

Both :conf_master:`gitfs_pubkey` and :conf_master:`gitfs_privkey` (or their
:ref:`per-remote counterparts <gitfs-per-remote-config>`) must be configured in
order to authenticate to SSH-based repos. If the private key is protected with
a passphrase, it can be configured using :conf_master:`gitfs_passphrase` (or
simply ``passphrase`` if being configured :ref:`per-remote
<gitfs-per-remote-config>`). For example:

.. code-block:: yaml

    gitfs_remotes:
      - git@github.com:user/repo.git:
        - pubkey: /root/.ssh/id_rsa.pub
        - privkey: /root/.ssh/id_rsa
        - passphrase: myawesomepassphrase

Finally, the SSH host key must be :ref:`added to the known_hosts file
<gitfs-ssh-fingerprint>`.

.. note::
    There is a known issue with public-key SSH authentication to Microsoft
    Visual Studio (VSTS) with pygit2. This is due to a bug or lack of support
    for VSTS in older libssh2 releases. Known working releases include libssh2
    1.7.0 and later, and known incompatible releases include 1.5.0 and older.
    At the time of this writing, 1.6.0 has not been tested.

    Since upgrading libssh2 would require rebuilding many other packages (curl,
    etc.), followed by a rebuild of libgit2 and a reinstall of pygit2, an
    easier workaround for systems with older libssh2 is to use GitPython with a
    passphraseless key for authentication.

GitPython
---------

HTTPS
~~~~~

For HTTPS repositories which require authentication, the username and password
can be configured in one of two ways. The first way is to include them in the
URL using the format ``https://<user>:<password>@<url>``, like so:

.. code-block:: yaml

    gitfs_remotes:
      - https://git:mypassword@domain.tld/myrepo.git

The other way would be to configure the authentication in ``/var/lib/salt/.netrc``:

.. code-block:: text

    machine domain.tld
    login git
    password mypassword


If the repository is served over HTTP instead of HTTPS, then Salt will by
default refuse to authenticate to it. This behavior can be overridden by adding
an ``insecure_auth`` parameter:

.. code-block:: yaml

    gitfs_remotes:
      - http://git:mypassword@domain.tld/insecure_repo.git:
        - insecure_auth: True

SSH
~~~

Only passphrase-less SSH public key authentication is supported using
GitPython. **The auth parameters (pubkey, privkey, etc.) shown in the pygit2
authentication examples above do not work with GitPython.**

.. code-block:: yaml

    gitfs_remotes:
      - ssh://git@github.com/example/salt-states.git

Since GitPython_ wraps the git CLI, the private key must be located in
``~/.ssh/id_rsa`` for the user under which the Master is running, and should
have permissions of ``0600``. Also, in the absence of a user in the repo URL,
GitPython_ will (just as SSH does) attempt to login as the current user (in
other words, the user under which the Master is running, usually ``root``).

If a key needs to be used, then ``~/.ssh/config`` can be configured to use
the desired key. Information on how to do this can be found by viewing the
manpage for ``ssh_config``. Here's an example entry which can be added to the
``~/.ssh/config`` to use an alternate key for gitfs:

.. code-block:: text

    Host github.com
        IdentityFile /root/.ssh/id_rsa_gitfs

The ``Host`` parameter should be a hostname (or hostname glob) that matches the
domain name of the git repository.

It is also necessary to :ref:`add the SSH host key to the known_hosts file
<gitfs-ssh-fingerprint>`. The exception to this would be if strict host key
checking is disabled, which can be done by adding ``StrictHostKeyChecking no``
to the entry in ``~/.ssh/config``

.. code-block:: text

    Host github.com
        IdentityFile /root/.ssh/id_rsa_gitfs
        StrictHostKeyChecking no

However, this is generally regarded as insecure, and is not recommended.

.. _gitfs-gitlab:

GitLab
------

GitLab repositories work with the same ``user``/``password`` and SSH
mechanics described above, but the credential to use depends on the
GitLab account type. The Salt master is a service account, so the
recommended options, in decreasing order of preference, are:

1. **Deploy token** (project- or group-scoped, read-only) — best fit for
   gitfs and git_pillar. Create one in GitLab under
   *Settings → Repository → Deploy tokens* with the ``read_repository``
   scope. The token's username is the value GitLab shows on creation;
   the token itself is the password:

   .. code-block:: yaml

       gitfs_remotes:
         - https://gitlab.example.com/group/states.git:
           - user: salt-deploy-states
           - password: gldt-XXXXXXXXXXXXXXXXXXXX

2. **Project access token** (project-scoped, configurable role) — useful
   when the master must push (for example, for the ``winrepo`` runner).
   Username is the token name; password is the token:

   .. code-block:: yaml

       gitfs_remotes:
         - https://gitlab.example.com/group/winrepo.git:
           - user: salt-winrepo
           - password: glpat-XXXXXXXXXXXXXXXXXXXX

3. **Personal access token** — works, but ties the master's access to a
   real user. Authenticate as the token owner:

   .. code-block:: yaml

       gitfs_remotes:
         - https://gitlab.example.com/group/repo.git:
           - user: my-gitlab-user
           - password: glpat-XXXXXXXXXXXXXXXXXXXX

4. **Deploy key over SSH** — use a passphraseless key pair, add the
   public key under *Project → Settings → Repository → Deploy Keys*, and
   reference the private key:

   .. code-block:: yaml

       gitfs_remotes:
         - git@gitlab.example.com:group/repo.git:
           - pubkey: /etc/salt/gitlab_deploy.pub
           - privkey: /etc/salt/gitlab_deploy

   This works with both pygit2_ and GitPython_. For GitPython_, only
   passphraseless keys are supported (see the GitPython section above).
   Add the GitLab host key with
   ``salt-call --local ssh.set_known_host hostname=gitlab.example.com``
   first.

.. note::
    GitLab returns ``401 Unauthorized`` rather than a descriptive error
    when a deploy/project token has expired or lacks ``read_repository``
    scope. If gitfs starts logging ``401`` after working previously,
    re-check the token's expiry and scopes before changing the Salt
    configuration.

.. _gitfs-ssh-fingerprint:

Adding the SSH Host Key to the known_hosts File
-----------------------------------------------

To use SSH authentication, it is necessary to have the remote repository's SSH
host key in the ``~/.ssh/known_hosts`` file. If the master is also a minion,
this can be done using the :mod:`ssh.set_known_host
<salt.modules.ssh.set_known_host>` function:

.. code-block:: console

    # salt mymaster ssh.set_known_host user=root hostname=github.com
    mymaster:
        ----------
        new:
            ----------
            enc:
                ssh-rsa
            fingerprint:
                16:27:ac:a5:76:28:2d:36:63:1b:56:4d:eb:df:a6:48
            hostname:
                |1|OiefWWqOD4kwO3BhoIGa0loR5AA=|BIXVtmcTbPER+68HvXmceodDcfI=
            key:
                AAAAB3NzaC1yc2EAAAABIwAAAQEAq2A7hRGmdnm9tUDbO9IDSwBK6TbQa+PXYPCPy6rbTrTtw7PHkccKrpp0yVhp5HdEIcKr6pLlVDBfOLX9QUsyCOV0wzfjIJNlGEYsdlLJizHhbn2mUjvSAHQqZETYP81eFzLQNnPHt4EVVUh7VfDESU84KezmD5QlWpXLmvU31/yMf+Se8xhHTvKSCZIFImWwoG6mbUoWf9nzpIoaSjB+weqqUUmpaaasXVal72J+UX2B+2RPW3RcT0eOzQgqlJL3RKrTJvdsjE3JEAvGq3lGHSZXy28G3skua2SmVi/w4yCE6gbODqnTWlg7+wC604ydGXA8VJiS5ap43JXiUFFAaQ==
        old:
            None
        status:
            updated

If not, then the easiest way to add the key is to su to the user (usually
``root``) under which the salt-master runs and attempt to login to the
server via SSH:

.. code-block:: text

    $ su -
    Password:
    # ssh github.com
    The authenticity of host 'github.com (192.30.252.128)' can't be established.
    RSA key fingerprint is 16:27:ac:a5:76:28:2d:36:63:1b:56:4d:eb:df:a6:48.
    Are you sure you want to continue connecting (yes/no)? yes
    Warning: Permanently added 'github.com,192.30.252.128' (RSA) to the list of known hosts.
    Permission denied (publickey).

It doesn't matter if the login was successful, as answering ``yes`` will write
the fingerprint to the known_hosts file.

Verifying the Fingerprint
~~~~~~~~~~~~~~~~~~~~~~~~~

To verify that the correct fingerprint was added, it is a good idea to look it
up. One way to do this is to use ``nmap``:

.. code-block:: console

    $ nmap -p 22 github.com --script ssh-hostkey

    Starting Nmap 5.51 ( http://nmap.org ) at 2014-08-18 17:47 CDT
    Nmap scan report for github.com (192.30.252.129)
    Host is up (0.17s latency).
    Not shown: 996 filtered ports
    PORT     STATE SERVICE
    22/tcp   open  ssh
    | ssh-hostkey: 1024 ad:1c:08:a4:40:e3:6f:9c:f5:66:26:5d:4b:33:5d:8c (DSA)
    |_2048 16:27:ac:a5:76:28:2d:36:63:1b:56:4d:eb:df:a6:48 (RSA)
    80/tcp   open  http
    443/tcp  open  https
    9418/tcp open  git

    Nmap done: 1 IP address (1 host up) scanned in 28.78 seconds

Another way is to check one's own ``known_hosts`` file, using this one-liner:

.. code-block:: bash

    $ ssh-keygen -l -f /dev/stdin <<<`ssh-keyscan github.com 2>/dev/null` | awk '{print $2}'
    16:27:ac:a5:76:28:2d:36:63:1b:56:4d:eb:df:a6:48

.. warning::
    AWS tracks usage of nmap and may flag it as abuse. On AWS hosts, the
    ``ssh-keygen`` method is recommended for host key verification.

.. note::
    As of `OpenSSH 6.8`_ the SSH fingerprint is now shown as a base64-encoded
    SHA256 checksum of the host key. So, instead of the fingerprint looking
    like ``16:27:ac:a5:76:28:2d:36:63:1b:56:4d:eb:df:a6:48``, it would look
    like ``SHA256:nThbg6kXUpJWGl7E1IGOCspRomTxdCARLviKw6E5SY8``.

.. _`OpenSSH 6.8`: http://www.openssh.com/txt/release-6.8

Refreshing gitfs Upon Push
==========================

By default, Salt updates the remote fileserver backends every 60 seconds.
However, if it is desirable to refresh quicker than that, the :ref:`Reactor
System <reactor>` can be used to signal the master to update the fileserver on
each push, provided that the git server is also a Salt minion. There are three
steps to this process:

1. On the master, create a file **/srv/reactor/update_fileserver.sls**, with
   the following contents:

   .. code-block:: yaml

       update_fileserver:
         runner.fileserver.update

2. Add the following reactor configuration to the master config file:

   .. code-block:: yaml

       reactor:
         - 'salt/fileserver/gitfs/update':
           - /srv/reactor/update_fileserver.sls

3. On the git server, add a `post-receive hook`_

   a. If the user executing `git push` is the same as the minion user, use the following hook:

     .. code-block:: bash

         #!/usr/bin/env sh
         salt-call event.fire_master update salt/fileserver/gitfs/update

   b. To enable other git users to run the hook after a `push`, use sudo in the hook script:

     .. code-block:: bash

         #!/usr/bin/env sh
         sudo -u root salt-call event.fire_master update salt/fileserver/gitfs/update

4. If using sudo in the git hook (above), the policy must be changed to permit
   all users to fire the event.  Add the following policy to the sudoers file
   on the git server.

   .. code-block:: console

       Cmnd_Alias SALT_GIT_HOOK = /bin/salt-call event.fire_master update salt/fileserver/gitfs/update
       Defaults!SALT_GIT_HOOK !requiretty
       ALL ALL=(root) NOPASSWD: SALT_GIT_HOOK

The ``update`` argument right after :mod:`event.fire_master
<salt.modules.event.fire_master>` in this example can really be anything, as it
represents the data being passed in the event, and the passed data is ignored
by this reactor.

Similarly, the tag name ``salt/fileserver/gitfs/update`` can be replaced by
anything, so long as the usage is consistent.

The ``root`` user name in the hook script and sudo policy should be changed to
match the user under which the minion is running.

.. _`post-receive hook`: https://www.git-scm.com/book/en/v2/Customizing-Git-Git-Hooks#Server-Side-Hooks

.. _git-as-ext_pillar:

Using Git as an External Pillar Source
======================================

The git external pillar (a.k.a. git_pillar) has been rewritten for the 2015.8.0
release. This rewrite brings with it pygit2_ support (allowing for access to
authenticated repositories), as well as more granular support for per-remote
configuration. This configuration schema is detailed :ref:`here
<git-pillar-configuration>`.

.. _faq-gitfs-bug:

Why aren't my custom modules/states/etc. syncing to my Minions?
===============================================================

In versions 0.16.3 and older, when using the :mod:`git fileserver backend
<salt.fileserver.gitfs>`, certain versions of GitPython may generate errors
when fetching, which Salt fails to catch. While not fatal to the fetch process,
these interrupt the fileserver update that takes place before custom types are
synced, and thus interrupt the sync itself. Try disabling the git fileserver
backend in the master config, restarting the master, and attempting the sync
again.

This issue is worked around in Salt 0.16.4 and newer.
