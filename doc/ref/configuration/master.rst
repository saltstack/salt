.. _configuration-salt-master:

===========================
Configuring the Salt Master
===========================

The Salt system is amazingly simple and easy to configure, the two components
of the Salt system each have a respective configuration file. The
:command:`salt-master` is configured via the master configuration file, and the
:command:`salt-minion` is configured via the minion configuration file.

.. seealso::
    :ref:`example master configuration file <configuration-examples-master>`

The configuration file for the salt-master is located at
:file:`/etc/salt/master`. The available options are as follows:

Primary Master Configuration
============================


.. conf_master:: interface

``interface``
-------------

Default: ``0.0.0.0`` (all interfaces)

The local interface to bind to.

.. code-block:: yaml

    interface: 192.168.0.1

.. conf_master:: ipv6

``ipv6``
--------

Default: ``False``

Whether the master should listen for IPv6 connections. If this is set to True,
the interface option must be adjusted too (for example: "interface: '::'")

.. code-block:: yaml

    ipv6: True

.. conf_master:: publish_port

``publish_port``
----------------

Default: ``4505``

The network port to set up the publication interface

.. code-block:: yaml

    publish_port: 4505


.. conf_master:: user

``user``
--------

Default: ``root``

The user to run the Salt processes

.. code-block:: yaml

    user: root

.. conf_master:: max_open_files

``max_open_files``
------------------

Default: ``max_open_files``

Each minion connecting to the master uses AT LEAST one file descriptor, the
master subscription connection. If enough minions connect you might start
seeing on the console(and then salt-master crashes)::

  Too many open files (tcp_listener.cpp:335)
  Aborted (core dumped)

By default this value will be the one of `ulimit -Hn`, i.e., the hard limit for
max open files.

If you wish to set a different value than the default one, uncomment and
configure this setting. Remember that this value CANNOT be higher than the
hard limit. Raising the hard limit depends on your OS and/or distribution,
a good way to find the limit is to search the internet for(for example)::

  raise max open files hard limit debian

.. code-block:: yaml

    max_open_files: 100000

.. conf_master:: worker_threads

``worker_threads``
------------------

Default: ``5``

The number of threads to start for receiving commands and replies from minions.
If minions are stalling on replies because you have many minions, raise the
worker_threads value.

Worker threads should not be put below 3 when using the peer system, but can
drop down to 1 worker otherwise.

.. code-block:: yaml

    worker_threads: 5

.. conf_master:: ret_port

``ret_port``
------------

Default: ``4506``

The port used by the return server, this is the server used by Salt to receive
execution returns and command executions.

.. code-block:: yaml

    ret_port: 4506

.. conf_master:: pidfile

``pidfile``
-----------

Default: ``/var/run/salt-master.pid``

Specify the location of the master pidfile

.. code-block:: yaml

    pidfile: /var/run/salt-master.pid

.. conf_master:: root_dir

``root_dir``
------------

Default: :file:`/`

The system root directory to operate from, change this to make Salt run from
an alternative root.

.. code-block:: yaml

    root_dir: /

.. note::

    This directory is prepended to the following options:
    :conf_master:`pki_dir`, :conf_master:`cachedir`, :conf_master:`sock_dir`,
    :conf_master:`log_file`, :conf_master:`autosign_file`,
    :conf_master:`autoreject_file`, :conf_master:`pidfile`.

.. conf_master:: pki_dir

``pki_dir``
-----------

Default: :file:`/etc/salt/pki`

The directory to store the pki authentication keys.

.. code-block:: yaml

    pki_dir: /etc/salt/pki

.. conf_master:: extension_modules

``extension_modules``
---------------------

Directory for custom modules. This directory can contain subdirectories for
each of Salt's module types such as "runners", "output", "wheel", "modules",
"states", "returners", etc. This path is appended to :conf_master:`root_dir`.

.. code-block:: yaml

    extension_modules: srv/modules

.. conf_master:: cachedir

``cachedir``
------------

Default: :file:`/var/cache/salt`

The location used to store cache information, particularly the job information
for executed salt commands.

.. code-block:: yaml

    cachedir: /var/cache/salt

.. conf_master:: verify_env

``verify_env``
--------------

Default: ``True``

Verify and set permissions on configuration directories at startup.

.. code-block:: yaml

    verify_env: True

.. conf_master:: keep_jobs

``keep_jobs``
-------------

Default: ``24``

Set the number of hours to keep old job information

.. conf_master:: timeout

``timeout``
-----------

Default: ``5``

Set the default timeout for the salt command and api. 

.. conf_master:: loop_interval

``loop_interval``
-----------------

Default: ``60``

The loop_interval option controls the seconds for the master's maintenance
process check cycle. This process updates file server backends, cleans the
job cache and executes the scheduler.

.. conf_master:: output

``output``
----------

Default: ``nested``

Set the default outputter used by the salt command.

.. conf_master:: color

``color``
---------

Default: ``True``

By default output is colored, to disable colored output set the color value
to False

.. code-block:: yaml

    color: False

.. conf_master:: sock_dir

``sock_dir``
------------

Default: :file:`/var/run/salt/master`

Set the location to use for creating Unix sockets for master process
communication

.. code-block:: yaml

    sock_dir: /var/run/salt/master

