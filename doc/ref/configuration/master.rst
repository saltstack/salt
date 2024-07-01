.. _configuration-salt-master:

===========================
Configuring the Salt Master
===========================

The Salt system is amazingly simple and easy to configure, the two components
of the Salt system each have a respective configuration file. The
``salt-master`` is configured via the master configuration file, and the
``salt-minion`` is configured via the minion configuration file.

.. seealso::

    :ref:`Example master configuration file <configuration-examples-master>`.

The configuration file for the salt-master is located at ``/etc/salt/master``
by default. Atomic included configuration files can be placed in
``/etc/salt/master.d/*.conf``. Warning: files with other suffixes than .conf will
not be included. A notable exception is FreeBSD, where the configuration file is
located at ``/usr/local/etc/salt``. The available options are as follows:


.. _primary-master-configuration:

Primary Master Configuration
============================

.. conf_master:: interface

``interface``
-------------

Default: ``0.0.0.0`` (all interfaces)

The local interface to bind to, must be an IP address.

.. code-block:: yaml

    interface: 192.168.0.1

.. conf_master:: ipv6

``ipv6``
--------

Default: ``False``

Whether the master should listen for IPv6 connections. If this is set to True,
the interface option must be adjusted too (for example: ``interface: '::'``)

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
-------------

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

.. note::

    Starting with version `3006.0`, Salt's offical packages ship with a default
    configuration which runs the Master as a non-priviledged user. The Master's
    configuration file has the `user` option set to `user: salt`. Unless you
    are absolutly sure want to run salt as some other user, care should be
    taken to preserve this setting in your Master configuration file..

.. conf_master:: ret_port

``enable_ssh_minions``
----------------------


Default: ``False``

Tell the master to also use salt-ssh when running commands against minions.

.. code-block:: yaml

    enable_ssh_minions: True

.. note::

    Enabling this does not influence the limitations on cross-minion communication.
    The Salt mine and ``publish.publish`` do not work from regular minions
    to SSH minions, the other way around is partly possible since 3007.0
    (during state rendering on the master).
    This means you can use the mentioned functions to call out to regular minions
    in ``sls`` templates and wrapper modules, but state modules
    (which are executed on the remote) relying on them still do not work.

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

Default: ``/``

The system root directory to operate from, change this to make Salt run from
an alternative root.

.. code-block:: yaml

    root_dir: /

.. note::

    This directory is prepended to the following options:
    :conf_master:`pki_dir`, :conf_master:`cachedir`, :conf_master:`sock_dir`,
    :conf_master:`log_file`, :conf_master:`autosign_file`,
    :conf_master:`autoreject_file`, :conf_master:`pidfile`,
    :conf_master:`autosign_grains_dir`.

.. conf_master:: conf_file

``conf_file``
-------------

Default: ``/etc/salt/master``

The path to the master's configuration file.

.. code-block:: yaml

    conf_file: /etc/salt/master

.. conf_master:: pki_dir

``pki_dir``
-----------

Default: ``<LIB_STATE_DIR>/pki/master``

The directory to store the pki authentication keys.

``<LIB_STATE_DIR>`` is the pre-configured variable state directory set during
installation via ``--salt-lib-state-dir``. It defaults to ``/etc/salt``. Systems
following the Filesystem Hierarchy Standard (FHS) might set it to
``/var/lib/salt``.

.. code-block:: yaml

    pki_dir: /etc/salt/pki/master


.. conf_master:: cluster_id

``cluster_id``
--------------

.. versionadded:: 3007

When defined, the master will operate in cluster mode. The master will send the
cluster key and id to minions instead of its own key and id. The master will
also forward its local event bus to other masters defined by ``cluster_peers``


.. code-block:: yaml

    cluster_id: master

.. conf_master:: cluster_peers

``cluster_peers``
-----------------

.. versionadded:: 3007

When ``cluster_id`` is defined, this setting is a list of other master
(hostnames or ips) that will be in the cluster.

.. code-block:: yaml

    cluster_peers:
       - master2
       - master3

.. conf_master:: cluster_pki_dir

``cluster_pki_dir``
-------------------

.. versionadded:: 3007

When ``cluster_id`` is defined, this sets the location of where this cluster
will store its cluster public and private key as well as any minion keys. This
setting will default to the value of ``pki_dir``, but should be changed
to the filesystem location shared between peers in the cluster.

.. code-block:: yaml

    cluster_pki: /my/gluster/share/pki


.. conf_master:: extension_modules

``extension_modules``
---------------------

.. versionchanged:: 2016.3.0

    The default location for this directory has been moved. Prior to this
    version, the location was a directory named ``extmods`` in the Salt
    cachedir (on most platforms, ``/var/cache/salt/extmods``). It has been
    moved into the master cachedir (on most platforms,
    ``/var/cache/salt/master/extmods``).

Directory where custom modules are synced to. This directory can contain
subdirectories for each of Salt's module types such as ``runners``,
``output``, ``wheel``, ``modules``, ``states``, ``returners``, ``engines``,
``utils``, etc.  This path is appended to :conf_master:`root_dir`.

Note, any directories or files not found in the `module_dirs` location
will be removed from the extension_modules path.

.. code-block:: yaml

    extension_modules: /root/salt_extmods

.. conf_master:: extmod_whitelist
.. conf_master:: extmod_blacklist

``extmod_whitelist/extmod_blacklist``
-------------------------------------

.. versionadded:: 2017.7.0

By using this dictionary, the modules that are synced to the master's extmod cache using `saltutil.sync_*` can be
limited.  If nothing is set to a specific type, then all modules are accepted.  To block all modules of a specific type,
whitelist an empty list.

.. code-block:: yaml

    extmod_whitelist:
      modules:
        - custom_module
      engines:
        - custom_engine
      pillars: []

    extmod_blacklist:
      modules:
        - specific_module

Valid options:
  - modules
  - states
  - grains
  - renderers
  - returners
  - output
  - proxy
  - runners
  - wheel
  - engines
  - queues
  - pillar
  - utils
  - sdb
  - cache
  - clouds
  - tops
  - roster
  - tokens

.. conf_master:: module_dirs

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

Default: ``/var/cache/salt/master``

The location used to store cache information, particularly the job information
for executed salt commands.

This directory may contain sensitive data and should be protected accordingly.

.. code-block:: yaml

    cachedir: /var/cache/salt/master

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

Set the number of hours to keep old job information. Note that setting this option
to ``0`` disables the cache cleaner.

.. deprecated:: 3006
    Replaced by :conf_master:`keep_jobs_seconds`

.. code-block:: yaml

    keep_jobs: 24

.. conf_master:: keep_jobs_seconds

``keep_jobs_seconds``
---------------------

Default: ``86400``

Set the number of seconds to keep old job information. Note that setting this option
to ``0`` disables the cache cleaner.

.. code-block:: yaml

    keep_jobs_seconds: 86400

.. conf_master:: gather_job_timeout

``gather_job_timeout``
----------------------

.. versionadded:: 2014.7.0

Default: ``10``

The number of seconds to wait when the client is requesting information
about running jobs.

.. code-block:: yaml

    gather_job_timeout: 10

.. conf_master:: timeout

``timeout``
-----------

Default: ``5``

Set the default timeout for the salt command and api.

.. conf_master:: loop_interval

``loop_interval``
-----------------

Default: ``60``

The loop_interval option controls the seconds for the master's Maintenance
process check cycle. This process updates file server backends, cleans the
job cache and executes the scheduler.

``maintenance_interval``
------------------------

.. versionadded:: 3006.0

Default: ``3600``

Defines how often to restart the master's Maintenance process.

.. code-block:: yaml

    maintenance_interval: 9600


.. conf_master:: output

``output``
----------

Default: ``nested``

Set the default outputter used by the salt command.

.. conf_master:: outputter_dirs

``outputter_dirs``
------------------

Default: ``[]``

A list of additional directories to search for salt outputters in.

.. code-block:: yaml

    outputter_dirs: []

.. conf_master:: output_file

``output_file``
---------------

Default: None

Set the default output file used by the salt command. Default is to output
to the CLI and not to a file. Functions the same way as the "--out-file"
CLI option, only sets this to a single file for all salt commands.

.. code-block:: yaml

    output_file: /path/output/file

.. conf_master:: show_timeout

``show_timeout``
----------------

Default: ``True``

Tell the client to show minions that have timed out.

.. code-block:: yaml

    show_timeout: True

.. conf_master:: show_jid

``show_jid``
------------

Default: ``False``

Tell the client to display the jid when a job is published.

.. code-block:: yaml

    show_jid: False

.. conf_master:: color

``color``
---------

Default: ``True``

By default output is colored, to disable colored output set the color value
to False.

.. code-block:: yaml

    color: False

.. conf_master:: color_theme

``color_theme``
---------------

Default: ``""``

Specifies a path to the color theme to use for colored command line output.

.. code-block:: yaml

    color_theme: /etc/salt/color_theme

.. conf_master:: cli_summary

``cli_summary``
---------------

Default: ``False``

When set to ``True``, displays a summary of the number of minions targeted,
the number of minions returned, and the number of minions that did not
return.

.. code-block:: yaml

    cli_summary: False

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

Default: ``False``

Enable GPU hardware data for your master. Be aware that the master can
take a while to start up when lspci and/or dmidecode is used to populate the
grains for the master.

.. code-block:: yaml

    enable_gpu_grains: True

.. conf_master:: skip_grains

``skip_grains``
---------------------

Default: ``False``

MasterMinions should omit grains. A MasterMinion is "a minion function object
for generic use on the master" that omit pillar. A RunnerClient creates a
MasterMinion omitting states and renderer. Setting to True can improve master
performance.

.. code-block:: yaml

    skip_grains: True

.. conf_master:: job_cache

``job_cache``
-------------

Default: ``True``

The master maintains a temporary job cache. While this is a great addition, it
can be a burden on the master for larger deployments (over 5000 minions).
Disabling the job cache will make previously executed jobs unavailable to
the jobs system and is not generally recommended. Normally it is wise to make
sure the master has access to a faster IO system or a tmpfs is mounted to the
jobs dir.

.. code-block:: yaml

    job_cache: True

.. note::

    Setting the ``job_cache`` to ``False`` will not cache minion returns, but
    the JID directory for each job is still created. The creation of the JID
    directories is necessary because Salt uses those directories to check for
    JID collisions. By setting this option to ``False``, the job cache
    directory, which is ``/var/cache/salt/master/jobs/`` by default, will be
    smaller, but the JID directories will still be present.

    Note that the :conf_master:`keep_jobs_seconds` option can be set to a lower
    value, such as ``3600``, to limit the number of seconds jobs are stored in
    the job cache. (The default is 86400 seconds.)

    Please see the :ref:`Managing the Job Cache <managing_the_job_cache>`
    documentation for more information.

.. conf_master:: minion_data_cache

``minion_data_cache``
---------------------

Default: ``True``

The minion data cache is a cache of information about the minions stored on the
master, this information is primarily the pillar, grains and mine data. The data
is cached via the cache subsystem in the Master cachedir under the name of the
minion or in a supported database. The data is used to predetermine what minions
are expected to reply from executions.

.. code-block:: yaml

    minion_data_cache: True

.. conf_master:: cache

``cache``
---------

Default: ``localfs``

Cache subsystem module to use for minion data cache.

.. code-block:: yaml

    cache: consul

.. conf_master:: memcache_expire_seconds

``memcache_expire_seconds``
---------------------------

Default: ``0``

Memcache is an additional cache layer that keeps a limited amount of data
fetched from the minion data cache for a limited period of time in memory that
makes cache operations faster. It doesn't make much sense for the ``localfs``
cache driver but helps for more complex drivers like ``consul``.

This option sets the memcache items expiration time. By default is set to ``0``
that disables the memcache.

.. code-block:: yaml

    memcache_expire_seconds: 30

.. conf_master:: memcache_max_items

``memcache_max_items``
----------------------

Default: ``1024``

Set memcache limit in items that are bank-key pairs. I.e the list of
minion_0/data, minion_0/mine, minion_1/data contains 3 items. This value depends
on the count of minions usually targeted in your environment. The best one could
be found by analyzing the cache log with ``memcache_debug`` enabled.

.. code-block:: yaml

    memcache_max_items: 1024

.. conf_master:: memcache_full_cleanup

``memcache_full_cleanup``
-------------------------

Default: ``False``

If cache storage got full, i.e. the items count exceeds the
``memcache_max_items`` value, memcache cleans up its storage. If this option
set to ``False`` memcache removes the only one oldest value from its storage.
If this set set to ``True`` memcache removes all the expired items and also
removes the oldest one if there are no expired items.

.. code-block:: yaml

    memcache_full_cleanup: True

.. conf_master:: memcache_debug

``memcache_debug``
------------------

Default: ``False``

Enable collecting the memcache stats and log it on `debug` log level. If enabled
memcache collect information about how many ``fetch`` calls has been done and
how many of them has been hit by memcache. Also it outputs the rate value that
is the result of division of the first two values. This should help to choose
right values for the expiration time and the cache size.

.. code-block:: yaml

    memcache_debug: True

.. conf_master:: ext_job_cache

``ext_job_cache``
-----------------

Default: ``''``

Used to specify a default returner for all minions. When this option is set,
the specified returner needs to be properly configured and the minions will
always default to sending returns to this returner. This will also disable the
local job cache on the master.

.. code-block:: yaml

    ext_job_cache: redis

.. conf_master:: event_return

``event_return``
----------------

.. versionadded:: 2015.5.0

Default: ``''``

Specify the returner(s) to use to log events. Each returner may have
installation and configuration requirements. Read the returner's
documentation.

.. note::

   Not all returners support event returns. Verify that a returner has an
   ``event_return()`` function before configuring this option with a returner.

.. code-block:: yaml

    event_return:
      - syslog
      - splunk

.. conf_master:: event_return_queue

``event_return_queue``
----------------------

.. versionadded:: 2015.5.0

Default: ``0``

On busy systems, enabling event_returns can cause a considerable load on
the storage system for returners. Events can be queued on the master and
stored in a batched fashion using a single transaction for multiple events.
By default, events are not queued.

.. code-block:: yaml

    event_return_queue: 0

.. conf_master:: event_return_whitelist

``event_return_whitelist``
--------------------------

.. versionadded:: 2015.5.0

Default: ``[]``

Only return events matching tags in a whitelist.

.. versionchanged:: 2016.11.0

    Supports glob matching patterns.

.. code-block:: yaml

    event_return_whitelist:
      - salt/master/a_tag
      - salt/run/*/ret

