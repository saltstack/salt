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
  ``associate_new_dhcp_options_to_vpc`` and
  ``associate_new_network_acl_to_subnet`` in favor of more concise function
  names, ``create_dhcp_options`` and ``create_network_acl``, respectively.

- The ``data`` execution module had ``getval`` and ``getvals`` functions removed
  in favor of one function, ``get``, which combines the functionality of the
  removed functions.

- The ``cache`` runner no longer accpets ``outputter`` or ``minion`` as keyword arguments.
  Users will need to specify an outputter using the ``--out`` option. ``tgt`` is
  replacing the ``minion`` kwarg.

- The use of ``jid_dir`` and ``jid_load`` were removed from the
  ``salt.utils.jid``. ``jid_dir`` functionality for job_cache management was moved to
  the ``local_cache`` returner. ``jid_load`` data is now retreived from the
  ``master_job_cache``
