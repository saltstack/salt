.. _configuration-salt-minion:

===========================
Configuring the Salt Minion
===========================

The Salt system is amazingly simple and easy to configure. The two components
of the Salt system each have a respective configuration file. The
:command:`salt-master` is configured via the master configuration file, and the
:command:`salt-minion` is configured via the minion configuration file.

.. seealso::
    :ref:`example minion configuration file <configuration-examples-minion>`

The Salt Minion configuration is very simple. Typically, the only value that
needs to be set is the master value so the minion knows where to locate its master.

By default, the salt-minion configuration will be in :file:`/etc/salt/minion`.
A notable exception is FreeBSD, where the configuration will be in
:file:`/usr/local/etc/salt/minion`.



Minion Primary Configuration
============================

.. conf_minion:: master

``master``
----------

Default: ``salt``

The hostname or IP address of the master. See :conf_minion:`ipv6` for IPv6
connections to the master.

Default: ``salt``

.. code-block:: yaml

    master: salt

master:port Syntax
~~~~~~~~~~~~~~~~~~

.. versionadded:: 2015.8.0

The ``master`` config option can also be set to use the master's IP in
conjunction with a port number by default.

.. code-block:: yaml

    master: localhost:1234

For IPv6 formatting with a port, remember to add brackets around the IP address
before adding the port and enclose the line in single quotes to make it a string:

.. code-block:: yaml

    master: '[2001:db8:85a3:8d3:1319:8a2e:370:7348]:1234'

.. note::

    If a port is specified in the ``master`` as well as :conf_minion:`master_port`,
    the ``master_port`` setting will be overridden by the ``master`` configuration.

List of Masters Syntax
~~~~~~~~~~~~~~~~~~~~~~

The option can also be set to a list of masters, enabling
:ref:`multi-master <tutorial-multi-master>` mode.

.. code-block:: yaml

    master:
      - address1
      - address2

.. versionchanged:: 2014.7.0

    The master can be dynamically configured. The :conf_minion:`master` value
    can be set to an module function which will be executed and will assume
    that the returning value is the ip or hostname of the desired master. If a
    function is being specified, then the :conf_minion:`master_type` option
    must be set to ``func``, to tell the minion that the value is a function to
    be run and not a fully-qualified domain name.

    .. code-block:: yaml

        master: module.function
        master_type: func

    In addition, instead of using multi-master mode, the minion can be
    configured to use the list of master addresses as a failover list, trying
    the first address, then the second, etc. until the minion successfully
    connects. To enable this behavior, set :conf_minion:`master_type` to
    ``failover``:

    .. code-block:: yaml

        master:
          - address1
          - address2
        master_type: failover

.. conf_minion:: ipv6

``ipv6``
--------

Default: ``None``

Whether the master should be connected over IPv6. By default salt minion
will try to automatically detect IPv6 connectivity to master.

.. code-block:: yaml

    ipv6: True

.. conf_minion:: master_uri_format

``master_uri_format``
---------------------

.. versionadded:: 2015.8.0

Specify the format in which the master address will be evaluated. Valid options
are ``default`` or ``ip_only``. If ``ip_only`` is specified, then the master
address will not be split into IP and PORT, so be sure that only an IP (or domain
name) is set in the :conf_minion:`master` configuration setting.

.. code-block:: yaml

    master_uri_format: ip_only

.. conf_minion:: master_tops_first

``master_tops_first``
---------------------

.. versionadded:: 2018.3.0

Default: ``False``

SLS targets defined using the :ref:`Master Tops <master-tops-system>` system
are normally executed *after* any matches defined in the :ref:`Top File
<states-top>`. Set this option to ``True`` to have the minion execute the
:ref:`Master Tops <master-tops-system>` states first.

.. code-block:: yaml

    master_tops_first: True

.. conf_minion:: master_type

``master_type``
---------------

.. versionadded:: 2014.7.0

Default: ``str``

The type of the :conf_minion:`master` variable. Can be ``str``, ``failover``,
``func`` or ``disable``.

.. code-block:: yaml

    master_type: failover

If this option is set to ``failover``, :conf_minion:`master` must be a list of
master addresses. The minion will then try each master in the order specified
in the list until it successfully connects.  :conf_minion:`master_alive_interval`
must also be set, this determines how often the minion will verify the presence
of the master.

.. code-block:: yaml

    master_type: func

If the master needs to be dynamically assigned by executing a function instead
of reading in the static master value, set this to ``func``. This can be used
to manage the minion's master setting from an execution module. By simply
changing the algorithm in the module to return a new master ip/fqdn, restart
the minion and it will connect to the new master.

As of version 2016.11.0 this option can be set to ``disable`` and the minion
will never attempt to talk to the master. This is useful for running a
masterless minion daemon.

.. code-block:: yaml

    master_type: disable

.. conf_minion:: max_event_size

``max_event_size``
------------------

.. versionadded:: 2014.7.0

Default: ``1048576``

Passing very large events can cause the minion to consume large amounts of
memory. This value tunes the maximum size of a message allowed onto the
minion event bus. The value is expressed in bytes.

.. code-block:: yaml

    max_event_size: 1048576

.. conf_minion:: enable_legacy_startup_events

``enable_legacy_startup_events``
--------------------------------

.. versionadded:: 2019.2.0

Default: ``True``

When a minion starts up it sends a notification on the event bus with a tag
that looks like this: ``salt/minion/<minion_id>/start``. For historical reasons
the minion also sends a similar event with an event tag like this:
``minion_start``. This duplication can cause a lot of clutter on the event bus
when there are many minions. Set ``enable_legacy_startup_events: False`` in the
minion config to ensure only the ``salt/minion/<minion_id>/start`` events are
sent. Beginning with the ``Sodium`` Salt release this option will default to
``False``.

.. code-block:: yaml

    enable_legacy_startup_events: True

.. conf_minion:: master_failback

``master_failback``
-------------------

.. versionadded:: 2016.3.0

Default: ``False``

If the minion is in multi-master mode and the :conf_minion`master_type`
configuration option is set to ``failover``, this setting can be set to ``True``
to force the minion to fail back to the first master in the list if the first
master is back online.

.. code-block:: yaml

    master_failback: False

.. conf_minion:: master_failback_interval

``master_failback_interval``
----------------------------

.. versionadded:: 2016.3.0

Default: ``0``

If the minion is in multi-master mode, the :conf_minion`master_type` configuration
is set to ``failover``, and the ``master_failback`` option is enabled, the master
failback interval can be set to ping the top master with this interval, in seconds.

.. code-block:: yaml

    master_failback_interval: 0

.. conf_minion:: master_alive_interval

``master_alive_interval``
-------------------------

Default: ``0``

Configures how often, in seconds, the minion will verify that the current
master is alive and responding.  The minion will try to establish a connection
to the next master in the list if it finds the existing one is dead.

.. code-block:: yaml

    master_alive_interval: 30

.. conf_minion:: master_shuffle

``master_shuffle``
------------------

.. versionadded:: 2014.7.0
.. deprecated:: 2019.2.0

Default: ``False``

.. warning::

    This option has been deprecated in Salt ``2019.2.0``. Please use
    :conf_minion:`random_master` instead.

.. code-block:: yaml

    master_shuffle: True

.. conf_minion:: random_master

``random_master``
-----------------

.. versionadded:: 2014.7.0
.. versionchanged:: 2019.2.0
    The :conf_minion:`master_failback` option can be used in conjunction with
    ``random_master`` to force the minion to fail back to the first master in the
    list if the first master is back online. Note that :conf_minion:`master_type`
    must be set to ``failover`` in order for the ``master_failback`` setting to
    work.

Default: ``False``

If :conf_minion:`master` is a list of addresses, shuffle them before trying to
connect to distribute the minions over all available masters. This uses Python's
:func:`random.shuffle <python2:random.shuffle>` method.

If multiple masters are specified in the 'master' setting as a list, the default
behavior is to always try to connect to them in the order they are listed. If
``random_master`` is set to True, the order will be randomized instead upon Minion
startup. This can be helpful in distributing the load of many minions executing
``salt-call`` requests, for example, from a cron job. If only one master is listed,
this setting is ignored and a warning is logged.

.. code-block:: yaml

    random_master: True

.. note::

    When the ``failover``, ``master_failback``, and ``random_master`` options are
    used together, only the "secondary masters" will be shuffled. The first master
    in the list is ignored in the :func:`random.shuffle <python2:random.shuffle>`
    call. See :conf_minion:`master_failback` for more information.

.. conf_minion:: retry_dns

``retry_dns``
-------------

Default: ``30``

Set the number of seconds to wait before attempting to resolve
the master hostname if name resolution fails. Defaults to 30 seconds.
Set to zero if the minion should shutdown and not retry.

.. code-block:: yaml

    retry_dns: 30

.. conf_minion:: retry_dns_count

``retry_dns_count``
-------------------

.. versionadded:: 2018.3.4

Default: ``None``

Set the number of attempts to perform when resolving
the master hostname if name resolution fails.
By default the minion will retry indefinitely.

.. code-block:: yaml

    retry_dns_count: 3

.. conf_minion:: master_port

``master_port``
---------------

Default: ``4506``

The port of the master ret server, this needs to coincide with the ret_port
option on the Salt master.

.. code-block:: yaml

    master_port: 4506

.. conf_minion:: publish_port

``publish_port``
----------------

