===========================
Dynamic Module Distribution
===========================

.. versionadded:: 0.9.5

Salt python modules can be distributed automatically via the salt file server.
Under the root of any environment defined via the file_roots option on the
master server directories corresponding to the type of module can be used.

The directories are prepended with an underscore:

  1. _modules
  2. _grains
  3. _renderers
  4. _returners
  5. _states

The contents of these directories need to be synced over to the minions after
python modules have been created in them. There are a number of ways to sync
the modules.

Sync Via States
===============

The minion configuration contains an option ``autoload_dynamic_modules``
which defaults to True. This option makes the state system refresh all
dynamic modules when states are run. To disable this behavior set
``autoload_dynamic_modules`` to False in the minion config.

Sync Via the saltutil Module
============================

The saltutil module has a number of functions that can be used to sync all
or specific dynamic modules. The saltutil module function ``saltutil.sync_all``
will sync all module types over to a minion. For more information see:
:mod:`salt.modules.saltutil`
