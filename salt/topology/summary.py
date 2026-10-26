"""
Fixed-size per-cluster aggregate propagated between topology peers.

Each cluster builds a :class:`ClusterSummary` of its own state on
``topology_summary_interval`` and pushes it to each direct peer.
Peers fold the summary into local state and re-forward it to their
own peers with the ``path`` field extended, so non-adjacent clusters
learn of each other's existence transitively via gossip.

Summary propagation is also what populates the routing table (see
:mod:`salt.topology.router`): the ``path`` carried on each summary
tells the receiver which direct peer to use as a next hop for the
origin cluster.

Size is bounded regardless of minion count --- a few counts, a few
small grain histograms, a short path of ``cluster_id`` strings ---
so this mechanism scales to arbitrarily large graphs.
"""

import logging
from typing import NamedTuple

log = logging.getLogger(__name__)


class ClusterSummary(NamedTuple):
    """
    Aggregate state of one cluster as seen by one of its peers.

    :param cluster_id: Origin cluster.  The ``path`` field tells
        the receiver which route this summary took, which also
        populates the routing table.
    :param path: Ordered tuple of ``cluster_id`` strings the
        summary has traversed, starting at the origin and
        ending at the direct-peer sender.  Length is the hop
        distance from origin to this receiver.  Used both for
        route derivation and for loop detection --- any summary
        whose path contains the receiver's own ``cluster_id``
        is dropped.  **Path authentication**: on receive,
        :meth:`salt.topology.router.TopologyRouter.ingest_summary`
        asserts ``path[-1] == inbound_link.peer_cluster_id`` so
        a hostile peer cannot forge the path to poison the
        routing table.
    :param minion_count: Total accepted minion keys at the
        origin cluster at ``origin_at`` time.
    :param up_count: Of those, how many are presence-up
        (last-seen within the master's presence window).
    :param grain_histograms: Optional per-grain-key value
        counts (e.g. ``{"os": {"Ubuntu": 900, "RHEL": 303}}``).
        Populated for the subset of grain keys named in
        ``opts["topology_summary_grains"]``; empty by default.
    :param origin_seq: Monotonically-increasing sequence
        number, incremented by each :func:`collect` call at the
        origin.  Receivers use this (not ``origin_at`` wall
        clock) to decide which of two summaries from the same
        origin is newer: clock skew between the origin and a
        receiver that cycles the newer summary back can cause
        older state to win otherwise.
    :param origin_at: Unix timestamp when the origin generated
        this summary.  Diagnostic only; comparisons for freshness
        use ``origin_seq``.
    """

    cluster_id: str
    path: tuple
    minion_count: int
    up_count: int
    grain_histograms: dict
    origin_seq: int
    origin_at: float


def collect(opts):
    """
    Build a :class:`ClusterSummary` for this cluster from local
    state.

    Called on ``topology_summary_interval`` by the summary
    heartbeat task.  Reads accepted-key count, presence state,
    and --- if ``opts["topology_summary_grains"]`` is set --- a
    grain histogram over the master's grain cache for the named
    keys.

    The returned summary has ``path = (opts["cluster_id"],)`` and
    ``origin_at = time.time()``.  Peers that receive and
    re-forward the summary extend ``path`` via
    :func:`with_path_extended`.
    """


def with_path_extended(summary, next_hop):
    """
    Return a new :class:`ClusterSummary` with ``next_hop``
    appended to ``summary.path``.

    Called by the forwarder before relaying the summary to its
    own peers so each successive receiver sees the full route the
    summary took.

    :param summary: The :class:`ClusterSummary` to extend.
    :param next_hop: The forwarder's own ``cluster_id``.
    :returns: A new :class:`ClusterSummary`; ``summary`` is
        unchanged (NamedTuple semantics).
    """


def is_cycle_for(summary, cluster_id):
    """
    Return True if ``cluster_id`` is already present in
    ``summary.path``.

    Receivers call this to drop summaries that would otherwise
    loop back through themselves on a cyclic graph.
    """


def serialize(summary):
    """
    Return a msgpack-friendly dict for wire transport.

    Field names are the NamedTuple attribute names; types are
    plain Python (lists for tuples, nested dicts for histograms).
    Caller is responsible for wrapping in whatever transport
    envelope the link protocol expects.
    """


def deserialize(data):
    """
    Reconstruct a :class:`ClusterSummary` from its wire dict.

    :raises ValueError: If the dict is missing required fields or
        has values of the wrong type.  Does not attempt to coerce
        types --- an incoming summary with the wrong shape is
        treated as a protocol error and dropped by the caller.
    """


def merge_into(summary, aggregate_counts, aggregate_histograms):
    """
    Fold ``summary``'s counts and histograms into caller-owned
    aggregate dicts.

    Used by ``topology.status`` and ``manage.status`` runners to
    produce whole-graph totals without constructing an
    intermediate flattened list.  Caller controls the aggregate
    state's lifetime, so this function is a pure accumulator and
    does not mutate ``summary``.
    """
