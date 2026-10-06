.. _resources-operations:

==========
Operations
==========

.. versionadded:: 3008.0

Day-to-day operator reference: how to refresh the master's view, how to
inspect what's registered, how to run jobs from ``salt-call`` against
resources.


Refreshing the master's view
============================

The master only knows about resources a minion has registered. Three
events trigger a re-registration:

1. **Minion start or reconnect**. ``tune_in`` calls
   ``_register_resources_with_master`` after pillar is compiled.
2. **A pillar refresh on the minion**.
   ``saltutil.refresh_pillar`` re-runs resource discovery and
   re-publishes.
3. **The** ``resource_refresh`` **event on the minion event bus**.
   Fired by the master-side ``resource.refresh`` runner — see below.

Per-resource ``grains_refresh()`` calls inside the connection module
do **not** auto-propagate to the master. To force the master to pick
up new grains without waiting for a pillar refresh::

    salt-run resource.refresh minion=resources-minion

The runner publishes ``minion/<id>/resource_refresh`` on the master
event bus; the minion's handler re-runs ``_discover_resources`` and
publishes the full resource grain set. Use this when a resource's
underlying state changes out-of-band — e.g. you ran
``ss_env.refresh()`` directly on the host and the new metadata isn't
yet visible to ``salt -G``.


Inspecting the master's resource view
=====================================

Two read-only runners surface what's in the registry. Useful for
"why didn't my ``-G`` target match this resource?" debugging.

``salt-run resource.list_grains``
   Lists every SRN (``"<type>:<id>"``) currently in the master's
   ``resource_grains`` cache bank, with a one-line summary of each
   resource's grain keys.

   .. code-block:: bash

       salt-run resource.list_grains

       # ssh:web-01:
       #   grain_count: 4
       #   grain_keys: [env, host, role, ssh_user]
       # dummy:dummy-01:
       #   grain_count: 4
       #   grain_keys: [dummy_grain_1, dummy_grain_2, dummy_grain_3, resource_id]

   If a resource you expect to see is missing, the minion managing it
   hasn't registered yet — check minion logs for a registration
   failure or run ``resource.refresh`` against that minion.

``salt-run resource.show_grains``
   Returns the full grain dict for one resource. Pair this with a
   listing to inspect specific values.

   .. code-block:: bash

       salt-run resource.show_grains type=ssh id=web-01


Targeting from the operator side
================================

Every targeting form Salt supports against minions works against
resources too. See :ref:`resources-targeting` for the full reference;
the highlights:

.. code-block:: bash

    # Glob target — matches both the managing minion and its resources
    salt '*' test.ping

    # Targeting a single resource by bare id
    salt 'web-01' test.ping

    # All resources of a type
    salt -C 'T@ssh' test.ping

    # One specific resource
    salt -C 'T@ssh:web-01' state.apply mysls

    # By per-resource grain
    salt -G 'env:prod' test.ping
    salt -C 'G@env:prod and T@ssh' state.apply nginx


``salt-call`` and resources
===========================

By default ``salt-call`` runs functions on the **managing minion
only** — resources are not dispatched. This preserves single-bare-value
return semantics for the existing universe of ``salt-call`` callers.

To opt **in** to resource dispatch from ``salt-call``, use the
``-r`` / ``--resources`` flag added in 3008.0:

.. code-block:: bash

    # Default — managing minion only, single bare value
    salt-call test.ping
    # → True

    # Resources enabled — managing minion + every managed resource
    salt-call -r test.ping
    # → {<managing-minion-id>: True, "web-01": True, "web-02": True, ...}

    # Resources enabled with a target
    salt-call -r --tgt web-01 test.ping
    # → True   (single match → bare value)

    salt-call -r --tgt 'T@ssh' --tgt-type compound state.apply mysls

    salt-call -r --tgt 'env:prod' --tgt-type grain test.ping

The ``--tgt`` and ``--tgt-type`` flags mirror the master CLI's
``-t``/``--target-type`` model. Default target is ``*`` (everything
the minion manages); default target type is ``glob``.

For more on the supported target types, see :ref:`resources-targeting`.


Forcing re-registration without a master
=========================================

A masterless ``salt-call`` can refresh its own resource view too. The
sequence is:

.. code-block:: bash

    salt-call saltutil.refresh_pillar
    salt-call -r --tgt '*' test.ping

The pillar refresh re-runs each resource type's ``discover()`` and
``grains()``. In masterless mode there's no master registry to update,
but the *minion's own* view of which resources exist is rebuilt.


Common debugging recipes
========================

**Resource not matching** ``-G env:prod``
   1. ``salt-run resource.list_grains`` — is the resource in the bank?
   2. If not: ``salt-run resource.refresh minion=<owner>``.
   3. If yes: ``salt-run resource.show_grains type=<t> id=<r>`` — does
      ``env`` actually equal ``prod`` in the registered grains? The
      managing minion's ``grains()`` is what produced this value;
      check the connection module.

**"Function X is not supported for resource type Y"**
   The per-resource loader doesn't have function ``X`` for type ``Y``.
   Either the type doesn't ship that function, or ``saltutil.sync_all``
   on the managing minion is overdue. Sync, refresh pillar, retry.

**State output missing per-resource blocks**
   For merge-mode functions, all results fold into a single combined
   return on the managing minion. If you see only one block when you
   expected several, check that the target expression actually
   matched multiple resources (``salt-run resource.list_grains``).

**Resource registry seems stale after a master restart**
   The registry is on-disk and survives restarts. If a minion
   restarted at the same time, give it 60 seconds to reconnect and
   re-register, then re-check with ``salt-run resource.list_grains``.


Related
=======

* :ref:`resources-targeting`
* :ref:`resources-configuration`
* :ref:`resources-architecture`
