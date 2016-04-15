.. _module-sync:
.. _dynamic-module-distribution:

===========================
Dynamic Module Distribution
===========================

.. versionadded:: 0.9.5

Custom Salt execution, state, and other modules can be distributed to Salt
minions using the Salt file server.

Under the root of any environment defined via the :conf_master:`file_roots`
option on the master server directories corresponding to the type of module can
be used.

The directories are prepended with an underscore:

- :file:`_beacons`
- :file:`_engines`
- :file:`_grains`
- :file:`_modules`
- :file:`_output`
- :file:`_proxy`
- :file:`_renderers`
- :file:`_returners`
- :file:`_states`
- :file:`_utils`

The contents of these directories need to be synced over to the minions after
Python modules have been created in them. There are a number of ways to sync
the modules.

Sync Via States
===============

The minion configuration contains an option ``autoload_dynamic_modules``
which defaults to ``True``. This option makes the state system refresh all
dynamic modules when states are run. To disable this behavior set
:conf_minion:`autoload_dynamic_modules` to ``False`` in the minion config.

When dynamic modules are autoloaded via states, modules only pertinent to
the environments matched in the master's top file are downloaded.

This is important to remember, because modules can be manually loaded from
any specific environment that environment specific modules will be loaded
when a state run is executed.

Sync Via the saltutil Module
============================

The saltutil module has a number of functions that can be used to sync all
or specific dynamic modules. The saltutil module function ``saltutil.sync_all``
will sync all module types over to a minion. For more information see:
:mod:`salt.modules.saltutil`
