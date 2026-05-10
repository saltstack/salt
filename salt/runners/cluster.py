"""
Salt runner for cluster ring management.

Stage 1 of the ring rollout: this runner is the operator-facing
control surface for the consistent-hash ring that distributes job /
key state across cluster masters.

Currently exposes a *query-only* view (``ring_info``) of the ring
state seen by the local master.  The proposal path (``ring_set``)
that commits a ``RING_CONFIG`` entry through Raft is deferred
because it requires IPC from the runner's subprocess across to the
publish daemon's ``RaftService``; that is a follow-up slice.

CLI Examples:

.. code-block:: bash

    # Show this master's current ring state.
    salt-run cluster.ring_info

.. versionadded:: 3009.0
"""

import logging

log = logging.getLogger(__name__)


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


def ring_set(members=None, replicas=None):  # pylint: disable=unused-argument
    """
    Propose a new ring policy through Raft.

    Stage 1 placeholder — actual Raft propose path requires IPC from
    this runner subprocess to the publish daemon's
    :class:`RaftService`, which is not yet wired.  Today the function
    raises :class:`NotImplementedError` so an operator who tries it
    sees the gap loudly rather than thinking their commit landed.

    Once the IPC path lands, expected semantics:

    * *members*: ``"self"`` (default ring contents — every master a
      single-node ring, broadcast everywhere) or ``"voters"`` (ring
      tracks the Raft voter set so writes shard).
    * *replicas*: integer >= 1.  ``1`` (default) means each key has
      exactly one owner; higher values request additional replica
      owners for fault tolerance.

    Until the propose path lands, operators wanting to flip the
    policy can call ``RaftService.propose_ring_config`` directly from
    a python hook running inside the master process — see the
    functional tests under
    ``tests/pytests/functional/cluster/consensus/test_raft_service.py``.

    CLI Example (will raise until stage 2):

    .. code-block:: bash

        salt-run cluster.ring_set members=voters replicas=2
    """
    raise NotImplementedError(
        "cluster.ring_set: cross-process Raft propose path is not yet wired. "
        "Track GAPS.md for the follow-up that adds runner -> RaftService IPC."
    )
