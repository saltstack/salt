"""
Salt runner for cluster ring management and inspection.

Query-only operator surface for the Raft-backed cluster.  Reads come
from the per-master persisted Raft state on disk, so the runner does
not need IPC into the publish daemon's ``RaftService`` (which is a
separate process and not reachable from a runner subprocess).

CLI Examples:

.. code-block:: bash

    # Show this master's view of the cluster voter/learner set.
    salt-run cluster.members

    # Show this master's current ring state.
    salt-run cluster.ring_info

.. versionadded:: 3009.0
"""

import logging

log = logging.getLogger(__name__)


def members():
    """
    Return this master's view of the cluster's committed Raft membership.

    Reads the persisted Raft log and snapshot from the local
    ``SaltStorage`` and replays committed CONFIG entries through a
    fresh :class:`~salt.cluster.consensus.raft.log.MembershipStateMachine`.
    The returned set is what *this master* has applied locally — in a
    healthy cluster every master converges to the same answer, but the
    response is local-only and may briefly diverge during membership
    changes.

    Output:

    .. code-block:: python

        {
            "node_id":            str,         # this master's interface
            "voters":             [str, ...],  # sorted
            "learners":           [str, ...],  # sorted
            "membership_version": int,         # log index of latest CONFIG entry
            "voter_count":        int,
            "learner_count":      int,
        }

    ``membership_version`` is ``-1`` when no CONFIG entry has been
    applied yet (e.g. a fresh master that has not finished joining).

    CLI Example:

    .. code-block:: bash

        salt-run cluster.members

    .. versionadded:: 3009.0
    """
    # Lazy imports — the consensus modules are optional when Salt is
    # installed without cluster support.
    from salt.cluster.consensus.raft.log import (  # pylint: disable=import-outside-toplevel
        Log,
        LogEntryType,
        MembershipStateMachine,
    )
    from salt.cluster.consensus.storage import (  # pylint: disable=import-outside-toplevel
        SaltStorage,
    )

    node_id = __opts__.get("id") or __opts__.get("interface") or "unknown"

    membership_sm = MembershipStateMachine()
    storage = SaltStorage(node_id, __opts__)
    # ``Log.__init__`` loads any persisted snapshot and restores the
    # registered state machines from it.  We then replay any post-
    # snapshot CONFIG entries below.
    log_ = Log(
        storage=storage,
        state_machines={"membership_sm": membership_sm},
    )

    # Replay CONFIG entries that landed after the snapshot.  Storage
    # holds entries in log order; non-CONFIG entries (COMMAND, RING_CONFIG)
    # are skipped because they don't move membership.
    for entry in log_.entries:
        if entry.type == LogEntryType.CONFIG:
            membership_sm.apply(entry.cmd, index=entry.index)

    voters = membership_sm.current_voters()
    learners = membership_sm.current_learners()

    # Term and most-recently-observed leader come from ``save_state``.
    # See ``salt/cluster/consensus/storage.py`` for the on-disk shape.
    # ``leader_id`` is observability only — Raft itself derives the
    # leader from incoming AppendEntries.  Persisted here so a
    # read-only consumer answers "who's the leader" without IPC; may
    # be stale on a partitioned follower that hasn't heard from the
    # current term's leader.
    raw_state = storage.load_state()
    term = raw_state.get("term", 0)
    leader_id = raw_state.get("leader_id")

    # Voter-health surface, if the leader's watchdog has written its
    # sentinel.  Absence of the file means either auto-replacement was
    # never armed on this node or the watchdog has not run yet — either
    # way, an empty list is the honest answer.
    health = _read_health_sentinel()
    return {
        "node_id": node_id,
        "voters": voters,
        "learners": learners,
        "membership_version": membership_sm.membership_version,
        "voter_count": len(voters),
        "learner_count": len(learners),
        "leader_id": leader_id,
        "term": term,
        "unhealthy_voters": health.get("unhealthy_voters", []),
        "recently_demoted": health.get("recently_demoted", []),
    }