Default: ``4505``

The port of the master publish server, this needs to coincide with the publish_port
option on the Salt master.

.. code-block:: yaml

    publish_port: 4505

.. conf_minion:: source_interface_name

``source_interface_name``
-------------------------

.. versionadded:: 2018.3.0

The name of the interface to use when establishing the connection to the Master.

.. note::

    If multiple IP addresses are configured on the named interface,
    the first one will be selected. In that case, for a better selection,
    consider using the :conf_minion:`source_address` option.

.. note::

    To use an IPv6 address from the named interface, make sure the option
    :conf_minion:`ipv6` is enabled, i.e., ``ipv6: true``.

.. note::

    If the interface is down, it will avoid using it, and the Minion
    will bind to ``0.0.0.0`` (all interfaces).

.. warning::

    This option requires modern version of the underlying libraries used by
    the selected transport:

    - ``zeromq`` requires ``pyzmq`` >= 16.0.1 and ``libzmq`` >= 4.1.6
    - ``tcp`` requires ``tornado`` >= 4.5

Configuration example:

.. code-block:: yaml

    source_interface_name: bond0.1234

.. conf_minion:: source_address

``source_address``
------------------

.. versionadded:: 2018.3.0

The source IP address or the domain name to be used when connecting the Minion
to the Master.
See :conf_minion:`ipv6` for IPv6 connections to the Master.

.. warning::

    This option requires modern version of the underlying libraries used by
    the selected transport:

    - ``zeromq`` requires ``pyzmq`` >= 16.0.1 and ``libzmq`` >= 4.1.6
    - ``tcp`` requires ``tornado`` >= 4.5

Configuration example:

.. code-block:: yaml

    source_address: if-bond0-1234.sjc.us-west.internal

.. conf_minion:: source_ret_port

``source_ret_port``
-------------------

.. versionadded:: 2018.3.0

The source port to be used when connecting the Minion to the Master ret server.

.. warning::

    This option requires modern version of the underlying libraries used by
    the selected transport:

    - ``zeromq`` requires ``pyzmq`` >= 16.0.1 and ``libzmq`` >= 4.1.6
    - ``tcp`` requires ``tornado`` >= 4.5

Configuration example:

.. code-block:: yaml

    source_ret_port: 49017

.. conf_minion:: source_publish_port

``source_publish_port``
-----------------------

.. versionadded:: 2018.3.0

The source port to be used when connecting the Minion to the Master publish
server.

.. warning::

    This option requires modern version of the underlying libraries used by
    the selected transport:

    - ``zeromq`` requires ``pyzmq`` >= 16.0.1 and ``libzmq`` >= 4.1.6
    - ``tcp`` requires ``tornado`` >= 4.5

Configuration example:

.. code-block:: yaml

    source_publish_port: 49018

.. conf_minion:: user

``user``
--------

Default: ``root``

The user to run the Salt processes

.. code-block:: yaml

    user: root

.. conf_minion:: sudo_user

``sudo_user``
-------------

Default: ``''``

The user to run salt remote execution commands as via sudo. If this option is
enabled then sudo will be used to change the active user executing the remote
command. If enabled the user will need to be allowed access via the sudoers file
for the user that the salt minion is configured to run as. The most common
option would be to use the root user. If this option is set the ``user`` option
should also be set to a non-root user. If migrating from a root minion to a non
root minion the minion cache should be cleared and the minion pki directory will
need to be changed to the ownership of the new user.

.. code-block:: yaml

    sudo_user: root


``pidfile``
-----------

Default: ``/var/run/salt-minion.pid``

The location of the daemon's process ID file

.. code-block:: yaml

    pidfile: /var/run/salt-minion.pid

.. conf_minion:: root_dir

``root_dir``
------------

Default: ``/``

This directory is prepended to the following options: :conf_minion:`pki_dir`,
:conf_minion:`cachedir`, :conf_minion:`log_file`, :conf_minion:`sock_dir`, and
:conf_minion:`pidfile`.

.. code-block:: yaml

    root_dir: /

.. conf_minion:: conf_file

``conf_file``
-------------

Default: ``/etc/salt/minion``

The path to the minion's configuration file.

.. code-block:: yaml

    conf_file: /etc/salt/minion

.. conf_minion:: pki_dir

``pki_dir``
-----------

Default: ``/etc/salt/pki/minion``

The directory used to store the minion's public and private keys.

.. code-block:: yaml

    pki_dir: /etc/salt/pki/minion

.. conf_minion:: id

``id``
------

Default: the system's hostname

.. seealso:: :ref:`Salt Walkthrough <minion-id-generation>`

    The :strong:`Setting up a Salt Minion` section contains detailed
    information on how the hostname is determined.

Explicitly declare the id for this minion to use. Since Salt uses detached ids
it is possible to run multiple minions on the same machine but with different
ids.

.. code-block:: yaml

    id: foo.bar.com

.. conf_minion:: minion_id_caching

``minion_id_caching``
---------------------

.. versionadded:: 0.17.2

Default: ``True``

Caches the minion id to a file when the minion's :conf_minion:`id` is not
statically defined in the minion config. This setting prevents potential
problems when automatic minion id resolution changes, which can cause the
minion to lose connection with the master. To turn off minion id caching,
set this config to ``False``.

For more information, please see `Issue #7558`_ and `Pull Request #8488`_.

.. code-block:: yaml

    minion_id_caching: True

.. _Issue #7558: https://github.com/saltstack/salt/issues/7558
.. _Pull Request #8488: https://github.com/saltstack/salt/pull/8488

.. conf_minion:: append_domain

``append_domain``
-----------------

Default: ``None``

Append a domain to a hostname in the event that it does not exist. This is
useful for systems where ``socket.getfqdn()`` does not actually result in a
FQDN (for instance, Solaris).

.. code-block:: yaml

    append_domain: foo.org

.. conf_minion:: minion_id_remove_domain

``minion_id_remove_domain``
---------------------------

.. versionadded:: Neon

Default: ``False``

Remove a domain when the minion id is generated as a fully qualified domain
name (either by the user provided ``id_function``, or by Salt). This is useful
when the minions shall be named like hostnames. Can be a single domain (to
prevent name clashes), or True, to remove all domains.

Examples:
 - minion_id_remove_domain = foo.org
   - FQDN = king_bob.foo.org --> minion_id = king_bob
   - FQDN = king_bob.bar.org --> minion_id = king_bob.bar.org
 - minion_id_remove_domain = True
   - FQDN = king_bob.foo.org --> minion_id = king_bob
   - FQDN = king_bob.bar.org --> minion_id = king_bob


For more information, please see :issue:`49212` and  :pull:`49378`.

.. code-block:: yaml

    minion_id_remove_domain: foo.org

.. conf_minion:: minion_id_lowercase

``minion_id_lowercase``
-----------------------

Default: ``False``

Convert minion id to lowercase when it is being generated. Helpful when some hosts
get the minion id in uppercase. Cached ids will remain the same and not converted.

.. code-block:: yaml

    minion_id_lowercase: True

.. conf_minion:: cachedir

``cachedir``
------------

Default: ``/var/cache/salt/minion``

The location for minion cache data.

This directory may contain sensitive data and should be protected accordingly.

.. code-block:: yaml

    cachedir: /var/cache/salt/minion

.. conf_master:: color_theme

``color_theme``
---------------

Default: ``""``

Specifies a path to the color theme to use for colored command line output.

.. code-block:: yaml

    color_theme: /etc/salt/color_theme

.. conf_minion:: append_minionid_config_dirs

``append_minionid_config_dirs``
-------------------------------

Default: ``[]`` (the empty list) for regular minions, ``['cachedir']`` for proxy minions.

Append minion_id to these configuration directories.  Helps with multiple proxies
and minions running on the same machine. Allowed elements in the list:
``pki_dir``, ``cachedir``, ``extension_modules``.
Normally not needed unless running several proxies and/or minions on the same machine.

.. code-block:: yaml

    append_minionid_config_dirs:
      - pki_dir
      - cachedir


``verify_env``
--------------

Default: ``True``

Verify and set permissions on configuration directories at startup.

.. code-block:: yaml

    verify_env: True

.. note::

    When set to ``True`` the verify_env option requires WRITE access to the
    configuration directory (/etc/salt/). In certain situations such as
    mounting /etc/salt/ as read-only for templating this will create a stack
    trace when :py:func:`state.apply <salt.modules.state.apply_>` is called.

.. conf_minion:: cache_jobs

``cache_jobs``
--------------

Default: ``False``

The minion can locally cache the return data from jobs sent to it, this can be
a good way to keep track of the minion side of the jobs the minion has
executed. By default this feature is disabled, to enable set cache_jobs to
``True``.

.. code-block:: yaml

    cache_jobs: False

.. conf_minion:: grains

``grains``
----------

Default: (empty)

.. seealso::
    :ref:`static-custom-grains`

Statically assigns grains to the minion.

.. code-block:: yaml

    grains:
      roles:
        - webserver
        - memcache
      deployment: datacenter4
      cabinet: 13
      cab_u: 14-15

.. conf_minion:: grains_blacklist

``grains_blacklist``
--------------------

Default: ``[]``

Each grains key will be compared against each of the expressions in this list.
Any keys which match will be filtered from the grains. Exact matches, glob
matches, and regular expressions are supported.

.. note::
    Some states and execution modules depend on grains. Filtering may cause
    them to be unavailable or run unreliably.

