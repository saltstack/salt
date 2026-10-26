"""
Topology operator commands.

Exposed via ``salt-run topology.<command>``. Read-mostly; the one
mutation (:func:`trust`) is a thin wrapper over ``salt-key --master``
for convenience in automation workflows that would otherwise shell
out to the key CLI.

All commands are no-ops with an INFO log when
``opts["topology_enabled"]`` is False.
"""

import logging

log = logging.getLogger(__name__)

__virtualname__ = "topology"


def __virtual__():
    """
    Available on any master; individual commands check
    ``opts["topology_enabled"]`` and return a helpful error dict
    if topology is off, rather than hiding the runner entirely.
    This matches the UX of ``salt-key`` --- the command exists
    even when the feature is inactive, and the error message
    points at the config knob.
    """
    return __virtualname__


def status():
    """
    Return a tree-shaped summary of the reachable topology graph.

    Each entry contains:

    * ``cluster_id``, ``minion_count``, ``up_count``.
    * Direct-peer entries with their last-received
      :class:`~salt.topology.summary.ClusterSummary`.
    * Path-to-this-master (any one of possibly multiple paths)
      for every non-direct cluster, derived from the routing
      table.

    CLI output format is Salt's standard output; a client wanting
    structured data can use ``--out json``.
    """


def links():
    """
    Return detailed health and metadata for every
    :class:`~salt.topology.link.TopologyLink` in the local
    :mod:`~salt.topology.link_manager`.

    Fields per link:

    * ``peer_cluster_id``, ``health``, ``endpoints``.
    * ``last_summary_at``, ``last_publish_sent``,
      ``last_return_sent``.
    * ``breadcrumbs_active``, ``bytes_sent``, ``bytes_received``.

    Used primarily for diagnostics and dashboards.
    """


def peers():
    """
    Return the list of peer references from this master's
    ``topology.conf``, annotated with current accept state and
    attach state for each.

    States surfaced:

    * ``configured`` --- in topology.conf but no attach yet.
    * ``pending`` --- our key is in the peer's ``masters_pre/``
      (we are waiting on operator acceptance there).
    * ``attached`` --- link is live, handshake complete.
    * ``rejected`` --- peer has us in ``masters_rejected/``.
    * ``unreachable`` --- all configured endpoints have failed
      TCP connect recently.
    """


def trust(cluster_id, action):
    """
    Thin wrapper over ``salt-key --master``.

    :param cluster_id: Peer cluster to act on.
    :param action: One of ``accept``, ``reject``, ``delete``,
        ``fingerprint``.
    :returns: The resulting state (``accepted``, ``rejected``,
        etc.) for the named ``cluster_id``. On ``fingerprint``,
        returns the pub-key fingerprint as a string.
    """


def find(minion_id, timeout=10):
    """
    On-demand fan-out lookup: ask every reachable cluster whether
    it has an accepted key for ``minion_id``.

    Implements the "where is this minion" diagnostic use case
    without requiring any resting per-minion state at this master.
    See the "knowing-about-minions" section of the design doc for
    the scaling rationale.

    :param minion_id: The minion id to locate.
    :param timeout: Seconds to wait for responses before returning
        partial results.
    :returns: Dict mapping ``cluster_path`` (a ``/``-joined string
        like ``"east/sub1"``) to the minion id as known locally
        on that cluster. Empty dict if no cluster has the id by
        the deadline.
    """


def graph(fmt="text"):
    """
    Render the known topology graph.

    :param fmt: Output format.

        * ``text`` (default) --- indented tree-ish rendering.
        * ``dot`` --- Graphviz DOT source, pipe-able to ``dot
          -Tpng``.
        * ``json`` --- adjacency-list JSON (``{"nodes": [...],
          "edges": [...]}``) for programmatic consumption.
    """
