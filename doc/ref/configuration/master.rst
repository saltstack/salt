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
:file:`/etc/salt/master` by default.  A notable exception is FreeBSD, where the
configuration file is located at :file:`/usr/local/etc/salt`.  The available
options are as follows:

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

The network port to set up the publication interface.

.. code-block:: yaml

    publish_port: 4505

.. conf_master:: master_id

``master_id``
----------------

Default: ``None``

The id to be passed in the publish job to minions. This is used for MultiSyndics
to return the job to the requesting master.

.. note::

    This must be the same string as the syndic is configured with.

.. code-block:: yaml

    master_id: MasterOfMaster

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

Default: ``100000``

Each minion connecting to the master uses AT LEAST one file descriptor, the
master subscription connection. If enough minions connect you might start
seeing on the console(and then salt-master crashes):

.. code-block:: bash

    Too many open files (tcp_listener.cpp:335)
    Aborted (core dumped)

.. code-block:: yaml

    max_open_files: 100000

By default this value will be the one of `ulimit -Hn`, i.e., the hard limit for
max open files.

To set a different value than the default one, uncomment, and configure this
setting. Remember that this value CANNOT be higher than the hard limit. Raising
the hard limit depends on the OS and/or distribution, a good way to find the
limit is to search the internet for something like this:

.. code-block:: text

    raise max open files hard limit debian

.. conf_master:: worker_threads

``worker_threads``
------------------

Default: ``5``

The number of threads to start for receiving commands and replies from minions.
If minions are stalling on replies because you have many minions, raise the
worker_threads value.

Worker threads should not be put below 3 when using the peer system, but can
drop down to 1 worker otherwise.

.. note::
    When the master daemon starts, it is expected behaviour to see
    multiple salt-master processes, even if 'worker_threads' is set to '1'. At
    a minimum, a controlling process will start along with a Publisher, an
    EventPublisher, and a number of MWorker processes will be started. The
    number of MWorker processes is tuneable by the 'worker_threads'
    configuration value while the others are not.

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

Specify the location of the master pidfile.

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

.. versionchanged:: 2016.3.0
    The default location for this directory has been moved. Prior to this
    version, the location was a directory named ``extmods`` in the Salt
    cachedir (on most platforms, ``/var/cache/salt/extmods``). It has been
    moved into the master cachedir (on most platforms,
    ``/var/cache/salt/master/extmods``).

Directory for custom modules. This directory can contain subdirectories for
each of Salt's module types such as ``runners``, ``output``, ``wheel``,
``modules``, ``states``, ``returners``, etc. This path is appended to
:conf_master:`root_dir`.

.. code-block:: yaml

    extension_modules: /root/salt_extmods

.. conf_minion:: module_dirs

``module_dirs``
---------------

Default: ``[]``

Like ``extension_modules``, but a list of extra directories to search
for Salt modules.

.. code-block:: yaml

    module_dirs:
      - /var/cache/salt/minion/extmods

.. conf_master:: cachedir

``cachedir``
------------

Default: :file:`/var/cache/salt`

The location used to store cache information, particularly the job information
for executed salt commands.

This directory may contain sensitive data and should be protected accordingly.

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

Set the number of hours to keep old job information.

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
to False.

.. code-block:: yaml

    color: False

.. conf_master:: sock_dir

``sock_dir``
------------

Default: :file:`/var/run/salt/master`

Set the location to use for creating Unix sockets for master process
communication.

.. code-block:: yaml

    sock_dir: /var/run/salt/master

.. conf_master:: enable_gpu_grains

``enable_gpu_grains``
---------------------

Default: ``True``

Enable GPU hardware data for your master. Be aware that the master can
take a while to start up when lspci and/or dmidecode is used to populate the
grains for the master.

.. conf_master:: job_cache

``job_cache``
-------------

Default: ``True``

The master maintains a job cache, while this is a great addition it can be
a burden on the master for larger deployments (over 5000 minions).
Disabling the job cache will make previously executed jobs unavailable to
the jobs system and is not generally recommended. Normally it is wise to make
sure the master has access to a faster IO system or a tmpfs is mounted to the
jobs dir.

.. conf_master:: minion_data_cache

``minion_data_cache``
---------------------

Default: ``True``

The minion data cache is a cache of information about the minions stored on the
master, this information is primarily the pillar and grains data. The data is
cached in the Master cachedir under the name of the minion and used to
predetermine what minions are expected to reply from executions.

.. code-block:: yaml

    minion_data_cache: True

.. conf_master:: ext_job_cache

``ext_job_cache``
-----------------

Default: ``''``

Used to specify a default returner for all minions, when this option is set
the specified returner needs to be properly configured and the minions will
always default to sending returns to this returner. This will also disable the
local job cache on the master.

.. code-block:: yaml

    ext_job_cache: redis

.. conf_master:: event_return

``event_return``
-----------------

.. versionadded:: 2015.5.0

Default: ``''``

Specify the returner to use to log events. A returner may have installation and
configuration requirements. Read the returner's documentation.

.. note::

   Not all returners support event returns. Verify that a returner has an
   ``event_return()`` function before configuring this option with a returner.

.. code-block:: yaml

    event_return: cassandra_cql

.. conf_master:: master_job_cache

``master_job_cache``
--------------------

.. versionadded:: 2014.7.0

Default: 'local_cache'

Specify the returner to use for the job cache. The job cache will only be
interacted with from the salt master and therefore does not need to be
accessible from the minions.

.. code-block:: yaml

    master_job_cache: redis

.. conf_master:: enforce_mine_cache

``enforce_mine_cache``
----------------------

Default: False

By-default when disabling the minion_data_cache mine will stop working since
it is based on cached data, by enabling this option we explicitly enabling
only the cache for the mine system.

