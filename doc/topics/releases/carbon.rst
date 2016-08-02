:orphan:

====================================
Salt Release Notes - Codename Carbon
====================================

Features
========

- Minions can run in stand-alone mode to use beacons and engines without
  having to connect to a master. (Thanks @adelcast!)
- Added a ``salt`` runner to allow running salt modules via salt-run.

    .. code-block:: bash

        salt-run salt.cmd test.ping
        # call functions with arguments and keyword arguments
        salt-run salt.cmd test.arg 1 2 3 a=1
- Added SSL support to Cassandra CQL returner.
  SSL can be enabled by setting ``ssl_options`` for the returner.
  Also added support for specifying ``protocol_version`` when establishing
  cluster connection.
- The ``mode`` parameter in the :py:mod:`file.managed
  <salt.states.file.managed>` state, and the ``file_mode`` parameter in the
  :py:mod:`file.recurse <salt.states.file.recurse>` state, can both now be set
  to ``keep`` and the minion will keep the mode of the file from the Salt
  fileserver. This works only with files coming from sources prefixed with
  ``salt://``, or files local to the minion (i.e. those which are absolute
  paths, or are prefixed with ``file://``). For example:

  .. code-block:: yaml

      /etc/myapp/myapp.conf:
        file.managed:
          - source: salt://conf/myapp/myapp.conf
          - mode: keep

      /var/www/myapp:
        file.recurse:
          - source: salt://path/to/myapp
          - dir_mode: 755
          - file_mode: keep

Config Changes
==============

The following default config values were changed:

- ``gitfs_ssl_verify``: Changed from ``False`` to ``True``
- ``git_pillar_ssl_verify``: Changed from ``False`` to ``True``
- ``winrepo_ssl_verify``: Changed from ``False`` to ``True``

Grains Changes
==============

- All core grains containing ``VMWare`` have been changed to ``VMware``, which
  is the `official capitalization <https://www.vmware.com>`_.  Additionally,
  all references to ``VMWare`` in the documentation have been changed to
  ``VMware`` :issue:`30807`.  Environments using versions of Salt before and
  after Salt Carbon should employ case-insensitive grain matching on these
  grains.

  .. code-block:: jinja

      {% set on_vmware = grains['virtual'].lower() == 'vmware' %}


- On Windows the ``cpu_model`` grain has been changed to provide the actual cpu
  model name and not the cpu family.

  Old behavior:

  .. code-block:: bash

      root@master:~# salt 'testwin200' grains.item cpu_model
      testwin200:
          ----------
          cpu_model:
              Intel64 Family 6 Model 58 Stepping 9, GenuineIntel

  New behavior:

  .. code-block:: bash

      root@master:~# salt 'testwin200' grains.item cpu_model
      testwin200:
          ----------
          cpu_model:
              Intel(R) Core(TM) i7-3520M CPU @ 2.90GHz


Beacons Changes
===============

- The ``loadavg`` beacon now outputs averages as integers instead of strings.
  (Via :issuse:`31124`.)

Runner Changes
==============

- Runners can now call out to :ref:`utility modules <writing-utility-modules>`
  via ``__utils__``.