.. versionadded:: Neon

.. code-block:: yaml

    grains_blacklist:
      - cpu_flags
      - zmq*
      - ipv[46]

.. conf_minion:: grains_cache

``grains_cache``
----------------

Default: ``False``

The minion can locally cache grain data instead of refreshing the data
each time the grain is referenced. By default this feature is disabled,
to enable set grains_cache to ``True``.

.. code-block:: yaml

    grains_cache: False

.. conf_minion:: grains_deep_merge

``grains_deep_merge``
---------------------

.. versionadded:: 2016.3.0

Default: ``False``

The grains can be merged, instead of overridden, using this option.
This allows custom grains to defined different subvalues of a dictionary
grain. By default this feature is disabled, to enable set grains_deep_merge
to ``True``.

.. code-block:: yaml

    grains_deep_merge: False

For example, with these custom grains functions:

.. code-block:: python

    def custom1_k1():
        return {'custom1': {'k1': 'v1'}}

    def custom1_k2():
        return {'custom1': {'k2': 'v2'}}

Without ``grains_deep_merge``, the result would be:

.. code-block:: yaml

    custom1:
      k1: v1

With ``grains_deep_merge``, the result will be:

.. code-block:: yaml

    custom1:
      k1: v1
      k2: v2

.. conf_minion:: grains_refresh_every

``grains_refresh_every``
------------------------

Default: ``0``

The ``grains_refresh_every`` setting allows for a minion to periodically
check its grains to see if they have changed and, if so, to inform the master
of the new grains. This operation is moderately expensive, therefore care
should be taken not to set this value too low.

Note: This value is expressed in minutes.

A value of 10 minutes is a reasonable default.

.. code-block:: yaml

    grains_refresh_every: 0

.. conf_minion:: metadata_server_grains

``metadata_server_grains``
--------------------------

.. versionadded:: 2017.7.0

Default: ``False``