.. code-block:: yaml

    enforce_mine_cache: False

.. conf_master:: max_minions

``max_minions``
---------------

Default: 0

The maximum number of minion connections allowed by the master. Use this to
accommodate the number of minions per master if you have different types of
hardware serving your minions. The default of ``0`` means unlimited connections.
Please note, that this can slow down the authentication process a bit in large
setups.

.. code-block:: yaml

    max_minions: 100

``con_cache``
-------------

Default: False

If max_minions is used in large installations, the master might experience
high-load situations because of having to check the number of connected
minions for every authentication. This cache provides the minion-ids of
all connected minions to all MWorker-processes and greatly improves the
performance of max_minions.

.. code-block:: yaml

    con_cache: True

.. conf_master:: presence_events

``presence_events``
-------------------

Default: False

Causes the master to periodically look for actively connected minions.
:ref:`Presence events <event-master_presence>` are fired on the event bus on a
regular interval with a list of connected minions, as well as events with lists
of newly connected or disconnected minions. This is a master-only operation
that does not send executions to minions. Note, this does not detect minions
that connect to a master via localhost.

.. code-block:: yaml

    presence_events: False

.. conf_master:: transport

``transport``
-------------

Default: ``zeromq``

Changes the underlying transport layer. ZeroMQ is the recommended transport
while additional transport layers are under development. Supported values are
``zeromq``, ``raet`` (experimental), and ``tcp`` (experimental). This setting has
a significant impact on performance and should not be changed unless you know
what you are doing! Transports are explained in :ref:`Salt Transports
<transports>`.

.. code-block:: yaml

    transport: zeromq

Salt-SSH Configuration
======================

.. conf_master:: roster_file

``roster_file``
---------------

Default: ``/etc/salt/roster``

Pass in an alternative location for the salt-ssh roster file.

.. code-block:: yaml

    roster_file: /root/roster

.. conf_master:: ssh_minion_opts

``ssh_minion_opts``
-------------------

Default: None

Pass in minion option overrides that will be inserted into the SHIM for
salt-ssh calls. The local minion config is not used for salt-ssh. Can be
overridden on a per-minion basis in the roster (``minion_opts``)

.. code-block:: yaml

    minion_opts:
      gpg_keydir: /root/gpg


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

.. conf_master:: autosign_timeout

``autosign_timeout``
--------------------

.. versionadded:: 2014.7.0

Default: ``120``

Time in minutes that a incoming public key with a matching name found in
pki_dir/minion_autosign/keyid is automatically accepted. Expired autosign keys
are removed when the master checks the minion_autosign directory. This method
to auto accept minions can be safer than an autosign_file because the
keyid record can expire and is limited to being an exact name match.
This should still be considered a less than secure option, due to the fact
that trust is based on just the requesting minion id.

.. conf_master:: autosign_file

``autosign_file``
-----------------

Default: ``not defined``

If the ``autosign_file`` is specified incoming keys specified in the autosign_file
will be automatically accepted. Matches will be searched for first by string
comparison, then by globbing, then by full-string regex matching.
This should still be considered a less than secure option, due to the fact
that trust is based on just the requesting minion id.

.. conf_master:: autoreject_file

``autoreject_file``
-------------------

.. versionadded:: 2014.1.0

Default: ``not defined``

Works like :conf_master:`autosign_file`, but instead allows you to specify
minion IDs for which keys will automatically be rejected. Will override both
membership in the :conf_master:`autosign_file` and the
:conf_master:`auto_accept` setting.

.. conf_master:: publisher_acl

``publisher_acl``
-----------------

Default: ``{}``

Enable user accounts on the master to execute specific modules. These modules
can be expressed as regular expressions. Note that client_acl option is
deprecated by publisher_acl option and will be removed in future releases.

.. code-block:: yaml

    publisher_acl:
      fred:
        - test.ping
        - pkg.*

.. conf_master:: publisher_acl_blacklist

``publisher_acl_blacklist``
---------------------------

Default: ``{}``

Blacklist users or modules

This example would blacklist all non sudo users, including root from
running any commands. It would also blacklist any use of the "cmd"
module. Note that client_acl_blacklist option is deprecated by
publisher_acl_blacklist option and will be removed in future releases.

This is completely disabled by default.

.. code-block:: yaml

    publisher_acl_blacklist:
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

Time (in seconds) for a newly generated token to live.

Default: 12 hours

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

.. conf_master:: master_sign_pubkey

``master_sign_pubkey``
----------------------

Default: ``False``

Sign the master auth-replies with a cryptographic signature of the masters
public key. Please see the tutorial how to use these settings in the
`Multimaster-PKI with Failover Tutorial <http://docs.saltstack.com/en/latest/topics/tutorials/multimaster_pki.html>`_

.. code-block:: yaml

    master_sign_pubkey: True

.. conf_master:: master_sign_key_name

``master_sign_key_name``
------------------------

Default: ``master_sign``

The customizable name of the signing-key-pair without suffix.

.. code-block:: yaml

    master_sign_key_name: <filename_without_suffix>

.. conf_master:: master_pubkey_signature

``master_pubkey_signature``
---------------------------

Default: ``master_pubkey_signature``

The name of the file in the masters pki-directory that holds the pre-calculated
signature of the masters public-key.

.. code-block:: yaml

    master_pubkey_signature: <filename>

.. conf_master:: master_use_pubkey_signature

``master_use_pubkey_signature``
-------------------------------

Default: ``False``

Instead of computing the signature for each auth-reply, use a pre-calculated
signature. The :conf_master:`master_pubkey_signature` must also be set for this.

.. code-block:: yaml

    master_use_pubkey_signature: True


.. conf_master:: rotate_aes_key

