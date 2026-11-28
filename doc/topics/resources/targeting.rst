.. _targeting-resources:
.. _resources-targeting:

================================
Targeting Salt Resources
================================

.. versionadded:: 3008.0

A *Salt resource* is something a minion manages on behalf of the master —
an SSH host, a virtual appliance, an external API endpoint — addressed
by an id of the operator's choosing. Resources extend Salt's targeting
system with selectors for resource IDs, types, grains, and managing minions.

This page is the targeting reference. For the conceptual introduction
see :ref:`resources`; for the registry and dispatch plumbing see
:ref:`resources-architecture`.


Targeting forms
===============

A command returns one entry per matched minion or resource ID.

Glob and exact-id
-----------------

A wildcard glob matches resource IDs directly::

    salt 'web-*' test.ping

A top-level wildcard glob also includes every resource managed by a
matching minion::

    salt '*' test.ping

A specific bare id matches a resource directly::

    salt 'web-01' test.ping

A specific minion ID targets the minion itself::

    salt 'minion-1' test.ping

Regular expressions use ``-E`` directly or ``E@`` in a compound target::

    salt -E '^web-0[12]$' test.ping


Compound ``T@`` (resource type)
-------------------------------

``T@<type>`` matches every resource of the given type::

    salt -C 'T@ssh' state.apply

``T@<type>:<id>`` targets exactly one resource::

    salt -C 'T@ssh:web-01' test.ping


Managing minion ``M@``
-----------------------

In a compound target, combine ``M@<minion-id>`` with a resource selector
to match resources managed by that minion::

    salt -C 'M@minion-1 and T@ssh' test.ping

By itself, ``M@minion-1`` matches the managing minion.

Resource ownership
------------------

A resource's type and ID identify its registered owner. If another minion
claims the same type and ID, the master logs the conflict and keeps the
existing owner. Remove the resource from that minion's inventory and
refresh registration before moving it to a new managing minion.

Use unique bare IDs for devices you address without a type. If a bare ID
is used by multiple resource types, use a single ``T@<type>:<id>``
selector. Publications without a clear type skip ambiguous Resource IDs.

Grain-based ``-G`` / ``G@``
---------------------------

A resource carries its own grains, produced by the ``grains`` function
in the resource's connection module (e.g.
:func:`salt.resource.dummy.grains`). The master records each minion's
per-resource grain dicts in the ``resource_grains`` cache bank when the
minion registers. The master learns the resource types from these
registrations. ``salt -G`` matches against both the resource and minion
grain caches::

    salt -G 'environment:prod' test.ping

Compound ``G@`` works the same way and supports the full boolean
algebra (``and``, ``or``, ``not``, parens)::

    salt -C 'G@environment:prod and G@role:web' state.apply
    salt -C 'T@ssh and not G@environment:staging' test.ping

The boolean form is evaluated **per resource**, so a compound matches a
resource iff that resource's identity and grains satisfy the entire
expression.


PCRE grain ``-P`` / ``P@``
--------------------------

Identical semantics to ``-G`` / ``G@`` but values are regex patterns::

    salt -P 'environment:^production-.*' test.ping
    salt -C 'P@environment:^production-.*' state.apply


List ``-L`` / ``L@``
--------------------

A bare resource id appearing in a list expression matches::

    salt -L 'web-01,web-02,db-01' test.ping
    salt -C 'T@ssh and L@web-01,web-02,db-01' test.ping


Pillar ``-I`` / ``I@``
----------------------

.. note::

    Pillar-based targeting of resources is **not** wired up. Resources
    do not carry per-resource pillar data today. ``-I`` and ``I@`` only
    match minions; resources are skipped silently. This is tracked as
    future work — see the gap notes in
    :py:mod:`salt.utils.resource_registry`.


How master and minion split the work
====================================

Master side
-----------

The master's ``CkMinions`` augments grain matches with resource ids
read from the ``resource_grains`` cache bank. The augment runs for
``-G``, ``-P``, and any ``G@`` / ``P@`` term inside a compound. The
matched bare resource ids are added to the response wait set so the
master accepts the corresponding returns. For transports that use publish topics,
the master also routes glob, list, and regex jobs to the matched resources'
managing minions. The original target expression determines what runs.

Minion side
-----------

When a publish arrives, the minion's ``_resolve_resource_targets``
walks every locally managed resource and decides, **per resource**,
whether the targeting expression matches. For glob / list / ``T@``
this is a string match; for ``G@`` / ``P@`` the minion uses the
grains it cached during its last registration; for compound, the
minion evaluates the full boolean expression against each resource's
identity and grains.

Each matched resource gets its own job dispatch with ``__grains__``
swapped to the resource's grain dict (so ``salt 'web-01' grains.items``
returns ``web-01``'s grains, not the managing minion's).


Freshness and refresh
=====================

The master's ``resource_grains`` bank is updated only when a minion
re-registers via ``_register_resources_with_master``. Triggers that
re-register are:

* Minion start / reconnect (``tune_in``);
* A ``saltutil.refresh_pillar`` (the minion's pillar refresh handler
  re-discovers resources before re-registering); and
* The ``resource_refresh`` event on the minion event bus.

A per-resource ``<type>.grains_refresh()`` invocation does **not**
auto-propagate to the master. To force the master's view to refresh
without waiting for a pillar refresh, fire the ``resource_refresh``
event for the relevant minion::

    salt-run resource.refresh minion=resources-minion

That runner publishes ``minion/<id>/resource_refresh`` on the master
event bus; the minion's handler re-runs resource discovery and
re-publishes its full grain set.


Operator inspection
===================

Two read-only runners expose what the master sees:

.. code-block:: bash

    # Show every SRN currently in the resource_grains bank with a
    # one-line summary (top-level grain keys + count).
    salt-run resource.list_grains

    # Show the full grain dict for one resource.
    salt-run resource.show_grains type=ssh id=web-01

When ``salt -G '<key>:<value>' test.ping`` returns less than expected,
``resource.list_grains`` is the first place to check: if a resource
isn't in the bank, the master will not match it, and the resource needs
a ``saltutil.refresh_pillar`` (or a ``resource.refresh``) on its
managing minion.