def rings():
    """
    Return the cluster-log multi-ring registry as this master sees it.

    Reads the persisted cluster Raft log on this master and replays
    every committed ``RING_REGISTRY`` entry through a fresh
    :class:`~salt.cluster.consensus.raft.log.RingRegistryStateMachine`.
    The result is the registry view *this* master has applied
    locally — in a healthy cluster every master converges to the
    same answer, but during a membership change a follower may lag
    by a heartbeat.

    Output:

    .. code-block:: python

        {
            "node_id": str,                # this master's interface
            "rings": {
                "<ring_id>": {
                    "founding_voters": [str, ...],
                    "status":          "active" | "destroyed",
                },
                ...
            },
            "active_rings":       [str, ...],   # sorted, status=="active" only
            "registry_version":   int,          # log index of last commit, -1 if none
        }

    CLI Example:

    .. code-block:: bash

        salt-run cluster.rings

    .. versionadded:: 3009.0
    """
    from salt.cluster.consensus.raft.log import (  # pylint: disable=import-outside-toplevel
        Log,
        LogEntryType,
        RingRegistryStateMachine,
    )
    from salt.cluster.consensus.storage import (  # pylint: disable=import-outside-toplevel
        SaltStorage,
    )

    node_id = __opts__.get("id") or __opts__.get("interface") or "unknown"
    registry_sm = RingRegistryStateMachine()
    storage = SaltStorage(node_id, __opts__)
    log_ = Log(
        storage=storage,
        state_machines={"ring_registry_sm": registry_sm},
    )
    for entry in log_.entries:
        if entry.type == LogEntryType.RING_REGISTRY:
            registry_sm.apply(entry.cmd, index=entry.index)

    return {
        "node_id": node_id,
        "rings": registry_sm.rings(),
        "active_rings": registry_sm.active_rings(),
        "registry_version": registry_sm.registry_version,
    }


def routes():
    """
    Return the cluster-log data-type -> ring routing table as this
    master sees it.

    Reads the persisted cluster Raft log and replays every committed
    ``ROUTE`` entry through a fresh
    :class:`~salt.cluster.consensus.raft.log.RoutingStateMachine`.
    Same caveats as :func:`rings`: a follower's view may briefly
    lag the leader during a routing change.

    Output:

    .. code-block:: python

        {
            "node_id":         str,
            "routes":          {"<data_type>": "<ring_id>" | None, ...},
            "routing_version": int,           # log index of last commit, -1
            "drop_stats":      {              # see ring_membership.drop_stats
                "<data_type>": {
                    "ring_id":           str,
                    "not_a_member":      int,
                    "other_ring_member": int,
                },
                ...
            },
        }

    The ``drop_stats`` field is local-process only — it reflects what
    *this* master has gated since startup.  ``not_a_member`` is the
    misconfig signal: a non-zero count means traffic for the named
    data type landed on a master that isn't in the routed ring (the
    load balancer probably needs adjusting).

    Note: the runner subprocess and the publish daemon are separate
    processes with their own counter state, so this surface reflects
    the runner's view, not the daemon's.  For an operational signal
    use ``grep "ring_membership: dropping"`` in the master log.

    CLI Example:

    .. code-block:: bash

        salt-run cluster.routes

    .. versionadded:: 3009.0
    """
    from salt.cluster import ring_membership  # pylint: disable=import-outside-toplevel
    from salt.cluster.consensus.raft.log import (  # pylint: disable=import-outside-toplevel
        Log,
        LogEntryType,
        RoutingStateMachine,
    )
    from salt.cluster.consensus.storage import (  # pylint: disable=import-outside-toplevel
        SaltStorage,
    )

    node_id = __opts__.get("id") or __opts__.get("interface") or "unknown"
    routing_sm = RoutingStateMachine()
    storage = SaltStorage(node_id, __opts__)
    log_ = Log(
        storage=storage,
        state_machines={"routing_sm": routing_sm},
    )
    for entry in log_.entries:
        if entry.type == LogEntryType.ROUTE:
            routing_sm.apply(entry.cmd, index=entry.index)

    return {
        "node_id": node_id,
        "routes": routing_sm.routes(),
        "routing_version": routing_sm.routing_version,
        "drop_stats": ring_membership.drop_stats(),
    }


def _read_health_sentinel():
    """
    Read the per-master health sentinel written by
    ``RaftService._check_voter_health``.

    Returns an empty dict if the sentinel is missing or unreadable.
    The sentinel is leader-written today (so only the current leader's
    cachedir holds a fresh copy); a non-leader's reply has empty lists
    even when the cluster has unhealthy voters.  Operators should
    invoke this runner against a known voter to get accurate signal.
    """
    import json  # pylint: disable=import-outside-toplevel
    import os  # pylint: disable=import-outside-toplevel

    import salt.utils.files  # pylint: disable=import-outside-toplevel

    cachedir = __opts__.get("cachedir")
    if not cachedir:
        return {}
    path = os.path.join(cachedir, "cluster-health.json")
    try:
        with salt.utils.files.fopen(path) as fp:
            return json.load(fp)
    except (OSError, ValueError):
        return {}