Set this option to enable gathering of cloud metadata from
``http://169.254.169.254/latest`` for use in grains (see :py:mod:`here
<salt.grains.metadata>` for more information).

.. code-block:: yaml

    metadata_server_grains: True

.. conf_minion:: fibre_channel_grains

``fibre_channel_grains``
------------------------

Default: ``False``

The ``fibre_channel_grains`` setting will enable the ``fc_wwn`` grain for
Fibre Channel WWN's on the minion. Since this grain is expensive, it is
disabled by default.

.. code-block:: yaml

    fibre_channel_grains: True

.. conf_minion:: iscsi_grains

``iscsi_grains``
------------------------

Default: ``False``

The ``iscsi_grains`` setting will enable the ``iscsi_iqn`` grain on the
minion. Since this grain is expensive, it is disabled by default.

.. code-block:: yaml

    iscsi_grains: True

.. conf_minion:: nvme_grains

``nvme_grains``
------------------------

Default: ``False``

The ``nvme_grains`` setting will enable the ``nvme_nqn`` grain on the
minion. Since this grain is expensive, it is disabled by default.

.. code-block:: yaml

    nvme_grains: True

.. conf_minion:: mine_enabled

``mine_enabled``
----------------

.. versionadded:: 2015.8.10

Default: ``True``

Determines whether or not the salt minion should run scheduled mine updates.  If this is set to
False then the mine update function will not get added to the scheduler for the minion.

.. code-block:: yaml

    mine_enabled: True

.. conf_minion:: mine_return_job

``mine_return_job``
-------------------

.. versionadded:: 2015.8.10

Default: ``False``

Determines whether or not scheduled mine updates should be accompanied by a job
return for the job cache.

.. code-block:: yaml

    mine_return_job: False

``mine_functions``
------------------

Default: Empty

Designate which functions should be executed at mine_interval intervals on each minion.
:ref:`See this documentation on the Salt Mine <salt-mine>` for more information.
Note these can be defined in the pillar for a minion as well.

    :ref:`example minion configuration file <configuration-examples-minion>`

.. code-block:: yaml

    mine_functions:
      test.ping: []
      network.ip_addrs:
        interface: eth0
        cidr: '10.0.0.0/8'

.. conf_minion:: mine_interval

``mine_interval``
-----------------

Default: ``60``

The number of minutes between mine updates.

.. code-block:: yaml

    mine_interval: 60

.. conf_minion:: sock_dir

``sock_dir``
------------

Default: ``/var/run/salt/minion``

The directory where Unix sockets will be kept.

.. code-block:: yaml

    sock_dir: /var/run/salt/minion

.. conf_minion:: enable_gpu_grains

``enable_gpu_grains``
---------------------

Default: ``True``

Enable GPU hardware data for your master. Be aware that the minion can
take a while to start up when lspci and/or dmidecode is used to populate the
grains for the minion, so this can be set to ``False`` if you do not need these
grains.

.. code-block:: yaml

    enable_gpu_grains: False

.. conf_minion:: outputter_dirs

``outputter_dirs``
------------------

Default: ``[]``

A list of additional directories to search for salt outputters in.

.. code-block:: yaml

    outputter_dirs: []

.. conf_minion:: backup_mode

``backup_mode``
---------------

Default: ``''``

Make backups of files replaced by ``file.managed`` and ``file.recurse`` state modules under
:conf_minion:`cachedir` in ``file_backup`` subdirectory preserving original paths.
Refer to :ref:`File State Backups documentation <file-state-backups>` for more details.

.. code-block:: yaml

    backup_mode: minion

.. conf_minion:: acceptance_wait_time

``acceptance_wait_time``
------------------------

Default: ``10``

The number of seconds to wait until attempting to re-authenticate with the
master.

.. code-block:: yaml

    acceptance_wait_time: 10

.. conf_minion:: acceptance_wait_time_max

``acceptance_wait_time_max``
----------------------------

Default: ``0``

The maximum number of seconds to wait until attempting to re-authenticate
with the master. If set, the wait will increase by :conf_minion:`acceptance_wait_time`
seconds each iteration.

.. code-block:: yaml

    acceptance_wait_time_max: 0

.. conf_minion:: rejected_retry

``rejected_retry``
------------------

Default: ``False``

If the master rejects the minion's public key, retry instead of exiting.
Rejected keys will be handled the same as waiting on acceptance.

.. code-block:: yaml

    rejected_retry: False

.. conf_minion:: random_reauth_delay

``random_reauth_delay``
-----------------------

Default: ``10``

When the master key changes, the minion will try to re-auth itself to
receive the new master key. In larger environments this can cause a syn-flood
on the master because all minions try to re-auth immediately. To prevent this
and have a minion wait for a random amount of time, use this optional
parameter. The wait-time will be a random number of seconds between
0 and the defined value.

.. code-block:: yaml

    random_reauth_delay: 60

.. conf_minion:: master_tries

``master_tries``
----------------

.. versionadded:: 2016.3.0

Default: ``1``

The number of attempts to connect to a master before giving up. Set this to
``-1`` for unlimited attempts. This allows for a master to have downtime and the
minion to reconnect to it later when it comes back up. In 'failover' mode, which
is set in the :conf_minion:`master_type` configuration, this value is the number
of attempts for each set of masters. In this mode, it will cycle through the list
of masters for each attempt.

``master_tries`` is different than :conf_minion:`auth_tries` because ``auth_tries``
attempts to retry auth attempts with a single master. ``auth_tries`` is under the
assumption that you can connect to the master but not gain authorization from it.
``master_tries`` will still cycle through all of the masters in a given try, so it
is appropriate if you expect occasional downtime from the master(s).

.. code-block:: yaml

    master_tries: 1

.. conf_minion:: auth_tries

``auth_tries``
--------------

.. versionadded:: 2014.7.0

Default: ``7``

The number of attempts to authenticate to a master before giving up. Or, more
technically, the number of consecutive SaltReqTimeoutErrors that are acceptable
when trying to authenticate to the master.

.. code-block:: yaml

    auth_tries: 7

.. conf_minion:: auth_timeout

``auth_timeout``
----------------

.. versionadded:: 2014.7.0

Default: ``60``

When waiting for a master to accept the minion's public key, salt will
continuously attempt to reconnect until successful. This is the timeout value,
in seconds, for each individual attempt. After this timeout expires, the minion
will wait for :conf_minion:`acceptance_wait_time` seconds before trying again.
Unless your master is under unusually heavy load, this should be left at the
default.

.. code-block:: yaml

    auth_timeout: 60

.. conf_minion:: auth_safemode

``auth_safemode``
-----------------

.. versionadded:: 2014.7.0

Default: ``False``

If authentication fails due to SaltReqTimeoutError during a ping_interval,
this setting, when set to ``True``, will cause a sub-minion process to
restart.

.. code-block:: yaml

    auth_safemode: False

.. conf_minion:: ping_interval

``ping_interval``
-----------------

Default: ``0``

Instructs the minion to ping its master(s) every n number of minutes. Used
primarily as a mitigation technique against minion disconnects.

.. code-block:: yaml

    ping_interval: 0

.. conf_minion:: recon_default

``random_startup_delay``
------------------------

Default: ``0``

The maximum bound for an interval in which a minion will randomly sleep upon starting
up prior to attempting to connect to a master. This can be used to splay connection attempts
for cases where many minions starting up at once may place undue load on a master.

For example, setting this to ``5`` will tell a minion to sleep for a value between ``0``
and ``5`` seconds.

.. code-block:: yaml

    random_startup_delay: 5

.. conf_minion:: random_startup_delay

``recon_default``
-----------------

Default: ``1000``

The interval in milliseconds that the socket should wait before trying to
reconnect to the master (1000ms = 1 second).

.. code-block:: yaml

    recon_default: 1000

.. conf_minion:: recon_max

``recon_max``
-------------

Default: ``10000``

The maximum time a socket should wait. Each interval the time to wait is calculated
by doubling the previous time. If recon_max is reached, it starts again at
the recon_default.

Short example:
    - reconnect 1: the socket will wait 'recon_default' milliseconds
    - reconnect 2: 'recon_default' * 2
    - reconnect 3: ('recon_default' * 2) * 2
    - reconnect 4: value from previous interval * 2
    - reconnect 5: value from previous interval * 2
    - reconnect x: if value >= recon_max, it starts again with recon_default

.. code-block:: yaml

    recon_max: 10000

.. conf_minion:: recon_randomize

``recon_randomize``
-------------------

Default: ``True``

Generate a random wait time on minion start. The wait time will be a random value
between recon_default and recon_default + recon_max. Having all minions reconnect
with the same recon_default and recon_max value kind of defeats the purpose of being
able to change these settings. If all minions have the same values and the setup is
quite large (several thousand minions), they will still flood the master. The desired
behavior is to have time-frame within all minions try to reconnect.

.. code-block:: yaml

    recon_randomize: True

.. conf_minion:: loop_interval

``loop_interval``
-----------------

Default: ``1``

The loop_interval sets how long in seconds the minion will wait between
evaluating the scheduler and running cleanup tasks. This defaults to 1
second on the minion scheduler.

.. code-block:: yaml

    loop_interval: 1


.. conf_minion:: pub_ret

``pub_ret``
-----------

Default: True

Some installations choose to start all job returns in a cache or a returner
and forgo sending the results back to a master. In this workflow, jobs
are most often executed with --async from the Salt CLI and then results
are evaluated by examining job caches on the minions or any configured returners.
WARNING: Setting this to False will **disable** returns back to the master.

.. code-block:: yaml

    pub_ret: True

.. conf_minion:: return_retry_timer

``return_retry_timer``
----------------------

Default: ``5``

The default timeout for a minion return attempt.

.. code-block:: yaml

    return_retry_timer: 5


.. conf_minion:: return_retry_timer_max

``return_retry_timer_max``
--------------------------

Default: ``10``

The maximum timeout for a minion return attempt. If non-zero the minion return
retry timeout will be a random int between ``return_retry_timer`` and
``return_retry_timer_max``

.. code-block:: yaml

    return_retry_timer_max: 10

.. conf_minion:: cache_sreqs

``cache_sreqs``
---------------

Default: ``True``

The connection to the master ret_port is kept open. When set to False, the minion
creates a new connection for every return to the master.

.. code-block:: yaml

    cache_sreqs: True

.. conf_minion:: ipc_mode

``ipc_mode``
------------

Default: ``ipc``

Windows platforms lack POSIX IPC and must rely on slower TCP based inter-
process communications. ``ipc_mode`` is set to ``tcp`` on such systems.

.. code-block:: yaml

    ipc_mode: ipc

.. conf_minion:: tcp_pub_port

``tcp_pub_port``
----------------

Default: ``4510``

Publish port used when :conf_minion:`ipc_mode` is set to ``tcp``.

.. code-block:: yaml

    tcp_pub_port: 4510

.. conf_minion:: tcp_pull_port

``tcp_pull_port``
-----------------

Default: ``4511``

Pull port used when :conf_minion:`ipc_mode` is set to ``tcp``.

.. code-block:: yaml

    tcp_pull_port: 4511

.. conf_minion:: transport

``transport``
-------------

Default: ``zeromq``

Changes the underlying transport layer. ZeroMQ is the recommended transport
while additional transport layers are under development. Supported values are
``zeromq`` and ``tcp`` (experimental). This setting has a significant impact
on performance and should not be changed unless you know what you are doing!

.. code-block:: yaml

    transport: zeromq

.. conf_minion:: syndic_finger

``syndic_finger``
-----------------

Default: ``''``

The key fingerprint of the higher-level master for the syndic to verify it is
talking to the intended master.

.. code-block:: yaml

    syndic_finger: 'ab:30:65:2a:d6:9e:20:4f:d8:b2:f3:a7:d4:65:50:10'

.. conf_minion:: http_connect_timeout

``http_connect_timeout``
------------------------

.. versionadded:: 2019.2.0

Default: ``20``

HTTP connection timeout in seconds.
Applied when fetching files using tornado back-end.
Should be greater than overall download time.

.. code-block:: yaml

    http_connect_timeout: 20

.. conf_minion:: http_request_timeout

``http_request_timeout``
------------------------

.. versionadded:: 2015.8.0

Default: ``3600``

HTTP request timeout in seconds.
Applied when fetching files using tornado back-end.
Should be greater than overall download time.

.. code-block:: yaml

    http_request_timeout: 3600

.. conf_minion:: proxy_host

``proxy_host``
--------------

Default: ``''``

The hostname used for HTTP proxy access.

.. code-block:: yaml

    proxy_host: proxy.my-domain

.. conf_minion:: proxy_port

``proxy_port``
--------------

Default: ``0``

The port number used for HTTP proxy access.

.. code-block:: yaml

    proxy_port: 31337

.. conf_minion:: proxy_username

``proxy_username``
------------------

Default: ``''``

The username used for HTTP proxy access.

.. code-block:: yaml

    proxy_username: charon

.. conf_minion:: proxy_password

``proxy_password``
------------------

Default: ``''``

The password used for HTTP proxy access.

.. code-block:: yaml

    proxy_password: obolus

.. conf_minion:: no_proxy

``no_proxy``
------------

.. versionadded:: 2019.2.0

Default: ``[]``

List of hosts to bypass HTTP proxy

.. note::
    This key does nothing unless proxy_host etc is configured, it does not
    support any kind of wildcards.

.. code-block:: yaml

    no_proxy: [ '127.0.0.1', 'foo.tld' ]

``use_yamlloader_old``
------------------------

.. versionadded:: 2019.2.1

Default: ``False``

Use the pre-2019.2 YAML renderer.
Uses legacy YAML rendering to support some legacy inline data structures.
See the :ref:`2019.2.1 release notes <release-2019-2-1>` for more details.

.. code-block:: yaml

    use_yamlloader_old: False

Docker Configuration
====================

.. conf_minion:: docker.update_mine

``docker.update_mine``
----------------------

.. versionadded:: 2017.7.8,2018.3.3
.. versionchanged:: 2019.2.0
    The default value is now ``False``

Default: ``True``

If enabled, when containers are added, removed, stopped, started, etc., the
:ref:`mine <salt-mine>` will be updated with the results of :py:func:`docker.ps
verbose=True all=True host=True <salt.modules.dockermod.ps>`. This mine data is
used by :py:func:`mine.get_docker <salt.modules.mine.get_docker>`. Set this
option to ``False`` to keep Salt from updating the mine with this information.

.. note::
    This option can also be set in Grains or Pillar data, with Grains
    overriding Pillar and the minion config file overriding Grains.

.. note::
    Disabling this will of course keep :py:func:`mine.get_docker
    <salt.modules.mine.get_docker>` from returning any information for a given
    minion.

.. code-block:: yaml

    docker.update_mine: False

.. conf_minion:: docker.compare_container_networks

``docker.compare_container_networks``
-------------------------------------

.. versionadded:: 2018.3.0

Default: ``{'static': ['Aliases', 'Links', 'IPAMConfig'], 'automatic': ['IPAddress', 'Gateway', 'GlobalIPv6Address', 'IPv6Gateway']}``

Specifies which keys are examined by
:py:func:`docker.compare_container_networks
<salt.modules.dockermod.compare_container_networks>`.

.. note::
    This should not need to be modified unless new features added to Docker
    result in new keys added to the network configuration which must be
    compared to determine if two containers have different network configs.
    This config option exists solely as a way to allow users to continue using
    Salt to manage their containers after an API change, without waiting for a
    new Salt release to catch up to the changes in the Docker API.

.. code-block:: yaml

    docker.compare_container_networks:
      static:
        - Aliases
        - Links
        - IPAMConfig
      automatic:
        - IPAddress
        - Gateway
        - GlobalIPv6Address
        - IPv6Gateway

.. conf_minion:: optimization_order

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

Minion Execution Module Management
==================================

.. conf_minion:: disable_modules

``disable_modules``
-------------------

Default: ``[]`` (all execution modules are enabled by default)

The event may occur in which the administrator desires that a minion should not
be able to execute a certain module.

However, the ``sys`` module is built into the minion and cannot be disabled.

This setting can also tune the minion. Because all modules are loaded into system
memory, disabling modules will lower the minion's memory footprint.

Modules should be specified according to their file name on the system and not by
their virtual name. For example, to disable ``cmd``, use the string ``cmdmod`` which
corresponds to ``salt.modules.cmdmod``.

.. code-block:: yaml

    disable_modules:
      - test
      - solr

.. conf_minion:: disable_returners

``disable_returners``
---------------------

Default: ``[]`` (all returners are enabled by default)

If certain returners should be disabled, this is the place

.. code-block:: yaml

    disable_returners:
      - mongo_return


.. conf_minion:: enable_whitelist_modules

``whitelist_modules``
---------------------

Default: ``[]`` (Module whitelisting is disabled.  Adding anything to the config option
will cause only the listed modules to be enabled.  Modules not in the list will
not be loaded.)

This option is the reverse of disable_modules. If enabled, only execution modules in this
list will be loaded and executed on the minion.

Note that this is a very large hammer and it can be quite difficult to keep the minion working
the way you think it should since Salt uses many modules internally itself.  At a bare minimum
you need the following enabled or else the minion won't start.

.. code-block:: yaml

    whitelist_modules:
      - cmdmod
      - test
      - config


.. conf_minion:: module_dirs

``module_dirs``
---------------

Default: ``[]``

A list of extra directories to search for Salt modules

.. code-block:: yaml

    module_dirs:
      - /var/lib/salt/modules

.. conf_minion:: returner_dirs

``returner_dirs``
-----------------

Default: ``[]``

A list of extra directories to search for Salt returners

.. code-block:: yaml

    returner_dirs:
      - /var/lib/salt/returners

.. conf_minion:: states_dirs

``states_dirs``
---------------

Default: ``[]``

A list of extra directories to search for Salt states

.. code-block:: yaml

    states_dirs:
      - /var/lib/salt/states


.. conf_minion:: grains_dirs

``grains_dirs``
---------------

Default: ``[]``

A list of extra directories to search for Salt grains

.. code-block:: yaml

    grains_dirs:
      - /var/lib/salt/grains


.. conf_minion:: render_dirs

``render_dirs``
---------------

Default: ``[]``

A list of extra directories to search for Salt renderers

.. code-block:: yaml

    render_dirs:
      - /var/lib/salt/renderers

.. conf_minion:: utils_dirs

``utils_dirs``
--------------

Default: ``[]``

A list of extra directories to search for Salt utilities

.. code-block:: yaml

    utils_dirs:
      - /var/lib/salt/utils

.. conf_minion:: cython_enable

``cython_enable``
-----------------

Default: ``False``

Set this value to true to enable auto-loading and compiling of ``.pyx`` modules,
This setting requires that ``gcc`` and ``cython`` are installed on the minion.

.. code-block:: yaml

    cython_enable: False

.. conf_minion:: enable_zip_modules

``enable_zip_modules``
----------------------

.. versionadded:: 2015.8.0

Default: ``False``

Set this value to true to enable loading of zip archives as extension modules.
This allows for packing module code with specific dependencies to avoid conflicts
and/or having to install specific modules' dependencies in system libraries.

.. code-block:: yaml

    enable_zip_modules: False

.. conf_minion:: providers

``providers``
-------------

Default: (empty)

A module provider can be statically overwritten or extended for the minion via
the ``providers`` option. This can be done :ref:`on an individual basis in an
SLS file <state-providers>`, or globally here in the minion config, like
below.

.. code-block:: yaml

    providers:
      service: systemd

.. conf_minion:: modules_max_memory

``modules_max_memory``
----------------------

Default: ``-1``

Specify a max size (in bytes) for modules on import. This feature is currently
only supported on \*NIX operating systems and requires psutil.

.. code-block:: yaml

    modules_max_memory: -1

.. conf_minion:: extmod_whitelist
.. conf_minion:: extmod_blacklist

``extmod_whitelist/extmod_blacklist``
-------------------------------------

.. versionadded:: 2017.7.0

By using this dictionary, the modules that are synced to the minion's extmod cache using `saltutil.sync_*` can be
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

  - beacons
  - clouds
  - sdb
  - modules
  - states
  - grains
  - renderers
  - returners
  - proxy
  - engines
  - output
  - utils
  - pillar


Top File Settings
=================

These parameters only have an effect if running a masterless minion.

.. conf_minion:: state_top

``state_top``
-------------

Default: ``top.sls``

The state system uses a "top" file to tell the minions what environment to
use and what modules to use. The state_top file is defined relative to the
root of the base environment.

.. code-block:: yaml

    state_top: top.sls

.. conf_minion:: state_top_saltenv

``state_top_saltenv``
---------------------

This option has no default value. Set it to an environment name to ensure that
*only* the top file from that environment is considered during a
:ref:`highstate <running-highstate>`.

.. note::
    Using this value does not change the merging strategy. For instance, if
    :conf_minion:`top_file_merging_strategy` is set to ``merge``, and
    :conf_minion:`state_top_saltenv` is set to ``foo``, then any sections for
    environments other than ``foo`` in the top file for the ``foo`` environment
    will be ignored. With :conf_minion:`state_top_saltenv` set to ``base``, all
    states from all environments in the ``base`` top file will be applied,
    while all other top files are ignored. The only way to set
    :conf_minion:`state_top_saltenv` to something other than ``base`` and not
    have the other environments in the targeted top file ignored, would be to
    set :conf_minion:`top_file_merging_strategy` to ``merge_all``.

.. code-block:: yaml

    state_top_saltenv: dev

.. conf_minion:: top_file_merging_strategy

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
environments are evaluated, use :conf_minion:`env_order`. Note that, aside from
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
file, then the top file from the :conf_minion:`default_top` config parameter
will be used as a fallback.

When set to ``merge_all``, then all states in all environments in all top files
will be applied. The order in which individual SLS files will be executed will
depend on the order in which the top files were evaluated, and the environments
will be evaluated in no specific order. For greater control over the order in
which the environments are evaluated, use :conf_minion:`env_order`.

.. code-block:: yaml

    top_file_merging_strategy: same

.. conf_minion:: env_order

``env_order``
-------------

Default: ``[]``

When :conf_minion:`top_file_merging_strategy` is set to ``merge``, and no
environment is specified for a :ref:`highstate <running-highstate>`, this
config option allows for the order in which top files are evaluated to be
explicitly defined.

.. code-block:: yaml

    env_order:
      - base
      - dev
      - qa

.. conf_minion:: default_top

``default_top``
---------------

Default: ``base``

When :conf_minion:`top_file_merging_strategy` is set to ``same``, and no
environment is specified for a :ref:`highstate <running-highstate>` (i.e.
:conf_minion:`environment` is not set for the minion), this config option
specifies a fallback environment in which to look for a top file if an
environment lacks one.

.. code-block:: yaml

    default_top: dev

.. conf_minion:: startup_states

``startup_states``
------------------

Default: ``''``

States to run when the minion daemon starts. To enable, set ``startup_states`` to:

- ``highstate``: Execute state.highstate
- ``sls``: Read in the sls_list option and execute the named sls files
- ``top``: Read top_file option and execute based on that file on the Master

.. code-block:: yaml

    startup_states: ''

.. conf_minion:: sls_list

``sls_list``
------------

Default: ``[]``

List of states to run when the minion starts up if ``startup_states`` is set to ``sls``.

.. code-block:: yaml

    sls_list:
      - edit.vim
      - hyper

.. conf_minion:: top_file

``top_file``
------------

Default: ``''``

Top file to execute if ``startup_states`` is set to ``top``.

.. code-block:: yaml

    top_file: ''


State Management Settings
=========================

.. conf_minion:: renderer

``renderer``
------------

Default: ``jinja|yaml``

The default renderer used for local state executions

.. code-block:: yaml

    renderer: jinja|json

.. conf_minion:: test

``test``
--------

Default: ``False``

Set all state calls to only test if they are going to actually make changes
or just post what changes are going to be made.

.. code-block:: yaml

    test: False

.. conf_minion:: state_verbose

``state_verbose``
-----------------

Default: ``True``

Controls the verbosity of state runs. By default, the results of all states are
returned, but setting this value to ``False`` will cause salt to only display
output for states that failed or states that have changes.

.. code-block:: yaml

    state_verbose: True

.. conf_minion:: state_output

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

.. conf_minion:: state_output_diff

``state_output_diff``
---------------------

Default: ``False``

The state_output_diff setting changes whether or not the output from
successful states is returned. Useful when even the terse output of these
states is cluttering the logs. Set it to True to ignore them.

.. code-block:: yaml

    state_output_diff: False

.. conf_minion:: autoload_dynamic_modules

``autoload_dynamic_modules``
----------------------------

Default: ``True``

autoload_dynamic_modules turns on automatic loading of modules found in the
environments on the master. This is turned on by default. To turn off
auto-loading modules when states run, set this value to ``False``.

.. code-block:: yaml

    autoload_dynamic_modules: True

.. conf_minion:: clean_dynamic_modules

Default: ``True``

clean_dynamic_modules keeps the dynamic modules on the minion in sync with
the dynamic modules on the master. This means that if a dynamic module is
not on the master it will be deleted from the minion. By default this is
enabled and can be disabled by changing this value to ``False``.

.. code-block:: yaml

    clean_dynamic_modules: True

.. note::

    If ``extmod_whitelist`` is specified, modules which are not whitelisted will also be cleaned here.

.. conf_minion:: environment
.. conf_minion:: saltenv

``saltenv``
-----------

.. versionchanged:: 2018.3.0
    Renamed from ``environment`` to ``saltenv``. If ``environment`` is used,
    ``saltenv`` will take its value. If both are used, ``environment`` will be
    ignored and ``saltenv`` will be used.

Normally the minion is not isolated to any single environment on the master
when running states, but the environment can be isolated on the minion side
by statically setting it. Remember that the recommended way to manage
environments is to isolate via the top file.

.. code-block:: yaml

    saltenv: dev

.. conf_minion:: lock_saltenv

``lock_saltenv``
----------------

.. versionadded:: 2018.3.0

Default: ``False``

For purposes of running states, this option prevents using the ``saltenv``
argument to manually set the environment. This is useful to keep a minion which
has the :conf_minion:`saltenv` option set to ``dev`` from running states from
an environment other than ``dev``.

.. code-block:: yaml

    lock_saltenv: True

.. conf_minion:: snapper_states

``snapper_states``
------------------

Default: False

The `snapper_states` value is used to enable taking snapper snapshots before
and after salt state runs. This allows for state runs to be rolled back.

For snapper states to function properly snapper needs to be installed and
enabled.

.. code-block:: yaml

    snapper_states: True

.. conf_minion:: snapper_states_config

``snapper_states_config``
-------------------------

Default: ``root``

Snapper can execute based on a snapper configuration. The configuration
needs to be set up before snapper can use it. The default configuration
is ``root``, this default makes snapper run on SUSE systems using the
default configuration set up at install time.

.. code-block:: yaml

    snapper_states_config: root

File Directory Settings
=======================

.. conf_minion:: file_client

``file_client``
---------------

Default: ``remote``

The client defaults to looking on the master server for files, but can be
directed to look on the minion by setting this parameter to ``local``.

.. code-block:: yaml

    file_client: remote

.. conf_minion:: use_master_when_local

``use_master_when_local``
-------------------------

Default: ``False``

When using a local :conf_minion:`file_client`, this parameter is used to allow
the client to connect to a master for remote execution.

.. code-block:: yaml

    use_master_when_local: False

.. conf_minion:: file_roots

``file_roots``
--------------

Default:

.. code-block:: yaml

    base:
      - /srv/salt

When using a local :conf_minion:`file_client`, this parameter is used to setup
the fileserver's environments. This parameter operates identically to the
:conf_master:`master config parameter <file_roots>` of the same name.

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

.. conf_minion:: fileserver_followsymlinks

``fileserver_followsymlinks``
-----------------------------

.. versionadded:: 2014.1.0

Default: ``True``

By default, the file_server follows symlinks when walking the filesystem tree.
Currently this only applies to the default roots fileserver_backend.

.. code-block:: yaml

    fileserver_followsymlinks: True

.. conf_minion:: fileserver_ignoresymlinks

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

.. conf_minion:: fileserver_limit_traversal

``fileserver_limit_traversal``
------------------------------

.. versionadded:: 2014.1.0

Default: ``False``

By default, the Salt fileserver recurses fully into all defined environments
to attempt to find files. To limit this behavior so that the fileserver only
traverses directories with SLS files and special Salt directories like _modules,
set ``fileserver_limit_traversal`` to ``True``. This might be useful for
installations where a file root has a very large number of files and performance
is impacted.

.. code-block:: yaml

    fileserver_limit_traversal: False

.. conf_minion:: hash_type

``hash_type``
-------------

Default: ``sha256``

The hash_type is the hash to use when discovering the hash of a file on the
local fileserver. The default is sha256, but md5, sha1, sha224, sha384, and
sha512 are also supported.

.. code-block:: yaml

    hash_type: sha256


.. _pillar-configuration-minion:

Pillar Configuration
====================

.. conf_minion:: pillar_roots

``pillar_roots``
----------------

Default:

.. code-block:: yaml

    base:
      - /srv/pillar

When using a local :conf_minion:`file_client`, this parameter is used to setup
the pillar environments.

.. code-block:: yaml

    pillar_roots:
      base:
        - /srv/pillar
      dev:
        - /srv/pillar/dev
      prod:
        - /srv/pillar/prod

.. conf_minion:: on_demand_ext_pillar

``on_demand_ext_pillar``
------------------------

.. versionadded:: 2016.3.6,2016.11.3,2017.7.0

Default: ``['libvirt', 'virtkey']``

When using a local :conf_minion:`file_client`, this option controls which
external pillars are permitted to be used on-demand using :py:func:`pillar.ext
<salt.modules.pillar.ext>`.

.. code-block:: yaml

    on_demand_ext_pillar:
      - libvirt
      - virtkey
      - git

.. warning::
    This will allow a masterless minion to request specific pillar data via
    :py:func:`pillar.ext <salt.modules.pillar.ext>`, and may be considered a
    security risk. However, pillar data generated in this way will not affect
    the :ref:`in-memory pillar data <pillar-in-memory>`, so this risk is
    limited to instances in which states/modules/etc. (built-in or custom) rely
    upon pillar data generated by :py:func:`pillar.ext
    <salt.modules.pillar.ext>`.

.. conf_minion:: decrypt_pillar

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
specified by :conf_minion:`decrypt_pillar_default` will be used.

.. conf_minion:: decrypt_pillar_delimiter

``decrypt_pillar_delimiter``
----------------------------

.. versionadded:: 2017.7.0

Default: ``:``

The delimiter used to distinguish nested data structures in the
:conf_minion:`decrypt_pillar` option.

.. code-block:: yaml

    decrypt_pillar_delimiter: '|'
    decrypt_pillar:
      - 'foo|bar': gpg
      - 'lorem|ipsum|dolor'

.. conf_minion:: decrypt_pillar_default

``decrypt_pillar_default``
--------------------------

.. versionadded:: 2017.7.0

Default: ``gpg``

The default renderer used for decryption, if one is not specified for a given
pillar key in :conf_minion:`decrypt_pillar`.

.. code-block:: yaml

    decrypt_pillar_default: my_custom_renderer

.. conf_minion:: decrypt_pillar_renderers

``decrypt_pillar_renderers``
----------------------------

.. versionadded:: 2017.7.0

Default: ``['gpg']``

List of renderers which are permitted to be used for pillar decryption.

.. code-block:: yaml

    decrypt_pillar_renderers:
      - gpg
      - my_custom_renderer

.. conf_minion:: pillarenv

``pillarenv``
-------------

Default: ``None``

Isolates the pillar environment on the minion side. This functions the same as
the environment setting, but for pillar instead of states.

.. code-block:: yaml

    pillarenv: dev

.. conf_minion:: pillarenv_from_saltenv

``pillarenv_from_saltenv``
--------------------------

.. versionadded:: 2017.7.0

Default: ``False``

When set to ``True``, the :conf_minion:`pillarenv` value will assume the value
of the effective saltenv when running states. This essentially makes ``salt '*'
state.sls mysls saltenv=dev`` equivalent to ``salt '*' state.sls mysls
saltenv=dev pillarenv=dev``. If :conf_minion:`pillarenv` is set, either in the
minion config file or via the CLI, it will override this option.

.. code-block:: yaml

    pillarenv_from_saltenv: True

.. conf_minion:: pillar_raise_on_missing

``pillar_raise_on_missing``
---------------------------

.. versionadded:: 2015.5.0

Default: ``False``

Set this option to ``True`` to force a ``KeyError`` to be raised whenever an
attempt to retrieve a named value from pillar fails. When this option is set
to ``False``, the failed attempt returns an empty string.

.. conf_minion:: minion_pillar_cache

``minion_pillar_cache``
-----------------------

.. versionadded:: 2016.3.0

Default: ``False``

The minion can locally cache rendered pillar data under
:conf_minion:`cachedir`/pillar. This allows a temporarily disconnected minion
to access previously cached pillar data by invoking salt-call with the --local
and --pillar_root=:conf_minion:`cachedir`/pillar options. Before enabling this
setting consider that the rendered pillar may contain security sensitive data.
Appropriate access restrictions should be in place. By default the saved pillar
data will be readable only by the user account running salt. By default this
feature is disabled, to enable set minion_pillar_cache to ``True``.

.. code-block:: yaml

    minion_pillar_cache: False

.. conf_minion:: file_recv_max_size

``file_recv_max_size``
----------------------

.. versionadded:: 2014.7.0

Default: ``100``

Set a hard-limit on the size of the files that can be pushed to the master.
It will be interpreted as megabytes.

.. code-block:: yaml

    file_recv_max_size: 100

.. conf_minion:: pass_to_ext_pillars

``pass_to_ext_pillars``
-----------------------

Specify a list of configuration keys whose values are to be passed to
external pillar functions.

Suboptions can be specified using the ':' notation (i.e. ``option:suboption``)

The values are merged and included in the ``extra_minion_data`` optional
parameter of the external pillar function.  The ``extra_minion_data`` parameter
is passed only to the external pillar functions that have it explicitly
specified in their definition.

If the config contains

.. code-block:: yaml

    opt1: value1
    opt2:
      subopt1: value2
      subopt2: value3

    pass_to_ext_pillars:
      - opt1
      - opt2: subopt1

the ``extra_minion_data`` parameter will be

.. code-block:: python

    {'opt1': 'value1',
     'opt2': {'subopt1': 'value2'}}

Security Settings
=================

.. conf_minion:: open_mode

``open_mode``
-------------

Default: ``False``

Open mode can be used to clean out the PKI key received from the Salt master,
turn on open mode, restart the minion, then turn off open mode and restart the
minion to clean the keys.

.. code-block:: yaml

    open_mode: False

.. conf_minion:: master_finger

``master_finger``
-----------------

Default: ``''``

Fingerprint of the master public key to validate the identity of your Salt master
before the initial key exchange. The master fingerprint can be found by running
"salt-key -F master" on the Salt master.

.. code-block:: yaml

   master_finger: 'ba:30:65:2a:d6:9e:20:4f:d8:b2:f3:a7:d4:65:11:13'

.. conf_minion:: keysize

``keysize``
-----------

Default: ``2048``

The size of key that should be generated when creating new keys.

.. code-block:: yaml

    keysize: 2048

.. conf_minion:: permissive_pki_access

``permissive_pki_access``
-------------------------

Default: ``False``

Enable permissive access to the salt keys. This allows you to run the
master or minion as root, but have a non-root group be given access to
your pki_dir. To make the access explicit, root must belong to the group
you've given access to. This is potentially quite insecure.

.. code-block:: yaml

    permissive_pki_access: False

.. conf_minion:: verify_master_pubkey_sign

``verify_master_pubkey_sign``
-----------------------------

Default: ``False``

Enables verification of the master-public-signature returned by the master in
auth-replies. Please see the tutorial on how to configure this properly
`Multimaster-PKI with Failover Tutorial <http://docs.saltstack.com/en/latest/topics/tutorials/multimaster_pki.html>`_

