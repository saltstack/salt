.. _modular-systems:

===============
Modular Systems
===============

When first working with Salt, it is not always clear where all of the modular
components are and what they do. Salt comes loaded with more modular systems
than many users are aware of, making Salt very easy to extend in many places.

The most commonly used modular systems are execution modules and states. But
the modular systems extend well beyond the more easily exposed components
and are often added to Salt to make the complete system more flexible.

.. toctree::
    :maxdepth: 2
    :glob:

    developing
    configuration


Loading Modules
===============

Modules come primarily from several sources:

* The Salt package itself
* The Salt File Server
* The extmods directory
* Secondary packages installed

Using one source to override another is not supported.

The Salt Package
----------------

Salt itself ships with a large number of modules. These are part of the Salt
package itself and don't require the user to do anything to use them. (Although
a number of them have additional dependencies and/or configuration.)

The Salt File Server
--------------------

The user may add modules by simply placing them in special directories in their
:ref:`fileserver <file-server>`.

The name of the directory inside of the file server is the directory name
prepended by underscore, such as:

- :file:`_grains`
- :file:`_modules`
- :file:`_states`

Modules must be synced before they can be used. This can happen a few ways,
discussed below.

.. note::
    Using saltenvs besides ``base`` may not work in all contexts.

Sync Via States
~~~~~~~~~~~~~~~

The minion configuration contains an option ``autoload_dynamic_modules``
which defaults to ``True``. This option makes the state system refresh all
dynamic modules when states are run. To disable this behavior set
:conf_minion:`autoload_dynamic_modules` to ``False`` in the minion config.

When dynamic modules are autoloaded via states, only the modules defined in the
same saltenvs as the states currently being run.

Also it is possible to use the explicit ``saltutil.sync_*`` :py:mod:`state functions <salt.states.saltutil>`
to sync the modules (previously it was necessary to use the ``module.run`` state):

.. code-block::yaml

   synchronize_modules:
     saltutil.sync_modules:
       - refresh: True


Sync Via the saltutil Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The saltutil module has a number of functions that can be used to sync all
or specific dynamic modules. The ``saltutil.sync_*``
:py:mod:`execution functions <salt.modules.saltutil>` and
:py:mod:`runner functions <salt.runners.saltutil>` can be used to sync modules
to minions and the master, respectively.


The extmods Directory
---------------------