def sync_roots(roots="both"):
    """
    Push this master's ``file_roots`` and/or ``pillar_roots`` to every
    other cluster master.

    Runs the operator-driven counterpart of the bulk state-sync that
    fires automatically during a cluster join.  Use it when the
    canonical content on this master has changed and you want every
    peer to pick up the new files without restarting them or waiting
    for the next join handshake.

    The runner fires a local event; the master daemon picks it up and
    fans out chunks to every peer over the encrypted cluster pub bus
    (same transport as the join-time state-sync).  Returns immediately
    after the event is fired — the actual sync runs asynchronously in
    the master process.  Check each peer's master log for the
    ``state-sync ... installed N items`` lines to confirm delivery.

    :param roots: ``"file"``, ``"pillar"``, or ``"both"`` (default
                  ``"both"``).  Selects which content trees to sync.

    CLI Example:

    .. code-block:: bash

        # Push both file_roots and pillar_roots to all peers
        salt-run cluster.sync_roots

        # Push only file_roots
        salt-run cluster.sync_roots roots=file

    .. versionadded:: 3009.0
    """
    if roots not in ("file", "pillar", "both"):
        raise ValueError(f"roots must be 'file', 'pillar', or 'both', got {roots!r}")
    # Lazy imports — keep the runner module light.
    import salt.utils.event  # pylint: disable=import-outside-toplevel

    cluster_id = __opts__.get("cluster_id")
    if not cluster_id:
        return {
            "status": "skipped",
            "reason": "no cluster_id configured; this master is not a cluster member",
        }

    channels = []
    if roots in ("file", "both"):
        channels.append("file_roots")
    if roots in ("pillar", "both"):
        channels.append("pillar_roots")

    with salt.utils.event.get_event(
        "master",
        sock_dir=__opts__["sock_dir"],
        opts=__opts__,
        listen=False,
    ) as event:
        event.fire_event(
            {"channels": channels},
            "cluster/runner/sync_roots",
        )
    return {
        "status": "fan-out initiated",
        "channels": channels,
        "cluster_id": cluster_id,
        "note": (
            "The sync runs asynchronously inside the master daemon.  Tail "
            "each peer's master log for the 'state-sync ... installed N items' "
            "lines to confirm delivery."
        ),
    }


def ring_info():
    """
    Return a snapshot of this master's ring state.

    Reads the per-process ring populated by
    :class:`~salt.cluster.consensus.service.RaftService`.  Output:

    .. code-block:: python

        {
            "is_clustered": bool,
            "node_count":   int,
            "nodes":        [str, ...],   # sorted
            "vnodes":       int,
        }

    Note that runners run in their own subprocess; the ring instance
    they see is **not** the publish daemon's ring.  In the current
    design that subprocess never has a populated ring, so this
    function will always report ``is_clustered=False`` until stage 2
    introduces a process-shared ring (see ``GAPS.md``).  The signature
    is stable so the caller's contract does not change when the
    backing source does.

    CLI Example:

    .. code-block:: bash

        salt-run cluster.ring_info
    """
    # Lazy import — the cluster module is optional when Salt is
    # installed without consensus support.
    from salt.cluster import ring_membership  # pylint: disable=import-outside-toplevel

    ring = ring_membership.get_ring()
    return {
        "is_clustered": bool(ring.is_clustered),
        "node_count": ring.node_count(),
        "nodes": sorted(ring.nodes()),
        "vnodes": ring.token_count() // max(1, ring.node_count() or 1),
    }


def _fire_cluster_event(tag, data):
    """
    Shared helper: fire *tag* with *data* on the master's local event
    bus.  The publish daemon's ``publish_payload`` intercepts the
    event and dispatches to ``RaftService``.

    Returns the fire-and-forget result; the runner subprocess is
    done as soon as the event is on the bus.  Operators check
    ``cluster.members`` or other read-only runners to confirm the
    proposed entry committed.
    """
    import salt.utils.event  # pylint: disable=import-outside-toplevel

    cluster_id = __opts__.get("cluster_id")
    if not cluster_id:
        return {
            "status": "skipped",
            "reason": "no cluster_id configured; this master is not a cluster member",
        }
    with salt.utils.event.get_event(
        "master",
        sock_dir=__opts__["sock_dir"],
        opts=__opts__,
        listen=False,
    ) as event:
        event.fire_event(data, tag)
    return {"status": "fan-out initiated", "tag": tag, "data": data}


def ring_create(name, voters):
    """
    Create a named ring with the given founding voters.

    Fires a ``cluster/runner/ring_create`` event on the master's
    local bus; the publish daemon intercepts it and proposes a
    ``RING_REGISTRY`` entry through the cluster Raft group.  Each
    master that is in *voters* will then bring up the per-ring
    Raft group locally when the registry entry commits.

    :param name:   Operator-chosen ring identifier (e.g. ``"jobs"``).
    :param voters: List of master node-ids (interface addresses) to
                   serve as the founding voter set of the ring.

    Asymmetric with ``cluster.ring_destroy``: this runner only
    requests creation — bring-up of the per-ring Node is driven by
    the registry's commit callback inside the daemon.

    CLI Example:

    .. code-block:: bash

        salt-run cluster.ring_create name=jobs voters='["m1","m2","m3"]'
    """
    if not name:
        raise ValueError("cluster.ring_create requires a non-empty 'name'")
    if not voters:
        raise ValueError("cluster.ring_create requires a non-empty 'voters' list")
    return _fire_cluster_event(
        "cluster/runner/ring_create",
        {"ring_id": name, "founding_voters": list(voters)},
    )


