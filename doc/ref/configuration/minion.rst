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

The hostname or ipv4 of the master.

Default: ``salt``

.. code-block:: yaml

    master: salt

The option can can also be set to a list of masters, enabling
:doc:`multi-master </topics/tutorials/multimaster>` mode.

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

.. conf_minion:: master_type

``master_type``
---------------

.. versionadded:: 2014.7.0

Default: ``str``

The type of the :conf_minion:`master` variable. Can be ``str``, ``failover`` or
``func``.

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

``master_alive_interval``
-------------------------

.. code-block:: yaml

    master_alive_interval: 30

Configures how often, in seconds, the minion will verify that the current
master is alive and responding.  The minion will try to establish a connection
to the next master in the list if it finds the existing one is dead.

``master_shuffle``
------------------

.. versionadded:: 2014.7.0

Default: ``False``

If :conf_minion:`master` is a list of addresses, shuffle them before trying to
connect to distribute the minions over all available masters. This uses
Python's :func:`random.shuffle <python2:random.shuffle>` method.

.. code-block:: yaml

    master_shuffle: True

.. conf_minion:: retry_dns

``retry_dns``
---------------

Default: ``30``

Set the number of seconds to wait before attempting to resolve
the master hostname if name resolution fails. Defaults to 30 seconds.
Set to zero if the minion should shutdown and not retry.

.. code-block:: yaml
    
    retry_dns: 30

.. conf_minion:: master_port

``master_port``
---------------

Default: ``4506``

The port of the master ret server, this needs to coincide with the ret_port
option on the Salt master.

.. code-block:: yaml

    master_port: 4506

.. conf_minion:: user

``user``
--------

Default: ``root``

The user to run the Salt processes

.. code-block:: yaml

    user: root

.. conf_minion:: sudo_user

``sudo_user``
--------

Default: ``''``

Setting ``sudo_user`` will cause salt to run all execution modules under an
sudo to the user given in ``sudo_user``.  The user under which the salt minion
process itself runs will still be that provided in :conf_minion:`user` above,
but all execution modules run by the minion will be rerouted through sudo.

.. code-block:: yaml

    sudo_user: saltadm

.. conf_minion:: pidfile

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

.. conf_minion:: pki_dir

``pki_dir``
-----------

Default: ``/etc/salt/pki``

The directory used to store the minion's public and private keys.

.. code-block:: yaml

    pki_dir: /etc/salt/pki

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

.. conf_minion:: append_domain

``append_domain``
-----------------

Default: ``None``

Append a domain to a hostname in the event that it does not exist. This is
useful for systems where ``socket.getfqdn()`` does not actually result in a
FQDN (for instance, Solaris).

.. code-block:: yaml

    append_domain: foo.org

.. conf_minion:: cachedir

``cachedir``
------------

Default: ``/var/cache/salt``

The location for minion cache data.

.. code-block:: yaml

    cachedir: /var/cache/salt

.. conf_minion:: verify_env

``verify_env``
--------------

Default: ``True``

Verify and set permissions on configuration directories at startup.

.. code-block:: yaml

    verify_env: True

.. note::

    When marked as True the verify_env option requires WRITE access to the
    configuration directory (/etc/salt/). In certain situations such as
    mounting /etc/salt/ as read-only for templating this will create a
    stack trace when state.highstate is called.

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

.. conf_minion:: grains_cache

``grains_cache``
----------------

Default: ``False``

The minion can locally cache grain data instead of refreshing the data
each time the grain is referenced. By default this feature is disabled,
to enable set grains_cache to ``True``.

.. code-block:: yaml

    grains_cache: False


.. conf_minion:: sock_dir

``sock_dir``
------------

Default: ``/var/run/salt/minion``

The directory where Unix sockets will be kept.

.. code-block:: yaml

    sock_dir: /var/run/salt/minion

.. conf_minion:: backup_mode

``backup_mode``
---------------

Default: ``[]``

Backup files replaced by file.managed and file.recurse under cachedir.

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

.. conf_minion:: random_reauth_delay

``random_reauth_delay``
-----------------------

When the master key changes, the minion will try to re-auth itself to
receive the new master key. In larger environments this can cause a syn-flood
on the master because all minions try to re-auth immediately. To prevent this
and have a minion wait for a random amount of time, use this optional
parameter. The wait-time will be a random number of seconds between
0 and the defined value.

.. code-block:: yaml

    random_reauth_delay: 60

.. conf_minion:: acceptance_wait_time_max

``acceptance_wait_time_max``
----------------------------

Default: ``None``

The maximum number of seconds to wait until attempting to re\-authenticate
with the master. If set, the wait will increase by acceptance_wait_time
seconds each iteration.

.. code-block:: yaml

    acceptance_wait_time_max: None

.. conf_minion:: recon_default

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
between recon_default and recon_default and recon_max. Having all minions reconnect
with the same recon_default and recon_max value kind of defeats the purpose of being
able to change these settings. If all minions have the same values and the setup is
quite large (several thousand minions), they will still flood the master. The desired
behavior is to have time-frame within all minions try to reconnect.

.. code-block:: yaml

    recon_randomize: True

.. conf_minion:: cache_sreqs

``cache_sreqs``
---------------

Default: ``True``

The connection to the master ret_port is kept open. When set to False, the minion
creates a new connection for every return to the master.
environment, set this value to ``False``.