.. versionadded:: 2014.7.0

.. code-block:: yaml

    verify_master_pubkey_sign: True

If this is set to ``True``, :conf_master:`master_sign_pubkey` must be also set
to ``True`` in the master configuration file.


.. conf_minion:: master_sign_key_name

``master_sign_key_name``
------------------------

Default: ``master_sign``

The filename without the *.pub* suffix of the public key that should be used
for verifying the signature from the master. The file must be located in the
minion's pki directory.

.. versionadded:: 2014.7.0

.. code-block:: yaml

    master_sign_key_name: <filename_without_suffix>

.. conf_minion:: autosign_grains

``autosign_grains``
-------------------

.. versionadded:: 2018.3.0

Default: ``not defined``

The grains that should be sent to the master on authentication to decide if
the minion's key should be accepted automatically.

Please see the :ref:`Autoaccept Minions from Grains <tutorial-autoaccept-grains>`
documentation for more information.

.. code-block:: yaml

    autosign_grains:
      - uuid
      - server_id

.. conf_minion:: always_verify_signature

``always_verify_signature``
---------------------------

Default: ``False``

If :conf_minion:`verify_master_pubkey_sign` is enabled, the signature is only verified
if the public-key of the master changes. If the signature should always be verified,
this can be set to ``True``.

