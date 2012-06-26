===========================
Configuring the Salt Minion
===========================

The Salt system is amazingly simple and easy to configure, the two components
of the Salt system each have a respective configuration file. The
:command:`salt-master` is configured via the master configuration file, and the
:command:`salt-minion` is configured via the minion configuration file.

.. seealso::
    :ref:`example minion configuration file <configuration-examples-minion>`

The Salt Minion configuration is very simple, typically the only value that
needs to be set is the master value so the minion can find its master.

Minion Primary Configuration
----------------------------

.. conf_minion:: master

``master``
----------

Default: ``salt``

The hostname or ipv4 of the master.

.. code-block:: yaml

    master: salt

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

.. conf_minion:: pki_dir

``pki_dir``
-----------

Default: :file:`/etc/salt/pki`

The directory used to store the minion's public and private keys.

.. code-block:: yaml

    pki_dir: /etc/salt/pki

.. conf_minion:: id

``id``
------

Default: hostname (as returned by the Python call: ``socket.getfqdn()``)

Explicitly declare the id for this minion to use, if left commented the id
will be the hostname as returned by the Python call: ``socket.getfqdn()``
Since Salt uses detached ids it is possible to run multiple minions on the
same machine but with different ids, this can be useful for Salt compute
clusters.

.. code-block:: yaml

    id: foo.bar.com

.. conf_minion:: sub_timeout

``sub_timeout``
---------------

The minion connection to the master may be interrupted, the minion will
verify the connection every so many seconds, to disable connection
verification set this value to 0

.. code-block:: yaml

    sub_timeout: 60

.. conf_minion:: cachedir

``cachedir``
------------

Default: :file:`/var/cache/salt`

The location for minion cache data.

.. code-block:: yaml

    cachedir: /var/cache/salt

.. conf_minion:: cache_jobs

``cache_jobs``
--------------

Default: ``False``

The minion can locally cache the return data from jobs sent to it, this
can be a good way to keep track minion side of the jobs the minion has
executed. By default this feature is disabled, to enable set cache_jobs
to True

.. code-block:: yaml

    cache_jobs: False

.. conf_minion:: acceptance_wait_time

``acceptance_wait_time``
------------------------

Default: ``10``

The number of seconds to wait until attempting to re-authenticate with the
master.

.. code-block:: yaml

    acceptance_wait_time: 10

Minion Module Management
------------------------

.. conf_minion:: disable_modules

``disable_modules``
-------------------

Default: ``[]`` (all modules are enabled by default)

The event may occur in which the administrator desires that a minion should not
be able to execute a certain module. The sys module is built into the minion
and cannot be disabled.

This setting can also tune the minion, as all modules are loaded into ram
disabling modules will lover the minion's ram footprint.

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

State Management Settings
-------------------------

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

.. conf_minion:: autoload_dynamic_modules

``autoload_dynamic_modules``
----------------------------

Default: ``True``

autoload_dynamic_modules Turns on automatic loading of modules found in the
environments on the master. This is turned on by default, to turn of
autoloading modules when states run set this value to ``False``

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

Security Settings
-----------------

.. conf_minion:: open_mode

``open_mode``
-------------

Default: ``False``

Open mode can be used to clean out the PKI key received from the Salt master,
turn on open mode, restart the minion, then turn off open mode and restart the
minion to clean the keys.

.. code-block:: yaml

    open_mode: False

Thread Settings
---------------

.. conf_minion:: multiprocessing

Default: ``True``

Disable multiprocessing support by default when a minion receives a
publication a new process is spawned and the command is executed therein.

.. code-block:: yaml

    multiprocessing: True

Minion Logging Settings
-----------------------

.. conf_minion:: log_file

``log_file``
------------

Default: :file:`/var/log/salt/minion`

The location of the minion log file

.. code-block:: yaml

    log_file: /var/log/salt/minion

.. conf_minion:: log_level

``log_level``
-------------

Default: ``warning``

The level of messages to send to the log file.
One of 'info', 'quiet', 'critical', 'error', 'debug', 'warning'.

.. code-block:: yaml

    log_level: warning

.. conf_minion:: log_granular_levels

``log_granular_levels``
-----------------------

Default: ``{}``

Logger levels can be used to tweak specific loggers logging levels.
Imagine you want to have the Salt library at the 'warning' level, but, you
still wish to have 'salt.modules' at the 'debug' level:

.. code-block:: yaml

  log_granular_levels:
    'salt': 'warning',
    'salt.modules': 'debug'

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
    include: minion.d/*

    # Include a single extra file into the configuration
    include: /etc/roles/webserver

    # Include several files and the minion.d directory
    include:
      - extra_config
      - minion.d/*
      - /etc/roles/webserver
