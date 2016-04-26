.. _tutorial-gitfs:

==================================
Git Fileserver Backend Walkthrough
==================================

.. note::

    This walkthrough assumes basic knowledge of Salt. To get up to speed, check
    out the :doc:`Salt Walkthrough </topics/tutorials/walkthrough>`.

The gitfs backend allows Salt to serve files from git repositories. It can be
enabled by adding ``git`` to the :conf_master:`fileserver_backend` list, and
configuring one or more repositories in :conf_master:`gitfs_remotes`.

Branches and tags become Salt fileserver environments.


.. _gitfs-dependencies:

Installing Dependencies
=======================

Beginning with version 2014.7.0, both pygit2_ and Dulwich_ are supported as
alternatives to GitPython_. The desired provider can be configured using the
:conf_master:`gitfs_provider` parameter in the master config file.

If :conf_master:`gitfs_provider` is not configured, then Salt will prefer
pygit2_ if a suitable version is available, followed by GitPython_ and
Dulwich_.

.. note::
    It is recommended to always run the most recent version of any the below
    dependencies. Certain features of gitfs may not be available without
    the most recent version of the chosen library.

.. _pygit2: https://github.com/libgit2/pygit2
.. _Dulwich: https://www.samba.org/~jelmer/dulwich/
.. _GitPython: https://github.com/gitpython-developers/GitPython

pygit2
------

The minimum supported version of pygit2_ is 0.20.3. Availability for this
version of pygit2_ is still limited, though the SaltStack team is working to
get compatible versions available for as many platforms as possible.

For the Fedora/EPEL versions which have a new enough version packaged, the
following command would be used to install pygit2_:

.. code-block:: bash

    # yum install python-pygit2

Provided a valid version is packaged for Debian/Ubuntu (which is not currently
the case), the package name would be the same, and the following command would
be used to install it:

.. code-block:: bash

    # apt-get install python-pygit2


If pygit2_ is not packaged for the platform on which the Master is running, the
pygit2_ website has installation instructions here__. Keep in mind however that
following these instructions will install libgit2_ and pygit2_ without system
packages. Additionally, keep in mind that :ref:`SSH authentication in pygit2
<pygit2-authentication-ssh>` requires libssh2_ (*not* libssh) development
libraries to be present before libgit2_ is built. On some Debian-based distros
``pkg-config`` is also required to link libgit2_ with libssh2.

Additionally, version 0.21.0 of pygit2 introduced a dependency on python-cffi_,
which in turn depends on newer releases of libffi_. Upgrading libffi_ is not
advisable as several other applications depend on it, so on older LTS linux
releases pygit2_ 0.20.3 and libgit2_ 0.20.0 is the recommended combination.
While these are not packaged in the official repositories for Debian and
Ubuntu, SaltStack is actively working on adding packages for these to our
repositories_. The progress of this effort can be tracked here__.

.. warning::
    pygit2_ is actively developed and :ref:`frequently makes
    non-backwards-compatible API changes <pygit2-version-policy>`, even in
    minor releases. It is not uncommon for pygit2_ upgrades to result in errors
    in Salt. Please take care when upgrading pygit2_, and pay close attention
    to the changelog_, keeping an eye out for API changes. Errors can be
    reported on the :ref:`SaltStack issue tracker <saltstack-issue-tracker>`.

.. _pygit2-version-policy: http://www.pygit2.org/install.html#version-numbers
.. _changelog: https://github.com/libgit2/pygit2#changelog
.. _saltstack-issue-tracker: https://github.com/saltstack/salt/issues
.. __: http://www.pygit2.org/install.html
.. _libgit2: https://libgit2.github.com/
.. _libssh2: http://www.libssh2.org/
.. _python-cffi: https://pypi.python.org/pypi/cffi
.. _libffi: http://sourceware.org/libffi/
.. _repositories: https://repo.saltstack.com
.. __: https://github.com/saltstack/salt-pack/issues/70

GitPython
---------

GitPython_ 0.3.0 or newer is required to use GitPython for gitfs. For
RHEL-based Linux distros, a compatible version is available in EPEL, and can be
easily installed on the master using yum:

.. code-block:: bash

    # yum install GitPython

Ubuntu 14.04 LTS and Debian Wheezy (7.x) also have a compatible version packaged:

.. code-block:: bash

    # apt-get install python-git

If your master is running an older version (such as Ubuntu 12.04 LTS or Debian
Squeeze), then you will need to install GitPython using either pip_ or
easy_install (it is recommended to use pip). Version 0.3.2.RC1 is now marked as
the stable release in PyPI, so it should be a simple matter of running ``pip
install GitPython`` (or ``easy_install GitPython``) as root.