.. versionadded:: 2014.7.0

.. code-block:: yaml

    always_verify_signature: True

.. conf_minion:: cmd_blacklist_glob

``cmd_blacklist_glob``
----------------------

Default: ``[]``

If :conf_minion:`cmd_blacklist_glob` is enabled then any shell command called over
remote execution or via salt-call will be checked against the glob matches found in
the `cmd_blacklist_glob` list and any matched shell command will be blocked.

.. note::

    This blacklist is only applied to direct executions made by the `salt` and
    `salt-call` commands. This does NOT blacklist commands called from states
    or shell commands executed from other modules.

.. versionadded:: 2016.11.0

.. code-block:: yaml

    cmd_blacklist_glob:
      - 'rm * '
      - 'cat /etc/* '

.. conf_minion:: cmd_whitelist_glob

``cmd_whitelist_glob``
----------------------

Default: ``[]``

If :conf_minion:`cmd_whitelist_glob` is enabled then any shell command called over
remote execution or via salt-call will be checked against the glob matches found in
the `cmd_whitelist_glob` list and any shell command NOT found in the list will be
blocked. If `cmd_whitelist_glob` is NOT SET, then all shell commands are permitted.

.. note::

    This whitelist is only applied to direct executions made by the `salt` and
    `salt-call` commands. This does NOT restrict commands called from states
    or shell commands executed from other modules.

