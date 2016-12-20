:orphan:

======================================
Salt Release Notes - Codename Nitrogen
======================================

States Added for Management of systemd Unit Masking
===================================================

The :py:func:`service.masked <salt.states.service.masked>` and
:py:func:`service.umasked <salt.states.service.unmasked>` states have been
added to allow Salt to manage masking of systemd units.

Additionally, the following functions in the :mod:`systemd
<salt.modules.systemd>` execution module have changed to accomodate the fact
that indefinite and runtime masks can co-exist for the same unit:

- :py:func:`service.masked <salt.modules.systemd.masked>` - The return from
  this function has changed from previous releases. Before, ``False`` would be
  returned if the unit was not masked, and the output of ``systemctl is-enabled
  <unit name>`` would be returned if the unit was masked. However, since
  indefinite and runtime masks can exist for the same unit at the same time,
  this function has been altered to accept a ``runtime`` argument. If ``True``,
  the minion will be checked for a runtime mask assigned to the named unit. If
  ``False``, then the minion will be checked for an indefinite mask. If one is
  found, ``True`` will be returned. If not, then ``False`` will be returned.
- :py:func:`service.masked <salt.modules.systemd.masked>` - This function used
  to just run ``systemctl is-enabled <unit name>`` and based on the return
  from this function the corresponding mask type would be removed. However, if
  both runtime and indefinite masks are set for the same unit, then ``systemctl
  is-enabled <unit name>`` would show just the indefinite mask. The indefinite
  mask would be removed, but the runtime mask would remain. The function has
  been modified to accept a ``runtime`` argument, and will attempt to remove a
  runtime mask if that argument is set to ``True``. If set to ``False``, it
  will attempt to remove an indefinite mask.

These new ``runtime`` arguments default to ``False``.

Grains Changes
==============

- The ``os_release`` grain has been changed from a string to an integer.
  State files, especially those using a templating language like Jinja
  may need to be adjusted to account for this change.
- Add ability to specify disk backing mode in the VMWare salt cloud profile.

Execution Module Changes
========================

- In the :mod:`solarisips <salt.modules.solarisips>` ``pkg`` module, the
  default value for the ``refresh`` argument to the ``list_upgrades`` function
  has been changed from ``False`` to ``True``. This makes the function more
  consistent with all of the other ``pkg`` modules (The other
  ``pkg.list_upgrades`` functions all defaulted to ``True``).
- The functions which handle masking in the :mod:`systemd
  <salt.modules.systemd>` module have changed. These changes are described
  above alongside the information on the new states which have been added to
  manage masking of systemd units.

Master Configuration Additions
==============================

- ``syndic_forward_all_events``: Option on multi-syndic or single when connected
  to multiple masters to be able to send events to all connected masters.

Python API Changes
==================

The :ref:`LocalClient <local-client>`'s ``expr_form`` argument has been
deprecated and renamed to ``tgt_type``. This change was made due to numerous
reports of confusion among community members, since the targeting method is
published to minions as ``tgt_type``, and appears as ``tgt_type`` in the job
cache as well.

While ``expr_form`` will continue to be supported until the **Fluorine**
release cycle (two major releases after this one), those who are using the
:ref:`LocalClient <local-client>` (either directly, or implictly via a
:ref:`netapi module <all-netapi-modules>`) are encouraged to update their code
to use ``tgt_type``.


Deprecations
============

General Deprecations
--------------------

- Beacon configurations should be lists instead of dictionaries.
- The ``PidfileMixin`` has been removed. Please use ``DaemonMixIn`` instead.

Configuration Option Deprecations
---------------------------------

- The ``client_acl`` configuration option has been removed. Please use
  ``publisher_acl`` instead.
- The ``client_acl_blacklist`` configuration option has been removed.
  Please use ``publisher_acl_blacklist`` instead.
- The ``win_gitrepos`` configuration option has been removed. Please use
  the ``winrepo_remotes`` option instead.
- The ``win_repo`` configuration option has been removed. Please use
  ``winrepo_dir`` instead.
- The ``win_repo_mastercachefile`` configuration option has been removed.
  Please use the ``winrepo_cachefile`` option instead.

Module Deprecations
-------------------

- The ``win_repo_source_dir`` option has been removed from the ``win_repo``
  module. Please use ``winrepo_source_dir`` instead.

Pillar Deprecations
-------------------

- Support for the ``raw_data`` argument for the file_tree ext_pillar has been
  removed. Please use ``keep_newline`` instead.
- SQLite3 database connection configuration previously had keys under
  pillar. This legacy compatibility has been removed.

Proxy Minion Deprecations
-------------------------

- The ``proxy_merge_grains_in_module`` default has been switched from
  ``False`` to ``True``.

Salt-API Deprecations
---------------------

- The ``SaltAPI.run()`` function has been removed. Please use the
  ``SaltAPI.start()`` function instead.

Salt-Cloud Deprecations
-----------------------

- Support for using the keyword ``provider`` in salt-cloud provider config
  files has been removed. Please use ``driver`` instead. The ``provider``
  keyword should now only be used in cloud profile config files.

Salt-SSH Deprecations
---------------------

- The ``wipe_ssh`` option for ``salt-ssh`` has been removed. Please use the
  ``ssh_wipe`` option instead.

State Deprecations
------------------

The ``apache_conf`` state had the following functions removed:

  - ``disable``: Please use ``disabled`` instead.
  - ``enable``: Please use ``enabled`` instead.

The ``apache_module`` state had the following functions removed:

  - ``disable``: Please use ``disabled`` instead.
  - ``enable``: Please use ``enabled`` instead.

The ``apache_site`` state had the following functions removed:

  - ``disable``: Please use ``disabled`` instead.
  - ``enable``: Please use ``enabled`` instead.

- The ``chocolatey`` state had the following functions removed:

  - ``install``: Please use ``installed`` instead.
  - ``uninstall``: Please use ``uninstalled`` instead.