.. conf_master:: enable_gpu_grains

``enable_gpu_grains``
---------------------

Default: ``False``

The master can take a while to start up when lspci and/or dmidecode is used
to populate the grains for the master. Enable if you want to see GPU hardware
data for your master.

.. conf_master:: job_cache

``job_cache``
-------------

Default: ``True``

The master maintains a job cache, while this is a great addition it can be
a burden on the master for larger deployments (over 5000 minions).
Disabling the job cache will make previously executed jobs unavailable to
the jobs system and is not generally recommended. Normally it is wise to make
sure the master has access to a faster IO system or a tmpfs is mounted to the
jobs dir

.. conf_master:: minion_data_cache

``minion_data_cache``
---------------------

Default: ``True``

The minion data cache is a cache of information about the minions stored on the
master, this information is primarily the pillar and grains data. The data is
cached in the Master cachedir under the name of the minion and used to pre
determine what minions are expected to reply from executions.

.. code-block:: yaml

    minion_data_cache: True

.. conf_master:: ext_job_cache

``ext_job_cache``
-----------------

Default: ``''``

Used to specify a default returner for all minions, when this option is set
the specified returner needs to be properly configured and the minions will
always default to sending returns to this returner. This will also disable the
local job cache on the master

.. code-block:: yaml

    ext_job_cache: redis

.. conf_master:: enforce_mine_cache

``enforce_mine_cache``
----------------------

Default: False

By-default when disabling the minion_data_cache mine will stop working since
it is based on cached data, by enabling this option we explicitly enabling
only the cache for the mine system.

.. code-block:: yaml

    enforce_mine_cache: False


Master Security Settings
========================

.. conf_master:: open_mode

``open_mode``
-------------

Default: ``False``

Open mode is a dangerous security feature. One problem encountered with pki
authentication systems is that keys can become "mixed up" and authentication
begins to fail. Open mode turns off authentication and tells the master to
accept all authentication. This will clean up the pki keys received from the
minions. Open mode should not be turned on for general use. Open mode should
only be used for a short period of time to clean up pki keys. To turn on open
mode set this value to ``True``.

.. code-block:: yaml

    open_mode: False

.. conf_master:: auto_accept

``auto_accept``
---------------

Default: ``False``

Enable auto_accept. This setting will automatically accept all incoming
public keys from minions.

.. code-block:: yaml

    auto_accept: False

.. conf_master:: autosign_file

``autosign_file``
-----------------

Default: ``not defined``

If the ``autosign_file`` is specified incoming keys specified in the autosign_file
will be automatically accepted. Matches will be searched for first by string
comparison, then by globbing, then by full-string regex matching. This is
insecure!

.. conf_master:: autoreject_file

``autoreject_file``
-------------------

.. versionadded:: 2014.1.0 (Hydrogen)

Default: ``not defined``

Works like :conf_master:`autosign_file`, but instead allows you to specify
minion IDs for which keys will automatically be rejected. Will override both
membership in the :conf_master:`autosign_file` and the
:conf_master:`auto_accept` setting.

.. conf_master:: client_acl

``client_acl``
--------------

Default: ``{}``

Enable user accounts on the master to execute specific modules. These modules
can be expressed as regular expressions

.. code-block:: yaml

    client_acl:
      fred:
        - test.ping
        - pkg.*

.. conf_master:: client_acl_blacklist

``client_acl_blacklist``
------------------------

Default: ``{}``

Blacklist users or modules

This example would blacklist all non sudo users, including root from
running any commands. It would also blacklist any use of the "cmd"
module.

This is completely disabled by default.

.. code-block:: yaml

    client_acl_blacklist:
      users:
        - root
        - '^(?!sudo_).*$'   #  all non sudo users
      modules:
        - cmd

.. conf_master:: external_auth

``external_auth``
-----------------

Default: ``{}``

The external auth system uses the Salt auth modules to authenticate and
validate users to access areas of the Salt system.

.. code-block:: yaml

    external_auth:
      pam:
        fred:
          - test.*

.. conf_master:: token_expire

``token_expire``
----------------

Default: ``43200``

Time (in seconds) for a newly generated token to live. Default: 12 hours

.. code-block:: yaml

    token_expire: 43200

.. conf_master:: file_recv

``file_recv``
-------------

Default: ``False``

Allow minions to push files to the master. This is disabled by default, for
security purposes.

.. code-block:: yaml

    file_recv: False 


Master Module Management
========================

.. conf_master:: runner_dirs

``runner_dirs``
---------------

Default: ``[]``

Set additional directories to search for runner modules

.. conf_master:: cython_enable

``cython_enable``
-----------------

Default: ``False``

Set to true to enable cython modules (.pyx files) to be compiled on the fly on
the Salt master

.. code-block:: yaml

    cython_enable: False


Master State System Settings
============================

.. conf_master:: state_top

``state_top``
-------------

Default: ``top.sls``

The state system uses a "top" file to tell the minions what environment to
use and what modules to use. The state_top file is defined relative to the
root of the base environment

.. code-block:: yaml

    state_top: top.sls

.. conf_master:: master_tops

``master_tops``
---------------

Default: ``{}``

