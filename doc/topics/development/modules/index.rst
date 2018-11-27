===============
Modular Systems
===============

When first working with Salt, it is not always clear where all of the modular
components are and what they do. Salt comes loaded with more modular systems
than many users are aware of, making Salt very easy to extend in many places.

The most commonly used modular systems are execution modules and states. But
the modular systems extend well beyond the more easily exposed components
and are often added to Salt to make the complete system more flexible.

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

These will be eventually picked up by minions, or users can use
the ``saltutil.sync_*`` :py:mod:`execution functions <salt.modules.saltutil>`
and :py:mod:`runner functions <salt.runners.saltutil>` to force it immediately.

The name of the directory inside of the file server is the directory name
prepended by ``_``.

Using saltenvs besides ``base`` may not work in all contexts.

The extmods Directory
---------------------

Any files places in the directory set by ``extension_modules`` settings
(:conf_minion:`minion <extension_modules>`,
:conf_master:`master <extension_modules>`, default
``/var/cache/salt/*/extmods``) can also be loaded as modules. Note that these
directories are also used by the ``saltutil.sync_*`` functions (mentioned
above).

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

Note that these are not synced from the Salt Master to the Minion. They must be
installed indepdendently on the Minion.

Names
-----

The specific names for each of these methods are as follows. See sections below
for a short summary of each of these systems.

============ ================================================================ ========================= =====================
Module Type  Salt Package Name                                                Directory Name            Entry Point
============ ================================================================ ========================= =====================
Auth         ``salt.auth`` (:ref:`index <external-logging-handlers>`)         ``auth`` [#no-fs]_        ``auth_dirs``
Beacon       ``salt.beacons`` (:ref:`index <beacons>`)                        ``beacons``               ``beacons_dirs``
Cache        ``salt.cache`` (:ref:`index <all-salt.cache>`)                   ``cache``                 ``cache_dirs``
Cloud        ``salt.cloud.clouds`` (:ref:`index <all-salt.clouds>`)           ``clouds``                ``cloud_dirs``
Engine       ``salt.engines`` (:ref:`index <engines>`)                        ``engines``               ``engines_dirs``
Executor     ``salt.executors`` (:ref:`index <all-salt_executors>`)           ``executors`` [#no-fs]_   ``executor_dirs``
Execution    ``salt.modules`` (:ref:`index <all-salt.modules>`)               ``modules``               ``module_dirs``
File Server  ``salt.fileserver`` (:ref:`index <file-server>`)                 ``fileserver`` [#no-fs]_  ``fileserver_dirs``
Grain        ``salt.grains`` (:ref:`index <all-salt.grains>`)                 ``grains``                ``grains_dirs``
Log Handler  ``salt.log.handlers`` (:ref:`index <external-logging-handlers>`) ``log_handlers``          ``log_handlers_dirs``
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
Search       ``salt.search``                                                  ``search`` [#no-fs]_      ``search_dirs``
Serializer   ``salt.serializers`` (:ref:`index <all-salt.serializers>`)       ``serializers`` [#no-fs]_ ``serializers_dirs``
SPM pkgdb    ``salt.spm.pkgdb``                                               ``pkgdb`` [#no-fs]_       ``pkgdb_dirs``
SPM pkgfiles ``salt.spm.pkgfiles``                                            ``pkgfiles`` [#no-fs]_    ``pkgfiles_dirs``
SSH Wrapper  ``salt.client.ssh``                                              ``wrapper`` [#no-fs]_     ``wrapper_dirs``
State        ``salt.states`` (:ref:`index <all-salt.states>`)                 ``states``                ``states_dirs``
Thorium      ``salt.thorium`` (:ref:`index <all-salt.thorium>`)               ``thorium`` [#no-fs]_     ``thorium_dirs``
Top          ``salt.tops`` (:ref:`index <all-salt.tops>`)                     ``tops``                  ``top_dirs``
Util         ``salt.utils``                                                   ``utils``                 ``utils_dirs``
Wheel        ``salt.wheels`` (:ref:`index <all-salt.wheel>`)                  ``wheel``                 ``wheel_dirs``
============ ================================================================ ========================= =====================

.. [#no-fs] These modules cannot be loaded from the Salt File Server.

Execution Modules
=================

Execution modules make up the core of the functionality used by Salt to
interact with client systems. The execution modules create the core system
management library used by all Salt systems, including states, which
interact with minion systems.

Execution modules are completely open ended in their execution. They can
be used to do anything required on a minion, from installing packages to
detecting information about the system. The only restraint in execution
modules is that the defined functions always return a JSON serializable
object.

For a list of all built in execution modules, click :ref:`here
<all-salt.modules>`

For information on writing execution modules, see :ref:`this page
<writing-execution-modules>`.


Interactive Debugging
=====================

Sometimes debugging with ``print()`` and extra logs sprinkled everywhere is not
the best strategy.

IPython is a helpful debug tool that has an interactive python environment
which can be embedded in python programs.

First the system will require IPython to be installed.

.. code-block:: bash

    # Debian
    apt-get install ipython

    # Arch Linux
    pacman -Syu ipython2

    # RHEL/CentOS (via EPEL)
    yum install python-ipython


Now, in the troubling python module, add the following line at a location where
the debugger should be started:

.. code-block:: python

    test = 'test123'
    import IPython; IPython.embed_kernel()

After running a Salt command that hits that line, the following will show up in
the log file:

.. code-block:: text

    [CRITICAL] To connect another client to this kernel, use:
    [IPKernelApp] --existing kernel-31271.json

Now on the system that invoked ``embed_kernel``, run the following command from
a shell:

.. code-block:: bash

    # NOTE: use ipython2 instead of ipython for Arch Linux
    ipython console --existing

This provides a console that has access to all the vars and functions, and even
supports tab-completion.

.. code-block:: python

    print(test)
    test123

To exit IPython and continue running Salt, press ``Ctrl-d`` to logout.


State Modules
=============

State modules are used to define the state interfaces used by Salt States.
These modules are restrictive in that they must follow a number of rules to
function properly.

.. note::

    State modules define the available routines in sls files. If calling
    an execution module directly is desired, take a look at the `module`
    state.

Auth
====

The auth module system allows for external authentication routines to be easily
added into Salt. The `auth` function needs to be implemented to satisfy the
requirements of an auth module. Use the ``pam`` module as an example.

Fileserver
==========

The fileserver module system is used to create fileserver backends used by the
Salt Master. These modules need to implement the functions used in the
fileserver subsystem. Use the ``gitfs`` module as an example.

Grains
======

Grain modules define extra routines to populate grains data. All defined
public functions will be executed and MUST return a Python dict object. The
dict keys will be added to the grains made available to the minion.

Output
======

The output modules supply the outputter system with routines to display data
in the terminal. These modules are very simple and only require the `output`
function to execute. The default system outputter is the ``nested`` module.

Pillar
======

Used to define optional external pillar systems. The pillar generated via
the filesystem pillar is passed into external pillars. This is commonly used
as a bridge to database data for pillar, but is also the backend to the libvirt
state used to generate and sign libvirt certificates on the fly.

Renderers
=========

Renderers are the system used to render sls files into salt highdata for the
state compiler. They can be as simple as the ``py`` renderer and as complex as
``stateconf`` and ``pydsl``.

Returners
=========

Returners are used to send data from minions to external sources, commonly
databases. A full returner will implement all routines to be supported as an
external job cache. Use the ``redis`` returner as an example.

Runners
=======

Runners are purely master-side execution sequences.

Tops
====

Tops modules are used to convert external data sources into top file data for
the state system.

Wheel
=====

The wheel system is used to manage master side management routines. These
routines are primarily intended for the API to enable master configuration.
