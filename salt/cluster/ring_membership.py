"""
High-level ownership query for cluster-distributed state.

Wraps per-process :class:`salt.cluster.ring.HashRing` instances with a
named-registry API the rest of the cluster code reaches for:

* :func:`get_ring(name)` — fetch (or lazily create) the named ring.
* :func:`rebuild(name, voters, replicas=1)` — replace a ring's
  contents (called from
  :meth:`salt.cluster.consensus.service.RaftService._on_ring_config_change_for`
  for per-ring policy commits).
* :func:`owns_for(opts, data_type, key)` — multi-ring gate: consult
  the routing table, then ask that ring whether this master owns
  *key*.
* :func:`owns(opts, key)` — legacy single-ring gate that targets the
  ``"cluster"`` named ring.  Pre-multi-ring callers keep working with
  no changes; new gate sites use :func:`owns_for` instead.

Multi-ring semantics
--------------------
For multi-ring deployments each Salt cache has its own
:class:`HashRing` keyed by a ring name (e.g. ``"jobs"``,
``"events"``).  ``_RINGS`` is the per-process registry — a subprocess
inherits the parent's registry at fork time and keeps it for its
lifetime.  Rings are only rebuilt in the publish daemon (where the
per-ring Raft groups live); other subprocesses see whatever the
parent had at fork.

Routing
-------
``_ROUTING`` is a per-process snapshot of the cluster-log
:class:`RoutingStateMachine` (data_type -> ring_id-or-None).
Populated by ``RaftService`` on each committed ``ROUTE`` entry so
gate sites can decide quickly without IPC.  A data type with no
routing entry is broadcast — every master keeps acting as the owner.

Why not pass a ring instance everywhere
---------------------------------------
The receivers we gate (``EventMonitor.handle_event`` at master.py)
live across a ``SignalHandlingProcess`` boundary from the place that
owns Raft membership (``RaftService`` inside the publish daemon).  A
single instance can't be smuggled across a fork without a shared-
memory backing store.  A module-level registry per process is the
smallest abstraction that survives both the current shape and any
future move to a shared-memory ring.
"""

import logging
import threading

from salt.cluster.ring import HashRing

log = logging.getLogger(__name__)


# Per-process registry of named rings.  Module load creates an empty
# dict; ``RaftService`` populates entries as rings come up.  A
# subprocess inherits this dict at fork time.
_RINGS = {}

# Per-process routing snapshot: data_type -> ring_id or None.  ``None``
# (or a missing entry) means broadcast — every master is the owner
# for that data type.
_ROUTING = {}

_LOCK = threading.RLock()


# The canonical name for the legacy single-ring path so pre-multi-ring
# callers of ``owns(opts, key)`` route to a stable place.
DEFAULT_RING = "cluster"


def get_ring(name=DEFAULT_RING):
    """
    Return this process's :class:`HashRing` for the named ring.

    Creates an empty ring on first reference so callers never have to
    null-check.  Use only from code that needs ring-internals
    (diagnostics, tests).  Production call sites should prefer
    :func:`owns_for` so the ownership decision flows through one
    place.
    """
    with _LOCK:
        ring = _RINGS.get(name)
        if ring is None:
            ring = HashRing()
            _RINGS[name] = ring
        return ring


def owns(opts, key, ring=DEFAULT_RING):
    """
    Return ``True`` if this master should process *key* locally.

    *opts* must carry ``"interface"`` — the cluster-wide node identity
    matching :func:`rebuild`'s input and ``cluster_peers``.  *ring* is
    the name of the ring to consult (defaults to the legacy
    ``"cluster"`` ring so pre-multi-ring call sites keep working).

    Empty rings answer ``True`` for every key, so a master that has
    not had its ring populated (subprocess pre-fork, or one without a
    routing entry) keeps the broadcast behaviour.
    """
    node_id = opts.get("interface")
    if node_id is None:
        # Defensive: opts without an interface (some test fixtures)
        # act as a standalone master — own everything.
        return True
    return get_ring(ring).owns(key, node_id)


def owns_for(opts, data_type, key):
    """
    Multi-ring ownership gate.

    Consults the routing table for *data_type*:

    * No entry, or entry mapping to ``None``: broadcast — every
      master owns everything (returns ``True``).
    * Entry maps to a ring this master *does not* host locally:
      returns ``False``.  Per the design the operator must arrange
      for traffic to reach a ring member; non-members no-op writes.
    * Entry maps to a ring this master hosts: defers to that ring's
      :meth:`HashRing.owns` answer.

    Used by gate sites in :mod:`salt.master` to decide whether to
    persist a job/event/etc. write locally.

    When the answer is ``False`` because this master isn't a ring
    member, the call increments a per-(data_type, ring) drop counter
    surfaced via :func:`drop_stats` so operators can detect a
    misconfigured load balancer — i.e. traffic for a routed data
    type landing on masters that aren't in the ring.
    """
    ring_id = _ROUTING.get(data_type)
    if ring_id is None:
        return True  # broadcast
    with _LOCK:
        ring = _RINGS.get(ring_id)
    if ring is None or not ring.nodes():
        # This master is not in the ring (no local Node) or the ring
        # is still empty.  Non-member masters no-op writes for routed
        # data — the operator is expected to route traffic at the
        # load balancer.  Count the drop so a misconfig is visible.
        _record_drop(data_type, ring_id, "not_a_member")
        return False
    node_id = opts.get("interface")
    if node_id is None:
        return True
    if ring.owns(key, node_id):
        return True
    # Owned by some other ring member.  This is the expected sharding
    # path, not a misconfig — counted separately so operators can
    # tell shedding from drops.
    _record_drop(data_type, ring_id, "other_ring_member")
    return False