``rotate_aes_key``
------------------

Default: ``True``

Rotate the salt-masters AES-key when a minion-public is deleted with salt-key.
This is a very important security-setting. Disabling it will enable deleted
minions to still listen in on the messages published by the salt-master.
Do not disable this unless it is absolutely clear what this does.

.. code-block:: yaml

    rotate_aes_key: True


Master Module Management
========================

.. conf_master:: runner_dirs

``runner_dirs``
---------------

Default: ``[]``

Set additional directories to search for runner modules.

.. conf_master:: cython_enable

``cython_enable``
-----------------

Default: ``False``

Set to true to enable Cython modules (.pyx files) to be compiled on the fly on
the Salt master.

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
root of the base environment.

.. code-block:: yaml

    state_top: top.sls

.. conf_master:: master_tops

``master_tops``
---------------

Default: ``{}``

The master_tops option replaces the external_nodes option by creating
a pluggable system for the generation of external top data. The external_nodes
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

The renderer to use on the minions to render the state data.

.. code-block:: yaml

    renderer: yaml_jinja

.. conf_master:: failhard

``failhard``
------------

Default: ``False``

Set the global failhard flag, this informs all states to stop running states
at the moment a single state fails.

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

.. conf_master:: state_aggregate

``state_aggregate``
-------------------

Default: ``False``

Automatically aggregate all states that have support for mod_aggregate by
setting to ``True``. Or pass a list of state module names to automatically
aggregate just those types.

.. code-block:: yaml

    state_aggregate:
      - pkg

.. code-block:: yaml

    state_aggregate: True

.. conf_master:: state_events

``state_events``
----------------

Default: ``False``

Send progress events as each function in a state run completes execution
by setting to ``True``. Progress events are in the format
``salt/job/<JID>/prog/<MID>/<RUN NUM>``.

.. code-block:: yaml

    state_events: True

.. conf_master:: yaml_utf8

``yaml_utf8``
-------------

Default: ``False``

Enable extra routines for YAML renderer used states containing UTF characters.

.. code-block:: yaml

    yaml_utf8: False

.. conf_master:: test

``test``
--------

Default: ``False``

Set all state calls to only test if they are going to actually make changes
or just post what changes are going to be made.

.. code-block:: yaml

    test: False

Master File Server Settings
===========================

.. conf_master:: fileserver_backend

``fileserver_backend``
----------------------

Default: ``['roots']``

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
the master server. The default is md5, but sha1, sha224, sha256, sha384, and
sha512 are also supported.

.. code-block:: yaml

    hash_type: md5

.. conf_master:: file_buffer_size

``file_buffer_size``
--------------------

Default: ``1048576``

The buffer size in the file server in bytes.

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

.. note::
    Vim's .swp files are a common cause of Unicode errors in
    :py:func:`file.recurse <salt.states.file.recurse>` states which use
    templating. Unless there is a good reason to distribute them via the
    fileserver, it is good practice to include ``'\*.swp'`` in the
    :conf_master:`file_ignore_glob`.


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

    ``file://`` repos will be treated as a remote and copied into the master's
    gitfs cache, so only the *local* refs for those repos will be exposed as
    fileserver environments.

As of 2014.7.0, it is possible to have per-repo versions of several of the
gitfs configuration parameters. For more information, see the :ref:`GitFS
Walkthrough <gitfs-per-remote-config>`.

.. conf_master:: gitfs_provider

``gitfs_provider``
******************

.. versionadded:: 2014.7.0

Optional parameter used to specify the provider to be used for gitfs. More
information can be found in the :ref:`GitFS Walkthrough <gitfs-dependencies>`.

Must be one of the following: ``pygit2``, ``gitpython``, or ``dulwich``. If
unset, then each will be tried in that same order, and the first one with a
compatible version installed will be the provider that is used.

.. code-block:: yaml

    gitfs_provider: dulwich

.. conf_master:: gitfs_ssl_verify

``gitfs_ssl_verify``
********************

Default: ``True``

Specifies whether or not to ignore SSL certificate errors when contacting the
remote repository. You might want to set this to ``False`` if you're using a
git repo that uses a self-signed certificate. However, keep in mind that
setting this to anything other ``True`` is a considered insecure, and using an
SSH-based transport (if available) may be a better option.

.. code-block:: yaml

    gitfs_ssl_verify: True

.. conf_master:: gitfs_mountpoint

``gitfs_mountpoint``
********************

.. versionadded:: 2014.7.0

Default: ``''``

Specifies a path on the salt fileserver which will be prepended to all files
served by gitfs. This option can be used in conjunction with
:conf_master:`gitfs_root`. It can also be configured on a per-remote basis, see
:ref:`here <gitfs-per-remote-config>` for more info.

.. code-block:: yaml

    gitfs_mountpoint: salt://foo/bar

.. note::

    The ``salt://`` protocol designation can be left off (in other words,
    ``foo/bar`` and ``salt://foo/bar`` are equivalent). Assuming a file
    ``baz.sh`` in the root of a gitfs remote, and the above example mountpoint,
    this file would be served up via ``salt://foo/bar/baz.sh``.

.. conf_master:: gitfs_root

``gitfs_root``
**************

Default: ``''``

Relative path to a subdirectory within the repository from which Salt should
begin to serve files. This is useful when there are files in the repository
that should not be available to the Salt fileserver. Can be used in conjunction
with :conf_master:`gitfs_mountpoint`. If used, then from Salt's perspective the
directories above the one specified will be ignored and the relative path will
(for the purposes of gitfs) be considered as the root of the repo.

.. code-block:: yaml

    gitfs_root: somefolder/otherfolder