.. conf_master:: event_return_blacklist

``event_return_blacklist``
--------------------------

.. versionadded:: 2015.5.0

Default: ``[]``

Store all event returns _except_ the tags in a blacklist.

.. versionchanged:: 2016.11.0

    Supports glob matching patterns.

.. code-block:: yaml

    event_return_blacklist:
      - salt/master/not_this_tag
      - salt/wheel/*/ret

.. conf_master:: max_event_size

``max_event_size``
------------------

.. versionadded:: 2014.7.0

Default: ``1048576``

Passing very large events can cause the minion to consume large amounts of
memory. This value tunes the maximum size of a message allowed onto the
master event bus. The value is expressed in bytes.

.. code-block:: yaml

    max_event_size: 1048576

.. conf_master:: master_job_cache

``master_job_cache``
--------------------

.. versionadded:: 2014.7.0

Default: ``local_cache``

Specify the returner to use for the job cache. The job cache will only be
interacted with from the salt master and therefore does not need to be
accessible from the minions.

.. code-block:: yaml

    master_job_cache: redis

.. conf_master:: job_cache_store_endtime

``job_cache_store_endtime``
---------------------------

.. versionadded:: 2015.8.0

Default: ``False``

Specify whether the Salt Master should store end times for jobs as returns
come in.

.. code-block:: yaml

    job_cache_store_endtime: False

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
Please note that this can slow down the authentication process a bit in large
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
that does not send executions to minions.

.. code-block:: yaml

    presence_events: False

``detect_remote_minions``
-------------------------

Default: False

When checking the minions connected to a master, also include the master's
connections to minions on the port specified in the setting `remote_minions_port`.
This is particularly useful when checking if the master is connected to any Heist-Salt
minions. If this setting is set to True, the master will check all connections on port 22
by default unless a user also configures a different port with the setting
`remote_minions_port`.

Changing this setting will check the remote minions the master is connected to when using
presence events, the manage runner, and any other parts of the code that call the
`connected_ids` method to check the status of connected minions.

.. code-block:: yaml

    detect_remote_minions: True

``remote_minions_port``
-----------------------

Default: 22

The port to use when checking for remote minions when `detect_remote_minions` is set
to True.

.. code-block:: yaml

    remote_minions_port: 2222


.. conf_master:: ping_on_rotate

``ping_on_rotate``
------------------

.. versionadded:: 2014.7.0

Default: ``False``

By default, the master AES key rotates every 24 hours. The next command
following a key rotation will trigger a key refresh from the minion which may
result in minions which do not respond to the first command after a key refresh.

To tell the master to ping all minions immediately after an AES key refresh,
set ``ping_on_rotate`` to ``True``. This should mitigate the issue where a
minion does not appear to initially respond after a key is rotated.

Note that enabling this may cause high load on the master immediately after the
key rotation event as minions reconnect. Consider this carefully if this salt
master is managing a large number of minions.

If disabled, it is recommended to handle this event by listening for the
``aes_key_rotate`` event with the ``key`` tag and acting appropriately.

.. code-block:: yaml

    ping_on_rotate: False

.. conf_master:: transport

``transport``
-------------

Default: ``zeromq``

Changes the underlying transport layer. ZeroMQ is the recommended transport
while additional transport layers are under development. Supported values are
``zeromq`` and ``tcp`` (experimental). This setting has a significant impact on
performance and should not be changed unless you know what you are doing!

.. code-block:: yaml

    transport: zeromq

.. conf_master:: transport_opts

``transport_opts``
------------------

Default: ``{}``

(experimental) Starts multiple transports and overrides options for each
transport with the provided dictionary This setting has a significant impact on
performance and should not be changed unless you know what you are doing!  The
following example shows how to start a TCP transport alongside a ZMQ transport.

.. code-block:: yaml

    transport_opts:
      tcp:
        publish_port: 4605
        ret_port: 4606
      zeromq: []

.. conf_master:: master_stats

``master_stats``
----------------

Default: False

Turning on the master stats enables runtime throughput and statistics events
to be fired from the master event bus. These events will report on what
functions have been run on the master and how long these runs have, on
average, taken over a given period of time.

.. conf_master:: master_stats_event_iter

``master_stats_event_iter``
---------------------------

Default: 60

The time in seconds to fire master_stats events. This will only fire in
conjunction with receiving a request to the master, idle masters will not
fire these events.

.. conf_master:: sock_pool_size

``sock_pool_size``
------------------

Default: 1

To avoid blocking waiting while writing a data to a socket, we support
socket pool for Salt applications. For example, a job with a large number
of target host list can cause long period blocking waiting. The option
is used by ZMQ and TCP transports, and the other transport methods don't
need the socket pool by definition. Most of Salt tools, including CLI,
are enough to use a single bucket of socket pool. On the other hands,
it is highly recommended to set the size of socket pool larger than 1
for other Salt applications, especially Salt API, which must write data
to socket concurrently.

.. code-block:: yaml

    sock_pool_size: 15

.. conf_master:: ipc_mode

``ipc_mode``
------------

Default: ``ipc``

The ipc strategy. (i.e., sockets versus tcp, etc.) Windows platforms lack
POSIX IPC and must rely on TCP based inter-process communications. ``ipc_mode``
is set to ``tcp`` by default on Windows.

.. code-block:: yaml

    ipc_mode: ipc

.. conf_master:: ipc_write_buffer

``ipc_write_buffer``
-----------------------

Default: ``0``

The maximum size of a message sent via the IPC transport module can be limited
dynamically or by sharing an integer value lower than the total memory size. When
the value ``dynamic`` is set, salt will use 2.5% of the total memory as
``ipc_write_buffer`` value (rounded to an integer). A value of ``0`` disables
this option.

.. code-block:: yaml

    ipc_write_buffer: 10485760

.. conf_master:: tcp_master_pub_port

``tcp_master_pub_port``
-----------------------

Default: ``4512``

The TCP port on which events for the master should be published if ``ipc_mode`` is TCP.

.. code-block:: yaml

    tcp_master_pub_port: 4512

.. conf_master:: tcp_master_pull_port

``tcp_master_pull_port``
------------------------

Default: ``4513``

The TCP port on which events for the master should be pulled if ``ipc_mode`` is TCP.

.. code-block:: yaml

    tcp_master_pull_port: 4513

.. conf_master:: tcp_master_publish_pull

``tcp_master_publish_pull``
---------------------------

Default: ``4514``

The TCP port on which events for the master should be pulled fom and then republished onto
the event bus on the master.

.. code-block:: yaml

    tcp_master_publish_pull: 4514

.. conf_master:: tcp_master_workers

``tcp_master_workers``
----------------------

Default: ``4515``

The TCP port for ``mworkers`` to connect to on the master.

.. code-block:: yaml

    tcp_master_workers: 4515

.. conf_master:: auth_events

``auth_events``
---------------

.. versionadded:: 2017.7.3

Default: ``True``

Determines whether the master will fire authentication events.
:ref:`Authentication events <event-master_auth>` are fired when
a minion performs an authentication check with the master.

.. code-block:: yaml

    auth_events: True

.. conf_master:: minion_data_cache_events

``minion_data_cache_events``
----------------------------

.. versionadded:: 2017.7.3

Default: ``True``

Determines whether the master will fire minion data cache events.  Minion data
cache events are fired when a minion requests a minion data cache refresh.

.. code-block:: yaml

    minion_data_cache_events: True

.. conf_master:: http_connect_timeout

``http_connect_timeout``
------------------------

.. versionadded:: 2019.2.0

Default: ``20``

HTTP connection timeout in seconds.
Applied when fetching files using tornado back-end.
Should be greater than overall download time.

.. code-block:: yaml

    http_connect_timeout: 20

.. conf_master:: http_request_timeout

``http_request_timeout``
------------------------

.. versionadded:: 2015.8.0

Default: ``3600``

HTTP request timeout in seconds.
Applied when fetching files using tornado back-end.
Should be greater than overall download time.

.. code-block:: yaml

    http_request_timeout: 3600

``use_yamlloader_old``
----------------------

.. versionadded:: 2019.2.1

Default: ``False``

Use the pre-2019.2 YAML renderer.
Uses legacy YAML rendering to support some legacy inline data structures.
See the :ref:`2019.2.1 release notes <release-2019-2-1>` for more details.

.. code-block:: yaml

    use_yamlloader_old: False

.. conf_master:: req_server_niceness

``req_server_niceness``
-----------------------

.. versionadded:: 3001

Default: ``None``

Process priority level of the ReqServer subprocess of the master.
Supported on POSIX platforms only.

.. code-block:: yaml

    req_server_niceness: 9

.. conf_master:: pub_server_niceness

``pub_server_niceness``
-----------------------

.. versionadded:: 3001

Default: ``None``

Process priority level of the PubServer subprocess of the master.
Supported on POSIX platforms only.

.. code-block:: yaml

    pub_server_niceness: 9

.. conf_master:: fileserver_update_niceness

``fileserver_update_niceness``
------------------------------

.. versionadded:: 3001

Default: ``None``

Process priority level of the FileServerUpdate subprocess of the master.
Supported on POSIX platforms only.

.. code-block:: yaml

    fileserver_update_niceness: 9

.. conf_master:: maintenance_niceness

``maintenance_niceness``
------------------------

.. versionadded:: 3001

Default: ``None``

Process priority level of the Maintenance subprocess of the master.
Supported on POSIX platforms only.

.. code-block:: yaml

    maintenance_niceness: 9

.. conf_master:: mworker_niceness

``mworker_niceness``
--------------------

.. versionadded:: 3001

Default: ``None``

Process priority level of the MWorker subprocess of the master.
Supported on POSIX platforms only.

.. code-block:: yaml

    mworker_niceness: 9

.. conf_master:: mworker_queue_niceness

``mworker_queue_niceness``
--------------------------

.. versionadded:: 3001

default: ``None``

process priority level of the MWorkerQueue subprocess of the master.
supported on POSIX platforms only.

.. code-block:: yaml

    mworker_queue_niceness: 9

.. conf_master:: event_return_niceness

``event_return_niceness``
-------------------------

.. versionadded:: 3001

default: ``None``

process priority level of the EventReturn subprocess of the master.
supported on POSIX platforms only.

.. code-block:: yaml

    event_return_niceness: 9


.. conf_master:: event_publisher_niceness

``event_publisher_niceness``
----------------------------

.. versionadded:: 3001

default: ``none``

process priority level of the EventPublisher subprocess of the master.
supported on POSIX platforms only.

.. code-block:: yaml

    event_publisher_niceness: 9

.. conf_master:: reactor_niceness

``reactor_niceness``
--------------------

.. versionadded:: 3001

default: ``None``

process priority level of the Reactor subprocess of the master.
supported on POSIX platforms only.

.. code-block:: yaml

    reactor_niceness: 9

.. _salt-ssh-configuration:

Salt-SSH Configuration
======================

.. conf_master:: roster

``roster``
---------------

Default: ``flat``

Define the default salt-ssh roster module to use

.. code-block:: yaml

    roster: cache

.. conf_master:: roster_defaults

``roster_defaults``
-------------------

.. versionadded:: 2017.7.0

Default settings which will be inherited by all rosters.

.. code-block:: yaml

    roster_defaults:
      user: daniel
      sudo: True
      priv: /root/.ssh/id_rsa
      tty: True

.. conf_master:: roster_file

``roster_file``
---------------

Default: ``/etc/salt/roster``

Pass in an alternative location for the salt-ssh :py:mod:`flat
<salt.roster.flat>` roster file.

.. code-block:: yaml

    roster_file: /root/roster

.. conf_master:: rosters

``rosters``
-----------

Default: ``None``

Define locations for :py:mod:`flat <salt.roster.flat>` roster files so they can
be chosen when using Salt API. An administrator can place roster files into
these locations. Then, when calling Salt API, the :conf_master:`roster_file`
parameter should contain a relative path to these locations. That is,
``roster_file=/foo/roster`` will be resolved as
``/etc/salt/roster.d/foo/roster`` etc. This feature prevents passing insecure
custom rosters through the Salt API.

.. code-block:: yaml

    rosters:
     - /etc/salt/roster.d
     - /opt/salt/some/more/rosters

.. conf_master:: ssh_passwd

``ssh_passwd``
--------------

Default: ``''``

The ssh password to log in with.

.. code-block:: yaml

    ssh_passwd: ''

.. conf_master:: ssh_priv_passwd

``ssh_priv_passwd``
-------------------

Default: ``''``

Passphrase for ssh private key file.

.. code-block:: yaml

    ssh_priv_passwd: ''

.. conf_master:: ssh_port

``ssh_port``
------------

Default: ``22``

The target system's ssh port number.

.. code-block:: yaml

    ssh_port: 22

.. conf_master:: ssh_scan_ports

``ssh_scan_ports``
------------------

Default: ``22``

Comma-separated list of ports to scan.

.. code-block:: yaml

    ssh_scan_ports: 22

.. conf_master:: ssh_scan_timeout

``ssh_scan_timeout``
--------------------

Default: ``0.01``

Scanning socket timeout for salt-ssh.

.. code-block:: yaml

    ssh_scan_timeout: 0.01

.. conf_master:: ssh_sudo

``ssh_sudo``
------------

Default: ``False``

Boolean to run command via sudo.

.. code-block:: yaml

    ssh_sudo: False

.. conf_master:: ssh_timeout

``ssh_timeout``
---------------

Default: ``60``

Number of seconds to wait for a response when establishing an SSH connection.

.. code-block:: yaml

    ssh_timeout: 60

.. conf_master:: ssh_user

``ssh_user``
------------

Default: ``root``

The user to log in as.

.. code-block:: yaml

    ssh_user: root

.. conf_master:: ssh_log_file

``ssh_log_file``
----------------

.. versionadded:: 2016.3.5

Default: ``/var/log/salt/ssh``

Specify the log file of the ``salt-ssh`` command.

.. code-block:: yaml

    ssh_log_file: /var/log/salt/ssh

.. conf_master:: ssh_minion_opts

``ssh_minion_opts``
-------------------

Default: None

Pass in minion option overrides that will be inserted into the SHIM for
salt-ssh calls. The local minion config is not used for salt-ssh. Can be
overridden on a per-minion basis in the roster (``minion_opts``)

.. code-block:: yaml

    ssh_minion_opts:
      gpg_keydir: /root/gpg

.. conf_master:: ssh_use_home_key

``ssh_use_home_key``
--------------------

Default: False

Set this to True to default to using ``~/.ssh/id_rsa`` for salt-ssh
authentication with minions

.. code-block:: yaml

    ssh_use_home_key: False

.. conf_master:: ssh_identities_only

``ssh_identities_only``
-----------------------

Default: ``False``

Set this to ``True`` to default salt-ssh to run with ``-o IdentitiesOnly=yes``. This
option is intended for situations where the ssh-agent offers many different identities
and allows ssh to ignore those identities and use the only one specified in options.

.. code-block:: yaml

    ssh_identities_only: False

.. conf_master:: ssh_list_nodegroups

``ssh_list_nodegroups``
-----------------------

Default: ``{}``

List-only nodegroups for salt-ssh. Each group must be formed as either a comma-separated
list, or a YAML list. This option is useful to group minions into easy-to-target groups
when using salt-ssh. These groups can then be targeted with the normal -N argument to
salt-ssh.

.. code-block:: yaml

    ssh_list_nodegroups:
      groupA: minion1,minion2
      groupB: minion1,minion3

.. conf_master:: ssh_run_pre_flight

Default: False

Run the ssh_pre_flight script defined in the salt-ssh roster. By default
the script will only run when the thin dir does not exist on the targeted
minion. This will force the script to run and not check if the thin dir
exists first.

.. conf_master:: thin_extra_mods

``thin_extra_mods``
-------------------

Default: None

List of additional modules, needed to be included into the Salt Thin.
Pass a list of importable Python modules that are typically located in
the `site-packages` Python directory so they will be also always included
into the Salt Thin, once generated.

``min_extra_mods``
------------------

Default: None

Identical as `thin_extra_mods`, only applied to the Salt Minimal.


.. _master-security-settings:

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

.. conf_master:: keysize

``keysize``
-----------

Default: ``2048``

The size of key that should be generated when creating new keys.

.. code-block:: yaml

    keysize: 2048

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

.. versionchanged:: 2018.3.0
    For security reasons the file must be readonly except for its owner.
    If :conf_master:`permissive_pki_access` is ``True`` the owning group can also
    have write access, but if Salt is running as ``root`` it must be a member of that group.
    A less strict requirement also existed in previous version.

.. conf_master:: autoreject_file

``autoreject_file``
-------------------

.. versionadded:: 2014.1.0

Default: ``not defined``

Works like :conf_master:`autosign_file`, but instead allows you to specify
minion IDs for which keys will automatically be rejected. Will override both
membership in the :conf_master:`autosign_file` and the
:conf_master:`auto_accept` setting.

.. conf_master:: autosign_grains_dir

``autosign_grains_dir``
-----------------------

.. versionadded:: 2018.3.0

Default: ``not defined``

If the ``autosign_grains_dir`` is specified, incoming keys from minions with
grain values that match those defined in files in the autosign_grains_dir
will be accepted automatically. Grain values that should be accepted automatically
can be defined by creating a file named like the corresponding grain in the
autosign_grains_dir and writing the values into that file, one value per line.
Lines starting with a ``#`` will be ignored.
Minion must be configured to send the corresponding grains on authentication.
This should still be considered a less than secure option, due to the fact
that trust is based on just the requesting minion.

Please see the :ref:`Autoaccept Minions from Grains <tutorial-autoaccept-grains>`
documentation for more information.

.. code-block:: yaml

    autosign_grains_dir: /etc/salt/autosign_grains

.. conf_master:: permissive_pki_access

``permissive_pki_access``
-------------------------

Default: ``False``

Enable permissive access to the salt keys. This allows you to run the
master or minion as root, but have a non-root group be given access to
your pki_dir. To make the access explicit, root must belong to the group
you've given access to. This is potentially quite insecure. If an autosign_file
is specified, enabling permissive_pki_access will allow group access to that
specific file.

.. code-block:: yaml

    permissive_pki_access: False

.. conf_master:: publisher_acl

``publisher_acl``
-----------------

Default: ``{}``

Enable user accounts on the master to execute specific modules. These modules
can be expressed as regular expressions.

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
module.

This is completely disabled by default.

.. code-block:: yaml

    publisher_acl_blacklist:
      users:
        - root
        - '^(?!sudo_).*$'   #  all non sudo users
      modules:
        - cmd.*
        - test.echo

.. conf_master:: sudo_acl

``sudo_acl``
------------

Default: ``False``

Enforce ``publisher_acl`` and ``publisher_acl_blacklist`` when users have sudo
access to the salt command.

.. code-block:: yaml

    sudo_acl: False

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

.. conf_master:: token_expire_user_override

``token_expire_user_override``
------------------------------

Default: ``False``

Allow eauth users to specify the expiry time of the tokens they generate.

A boolean applies to all users or a dictionary of whitelisted eauth backends
and usernames may be given:

.. code-block:: yaml

    token_expire_user_override:
      pam:
        - fred
        - tom
      ldap:
        - gary

.. conf_master:: keep_acl_in_token

``keep_acl_in_token``
---------------------

Default: ``False``

Set to True to enable keeping the calculated user's auth list in the token
file. This is disabled by default and the auth list is calculated or requested
from the eauth driver each time.

Note: `keep_acl_in_token` will be forced to True when using external authentication
for REST API (`rest` is present under `external_auth`). This is because the REST API
does not store the password, and can therefore not retroactively fetch the ACL, so
the ACL must be stored in the token.

.. code-block:: yaml

    keep_acl_in_token: False

.. conf_master:: eauth_acl_module

``eauth_acl_module``
--------------------

Default: ``''``

Auth subsystem module to use to get authorized access list for a user. By default it's
the same module used for external authentication.

.. code-block:: yaml

    eauth_acl_module: django

.. conf_master:: file_recv

``file_recv``
-------------

Default: ``False``

Allow minions to push files to the master. This is disabled by default, for
security purposes.

.. code-block:: yaml

    file_recv: False

.. conf_master:: file_recv_max_size

``file_recv_max_size``
----------------------

.. versionadded:: 2014.7.0

Default: ``100``

Set a hard-limit on the size of the files that can be pushed to the master.
It will be interpreted as megabytes.

.. code-block:: yaml

    file_recv_max_size: 100

.. conf_master:: master_sign_pubkey

``master_sign_pubkey``
----------------------

Default: ``False``

Sign the master auth-replies with a cryptographic signature of the master's
public key. Please see the tutorial how to use these settings in the
`Multimaster-PKI with Failover Tutorial <https://docs.saltproject.io/en/latest/topics/tutorials/multimaster_pki.html>`_

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

The name of the file in the master's pki-directory that holds the pre-calculated
signature of the master's public-key.

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

.. conf_master:: publish_session

``publish_session``
-------------------

Default: ``86400``

The number of seconds between AES key rotations on the master.

.. code-block:: yaml

    publish_session: Default: 86400

.. conf_master:: ssl


``publish_signing_algorithm``
-----------------------------

.. versionadded:: 3006.9

Default: PKCS1v15-SHA1

The RSA signing algorithm used by this minion when connecting to the
master's request channel. Valid values are ``PKCS1v15-SHA1`` and
``PKCS1v15-SHA224``. Minions must be at version ``3006.9`` or greater if this
is changed from the default setting.


``ssl``
-------

.. versionadded:: 2016.11.0

Default: ``None``

TLS/SSL connection options. This could be set to a dictionary containing
arguments corresponding to python ``ssl.wrap_socket`` method. For details see
`Tornado <http://www.tornadoweb.org/en/stable/tcpserver.html#tornado.tcpserver.TCPServer>`_
and `Python <https://docs.python.org/3/library/ssl.html#ssl.wrap_socket>`_
documentation.

Note: to set enum arguments values like ``cert_reqs`` and ``ssl_version`` use
constant names without ssl module prefix: ``CERT_REQUIRED`` or ``PROTOCOL_SSLv23``.

.. code-block:: yaml

    ssl:
        keyfile: <path_to_keyfile>
        certfile: <path_to_certfile>
        ssl_version: PROTOCOL_TLSv1_2

.. conf_master:: preserve_minion_cache

``preserve_minion_cache``
-------------------------

Default: ``False``

By default, the master deletes its cache of minion data when the key for that
minion is removed. To preserve the cache after key deletion, set
``preserve_minion_cache`` to True.

WARNING: This may have security implications if compromised minions auth with
a previous deleted minion ID.

.. code-block:: yaml

    preserve_minion_cache: False

.. conf_master:: allow_minion_key_revoke

``allow_minion_key_revoke``
---------------------------

Default: ``True``

Controls whether a minion can request its own key revocation.  When True
the master will honor the minion's request and revoke its key.  When False,
the master will drop the request and the minion's key will remain accepted.


.. code-block:: yaml

    allow_minion_key_revoke: False

.. conf_master:: optimization_order

``optimization_order``
----------------------

Default: ``[0, 1, 2]``

In cases where Salt is distributed without .py files, this option determines
the priority of optimization level(s) Salt's module loader should prefer.

.. note::
    This option is only supported on Python 3.5+.

.. code-block:: yaml

    optimization_order:
      - 2
      - 0
      - 1

Master Large Scale Tuning Settings
==================================

.. conf_master:: max_open_files

``max_open_files``
------------------

Default: ``100000``

Each minion connecting to the master uses AT LEAST one file descriptor, the
master subscription connection. If enough minions connect you might start
seeing on the console(and then salt-master crashes):

.. code-block:: text

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

Standards for busy environments:

* Use one worker thread per 200 minions.
* The value of worker_threads should not exceed 1½ times the available CPU cores.

.. note::
    When the master daemon starts, it is expected behaviour to see
    multiple salt-master processes, even if 'worker_threads' is set to '1'. At
    a minimum, a controlling process will start along with a Publisher, an
    EventPublisher, and a number of MWorker processes will be started. The
    number of MWorker processes is tuneable by the 'worker_threads'
    configuration value while the others are not.

.. code-block:: yaml

    worker_threads: 5

.. conf_master:: pub_hwm

``pub_hwm``
-----------

Default: ``1000``

The zeromq high water mark on the publisher interface.

.. code-block:: yaml

    pub_hwm: 1000

.. conf_master:: zmq_backlog

``zmq_backlog``
---------------

Default: ``1000``

The listen queue size of the ZeroMQ backlog.

.. code-block:: yaml

    zmq_backlog: 1000

.. _master-module-management:

Master Module Management
========================

.. conf_master:: runner_dirs

``runner_dirs``
---------------

Default: ``[]``

Set additional directories to search for runner modules.

.. code-block:: yaml

    runner_dirs:
      - /var/lib/salt/runners

.. conf_master:: utils_dirs

``utils_dirs``
---------------

.. versionadded:: 2018.3.0

Default: ``[]``

Set additional directories to search for util modules.

.. code-block:: yaml

    utils_dirs:
      - /var/lib/salt/utils

.. conf_master:: cython_enable

``cython_enable``
-----------------

Default: ``False``

Set to true to enable Cython modules (.pyx files) to be compiled on the fly on
the Salt master.

.. code-block:: yaml

    cython_enable: False


.. _master-state-system-settings:

Master State System Settings
============================

.. conf_master:: state_top

``state_top``
-------------

Default: ``top.sls``

The state system uses a "top" file to tell the minions what environment to
use and what modules to use. The state_top file is defined relative to the
root of the base environment. The value of "state_top" is also used for the
pillar top file

.. code-block:: yaml

    state_top: top.sls

.. conf_master:: state_top_saltenv

``state_top_saltenv``
---------------------

This option has no default value. Set it to an environment name to ensure that
*only* the top file from that environment is considered during a
:ref:`highstate <running-highstate>`.

.. note::
    Using this value does not change the merging strategy. For instance, if
    :conf_master:`top_file_merging_strategy` is set to ``merge``, and
    :conf_master:`state_top_saltenv` is set to ``foo``, then any sections for
    environments other than ``foo`` in the top file for the ``foo`` environment
    will be ignored. With :conf_master:`state_top_saltenv` set to ``base``, all
    states from all environments in the ``base`` top file will be applied,
    while all other top files are ignored. The only way to set
    :conf_master:`state_top_saltenv` to something other than ``base`` and not
    have the other environments in the targeted top file ignored, would be to
    set :conf_master:`top_file_merging_strategy` to ``merge_all``.

.. code-block:: yaml

    state_top_saltenv: dev

.. conf_master:: top_file_merging_strategy

``top_file_merging_strategy``
-----------------------------

.. versionchanged:: 2016.11.0
    A ``merge_all`` strategy has been added.

Default: ``merge``

When no specific fileserver environment (a.k.a. ``saltenv``) has been specified
for a :ref:`highstate <running-highstate>`, all environments' top files are
inspected. This config option determines how the SLS targets in those top files
are handled.

When set to ``merge``, the ``base`` environment's top file is evaluated first,
followed by the other environments' top files. The first target expression
(e.g. ``'*'``) for a given environment is kept, and when the same target
expression is used in a different top file evaluated later, it is ignored.
Because ``base`` is evaluated first, it is authoritative. For example, if there
is a target for ``'*'`` for the ``foo`` environment in both the ``base`` and
``foo`` environment's top files, the one in the ``foo`` environment would be
ignored. The environments will be evaluated in no specific order (aside from
``base`` coming first). For greater control over the order in which the
environments are evaluated, use :conf_master:`env_order`. Note that, aside from
the ``base`` environment's top file, any sections in top files that do not
match that top file's environment will be ignored. So, for example, a section
for the ``qa`` environment would be ignored if it appears in the ``dev``
environment's top file. To keep use cases like this from being ignored, use the
``merge_all`` strategy.

When set to ``same``, then for each environment, only that environment's top
file is processed, with the others being ignored. For example, only the ``dev``
environment's top file will be processed for the ``dev`` environment, and any
SLS targets defined for ``dev`` in the ``base`` environment's (or any other
environment's) top file will be ignored. If an environment does not have a top
file, then the top file from the :conf_master:`default_top` config parameter
will be used as a fallback.

When set to ``merge_all``, then all states in all environments in all top files
will be applied. The order in which individual SLS files will be executed will
depend on the order in which the top files were evaluated, and the environments
will be evaluated in no specific order. For greater control over the order in
which the environments are evaluated, use :conf_master:`env_order`.

.. code-block:: yaml

    top_file_merging_strategy: same

.. conf_master:: env_order

``env_order``
-------------

Default: ``[]``

When :conf_master:`top_file_merging_strategy` is set to ``merge``, and no
environment is specified for a :ref:`highstate <running-highstate>`, this
config option allows for the order in which top files are evaluated to be
explicitly defined.

.. code-block:: yaml

    env_order:
      - base
      - dev
      - qa

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

.. conf_master:: renderer

``renderer``
------------

Default: ``jinja|yaml``

The renderer to use on the minions to render the state data.

.. code-block:: yaml

    renderer: jinja|json

.. conf_master:: userdata_template

``userdata_template``
---------------------

.. versionadded:: 2016.11.4

Default: ``None``

The renderer to use for templating userdata files in salt-cloud, if the
``userdata_template`` is not set in the cloud profile. If no value is set in
the cloud profile or master config file, no templating will be performed.

.. code-block:: yaml

    userdata_template: jinja

.. conf_master:: jinja_env

``jinja_env``
-------------

.. versionadded:: 2018.3.0

Default: ``{}``

jinja_env overrides the default Jinja environment options for
**all templates except sls templates**.
To set the options for sls templates use :conf_master:`jinja_sls_env`.

.. note::

    The `Jinja2 Environment documentation <https://jinja.palletsprojects.com/en/2.11.x/api/#jinja2.Environment>`_ is the official source for the default values.
    Not all the options listed in the jinja documentation can be overridden using :conf_master:`jinja_env` or :conf_master:`jinja_sls_env`.

The default options are:

.. code-block:: yaml

    jinja_env:
      block_start_string: '{%'
      block_end_string: '%}'
      variable_start_string: '{{'
      variable_end_string: '}}'
      comment_start_string: '{#'
      comment_end_string: '#}'
      line_statement_prefix:
      line_comment_prefix:
      trim_blocks: False
      lstrip_blocks: False
      newline_sequence: '\n'
      keep_trailing_newline: False

.. conf_master:: jinja_sls_env

``jinja_sls_env``
-----------------

.. versionadded:: 2018.3.0

Default: ``{}``

jinja_sls_env sets the Jinja environment options for **sls templates**.
The defaults and accepted options are exactly the same as they are
for :conf_master:`jinja_env`.

The default options are:

.. code-block:: yaml

    jinja_sls_env:
      block_start_string: '{%'
      block_end_string: '%}'
      variable_start_string: '{{'
      variable_end_string: '}}'
      comment_start_string: '{#'
      comment_end_string: '#}'
      line_statement_prefix:
      line_comment_prefix:
      trim_blocks: False
      lstrip_blocks: False
      newline_sequence: '\n'
      keep_trailing_newline: False

Example using line statements and line comments to increase ease of use:

If your configuration options are

.. code-block:: yaml

    jinja_sls_env:
      line_statement_prefix: '%'
      line_comment_prefix: '##'

With these options jinja will interpret anything after a ``%`` at the start of a line (ignoreing whitespace)
as a jinja statement and will interpret anything after a ``##`` as a comment.

This allows the following more convenient syntax to be used:

.. code-block:: jinja

    ## (this comment will not stay once rendered)
    # (this comment remains in the rendered template)
    ## ensure all the formula services are running
    % for service in formula_services:
    enable_service_{{ service }}:
      service.running:
        name: {{ service }}
    % endfor

The following less convenient but equivalent syntax would have to
be used if you had not set the line_statement and line_comment options:

.. code-block:: jinja

    {# (this comment will not stay once rendered) #}
    # (this comment remains in the rendered template)
    {# ensure all the formula services are running #}
    {% for service in formula_services %}
    enable_service_{{ service }}:
      service.running:
        name: {{ service }}
    {% endfor %}

.. conf_master:: jinja_trim_blocks

``jinja_trim_blocks``
---------------------

.. deprecated:: 2018.3.0
    Replaced by :conf_master:`jinja_env` and :conf_master:`jinja_sls_env`

.. versionadded:: 2014.1.0

Default: ``False``

If this is set to ``True``, the first newline after a Jinja block is
removed (block, not variable tag!). Defaults to ``False`` and corresponds
to the Jinja environment init variable ``trim_blocks``.

.. code-block:: yaml

    jinja_trim_blocks: False

.. conf_master:: jinja_lstrip_blocks

``jinja_lstrip_blocks``
-----------------------

.. deprecated:: 2018.3.0
    Replaced by :conf_master:`jinja_env` and :conf_master:`jinja_sls_env`

.. versionadded:: 2014.1.0

Default: ``False``

If this is set to ``True``, leading spaces and tabs are stripped from the
start of a line to a block. Defaults to ``False`` and corresponds to the
Jinja environment init variable ``lstrip_blocks``.

.. code-block:: yaml

    jinja_lstrip_blocks: False

.. conf_master:: failhard

``failhard``
------------

Default: ``False``

Set the global failhard flag. This informs all states to stop running states
at the moment a single state fails.

.. code-block:: yaml

    failhard: False

.. conf_master:: state_verbose

``state_verbose``
-----------------

Default: ``True``

Controls the verbosity of state runs. By default, the results of all states are
returned, but setting this value to ``False`` will cause salt to only display
output for states that failed or states that have changes.

.. code-block:: yaml

    state_verbose: False

.. conf_master:: state_output

``state_output``
----------------

Default: ``full``

The state_output setting controls which results will be output full multi line:

* ``full``, ``terse`` - each state will be full/terse
* ``mixed`` - only states with errors will be full
* ``changes`` - states with changes and errors will be full

``full_id``, ``mixed_id``, ``changes_id`` and ``terse_id`` are also allowed;
when set, the state ID will be used as name in the output.

.. code-block:: yaml

    state_output: full

.. conf_master:: state_output_diff

``state_output_diff``
---------------------

Default: ``False``

The state_output_diff setting changes whether or not the output from
successful states is returned. Useful when even the terse output of these
states is cluttering the logs. Set it to True to ignore them.

.. code-block:: yaml

    state_output_diff: False

.. conf_master:: state_output_profile

``state_output_profile``
------------------------

Default: ``True``

The ``state_output_profile`` setting changes whether profile information
will be shown for each state run.

.. code-block:: yaml

    state_output_profile: True

.. conf_master:: state_output_pct

``state_output_pct``
--------------------

Default: ``False``

The ``state_output_pct`` setting changes whether success and failure information
as a percent of total actions will be shown for each state run.

.. code-block:: yaml

    state_output_pct: False

.. conf_master:: state_compress_ids

``state_compress_ids``
----------------------

Default: ``False``

The ``state_compress_ids`` setting aggregates information about states which
have multiple "names" under the same state ID in the highstate output.

.. code-block:: yaml

    state_compress_ids: False

.. conf_master:: state_aggregate

``state_aggregate``
-------------------

Default: ``False``

Automatically aggregate all states that have support for ``mod_aggregate`` by
setting to ``True``.

.. code-block:: yaml

    state_aggregate: True

Or pass a list of state module names to automatically
aggregate just those types.

.. code-block:: yaml

    state_aggregate:
      - pkg

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

``runner_returns``
------------------

Default: ``True``

If set to ``False``, runner jobs will not be saved to job cache (defined by
:conf_master:`master_job_cache`).

.. code-block:: yaml

    runner_returns: False


.. _master-file-server-settings:

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
      - gitfs

.. note::
    For masterless Salt, this parameter must be specified in the minion config
    file.

.. conf_master:: fileserver_followsymlinks

``fileserver_followsymlinks``
-----------------------------

.. versionadded:: 2014.1.0

Default: ``True``

By default, the file_server follows symlinks when walking the filesystem tree.
Currently this only applies to the default roots fileserver_backend.

.. code-block:: yaml

    fileserver_followsymlinks: True

.. conf_master:: fileserver_ignoresymlinks

``fileserver_ignoresymlinks``
-----------------------------

.. versionadded:: 2014.1.0

Default: ``False``

If you do not want symlinks to be treated as the files they are pointing to,
set ``fileserver_ignoresymlinks`` to ``True``. By default this is set to
False. When set to ``True``, any detected symlink while listing files on the
Master will not be returned to the Minion.

.. code-block:: yaml

    fileserver_ignoresymlinks: False

.. conf_master:: fileserver_list_cache_time

``fileserver_list_cache_time``
------------------------------

.. versionadded:: 2014.1.0
.. versionchanged:: 2016.11.0
    The default was changed from ``30`` seconds to ``20``.

Default: ``20``

Salt caches the list of files/symlinks/directories for each fileserver backend
and environment as they are requested, to guard against a performance
bottleneck at scale when many minions all ask the fileserver which files are
available simultaneously. This configuration parameter allows for the max age
of that cache to be altered.

Set this value to ``0`` to disable use of this cache altogether, but keep in
mind that this may increase the CPU load on the master when running a highstate
on a large number of minions.

.. note::
    Rather than altering this configuration parameter, it may be advisable to
    use the :mod:`fileserver.clear_file_list_cache
    <salt.runners.fileserver.clear_file_list_cache>` runner to clear these
    caches.

.. code-block:: yaml

    fileserver_list_cache_time: 5

.. conf_master:: fileserver_verify_config

``fileserver_verify_config``
----------------------------

.. versionadded:: 2017.7.0

Default: ``True``

By default, as the master starts it performs some sanity checks on the
configured fileserver backends. If any of these sanity checks fail (such as
when an invalid configuration is used), the master daemon will abort.

To skip these sanity checks, set this option to ``False``.

.. code-block:: yaml

    fileserver_verify_config: False

.. conf_master:: hash_type

``hash_type``
-------------

Default: ``sha256``

The hash_type is the hash to use when discovering the hash of a file on
the master server. The default is sha256, but md5, sha1, sha224, sha384, and
sha512 are also supported.

.. code-block:: yaml

    hash_type: sha256

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

.. conf_master:: master_roots

``master_roots``
----------------

Default: ``''``

A master-only copy of the :conf_master:`file_roots` dictionary, used by the
state compiler.

Example:

.. code-block:: yaml

    master_roots:
      base:
        - /srv/salt-master

roots: Master's Local File Server
---------------------------------

.. conf_master:: file_roots

``file_roots``
**************

.. versionchanged:: 3005

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

As of 2018.3.5 and 2019.2.1, it is possible to have `__env__` as a catch-all environment.

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
      __env__:
        - /srv/salt/default

Taking dynamic environments one step further, ``__env__`` can also be used in
the ``file_roots`` filesystem path as of version 3005. It will be replaced with
the actual ``saltenv`` and searched for states and data to provide to the
minion. Note this substitution ONLY occurs for the ``__env__`` environment. For
instance, this configuration:

.. code-block:: yaml

    file_roots:
      __env__:
        - /srv/__env__/salt

is equivalent to this static configuration:

.. code-block:: yaml

    file_roots:
      dev:
        - /srv/dev/salt
      test:
        - /srv/test/salt
      prod:
        - /srv/prod/salt

.. note::
    For masterless Salt, this parameter must be specified in the minion config
    file.

.. conf_master:: roots_update_interval

``roots_update_interval``
*************************

.. versionadded:: 2018.3.0

Default: ``60``

This option defines the update interval (in seconds) for
:conf_master:`file_roots`.

.. note::
    Since ``file_roots`` consists of files local to the minion, the update
    process for this fileserver backend just reaps the cache for this backend.

.. code-block:: yaml

    roots_update_interval: 120

gitfs: Git Remote File Server Backend
-------------------------------------

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

Must be either ``pygit2`` or ``gitpython``. If unset, then each will be tried
in that same order, and the first one with a compatible version installed will
be the provider that is used.

.. code-block:: yaml

    gitfs_provider: gitpython

.. conf_master:: gitfs_ssl_verify

``gitfs_ssl_verify``
********************

Default: ``True``

Specifies whether or not to ignore SSL certificate errors when fetching from
the repositories configured in :conf_master:`gitfs_remotes`. The ``False``
setting is useful if you're using a git repo that uses a self-signed
certificate. However, keep in mind that setting this to anything other ``True``
is a considered insecure, and using an SSH-based transport (if available) may
be a better option.

.. code-block:: yaml

    gitfs_ssl_verify: False

.. note::
    pygit2 only supports disabling SSL verification in versions 0.23.2 and
    newer.

.. versionchanged:: 2015.8.0
    This option can now be configured on individual repositories as well. See
    :ref:`here <gitfs-per-remote-config>` for more info.

.. versionchanged:: 2016.11.0
    The default config value changed from ``False`` to ``True``.

.. conf_master:: gitfs_mountpoint

``gitfs_mountpoint``
********************

.. versionadded:: 2014.7.0

Default: ``''``

Specifies a path on the salt fileserver which will be prepended to all files
served by gitfs. This option can be used in conjunction with
:conf_master:`gitfs_root`. It can also be configured for an individual
repository, see :ref:`here <gitfs-per-remote-config>` for more info.

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
    This option can now be configured on individual repositories as well. See
    :ref:`here <gitfs-per-remote-config>` for more info.

.. conf_master:: gitfs_base

``gitfs_base``
**************

Default: ``master``

Defines which branch/tag should be used as the ``base`` environment.

.. code-block:: yaml

    gitfs_base: salt

.. versionchanged:: 2014.7.0
    This option can now be configured on individual repositories as well. See
    :ref:`here <gitfs-per-remote-config>` for more info.

.. conf_master:: gitfs_saltenv

``gitfs_saltenv``
*****************

.. versionadded:: 2016.11.0

Default: ``[]``

Global settings for :ref:`per-saltenv configuration parameters
<gitfs-per-saltenv-config>`. Though per-saltenv configuration parameters are
typically one-off changes specific to a single gitfs remote, and thus more
often configured on a per-remote basis, this parameter can be used to specify
per-saltenv changes which should apply to all remotes. For example, the below
configuration will map the ``develop`` branch to the ``dev`` saltenv for all
gitfs remotes.

.. code-block:: yaml

    gitfs_saltenv:
      - dev:
        - ref: develop

.. conf_master:: gitfs_disable_saltenv_mapping

``gitfs_disable_saltenv_mapping``
*********************************

.. versionadded:: 2018.3.0

Default: ``False``

When set to ``True``, all saltenv mapping logic is disregarded (aside from
which branch/tag is mapped to the ``base`` saltenv). To use any other
environments, they must then be defined using :ref:`per-saltenv configuration
parameters <gitfs-per-saltenv-config>`.

.. code-block:: yaml

    gitfs_disable_saltenv_mapping: True

.. note::
    This is is a global configuration option, see :ref:`here
    <gitfs-per-remote-config>` for examples of configuring it for individual
    repositories.

.. conf_master:: gitfs_ref_types

``gitfs_ref_types``
*******************

.. versionadded:: 2018.3.0

Default: ``['branch', 'tag', 'sha']``

This option defines what types of refs are mapped to fileserver environments
(i.e. saltenvs). It also sets the order of preference when there are
ambiguously-named refs (i.e. when a branch and tag both have the same name).
The below example disables mapping of both tags and SHAs, so that only branches
are mapped as saltenvs:

.. code-block:: yaml

    gitfs_ref_types:
      - branch

.. note::
    This is is a global configuration option, see :ref:`here
    <gitfs-per-remote-config>` for examples of configuring it for individual
    repositories.

.. note::
    ``sha`` is special in that it will not show up when listing saltenvs (e.g.
    with the :py:func:`fileserver.envs <salt.runners.fileserver.envs>` runner),
    but works within states and with :py:func:`cp.cache_file
    <salt.modules.cp.cache_file>` to retrieve a file from a specific git SHA.

.. conf_master:: gitfs_saltenv_whitelist

``gitfs_saltenv_whitelist``
***************************

.. versionadded:: 2014.7.0
.. versionchanged:: 2018.3.0
    Renamed from ``gitfs_env_whitelist`` to ``gitfs_saltenv_whitelist``

Default: ``[]``

Used to restrict which environments are made available. Can speed up state runs
if the repos in :conf_master:`gitfs_remotes` contain many branches/tags.  More
information can be found in the :ref:`GitFS Walkthrough
<gitfs-whitelist-blacklist>`.

.. code-block:: yaml

    gitfs_saltenv_whitelist:
      - base
      - v1.*
      - 'mybranch\d+'

.. conf_master:: gitfs_saltenv_blacklist

``gitfs_saltenv_blacklist``
***************************

.. versionadded:: 2014.7.0
.. versionchanged:: 2018.3.0
    Renamed from ``gitfs_env_blacklist`` to ``gitfs_saltenv_blacklist``

Default: ``[]``

Used to restrict which environments are made available. Can speed up state runs
if the repos in :conf_master:`gitfs_remotes` contain many branches/tags. More
information can be found in the :ref:`GitFS Walkthrough
<gitfs-whitelist-blacklist>`.

.. code-block:: yaml

    gitfs_saltenv_blacklist:
      - base
      - v1.*
      - 'mybranch\d+'

.. conf_master:: gitfs_global_lock

``gitfs_global_lock``
*********************

.. versionadded:: 2015.8.9

Default: ``True``

When set to ``False``, if there is an update lock for a gitfs remote and the
pid written to it is not running on the master, the lock file will be
automatically cleared and a new lock will be obtained. When set to ``True``,
Salt will simply log a warning when there is an update lock present.

On single-master deployments, disabling this option can help automatically deal
with instances where the master was shutdown/restarted during the middle of a
gitfs update, leaving a update lock in place.

However, on multi-master deployments with the gitfs cachedir shared via
`GlusterFS`__, nfs, or another network filesystem, it is strongly recommended
not to disable this option as doing so will cause lock files to be removed if
they were created by a different master.

.. code-block:: yaml

    # Disable global lock
    gitfs_global_lock: False

.. __: http://www.gluster.org/

.. conf_master:: gitfs_update_interval

``gitfs_update_interval``
*************************

.. versionadded:: 2018.3.0

Default: ``60``

This option defines the default update interval (in seconds) for gitfs remotes.
The update interval can also be set for a single repository via a
:ref:`per-remote config option <gitfs-per-remote-config>`

.. code-block:: yaml

    gitfs_update_interval: 120

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

.. note::
    This is is a global configuration option, see :ref:`here
    <gitfs-per-remote-config>` for examples of configuring it for individual
    repositories.

.. conf_master:: gitfs_password

``gitfs_password``
~~~~~~~~~~~~~~~~~~

.. versionadded:: 2014.7.0

Default: ``''``

Along with :conf_master:`gitfs_user`, is used to authenticate to HTTPS remotes.
This parameter is not required if the repository does not use authentication.

.. code-block:: yaml

    gitfs_password: mypassword

.. note::
    This is is a global configuration option, see :ref:`here
    <gitfs-per-remote-config>` for examples of configuring it for individual
    repositories.

.. conf_master:: gitfs_insecure_auth

``gitfs_insecure_auth``
~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2014.7.0

Default: ``False``

By default, Salt will not authenticate to an HTTP (non-HTTPS) remote. This
parameter enables authentication over HTTP. **Enable this at your own risk.**

.. code-block:: yaml

    gitfs_insecure_auth: True

.. note::
    This is is a global configuration option, see :ref:`here
    <gitfs-per-remote-config>` for examples of configuring it for individual
    repositories.

.. conf_master:: gitfs_pubkey

``gitfs_pubkey``
~~~~~~~~~~~~~~~~

.. versionadded:: 2014.7.0

Default: ``''``

Along with :conf_master:`gitfs_privkey` (and optionally
:conf_master:`gitfs_passphrase`), is used to authenticate to SSH remotes.
Required for SSH remotes.

.. code-block:: yaml

    gitfs_pubkey: /path/to/key.pub

.. note::
    This is is a global configuration option, see :ref:`here
    <gitfs-per-remote-config>` for examples of configuring it for individual
    repositories.

.. conf_master:: gitfs_privkey

``gitfs_privkey``
~~~~~~~~~~~~~~~~~

.. versionadded:: 2014.7.0

Default: ``''``

Along with :conf_master:`gitfs_pubkey` (and optionally
:conf_master:`gitfs_passphrase`), is used to authenticate to SSH remotes.
Required for SSH remotes.

.. code-block:: yaml

    gitfs_privkey: /path/to/key

.. note::
    This is is a global configuration option, see :ref:`here
    <gitfs-per-remote-config>` for examples of configuring it for individual
    repositories.

.. conf_master:: gitfs_passphrase

``gitfs_passphrase``
~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2014.7.0

Default: ``''``

This parameter is optional, required only when the SSH key being used to
authenticate is protected by a passphrase.

.. code-block:: yaml

    gitfs_passphrase: mypassphrase

.. note::
    This is is a global configuration option, see :ref:`here
    <gitfs-per-remote-config>` for examples of configuring it for individual
    repositories.

.. conf_master:: gitfs_refspecs

``gitfs_refspecs``
~~~~~~~~~~~~~~~~~~

.. versionadded:: 2017.7.0

Default: ``['+refs/heads/*:refs/remotes/origin/*', '+refs/tags/*:refs/tags/*']``

When fetching from remote repositories, by default Salt will fetch branches and
tags. This parameter can be used to override the default and specify
alternate refspecs to be fetched. More information on how this feature works
can be found in the :ref:`GitFS Walkthrough <gitfs-custom-refspecs>`.

.. code-block:: yaml

    gitfs_refspecs:
      - '+refs/heads/*:refs/remotes/origin/*'
      - '+refs/tags/*:refs/tags/*'
      - '+refs/pull/*/head:refs/remotes/origin/pr/*'
      - '+refs/pull/*/merge:refs/remotes/origin/merge/*'

hgfs: Mercurial Remote File Server Backend
------------------------------------------

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

.. conf_master:: hgfs_saltenv_whitelist

``hgfs_saltenv_whitelist``
**************************

.. versionadded:: 2014.7.0
.. versionchanged:: 2018.3.0
    Renamed from ``hgfs_env_whitelist`` to ``hgfs_saltenv_whitelist``

Default: ``[]``

Used to restrict which environments are made available. Can speed up state runs
if your hgfs remotes contain many branches/bookmarks/tags. Full names, globs,
and regular expressions are supported. If using a regular expression, the
expression must match the entire minion ID.

If used, only branches/bookmarks/tags which match one of the specified
expressions will be exposed as fileserver environments.

If used in conjunction with :conf_master:`hgfs_saltenv_blacklist`, then the subset
of branches/bookmarks/tags which match the whitelist but do *not* match the
blacklist will be exposed as fileserver environments.

.. code-block:: yaml

    hgfs_saltenv_whitelist:
      - base
      - v1.*
      - 'mybranch\d+'

.. conf_master:: hgfs_saltenv_blacklist

``hgfs_saltenv_blacklist``
**************************

.. versionadded:: 2014.7.0
.. versionchanged:: 2018.3.0
    Renamed from ``hgfs_env_blacklist`` to ``hgfs_saltenv_blacklist``

Default: ``[]``

Used to restrict which environments are made available. Can speed up state runs
if your hgfs remotes contain many branches/bookmarks/tags. Full names, globs,
and regular expressions are supported. If using a regular expression, the
expression must match the entire minion ID.

If used, branches/bookmarks/tags which match one of the specified expressions
will *not* be exposed as fileserver environments.

If used in conjunction with :conf_master:`hgfs_saltenv_whitelist`, then the subset
of branches/bookmarks/tags which match the whitelist but do *not* match the
blacklist will be exposed as fileserver environments.

.. code-block:: yaml

    hgfs_saltenv_blacklist:
      - base
      - v1.*
      - 'mybranch\d+'

.. conf_master:: hgfs_update_interval

``hgfs_update_interval``
************************

.. versionadded:: 2018.3.0

Default: ``60``

This option defines the update interval (in seconds) for
:conf_master:`hgfs_remotes`.

.. code-block:: yaml

    hgfs_update_interval: 120

svnfs: Subversion Remote File Server Backend
--------------------------------------------

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

.. conf_master:: svnfs_saltenv_whitelist

``svnfs_saltenv_whitelist``
***************************

.. versionadded:: 2014.7.0
.. versionchanged:: 2018.3.0
    Renamed from ``svnfs_env_whitelist`` to ``svnfs_saltenv_whitelist``

Default: ``[]``

Used to restrict which environments are made available. Can speed up state runs
if your svnfs remotes contain many branches/tags. Full names, globs, and
regular expressions are supported. If using a regular expression, the expression
must match the entire minion ID.

If used, only branches/tags which match one of the specified expressions will
be exposed as fileserver environments.

If used in conjunction with :conf_master:`svnfs_saltenv_blacklist`, then the subset
of branches/tags which match the whitelist but do *not* match the blacklist
will be exposed as fileserver environments.

.. code-block:: yaml

    svnfs_saltenv_whitelist:
      - base
      - v1.*
      - 'mybranch\d+'

.. conf_master:: svnfs_saltenv_blacklist

``svnfs_saltenv_blacklist``
***************************

.. versionadded:: 2014.7.0
.. versionchanged:: 2018.3.0
    Renamed from ``svnfs_env_blacklist`` to ``svnfs_saltenv_blacklist``

Default: ``[]``

Used to restrict which environments are made available. Can speed up state runs
if your svnfs remotes contain many branches/tags. Full names, globs, and
regular expressions are supported. If using a regular expression, the
expression must match the entire minion ID.

If used, branches/tags which match one of the specified expressions will *not*
be exposed as fileserver environments.

If used in conjunction with :conf_master:`svnfs_saltenv_whitelist`, then the subset
of branches/tags which match the whitelist but do *not* match the blacklist
will be exposed as fileserver environments.

.. code-block:: yaml

    svnfs_saltenv_blacklist:
      - base
      - v1.*
      - 'mybranch\d+'

.. conf_master:: svnfs_update_interval

``svnfs_update_interval``
*************************

.. versionadded:: 2018.3.0

Default: ``60``

This option defines the update interval (in seconds) for
:conf_master:`svnfs_remotes`.

.. code-block:: yaml

    svnfs_update_interval: 120

minionfs: MinionFS Remote File Server Backend
---------------------------------------------

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
      - server01
      - dev*
      - 'mail\d+.mydomain.tld'

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
      - server01
      - dev*
      - 'mail\d+.mydomain.tld'

.. conf_master:: minionfs_update_interval

``minionfs_update_interval``
****************************

.. versionadded:: 2018.3.0

Default: ``60``

This option defines the update interval (in seconds) for :ref:`MinionFS
<tutorial-minionfs>`.

.. note::
    Since :ref:`MinionFS <tutorial-minionfs>` consists of files local to the
    master, the update process for this fileserver backend just reaps the cache
    for this backend.

.. code-block:: yaml

    minionfs_update_interval: 120

s3fs: S3 File Server Backend
----------------------------

.. versionadded:: 0.16.0

See the :mod:`s3fs documentation <salt.fileserver.s3fs>` for usage examples.

.. conf_master:: s3fs_update_interval

``s3fs_update_interval``
************************

.. versionadded:: 2018.3.0

Default: ``60``

This option defines the update interval (in seconds) for s3fs.

.. code-block:: yaml

    s3fs_update_interval: 120

``fileserver_interval``
***********************

.. versionadded:: 3006.0

Default: ``3600``

Defines how often to restart the master's FilesServerUpdate process.

.. code-block:: yaml

    fileserver_interval: 9600


.. _pillar-configuration-master:

Pillar Configuration
====================

.. conf_master:: pillar_roots

``pillar_roots``
----------------

.. versionchanged:: 3005

Default:

.. code-block:: yaml

    base:
      - /srv/pillar

Set the environments and directories used to hold pillar sls data. This
configuration is the same as :conf_master:`file_roots`:

As of 2017.7.5 and 2018.3.1, it is possible to have `__env__` as a catch-all environment.

Example:

.. code-block:: yaml

    pillar_roots:
      base:
        - /srv/pillar
      dev:
        - /srv/pillar/dev
      prod:
        - /srv/pillar/prod
      __env__:
        - /srv/pillar/others

Taking dynamic environments one step further, ``__env__`` can also be used in
the ``pillar_roots`` filesystem path as of version 3005. It will be replaced
with the actual ``pillarenv`` and searched for Pillar data to provide to the
minion. Note this substitution ONLY occurs for the ``__env__`` environment. For
instance, this configuration:

.. code-block:: yaml

    pillar_roots:
      __env__:
        - /srv/__env__/pillar

is equivalent to this static configuration:

.. code-block:: yaml

    pillar_roots:
      dev:
        - /srv/dev/pillar
      test:
        - /srv/test/pillar
      prod:
        - /srv/prod/pillar

.. conf_master:: on_demand_ext_pillar

``on_demand_ext_pillar``
------------------------

.. versionadded:: 2016.3.6,2016.11.3,2017.7.0

Default: ``['libvirt', 'virtkey']``

The external pillars permitted to be used on-demand using :py:func:`pillar.ext
<salt.modules.pillar.ext>`.

.. code-block:: yaml

    on_demand_ext_pillar:
      - libvirt
      - virtkey
      - git

.. warning::
    This will allow minions to request specific pillar data via
    :py:func:`pillar.ext <salt.modules.pillar.ext>`, and may be considered a
    security risk. However, pillar data generated in this way will not affect
    the :ref:`in-memory pillar data <pillar-in-memory>`, so this risk is
    limited to instances in which states/modules/etc. (built-in or custom) rely
    upon pillar data generated by :py:func:`pillar.ext
    <salt.modules.pillar.ext>`.

.. conf_master:: decrypt_pillar

``decrypt_pillar``
------------------

.. versionadded:: 2017.7.0

Default: ``[]``

A list of paths to be recursively decrypted during pillar compilation.

.. code-block:: yaml

    decrypt_pillar:
      - 'foo:bar': gpg
      - 'lorem:ipsum:dolor'

Entries in this list can be formatted either as a simple string, or as a
key/value pair, with the key being the pillar location, and the value being the
renderer to use for pillar decryption. If the former is used, the renderer
specified by :conf_master:`decrypt_pillar_default` will be used.

.. conf_master:: decrypt_pillar_delimiter

``decrypt_pillar_delimiter``
----------------------------

.. versionadded:: 2017.7.0

Default: ``:``

The delimiter used to distinguish nested data structures in the
:conf_master:`decrypt_pillar` option.

.. code-block:: yaml

    decrypt_pillar_delimiter: '|'
    decrypt_pillar:
      - 'foo|bar': gpg
      - 'lorem|ipsum|dolor'

.. conf_master:: decrypt_pillar_default

``decrypt_pillar_default``
--------------------------

.. versionadded:: 2017.7.0

Default: ``gpg``

The default renderer used for decryption, if one is not specified for a given
pillar key in :conf_master:`decrypt_pillar`.

.. code-block:: yaml

    decrypt_pillar_default: my_custom_renderer

.. conf_master:: decrypt_pillar_renderers

``decrypt_pillar_renderers``
----------------------------

.. versionadded:: 2017.7.0

Default: ``['gpg']``

List of renderers which are permitted to be used for pillar decryption.

.. code-block:: yaml

    decrypt_pillar_renderers:
      - gpg
      - my_custom_renderer

.. conf_master:: gpg_decrypt_must_succeed

``gpg_decrypt_must_succeed``
----------------------------

.. versionadded:: 3005

Default: ``False``

If this is ``True`` and the ciphertext could not be decrypted, then an error is
raised.

Sending the ciphertext through basically is *never* desired, for example if a
state is setting a database password from pillar and gpg rendering fails, then
the state will update the password to the ciphertext, which by definition is
not encrypted.

.. warning::

    The value defaults to ``False`` for backwards compatibility.  In the
    ``Chlorine`` release, this option will default to ``True``.

.. code-block:: yaml

    gpg_decrypt_must_succeed: False

.. conf_master:: pillar_opts

``pillar_opts``
---------------

Default: ``False``

The ``pillar_opts`` option adds the master configuration file data to a dict in
the pillar called ``master``. This can be used to set simple configurations in
the master config file that can then be used on minions.

Note that setting this option to ``True`` means the master config file will be
included in all minion's pillars. While this makes global configuration of services
and systems easy, it may not be desired if sensitive data is stored in the master
configuration.

.. code-block:: yaml

    pillar_opts: False

.. conf_master:: pillar_safe_render_error

``pillar_safe_render_error``
----------------------------

Default: ``True``

The pillar_safe_render_error option prevents the master from passing pillar
render errors to the minion. This is set on by default because the error could
contain templating data which would give that minion information it shouldn't
have, like a password! When set ``True`` the error message will only show:

.. code-block:: shell

    Rendering SLS 'my.sls' failed. Please see master log for details.

.. code-block:: yaml

    pillar_safe_render_error: True

.. _master-configuration-ext-pillar:

.. conf_master:: ext_pillar

``ext_pillar``
--------------

The ext_pillar option allows for any number of external pillar interfaces to be
called when populating pillar data. The configuration is based on ext_pillar
functions. The available ext_pillar functions can be found herein:

:blob:`salt/pillar`

By default, the ext_pillar interface is not configured to run.

Default: ``[]``

.. code-block:: yaml

    ext_pillar:
      - hiera: /etc/hiera.yaml
      - cmd_yaml: cat /etc/salt/yaml
      - reclass:
          inventory_base_uri: /etc/reclass

There are additional details at :ref:`salt-pillars`

.. conf_master:: ext_pillar_first

``ext_pillar_first``
--------------------

.. versionadded:: 2015.5.0

Default: ``False``

This option allows for external pillar sources to be evaluated before
:conf_master:`pillar_roots`. External pillar data is evaluated separately from
:conf_master:`pillar_roots` pillar data, and then both sets of pillar data are
merged into a single pillar dictionary, so the value of this config option will
have an impact on which key "wins" when there is one of the same name in both
the external pillar data and :conf_master:`pillar_roots` pillar data. By
setting this option to ``True``, ext_pillar keys will be overridden by
:conf_master:`pillar_roots`, while leaving it as ``False`` will allow
ext_pillar keys to override those from :conf_master:`pillar_roots`.

.. note::
    For a while, this config option did not work as specified above, because of
    a bug in Pillar compilation. This bug has been resolved in version 2016.3.4
    and later.

.. code-block:: yaml

    ext_pillar_first: False

.. conf_master:: pillarenv_from_saltenv

``pillarenv_from_saltenv``
--------------------------

Default: ``False``

When set to ``True``, the :conf_master:`pillarenv` value will assume the value
of the effective saltenv when running states. This essentially makes ``salt-run
pillar.show_pillar saltenv=dev`` equivalent to ``salt-run pillar.show_pillar
saltenv=dev pillarenv=dev``. If :conf_master:`pillarenv` is set on the CLI, it
will override this option.

.. code-block:: yaml

    pillarenv_from_saltenv: True

.. note::
    For salt remote execution commands this option should be set in the Minion
    configuration instead.

.. conf_master:: pillar_raise_on_missing

``pillar_raise_on_missing``
---------------------------

.. versionadded:: 2015.5.0

Default: ``False``

Set this option to ``True`` to force a ``KeyError`` to be raised whenever an
attempt to retrieve a named value from pillar fails. When this option is set
to ``False``, the failed attempt returns an empty string.

.. _git-pillar-config-opts:

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
configured as its environment to keep it from also being mapped to the
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
.. versionchanged:: 2016.11.0

Default: ``False``

Specifies whether or not to ignore SSL certificate errors when contacting the
remote repository. The ``False`` setting is useful if you're using a
git repo that uses a self-signed certificate. However, keep in mind that
setting this to anything other ``True`` is a considered insecure, and using an
SSH-based transport (if available) may be a better option.

In the 2016.11.0 release, the default config value changed from ``False`` to
``True``.

.. code-block:: yaml

    git_pillar_ssl_verify: True

.. note::
    pygit2 only supports disabling SSL verification in versions 0.23.2 and
    newer.

.. conf_master:: git_pillar_global_lock

``git_pillar_global_lock``
**************************

.. versionadded:: 2015.8.9

Default: ``True``

When set to ``False``, if there is an update/checkout lock for a git_pillar
remote and the pid written to it is not running on the master, the lock file
will be automatically cleared and a new lock will be obtained. When set to
``True``, Salt will simply log a warning when there is an lock present.

On single-master deployments, disabling this option can help automatically deal
with instances where the master was shutdown/restarted during the middle of a
git_pillar update/checkout, leaving a lock in place.

However, on multi-master deployments with the git_pillar cachedir shared via
`GlusterFS`__, nfs, or another network filesystem, it is strongly recommended
not to disable this option as doing so will cause lock files to be removed if
they were created by a different master.

.. code-block:: yaml

    # Disable global lock
    git_pillar_global_lock: False

.. __: http://www.gluster.org/

.. conf_master:: git_pillar_includes

``git_pillar_includes``
***********************

.. versionadded:: 2017.7.0

Default: ``True``

Normally, when processing :ref:`git_pillar remotes
<git-pillar-configuration>`, if more than one repo under the same ``git``
section in the ``ext_pillar`` configuration refers to the same pillar
environment, then each repo in a given environment will have access to the
other repos' files to be referenced in their top files. However, it may be
desirable to disable this behavior. If so, set this value to ``False``.

For a more detailed examination of how includes work, see :ref:`this
explanation <git-pillar-multiple-remotes>` from the git_pillar documentation.

.. code-block:: yaml

    git_pillar_includes: False

``git_pillar_update_interval``
******************************

.. versionadded:: 3000

Default: ``60``

This option defines the default update interval (in seconds) for git_pillar
remotes. The update is handled within the global loop, hence
``git_pillar_update_interval`` should be a multiple of ``loop_interval``.

.. code-block:: yaml

    git_pillar_update_interval: 120

.. _git-ext-pillar-auth-opts:

Git External Pillar Authentication Options
******************************************

These parameters only currently apply to the ``pygit2``
:conf_master:`git_pillar_provider`. Authentication works the same as it does
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

.. conf_master:: git_pillar_refspecs

``git_pillar_refspecs``
~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2017.7.0

Default: ``['+refs/heads/*:refs/remotes/origin/*', '+refs/tags/*:refs/tags/*']``

When fetching from remote repositories, by default Salt will fetch branches and
tags. This parameter can be used to override the default and specify
alternate refspecs to be fetched. This parameter works similarly to its
:ref:`GitFS counterpart <gitfs-custom-refspecs>`, in that it can be
configured both globally and for individual remotes.

.. code-block:: yaml

    git_pillar_refspecs:
      - '+refs/heads/*:refs/remotes/origin/*'
      - '+refs/tags/*:refs/tags/*'
      - '+refs/pull/*/head:refs/remotes/origin/pr/*'
      - '+refs/pull/*/merge:refs/remotes/origin/merge/*'

.. conf_master:: git_pillar_verify_config

``git_pillar_verify_config``
----------------------------

.. versionadded:: 2017.7.0

Default: ``True``

By default, as the master starts it performs some sanity checks on the
configured git_pillar repositories. If any of these sanity checks fail (such as
when an invalid configuration is used), the master daemon will abort.

To skip these sanity checks, set this option to ``False``.

.. code-block:: yaml

    git_pillar_verify_config: False

.. _pillar-merging-opts:

Pillar Merging Options
----------------------

.. conf_master:: pillar_source_merging_strategy

``pillar_source_merging_strategy``
**********************************

.. versionadded:: 2014.7.0

Default: ``smart``

The pillar_source_merging_strategy option allows you to configure merging
strategy between different sources. It accepts 5 values:

* ``none``:

  It will not do any merging at all and only parse the pillar data from the passed environment and 'base' if no environment was specified.

  .. versionadded:: 2016.3.4

* ``recurse``:

  It will recursively merge data. For example, theses 2 sources:

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

* ``aggregate``:

  instructs aggregation of elements between sources that use the #!yamlex renderer.

  For example, these two documents:

  .. code-block:: yaml

      foo: 42
      bar: !aggregate {
        element1: True
      }
      baz: !aggregate quux

  .. code-block:: yaml

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

  .. note::
      This requires that the :ref:`render pipeline <renderers-composing>`
      defined in the :conf_master:`renderer` master configuration ends in
      ``yamlex``.

* ``overwrite``:

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

* ``smart`` (default):

  Guesses the best strategy based on the "renderer" setting.

.. note::
    In order for yamlex based features such as ``!aggregate`` to work as expected
    across documents using the default ``smart`` merge strategy, the :conf_master:`renderer`
    config option must be set to ``jinja|yamlex`` or similar.

.. conf_master:: pillar_merge_lists

``pillar_merge_lists``
**********************

.. versionadded:: 2015.8.0

Default: ``False``

Recursively merge lists by aggregating them instead of replacing them.

.. code-block:: yaml

    pillar_merge_lists: False

.. conf_master:: pillar_includes_override_sls

``pillar_includes_override_sls``
********************************

.. versionadded:: 2017.7.6,2018.3.1

Default: ``False``

Prior to version 2017.7.3, keys from :ref:`pillar includes <pillar-include>`
would be merged on top of the pillar SLS. Since 2017.7.3, the includes are
merged together and then the pillar SLS is merged on top of that.

Set this option to ``True`` to return to the old behavior.

.. code-block:: yaml

    pillar_includes_override_sls: True

.. _pillar-cache-opts:

Pillar Cache Options
--------------------

.. conf_master:: pillar_cache

``pillar_cache``
****************

.. versionadded:: 2015.8.8

Default: ``False``

A master can cache pillars locally to bypass the expense of having to render them
for each minion on every request. This feature should only be enabled in cases
where pillar rendering time is known to be unsatisfactory and any attendant security
concerns about storing pillars in a master cache have been addressed.

When enabling this feature, be certain to read through the additional ``pillar_cache_*``
configuration options to fully understand the tunable parameters and their implications.

.. code-block:: yaml

    pillar_cache: False

.. note::

    Setting ``pillar_cache: True`` has no effect on
    :ref:`targeting minions with pillar <targeting-pillar>`.

.. conf_master:: pillar_cache_ttl

``pillar_cache_ttl``
********************

.. versionadded:: 2015.8.8

Default: ``3600``

If and only if a master has set ``pillar_cache: True``, the cache TTL controls the amount
of time, in seconds, before the cache is considered invalid by a master and a fresh
pillar is recompiled and stored.
The cache TTL does not prevent pillar cache from being refreshed before its TTL expires.

.. conf_master:: pillar_cache_backend

``pillar_cache_backend``
************************

.. versionadded:: 2015.8.8

Default: ``disk``

If an only if a master has set ``pillar_cache: True``, one of several storage providers
can be utilized:

* ``disk`` (default):

  The default storage backend. This caches rendered pillars to the master cache.
  Rendered pillars are serialized and deserialized as ``msgpack`` structures for speed.
  Note that pillars are stored UNENCRYPTED. Ensure that the master cache has permissions
  set appropriately (sane defaults are provided).

* ``memory`` [EXPERIMENTAL]:

  An optional backend for pillar caches which uses a pure-Python
  in-memory data structure for maximal performance. There are several caveats,
  however. First, because each master worker contains its own in-memory cache,
  there is no guarantee of cache consistency between minion requests. This
  works best in situations where the pillar rarely if ever changes. Secondly,
  and perhaps more importantly, this means that unencrypted pillars will
  be accessible to any process which can examine the memory of the ``salt-master``!
  This may represent a substantial security risk.

.. code-block:: yaml

    pillar_cache_backend: disk


Master Reactor Settings
=======================

.. conf_master:: reactor

``reactor``
-----------

Default: ``[]``

Defines a salt reactor. See the :ref:`Reactor <reactor>` documentation for more
information.

.. code-block:: yaml

    reactor:
      - 'salt/minion/*/start':
        - salt://reactor/startup_tasks.sls