The master_tops option replaces the external_nodes option by creating
a plugable system for the generation of external top data. The external_nodes
option is deprecated by the master_tops option.
To gain the capabilities of the classic external_nodes system, use the
following configuration:

.. code-block:: yaml

    master_tops:
      ext_nodes: <Shell command which returns yaml>

.. conf_master:: external_nodes

``external_nodes``
------------------

Default: None

The external_nodes option allows Salt to gather data that would normally be
placed in a top file from and external node controller. The external_nodes
option is the executable that will return the ENC data. Remember that Salt
will look for external nodes AND top files and combine the results if both
are enabled and available!

.. code-block:: yaml

    external_nodes: cobbler-ext-nodes

.. conf_master:: renderer

``renderer``
------------

Default: ``yaml_jinja``

The renderer to use on the minions to render the state data

.. code-block:: yaml

    renderer: yaml_jinja

.. conf_master:: failhard

``failhard``
------------

Default: ``False``

Set the global failhard flag, this informs all states to stop running states
at the moment a single state fails

.. code-block:: yaml

    failhard: False

.. conf_master:: state_verbose

``state_verbose``
-----------------

Default: ``True``

Controls the verbosity of state runs. By default, the results of all states are
returned, but setting this value to ``False`` will cause salt to only display
output for states which either failed, or succeeded without making any changes
to the minion.

.. code-block:: yaml

    state_verbose: False

.. conf_master:: state_output

``state_output``
----------------

Default: ``full``

The state_output setting changes if the output is the full multi line
output for each changed state if set to 'full', but if set to 'terse'
the output will be shortened to a single line.  If set to 'mixed', the output
will be terse unless a state failed, in which case that output will be full.
If set to 'changes', the output will be full unless the state didn't change.

.. code-block:: yaml

    state_output: full

.. conf_master:: yaml_utf8 

``yaml_utf8``
-------------

Default: ``False``

Enable extra yaml render routines for states containing UTF characters

.. code-block:: yaml

    yaml_utf8: False

.. conf_master:: test

``test``
--------

Default: ``False``

Set all state calls to only test if they are going to actually make changes
or just post what changes are going to be made

.. code-block:: yaml

    test: False

Master File Server Settings
===========================

.. conf_master:: fileserver_backend

``fileserver_backend``
----------------------

Default:

.. code-block:: yaml

    fileserver_backend:
      - roots

Salt supports a modular fileserver backend system, this system allows the salt
master to link directly to third party systems to gather and manage the files
available to minions. Multiple backends can be configured and will be searched
for the requested file in the order in which they are defined here. The default
setting only enables the standard backend ``roots``, which is configured using
the :conf_master:`file_roots` option.

Example:

.. code-block:: yaml

    fileserver_backend:
      - roots
      - git

.. conf_master:: hash_type

``hash_type``
-------------

Default: ``md5``

The hash_type is the hash to use when discovering the hash of a file on
the master server. The default is md5, but sha1, sha224, sha256, sha384
and sha512 are also supported.

.. code-block:: yaml

    hash_type: md5

.. conf_master:: file_buffer_size

``file_buffer_size``
--------------------

Default: ``1048576``

The buffer size in the file server in bytes

.. code-block:: yaml

    file_buffer_size: 1048576

.. conf_master:: file_ignore_regex

``file_ignore_regex``
---------------------

Default: ``''``

A regular expression (or a list of expressions) that will be matched
against the file path before syncing the modules and states to the minions.
This includes files affected by the file.recurse state.
For example, if you manage your custom modules and states in subversion
and don't want all the '.svn' folders and content synced to your minions,
you could set this to '/\.svn($|/)'. By default nothing is ignored.

.. code-block:: yaml

    file_ignore_regex:
      - '/\.svn($|/)'
      - '/\.git($|/)'

.. conf_master:: file_ignore_glob

``file_ignore_glob``
--------------------

Default ``''``

A file glob (or list of file globs) that will be matched against the file
path before syncing the modules and states to the minions. This is similar
to file_ignore_regex above, but works on globs instead of regex. By default
nothing is ignored.

.. code-block:: yaml
   
    file_ignore_glob:
      - '\*.pyc'
      - '\*/somefolder/\*.bak'
      - '\*.swp'

roots: Master's Local File Server
---------------------------------

.. conf_master:: file_roots

``file_roots``
**************

Default:

.. code-block:: yaml

    base:
      - /srv/salt

Salt runs a lightweight file server written in ZeroMQ to deliver files to
minions. This file server is built into the master daemon and does not
require a dedicated port.

The file server works on environments passed to the master. Each environment
can have multiple root directories. The subdirectories in the multiple file
roots cannot match, otherwise the downloaded files will not be able to be
reliably ensured. A base environment is required to house the top file.
Example:

.. code-block:: yaml

    file_roots:
      base:
        - /srv/salt
      dev:
        - /srv/salt/dev/services
        - /srv/salt/dev/states
      prod:
        - /srv/salt/prod/services
        - /srv/salt/prod/states

git: Git Remote File Server Backend
-----------------------------------

.. conf_master:: gitfs_remotes

``gitfs_remotes``
*****************

Default: ``[]``

When using the ``git`` fileserver backend at least one git remote needs to be
defined. The user running the salt master will need read access to the repo.