# Per-process drop counters — populated by ``owns_for`` when it
# answers False, queried by the ``cluster.routes`` runner so
# operators can spot misconfigured routing without tailing logs.
# Keyed by ``(data_type, ring_id, reason)``; reason is
# "not_a_member" (this master isn't in the named ring at all) or
# "other_ring_member" (the key hashed to a sibling — expected
# under sharded routing, included for completeness).
_DROP_STATS = {}


def _record_drop(data_type, ring_id, reason):
    """
    Bump the drop counter for the given (data_type, ring, reason) bucket
    and emit a rate-limited log line so a misconfigured deployment is
    visible in the master log without operator intervention.

    Rate limit: one log line per (data_type, ring_id, reason) bucket
    every ``_DROP_LOG_RATE_SECONDS`` (60s default).  Counters keep
    advancing on every drop; the log line carries the cumulative
    count so an operator scanning logs can see the magnitude even
    between rate-limited windows.

    Only the ``not_a_member`` reason logs at WARNING — that's the
    misconfig signal.  ``other_ring_member`` is the expected
    sharded-traffic path and would drown out the warning, so it's
    counter-only.
    """
    import time  # pylint: disable=import-outside-toplevel

    key = (data_type, ring_id, reason)
    now = time.monotonic()
    log_now = False
    count = 0
    with _LOCK:
        _DROP_STATS[key] = _DROP_STATS.get(key, 0) + 1
        count = _DROP_STATS[key]
        if reason == "not_a_member":
            last = _DROP_LAST_LOG.get(key, 0.0)
            if now - last >= _DROP_LOG_RATE_SECONDS:
                _DROP_LAST_LOG[key] = now
                log_now = True
    if log_now:
        log.warning(
            "ring_membership: dropping %s write — this master is not in "
            "ring %r (count=%d).  Operator likely needs to route traffic "
            "for data_type=%s to a ring member.",
            data_type,
            ring_id,
            count,
            data_type,
        )


# Rate-limit knob.  60 s is fast enough for an operator running a
# checklist to spot the warning, slow enough that a busy master
# under sustained misrouting doesn't spam the log.
_DROP_LOG_RATE_SECONDS = 60.0

# Last-log-time tracking, parallel to _DROP_STATS but consumed by
# the rate limiter, not the operator surface.
_DROP_LAST_LOG = {}


def drop_stats():
    """
    Return a snapshot of the per-process drop counters.

    Shape::

        {
            "<data_type>": {
                "ring_id": "<ring_id>",
                "not_a_member": int,
                "other_ring_member": int,
            },
            ...
        }

    ``not_a_member`` is the field operators should care about — a
    rising count means traffic for a routed data type is landing on
    masters that aren't in the ring.  ``other_ring_member`` is
    expected to rise steadily under sharded routing and isn't a
    misconfig signal on its own.
    """
    with _LOCK:
        snapshot = dict(_DROP_STATS)
    result = {}
    for (data_type, ring_id, reason), count in snapshot.items():
        bucket = result.setdefault(
            data_type,
            {"ring_id": ring_id, "not_a_member": 0, "other_ring_member": 0},
        )
        bucket[reason] = count
    return result


def rebuild(name_or_voters, voters=None, replicas=1):
    """
    Replace the named ring's contents.

    Two call shapes:

    * ``rebuild(voters)`` (legacy single-ring) — targets the
      ``"cluster"`` ring for backward compatibility.
    * ``rebuild(name, voters, replicas=N)`` (multi-ring) — names the
      ring explicitly.

    Idempotent: rebuilding to the same voter set is cheap and emits
    no spurious log noise.

    *voters* is the committed voter list — learners are excluded
    because they don't yet hold replica state to be the canonical
    owner of anything.
    """
    if voters is None:
        # Legacy shape: rebuild(voters_list)
        name = DEFAULT_RING
        voters_list = name_or_voters
    else:
        name = name_or_voters
        voters_list = voters
    with _LOCK:
        ring = _RINGS.get(name)
        if ring is None:
            ring = HashRing(replicas=replicas)
            _RINGS[name] = ring
        elif replicas != ring._replicas:
            # Replica count changed — rebuild a new ring instead of
            # silently keeping the old factor.
            ring = HashRing(replicas=replicas)
            _RINGS[name] = ring
        ring.rebuild(voters_list)


def set_route(data_type, ring_id):
    """
    Update the per-process routing snapshot.

    Called by ``RaftService`` after each committed ``ROUTE`` entry so
    gate sites in this process see the new mapping without IPC.  Set
    *ring_id* to ``None`` to clear the route (broadcast).
    """
    with _LOCK:
        if ring_id is None:
            _ROUTING.pop(data_type, None)
        else:
            _ROUTING[data_type] = ring_id


def get_routes():
    """
    Return a copy of the per-process routing snapshot.  Diagnostic /
    test helper.
    """
    with _LOCK:
        return dict(_ROUTING)


def drop_ring(name):
    """
    Remove the named ring from the registry.  Called when ``RaftService``
    tears down a per-ring Raft group so subsequent ``owns_for`` calls
    treat this master as a non-member of the destroyed ring.
    """
    with _LOCK:
        _RINGS.pop(name, None)


def reset():
    """
    Replace the registry with a fresh empty one.

    Test-only escape hatch — production code never calls this.  Pytest
    fixtures that build and tear down a cluster within the same
    process need to reset the registry between tests so leftover
    voters from one test don't bleed into the next.
    """
    with _LOCK:
        _RINGS.clear()
        _ROUTING.clear()
        _DROP_STATS.clear()
        _DROP_LAST_LOG.clear()