.. code-block:: yaml

    cache_sreqs: True

.. conf_minion:: ipc_mode

``ipc_mode``
------------

Default: ``ipc``

Windows platforms lack POSIX IPC and must rely on slower TCP based inter-
process communications. Set ipc_mode to ``tcp`` on such systems.

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



Minion Module Management
========================

.. conf_minion:: disable_modules

``disable_modules``
-------------------

Default: ``[]`` (all modules are enabled by default)

The event may occur in which the administrator desires that a minion should not
be able to execute a certain module. The sys module is built into the minion
and cannot be disabled.

This setting can also tune the minion, as all modules are loaded into ram
disabling modules will lower the minion's ram footprint.

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

    returners_dirs:
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

.. conf_minion:: cython_enable

``cython_enable``
-----------------

Default: ``False``

Set this value to true to enable auto-loading and compiling of ``.pyx`` modules,
This setting requires that ``gcc`` and ``cython`` are installed on the minion

.. code-block:: yaml

    cython_enable: False

.. conf_minion:: providers

``providers``
-------------

Default: (empty)

A module provider can be statically overwritten or extended for the minion via
the ``providers`` option. This can be done :doc:`on an individual basis in an
SLS file <../states/providers>`, or globally here in the minion config, like
below.

.. code-block:: yaml

    providers:
      service: systemd


State Management Settings
=========================

.. conf_minion:: renderer

``renderer``
------------

Default: ``yaml_jinja``

The default renderer used for local state executions

.. code-block:: yaml

    renderer: yaml_jinja

.. conf_minion:: state_verbose

``state_verbose``
-----------------

Default: ``False``

state_verbose allows for the data returned from the minion to be more
verbose. Normally only states that fail or states that have changes are
returned, but setting state_verbose to ``True`` will return all states that
were checked

.. code-block:: yaml

    state_verbose: True

.. conf_minion:: state_output

``state_output``
----------------

Default: ``full``

The state_output setting changes if the output is the full multi line
output for each changed state if set to 'full', but if set to 'terse'
the output will be shortened to a single line.

.. code-block:: yaml

    state_output: full

.. conf_minion:: autoload_dynamic_modules

``autoload_dynamic_modules``
----------------------------

Default: ``True``

autoload_dynamic_modules Turns on automatic loading of modules found in the
environments on the master. This is turned on by default, to turn of
auto-loading modules when states run set this value to ``False``

.. code-block:: yaml

    autoload_dynamic_modules: True

.. conf_minion:: clean_dynamic_modules

Default: ``True``

clean_dynamic_modules keeps the dynamic modules on the minion in sync with
the dynamic modules on the master, this means that if a dynamic module is
not on the master it will be deleted from the minion. By default this is
enabled and can be disabled by changing this value to ``False``

.. code-block:: yaml

    clean_dynamic_modules: True

.. conf_minion:: environment

``environment``
---------------

Default: ``None``

Normally the minion is not isolated to any single environment on the master
when running states, but the environment can be isolated on the minion side
by statically setting it. Remember that the recommended way to manage
environments is to isolate via the top file.

.. code-block:: yaml

    environment: None



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

.. conf_minion:: hash_type

``hash_type``
-------------

Default: ``md5``

The hash_type is the hash to use when discovering the hash of a file on the
local fileserver. The default is md5, but sha1, sha224, sha256, sha384, and
sha512 are also supported.

.. code-block:: yaml

    hash_type: md5

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

.. conf_minion:: always_verify_signature

``always_verify_signature``
---------------------------

Default: ``False``

If :conf_minion:`verify_master_pubkey_sign` is enabled, the signature is only verified,
if the public-key of the master changes. If the signature should always be verified,
this can be set to ``True``.

.. versionadded:: 2014.7.0

.. code-block:: yaml

    always_verify_signature: True

Thread Settings
===============

.. conf_minion:: multiprocessing

Default: ``True``

Disable multiprocessing support by default when a minion receives a
publication a new process is spawned and the command is executed therein.

.. code-block:: yaml

    multiprocessing: True




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
:conf_log:`log_level_logfile`.

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

.. code-block:: yaml

    log_fmt_console: '[%(levelname)-8s] %(message)s'



.. conf_minion:: log_fmt_logfile

``log_fmt_logfile``
-------------------

Default: ``%(asctime)s,%(msecs)03.0f [%(name)-17s][%(levelname)-8s] %(message)s``

The format of the log file logging messages. See also
:conf_log:`log_fmt_logfile`.

.. code-block:: yaml

    log_fmt_logfile: '%(asctime)s,%(msecs)03.0f [%(name)-17s][%(levelname)-8s] %(message)s'



.. conf_minion:: log_granular_levels

``log_granular_levels``
-----------------------

Default: ``{}``

This can be used to control logging levels more specifically. See also
:conf_log:`log_granular_levels`.



.. conf_minion:: failhard

``failhard``
------------

Default: ``False``

Set the global failhard flag, this informs all states to stop running states
at the moment a single state fails



.. code-block:: yaml

    failhard: False

Include Configuration
=====================

.. conf_minion:: include

``default_include``
-------------------

Default: ``minion.d/*.conf``

The minion can include configuration from other files. Per default the
minion will automatically include all config files from `minion.d/*.conf`
where minion.d is relative to the directory of the minion configuration
file.

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
