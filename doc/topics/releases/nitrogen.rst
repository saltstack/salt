:orphan:

======================================
Salt Release Notes - Codename Nitrogen
======================================

Grains Changes
==============

- The ``os_release`` grain has been changed from a string to an integer.
  State files, especially those using a templating language like Jinja
  may need to be adjusted to account for this change.
- Add ability to specify disk backing mode in the VMWare salt cloud profile.

Execution Module Changes
========================

- The ``refresh`` kwarg for the ``list_upgrades`` function in the ``solarisips``
  package module default value has been changed from ``True`` to ``False``. This
  makes the function more consistent with all of the other package execution
  modules. All other ``pkg.list_upgrades`` functions already default to ``True``.