def ring_destroy(name):
    """
    Mark the named ring as destroyed.

    Fires a ``cluster/runner/ring_destroy`` event; the publish daemon
    proposes a ``RING_REGISTRY`` entry with ``status="destroyed"``.
    Once committed, every master that hosted the ring's Raft group
    tears it down locally.  The on-disk state is left in place so an
    operator who re-creates the same ring picks up the persisted
    state.

    :param name: Ring identifier (must match the ``name`` used at
                 :func:`ring_create` time).

    CLI Example:

    .. code-block:: bash

        salt-run cluster.ring_destroy name=jobs
    """
    if not name:
        raise ValueError("cluster.ring_destroy requires a non-empty 'name'")
    return _fire_cluster_event(
        "cluster/runner/ring_destroy",
        {"ring_id": name},
    )


def route_set(data_type, ring):
    """
    Route a data type to a named ring.

    Fires a ``cluster/runner/route_set`` event; the publish daemon
    proposes a ``ROUTE`` entry through the cluster Raft group.  Once
    committed, gate sites in :mod:`salt.master` consult the routing
    table when they receive a write for *data_type* and defer to
    that ring's :meth:`HashRing.owns` answer.

    :param data_type: Logical cache identifier (e.g. ``"jobs"``).
    :param ring:      Ring name to route to (must have been created
                      via :func:`ring_create`).

    CLI Example:

    .. code-block:: bash

        salt-run cluster.route_set data_type=jobs ring=jobs
    """
    if not data_type:
        raise ValueError("cluster.route_set requires a non-empty 'data_type'")
    if not ring:
        raise ValueError("cluster.route_set requires a non-empty 'ring'")
    return _fire_cluster_event(
        "cluster/runner/route_set",
        {"data_type": data_type, "ring_id": ring},
    )


def route_clear(data_type):
    """
    Clear the route for a data type, returning it to broadcast.

    Fires a ``cluster/runner/route_clear`` event; the publish daemon
    proposes a ``ROUTE`` entry mapping *data_type* to ``None``.
    Once committed, every master mirrors the data type's writes
    again (the pre-multi-ring default).

    :param data_type: Logical cache identifier (e.g. ``"jobs"``).

    CLI Example:

    .. code-block:: bash

        salt-run cluster.route_clear data_type=jobs
    """
    if not data_type:
        raise ValueError("cluster.route_clear requires a non-empty 'data_type'")
    return _fire_cluster_event(
        "cluster/runner/route_clear",
        {"data_type": data_type},
    )


_DEFAULT_SHED_BANKS = (
    "jobs/loads",
    "jobs/minions",
    "jobs/endtimes",
    "jobs/nocache",
)
_DEFAULT_SUBBANK_TEMPLATE = "jobs/returns/{key}"


def shed_unowned(
    ring,
    banks=_DEFAULT_SHED_BANKS,
    subbank_template=_DEFAULT_SUBBANK_TEMPLATE,
    driver=None,
    dry_run=False,
):
    """
    Drop cache entries this master does not own for the named ring.

    The migration "going in" runner.  After
    ``cluster.ring_create``/``route_set`` have wired *ring* into the
    routing table and the per-ring Raft group has elected a leader,
    every master still has the *full* keyspace in its caches (a
    legacy of the pre-multi-ring broadcast era).  This runner walks
    the configured cache banks on this master and deletes the entries
    that hash to other ring members.

    :param ring:             Ring identifier whose voter set defines
                             ownership.
    :param banks:            Cache banks to scan.  Defaults match the
                             :mod:`salt.returners.salt_cache` job
                             layout (``jobs/loads`` is the primary
                             JID index; the others are sibling banks
                             keyed by JID).  Operators routing other
                             caches override.
    :param subbank_template: Optional ``str.format``-able template.
                             When set, for each unowned key found in
                             the first ``banks`` entry the runner
                             also flushes the templated bank in its
                             entirety — used for the salt_cache
                             returner's per-JID returns bank
                             (``"jobs/returns/{key}"``).  Pass
                             ``None`` for caches without sub-banks.
    :param driver:           Optional override for the
                             ``salt.cache.Cache`` driver.  Defaults
                             to the ``cache:`` opt — the same driver
                             the returner writes through.
    :param dry_run:          If ``True``, compute the counts but
                             don't flush anything.  Use to preview
                             the partition before committing.

    Returns a structured result::

        {
            "status":           "ok" | "skipped",
            "ring":             str,
            "dropped":          int,   # primary-bank entries flushed
            "kept":             int,   # primary-bank entries this master owns
            "subbanks_dropped": int,   # cascade banks flushed wholesale
            "dry_run":          bool,
        }

    Reads membership from local persisted Raft state (same path
    ``cluster.members`` already uses) so the runner subprocess can
    answer "what does the ring look like?" without IPC into the
    publish daemon.

    CLI Examples:

    .. code-block:: bash

        # Preview which JIDs would be dropped on this master.
        salt-run cluster.shed_unowned ring=jobs dry_run=True

        # Commit the deletions on the default jobs/* banks.
        salt-run cluster.shed_unowned ring=jobs

        # Shard a different cache type (the keys/denied-keys banks
        # are intentionally broadcast and should NOT be sharded; this
        # example assumes the operator has built a routed
        # ``inventory`` cache).
        salt-run cluster.shed_unowned ring=inventory \\
            banks='["inventory/items"]' subbank_template=None
    """
    if not ring:
        raise ValueError("cluster.shed_unowned requires a non-empty 'ring'")
    if not banks:
        raise ValueError("cluster.shed_unowned requires at least one bank")
    # The shed implementation is shared with the daemon-side
    # ``cluster/peer/shed-request`` intercept; both paths call into
    # ``salt.cluster.migration.perform_shed`` so the bank layout +
    # cascade rules stay consistent.
    from salt.cluster import migration  # pylint: disable=import-outside-toplevel

    result = migration.perform_shed(
        __opts__,
        ring,
        banks=banks,
        subbank_template=subbank_template,
        driver=driver,
        dry_run=dry_run,
    )
    migration.write_shed_status(__opts__, result, source="runner")
    return result