The repos will be searched in order to find the file requested by a client and
the first repo to have the file will return it. Branches and tags are
translated into salt environments.

.. code-block:: yaml

    gitfs_remotes:
      - git://github.com/saltstack/salt-states.git
      - file:///var/git/saltmaster

.. note::

    ``file://`` repos will be treated as a remote, so refs you want used must
    exist in that repo as *local* refs.

.. note::

    As of the upcoming **Helium** release (and right now in the development
    branch), it is possible to have per-repo versions of the
    :conf_master:`gitfs_base`, :conf_master:`gitfs_root`, and
    :conf_master:`gitfs_mountpoint` parameters. For example:

    .. code-block:: yaml

        gitfs_remotes:
          - https://foo.com/foo.git
          - https://foo.com/bar.git:
            - root: salt
            - mountpoint: salt://foo/bar/baz
            - base: salt-base
          - https://foo.com/baz.git:
            - root: salt/states

.. conf_master:: gitfs_provider

``gitfs_provider``
******************

.. versionadded:: Helium

Gitfs can be provided by one of two python modules: `GitPython`_ or `pygit2`_.
If using pygit2, both libgit2 and git itself must also be installed. More
information can be found in the :mod:`gitfs backend documentation
<salt.fileserver.gitfs>`.

.. _GitPython: https://github.com/gitpython-developers/GitPython
.. _pygit2: https://github.com/libgit2/pygit2

.. code-block:: yaml

    gitfs_provider: pygit2

.. conf_master:: gitfs_ssl_verify

``gitfs_ssl_verify``
********************

Default: ``[]``

The ``gitfs_ssl_verify`` option specifies whether to ignore ssl certificate
errors when contacting the gitfs backend. You might want to set this to
false if you're using a git backend that uses a self-signed certificate but
keep in mind that setting this flag to anything other than the default of True
is a security concern, you may want to try using the ssh transport.

.. code-block:: yaml

    gitfs_ssl_verify: True

.. conf_master:: gitfs_mountpoint

``gitfs_mountpoint``
********************

.. versionadded:: Helium

Default: ``''``

Specifies a path on the salt fileserver from which gitfs remotes are served.
Can be used in conjunction with :conf_master:`gitfs_root`. Can also be
configured on a per-remote basis, see :conf_master:`here <gitfs_remotes>` for
more info.

.. code-block:: yaml

    gitfs_mountpoint: salt://foo/bar

.. note::

    The ``salt://`` protocol designation can be left off (in other words,
    ``foo/bar`` and ``salt://foo/bar`` are equivalent).

.. conf_master:: gitfs_root

``gitfs_root``
**************

Default: ``''``

Serve files from a subdirectory within the repository, instead of the root.
This is useful when there are files in the repository that should not be
available to the Salt fileserver. Can be used in conjunction with
:conf_master:`gitfs_mountpoint`.

.. code-block:: yaml

    gitfs_root: somefolder/otherfolder

.. versionchanged:: Helium

   Ability to specify gitfs roots on a per-remote basis was added. See
   :conf_master:`here <gitfs_remotes>` for more info.

.. conf_master:: gitfs_base

``gitfs_base``
**************

Default: ``master``

Defines which branch/tag should be used as the ``base`` environment.

.. versionchanged:: Helium
    Can also be configured on a per-remote basis, see :conf_master:`here
    <gitfs_remotes>` for more info.

.. code-block:: yaml

    gitfs_base: salt

.. conf_master:: gitfs_env_whitelist

``gitfs_env_whitelist``
***********************

.. versionadded:: Helium

Default: ``[]``

Used to restrict which environments are made available. Can speed up state runs
if your gitfs remotes contain many branches/tags. Full names, globs, and
regular expressions are supported. If using a regular expression, the
expression must match the entire minion ID.

If used, only branches/tags/SHAs which match one of the specified expressions
will be exposed as fileserver environments.

If used in conjunction with :conf_master:`gitfs_env_blacklist`, then the subset
of branches/tags/SHAs which match the whitelist but do *not* match the
blacklist will be exposed as fileserver environments.

.. code-block:: yaml

    gitfs_env_whitelist:
      - base
      - v1.*
      - 'mybranch\d+'

.. conf_master:: gitfs_env_blacklist

``gitfs_env_blacklist``
***********************

.. versionadded:: Helium

Default: ``[]``

Used to restrict which environments are made available. Can speed up state runs
if your gitfs remotes contain many branches/tags. Full names, globs, and
regular expressions are supported. If using a regular expression, the
expression must match the entire minion ID.

If used, branches/tags/SHAs which match one of the specified expressions will
*not* be exposed as fileserver environments.

If used in conjunction with :conf_master:`gitfs_env_whitelist`, then the subset
of branches/tags/SHAs which match the whitelist but do *not* match the
blacklist will be exposed as fileserver environments.

.. code-block:: yaml

    gitfs_env_blacklist:
      - base
      - v1.*
      - 'mybranch\d+'

hg: Mercurial Remote File Server Backend
----------------------------------------

.. conf_master:: hgfs_remotes

``hgfs_remotes``
****************

.. versionadded:: 0.17.0

Default: ``[]``

When using the ``hg`` fileserver backend at least one mercurial remote needs to
be defined. The user running the salt master will need read access to the repo.

