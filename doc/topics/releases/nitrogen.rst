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