_DEFAULT_COLLECT_BANKS = (
    "jobs/loads",
    "jobs/minions",
    "jobs/endtimes",
    "jobs/nocache",
)


def shed_unowned_all(
    ring,
    banks=_DEFAULT_SHED_BANKS,
    subbank_template=_DEFAULT_SUBBANK_TEMPLATE,
    driver=None,
    dry_run=False,
):
    """
    Fan-out :func:`shed_unowned` across every master in the cluster.

    The single-master :func:`shed_unowned` runner drops the local
    master's unowned cache entries.  For a complete migration the
    operator has to run that on every ring member — error-prone
    and verbose for clusters with more than three or four masters.
    This runner solves the operator UX:

    1. Fires a ``cluster/runner/shed_unowned_all`` event from the
       runner subprocess on this master.
    2. The publish daemon intercepts the event, broadcasts a
       ``cluster/peer/shed-request`` event (cluster_aes-encrypted)
       to every peer carrying the runner's parameters.
    3. Each peer's daemon intercepts the request and runs the same
       shed-unowned logic locally, writing a per-master sentinel
       at ``cachedir/cluster-shed-status.json`` so the operator can
       poll for results without tailing logs.
    4. The originator also runs its own local shed inline so the
       runner returns with a useful result even before peer
       sentinels appear.

    :param ring:             Ring identifier whose voter set defines
                             ownership.  Same shape as
                             :func:`shed_unowned`.
    :param banks:            Cache banks to scan; defaults to the
                             salt_cache jobs layout.
    :param subbank_template: Cascade bank template; defaults to
                             ``"jobs/returns/{key}"``.  Pass
                             ``None`` to disable the cascade.
    :param driver:           Optional ``salt.cache.Cache`` driver
                             override.  Defaults to the ``cache:``
                             opt.
    :param dry_run:          When True, runs the partition preview
                             on every master without committing.

    Returns the same shape as :func:`shed_unowned` for *this*
    master's local pass, plus a ``fan_out`` field naming the
    cluster/peer/shed-request event that fanned to peers.
    Per-peer results land in their own sentinel files; operators
    can collect them with ``cluster.shed_status``.

    CLI Example:

    .. code-block:: bash

        # Preview shed across every master in the cluster.
        salt-run cluster.shed_unowned_all ring=jobs dry_run=True

        # Commit shed across every master.
        salt-run cluster.shed_unowned_all ring=jobs
    """
    if not ring:
        raise ValueError("cluster.shed_unowned_all requires a non-empty 'ring'")
    payload = {
        "ring_id": ring,
        "banks": list(banks),
        "subbank_template": subbank_template,
        "driver": driver,
        "dry_run": bool(dry_run),
    }
    # Fire the event so the publish daemon fans it out to peers.
    fan_out = _fire_cluster_event("cluster/runner/shed_unowned_all", payload)
    # Also run locally — operator gets back a meaningful per-master
    # result from this side of the fan-out without polling.
    local = shed_unowned(
        ring,
        banks=banks,
        subbank_template=subbank_template,
        driver=driver,
        dry_run=dry_run,
    )
    return {
        "fan_out": fan_out,
        "local": local,
    }