The repos will be searched in order to find the file requested by a client and
the first repo to have the file will return it. Branches and/or bookmarks are
translated into salt environments, as defined by the
:conf_master:`hgfs_branch_method` parameter.

.. code-block:: yaml

    hgfs_remotes:
      - https://username@bitbucket.org/username/reponame

.. note::

    As of the upcoming **Helium** release (and right now in the development
    branch), it is possible to have per-repo versions of the
    :conf_master:`hgfs_root`, :conf_master:`hgfs_mountpoint`,
    :conf_master:`hgfs_base`, and :conf_master:`hgfs_branch_method` parameters.
    For example:

    .. code-block:: yaml

        hgfs_remotes:
          - https://username@bitbucket.org/username/repo1
            - base: saltstates
          - https://username@bitbucket.org/username/repo2:
            - root: salt
            - mountpoint: salt://foo/bar/baz
          - https://username@bitbucket.org/username/repo3:
            - root: salt/states
            - branch_method: mixed

.. conf_master:: hgfs_branch_method

``hgfs_branch_method``
**********************

.. versionadded:: 0.17.0

Default: ``branches``

Defines the objects that will be used as fileserver environments.

* ``branches`` - Only branches and tags will be used
* ``bookmarks`` - Only bookmarks and tags will be used
* ``mixed`` - Branches, bookmarks, and tags will be used

.. code-block:: yaml

    hgfs_branch_method: mixed

.. note::

    Starting in version 2014.1.0 (Hydrogen), the value of the
    :conf_master:`hgfs_base` parameter defines which branch is used as the
    ``base`` environment, allowing for a ``base`` environment to be used with
    an :conf_master:`hgfs_branch_method` of ``bookmarks``.

    Prior to this release, the ``default`` branch will be used as the ``base``
    environment.

.. conf_master:: hgfs_mountpoint

``hgfs_mountpoint``
*******************

.. versionadded:: Helium

Default: ``''``

Specifies a path on the salt fileserver from which hgfs remotes are served.
Can be used in conjunction with :conf_master:`hgfs_root`. Can also be
configured on a per-remote basis, see :conf_master:`here <hgfs_remotes>` for
more info.

.. code-block:: yaml

    hgfs_mountpoint: salt://foo/bar

.. note::

    The ``salt://`` protocol designation can be left off (in other words,
    ``foo/bar`` and ``salt://foo/bar`` are equivalent).

.. conf_master:: hgfs_root

``hgfs_root``
*************

.. versionadded:: 0.17.0

Default: ``''``

Serve files from a subdirectory within the repository, instead of the root.
This is useful when there are files in the repository that should not be
available to the Salt fileserver. Can be used in conjunction with
:conf_master:`hgfs_mountpoint`.

.. code-block:: yaml

    hgfs_root: somefolder/otherfolder

.. versionchanged:: Helium

   Ability to specify hgfs roots on a per-remote basis was added. See
   :conf_master:`here <hgfs_remotes>` for more info.

.. conf_master:: hgfs_base

``hgfs_base``
*************

.. versionadded:: 2014.1.0 (Hydrogen)

Default: ``default``

Defines which branch should be used as the ``base`` environment. Change this if
:conf_master:`hgfs_branch_method` is set to ``bookmarks`` to specify which
bookmark should be used as the ``base`` environment.

.. code-block:: yaml

    hgfs_base: salt

.. conf_master:: hgfs_env_whitelist

``hgfs_env_whitelist``
**********************

.. versionadded:: Helium

Default: ``[]``

Used to restrict which environments are made available. Can speed up state runs
if your hgfs remotes contain many branches/bookmarks/tags. Full names, globs,
and regular expressions are supported. If using a regular expression, the
expression must match the entire minion ID.

If used, only branches/bookmarks/tags which match one of the specified
expressions will be exposed as fileserver environments.

If used in conjunction with :conf_master:`hgfs_env_blacklist`, then the subset
of branches/bookmarks/tags which match the whitelist but do *not* match the
blacklist will be exposed as fileserver environments.

.. code-block:: yaml

    hgfs_env_whitelist:
      - base
      - v1.*
      - 'mybranch\d+'

.. conf_master:: hgfs_env_blacklist

``hgfs_env_blacklist``
**********************

.. versionadded:: Helium

Default: ``[]``

Used to restrict which environments are made available. Can speed up state runs
if your hgfs remotes contain many branches/bookmarks/tags. Full names, globs,
and regular expressions are supported. If using a regular expression, the
expression must match the entire minion ID.

If used, branches/bookmarks/tags which match one of the specified expressions
will *not* be exposed as fileserver environments.

If used in conjunction with :conf_master:`hgfs_env_whitelist`, then the subset
of branches/bookmarks/tags which match the whitelist but do *not* match the
blacklist will be exposed as fileserver environments.

.. code-block:: yaml

    hgfs_env_blacklist:
      - base
      - v1.*
      - 'mybranch\d+'

svn: Subversion Remote File Server Backend
------------------------------------------

.. conf_master:: svnfs_remotes

``svnfs_remotes``
*****************

.. versionadded:: 0.17.0

Default: ``[]``