- ref:`Utility modules <writing-utility-modules>` (placed in
  ``salt://_utils/``) are now able to be synced to the master, making it easier
  to use them in custom runners. A :py:mod:`saltutil.sync_utils
  <salt.runners.saltutil.sync_utils>` function has been added to the
  :py:mod:`saltutil runner <salt.runners.saltutil>` to faciliate the syncing of
  utility modules to the master.

Pillar Changes
==============

- Thanks to the new :py:mod:`saltutil.sync_utils
  <salt.runners.saltutil.sync_utils>` runner, it is now easier to get
  ref:`utility modules <writing-utility-modules>` synced to the correct
  location on the Master so that they are available in execution modules called
  from Pillar SLS files.

Returner Changes
================

- Any returner which implements a `save_load` function is now required to
  accept a `minions` keyword argument. All returners which ship with Salt
  have been modified to do so.

External Module Packaging
=========================

Modules may now be packaged via entry-points in setuptools. See
:doc:`external module packaging </topics/tutorials/packaging_modules>` tutorial
for more information.

Functionality Changes
=====================

- The ``onfail`` requisite now uses OR logic instead of AND logic.
  :issue:`22370`
- The consul external pillar now strips leading and trailing whitespace.
  :issue:`31165`
- The win_system.py state is now case sensitive for computer names. Previously
  computer names set with a state were converted to all caps. If you have a
  state setting computer names with lower case letters in the name that has
  been applied, the computer name will be changed again to apply the case
  sensitive name.
- The ``mac_user.list_groups`` function in the ``mac_user`` execution module
  now lists all groups for the specified user, including groups beginning with
  an underscore. In previous releases, groups beginning with an underscore were
  excluded from the list of groups.
- A new option for minions called ``master_tries`` has been added. This
  specifies the number of times a minion should attempt to contact a master to
  attempt a connection.  This allows better handling of occasional master
  downtime in a multi-master topology.
- Nodegroups consisting of a simple list of minion IDs can now also be declared
  as a yaml list. The below two examples are equivalent:

  .. code-block:: yaml

      # Traditional way
      nodegroups:
        - group1: L@host1,host2,host3

      # New way (optional)
      nodegroups:
        - group1:
          - host1
          - host2
          - host3

Deprecations
============

- ``env`` to ``saltenv``

  All occurrences of ``env`` and some occurrences of ``__env__`` marked for
  deprecation in Salt Carbon have been removed.  The new way to use the salt
  environment setting is with a variable called ``saltenv``:

  .. code-block:: python

    def fcn(msg='', env='base', refresh=True, saltenv='base', **kwargs):

  has been changed to

  .. code-block:: python

    def fcn(msg='', refresh=True, saltenv='base', **kwargs):

  - If ``env`` (or ``__env__``) is supplied as a keyword argument to a function
    that also accepts arbitrary keyword arguments, then a new warning informs the
    user that ``env`` is no longer used if it is found.  This new warning will be
    removed in Salt Nitrogen.

    .. code-block:: python

      def fcn(msg='', refresh=True, saltenv='base', **kwargs):

    .. code-block:: python

      # will result in a warning log message
      fcn(msg='add more salt', env='prod', refresh=False)

  - If ``env`` (or ``__env__``) is supplied as a keyword argument to a function
    that does not accept arbitrary keyword arguments, then python will issue an
    error.

    .. code-block:: python

      def fcn(msg='', refresh=True, saltenv='base'):

    .. code-block:: python

      # will result in a python TypeError
      fcn(msg='add more salt', env='prod', refresh=False)

  - If ``env`` (or ``__env__``) is supplied as a positional argument to a
    function, then undefined behavior will occur, as the removal of ``env`` and
    ``__env__`` from the function's argument list changes the function's
    signature.

    .. code-block:: python

      def fcn(msg='', refresh=True, saltenv='base'):

    .. code-block:: python

      # will result in refresh evaluating to True and saltenv likely not being a string at all
      fcn('add more salt', 'prod', False)

- The ``boto_vpc`` execution module had two functions removed,
  ``boto_vpc.associate_new_dhcp_options_to_vpc`` and
  ``boto_vpc.associate_new_network_acl_to_subnet`` in favor of more concise function
  names, ``boto_vpc.create_dhcp_options`` and ``boto_vpc.create_network_acl``, respectively.

- The ``data`` execution module had ``getval`` and ``getvals`` functions removed
  in favor of one function, ``get``, which combines the functionality of the
  removed functions.

- The ``grains.cache`` runner no longer accpets ``outputter`` or ``minion`` as keyword arguments.
  Users will need to specify an outputter using the ``--out`` option. ``tgt`` is
  replacing the ``minion`` kwarg.

- The use of ``jid_dir`` and ``jid_load`` were removed from the
  ``salt.utils.jid``. ``jid_dir`` functionality for job_cache management was moved to
  the ``local_cache`` returner. ``jid_load`` data is now retreived from the
  ``master_job_cache``

- ``reg`` execution module

  Functions in the ``reg`` execution module had misleading and confusing names
  for dealing with the Windows registry. They failed to clearly differentiate
  between hives, keys, and name/value pairs. Keys were treated like value names.
  There was no way to delete a key.

  New functions were added in 2015.5 to properly work with the registry. They
  also made it possible to edit key default values as well as delete an entire
  key tree recursively. With the new functions in place, the following functions
  have been deprecated:

  - read_key
  - set_key
  - create_key
  - delete_key

  Use the following functions instead:

  - for ``read_key`` use ``read_value``
  - for ``set_key`` use ``set_value``
  - for ``create_key`` use ``set_value`` with no ``vname`` and no ``vdata``
  - for ``delete_key`` use ``delete_key_recursive``. To delete a value, use
    ``delete_value``.

- ``reg`` state module

  The ``reg`` state module was modified to work with the new functions in the
  execution module. Some logic was left in the ``reg.present`` and the
  ``reg.absent`` functions to handle existing state files that used the final
  key in the name as the value name. That logic has been removed so you now must
  specify value name (``vname``) and, if needed, value data (``vdata``).

  For example, a state file that adds the version value/data pair to the
  Software\\Salt key in the HKEY_LOCAL_MACHINE hive used to look like this:

  .. code-block:: yaml

      HKEY_LOCAL_MACHINE\\Software\\Salt\\version:
        reg.present:
          - value: 2016.3.1

  Now it should look like this:

  .. code-block:: yaml

      HKEY_LOCAL_MACHINE\\Software\\Salt
        reg.present:
          - vname: version
          - vdata: 2016.3.1

  A state file for removing the same value added above would have looked like
  this:

  .. code-block:: yaml

      HKEY_LOCAL_MACHINE\\Software\\Salt\\version:
        reg.absent:

  Now it should look like this:

  .. code-block:: yaml

      HKEY_LOCAL_MACHINE\\Software\\Salt
        reg.absent:
          - vname: version

  This new structure is important as it allows salt to deal with key default
  values which was not possible before. If vname is not passed, salt will work
  with the default value for that hive\key.

  Additionally, since you could only delete a value from a the state module, a
  new function (``key_absent``) has been added to allow you to delete a registry
  key and all subkeys and name/value pairs recursively. It uses the new
  ``delete_key_recursive`` function.

  For additional information see the documentation for the ``reg`` execution and
  state modules.