def shed_status():
    """
    Read this master's local ``cluster-shed-status.json`` sentinel,
    if any.

    The sentinel is written by the master daemon whenever it runs a
    local shed (either operator-triggered ``cluster.shed_unowned``,
    or a peer-triggered fan-out via
    ``cluster.shed_unowned_all``).  Operators check this file
    cluster-wide to confirm shed completed on every master.

    Returns ``{"status": "missing"}`` when no sentinel has been
    written yet — typical on a master that has never run shed.

    CLI Example:

    .. code-block:: bash

        salt-run cluster.shed_status
    """
    import json  # pylint: disable=import-outside-toplevel
    import os  # pylint: disable=import-outside-toplevel

    import salt.utils.files  # pylint: disable=import-outside-toplevel

    cachedir = __opts__.get("cachedir")
    if not cachedir:
        return {"status": "missing", "reason": "no cachedir opt"}
    path = os.path.join(cachedir, "cluster-shed-status.json")
    try:
        with salt.utils.files.fopen(path) as fp:
            return json.load(fp)
    except (OSError, ValueError):
        return {"status": "missing", "path": path}


def collect_from_peers(channels=(), banks=_DEFAULT_COLLECT_BANKS):
    """
    Pull cache contents from every peer to this master.

    The migration "going out" runner — reverses
    :func:`cluster.sync_roots` direction.  This master fires a
    ``cluster/runner/collect_from_peers`` event; the publish daemon
    broadcasts a collect-request to every peer.  Each peer streams
    its cache contents for the requested channels back over the
    existing state-sync chunk transport, and this master's receiver
    applies them locally.

    Use to gather full coverage before flipping
    :func:`cluster.route_clear` a data type back to broadcast: after
    every master has run this runner successfully, every master
    holds the full keyspace again and a route flip won't strand
    reads.

    Two channel families are supported:

    * ``channels`` — fixed state-sync channels ``keys`` and
      ``denied_keys`` (the join-time minion-key transport).
    * ``banks`` — arbitrary :class:`salt.cache.Cache` banks (e.g.
      the salt_cache returner's ``jobs/*`` banks).  Each bank name
      is wrapped as a ``bank:<bank>`` channel on the wire and the
      peer streams it via
      :func:`salt.cluster.state_sync.iter_bank_chunks`.

    :param channels: Iterable of fixed state-sync channel names
                     (subset of ``{"keys", "denied_keys"}``).
                     Defaults to empty; only set when migrating PKI
                     banks (the default keys/denied_keys layout is
                     intentionally broadcast in this branch — see
                     ``MULTI_RING_DESIGN.md``).
    :param banks:    Iterable of :class:`salt.cache.Cache` bank
                     names.  Defaults to the four ``jobs/*`` banks
                     written by :mod:`salt.returners.salt_cache`,
                     which is the production case for multi-ring
                     migrations.

    Fire-and-forget: the runner returns immediately after the event
    is on the bus.  Poll local cache contents (or tail the master
    log for ``state-sync ... installed N items``) to confirm
    delivery from each peer.

    CLI Examples:

    .. code-block:: bash

        # Default: collect the jobs/* banks from every peer.
        salt-run cluster.collect_from_peers

        # Collect a specific bank only.
        salt-run cluster.collect_from_peers banks='["jobs/loads"]'

        # Operator migrating a routed PKI-keys bank (rare).
        salt-run cluster.collect_from_peers channels='["keys"]' banks='[]'
    """
    from salt.cluster.state_sync import (  # pylint: disable=import-outside-toplevel
        BANK_CHANNEL_PREFIX,
    )

    fixed = list(channels) if channels else []
    bank_list = list(banks) if banks else []
    invalid = [ch for ch in fixed if ch not in ("keys", "denied_keys")]
    if invalid:
        raise ValueError(
            f"cluster.collect_from_peers: unsupported fixed channels {invalid!r} "
            "(only 'keys' and 'denied_keys' are recognised; arbitrary cache "
            "banks go through the 'banks' parameter)"
        )
    if not fixed and not bank_list:
        raise ValueError(
            "cluster.collect_from_peers requires at least one channel or bank"
        )
    requested = fixed + [f"{BANK_CHANNEL_PREFIX}{b}" for b in bank_list]
    return _fire_cluster_event(
        "cluster/runner/collect_from_peers",
        {"channels": requested},
    )


def ring_set(name=None, members=None, replicas=None):
    """
    Propose a new policy for the named ring.

    Fires a ``cluster/runner/ring_set`` event; the publish daemon
    proposes a ``RING_CONFIG`` entry on the *ring's own* Raft log
    (not the cluster log).  Partial updates are honoured — omit a
    knob to keep its existing value.

    :param name:     Ring identifier (required).
    :param members:  ``"self"`` (ring is self-only — gate writes
                     broadcast) or ``"voters"`` (ring tracks the
                     ring's committed voter set — gate writes shard).
                     ``None`` keeps the existing value.
    :param replicas: Integer >= 1.  ``None`` keeps the existing value.

    Must be invoked on a master that is a leader of the named ring's
    Raft group.  Operators typically discover this by checking
    ``cluster.members`` first to find the ring's current leader.

    CLI Example:

    .. code-block:: bash

        salt-run cluster.ring_set name=jobs members=voters replicas=2
    """
    if not name:
        raise ValueError("cluster.ring_set requires a non-empty 'name'")
    payload = {"ring_id": name}
    if members is not None:
        payload["members"] = members
    if replicas is not None:
        payload["replicas"] = int(replicas)
    return _fire_cluster_event("cluster/runner/ring_set", payload)