When using the ``svn`` fileserver backend at least one subversion remote needs
to be defined. The user running the salt master will need read access to the
repo.

The repos will be searched in order to find the file requested by a client and
the first repo to have the file will return it. The trunk, branches, and tags
become environments, with the trunk being the ``base`` environment.

.. code-block:: yaml

    svnfs_remotes:
      - svn://foo.com/svn/myproject

.. note::

    As of the upcoming **Helium** release (and right now in the development
    branch), it is possible to have per-repo versions of the following
    configuration parameters:

    * :conf_master:`svnfs_root`
    * :conf_master:`svnfs_mountpoint`
    * :conf_master:`svnfs_trunk`
    * :conf_master:`svnfs_branches`
    * :conf_master:`svnfs_tags`

    For example:

    .. code-block:: yaml

        svnfs_remotes:
          - svn://foo.com/svn/project1
          - svn://foo.com/svn/project2:
            - root: salt
            - mountpoint: salt://foo/bar/baz
          - svn//foo.com/svn/project3:
            - root: salt/states
            - branches: branch
            - tags: tag

.. conf_master:: svnfs_mountpoint

``svnfs_mountpoint``
********************

.. versionadded:: Helium

Default: ``''``

Specifies a path on the salt fileserver from which svnfs remotes are served.
Can be used in conjunction with :conf_master:`svnfs_root`. Can also be
configured on a per-remote basis, see :conf_master:`here <svnfs_remotes>` for
more info.

.. code-block:: yaml

    svnfs_mountpoint: salt://foo/bar

.. note::

    The ``salt://`` protocol designation can be left off (in other words,
    ``foo/bar`` and ``salt://foo/bar`` are equivalent).

.. conf_master:: svnfs_root

``svnfs_root``
**************

.. versionadded:: 0.17.0

Default: ``''``

Serve files from a subdirectory within the repository, instead of the root.
This is useful when there are files in the repository that should not be
available to the Salt fileserver. Can be used in conjunction with
:conf_master:`svnfs_mountpoint`.

.. code-block:: yaml

    svnfs_root: somefolder/otherfolder

.. versionchanged:: Helium

   Ability to specify svnfs roots on a per-remote basis was added. See
   :conf_master:`here <svnfs_remotes>` for more info.

.. conf_master:: svnfs_trunk

``svnfs_trunk``
***************

.. versionadded:: Helium

Default: ``trunk``

Path relative to the root of the repository where the trunk is located. Can
also be configured on a per-remote basis, see :conf_master:`here
<svnfs_remotes>` for more info.

.. code-block:: yaml

    svnfs_trunk: trunk

.. conf_master:: svnfs_branches

``svnfs_branches``
******************

.. versionadded:: Helium

Default: ``branches``

Path relative to the root of the repository where the branches are located. Can
also be configured on a per-remote basis, see :conf_master:`here
<svnfs_remotes>` for more info.

.. code-block:: yaml

    svnfs_branches: branches

.. conf_master:: svnfs_tags

``svnfs_tags``
**************

.. versionadded:: Helium

Default: ``tags``

Path relative to the root of the repository where the tags is located. Can also
be configured on a per-remote basis, see :conf_master:`here <svnfs_remotes>`
for more info.

.. code-block:: yaml

    svnfs_tags: tags

.. conf_master:: svnfs_env_whitelist

``svnfs_env_whitelist``
***********************

.. versionadded:: Helium

Default: ``[]``

Used to restrict which environments are made available. Can speed up state runs
if your svnfs remotes contain many branches/tags. Full names, globs, and
regular expressions are supported. If using a regular expression, the expression
must match the entire minion ID.

If used, only branches/tags which match one of the specified expressions will
be exposed as fileserver environments.

If used in conjunction with :conf_master:`svnfs_env_blacklist`, then the subset
of branches/tags which match the whitelist but do *not* match the blacklist
will be exposed as fileserver environments.

.. code-block:: yaml

    svnfs_env_whitelist:
      - base
      - v1.*
      - 'mybranch\d+'

.. conf_master:: svnfs_env_blacklist

``svnfs_env_blacklist``
***********************

.. versionadded:: Helium

Default: ``[]``

Used to restrict which environments are made available. Can speed up state runs
if your svnfs remotes contain many branches/tags. Full names, globs, and
regular expressions are supported. If using a regular expression, the
expression must match the entire minion ID.

If used, branches/tags which match one of the specified expressions will *not*
be exposed as fileserver environments.

If used in conjunction with :conf_master:`svnfs_env_whitelist`, then the subset
of branches/tags which match the whitelist but do *not* match the blacklist
will be exposed as fileserver environments.

.. code-block:: yaml

    svnfs_env_blacklist:
      - base
      - v1.*
      - 'mybranch\d+'

minion: MinionFS Remote File Server Backend
-------------------------------------------

.. conf_master:: minionfs_env

``minionfs_env``
****************

.. versionadded:: Helium

Default: ``base``

Environment from which MinionFS files are made available.

.. code-block:: yaml

    minionfs_env: minionfs

.. conf_master:: minionfs_mountpoint

``minionfs_mountpoint``
***********************

.. versionadded:: Helium

Default: ``''``

Specifies a path on the salt fileserver from which minionfs files are served.