.. conf_master:: reactor_refresh_interval

``reactor_refresh_interval``
----------------------------

Default: ``60``

The TTL for the cache of the reactor configuration.

.. code-block:: yaml

    reactor_refresh_interval: 60

.. conf_master:: reactor_worker_threads

``reactor_worker_threads``
--------------------------

Default: ``10``

The number of workers for the runner/wheel in the reactor.

.. code-block:: yaml

    reactor_worker_threads: 10

.. conf_master:: reactor_worker_hwm

``reactor_worker_hwm``
----------------------

Default: ``10000``

The queue size for workers in the reactor.

.. code-block:: yaml

    reactor_worker_hwm: 10000


.. _salt-api-master-settings:

Salt-API Master Settings
========================

There are some settings for :ref:`salt-api <netapi-introduction>` that can be
configured on the Salt Master.

.. conf_master:: api_logfile

``api_logfile``
---------------

Default: ``/var/log/salt/api``

The logfile location for ``salt-api``.

.. code-block:: yaml

    api_logfile: /var/log/salt/api

.. conf_master:: api_pidfile

``api_pidfile``
---------------

Default: /var/run/salt-api.pid

If this master will be running ``salt-api``, specify the pidfile of the
``salt-api`` daemon.

.. code-block:: yaml

    api_pidfile: /var/run/salt-api.pid

