"""
Master topology --- peer graph of 3008.x master clusters.

This package provides the runtime machinery for connecting
multiple master clusters into a loop-detected peer graph, with
routing, breadcrumb-based return paths, and aggregate summaries
propagated via gossip.

The topology package is active only when
``opts["topology_enabled"]`` is True.  When disabled, no files in
this package are imported at runtime.

Process model
-------------
The salt-master is multi-process.  Topology code lives in one
process (the publish daemon) with cross-process reads via
:mod:`salt.utils.mmap_cache`:

* The publish daemon owns
  :class:`salt.topology.link.PeerMasterLink` objects, the
  :class:`salt.topology.router.TopologyRouter` instance, and the
  routing table.  It is the sole writer of the registry and
  breadcrumbs MmapCaches.
* MWorkers open the breadcrumbs MmapCache as readers to decide
  whether an inbound minion return belongs to a topology-origin
  publish (and if so, hand off to the publish daemon via one
  event-bus message per return).
* The identity key is Raft-replicated inside a cluster via
  :class:`salt.cluster.consensus.raft.topology.TopologyStateMachine`,
  which writes into the same registry MmapCache that solo
  masters write to directly.  The MmapCache is the authoritative
  read source regardless of mode.

Module map
----------
* :mod:`salt.config.topology`           --- load/validate
  ``topology.conf``.  Lives alongside
  :mod:`salt.config.worker_pools`.
* :mod:`salt.topology.registry`         --- MmapCache-backed
  identity + peer registry; readable from any process.
* :mod:`salt.topology.breadcrumbs`      --- MmapCache-backed
  ``jid -> inbound link`` map; MWorker reads, publish daemon
  writes.
* :mod:`salt.topology.link`             --- :class:`PeerMasterLink`
  and health states.  Publish daemon only.
* :mod:`salt.topology.link_manager`     --- process-wide link
  registry and inbound-listener lifecycle
  (ring_membership pattern).  Publish daemon only.
* :mod:`salt.topology.router`           --- publish routing,
  breadcrumb lifecycle, event forwarding.  Publish daemon only.
* :mod:`salt.topology.summary`          --- :class:`ClusterSummary`
  data type; propagated between peers for scaling + routing.
* :mod:`salt.topology.migration`        --- one-shot solo ->
  clustered promotion of the registry contents into Raft.
* :mod:`salt.cluster.consensus.raft.topology` --- Raft-committed
  write path for clustered masters.  Writes into the same
  MmapCaches used by solo-mode direct writes.

See ``rfcs/master-topology.md`` for the full design rationale
and the backward-compatibility guarantees.
"""