.. code-block:: yaml

    minionfs_mountpoint: salt://foo/bar

.. note::

    The ``salt://`` protocol designation can be left off (in other words,
    ``foo/bar`` and ``salt://foo/bar`` are equivalent).

.. conf_master:: minionfs_whitelist

``minionfs_whitelist``
**********************

.. versionadded:: Helium

Default: ``[]``

Used to restrict which minions' pushed files are exposed via minionfs. If using
a regular expression, the expression must match the entire minion ID.

If used, only the pushed files from minions which match one of the specified
expressions will be exposed.

If used in conjunction with :conf_master:`minionfs_blacklist`, then the subset
of hosts which match the whitelist but do *not* match the blacklist will be
exposed.

.. code-block:: yaml

    minionfs_whitelist:
      - base
      - v1.*
      - 'mybranch\d+'

.. conf_master:: minionfs_blacklist

``minionfs_blacklist``
**********************

.. versionadded:: Helium

Default: ``[]``

Used to restrict which minions' pushed files are exposed via minionfs. If using
a regular expression, the expression must match the entire minion ID.

If used, only the pushed files from minions which match one of the specified
expressions will *not* be exposed.

If used in conjunction with :conf_master:`minionfs_whitelist`, then the subset
of hosts which match the whitelist but do *not* match the blacklist will be
exposed.

.. code-block:: yaml

    minionfs_blacklist:
      - base
      - v1.*
      - 'mybranch\d+'


.. _pillar-configuration:

Pillar Configuration
====================

.. conf_master:: pillar_roots

``pillar_roots``
----------------

Default:

.. code-block:: yaml

    base:
      - /srv/pillar

Set the environments and directories used to hold pillar sls data. This
configuration is the same as :conf_master:`file_roots`:

.. code-block:: yaml

    pillar_roots:
      base:
        - /srv/pillar
      dev:
        - /srv/pillar/dev
      prod:
        - /srv/pillar/prod

.. conf_master:: ext_pillar

``ext_pillar``
--------------

The ext_pillar option allows for any number of external pillar interfaces to be
called when populating pillar data. The configuration is based on ext_pillar
functions. The available ext_pillar functions can be found herein:

:blob:`salt/pillar`

By default, the ext_pillar interface is not configured to run.

Default: ``None``

.. code-block:: yaml

    ext_pillar:
      - hiera: /etc/hiera.yaml
      - cmd_yaml: cat /etc/salt/yaml
      - reclass:
          inventory_base_uri: /etc/reclass

There are additional details at :ref:`salt-pillars`

Syndic Server Settings
======================

A Salt syndic is a Salt master used to pass commands from a higher Salt master to
minions below the syndic. Using the syndic is simple. If this is a master that
will have syndic servers(s) below it, set the "order_masters" setting to True. If this
is a master that will be running a syndic daemon for passthrough the
"syndic_master" setting needs to be set to the location of the master server

Do not not forget that in other word it means that it shares with the local minion it's ID and PKI_DIR.

.. conf_master:: order_masters

``order_masters``
-----------------

Default: ``False``

Extra data needs to be sent with publications if the master is controlling a
lower level master via a syndic minion. If this is the case the order_masters
value must be set to True

.. code-block:: yaml

    order_masters: False

.. conf_master:: syndic_master

``syndic_master``
-----------------

Default: ``None``

If this master will be running a salt-syndic to connect to a higher level
master, specify the higher level master with this configuration value

.. code-block:: yaml

    syndic_master: masterofmasters

.. conf_master:: syndic_master_port

``syndic_master_port``
-----------------------

Default: ``4506``

If this master will be running a salt-syndic to connect to a higher level
master, specify the higher level master port with this configuration value

.. code-block:: yaml

    syndic_master_port: 4506

.. conf_master:: syndic_log_file

.. conf_master:: syndic_master_log_file

``syndic_pidfile``
------------------

Default: ``salt-syndic.pid``

If this master will be running a salt-syndic to connect to a higher level
master, specify the pidfile of the syndic daemon.

.. code-block:: yaml

    syndic_pidfile: syndic.pid

``syndic_log_file``
-------------------

Default: ``syndic.log``

If this master will be running a salt-syndic to connect to a higher level
master, specify the log_file of the syndic daemon.

.. code-block:: yaml

    syndic_log_file: salt-syndic.log


Peer Publish Settings
=====================

Salt minions can send commands to other minions, but only if the minion is
allowed to. By default "Peer Publication" is disabled, and when enabled it
is enabled for specific minions and specific commands. This allows secure
compartmentalization of commands based on individual minions.

.. conf_master:: peer

``peer``
--------

Default: ``{}``

The configuration uses regular expressions to match minions and then a list
of regular expressions to match functions. The following will allow the
minion authenticated as foo.example.com to execute functions from the test
and pkg modules

.. code-block:: yaml

    peer:
      foo.example.com:
          - test.*
          - pkg.*

This will allow all minions to execute all commands:

.. code-block:: yaml

    peer:
      .*:
          - .*

This is not recommended, since it would allow anyone who gets root on any
single minion to instantly have root on all of the minions!

By adding an additional layer you can limit the target hosts in addition to the
accessible commands:

.. code-block:: yaml

    peer:
      foo.example.com:
        'db*':
          - test.*
          - pkg.*

