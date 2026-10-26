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

import itertools
import logging
import time
from typing import NamedTuple

import salt.cache
import salt.exceptions
import salt.key

log = logging.getLogger(__name__)


# Module-level monotonic sequence counter.  ``itertools.count`` is
# incremented atomically under the CPython GIL, so concurrent
# ``collect`` calls from the summary heartbeat task + an ad-hoc
# ``topology.status`` runner cannot collide on the same ``origin_seq``.
# This is the clock-skew mitigation called out in the ``origin_seq``
# docstring: receivers compare seq numbers (not wall-clock
# ``origin_at``) when picking the newer of two summaries.
_SEQ_COUNTER = itertools.count(1)


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


def _count_accepted_minions(opts):
    """
    Return the number of accepted minion keys for the master
    described by *opts*.

    Any PKI read failure is logged and treated as zero rather than
    raising --- the summary heartbeat must not take the publish
    daemon down over a transient disk hiccup.
    """
    try:
        key = salt.key.get_key(opts)
        return len(key.list_keys().get("minions", []))
    except (OSError, salt.exceptions.SaltException) as exc:  # pragma: no cover
        log.warning("topology summary: accepted-key count failed: %s", exc)
        return 0
    except Exception as exc:  # pylint: disable=broad-except  # pragma: no cover
        log.warning("topology summary: accepted-key count errored: %s", exc)
        return 0


def _cached_minion_ids(opts):
    """
    Return the set of minion ids whose grains are cached at the
    master, i.e. minions that have authed and reported in within
    the master's cache window.  Used both as the ``up_count``
    source and as the ``grain_histograms`` iteration set.
    """
    try:
        cache = salt.cache.factory(opts)
        ids = cache.list("grains") or []
    except salt.exceptions.SaltCacheError as exc:  # pragma: no cover
        log.warning("topology summary: grain cache list failed: %s", exc)
        return []
    except Exception as exc:  # pylint: disable=broad-except  # pragma: no cover
        log.warning("topology summary: grain cache list errored: %s", exc)
        return []
    return list(ids)


def _build_grain_histograms(opts, grain_keys, cached_ids):
    """
    Build ``{grain_key: {value: count}}`` for *grain_keys* across
    the minions whose grains are cached.  Keys with no data still
    appear in the result (as empty dicts) so receivers can
    distinguish "we asked for this grain, no minion reports it"
    from "we never asked for this grain".
    """
    histograms = {k: {} for k in grain_keys}
    if not cached_ids:
        return histograms
    try:
        cache = salt.cache.factory(opts)
    except Exception as exc:  # pylint: disable=broad-except  # pragma: no cover
        log.warning("topology summary: grain cache factory failed: %s", exc)
        return histograms
    for minion_id in cached_ids:
        try:
            grains = cache.fetch("grains", minion_id)
        except salt.exceptions.SaltCacheError:  # pragma: no cover
            continue
        except Exception:  # pylint: disable=broad-except  # pragma: no cover
            continue
        if not grains:
            continue
        for grain_key in grain_keys:
            if grain_key not in grains:
                continue
            value = grains[grain_key]
            # Grain values can be lists/dicts; stringify for histogram
            # bucketing so wire form stays plain-dict-of-plain-dict.
            if isinstance(value, (list, tuple)):
                for sub in value:
                    bucket = str(sub)
                    histograms[grain_key][bucket] = (
                        histograms[grain_key].get(bucket, 0) + 1
                    )
            else:
                bucket = str(value)
                histograms[grain_key][bucket] = histograms[grain_key].get(bucket, 0) + 1
    return histograms


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
    cluster_id = opts["cluster_id"]
    minion_count = _count_accepted_minions(opts)
    cached_ids = _cached_minion_ids(opts)
    # ``up_count`` is bounded above by ``minion_count`` --- the
    # grain cache can lag behind key removal in corner cases
    # (minion key deleted while a stale grain file still exists),
    # so clamp here rather than letting an inconsistent snapshot
    # produce ``up_count > minion_count`` on the wire.
    up_count = min(len(cached_ids), minion_count)

    grain_keys = opts.get("topology_summary_grains") or []
    if grain_keys:
        grain_histograms = _build_grain_histograms(opts, grain_keys, cached_ids)
    else:
        grain_histograms = {}

    return ClusterSummary(
        cluster_id=cluster_id,
        path=(cluster_id,),
        minion_count=minion_count,
        up_count=up_count,
        grain_histograms=grain_histograms,
        origin_seq=next(_SEQ_COUNTER),
        origin_at=time.time(),
    )


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
    return summary._replace(path=summary.path + (next_hop,))


