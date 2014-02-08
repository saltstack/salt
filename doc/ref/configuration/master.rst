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

.. conf_master:: cachedir

``cachedir``
------------

Default: :file:`/var/cache/salt`

The location used to store cache information, particularly the job information
for executed salt commands.

.. code-block:: yaml

    cachedir: /var/cache/salt

.. conf_master:: keep_jobs

``keep_jobs``
-------------

Default: ``24``

Set the number of hours to keep old job information

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

.. conf_master:: ext_job_cache

``ext_job_cache``
-----------------

Default: ''

Used to specify a default returner for all minions, when this option is set
the specified returner needs to be properly configured and the minions will
always default to sending returns to this returner. This will also disable the
local job cache on the master

.. code-block:: yaml

    ext_job_cache: redis

.. conf_master:: minion_data_cache

``minion_data_cache``
---------------------

Default: True

The minion data cache is a cache of information about the minions stored on the
master, this information is primarily the pillar and grains data. The data is
cached in the Master cachedir under the name of the minion and used to pre
determine what minions are expected to reply from executions.

.. code-block:: yaml

    minion_cache_dir: True

.. conf_master:: enforce_mine_cache

``enforce_mine_cache``
----------------------

Default: False

By-default when disabling the minion_data_cache mine will stop working since
it is based on cached data, by enabling this option we explicitly enabling
only the cache for the mine system.

.. code-block:: yaml

    enforce_mine_cache: False

.. conf_master:: sock_dir

``sock_dir``
------------

Default: :file:`/tmp/salt-unix`

Set the location to use for creating Unix sockets for master process
communication


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

.. conf_master:: state_verbose

``state_verbose``
-----------------

Default: ``False``

state_verbose allows for the data returned from the minion to be more
verbose. Normally only states that fail or states that have changes are
returned, but setting state_verbose to ``True`` will return all states that
were checked

.. code-block:: yaml

    state_verbose: True

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

.. conf_master:: state_top

``state_top``
-------------

Default: ``top.sls``

The state system uses a "top" file to tell the minions what environment to
use and what modules to use. The state_top file is defined relative to the
root of the base environment

.. code-block:: yaml

    state_top: top.sls

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
      - gitfs

.. conf_master:: file_roots

``file_roots``
--------------

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

.. conf_master:: gitfs_provider

``gitfs_provider``
------------------

.. versionadded:: Helium

Gitfs can be provided by one of two python modules: `GitPython`_ or `pygit2`_.
If using pygit2, both libgit2 and git itself must also be installed. More
information can be found in the :mod:`gitfs backend documentation
<salt.fileserver.gitfs>`.

.. _GitPython: https://github.com/gitpython-developers/GitPython
.. _pygit2: https://github.com/libgit2/pygit2

.. code-block:: yaml

    gitfs_provider: pygit2

.. conf_master:: gitfs_remotes

``gitfs_remotes``
-----------------

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

.. conf_master:: gitfs_ssl_verify

``gitfs_ssl_verify``
--------------------

Default: ``[]``

The ``gitfs_ssl_verify`` option specifies whether to ignore ssl certificate
errors when contacting the gitfs backend. You might want to set this to
false if you're using a git backend that uses a self-signed certificate but
keep in mind that setting this flag to anything other than the default of True
is a security concern, you may want to try using the ssh transport.

.. code-block:: yaml

    gitfs_ssl_verify: True

.. conf_master:: gitfs_root

``gitfs_root``
--------------

Default: ``''``

Serve files from a subdirectory within the repository, instead of the root.
This is useful when there are files in the repository that should not be
available to the Salt fileserver.

.. code-block:: yaml

    gitfs_root: somefolder/otherfolder

.. conf_master:: gitfs_base

``gitfs_base``
--------------

Default: ``master``

Defines which branch/tag should be used as the ``base`` environment.

.. code-block:: yaml

    gitfs_base: salt

.. conf_master:: hgfs_remotes

``hgfs_remotes``
----------------

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

.. conf_master:: hgfs_branch_method

``hgfs_branch_method``
----------------------

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

.. conf_master:: hgfs_root

``hgfs_root``
-------------

.. versionadded:: 0.17.0

Default: ``''``

Serve files from a subdirectory within the repository, instead of the root.
This is useful when there are files in the repository that should not be
available to the Salt fileserver.

.. code-block:: yaml

    hgfs_root: somefolder/otherfolder

.. conf_master:: hgfs_base

``hgfs_base``
-------------

.. versionadded:: 2014.1.0 (Hydrogen)

Default: ``default``

Defines which branch should be used as the ``base`` environment. Change this if
:conf_master:`hgfs_branch_method` is set to ``bookmarks`` to specify which
bookmark should be used as the ``base`` environment.

.. code-block:: yaml

    hgfs_base: salt


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

``syndic_log_file``
-------------------

Default: ``syndic.log``

If this master will be running a salt-syndic to connect to a higher level
master, specify the log_file of the syndic daemon.

.. code-block:: yaml

    syndic_log_file: salt-syndic.log

.. conf_master:: syndic_master_log_file

``syndic_pidfile``
------------------

Default: ``salt-syndic.pid``

If this master will be running a salt-syndic to connect to a higher level
master, specify the pidfile of the syndic daemon.

.. code-block:: yaml

    syndic_pidfile: syndic.pid

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

