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

import fnmatch
import logging
import os
import re
from typing import NamedTuple

import salt.utils.files
import salt.utils.yaml

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
#
# ``\A`` and ``\Z`` are used instead of ``^`` and ``$`` because Python's
# ``$`` matches just before a trailing newline by default, which would
# admit ``"east\n"`` --- unsafe as a filename component, log token, or
# MmapCache key.  ``\A``/``\Z`` match only true string boundaries.
CLUSTER_ID_RE = r"\A[a-z0-9][a-z0-9_-]*\Z"


# MmapCache sentinel keys that must never collide with a user-supplied
# cluster_id.  The regex above already rejects leading underscores so
# none of these can match today, but the loader checks the names
# explicitly as a belt-and-braces guard against a future regex
# relaxation silently opening the collision.
_RESERVED_CLUSTER_IDS = frozenset(
    {
        "__identity_pub__",
        "__cluster_meta__",
        "__peer_index__",
    }
)


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


def _disabled_config():
    """Return the canonical disabled :class:`TopologyConfig`.

    Centralized so the ``disabled`` short-circuit and the
    missing-file short-circuit return byte-identical shapes; callers
    that duck-type over ``enabled`` + ``peers`` get the same
    guarantees from both paths.
    """
    return TopologyConfig(
        cluster_id="",
        peers=(),
        event_subscriptions=DEFAULT_EVENT_SUBSCRIPTIONS,
        enabled=False,
    )


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
    if not isinstance(cfg, TopologyConfig):
        raise ValueError(
            f"validate_topology_config expected TopologyConfig, got "
            f"{type(cfg).__name__}"
        )

    # Disabled configs have no invariants to enforce --- callers may
    # construct them with empty values on purpose.
    if not cfg.enabled:
        return

    errors = []

    # cluster_id presence / shape
    cluster_id = cfg.cluster_id
    if not isinstance(cluster_id, str) or not cluster_id:
        errors.append("cluster_id is required when topology is enabled")
    else:
        if cluster_id in _RESERVED_CLUSTER_IDS:
            errors.append(
                f"cluster_id {cluster_id!r} is a reserved MmapCache sentinel name"
            )
        elif not re.match(CLUSTER_ID_RE, cluster_id):
            errors.append(
                f"cluster_id {cluster_id!r} does not match "
                f"{CLUSTER_ID_RE} (short, lowercase, [a-z0-9][a-z0-9_-]*)"
            )

    # peers container
    if not isinstance(cfg.peers, tuple):
        errors.append(f"peers must be a tuple, got {type(cfg.peers).__name__}")
    else:
        seen = {}
        for idx, peer in enumerate(cfg.peers):
            if not isinstance(peer, PeerRef):
                errors.append(
                    f"peers[{idx}] must be PeerRef, got " f"{type(peer).__name__}"
                )
                continue
            if not isinstance(peer.host, str) or not peer.host:
                errors.append(f"peers[{idx}].host is empty or non-string")
                continue
            if peer.port is not None:
                if not isinstance(peer.port, int) or isinstance(peer.port, bool):
                    errors.append(
                        f"peers[{idx}].port must be int, got "
                        f"{type(peer.port).__name__}"
                    )
                elif peer.port < 1 or peer.port > 65535:
                    errors.append(
                        f"peers[{idx}].port {peer.port} out of range " "(1-65535)"
                    )
            # Conflicting-fingerprint detection on identical (host, port).
            key = (peer.host, peer.port)
            if key in seen:
                prior = seen[key]
                if (
                    prior is not None
                    and peer.finger is not None
                    and prior != peer.finger
                ):
                    errors.append(
                        f"peers[{idx}] duplicate (host={peer.host!r}, "
                        f"port={peer.port!r}) with conflicting fingerprints "
                        f"{prior!r} vs {peer.finger!r}"
                    )
            else:
                seen[key] = peer.finger

    # event_subscriptions shape and glob validity.
    if not isinstance(cfg.event_subscriptions, tuple):
        errors.append(
            "event_subscriptions must be a tuple, got "
            f"{type(cfg.event_subscriptions).__name__}"
        )
    else:
        for idx, pattern in enumerate(cfg.event_subscriptions):
            if not isinstance(pattern, str) or not pattern:
                errors.append(f"event_subscriptions[{idx}] must be a non-empty string")
                continue
            try:
                fnmatch.translate(pattern)
            except (
                re.error,
                TypeError,
            ) as exc:  # pragma: no cover - fnmatch is permissive
                errors.append(
                    f"event_subscriptions[{idx}] {pattern!r} is not a valid "
                    f"glob: {exc}"
                )

    if errors:
        raise ValueError(
            "topology.conf validation failed:\n  - " + "\n  - ".join(errors)
        )