.. versionchanged:: 2014.7.0

   Ability to specify gitfs roots on a per-remote basis was added. See
   :ref:`here <gitfs-per-remote-config>` for more info.

.. conf_master:: gitfs_base

``gitfs_base``
**************

Default: ``master``

Defines which branch/tag should be used as the ``base`` environment.

.. code-block:: yaml

    gitfs_base: salt

.. versionchanged:: 2014.7.0
    Ability to specify the base on a per-remote basis was added. See :ref:`here
    <gitfs-per-remote-config>` for more info.

.. conf_master:: gitfs_env_whitelist

``gitfs_env_whitelist``
***********************

.. versionadded:: 2014.7.0

Default: ``[]``

Used to restrict which environments are made available. Can speed up state runs
if the repos in :conf_master:`gitfs_remotes` contain many branches/tags.  More
information can be found in the :ref:`GitFS Walkthrough
<gitfs-whitelist-blacklist>`.

.. code-block:: yaml

    gitfs_env_whitelist:
      - base
      - v1.*
      - 'mybranch\d+'

.. conf_master:: gitfs_env_blacklist

``gitfs_env_blacklist``
***********************

.. versionadded:: 2014.7.0

Default: ``[]``

Used to restrict which environments are made available. Can speed up state runs
if the repos in :conf_master:`gitfs_remotes` contain many branches/tags. More
information can be found in the :ref:`GitFS Walkthrough
<gitfs-whitelist-blacklist>`.

.. code-block:: yaml

    gitfs_env_blacklist:
      - base
      - v1.*
      - 'mybranch\d+'


GitFS Authentication Options
****************************

These parameters only currently apply to the pygit2 gitfs provider. Examples of
how to use these can be found in the :ref:`GitFS Walkthrough
<gitfs-authentication>`.

.. conf_master:: gitfs_user

``gitfs_user``
~~~~~~~~~~~~~~

.. versionadded:: 2014.7.0

Default: ``''``

Along with :conf_master:`gitfs_password`, is used to authenticate to HTTPS
remotes.

.. code-block:: yaml

    gitfs_user: git

.. conf_master:: gitfs_password

``gitfs_password``
~~~~~~~~~~~~~~~~~~

.. versionadded:: 2014.7.0

Default: ``''``

Along with :conf_master:`gitfs_user`, is used to authenticate to HTTPS remotes.
This parameter is not required if the repository does not use authentication.

.. code-block:: yaml

    gitfs_password: mypassword

.. conf_master:: gitfs_insecure_auth

``gitfs_insecure_auth``
~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2014.7.0

Default: ``False``

By default, Salt will not authenticate to an HTTP (non-HTTPS) remote. This
parameter enables authentication over HTTP. **Enable this at your own risk.**

.. code-block:: yaml

    gitfs_insecure_auth: True

.. conf_master:: gitfs_pubkey

``gitfs_pubkey``
~~~~~~~~~~~~~~~~

.. versionadded:: 2014.7.0

Default: ``''``

Along with :conf_master:`gitfs_privkey` (and optionally
:conf_master:`gitfs_passphrase`), is used to authenticate to SSH remotes. This
parameter (or its :ref:`per-remote counterpart <gitfs-per-remote-config>`) is
required for SSH remotes.

.. code-block:: yaml

    gitfs_pubkey: /path/to/key.pub

.. conf_master:: gitfs_privkey

``gitfs_privkey``
~~~~~~~~~~~~~~~~~

.. versionadded:: 2014.7.0

Default: ``''``

Along with :conf_master:`gitfs_pubkey` (and optionally
:conf_master:`gitfs_passphrase`), is used to authenticate to SSH remotes. This
parameter (or its :ref:`per-remote counterpart <gitfs-per-remote-config>`) is
required for SSH remotes.

.. code-block:: yaml

    gitfs_privkey: /path/to/key

.. conf_master:: gitfs_passphrase

``gitfs_passphrase``
~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2014.7.0

Default: ``''``

This parameter is optional, required only when the SSH key being used to
authenticate is protected by a passphrase.

.. code-block:: yaml

    gitfs_passphrase: mypassphrase


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

    As of 2014.7.0, it is possible to have per-repo versions of the
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

    Starting in version 2014.1.0, the value of the :conf_master:`hgfs_base`
    parameter defines which branch is used as the ``base`` environment,
    allowing for a ``base`` environment to be used with an
    :conf_master:`hgfs_branch_method` of ``bookmarks``.

    Prior to this release, the ``default`` branch will be used as the ``base``
    environment.

.. conf_master:: hgfs_mountpoint

``hgfs_mountpoint``
*******************

.. versionadded:: 2014.7.0

Default: ``''``

Specifies a path on the salt fileserver which will be prepended to all files
served by hgfs. This option can be used in conjunction with
:conf_master:`hgfs_root`. It can also be configured on a per-remote basis, see
:conf_master:`here <hgfs_remotes>` for more info.

.. code-block:: yaml

    hgfs_mountpoint: salt://foo/bar

.. note::

    The ``salt://`` protocol designation can be left off (in other words,
    ``foo/bar`` and ``salt://foo/bar`` are equivalent). Assuming a file
    ``baz.sh`` in the root of an hgfs remote, this file would be served up via
    ``salt://foo/bar/baz.sh``.

.. conf_master:: hgfs_root

``hgfs_root``
*************

.. versionadded:: 0.17.0

Default: ``''``

Relative path to a subdirectory within the repository from which Salt should
begin to serve files. This is useful when there are files in the repository
that should not be available to the Salt fileserver. Can be used in conjunction
with :conf_master:`hgfs_mountpoint`. If used, then from Salt's perspective the
directories above the one specified will be ignored and the relative path will
(for the purposes of hgfs) be considered as the root of the repo.

