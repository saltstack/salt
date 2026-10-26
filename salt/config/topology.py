"""
Load and validate the per-master ``topology.conf``.

Master topology connects multiple 3008.x master clusters into a
loop-detected peer graph.  The per-master config is minimal: each
master declares only its own ``cluster_id`` and the seed addresses
of its direct peers.  The full peer graph emerges from each
master's local view --- no master declares descendants.

This module contains four things:

* :data:`DEFAULT_EVENT_SUBSCRIPTIONS`, the default set of event tag
  patterns forwarded across a peer link when the operator does not
  override.
* :class:`PeerRef`, a NamedTuple describing one seed entry from
  ``topology.conf``.
* :class:`TopologyConfig`, the parsed-and-validated config object
  consumed by :mod:`salt.topology` runtime machinery.
* :func:`validate_topology_config` and :func:`load_topology_config`,
  the public entry points called from master configuration
  processing.  See :mod:`salt.config.worker_pools` for the sibling
  pattern.

The topology config file lives at ``opts["topology_config_file"]``
(default ``/etc/salt/topology.conf``) and is read only when
``opts["topology_enabled"]`` is True.  On a disabled or missing-file
master, :func:`load_topology_config` returns a disabled
:class:`TopologyConfig` with empty peers so callers can rely on the
``enabled`` attribute without a None-check.
"""

import logging
from typing import NamedTuple

log = logging.getLogger(__name__)


DEFAULT_EVENT_SUBSCRIPTIONS = (
    "salt/job/*/ret/*",
    "salt/job/*/new",
)
# Default set of event tag patterns that cross a peer link.
# Operators who want presence events, authentication events, or the
# full event firehose override this via ``event_subscriptions:`` in
# ``topology.conf``.  The default is job events only --- cheapest
# wire volume, lowest surprise, matches the operational shape of
# ``syndic_mode: cluster`` in the pre-topology world.


# Regex a cluster_id must match: short, lowercase, no shell-sensitive
# characters.  Enforced by :func:`validate_topology_config` and
# (critically) re-validated at Raft apply time on peer-supplied
# cluster_ids so a hostile peer cannot claim a reserved name.
CLUSTER_ID_RE = r"^[a-z0-9][a-z0-9_-]*$"


class PeerRef(NamedTuple):
    """
    A single peer entry from ``topology.conf``.

    :param host: Seed hostname or IP.  The full peer list for the
        peer's cluster is learned from Raft state during handshake;
        this entry is only used for first-connect bootstrap and as
        a fallback endpoint if all learned endpoints become
        unreachable.
    :param port: TCP port for the peer's ``topology_link_port``.
        Falls back to this master's own ``topology_link_port`` opt
        when ``None``.
    :param finger: Optional pinned fingerprint (TOFU avoidance) of
        the peer's ``master_identity.pub``.  If present and the
        presented key does not match, handshake aborts with an
        authentication error logged at CRITICAL.
    """

    host: str
    port: int = None
    finger: str = None


class TopologyConfig(NamedTuple):
    """
    Parsed and validated contents of ``topology.conf``.

    :param cluster_id: This logical master's identity in the graph.
        Short, unique within the graph.  Required when ``enabled``
        is True.
    :param peers: Zero or more :class:`PeerRef` entries.  Order
        does not matter; duplicates with identical ``(host, port)``
        are deduplicated.  Duplicates with conflicting fingerprints
        are a validation error.
    :param event_subscriptions: Glob tag patterns forwarded from
        this master to each peer.  Defaults to
        :data:`DEFAULT_EVENT_SUBSCRIPTIONS` (job events only).
    :param enabled: True when ``opts["topology_enabled"]`` is True
        AND the config file loaded and validated successfully.
        False means :mod:`salt.topology` should remain inert in
        this process.
    """

    cluster_id: str
    peers: tuple
    event_subscriptions: tuple
    enabled: bool


def validate_topology_config(cfg):
    """
    Enforce structural and security invariants on a
    :class:`TopologyConfig` before the master is allowed to start.

    Called from master configuration processing, like
    :func:`salt.config.worker_pools.validate_worker_pools_config`.
    Also safe to call on a hand-constructed instance during tests.

    Checks:

    * ``cluster_id`` present and non-empty when ``enabled`` is
      True.
    * ``cluster_id`` matches :data:`CLUSTER_ID_RE` --- short,
      lowercase, no spaces or shell-sensitive characters.
    * ``cluster_id`` is not one of the reserved MmapCache sentinel
      keys (``__identity_pub__`` et al.).  Belt-and-braces: the
      regex above already rejects leading underscores, but we
      enumerate the reserved names explicitly so a future regex
      change does not silently open an attack vector.
    * No empty-string host entries in ``peers``.
    * ``port`` values, when set, fall in the usable TCP range
      (1-65535).
    * No duplicate ``(host, port)`` pairs with conflicting
      fingerprints; identical fingerprints are deduped silently
      by :func:`load_topology_config`.
    * ``event_subscriptions`` entries parse as valid glob tag
      patterns via :func:`fnmatch.translate`.

    :raises ValueError: On any invariant violation.  The message
        names the specific field at fault.
    """


def load_topology_config(opts):
    """
    Load and validate the topology config file for this master.

    Behavior matches the sibling
    :func:`salt.config.worker_pools.get_worker_pools_config`:

    * ``opts["topology_enabled"]`` False -> returns a disabled
      :class:`TopologyConfig` with empty peers.  The file is not
      opened.
    * File absent at ``opts["topology_config_file"]`` -> returns a
      disabled :class:`TopologyConfig` with an INFO log line.
    * File present and valid -> returns an enabled
      :class:`TopologyConfig` after passing
      :func:`validate_topology_config`.

    :raises ValueError: If topology is enabled and the config file
        is malformed, missing ``cluster_id``, or fails validation.
        Callers in the master startup path treat this as fatal.
    :raises OSError: If the config file is present but unreadable
        (permissions, I/O error).  Fatal at daemon start.
    """