.. conf_master:: rest_timeout

``rest_timeout``
----------------

Default: ``300``

Used by ``salt-api`` for the master requests timeout.

.. code-block:: yaml

    rest_timeout: 300

.. conf_master:: netapi_disable_clients

``netapi_enable_clients``
--------------------------

.. versionadded:: 3006.0

Default: ``[]``

Used by ``salt-api`` to enable access to the listed clients. Unless a
client is addded to this list, requests will be rejected before
authentication is attempted or processing of the low state occurs.

This can be used to only expose the required functionality via
``salt-api``.

Configuration with all possible clients enabled:

.. code-block:: yaml

    netapi_enable_clients:
      - local
      - local_async
      - local_batch
      - local_subset
      - runner
      - runner_async
      - ssh
      - wheel
      - wheel_async

.. note::

    Enabling all clients is not recommended - only enable the
    clients that provide the functionality required.

.. _syndic-server-settings:

Syndic Server Settings
======================

A Salt syndic is a Salt master used to pass commands from a higher Salt master
to minions below the syndic. Using the syndic is simple. If this is a master
that will have syndic servers(s) below it, set the ``order_masters`` setting to
``True``.

If this is a master that will be running a syndic daemon for passthrough the
``syndic_master`` setting needs to be set to the location of the master server.