# Filename constants matching ``salt.returners.local_cache``.  Kept
# verbatim so the migration is bit-exact against existing on-disk
# state — DO NOT rename without verifying old caches still parse.
_LC_LOAD_P = ".load.p"
_LC_MINIONS_P = ".minions.p"
_LC_SYNDIC_MINIONS_PREFIX = ".minions."  # ".minions.<syndic_id>.p"
_LC_RETURN_P = "return.p"
_LC_OUT_P = "out.p"
_LC_ENDTIME = "endtime"
_LC_NOCACHE = "nocache"


def migrate_jobs_to_cache(dry_run=False):
    """
    Migrate job-cache state from the ``local_cache`` returner layout
    into the bank layout :mod:`salt.returners.salt_cache` uses.

    The default ``master_job_cache: local_cache`` returner writes
    each JID to
    ``<cachedir>/jobs/<2-hex>/<28-hex>/{.load.p, .minions.p,
    <minion_id>/return.p, …}``.  Operators flipping to
    ``master_job_cache: salt_cache`` (the multi-ring-capable
    returner) start with an empty bank set — every job submitted
    before the flip becomes invisible to the new returner.

    This one-shot runner walks the old filesystem layout and
    populates the salt_cache banks::

        <cachedir>/jobs/<2>/<28>/.load.p        -> bank "jobs/loads",     key=jid
        <cachedir>/jobs/<2>/<28>/.minions.p     -> bank "jobs/minions",   key=jid
        <cachedir>/jobs/<2>/<28>/endtime        -> bank "jobs/endtimes",  key=jid
        <cachedir>/jobs/<2>/<28>/nocache        -> bank "jobs/nocache",   key=jid
        <cachedir>/jobs/<2>/<28>/<m>/return.p   -> bank "jobs/returns/<jid>", key=<m>
        <cachedir>/jobs/<2>/<28>/<m>/out.p      -> folded into the same record

    The original files are left in place — operators who want to
    reclaim the disk can ``rm -rf`` ``<cachedir>/jobs`` after
    confirming the new banks are correct (running ``cluster.members``
    /  ``salt-run jobs.list_jobs`` against the new returner is the
    smoke check).

    :param dry_run: If ``True``, walk and count without writing any
                    cache entries.  Use to verify the runner sees
                    every JID before committing.

    Returns a structured result::

        {
            "status":           "ok" | "skipped",
            "scanned":          int,   # JIDs walked
            "migrated":         int,   # JIDs successfully written
            "skipped":          int,   # malformed entries the runner ignored
            "returns_migrated": int,   # minion return records written
            "dry_run":          bool,
            "jobs_root":        str,   # path that was walked
        }

    CLI Examples:

    .. code-block:: bash

        # Preview without writing anything.
        salt-run cluster.migrate_jobs_to_cache dry_run=True

        # Actually copy the state across.
        salt-run cluster.migrate_jobs_to_cache

    Operationally: stop the master before flipping
    ``master_job_cache`` so new writes don't race the migration,
    run this runner, restart the master with the new opt set.
    """
    import os  # pylint: disable=import-outside-toplevel

    import salt.cache  # pylint: disable=import-outside-toplevel
    import salt.payload  # pylint: disable=import-outside-toplevel
    import salt.utils.files  # pylint: disable=import-outside-toplevel

    cachedir = __opts__.get("cachedir")
    if not cachedir:
        return {
            "status": "skipped",
            "reason": "cachedir opt not set; cannot locate jobs root",
            "scanned": 0,
            "migrated": 0,
            "skipped": 0,
            "returns_migrated": 0,
            "dry_run": dry_run,
            "jobs_root": None,
        }
    jobs_root = os.path.join(cachedir, "jobs")
    if not os.path.isdir(jobs_root):
        return {
            "status": "skipped",
            "reason": f"no local_cache jobs root at {jobs_root!r}; nothing to do",
            "scanned": 0,
            "migrated": 0,
            "skipped": 0,
            "returns_migrated": 0,
            "dry_run": dry_run,
            "jobs_root": jobs_root,
        }

    cache = (
        None
        if dry_run
        else salt.cache.Cache(
            __opts__,
            driver=__opts__.get("cache") or __opts__.get("keys.cache_driver"),
        )
    )

    scanned = migrated = skipped = returns_migrated = 0

    for top in sorted(os.listdir(jobs_root)):
        t_path = os.path.join(jobs_root, top)
        if not os.path.isdir(t_path):
            continue
        for jid_hash in sorted(os.listdir(t_path)):
            jid_dir = os.path.join(t_path, jid_hash)
            if not os.path.isdir(jid_dir):
                continue
            scanned += 1
            try:
                ok, ret_count = _migrate_one_jid(
                    jid_dir, cache, dry_run, salt.utils.files, salt.payload
                )
            except Exception:  # pylint: disable=broad-except
                log.exception(
                    "cluster.migrate_jobs_to_cache: failed to migrate %s",
                    jid_dir,
                )
                skipped += 1
                continue
            if ok:
                migrated += 1
                returns_migrated += ret_count
            else:
                skipped += 1

    log.info(
        "cluster.migrate_jobs_to_cache: scanned=%d migrated=%d skipped=%d "
        "returns_migrated=%d dry_run=%s (root=%s)",
        scanned,
        migrated,
        skipped,
        returns_migrated,
        dry_run,
        jobs_root,
    )
    return {
        "status": "ok",
        "scanned": scanned,
        "migrated": migrated,
        "skipped": skipped,
        "returns_migrated": returns_migrated,
        "dry_run": dry_run,
        "jobs_root": jobs_root,
    }


