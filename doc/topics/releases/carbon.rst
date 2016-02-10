:orphan:

====================================
Salt Release Notes - Codename Carbon
====================================

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

- The ``loadavg`` beacon now outputs averages as integers instead of strings.
  (Via :issuse:`31124`.)

Deprecations
============

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

reg execution module
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

reg state module
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
