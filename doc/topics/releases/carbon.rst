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
