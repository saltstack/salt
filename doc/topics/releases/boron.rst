:orphan:

===================================
Salt Release Notes - Codename Boron
===================================

Backwards-incompatible Changes
==============================

- The default path for the :conf_master:`extension_modules` master config
  option has been changed.  Prior to this release, the location was a directory
  named ``extmods`` in the Salt cachedir. On most platforms, this would put the
  :conf_master:`extension_modules` directory in ``/var/cache/salt/extmods``.
  It has been moved one directory down, into the master cachedir. On most
  platforms, this is ``/var/cache/salt/master/extmods``. Most users won't have
  to worry about this, but those who have been manually placing custom runners
  into ``/var/cache/salt/extmods/runners``, or ouputters into
  ``/var/cache/salt/extmods/output``, etc. will be affected by this. To
  transition, it is recommended not to simply move the extmods directory into
  ``/var/cache/salt/master``, but to copy the custom modules into the salt
  fileserver under ``salt://_runners``, ``salt://_output``, etc. and sync them
  using the functions in the new :mod:`saltutil runner
  <salt.runners.saltutil>`.


Core Changes
============

- The onchanges requisite now fires if _any_ watched state changes. Refs #19592.
- The ``ext_pillar`` functions **must** now accept a minion ID as the first
  argument. This stops the deprecation path started in Salt 0.17.x. Before this
  minion ID first argument was introduced, the minion ID could be retrieved
  accessing ``__opts__['id']`` loosing the reference to the master ID initially
  set in opts. This is no longer the case, ``__opts__['id']`` will be kept as
  the master ID.
- Custom types can now be synced to the master using the new :mod:`saltutil
  runner <salt.runners.saltutil>`. Before, these needed to manually be placed
  under the :conf_master:`extension_modules` directory. This allows custom
  modules to easily be synced to the master to make them available when
  compiling Pillar data. Just place custom runners into ``salt://_runners``,
  custom outputters into ``salt://_output``, etc. and use the functions from
  the :mod:`saltutil runner <salt.runners.saltutil>` to sync them.


Cloud Changes
=============

- Refactored the OpenNebula driver and added numerous ``--function``s and
  ``--action``s to enhance Salt support for image, template, security group,
  virtual network and virtual machine management in OpenNebula.


Platform Changes
================

- Renamed modules related to OS X. The following module filenames were changed.
  The virtual name remained unchanged.

- **PR** `#30558`_: renamed osxdesktop.py to mac_desktop.py
- **PR** `#30557`_: renamed macports.py to mac_ports.py
- **PR** `#30556`_: renamed darwin_sysctl.py to mac_sysctl.py
- **PR** `#30555`_: renamed brew.py to mac_brew.py
- **PR** `#30552`_: renamed darwin_pkgutil.py to mac_pkgutil.py

.. _`#30558`: https://github.com/saltstack/salt/pull/30558
.. _`#30557`: https://github.com/saltstack/salt/pull/30557
.. _`#30556`: https://github.com/saltstack/salt/pull/30556
.. _`#30555`: https://github.com/saltstack/salt/pull/30555
.. _`#30552`: https://github.com/saltstack/salt/pull/30552
