.. _cache-rings:

===============================
Managing Caches on a Hash Ring
===============================

.. versionadded:: 3008.0

By default every master in a :ref:`master cluster <tutorial-master-cluster>`
holds a full copy of every cache (jobs, grains, mine, etc.) — each write
fans out to every peer and each master can answer a read without
coordination.  That is the right default for small clusters, but for
clusters where the job cache dominates disk use or where a shared
filesystem is expensive to scale, Salt can **shard** a cache across the
cluster using a consistent-hash ring so that each key is owned by a
subset of masters instead of all of them.

This page explains the ring model, the per-ring Raft groups that keep it
consistent, and the operator runners that create, route, migrate and
tear down a sharded cache.

Conceptual model
================

Consistent hashing with virtual nodes
-------------------------------------

A ring (:class:`salt.cluster.ring.HashRing`) maps arbitrary keys —
job-ids, minion-ids, cache bank names — to the master that owns them.
Positions on the ring are 64-bit unsigned integers derived from
``xxhash.xxh3_64_intdigest``; each physical master contributes a set of
*virtual nodes* (VNodes) whose positions are

.. code-block:: python

    xxhash.xxh3_64_intdigest(f"{node_id}#vnode{replica}".encode())

The default 150 VNodes per physical node keep the coefficient of
variation below 10 % for typical cluster sizes.  A key is owned by the
first VNode whose position is ``>=`` the key's hash (clockwise successor,
wrapping at ``2**64``), with the owning physical node being the one
behind that VNode.

Because every master derives the same positions from the same node set
and the same key, ownership is deterministic — no cluster-wide lookup is
needed on the hot path.  A master consults its local
:class:`HashRing` instance and answers *yes* or *no* for each write it
sees.

Multi-ring registry
-------------------

Each sharded cache has its own :class:`HashRing`.  The named rings are
tracked in a cluster-wide registry committed through the cluster's own
Raft log as ``RING_REGISTRY`` entries.  When the leader of the cluster
Raft group commits a ``RING_REGISTRY`` entry announcing a new ring,
every master that is in the founding voter set brings up a *per-ring
Raft group* locally — a separate consensus group whose log is used to
commit the ring's policy (voter membership, replica count) and whose
committed CONFIG entries drive the HashRing's node set.

:func:`salt.cluster.ring_membership.get_ring` is the lookup; it returns
the current per-process :class:`HashRing` for a ring name.

Routing table
-------------

Caches are routed to rings by a cluster-wide **routing table** —
``data_type → ring_id`` (or ``None`` meaning *broadcast*) — also
committed through the cluster Raft log as ``ROUTE`` entries.  The gate
sites in :mod:`salt.master` ask
:func:`salt.cluster.ring_membership.owns_for` whether this master owns
*key* for *data_type*; the gate consults the routing table, then the
named ring's ownership answer.

The gate's decision table for a write arriving at a master:

* **No routing entry for the data type** (or the route points at
  ``None``): broadcast — every master owns, the write persists
  locally.  This is the pre-multi-ring default and the state every
  master is in before :func:`cluster.route_set` commits.
* **Route points at a ring this master does not host locally**:
  returns ``False`` — the write is dropped locally, counted under
  ``not_a_member`` in :func:`salt.cluster.ring_membership.drop_stats`.
  The load balancer is expected to steer traffic for a routed cache
  to a master that *is* in the ring; this drop is the "misconfig"
  signal.
* **Route points at a local ring**: defers to the ring's
  :meth:`HashRing.owns` answer.  Non-owners drop under
  ``other_ring_member`` (the expected shard-miss path, not a
  misconfig), and :meth:`_delegate_on_miss` in :mod:`salt.master`
  forwards the write back onto the cluster bus so the owning master
  picks it up.

A master whose ring is empty (subprocess pre-fork, or a ring whose
per-ring Raft group has not yet committed membership) behaves as "not
a member" and drops routed writes — this is why the operator
cookbook below verifies ring state via ``cluster.rings`` before
clearing the pre-route broadcast assumption.

What is actually consistent, and what is eventual
-------------------------------------------------

Three Raft logs matter for a sharded cache:

1. **The cluster log** — carries ``RING_REGISTRY`` (ring exists / is
   destroyed) and ``ROUTE`` (``data_type → ring_id``) entries.  Every
   master is a voter in this group.
2. **Each ring's own log** — carries ``RING_CONFIG`` policy
   (``members = voters | self``, ``replicas = N``) and ``CONFIG``
   membership entries.  Only masters in that ring's voter set
   participate.
3. **The data cache itself** (``salt_cache``, ``mmap_cache``, …) is
   *not* Raft-replicated.  Keys are placed on a master by the ring; the
   master stores them locally.

During a routing change or a membership change there is a short window
in which different masters see a different ring state.  Writes keep
working — a write arriving at a master that *used to* own the key is
routed back onto the bus via the gate sites' ``_delegate_on_miss`` path
and picked up by the new owner.  Reads during this window may miss until
the state settles, which the operator tooling below is written to
observe (dry-run, status sentinels, idempotent shed).

