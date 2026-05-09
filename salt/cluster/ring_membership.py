"""
High-level ownership query for cluster-distributed state.

Wraps a per-process :class:`salt.cluster.ring.HashRing` instance with
the convenience API the rest of the cluster code reaches for:

* :func:`owns` — does this master own *key* per the current ring?
* :func:`rebuild` — replace the ring contents (called from
  :meth:`salt.cluster.consensus.service.RaftService._on_membership_change`).
* :func:`get_ring` — escape hatch for tests and diagnostics.

Stage 0 semantics
-----------------
For the initial rollout the ring is **per-process** (a module-level
singleton) and only ``RaftService`` rebuilds its copy.  Every other
process (notably ``EventMonitor``, which runs as its own
``SignalHandlingProcess`` subprocess and does not see the parent's
membership commits) keeps an *empty* ring.  Because
:meth:`HashRing.owns` returns ``True`` for an empty ring, every master
still acts as the owner of every key in those subprocesses.  That
preserves today's broadcast-fan-out behaviour while putting the gate
points in code so a future config flip — *not* a code change — can
turn on real sharding.

Stage 1 will switch to a process-shared ring driven by a
``RingConfigStateMachine`` so every subprocess agrees on the
authoritative ring.  At that point the call sites here do not need to
change; only the underlying transport for ring state does.

Why not pass a ring instance everywhere
---------------------------------------
The receivers we gate (``EventMonitor.handle_event`` at master.py:1149-
1197) live across a ``SignalHandlingProcess`` boundary from the place
that owns Raft membership (``RaftService`` inside the publish daemon).
A single instance can't be smuggled across a fork without a shared-
memory backing store.  A module-level singleton per process is the
smallest abstraction that survives both the current shape and the
stage-1 swap.
"""

import logging
import threading

from salt.cluster.ring import HashRing

log = logging.getLogger(__name__)


# Per-process singleton.  Module load creates an empty ring; only
# RaftService.rebuild() populates it.  A subprocess inherits the empty
# ring at fork time and keeps it empty for its lifetime in stage 0.
_PROCESS_RING = HashRing()
_LOCK = threading.RLock()


def get_ring():
    """
    Return this process's :class:`HashRing` singleton.

    Use only from code that needs ring-internals (diagnostics, tests).
    Production call sites should prefer :func:`owns` so the ownership
    decision flows through one place.
    """
    return _PROCESS_RING


def owns(opts, key):
    """
    Return ``True`` if this master should process *key* locally.

    *opts* must carry ``"interface"`` — the cluster-wide node identity
    matching :func:`rebuild`'s input and ``cluster_peers``.

    Stage 0: the ring is empty in any process that did not call
    :func:`rebuild` (which is currently only ``RaftService``).  An
    empty ring's :meth:`HashRing.owns` returns ``True`` for every key,
    so behaviour is unchanged from the pre-ring code path.
    """
    node_id = opts.get("interface")
    if node_id is None:
        # Defensive: opts without an interface (some test fixtures) act
        # as a standalone master — own everything.
        return True
    return _PROCESS_RING.owns(key, node_id)


def rebuild(voters):
    """
    Replace the process ring's contents with *voters*.

    Called from :meth:`RaftService._on_membership_change` after every
    committed CONFIG entry.  Idempotent: rebuilding to the same voter
    set is cheap and emits no spurious log noise beyond ``HashRing``'s
    own info-level "rebuilt with N node(s)" message.

    *voters* is the committed voter list — learners are excluded
    because they don't yet hold replica state to be the canonical
    owner of anything.  When the ring policy later allows
    learner-as-replica, this function will grow a ``learners`` arg.
    """
    with _LOCK:
        _PROCESS_RING.rebuild(voters)


def reset():
    """
    Replace the process ring with a fresh empty one.

    Test-only escape hatch — production code never calls this.  Pytest
    fixtures that build and tear down a cluster within the same
    process need to reset the ring between tests so leftover voters
    from one test don't bleed into the next.
    """
    global _PROCESS_RING  # pylint: disable=global-statement
    with _LOCK:
        _PROCESS_RING = HashRing()