Any files places in the directory set by ``extension_modules`` settings
(:conf_minion:`minion <extension_modules>`,
:conf_master:`master <extension_modules>`, default
``/var/cache/salt/*/extmods``) can also be loaded as modules. Note that these
directories are also used by the ``saltutil.sync_*`` functions (mentioned
above) and files may be overwritten.

Secondary Packages
------------------

Third-party packages may also add modules to Salt if they are installed in the
same system and Python environment as the Salt Minion or Master.

This is done via setuptools entry points:

.. code-block:: python

    setup(
        # ...
        entry_points={
            'salt.loader': [
                'module_dirs=spirofs.loader:module',
            ],
        },
        # ...
    )

Note that these are not synced from the Salt Master to the Minions. They must be
installed independently on each Minion.

Module Types
============

The specific names used by each loading method above are as follows. See sections below
for a short summary of each of these systems.

.. _module-name-table:

============ ================================================================ ========================= =====================
Module Type  Salt Package Name                                                FS/Directory Name         Entry Point
============ ================================================================ ========================= =====================
Auth         ``salt.auth`` (:ref:`index <external-logging-handlers>`)         ``auth`` [#no-fs]_        ``auth_dirs``
Beacon       ``salt.beacons`` (:ref:`index <beacons>`)                        ``beacons``               ``beacons_dirs``
Cache        ``salt.cache`` (:ref:`index <all-salt.cache>`)                   ``cache``                 ``cache_dirs``
Cloud        ``salt.cloud.clouds`` (:ref:`index <all-salt.clouds>`)           ``clouds``                ``cloud_dirs``
Engine       ``salt.engines`` (:ref:`index <engines>`)                        ``engines``               ``engines_dirs``
Execution    ``salt.modules`` (:ref:`index <all-salt.modules>`)               ``modules``               ``module_dirs``
Executor     ``salt.executors`` (:ref:`index <all-salt.executors>`)           ``executors``             ``executor_dirs``
File Server  ``salt.fileserver`` (:ref:`index <file-server>`)                 ``fileserver``            ``fileserver_dirs``
Grain        ``salt.grains`` (:ref:`index <all-salt.grains>`)                 ``grains``                ``grains_dirs``
Log Handler  ``salt.log.handlers`` (:ref:`index <external-logging-handlers>`) ``log_handlers``          ``log_handlers_dirs``
Matcher      ``salt.matchers``                                                ``matchers``              ``matchers_dirs``
Metaproxy    ``salt.metaproxy``                                               ``metaproxy`` [#no-fs]_   ``metaproxy_dirs``
Net API      ``salt.netapi`` (:ref:`index <all-netapi-modules>`)              ``netapi`` [#no-fs]_      ``netapi_dirs``
Outputter    ``salt.output`` (:ref:`index <all-salt.output>`)                 ``output``                ``outputter_dirs``
Pillar       ``salt.pillar`` (:ref:`index <all-salt.pillars>`)                ``pillar``                ``pillar_dirs``
Proxy        ``salt.proxy`` (:ref:`index <all-salt.proxy>`)                   ``proxy``                 ``proxy_dirs``
Queue        ``salt.queues`` (:ref:`index <all-salt.queues>`)                 ``queues``                ``queue_dirs``
Renderer     ``salt.renderers`` (:ref:`index <all-salt.renderers>`)           ``renderers``             ``render_dirs``
Returner     ``salt.returners`` (:ref:`index <all-salt.returners>`)           ``returners``             ``returner_dirs``
Roster       ``salt.roster`` (:ref:`index <all-salt.roster>`)                 ``roster``                ``roster_dirs``
Runner       ``salt.runners`` (:ref:`index <all-salt.runners>`)               ``runners``               ``runner_dirs``
SDB          ``salt.sdb`` (:ref:`index <all-salt.sdb>`)                       ``sdb``                   ``sdb_dirs``
Serializer   ``salt.serializers`` (:ref:`index <all-salt.serializers>`)       ``serializers`` [#no-fs]_ ``serializers_dirs``
SPM pkgdb    ``salt.spm.pkgdb``                                               ``pkgdb`` [#no-fs]_       ``pkgdb_dirs``
SPM pkgfiles ``salt.spm.pkgfiles``                                            ``pkgfiles`` [#no-fs]_    ``pkgfiles_dirs``
SSH Wrapper  ``salt.client.ssh.wrapper``                                      ``wrapper`` [#no-fs]_     ``wrapper_dirs``
State        ``salt.states`` (:ref:`index <all-salt.states>`)                 ``states``                ``states_dirs``
Thorium      ``salt.thorium`` (:ref:`index <all-salt.thorium>`)               ``thorium``               ``thorium_dirs``
Tokens       ``salt.tokens``                                                  ``tokens``                ``tokens_dirs``
Top          ``salt.tops`` (:ref:`index <all-salt.tops>`)                     ``tops``                  ``top_dirs``
Util         ``salt.utils``                                                   ``utils``                 ``utils_dirs``
Wheel        ``salt.wheels`` (:ref:`index <all-salt.wheel>`)                  ``wheel``                 ``wheel_dirs``
============ ================================================================ ========================= =====================

.. [#no-fs] These modules cannot be loaded from the Salt File Server.

.. note::
    While it is possible to import modules directly with the import statement,
    it is strongly recommended that the appropriate
    :ref:`dunder dictionary <dunder-dictionaries>` is used to access them
    instead. This is because a number of factors affect module names, module
    selection, and module overloading.

Auth
----

The auth module system allows for external authentication routines to be easily
added into Salt. The `auth` function needs to be implemented to satisfy the
requirements of an auth module. Use the ``pam`` module as an example.

See :ref:`External Authentication System <acl-eauth>` for more about
authentication in Salt.

Beacon
------

* :ref:`Writing Beacons <writing-beacons>`

Beacons are polled by the Salt event loop to monitor non-salt processes. See
:ref:`Beacons <beacons>` for more information about the beacon system.

Cache
-----

The minion cache is used by the master to store various information about
minions. See :ref:`Minion Data Cache <cache>` for more information.

Cloud
-----

Cloud modules are backend implementations used by :ref:`Salt Cloud <salt-cloud>`.

Engine
------

Engines are open-ended services managed by the Salt daemon (both master and
minion). They may interact with event loop, call other modules, or a variety of
non-salt tasks. See :ref:`Salt Engines <engines>` for complete details.

Execution
---------

.. toctree::
    :maxdepth: 1
    :glob:

    /ref/modules/index

Execution modules make up the core of the functionality used by Salt to
interact with client systems. The execution modules create the core system
management library used by all Salt systems, including states, which
interact with minion systems.

Execution modules are completely open ended in their execution. They can
be used to do anything required on a minion, from installing packages to
detecting information about the system. The only restraint in execution
modules is that the defined functions always return a JSON serializable
object.

Executor
--------

.. toctree::
    :maxdepth: 1
    :glob:

    /ref/executors/index

Executors control how execution modules get called. The default is to just call
them, but this can be customized.

File Server
-----------

The file server module system is used to create file server backends used by the
Salt Master. These modules need to implement the functions used in the
fileserver subsystem. Use the ``gitfs`` module as an example.

See :ref:`File Server Backends <file-server-backends>` for more information.

Grains
------

* :ref:`writing-grains`

Grain modules define extra routines to populate grains data. All defined
public functions will be executed and MUST return a Python dict object. The
dict keys will be added to the grains made available to the minion.

See :ref:`Grains <grains>` for more.

Log Handler
-----------

Log handlers allows the logs from salt (master or minion) to be sent to log
aggregation systems.

Matcher
-------

Matcher modules are used to define the :ref:`minion targeting expressions <targeting>`.
For now, it is only possible to override the :ref:`existing matchers <matchers>`
(the required CLI plumbing for custom matchers is not implemented yet).

Metaproxy
---------

Metaproxy is an abstraction layer above the existing proxy minion. It enables
adding different types of proxy minions that can still load existing proxymodules.

Net API
-------

Net API modules are the actual server implementation used by Salt API.

Output
------

The output modules supply the outputter system with routines to display data
in the terminal. These modules are very simple and only require the `output`
function to execute. The default system outputter is the ``nested`` module.

Pillar
------

.. toctree::
    :maxdepth: 1
    :glob:

    external_pillars

Used to define optional external pillar systems. The pillar generated via
the filesystem pillar is passed into external pillars. This is commonly used
as a bridge to database data for pillar, but is also the backend to the libvirt
state used to generate and sign libvirt certificates on the fly.

Proxy
-----

:ref:`Proxy Minions <proxy-minion>` are a way to manage devices that cannot run
a full minion directly.

Renderers
---------

Renderers are the system used to render sls files into salt highdata for the
state compiler. They can be as simple as the ``py`` renderer and as complex as
``stateconf`` and ``pydsl``.

Returners
---------

Returners are used to send data from minions to external sources, commonly
databases. A full returner will implement all routines to be supported as an
external job cache. Use the ``redis`` returner as an example.

Roster
------

The :ref:`Roster system <ssh-roster>` is used by Salt SSH to enumerate devices.

Runners
-------

.. toctree::
    :maxdepth: 1
    :glob:

    /ref/runners/index

Runners are purely master-side execution sequences.

SDB
---

* :ref:`Writing SDB Modules <sdb-writing-modules>`

SDB is a way to store data that's not associated with a minion. See 
:ref:`Storing Data in Other Databases <sdb>`.

Serializer
----------

Primarily used with :py:func:`file.serialize <salt.states.file.serialize>`.

State
-----

.. toctree::
    :maxdepth: 1
    :glob:

    /ref/states/index

State modules are used to define the state interfaces used by Salt States.
These modules are restrictive in that they must follow a number of rules to
function properly.

.. note::

    State modules define the available routines in sls files. If calling
    an execution module directly is desired, take a look at the `module`
    state.

SPM pkgdb
---------

* :ref:`SPM Development Guide: Package Database <spm-development-pkgdb>`

pkgdb modules provides storage backends to the package database.

SPM pkgfiles
------------

* :ref:`SPM Development Guide: Package Database <spm-development-pkgfiles>`

pkgfiles modules handle the actual installation.

SSH Wrapper
-----------

Replacement execution modules for :ref:`Salt SSH <salt-ssh>`.

Thorium
-------

Modules for use in the :ref:`Thorium <thorium-reactor>` event reactor.

Tokens
------

Token stores for :ref:`External Authentication <acl-eauth>`. See the
:py:mod:`salt.tokens` docstring for details.

.. note::
    The runner to load tokens modules is
    :py:func:`saltutil.sync_eauth_tokens <salt.runners.saltutil.sync_eauth_tokens>`.

Tops
----

Tops modules are used to convert external data sources into top file data for
the state system.

Util
----

Just utility modules to use with other modules via ``__utils__`` (see 
:ref:`Dunder Dictionaries <dunder-dictionaries>`).

Wheel
-----

The wheel system is used to manage master side management routines. These
routines are primarily intended for the API to enable master configuration.