.. code-block:: yaml

    hgfs_root: somefolder/otherfolder

.. versionchanged:: 2014.7.0

   Ability to specify hgfs roots on a per-remote basis was added. See
   :conf_master:`here <hgfs_remotes>` for more info.

.. conf_master:: hgfs_base

``hgfs_base``
*************

.. versionadded:: 2014.1.0

Default: ``default``

Defines which branch should be used as the ``base`` environment. Change this if
:conf_master:`hgfs_branch_method` is set to ``bookmarks`` to specify which
bookmark should be used as the ``base`` environment.

.. code-block:: yaml

    hgfs_base: salt

.. conf_master:: hgfs_env_whitelist

``hgfs_env_whitelist``
**********************

.. versionadded:: 2014.7.0

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

.. versionadded:: 2014.7.0

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

    As of 2014.7.0, it is possible to have per-repo versions of the following
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

.. versionadded:: 2014.7.0

Default: ``''``

Specifies a path on the salt fileserver which will be prepended to all files
served by hgfs. This option can be used in conjunction with
:conf_master:`svnfs_root`. It can also be configured on a per-remote basis, see
:conf_master:`here <svnfs_remotes>` for more info.

.. code-block:: yaml

    svnfs_mountpoint: salt://foo/bar

.. note::

    The ``salt://`` protocol designation can be left off (in other words,
    ``foo/bar`` and ``salt://foo/bar`` are equivalent). Assuming a file
    ``baz.sh`` in the root of an svnfs remote, this file would be served up via
    ``salt://foo/bar/baz.sh``.

.. conf_master:: svnfs_root

``svnfs_root``
**************

.. versionadded:: 0.17.0

Default: ``''``

Relative path to a subdirectory within the repository from which Salt should
begin to serve files. This is useful when there are files in the repository
that should not be available to the Salt fileserver. Can be used in conjunction
with :conf_master:`svnfs_mountpoint`. If used, then from Salt's perspective the
directories above the one specified will be ignored and the relative path will
(for the purposes of svnfs) be considered as the root of the repo.

.. code-block:: yaml

    svnfs_root: somefolder/otherfolder

.. versionchanged:: 2014.7.0

   Ability to specify svnfs roots on a per-remote basis was added. See
   :conf_master:`here <svnfs_remotes>` for more info.

.. conf_master:: svnfs_trunk

``svnfs_trunk``
***************

.. versionadded:: 2014.7.0

Default: ``trunk``

Path relative to the root of the repository where the trunk is located. Can
also be configured on a per-remote basis, see :conf_master:`here
<svnfs_remotes>` for more info.

.. code-block:: yaml

    svnfs_trunk: trunk

.. conf_master:: svnfs_branches

``svnfs_branches``
******************

.. versionadded:: 2014.7.0

Default: ``branches``

Path relative to the root of the repository where the branches are located. Can
also be configured on a per-remote basis, see :conf_master:`here
<svnfs_remotes>` for more info.

.. code-block:: yaml

    svnfs_branches: branches

.. conf_master:: svnfs_tags

``svnfs_tags``
**************

.. versionadded:: 2014.7.0

Default: ``tags``

Path relative to the root of the repository where the tags are located. Can
also be configured on a per-remote basis, see :conf_master:`here
<svnfs_remotes>` for more info.

.. code-block:: yaml

    svnfs_tags: tags

.. conf_master:: svnfs_env_whitelist

``svnfs_env_whitelist``
***********************

.. versionadded:: 2014.7.0

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

.. versionadded:: 2014.7.0

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

.. versionadded:: 2014.7.0

Default: ``base``

Environment from which MinionFS files are made available.

.. code-block:: yaml

    minionfs_env: minionfs

.. conf_master:: minionfs_mountpoint

``minionfs_mountpoint``
***********************

.. versionadded:: 2014.7.0

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

.. versionadded:: 2014.7.0

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

.. versionadded:: 2014.7.0

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

.. _master-configuration-ext-pillar:

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

.. conf_master:: pillar_roots_override_ext_pillar

``pillar_roots_override_ext_pillar``
--------------------

.. versionadded:: Boron

Default: ``False``

This option allows for external pillar sources to be evaluated before
:conf_master:`pillar_roots`, which means that values obtained from
:conf_master:`pillar_roots` take precedence over those found from
:conf_master:`ext_pillar` sources.

.. code-block:: yaml

    pillar_roots_override_ext_pillar: False

.. conf_master:: ext_pillar_first

``ext_pillar_first``
--------------------

.. versionadded:: 2015.5.0

Default: ``False``

This option allows for external pillar sources to be evaluated before
:conf_master:`pillar_roots`. This allows for targeting file system pillar from
ext_pillar. Note that ext_pillar_first option is deprecated by
pillar_roots_override_ext_pillar option and will be removed in future releases.

.. code-block:: yaml

    ext_pillar_first: False

.. _git_pillar-config-opts:

Git External Pillar (git_pillar) Configuration Options
------------------------------------------------------

.. conf_master:: git_pillar_provider

``git_pillar_provider``
***********************

.. versionadded:: 2015.8.0

Specify the provider to be used for git_pillar. Must be either ``pygit2`` or
``gitpython``. If unset, then both will be tried in that same order, and the
first one with a compatible version installed will be the provider that is
used.

.. code-block:: yaml

    git_pillar_provider: gitpython

.. conf_master:: git_pillar_base

``git_pillar_base``
*******************

.. versionadded:: 2015.8.0

Default: ``master``

If the desired branch matches this value, and the environment is omitted from
the git_pillar configuration, then the environment for that git_pillar remote
will be ``base``. For example, in the configuration below, the ``foo``
branch/tag would be assigned to the ``base`` environment, while ``bar`` would
be mapped to the ``bar`` environment.