def _coerce_peer(raw, idx):
    """Build a :class:`PeerRef` from a raw YAML dict entry.

    Validation of the resulting PeerRef happens in
    :func:`validate_topology_config`; this helper is just structural
    shape-checking.
    """
    if not isinstance(raw, dict):
        raise ValueError(
            f"peers[{idx}] must be a mapping (host/port/finger), got "
            f"{type(raw).__name__}"
        )
    if "host" not in raw:
        raise ValueError(f"peers[{idx}] missing required 'host' key")

    host = raw.get("host")
    port = raw.get("port")
    finger = raw.get("finger")

    if host is not None and not isinstance(host, str):
        raise ValueError(
            f"peers[{idx}].host must be a string, got {type(host).__name__}"
        )
    if finger is not None and not isinstance(finger, str):
        raise ValueError(
            f"peers[{idx}].finger must be a string, got " f"{type(finger).__name__}"
        )
    # Allow None port (falls back to this master's topology_link_port).
    # Any non-None non-int port is caught by the validator below with a
    # consistent error message.
    return PeerRef(host=host, port=port, finger=finger)


def _dedupe_peers(peers):
    """Collapse duplicate ``(host, port)`` entries.

    * Identical ``(host, port, finger)`` -> silently kept once.
    * Identical ``(host, port)``, one with ``finger=None`` and one
      with a specific fingerprint -> keep the pinned entry (more
      specific wins).
    * Identical ``(host, port)`` with two different non-None
      fingerprints -> left in the list; the validator rejects.
    """
    by_key = {}
    order = []
    for peer in peers:
        key = (peer.host, peer.port)
        if key not in by_key:
            by_key[key] = peer
            order.append(key)
            continue
        existing = by_key[key]
        if existing.finger == peer.finger:
            # Exact duplicate; drop.
            continue
        if existing.finger is None and peer.finger is not None:
            # Promote to the pinned entry.
            by_key[key] = peer
            continue
        if existing.finger is not None and peer.finger is None:
            # Keep the pinned entry.
            continue
        # Conflicting non-None fingerprints: leave both so the
        # validator can report the specific pair.
        order.append(key + (id(peer),))
        by_key[key + (id(peer),)] = peer
    return tuple(by_key[k] for k in order)


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
    if not opts.get("topology_enabled"):
        return _disabled_config()

    path = opts.get("topology_config_file")
    if not path:
        # Enabled but no path at all --- treat as missing-file.  Rare
        # (the master opts default to /etc/salt/topology.conf) but
        # we don't want to blow up with a non-informative TypeError.
        log.info("topology enabled but no topology_config_file set; topology inert")
        return _disabled_config()

    if not os.path.exists(path):
        log.info(
            "topology config file %s does not exist; topology inert",
            path,
        )
        return _disabled_config()

    # Open explicitly so a permission failure surfaces as OSError,
    # per the public contract.  salt.utils.yaml.safe_load accepts a
    # file-like object.
    with salt.utils.files.fopen(path, encoding="utf-8") as fh:
        try:
            raw = salt.utils.yaml.safe_load(fh) or {}
        except salt.utils.yaml.YAMLError as exc:
            raise ValueError(
                f"topology.conf at {path} is not valid YAML: {exc}"
            ) from exc

    if not isinstance(raw, dict):
        raise ValueError(
            f"topology.conf at {path} must be a YAML mapping, got "
            f"{type(raw).__name__}"
        )

    cluster_id = raw.get("cluster_id")
    if cluster_id is None:
        cluster_id = ""

    raw_peers = raw.get("peers") or []
    if not isinstance(raw_peers, list):
        raise ValueError(
            f"topology.conf peers must be a list, got " f"{type(raw_peers).__name__}"
        )
    peers_in = tuple(_coerce_peer(entry, idx) for idx, entry in enumerate(raw_peers))
    peers = _dedupe_peers(peers_in)

    raw_subs = raw.get("event_subscriptions")
    if raw_subs is None:
        event_subscriptions = DEFAULT_EVENT_SUBSCRIPTIONS
    else:
        if not isinstance(raw_subs, list):
            raise ValueError(
                f"topology.conf event_subscriptions must be a list, got "
                f"{type(raw_subs).__name__}"
            )
        event_subscriptions = tuple(raw_subs)

    cfg = TopologyConfig(
        cluster_id=cluster_id,
        peers=peers,
        event_subscriptions=event_subscriptions,
        enabled=True,
    )

    validate_topology_config(cfg)

    return cfg