def _migrate_one_jid(jid_dir, cache, dry_run, files_mod, payload_mod):
    """
    Migrate a single ``local_cache`` JID directory.

    Returns ``(success, return_count)``.  *success* is False when the
    JID directory has no usable ``.load.p`` (i.e. a stub left behind
    by an in-flight crash); the caller bumps the ``skipped`` counter
    and moves on.
    """
    import os  # pylint: disable=import-outside-toplevel

    load_path = os.path.join(jid_dir, _LC_LOAD_P)
    if not os.path.isfile(load_path):
        return False, 0
    with files_mod.fopen(load_path, "rb") as fp:
        load = payload_mod.load(fp)
    if not isinstance(load, dict):
        return False, 0
    jid = load.get("jid") or os.path.basename(jid_dir)

    # ``jobs/minions`` — merge the main file with any syndic-supplied
    # variants so the new bank reflects the union (which is also what
    # ``local_cache.get_load`` returns under ``Minions``).
    minions = set()
    for fname in os.listdir(jid_dir):
        if fname == _LC_MINIONS_P or (
            fname.startswith(_LC_SYNDIC_MINIONS_PREFIX) and fname.endswith(".p")
        ):
            try:
                with files_mod.fopen(os.path.join(jid_dir, fname), "rb") as fp:
                    blob = payload_mod.load(fp)
            except Exception:  # pylint: disable=broad-except
                continue
            if isinstance(blob, (list, tuple, set)):
                minions.update(blob)
    minions_list = sorted(minions)

    # ``endtime`` is plain text, not msgpack.
    endtime = None
    endtime_path = os.path.join(jid_dir, _LC_ENDTIME)
    if os.path.isfile(endtime_path):
        try:
            with files_mod.fopen(endtime_path) as fp:
                endtime = float(fp.read().strip())
        except (OSError, ValueError):
            endtime = None

    nocache = os.path.isfile(os.path.join(jid_dir, _LC_NOCACHE))

    # Per-minion returns: each subdir is a minion id.
    returns = {}
    for fname in os.listdir(jid_dir):
        sub = os.path.join(jid_dir, fname)
        if not os.path.isdir(sub):
            continue
        ret_path = os.path.join(sub, _LC_RETURN_P)
        if not os.path.isfile(ret_path):
            continue
        try:
            with files_mod.fopen(ret_path, "rb") as fp:
                record = payload_mod.load(fp)
        except Exception:  # pylint: disable=broad-except
            continue
        if not isinstance(record, dict) or "return" not in record:
            # Legacy v1: bare return value at the key.  Wrap into
            # the modern dict shape so the salt_cache get_jid path
            # treats it consistently.
            record = {"return": record}
        out_path = os.path.join(sub, _LC_OUT_P)
        if os.path.isfile(out_path):
            try:
                with files_mod.fopen(out_path, "rb") as fp:
                    record["out"] = payload_mod.load(fp)
            except Exception:  # pylint: disable=broad-except
                pass
        returns[fname] = record

    if dry_run:
        return True, len(returns)

    cache.store("jobs/loads", jid, load)
    if minions_list:
        cache.store("jobs/minions", jid, minions_list)
    if endtime is not None:
        cache.store("jobs/endtimes", jid, endtime)
    if nocache:
        cache.store("jobs/nocache", jid, True)
    for minion_id, record in returns.items():
        cache.store(f"jobs/returns/{jid}", minion_id, record)

    return True, len(returns)