def is_cycle_for(summary, cluster_id):
    """
    Return True if ``cluster_id`` is already present in
    ``summary.path``.

    Receivers call this to drop summaries that would otherwise
    loop back through themselves on a cyclic graph.
    """
    return cluster_id in summary.path


def serialize(summary):
    """
    Return a msgpack-friendly dict for wire transport.

    Field names are the NamedTuple attribute names; types are
    plain Python (lists for tuples, nested dicts for histograms).
    Caller is responsible for wrapping in whatever transport
    envelope the link protocol expects.
    """
    return {
        "cluster_id": summary.cluster_id,
        "path": list(summary.path),
        "minion_count": summary.minion_count,
        "up_count": summary.up_count,
        "grain_histograms": {k: dict(v) for k, v in summary.grain_histograms.items()},
        "origin_seq": summary.origin_seq,
        "origin_at": summary.origin_at,
    }


_REQUIRED_FIELDS = (
    "cluster_id",
    "path",
    "minion_count",
    "up_count",
    "grain_histograms",
    "origin_seq",
    "origin_at",
)


def deserialize(data):
    """
    Reconstruct a :class:`ClusterSummary` from its wire dict.

    :raises ValueError: If the dict is missing required fields or
        has values of the wrong type.  Does not attempt to coerce
        types --- an incoming summary with the wrong shape is
        treated as a protocol error and dropped by the caller.
    """
    if not isinstance(data, dict):
        raise ValueError(f"ClusterSummary wire form must be a dict, got {type(data)!r}")
    missing = [f for f in _REQUIRED_FIELDS if f not in data]
    if missing:
        raise ValueError(
            "ClusterSummary wire form missing fields: {}".format(", ".join(missing))
        )
    if not isinstance(data["cluster_id"], str):
        raise ValueError("ClusterSummary.cluster_id must be str")
    if not isinstance(data["path"], (list, tuple)):
        raise ValueError("ClusterSummary.path must be list or tuple")
    for hop in data["path"]:
        if not isinstance(hop, str):
            raise ValueError("ClusterSummary.path entries must be str")
    # ``bool`` is a subclass of ``int`` in Python; reject explicitly so
    # a stray ``True`` on the wire doesn't masquerade as a count.
    if isinstance(data["minion_count"], bool) or not isinstance(
        data["minion_count"], int
    ):
        raise ValueError("ClusterSummary.minion_count must be int")
    if isinstance(data["up_count"], bool) or not isinstance(data["up_count"], int):
        raise ValueError("ClusterSummary.up_count must be int")
    if not isinstance(data["grain_histograms"], dict):
        raise ValueError("ClusterSummary.grain_histograms must be dict")
    for grain_key, buckets in data["grain_histograms"].items():
        if not isinstance(grain_key, str):
            raise ValueError("ClusterSummary.grain_histograms keys must be str")
        if not isinstance(buckets, dict):
            raise ValueError(
                f"ClusterSummary.grain_histograms[{grain_key!r}] must be dict"
            )
    if isinstance(data["origin_seq"], bool) or not isinstance(data["origin_seq"], int):
        raise ValueError("ClusterSummary.origin_seq must be int")
    if not isinstance(data["origin_at"], (int, float)) or isinstance(
        data["origin_at"], bool
    ):
        raise ValueError("ClusterSummary.origin_at must be numeric")

    return ClusterSummary(
        cluster_id=data["cluster_id"],
        path=tuple(data["path"]),
        minion_count=data["minion_count"],
        up_count=data["up_count"],
        grain_histograms={k: dict(v) for k, v in data["grain_histograms"].items()},
        origin_seq=data["origin_seq"],
        origin_at=float(data["origin_at"]),
    )


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
    aggregate_counts["minion_count"] = (
        aggregate_counts.get("minion_count", 0) + summary.minion_count
    )
    aggregate_counts["up_count"] = (
        aggregate_counts.get("up_count", 0) + summary.up_count
    )
    for grain_key, buckets in summary.grain_histograms.items():
        target = aggregate_histograms.setdefault(grain_key, {})
        for value, count in buckets.items():
            target[value] = target.get(value, 0) + count