.. code-block:: yaml

    git_pillar_base: foo

    ext_pillar:
      - git:
        - foo https://mygitserver/git-pillar.git
        - bar https://mygitserver/git-pillar.git

.. conf_master:: git_pillar_branch

``git_pillar_branch``
*********************

.. versionadded:: 2015.8.0

Default: ``master``

If the branch is omitted from a git_pillar remote, then this branch will be
used instead. For example, in the configuration below, the first two remotes
would use the ``pillardata`` branch/tag, while the third would use the ``foo``
branch/tag.

.. code-block:: yaml

    git_pillar_branch: pillardata

    ext_pillar:
      - git:
        - https://mygitserver/pillar1.git
        - https://mygitserver/pillar2.git:
          - root: pillar
        - foo https://mygitserver/pillar3.git

.. conf_master:: git_pillar_env

``git_pillar_env``
******************

.. versionadded:: 2015.8.0

Default: ``''`` (unset)

Environment to use for git_pillar remotes. This is normally derived from the
branch/tag (or from a per-remote ``env`` parameter), but if set this will
override the process of deriving the env from the branch/tag name. For example,
in the configuration below the ``foo`` branch would be assigned to the ``base``
environment, while the ``bar`` branch would need to explicitly have ``bar``
configured as it's environment to keep it from also being mapped to the
``base`` environment.

.. code-block:: yaml

    git_pillar_env: base

    ext_pillar:
      - git:
        - foo https://mygitserver/git-pillar.git
        - bar https://mygitserver/git-pillar.git:
          - env: bar

For this reason, this option is recommended to be left unset, unless the use
case calls for all (or almost all) of the git_pillar remotes to use the same
environment irrespective of the branch/tag being used.

.. conf_master:: git_pillar_root

``git_pillar_root``
*******************

.. versionadded:: 2015.8.0

Default: ``''``

Path relative to the root of the repository where the git_pillar top file and
SLS files are located. In the below configuration, the pillar top file and SLS
files would be looked for in a subdirectory called ``pillar``.

.. code-block:: yaml

    git_pillar_root: pillar

    ext_pillar:
      - git:
        - master https://mygitserver/pillar1.git
        - master https://mygitserver/pillar2.git

.. note::

    This is a global option. If only one or two repos need to have their files
    sourced from a subdirectory, then :conf_master:`git_pillar_root` can be
    omitted and the root can be specified on a per-remote basis, like so:

    .. code-block:: yaml

        ext_pillar:
          - git:
            - master https://mygitserver/pillar1.git
            - master https://mygitserver/pillar2.git:
              - root: pillar

    In this example, for the first remote the top file and SLS files would be
    looked for in the root of the repository, while in the second remote the
    pillar data would be retrieved from the ``pillar`` subdirectory.

.. conf_master:: git_pillar_ssl_verify

``git_pillar_ssl_verify``
*************************

.. versionadded:: 2015.8.0

Default: ``True``

Specifies whether or not to ignore SSL certificate errors when contacting the
remote repository. You might want to set this to ``False`` if you're using a
git repo that uses a self-signed certificate. However, keep in mind that
setting this to anything other ``True`` is a considered insecure, and using an
SSH-based transport (if available) may be a better option.

.. code-block:: yaml

    git_pillar_ssl_verify: True

Git External Pillar Authentication Options
******************************************

These parameters only currently apply to the ``pygit2``
:conf_master:`git_pillar_provider`.  Authentication works the same as it does
in gitfs, as outlined in the :ref:`GitFS Walkthrough <gitfs-authentication>`,
though the global configuration options are named differently to reflect that
they are for git_pillar instead of gitfs.

.. conf_master:: git_pillar_user

``git_pillar_user``
~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2015.8.0

Default: ``''``

Along with :conf_master:`git_pillar_password`, is used to authenticate to HTTPS
remotes.

.. code-block:: yaml

    git_pillar_user: git

.. conf_master:: git_pillar_password

``git_pillar_password``
~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2015.8.0

Default: ``''``

Along with :conf_master:`git_pillar_user`, is used to authenticate to HTTPS
remotes. This parameter is not required if the repository does not use
authentication.

.. code-block:: yaml

    git_pillar_password: mypassword

.. conf_master:: git_pillar_insecure_auth

``git_pillar_insecure_auth``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2015.8.0

Default: ``False``

By default, Salt will not authenticate to an HTTP (non-HTTPS) remote. This
parameter enables authentication over HTTP. **Enable this at your own risk.**

.. code-block:: yaml

    git_pillar_insecure_auth: True

.. conf_master:: git_pillar_pubkey

``git_pillar_pubkey``
~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2015.8.0

Default: ``''``

Along with :conf_master:`git_pillar_privkey` (and optionally
:conf_master:`git_pillar_passphrase`), is used to authenticate to SSH remotes.

.. code-block:: yaml

    git_pillar_pubkey: /path/to/key.pub

.. conf_master:: git_pillar_privkey

``git_pillar_privkey``
~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2015.8.0

Default: ``''``

Along with :conf_master:`git_pillar_pubkey` (and optionally
:conf_master:`git_pillar_passphrase`), is used to authenticate to SSH remotes.

.. code-block:: yaml

    git_pillar_privkey: /path/to/key

.. conf_master:: git_pillar_passphrase

``git_pillar_passphrase``
~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2015.8.0

Default: ``''``

This parameter is optional, required only when the SSH key being used to
authenticate is protected by a passphrase.

.. code-block:: yaml

    git_pillar_passphrase: mypassphrase

.. conf_master:: pillar_source_merging_strategy

``pillar_source_merging_strategy``
----------------------------------

.. versionadded:: 2014.7.0

Default: ``smart``