.. versionadded:: 2016.11.0

.. code-block:: yaml

    cmd_whitelist_glob:
      - 'ls * '
      - 'cat /etc/fstab'


.. conf_minion:: ssl

``ssl``
-------

.. versionadded:: 2016.11.0

Default: ``None``

TLS/SSL connection options. This could be set to a dictionary containing
arguments corresponding to python ``ssl.wrap_socket`` method. For details see
`Tornado <http://www.tornadoweb.org/en/stable/tcpserver.html#tornado.tcpserver.TCPServer>`_
and `Python <http://docs.python.org/2/library/ssl.html#ssl.wrap_socket>`_
documentation.

Note: to set enum arguments values like ``cert_reqs`` and ``ssl_version`` use
constant names without ssl module prefix: ``CERT_REQUIRED`` or ``PROTOCOL_SSLv23``.

.. code-block:: yaml

    ssl:
        keyfile: <path_to_keyfile>
        certfile: <path_to_certfile>
        ssl_version: PROTOCOL_TLSv1_2


Reactor Settings
================

.. conf_minion:: reactor

``reactor``
-----------

Default: ``[]``

Defines a salt reactor. See the :ref:`Reactor <reactor>` documentation for more
information.

.. code-block:: yaml

    reactor: []

.. conf_minion:: reactor_refresh_interval

``reactor_refresh_interval``
----------------------------

Default: ``60``

The TTL for the cache of the reactor configuration.

.. code-block:: yaml

    reactor_refresh_interval: 60

.. conf_minion:: reactor_worker_threads

``reactor_worker_threads``
--------------------------

Default: ``10``

The number of workers for the runner/wheel in the reactor.

.. code-block:: yaml

    reactor_worker_threads: 10

.. conf_minion:: reactor_worker_hwm

``reactor_worker_hwm``
----------------------

Default: ``10000``

The queue size for workers in the reactor.

.. code-block:: yaml

    reactor_worker_hwm: 10000


Thread Settings
===============

.. conf_minion:: multiprocessing

``multiprocessing``
-------------------

Default: ``True``

If ``multiprocessing`` is enabled when a minion receives a
publication a new process is spawned and the command is executed therein.
Conversely, if ``multiprocessing`` is disabled the new publication will be run
executed in a thread.


.. code-block:: yaml

    multiprocessing: True

.. conf_minion:: process_count_max

``process_count_max``
---------------------

.. versionadded:: 2018.3.0

Default: ``-1``

Limit the maximum amount of processes or threads created by ``salt-minion``.
This is useful to avoid resource exhaustion in case the minion receives more
publications than it is able to handle, as it limits the number of spawned
processes or threads. ``-1`` is the default and disables the limit.

.. code-block:: yaml

    process_count_max: -1

.. _minion-logging-settings:

Minion Logging Settings
=======================

.. conf_minion:: log_file

``log_file``
------------

Default: ``/var/log/salt/minion``

The minion log can be sent to a regular file, local path name, or network
location.  See also :conf_log:`log_file`.

Examples:

.. code-block:: yaml

    log_file: /var/log/salt/minion

.. code-block:: yaml

    log_file: file:///dev/log

.. code-block:: yaml

    log_file: udp://loghost:10514


.. conf_minion:: log_level

``log_level``
-------------

Default: ``warning``

The level of messages to send to the console. See also :conf_log:`log_level`.

.. code-block:: yaml

    log_level: warning


.. conf_minion:: log_level_logfile

``log_level_logfile``
---------------------

Default: ``warning``

The level of messages to send to the log file. See also
:conf_log:`log_level_logfile`. When it is not set explicitly
it will inherit the level set by :conf_log:`log_level` option.

.. code-block:: yaml

    log_level_logfile: warning


.. conf_minion:: log_datefmt

``log_datefmt``
---------------

Default: ``%H:%M:%S``

The date and time format used in console log messages. See also
:conf_log:`log_datefmt`.

.. code-block:: yaml

    log_datefmt: '%H:%M:%S'


.. conf_minion:: log_datefmt_logfile

``log_datefmt_logfile``
-----------------------

Default: ``%Y-%m-%d %H:%M:%S``

The date and time format used in log file messages. See also
:conf_log:`log_datefmt_logfile`.

.. code-block:: yaml

    log_datefmt_logfile: '%Y-%m-%d %H:%M:%S'


.. conf_minion:: log_fmt_console

``log_fmt_console``
-------------------

Default: ``[%(levelname)-8s] %(message)s``

The format of the console logging messages. See also
:conf_log:`log_fmt_console`.

.. note::
    Log colors are enabled in ``log_fmt_console`` rather than the
    :conf_minion:`color` config since the logging system is loaded before the
    minion config.

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


.. conf_minion:: log_fmt_logfile

``log_fmt_logfile``
-------------------

Default: ``%(asctime)s,%(msecs)03d [%(name)-17s][%(levelname)-8s] %(message)s``

The format of the log file logging messages. See also
:conf_log:`log_fmt_logfile`.

.. code-block:: yaml

    log_fmt_logfile: '%(asctime)s,%(msecs)03d [%(name)-17s][%(levelname)-8s] %(message)s'


.. conf_minion:: log_granular_levels

``log_granular_levels``
-----------------------

Default: ``{}``

This can be used to control logging levels more specifically. See also
:conf_log:`log_granular_levels`.


.. conf_minion:: log_rotate_max_bytes

``log_rotate_max_bytes``
------------------------

Default:  ``0``

The maximum number of bytes a single log file may contain before it is rotated.
A value of 0 disables this feature. Currently only supported on Windows. On
other platforms, use an external tool such as 'logrotate' to manage log files.
:conf_log:`log_rotate_max_bytes`


.. conf_minion:: log_rotate_backup_count