Do not forget that, in other words, it means that it shares with the local minion
its ID and PKI directory.

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

.. versionchanged:: 2016.3.5,2016.11.1

    Set default higher level master address.

Default: ``masterofmasters``

If this master will be running the ``salt-syndic`` to connect to a higher level
master, specify the higher level master with this configuration value.

.. code-block:: yaml

    syndic_master: masterofmasters

You can optionally connect a syndic to multiple higher level masters by
setting the ``syndic_master`` value to a list:

.. code-block:: yaml

    syndic_master:
      - masterofmasters1
      - masterofmasters2

Each higher level master must be set up in a multi-master configuration.

.. conf_master:: syndic_master_port

``syndic_master_port``
----------------------

Default: ``4506``

If this master will be running the ``salt-syndic`` to connect to a higher level
master, specify the higher level master port with this configuration value.

.. code-block:: yaml

    syndic_master_port: 4506

.. conf_master:: syndic_pidfile

``syndic_pidfile``
------------------

Default: ``/var/run/salt-syndic.pid``

If this master will be running the ``salt-syndic`` to connect to a higher level
master, specify the pidfile of the syndic daemon.

.. code-block:: yaml

    syndic_pidfile: /var/run/syndic.pid

.. conf_master:: syndic_log_file

``syndic_log_file``
-------------------