The pillar_source_merging_strategy option allows you to configure merging
strategy between different sources. It accepts 4 values:

* recurse:

  it will merge recursively mapping of data. For example, theses 2 sources:

  .. code-block:: yaml

      foo: 42
      bar:
          element1: True

  .. code-block:: yaml

      bar:
          element2: True
      baz: quux

  will be merged as:

  .. code-block:: yaml

      foo: 42
      bar:
          element1: True
          element2: True
      baz: quux

* aggregate:

  instructs aggregation of elements between sources that use the #!yamlex renderer.

  For example, these two documents:

  .. code-block:: yaml

      #!yamlex
      foo: 42
      bar: !aggregate {
        element1: True
      }
      baz: !aggregate quux

  .. code-block:: yaml

      #!yamlex
      bar: !aggregate {
        element2: True
      }
      baz: !aggregate quux2

  will be merged as:

  .. code-block:: yaml

      foo: 42
      bar:
        element1: True
        element2: True
      baz:
        - quux
        - quux2

* overwrite:

  Will use the behaviour of the 2014.1 branch and earlier.

  Overwrites elements according the order in which they are processed.

  First pillar processed:

  .. code-block:: yaml

      A:
        first_key: blah
        second_key: blah

  Second pillar processed:

  .. code-block:: yaml

      A:
        third_key: blah
        fourth_key: blah

  will be merged as:

  .. code-block:: yaml

      A:
        third_key: blah
        fourth_key: blah

* smart (default):

  Guesses the best strategy based on the "renderer" setting.

.. conf_master:: pillar_merge_lists

``pillar_merge_lists``
----------------------

.. versionadded:: 2015.8.0

Default: ``False``

Recursively merge lists by aggregating them instead of replacing them.

.. code-block:: yaml

    pillar_merge_lists: False


Syndic Server Settings
======================

A Salt syndic is a Salt master used to pass commands from a higher Salt master to
minions below the syndic. Using the syndic is simple. If this is a master that
will have syndic servers(s) below it, set the "order_masters" setting to True.

If this is a master that will be running a syndic daemon for passthrough the
"syndic_master" setting needs to be set to the location of the master server.

Do not not forget that, in other words, it means that it shares with the local minion
its ID and PKI_DIR.

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
master, specify the higher level master with this configuration value.

.. code-block:: yaml

    syndic_master: masterofmasters

You can optionally connect a syndic to multiple higher level masters by
setting the 'syndic_master' value to a list:

.. code-block:: yaml

    syndic_master:
      - masterofmasters1
      - masterofmasters2

Each higher level master must be set up in a multimaster configuration.

.. conf_master:: syndic_master_port

``syndic_master_port``
----------------------

Default: ``4506``

If this master will be running a salt-syndic to connect to a higher level
master, specify the higher level master port with this configuration value.

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
and pkg modules.

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
:conf_log:`log_level_logfile`. When it is not set explicitly
it will inherit the level set by :conf_log:`log_level` option.

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

.. note::
    Log colors are enabled in ``log_fmt_console`` rather than the
    :conf_master:`color` config since the logging system is loaded before the
    master config.

    Console log colors are specified by these additional formatters:

    %(colorlevel)s
    %(colorname)s
    %(colorprocess)s
    %(colormsg)s

    Since it is desirable to include the surrounding brackets, '[' and ']', in
    the coloring of the messages, these color formatters also include padding
    as well.  Color LogRecord attributes are only available for console
    logging.

.. code-block:: yaml

    log_fmt_console: '%(colorlevel)s %(colormsg)s'
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
      group3: 'G@os:Debian and N@group1'
      group4:
	- 'G@foo:bar'
	- 'or'
	- 'G@foo:baz'

More information on using nodegroups can be found :ref:`here <targeting-nodegroups>`.


Range Cluster Settings
======================

.. conf_master:: range_server

``range_server``
----------------

Default: ``''``

The range server (and optional port) that serves your cluster information
https://github.com/ytoolshed/range/wiki/%22yamlfile%22-module-file-spec

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

.. _winrepo-master-config-opts:

Windows Software Repo Settings
==============================

.. conf_master:: winrepo_provider

``winrepo_provider``
--------------------

.. versionadded:: 2015.8.0

Specify the provider to be used for winrepo. Must be either ``pygit2`` or
``gitpython``. If unset, then both will be tried in that same order, and the
first one with a compatible version installed will be the provider that is
used.

.. code-block:: yaml

    winrepo_provider: gitpython

.. conf_master:: winrepo_dir
.. conf_master:: win_repo

``winrepo_dir``
---------------

.. versionchanged:: 2015.8.0
    Renamed from ``win_repo`` to ``winrepo_dir``.

Default: ``/srv/salt/win/repo``

Location on the master where the :conf_master:`winrepo_remotes` are checked out
for pre-2015.8.0 minions. 2015.8.0 and later minions use
:conf_master:`winrepo_remotes_ng <winrepo_remotes_ng>` instead.

.. code-block:: yaml

    winrepo_dir: /srv/salt/win/repo

.. conf_master:: winrepo_dir_ng

``winrepo_dir_ng``
------------------

.. versionadded:: 2015.8.0
    A new :ref:`ng <windows-package-manager>` repo was added.

Default: ``/srv/salt/win/repo-ng``

Location on the master where the :conf_master:`winrepo_remotes_ng` are checked
out for 2015.8.0 and later minions.

.. code-block:: yaml

    winrepo_dir: /srv/salt/win/repo-ng

.. conf_master:: winrepo_cachefile
.. conf_master:: win_repo_mastercachefile

``winrepo_cachefile``
---------------------

.. versionchanged:: 2015.8.0
    Renamed from ``win_repo_mastercachefile`` to ``winrepo_cachefile``