``log_rotate_backup_count``
---------------------------

Default:  ``0``

The number of backup files to keep when rotating log files. Only used if
:conf_minion:`log_rotate_max_bytes` is greater than 0. Currently only supported
on Windows. On other platforms, use an external tool such as 'logrotate' to
manage log files.
:conf_log:`log_rotate_backup_count`


.. conf_minion:: zmq_monitor

``zmq_monitor``
---------------

Default: ``False``

To diagnose issues with minions disconnecting or missing returns, ZeroMQ
supports the use of monitor sockets to log connection events. This
feature requires ZeroMQ 4.0 or higher.

To enable ZeroMQ monitor sockets, set 'zmq_monitor' to 'True' and log at a
debug level or higher.

A sample log event is as follows:

.. code-block:: yaml

    [DEBUG   ] ZeroMQ event: {'endpoint': 'tcp://127.0.0.1:4505', 'event': 512,
    'value': 27, 'description': 'EVENT_DISCONNECTED'}

All events logged will include the string ``ZeroMQ event``. A connection event
should be logged as the minion starts up and initially connects to the
master. If not, check for debug log level and that the necessary version of
ZeroMQ is installed.

.. conf_minion:: failhard

``tcp_authentication_retries``
------------------------------

Default: ``5``

The number of times to retry authenticating with the salt master when it comes
back online.

Zeromq does a lot to make sure when connections come back online that they
reauthenticate. The tcp transport should try to connect with a new connection
if the old one times out on reauthenticating.

`-1` for infinite tries.

``failhard``
------------

Default: ``False``

Set the global failhard flag. This informs all states to stop running states
at the moment a single state fails

.. code-block:: yaml

    failhard: False

Include Configuration
=====================

Configuration can be loaded from multiple files. The order in which this is
done is:

1. The minion config file itself

2. The files matching the glob in :conf_minion:`default_include`

3. The files matching the glob in :conf_minion:`include` (if defined)

Each successive step overrides any values defined in the previous steps.
Therefore, any config options defined in one of the
:conf_minion:`default_include` files would override the same value in the
minion config file, and any options defined in :conf_minion:`include` would
override both.

.. conf_minion:: default_include

``default_include``
-------------------

Default: ``minion.d/*.conf``

The minion can include configuration from other files. Per default the
minion will automatically include all config files from `minion.d/*.conf`
where minion.d is relative to the directory of the minion configuration
file.

.. note::

    Salt creates files in the ``minion.d`` directory for its own use. These
    files are prefixed with an underscore. A common example of this is the
    ``_schedule.conf`` file.

.. conf_minion:: include

``include``
-----------

Default: ``not defined``

The minion can include configuration from other files. To enable this,
pass a list of paths to this option. The paths can be either relative or
absolute; if relative, they are considered to be relative to the directory
the main minion configuration file lives in. Paths can make use of
shell-style globbing. If no files are matched by a path passed to this
option then the minion will log a warning message.

.. code-block:: yaml

    # Include files from a minion.d directory in the same
    # directory as the minion config file
    include: minion.d/*.conf

    # Include a single extra file into the configuration
    include: /etc/roles/webserver

    # Include several files and the minion.d directory
    include:
      - extra_config
      - minion.d/*
      - /etc/roles/webserver


Keepalive Settings
==================

.. conf_minion:: tcp_keepalive

``tcp_keepalive``
-----------------

Default: ``True``

The tcp keepalive interval to set on TCP ports. This setting can be used to tune Salt
connectivity issues in messy network environments with misbehaving firewalls.

.. code-block:: yaml

    tcp_keepalive: True

.. conf_minion:: tcp_keepalive_cnt

``tcp_keepalive_cnt``
---------------------

Default: ``-1``

Sets the ZeroMQ TCP keepalive count. May be used to tune issues with minion disconnects.

.. code-block:: yaml

    tcp_keepalive_cnt: -1

.. conf_minion:: tcp_keepalive_idle

``tcp_keepalive_idle``
----------------------

Default: ``300``

Sets ZeroMQ TCP keepalive idle. May be used to tune issues with minion disconnects.

.. code-block:: yaml

    tcp_keepalive_idle: 300

.. conf_minion:: tcp_keepalive_intvl

``tcp_keepalive_intvl``
-----------------------

Default: ``-1``

Sets ZeroMQ TCP keepalive interval. May be used to tune issues with minion disconnects.

.. code-block:: yaml

    tcp_keepalive_intvl': -1


Frozen Build Update Settings
============================

These options control how :py:func:`salt.modules.saltutil.update` works with esky
frozen apps. For more information look at `<https://github.com/cloudmatrix/esky/>`_.

.. conf_minion:: update_url

``update_url``
--------------

Default: ``False`` (Update feature is disabled)

The url to use when looking for application updates. Esky depends on directory
listings to search for new versions. A webserver running on your Master is a
good starting point for most setups.

.. code-block:: yaml

    update_url: 'http://salt.example.com/minion-updates'

.. conf_minion:: update_restart_services

``update_restart_services``
---------------------------

Default: ``[]`` (service restarting on update is disabled)

A list of services to restart when the minion software is updated. This would
typically just be a list containing the minion's service name, but you may
have other services that need to go with it.

.. code-block:: yaml

    update_restart_services: ['salt-minion']

.. conf_minion:: winrepo_cache_expire_min

``winrepo_cache_expire_min``
----------------------------

.. versionadded:: 2016.11.0

Default: ``1800``

If set to a nonzero integer, then passing ``refresh=True`` to functions in the
:mod:`windows pkg module <salt.modules.win_pkg>` will not refresh the windows
repo metadata if the age of the metadata is less than this value. The exception
to this is :py:func:`pkg.refresh_db <salt.modules.win_pkg.refresh_db>`, which
will always refresh the metadata, regardless of age.

.. code-block:: yaml

    winrepo_cache_expire_min: 1800

.. conf_minion:: winrepo_cache_expire_max

``winrepo_cache_expire_max``
----------------------------

.. versionadded:: 2016.11.0

Default: ``21600``

If the windows repo metadata is older than this value, and the metadata is
needed by a function in the :mod:`windows pkg module <salt.modules.win_pkg>`,
the metadata will be refreshed.

.. code-block:: yaml

    winrepo_cache_expire_max: 86400

.. _winrepo-minion-config-opts:

Minion Windows Software Repo Settings
=====================================

.. important::
    To use these config options, the minion can be running in master-minion or
    masterless mode.


.. conf_minion:: winrepo_source_dir

``winrepo_source_dir``
----------------------

Default: ``salt://win/repo-ng/``

The source location for the winrepo sls files.

.. code-block:: yaml

    winrepo_source_dir: salt://win/repo-ng/

Standalone Minion Windows Software Repo Settings
================================================

.. important::
    To use these config options, the minion must be running in masterless mode
    (set :conf_minion:`file_client` to ``local``).

.. conf_minion:: winrepo_dir
.. conf_minion:: win_repo

``winrepo_dir``
---------------

.. versionchanged:: 2015.8.0
    Renamed from ``win_repo`` to ``winrepo_dir``. Also, this option did not
    have a default value until this version.

Default: ``C:\salt\srv\salt\win\repo``

Location on the minion where the :conf_minion:`winrepo_remotes` are checked
out.

.. code-block:: yaml

    winrepo_dir: 'D:\winrepo'

.. conf_minion:: winrepo_dir_ng

``winrepo_dir_ng``
------------------

.. versionadded:: 2015.8.0
    A new :ref:`ng <windows-package-manager>` repo was added.

Default: ``/srv/salt/win/repo-ng``

Location on the minion where the :conf_minion:`winrepo_remotes_ng` are checked
out for 2015.8.0 and later minions.

.. code-block:: yaml

    winrepo_dir_ng: /srv/salt/win/repo-ng

.. conf_minion:: winrepo_cachefile
.. conf_minion:: win_repo_cachefile

``winrepo_cachefile``
---------------------

.. versionchanged:: 2015.8.0
    Renamed from ``win_repo_cachefile`` to ``winrepo_cachefile``. Also,
    this option did not have a default value until this version.

Default: ``winrepo.p``

Path relative to :conf_minion:`winrepo_dir` where the winrepo cache should be
created.

.. code-block:: yaml

    winrepo_cachefile: winrepo.p

.. conf_minion:: winrepo_remotes
.. conf_minion:: win_gitrepos

``winrepo_remotes``
-------------------

.. versionchanged:: 2015.8.0
    Renamed from ``win_gitrepos`` to ``winrepo_remotes``. Also, this option did
    not have a default value until this version.


.. versionadded:: 2015.8.0

Default: ``['https://github.com/saltstack/salt-winrepo.git']``

List of git repositories to checkout and include in the winrepo

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

.. conf_minion:: winrepo_remotes_ng

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

``ssh_merge_pillar``
--------------------

.. versionadded:: 2018.3.2

Default: ``True``

Merges the compiled pillar data with the pillar data already available globally.
This is useful when using ``salt-ssh`` or ``salt-call --local`` and overriding the pillar
data in a state file:

.. code-block:: yaml

    apply_showpillar:
      module.run:
        - name: state.apply
        - mods:
          - showpillar
        - kwargs:
              pillar:
                  test: "foo bar"

If set to ``True`` the ``showpillar`` state will have access to the
global pillar data.

If set to ``False`` only the overriding pillar data will be available
to the ``showpillar`` state.