Default: ``/var/log/salt/syndic``

If this master will be running the ``salt-syndic`` to connect to a higher level
master, specify the log file of the syndic daemon.

.. code-block:: yaml

    syndic_log_file: /var/log/salt-syndic.log

.. conf_master:: syndic_failover

``syndic_failover``
-------------------

.. versionadded:: 2016.3.0

Default: ``random``

The behaviour of the multi-syndic when connection to a master of masters failed.
Can specify ``random`` (default) or ``ordered``. If set to ``random``, masters
will be iterated in random order. If ``ordered`` is specified, the configured
order will be used.

.. code-block:: yaml

    syndic_failover: random

.. conf_master:: syndic_wait

``syndic_wait``
---------------

Default: ``5``

The number of seconds for the salt client to wait for additional syndics to
check in with their lists of expected minions before giving up.

.. code-block:: yaml

    syndic_wait: 5

.. conf_master:: syndic_forward_all_events

``syndic_forward_all_events``
-----------------------------

.. versionadded:: 2017.7.0

Default: ``False``

Option on multi-syndic or single when connected to multiple masters to be able to
send events to all connected masters.

.. code-block:: yaml

    syndic_forward_all_events: False


.. _peer-publish-settings:

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
      foo\.example\.com:
          - test\..*
          - pkg\..*