.. note::
    2015.8.0 and later minions do not use this setting since the cachefile
    is now located on the minion.

Default: ``winrepo.p``

Path relative to :conf_master:`winrepo_dir` where the winrepo cache should be
created.

.. code-block:: yaml

    winrepo_cachefile: winrepo.p

.. conf_master:: winrepo_remotes
.. conf_master:: win_gitrepos

``winrepo_remotes``
-------------------

.. versionchanged:: 2015.8.0
    Renamed from ``win_gitrepos`` to ``winrepo_remotes``.

Default: ``['https://github.com/saltstack/salt-winrepo.git']``

List of git repositories to checkout and include in the winrepo for
pre-2015.8.0 minions. 2015.8.0 and later minions use
:conf_master:`winrepo_remotes_ng <winrepo_remotes_ng>` instead.

.. code-block:: yaml

    winrepo_remotes:
      - https://github.com/saltstack/salt-winrepo.git

To specify a specific revision of the repository, prepend a commit ID to the
URL of the repository:

.. code-block:: yaml

    winrepo_remotes:
      - '<commit_id> https://github.com/saltstack/salt-winrepo.git'

Replace ``<commit_id>`` with the SHA1 hash of a commit ID. Specifying a commit
ID is useful in that it allows one to revert back to a previous version in the
event that an error is introduced in the latest revision of the repo.

.. conf_master:: winrepo_remotes_ng

``winrepo_remotes_ng``
----------------------

.. versionadded:: 2015.8.0
    A new :ref:`ng <windows-package-manager>` repo was added.

Default: ``['https://github.com/saltstack/salt-winrepo-ng.git']``

List of git repositories to checkout and include in the winrepo for
2015.8.0 and later minions.

.. code-block:: yaml

    winrepo_remotes_ng:
      - https://github.com/saltstack/salt-winrepo-ng.git

To specify a specific revision of the repository, prepend a commit ID to the
URL of the repository:

.. code-block:: yaml

    winrepo_remotes:
      - '<commit_id> https://github.com/saltstack/salt-winrepo-ng.git'

Replace ``<commit_id>`` with the SHA1 hash of a commit ID. Specifying a commit
ID is useful in that it allows one to revert back to a previous version in the
event that an error is introduced in the latest revision of the repo.

.. conf_master:: winrepo_branch

``winrepo_branch``
------------------

.. versionadded:: 2015.8.0

Default: ``master``

If the branch is omitted from a winrepo remote, then this branch will be
used instead. For example, in the configuration below, the first two remotes
would use the ``winrepo`` branch/tag, while the third would use the ``foo``
branch/tag.

.. code-block:: yaml

    winrepo_branch: winrepo

    ext_pillar:
      - git:
        - https://mygitserver/winrepo1.git
        - https://mygitserver/winrepo2.git:
        - foo https://mygitserver/winrepo3.git

.. conf_master:: winrepo_ssl_verify

``winrepo_ssl_verify``
----------------------

.. versionadded:: 2015.8.0

Default: ``True``

Specifies whether or not to ignore SSL certificate errors when contacting the
remote repository. You might want to set this to ``False`` if you're using a
git repo that uses a self-signed certificate. However, keep in mind that
setting this to anything other ``True`` is a considered insecure, and using an
SSH-based transport (if available) may be a better option.

.. code-block:: yaml

    winrepo_ssl_verify: True

Winrepo Authentication Options
------------------------------

These parameters only currently apply to the ``pygit2``
:conf_master:`winrepo_provider`. Authentication works the same as it does in
gitfs, as outlined in the :ref:`GitFS Walkthrough <gitfs-authentication>`,
though the global configuration options are named differently to reflect that
they are for winrepo instead of gitfs.

.. conf_master:: winrepo_user

``winrepo_user``
****************

.. versionadded:: 2015.8.0

Default: ``''``

Along with :conf_master:`winrepo_password`, is used to authenticate to HTTPS
remotes.

.. code-block:: yaml

    winrepo_user: git

.. conf_master:: winrepo_password

``winrepo_password``
********************

.. versionadded:: 2015.8.0

Default: ``''``

Along with :conf_master:`winrepo_user`, is used to authenticate to HTTPS
remotes. This parameter is not required if the repository does not use
authentication.

.. code-block:: yaml

    winrepo_password: mypassword

.. conf_master:: winrepo_insecure_auth

``winrepo_insecure_auth``
*************************

.. versionadded:: 2015.8.0

Default: ``False``

By default, Salt will not authenticate to an HTTP (non-HTTPS) remote. This
parameter enables authentication over HTTP. **Enable this at your own risk.**

.. code-block:: yaml

    winrepo_insecure_auth: True

.. conf_master:: winrepo_pubkey

``winrepo_pubkey``
******************

.. versionadded:: 2015.8.0

Default: ``''``

Along with :conf_master:`winrepo_privkey` (and optionally
:conf_master:`winrepo_passphrase`), is used to authenticate to SSH remotes.

.. code-block:: yaml

    winrepo_pubkey: /path/to/key.pub

.. conf_master:: winrepo_privkey

``winrepo_privkey``
*******************

.. versionadded:: 2015.8.0

Default: ``''``

Along with :conf_master:`winrepo_pubkey` (and optionally
:conf_master:`winrepo_passphrase`), is used to authenticate to SSH remotes.

.. code-block:: yaml

    winrepo_privkey: /path/to/key

.. conf_master:: winrepo_passphrase

``winrepo_passphrase``
**********************

.. versionadded:: 2015.8.0

Default: ``''``

This parameter is optional, required only when the SSH key being used to
authenticate is protected by a passphrase.

.. code-block:: yaml

    winrepo_passphrase: mypassphrase