.. _`pip`: http://www.pip-installer.org/

.. warning::

    Keep in mind that if GitPython has been previously installed on the master
    using pip (even if it was subsequently uninstalled), then it may still
    exist in the build cache (typically ``/tmp/pip-build-root/GitPython``) if
    the cache is not cleared after installation. The package in the build cache
    will override any requirement specifiers, so if you try upgrading to
    version 0.3.2.RC1 by running ``pip install 'GitPython==0.3.2.RC1'`` then it
    will ignore this and simply install the version from the cache directory.
    Therefore, it may be necessary to delete the GitPython directory from the
    build cache in order to ensure that the specified version is installed.

Dulwich
-------

Dulwich 0.9.4 or newer is required to use Dulwich as backend for gitfs.

Dulwich is available in EPEL, and can be easily installed on the master using
yum:

.. code-block:: bash

    # yum install python-dulwich

For APT-based distros such as Ubuntu and Debian:

.. code-block:: bash

    # apt-get install python-dulwich

.. important::

    If switching to Dulwich from GitPython/pygit2, or switching from
    GitPython/pygit2 to Dulwich, it is necessary to clear the gitfs cache to
    avoid unpredictable behavior. This is probably a good idea whenever
    switching to a new :conf_master:`gitfs_provider`, but it is less important
    when switching between GitPython and pygit2.

    Beginning in version 2015.5.0, the gitfs cache can be easily cleared using
    the :mod:`fileserver.clear_cache <salt.runners.fileserver.clear_cache>`
    runner.

    .. code-block:: bash

        salt-run fileserver.clear_cache backend=git

    If the Master is running an earlier version, then the cache can be cleared
    by removing the ``gitfs`` and ``file_lists/gitfs`` directories (both paths
    relative to the master cache directory, usually
    ``/var/cache/salt/master``).

    .. code-block:: bash

        rm -rf /var/cache/salt/master{,/file_lists}/gitfs

Simple Configuration
====================

To use the gitfs backend, only two configuration changes are required on the
master:

1. Include ``git`` in the :conf_master:`fileserver_backend` list in the master
   config file:

   .. code-block:: yaml

       fileserver_backend:
         - git

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

   .. note::

       Dulwich does not recognize ``ssh://`` URLs, ``git+ssh://`` must be used
       instead. Salt version 2015.5.0 and later will automatically add the
       ``git+`` to the beginning of these URLs before fetching, but earlier
       Salt versions will fail to fetch unless the URL is specified using
       ``git+ssh://``.

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

    second.git:
        edit/dev_vimrc
        haproxy/init.sls

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
* :conf_master:`gitfs_mountpoint` (new in 2014.7.0)
* :conf_master:`gitfs_user` (**pygit2 only**, new in 2014.7.0)
* :conf_master:`gitfs_password` (**pygit2 only**, new in 2014.7.0)
* :conf_master:`gitfs_insecure_auth` (**pygit2 only**, new in 2014.7.0)
* :conf_master:`gitfs_pubkey` (**pygit2 only**, new in 2014.7.0)
* :conf_master:`gitfs_privkey` (**pygit2 only**, new in 2014.7.0)
* :conf_master:`gitfs_passphrase` (**pygit2 only**, new in 2014.7.0)

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
      - https://foo.com/bar.git:
        - name: second_bar_repo
        - root: other/salt
        - mountpoint: salt://other/bar
        - base: salt-base
      - http://foo.com/baz.git:
        - root: salt/states
        - user: joe
        - password: mysupersecretpassword
        - insecure_auth: True

.. important::

    There are two important distinctions which should be noted for per-remote
    configuration:

    1. The URL of a remote which has per-remote configuration must be suffixed
       with a colon.

    2. Per-remote configuration parameters are named like the global versions,
       with the ``gitfs_`` removed from the beginning. The exception being the
       ``name`` parameter which is only available to per-remote configurations.

In the example configuration above, the following is true:

1. The first and fourth gitfs remotes will use the ``develop`` branch/tag as the
   ``base`` environment, while the second and third will use the ``salt-base``
   branch/tag as the ``base`` environment.

2. The first remote will serve all files in the repository. The second
   remote will only serve files from the ``salt`` directory (and its
   subdirectories). The third remote will only server files from the
   ``other/salt`` directory (and its subdirectorys), while the fourth remote
   will only serve files from the ``salt/states`` directory (and its
   subdirectories).