This will allow all minions to execute all commands:

.. code-block:: yaml

    peer:
      .*:
          - .*

This is not recommended, since it would allow anyone who gets root on any
single minion to instantly have root on all of the minions!

It is also possible to limit target hosts with the :term:`Compound Matcher`.
You can achieve this by adding another layer in between the source and the
allowed functions:

.. code-block:: yaml

    peer:
      '.*\.example\.com':
        - 'G@role:db':
          - test\..*
          - pkg\..*

.. note::

    Notice that the source hosts are matched by a regular expression
    on their minion ID, while target hosts can be matched by any of
    the :ref:`available matchers <targeting-compound>`.

    Note that globbing and regex matching on pillar values is not supported. You can only match exact values.

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

Any log level below the `info` level is INSECURE and may log sensitive data. This currently includes:
#. profile
#. debug
#. trace
#. garbage
#. all

.. conf_master:: log_level_logfile

``log_level_logfile``
---------------------

Default: ``warning``

The level of messages to send to the log file. See also
:conf_log:`log_level_logfile`. When it is not set explicitly
it will inherit the level set by :conf_log:`log_level` option.

.. code-block:: yaml

    log_level_logfile: warning

Any log level below the `info` level is INSECURE and may log sensitive data. This currently includes:
#. profile
#. debug
#. trace
#. garbage
#. all

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