.. conf_master:: peer_run

``peer_run``
------------

Default: ``{}``

The peer_run option is used to open up runners on the master to access from the
minions. The peer_run configuration matches the format of the peer
configuration.

The following example would allow foo.example.com to execute the manage.up
runner:


.. code-block:: yaml

    peer_run:
      foo.example.com:
          - manage.up


.. _master-logging-settings:

Master Logging Settings
=======================

.. conf_master:: log_file

``log_file``
------------

Default: ``/var/log/salt/master``

The master log can be sent to a regular file, local path name, or network
location. See also :conf_log:`log_file`.

Examples:

.. code-block:: yaml

    log_file: /var/log/salt/master

.. code-block:: yaml

    log_file: file:///dev/log

.. code-block:: yaml

    log_file: udp://loghost:10514



.. conf_master:: log_level

``log_level``
-------------

Default: ``warning``

The level of messages to send to the console. See also :conf_log:`log_level`.

.. code-block:: yaml

    log_level: warning




.. conf_master:: log_level_logfile

``log_level_logfile``
---------------------

Default: ``warning``

The level of messages to send to the log file. See also
:conf_log:`log_level_logfile`.

.. code-block:: yaml

    log_level_logfile: warning



.. conf_master:: log_datefmt

``log_datefmt``
---------------

Default: ``%H:%M:%S``

The date and time format used in console log messages. See also
:conf_log:`log_datefmt`.

.. code-block:: yaml

    log_datefmt: '%H:%M:%S'




.. conf_master:: log_datefmt_logfile

``log_datefmt_logfile``
-----------------------

Default: ``%Y-%m-%d %H:%M:%S``

The date and time format used in log file messages. See also
:conf_log:`log_datefmt_logfile`.

.. code-block:: yaml

    log_datefmt_logfile: '%Y-%m-%d %H:%M:%S'



.. conf_master:: log_fmt_console

``log_fmt_console``
-------------------

Default: ``[%(levelname)-8s] %(message)s``

The format of the console logging messages. See also
:conf_log:`log_fmt_console`.

.. code-block:: yaml

    log_fmt_console: '[%(levelname)-8s] %(message)s'



.. conf_master:: log_fmt_logfile

``log_fmt_logfile``
-------------------

Default: ``%(asctime)s,%(msecs)03.0f [%(name)-17s][%(levelname)-8s] %(message)s``

The format of the log file logging messages. See also
:conf_log:`log_fmt_logfile`.

.. code-block:: yaml

    log_fmt_logfile: '%(asctime)s,%(msecs)03.0f [%(name)-17s][%(levelname)-8s] %(message)s'



.. conf_master:: log_granular_levels

``log_granular_levels``
-----------------------

Default: ``{}``

This can be used to control logging levels more specifically. See also
:conf_log:`log_granular_levels`.


Node Groups
===========

.. conf_master:: nodegroups

Default: ``{}``

Node groups allow for logical groupings of minion nodes.
A group consists of a group name and a compound target.

.. code-block:: yaml

    nodegroups:
      group1: 'L@foo.domain.com,bar.domain.com,baz.domain.com or bl*.domain.com'
      group2: 'G@os:Debian and foo.domain.com'


Range Cluster Settings
======================

.. conf_master:: range_server

``range_server``
----------------

Default: ``''``

The range server (and optional port) that serves your cluster information
https://github.com/grierj/range/wiki/Introduction-to-Range-with-YAML-files

.. code-block:: yaml

  range_server: range:80


Include Configuration
=====================

.. conf_master:: default_include

``default_include``
-------------------

Default: ``master.d/*.conf``

The master can include configuration from other files. Per default the
master will automatically include all config files from ``master.d/*.conf``
where ``master.d`` is relative to the directory of the master configuration
file.


.. conf_master:: include

``include``
-----------

Default: ``not defined``

The master can include configuration from other files. To enable this,
pass a list of paths to this option. The paths can be either relative or
absolute; if relative, they are considered to be relative to the directory
the main minion configuration file lives in. Paths can make use of
shell-style globbing. If no files are matched by a path passed to this
option then the master will log a warning message.

.. code-block:: yaml

    # Include files from a master.d directory in the same
    # directory as the master config file
    include: master.d/*

    # Include a single extra file into the configuration
    include: /etc/roles/webserver

    # Include several files and the master.d directory
    include:
      - extra_config
      - master.d/*
      - /etc/roles/webserver


Windows Software Repo Settings
==============================

.. conf_master:: win_repo

``win_repo``
------------

Default: ``/srv/salt/win/repo``

Location of the repo on the master


.. code-block:: yaml

    win_repo: '/srv/salt/win/repo'

.. conf_master:: win_repo_mastercachefile

``win_repo_mastercachefile``
----------------------------

Default: ``/srv/salt/win/repo/winrepo.p``

.. code-block:: yaml

    win_repo_mastercachefile: '/srv/salt/win/repo/winrepo.p'

.. conf_master:: win_gitrepos

``win_gitrepos``
----------------

Default: ``''``

List of git repositories to include with the local repo

.. code-block:: yaml

    win_gitrepos:
      - 'https://github.com/saltstack/salt-winrepo.git'