When to shard a cache
=====================

The default broadcast behaviour is correct for most clusters.  Shard a
cache when at least one of these is true:

* The cache dominates per-master disk use.  The job cache is the usual
  example — minute-by-minute return storage on a chatty fleet can
  outgrow the share before anything else does.
* You run :conf_master:`cluster_isolated_filesystem` mode and want to
  stop replicating the full cache across peers over the cluster
  transport.
* A single master's cache-serve path is the bottleneck (returns/jobs
  reads outpace a single master's I/O or CPU).

Do **not** shard:

* ``keys/`` or ``denied_keys/`` — minion-key material must be visible on
  every master or minion-authentication becomes positionally
  unreliable.  The gate deliberately broadcasts these.
* Any cache whose consumer does not go through the gate.  Routed caches
  only work for data types the ``EventMonitor`` /
  ``local_cache``-replacement path in :mod:`salt.master` writes to.

Prerequisites
=============

* Cluster is already up and healthy — ``salt-run cluster.members`` on
  every master returns the same voter set.
* The cache you are about to shard has a banks-capable returner.  For
  the job cache this means setting :conf_master:`master_job_cache` to
  ``salt_cache`` (the broadcast default is ``local_cache``, which writes
  the historical ``jobs/<2-hex>/<28-hex>/…`` filesystem layout that the
  gate cannot route).
* If there is existing data in the old layout, run
  :func:`salt.runners.cluster.migrate_jobs_to_cache` *before* enabling
  routing, so the pre-flip data lives in banks the ring can actually
  reason about.

Operator cookbook
=================

The worked example below shards the job cache across a three-master
cluster.  Every command is a :command:`salt-run` call and is
idempotent — re-running a step that has already converged is a no-op.

1. Migrate pre-flip job data (optional)
---------------------------------------

Only applies when a cluster has been running with
``master_job_cache: local_cache`` (the pre-sharding default) and is
about to flip to ``master_job_cache: salt_cache``.

.. code-block:: bash

    # Preview: scan the on-disk jobs/ layout and count what would be migrated.
    salt-run cluster.migrate_jobs_to_cache dry_run=True

    # Commit: write the salt_cache banks from the historical layout.
    salt-run cluster.migrate_jobs_to_cache

The original ``jobs/<2>/<28>/`` tree is left on disk so the operator can
``rm -rf`` it manually after confirming the new banks parse.  Run on one
master; the banks live under the same ``cachedir`` the daemon is already
sharing or replicating.

2. Create the ring
------------------

Decide the founding voter set.  For a three-master cluster every master
is a voter by default.  Larger clusters typically pick a subset (3, 5,
or 7 nodes) so Raft quorum stays cheap.

.. code-block:: bash

    salt-run cluster.ring_create name=jobs voters='["m1","m2","m3"]'

This fires a ``cluster/runner/ring_create`` event; the publish daemon
proposes a ``RING_REGISTRY`` entry on the cluster Raft group.  Once
committed, every master in ``voters`` brings up the per-ring Raft group
locally.

Verify the registry caught up on every master:

.. code-block:: bash

    salt-run cluster.rings
    # => active_rings: [..., "jobs"]

``cluster.rings`` is authoritative — it replays the committed cluster
Raft log.  ``cluster.ring_info`` reports the runner-subprocess copy of
the ring, which in 3008.x is intentionally empty (the publish daemon's
ring is in a separate process; a shared-memory ring is a future
improvement — see ``GAPS.md``).  Prefer ``cluster.rings`` and
``cluster.routes`` for topology verification; use the master log
(``cluster/registry/ring_created``, ``_on_ring_config_change_for``
lines) for gate-side state.

3. Route the data type to the ring
----------------------------------

Until a route exists, the ring is "built but unused" — gate sites
broadcast the cache because no ``data_type`` points at the ring.

.. code-block:: bash

    salt-run cluster.route_set data_type=jobs ring=jobs

Fires ``cluster/runner/route_set``; the daemon proposes a ``ROUTE``
entry on the cluster Raft group.  Confirm it committed:

.. code-block:: bash

    salt-run cluster.routes
    # => {"jobs": "jobs"}

4. Shed data no longer owned by this master
-------------------------------------------

Before the route, every master wrote every key.  After the route, each
master only *writes* the keys it owns — but the pre-route keys it does
not own are still on disk.  ``cluster.shed_unowned_all`` drops them
cluster-wide:

.. code-block:: bash

    # Preview: no deletions, just the partition report per master.
    salt-run cluster.shed_unowned_all ring=jobs dry_run=True

    # Commit: drop locally-not-owned keys on every master.
    salt-run cluster.shed_unowned_all ring=jobs

The runner fires ``cluster/runner/shed_unowned_all``; each peer runs
:func:`salt.cluster.migration.perform_shed` locally and writes a
per-master sentinel at ``<cachedir>/cluster-shed-status.json``.  Poll
it on each master:

.. code-block:: bash

    # On every master, or via a loop across peers.
    salt-run cluster.shed_status

The single-master variant :func:`salt.runners.cluster.shed_unowned` is
available for targeted cleanup during incident response; the fan-out
form is what the routine migration uses.

5. Tune ring policy (optional)
------------------------------

Replica count and membership mode live on the *ring's own* Raft log.
Must be invoked on a master that is leader of the named ring's group
(find it via ``cluster.members``).

.. code-block:: bash

    # Two replicas per key (higher availability, 2x write cost).
    salt-run cluster.ring_set name=jobs replicas=2

    # Track the ring's voter set (default; shards the data type).
    salt-run cluster.ring_set name=jobs members=voters

    # Collapse the ring: self-only, writes go back to broadcast.
    salt-run cluster.ring_set name=jobs members=self

Partial updates are honoured — omit a knob to keep its current value.
After a policy change, re-run ``cluster.shed_unowned_all ring=<name>``
to realign on-disk state.

6. Reverse a sharded cache
--------------------------

To return a cache to broadcast without destroying the ring (the ring
and its history stay on disk, ready to re-route):

.. code-block:: bash

    salt-run cluster.route_clear data_type=jobs

Gate sites fall back to broadcast immediately; keys written after this
point go to every master.  Pre-existing keys stay where the ring left
them until the next broadcast write for that key, so operators who need
a fully-converged broadcast state typically pair ``route_clear`` with a
cache-rebuild step (for jobs: new jobs over-write; for grains: a
scheduled ``saltutil.refresh_grains``).

To destroy the ring entirely:

.. code-block:: bash

    salt-run cluster.ring_destroy name=jobs

Fires ``cluster/runner/ring_destroy``; the daemon proposes a
``RING_REGISTRY`` entry with ``status="destroyed"``.  Every master that
hosted the per-ring Raft group tears it down locally; the ring's
on-disk state is left in place so an operator who re-creates the same
ring picks up where they left off.

Inspecting ring state
=====================

All of the following are read-only and local — they replay the
persisted Raft log on *this* master, which in a healthy cluster matches
every peer:

* :func:`salt.runners.cluster.rings` — the cluster-log multi-ring
  registry (which rings exist, which are destroyed, when they were
  created).
* :func:`salt.runners.cluster.routes` — the committed
  ``data_type → ring_id`` routing table.
* :func:`salt.runners.cluster.ring_info` — the runner-subprocess
  ring (empty in 3008.x; see note under *Verify the registry caught
  up* above).  The publish-daemon's ring is in a separate process;
  gate-side state is observable via the master log.
* :func:`salt.runners.cluster.shed_status` — this master's last-shed
  sentinel (status, counts, bank layout).

Interaction with other cluster features
=======================================

``cluster_isolated_filesystem``
    Sharding is most meaningful in isolated-fs mode — each master keeps
    only the keys it owns on local disk instead of the whole set.  In
    shared-fs mode every write still hits the shared filesystem, so
    sharding reduces compute but not storage.  See
    :ref:`master-cluster-topology` for the trade-offs.

``cluster.sync_roots``
    Independent of the ring.  Rings route *cache* data; ``sync_roots``
    pushes :conf_master:`file_roots` / :conf_master:`pillar_roots`
    content between peers in isolated-fs mode.

``cluster.collect_from_peers``
    The complement of shed — pulls cache contents *to* this master from
    every peer.  Useful when decommissioning a ring or consolidating a
    cache back to broadcast; otherwise unused.

Troubleshooting
===============

``cluster.ring_info`` reports ``is_clustered=False`` even after the ring is up
    Expected in 3008.x.  The runner runs in its own subprocess and
    cannot see the publish-daemon's ring instance; the design puts a
    shared-memory ring behind the runner surface as a later stage
    (see ``GAPS.md``).  Use ``cluster.rings`` for authoritative ring
    state and the master log for gate-side state.

Writes for a routed cache seem to still fan out
    Either the route has not committed (``cluster.routes`` to confirm),
    or the data type is not gate-wired (e.g. ``keys/``, which is
    intentionally broadcast).  Routing a data type the gate doesn't
    recognise is a no-op.

Shed never completes on one master
    ``cluster.shed_status`` on that master will show either ``missing``
    (the fan-out event never arrived — check the master's event log for
    ``cluster/peer/shed-request`` reception) or an error from
    ``perform_shed``.  Re-run ``cluster.shed_unowned`` directly on the
    problem master to produce a fresh sentinel.

A master I removed still appears in ``cluster.rings``
    Ring membership follows the ring's Raft-group CONFIG, not the
    cluster-wide one.  Remove the master from the ring explicitly with
    ``cluster.ring_set`` or by issuing a ring-local ``remove-server``.

See also
========

* :ref:`tutorial-master-cluster` — cluster bring-up and topology.
* :ref:`mmap-cache` — the recommended companion cache driver for
  isolated-filesystem clusters.
* :py:mod:`salt.runners.cluster` — full runner reference with
  parameter lists and return shapes.