3. The first and fourth remotes will have files located under the root of the
   Salt fileserver namespace (``salt://``). The files from the second remote
   will be located under ``salt://bar``, while the files from the third remote
   will be located under ``salt://other/bar``.

4. The second and third remotes reference the same repository and unique names
   need to be declared for duplicate gitfs remotes.

5. The fourth remote overrides the default behavior of :ref:`not authenticating
   to insecure (non-HTTPS) remotes <gitfs-insecure-auth>`.

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
file was properly located in the remote repository, and that all of the the
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

Using gitfs Alongside Other Backends
====================================

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


Branches, Environments, and Top Files
=====================================

When using the gitfs backend, branches, and tags will be mapped to environments
using the branch/tag name as an identifier.

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
to have a separate repository, containing only the ``top.sls`` file with just
one single ``master`` branch.

To map a branch other than ``master`` as the ``base`` environment, use the
:conf_master:`gitfs_base` parameter.

.. code-block:: yaml

    gitfs_base: salt-base

The base can also be configured on a :ref:`per-remote basis
<gitfs-per-remote-config>`.


.. _gitfs-whitelist-blacklist:

Environment Whitelist/Blacklist
===============================

.. versionadded:: 2014.7.0

The :conf_master:`gitfs_env_whitelist` and :conf_master:`gitfs_env_blacklist`
parameters allow for greater control over which branches/tags are exposed as
fileserver environments. Exact matches, globs, and regular expressions are
supported, and are evaluated in that order. If using a regular expression,
``^`` and ``$`` must be omitted, and the expression must match the entire
branch/tag.

.. code-block:: yaml

    gitfs_env_whitelist:
      - base
      - v1.*
      - 'mybranch\d+'

.. note::

    ``v1.*``, in this example, will match as both a glob and a regular
    expression (though it will have been matched as a glob, since globs are
    evaluated before regular expressions).

The behavior of the blacklist/whitelist will differ depending on which
combination of the two options is used:

* If only :conf_master:`gitfs_env_whitelist` is used, then **only** branches/tags
  which match the whitelist will be available as environments

* If only :conf_master:`gitfs_env_blacklist` is used, then the branches/tags
  which match the blacklist will **not** be available as environments

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

GitPython
---------

With GitPython_, only passphrase-less SSH public key authentication is
supported. **The auth parameters (pubkey, privkey, etc.) shown in the pygit2
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

.. _gitfs-ssh-fingerprint:

Adding the SSH Host Key to the known_hosts File
-----------------------------------------------

To use SSH authentication, it is necessary to have the remote repository's SSH
host key in the ``~/.ssh/known_hosts`` file. If the master is also a minion,
this can be done using the :mod:`ssh.set_known_host
<salt.modules.ssh.set_known_host>` function:

.. code-block:: bash

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

.. code-block:: bash

    $ su
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
up. One way to do this is to use nmap:

.. code-block:: bash

    $ nmap github.com --script ssh-hostkey

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

Another way is to check one's own known_hosts file, using this one-liner:

.. code-block:: bash

    $ ssh-keygen -l -f /dev/stdin <<<`ssh-keyscan -t rsa github.com 2>/dev/null` | awk '{print $2}'
    16:27:ac:a5:76:28:2d:36:63:1b:56:4d:eb:df:a6:48


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

3. On the git server, add a `post-receive hook`_ with the following contents:

   .. code-block:: bash

       #!/usr/bin/env sh

       salt-call event.fire_master update salt/fileserver/gitfs/update

The ``update`` argument right after :mod:`event.fire_master
<salt.modules.event.fire_master>` in this example can really be anything, as it
represents the data being passed in the event, and the passed data is ignored
by this reactor.

Similarly, the tag name ``salt/fileserver/gitfs/update`` can be replaced by
anything, so long as the usage is consistent.

.. _`post-receive hook`: http://www.git-scm.com/book/en/Customizing-Git-Git-Hooks#Server-Side-Hooks

.. _git-as-ext_pillar

Using Git as an External Pillar Source
======================================

The git external pillar (a.k.a. git_pillar) has been rewritten for the 2015.8.0
release. This rewrite brings with it pygit2_ support (allowing for access to
authenticated repositories), as well as more granular support for per-remote
configuration.

To make use of the new features, changes to the git ext_pillar configuration
must be made. The new configuration schema is detailed :ref:`here
<git-pillar-2015-8-0-and-later>`.

For Salt releases before 2015.8.0, click :ref:`here <git-pillar-pre-2015-8-0>`
for documentation.


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