Default: ``%(asctime)s,%(msecs)03d [%(name)-17s][%(levelname)-8s] %(message)s``

The format of the log file logging messages. See also
:conf_log:`log_fmt_logfile`.

.. code-block:: yaml

    log_fmt_logfile: '%(asctime)s,%(msecs)03d [%(name)-17s][%(levelname)-8s] %(message)s'

.. conf_master:: log_granular_levels

``log_granular_levels``
-----------------------

Default: ``{}``

This can be used to control logging levels more specifically. See also
:conf_log:`log_granular_levels`.


.. conf_master:: log_rotate_max_bytes

``log_rotate_max_bytes``
------------------------

Default:  ``0``

The maximum number of bytes a single log file may contain before it is rotated.
A value of 0 disables this feature. Currently only supported on Windows. On
other platforms, use an external tool such as 'logrotate' to manage log files.
:conf_log:`log_rotate_max_bytes`


.. conf_master:: log_rotate_backup_count

``log_rotate_backup_count``
---------------------------

Default:  ``0``

The number of backup files to keep when rotating log files. Only used if
:conf_master:`log_rotate_max_bytes` is greater than 0. Currently only supported
on Windows. On other platforms, use an external tool such as 'logrotate' to
manage log files.
:conf_log:`log_rotate_backup_count`


.. _node-groups:

Node Groups
===========

.. conf_master:: nodegroups

``nodegroups``
--------------

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


.. _range-cluster-settings:

Range Cluster Settings
======================

.. conf_master:: range_server

``range_server``
----------------

Default: ``'range:80'``

The range server (and optional port) that serves your cluster information
https://github.com/ytoolshed/range/wiki/%22yamlfile%22-module-file-spec

.. code-block:: yaml

    range_server: range:80


.. _include-configuration:

Include Configuration
=====================

Configuration can be loaded from multiple files. The order in which this is
done is:

1. The master config file itself

2. The files matching the glob in :conf_master:`default_include`

3. The files matching the glob in :conf_master:`include` (if defined)

Each successive step overrides any values defined in the previous steps.
Therefore, any config options defined in one of the
:conf_master:`default_include` files would override the same value in the
master config file, and any options defined in :conf_master:`include` would
override both.

.. conf_master:: default_include

``default_include``
-------------------

Default: ``master.d/*.conf``

The master can include configuration from other files. Per default the
master will automatically include all config files from ``master.d/*.conf``
where ``master.d`` is relative to the directory of the master configuration
file.

.. note::

    Salt creates files in the ``master.d`` directory for its own use. These
    files are prefixed with an underscore. A common example of this is the
    ``_schedule.conf`` file.

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


Keepalive Settings
==================

.. conf_master:: tcp_keepalive

``tcp_keepalive``
-----------------

Default: ``True``

The tcp keepalive interval to set on TCP ports. This setting can be used to tune Salt
connectivity issues in messy network environments with misbehaving firewalls.

.. code-block:: yaml

    tcp_keepalive: True

.. conf_master:: tcp_keepalive_cnt

``tcp_keepalive_cnt``
---------------------

Default: ``-1``

Sets the ZeroMQ TCP keepalive count. May be used to tune issues with minion disconnects.

.. code-block:: yaml

    tcp_keepalive_cnt: -1

.. conf_master:: tcp_keepalive_idle

``tcp_keepalive_idle``
----------------------

Default: ``300``

Sets ZeroMQ TCP keepalive idle. May be used to tune issues with minion disconnects.

.. code-block:: yaml

    tcp_keepalive_idle: 300

.. conf_master:: tcp_keepalive_intvl

``tcp_keepalive_intvl``
-----------------------

Default: ``-1``

Sets ZeroMQ TCP keepalive interval. May be used to tune issues with minion disconnects.

.. code-block:: yaml

    tcp_keepalive_intvl': -1


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

    winrepo_dir_ng: /srv/salt/win/repo-ng

.. conf_master:: winrepo_cachefile
.. conf_master:: win_repo_mastercachefile

``winrepo_cachefile``
---------------------

.. versionchanged:: 2015.8.0

    Renamed from ``win_repo_mastercachefile`` to ``winrepo_cachefile``

.. note::

    2015.8.0 and later minions do not use this setting since the cachefile
    is now generated by the minion.

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

    winrepo_remotes_ng:
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

    winrepo_remotes:
      - https://mygitserver/winrepo1.git
      - https://mygitserver/winrepo2.git:
      - foo https://mygitserver/winrepo3.git

.. conf_master:: winrepo_ssl_verify

``winrepo_ssl_verify``
----------------------

.. versionadded:: 2015.8.0
.. versionchanged:: 2016.11.0

Default: ``False``

Specifies whether or not to ignore SSL certificate errors when contacting the
remote repository. The  ``False`` setting is useful if you're using a
git repo that uses a self-signed certificate. However, keep in mind that
setting this to anything other ``True`` is a considered insecure, and using an
SSH-based transport (if available) may be a better option.

In the 2016.11.0 release, the default config value changed from ``False`` to
``True``.

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

.. conf_master:: winrepo_refspecs

``winrepo_refspecs``
********************

.. versionadded:: 2017.7.0

Default: ``['+refs/heads/*:refs/remotes/origin/*', '+refs/tags/*:refs/tags/*']``

When fetching from remote repositories, by default Salt will fetch branches and
tags. This parameter can be used to override the default and specify
alternate refspecs to be fetched. This parameter works similarly to its
:ref:`GitFS counterpart <gitfs-custom-refspecs>`, in that it can be
configured both globally and for individual remotes.

.. code-block:: yaml

    winrepo_refspecs:
      - '+refs/heads/*:refs/remotes/origin/*'
      - '+refs/tags/*:refs/tags/*'
      - '+refs/pull/*/head:refs/remotes/origin/pr/*'
      - '+refs/pull/*/merge:refs/remotes/origin/merge/*'


.. _configure-master-on-windows:

Configure Master on Windows
===========================

The master on Windows requires no additional configuration. You can modify the
master configuration by creating/editing the master config file located at
``c:\salt\conf\master``. The same configuration options available on Linux are
available in Windows, as long as they apply. For example, SSH options wouldn't
apply in Windows. The main differences are the file paths. If you are familiar
with common salt paths, the following table may be useful:

=============  =========  =================
linux Paths               Windows Paths
=============  =========  =================
``/etc/salt``  ``<--->``  ``c:\salt\conf``
``/``          ``<--->``  ``c:\salt``
=============  =========  =================

So, for example, the master config file in Linux is ``/etc/salt/master``. In
Windows the master config file is ``c:\salt\conf\master``. The Linux path
``/etc/salt`` becomes ``c:\salt\conf`` in Windows.

Common File Locations
---------------------

======================================  =============================================
Linux Paths                             Windows Paths
======================================  =============================================
``conf_file: /etc/salt/master``         ``conf_file: c:\salt\conf\master``
``log_file: /var/log/salt/master``      ``log_file: c:\salt\var\log\salt\master``
``pidfile: /var/run/salt-master.pid``   ``pidfile: c:\salt\var\run\salt-master.pid``
======================================  =============================================

Common Directories
------------------

======================================================  ============================================
Linux Paths                                             Windows Paths
======================================================  ============================================
``cachedir: /var/cache/salt/master``                    ``cachedir: c:\salt\var\cache\salt\master``
``extension_modules: /var/cache/salt/master/extmods``   ``c:\salt\var\cache\salt\master\extmods``
``pki_dir: /etc/salt/pki/master``                       ``pki_dir: c:\salt\conf\pki\master``
``root_dir: /``                                         ``root_dir: c:\salt``
``sock_dir: /var/run/salt/master``                      ``sock_dir: c:\salt\var\run\salt\master``
======================================================  ============================================

Roots
-----

**file_roots**

==================  =========================
Linux Paths         Windows Paths
==================  =========================
``/srv/salt``       ``c:\salt\srv\salt``
``/srv/spm/salt``   ``c:\salt\srv\spm\salt``
==================  =========================

**pillar_roots**

====================  ===========================
Linux Paths           Windows Paths
====================  ===========================
``/srv/pillar``       ``c:\salt\srv\pillar``
``/srv/spm/pillar``   ``c:\salt\srv\spm\pillar``
====================  ===========================

Win Repo Settings
-----------------

==========================================  =================================================
Linux Paths                                 Windows Paths
==========================================  =================================================
``winrepo_dir: /srv/salt/win/repo``         ``winrepo_dir: c:\salt\srv\salt\win\repo``
``winrepo_dir_ng: /srv/salt/win/repo-ng``   ``winrepo_dir_ng: c:\salt\srv\salt\win\repo-ng``
==========================================  =================================================
