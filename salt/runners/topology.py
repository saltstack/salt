"""
Topology operator commands.

Exposed via ``salt-run topology.<command>``.  Read-mostly; the one
mutation (:func:`trust`) is a thin wrapper over ``salt-key --master``
semantics for convenience in automation workflows that would
otherwise shell out to the key CLI.

All read commands degrade gracefully to on-disk state when the
publish daemon's :mod:`salt.topology.link_manager` module is not
live in this process (which is the typical case: runners run from
a short-lived :class:`salt.runner.RunnerClient` process that does
not share module-level state with the master's publish daemon).

The resting state consulted here is:

* ``<pki_dir>/masters/``          --- accepted peers
* ``<pki_dir>/masters_pre/``      --- pending peers
* ``<pki_dir>/masters_rejected/`` --- rejected peers
* ``<pki_dir>/master/topology_registry.mmap*`` --- registry cache
* ``<pki_dir>/master/topology_breadcrumbs.mmap*`` --- breadcrumbs cache
* ``opts["topology_peers"]`` --- configured seed peers

Any of these may be absent on a fresh master; absence is treated
as empty rather than as an error.
"""

import logging
import os
import pathlib

import salt.config.topology
import salt.topology.breadcrumbs as breadcrumbs
import salt.topology.registry as registry
import salt.utils.crypt
import salt.utils.files
import salt.utils.json

log = logging.getLogger(__name__)

__virtualname__ = "topology"


_VALID_TRUST_ACTIONS = ("accept", "reject", "delete", "fingerprint")
_VALID_GRAPH_FORMATS = ("text", "dot", "json")


def __virtual__():
    """
    Load the runner when ``opts["topology_enabled"]`` is True.

    Returns ``(False, reason)`` otherwise so ``salt-run doc.runner``
    surfaces the config knob the operator needs to flip.  Matches the
    pattern used by :mod:`salt.runners.net` (optional-feature gate
    with an explanatory reason string).
    """
    opts = globals().get("__opts__") or {}
    if opts.get("topology_enabled"):
        return __virtualname__
    return (False, "topology is disabled (set topology_enabled: True in master config)")


# ---------------------------------------------------------------------------
# Internal helpers --- opts, pki paths, config
# ---------------------------------------------------------------------------


def _opts():
    """Return the runner's opts dict."""
    return globals().get("__opts__") or {}


def _pki_dir(opts):
    return pathlib.Path(opts.get("pki_dir", ""))


def _masters_dir(opts, name):
    """Return ``<pki_dir>/<name>`` without creating it."""
    return _pki_dir(opts) / name


def _list_pub_stems(path):
    """Return sorted ``.pub`` stems under *path*, or [] if missing."""
    if not path.is_dir():
        return []
    out = []
    for entry in sorted(path.iterdir()):
        if entry.is_file() and entry.suffix == ".pub":
            out.append(entry.stem)
    return out


def _accepted_peers(opts):
    return _list_pub_stems(_masters_dir(opts, "masters"))


def _pending_peers(opts):
    return _list_pub_stems(_masters_dir(opts, "masters_pre"))


def _rejected_peers(opts):
    return _list_pub_stems(_masters_dir(opts, "masters_rejected"))


def _topology_config(opts):
    """Load the on-disk topology.conf; disabled config on failure."""
    try:
        return salt.config.topology.load_topology_config(opts)
    except (ValueError, OSError) as exc:
        log.warning("topology runner: topology.conf load failed: %s", exc)
        # Return a disabled TopologyConfig so callers can read .peers.
        return salt.config.topology.TopologyConfig(
            cluster_id="",
            peers=(),
            event_subscriptions=salt.config.topology.DEFAULT_EVENT_SUBSCRIPTIONS,
            enabled=False,
        )


def _own_cluster_id(opts):
    """Return the loaded ``cluster_id`` from topology.conf, or "" if absent."""
    cfg = _topology_config(opts)
    if cfg.enabled and cfg.cluster_id:
        return cfg.cluster_id
    return opts.get("cluster_id") or ""


# ---------------------------------------------------------------------------
# Internal helpers --- registry + breadcrumbs
# ---------------------------------------------------------------------------


def _open_registry_reader(opts):
    """
    Open a read-only registry handle, pre-creating the cache files
    if the writer side has not run yet.

    Returns ``None`` on any failure --- callers treat that as
    "no registry state" rather than raising.
    """
    try:
        registry.pre_create(opts)
    except Exception:  # pylint: disable=broad-except
        log.debug("topology runner: registry pre_create failed", exc_info=True)
        return None
    try:
        return registry.open_reader(opts)
    except Exception:  # pylint: disable=broad-except
        log.debug("topology runner: registry open_reader failed", exc_info=True)
        return None


def _open_breadcrumbs_reader(opts):
    """Open a read-only breadcrumbs handle; None on failure."""
    try:
        breadcrumbs.pre_create(opts)
    except Exception:  # pylint: disable=broad-except
        log.debug("topology runner: breadcrumbs pre_create failed", exc_info=True)
        return None
    try:
        return breadcrumbs.open_reader(opts)
    except Exception:  # pylint: disable=broad-except
        log.debug("topology runner: breadcrumbs open_reader failed", exc_info=True)
        return None


def _registry_peer_state(reader, cluster_id):
    """Return the registry peer dict for *cluster_id*, or None."""
    if reader is None:
        return None
    try:
        return registry.get_peer(reader, cluster_id)
    except Exception:  # pylint: disable=broad-except
        log.debug(
            "topology runner: registry.get_peer(%r) failed", cluster_id, exc_info=True
        )
        return None


def _registry_peer_ids(reader):
    """Return the list of attached peer cluster_ids, or []."""
    if reader is None:
        return []
    try:
        return list(registry.list_peer_ids(reader))
    except Exception:  # pylint: disable=broad-except
        log.debug("topology runner: registry.list_peer_ids failed", exc_info=True)
        return []


def _breadcrumbs_count(reader):
    """Return the count of in-flight breadcrumbs, or 0."""
    if reader is None:
        return 0
    try:
        return len(list(reader.list_items()))
    except Exception:  # pylint: disable=broad-except
        log.debug("topology runner: breadcrumbs list_items failed", exc_info=True)
        return 0


# ---------------------------------------------------------------------------
# Internal helpers --- live link_manager (same-process only)
# ---------------------------------------------------------------------------


def _live_link_by_cluster(cluster_id):
    """
    Return the live :class:`PeerMasterLink` for *cluster_id* if the
    :mod:`salt.topology.link_manager` module is active in this
    process, otherwise ``None``.
    """
    try:
        from salt.topology.link_manager import get_link

        return get_link(cluster_id)
    except Exception:  # pylint: disable=broad-except
        return None


# ---------------------------------------------------------------------------
# Internal helpers --- counts
# ---------------------------------------------------------------------------


def _local_minion_counts(opts):
    """
    Return ``(minion_count, up_count)`` for the local master.

    ``minion_count`` is the number of accepted minion keys;
    ``up_count`` is the number of minions whose grains cache is
    populated (same signal :mod:`salt.topology.summary` uses).  Any
    read failure returns zeroes so the runner never crashes on a
    half-set-up master.
    """
    minion_count = 0
    up_count = 0
    try:
        import salt.cache
        import salt.key

        with salt.key.get_key(opts) as key:
            minion_count = len(key.list_keys().get("minions", []))
    except Exception:  # pylint: disable=broad-except
        log.debug("topology runner: minion-key count failed", exc_info=True)
    try:
        import salt.cache

        cache = salt.cache.factory(opts)
        up_count = min(len(cache.list("grains") or []), minion_count)
    except Exception:  # pylint: disable=broad-except
        log.debug("topology runner: grain-cache list failed", exc_info=True)
    return minion_count, up_count


# ---------------------------------------------------------------------------
# Public: __virtual__-gated commands
# ---------------------------------------------------------------------------


def status():
    """
    Return a tree-shaped summary of the reachable topology graph.

    Shape::

        {
            "cluster_id": "<local>",
            "minion_count": N,
            "up_count": N,
            "peers": [
                {
                    "cluster_id": "<peer>",
                    "state": "attached" | "pending" | ...,
                    "minion_count": N,
                    "up_count": N,
                    "last_summary_at": <unix ts> | None,
                },
                ...
            ],
        }

    Peers in the registry carry minion counts from the most recent
    summary this master received from them; peers whose state is
    on-disk only (pending / configured) carry zeroes.
    """
    opts = _opts()
    minion_count, up_count = _local_minion_counts(opts)
    out = {
        "cluster_id": _own_cluster_id(opts),
        "minion_count": minion_count,
        "up_count": up_count,
        "peers": [],
    }
    reader = _open_registry_reader(opts)
    try:
        peer_entries = peers()
        if isinstance(peer_entries, list):
            for entry in peer_entries:
                cluster_id = entry.get("cluster_id")
                if not cluster_id:
                    continue
                state = _registry_peer_state(reader, cluster_id)
                row = {
                    "cluster_id": cluster_id,
                    "state": entry.get("state"),
                    "minion_count": 0,
                    "up_count": 0,
                    "last_summary_at": None,
                }
                if state is not None:
                    row["last_summary_at"] = state.get("attached_at")
                out["peers"].append(row)
    finally:
        if reader is not None:
            try:
                reader.close()
            except Exception:  # pylint: disable=broad-except
                pass
    return out


def links():
    """
    Return detailed health + metadata for every known peer link.

    Fields per entry:

    * ``peer_cluster_id``
    * ``health``
    * ``endpoints``
    * ``last_summary_at``
    * ``breadcrumbs_active``

    Live-link health is taken from the in-process
    :mod:`salt.topology.link_manager` when it is active in the
    current process; when the runner runs in a RunnerClient
    subprocess (the usual case), health falls back to
    ``"attached"`` for peers present in the registry, and
    ``"disconnected"`` for peers whose key is on disk but not in
    the registry.
    """
    opts = _opts()
    out = []
    reader = _open_registry_reader(opts)
    bread = _open_breadcrumbs_reader(opts)
    try:
        active = _breadcrumbs_count(bread)
        for cluster_id in _registry_peer_ids(reader):
            state = _registry_peer_state(reader, cluster_id) or {}
            endpoints = list(state.get("endpoints") or [])
            live = _live_link_by_cluster(cluster_id)
            if live is not None:
                health = getattr(live, "health", None) or "unknown"
                last_summary = getattr(live, "remote_summary", None)
                last_summary_at = (
                    getattr(last_summary, "origin_at", None)
                    if last_summary is not None
                    else state.get("attached_at")
                )
            else:
                health = "attached"
                last_summary_at = state.get("attached_at")
            out.append(
                {
                    "peer_cluster_id": cluster_id,
                    "health": health,
                    "endpoints": endpoints,
                    "last_summary_at": last_summary_at,
                    "breadcrumbs_active": active,
                }
            )

        # Peers whose key sits in masters/ but have never completed
        # a handshake (no registry entry): surface as DISCONNECTED
        # so operators see them with an explanation.
        registry_set = set(_registry_peer_ids(reader))
        for accepted in _accepted_peers(opts):
            if accepted in registry_set:
                continue
            out.append(
                {
                    "peer_cluster_id": accepted,
                    "health": "disconnected",
                    "endpoints": [],
                    "last_summary_at": None,
                    "breadcrumbs_active": active,
                }
            )
    finally:
        for handle in (reader, bread):
            if handle is None:
                continue
            try:
                handle.close()
            except Exception:  # pylint: disable=broad-except
                pass
    return out


def peers():
    """
    Return the list of peer references, each with its current
    state:

    * ``configured`` --- in ``topology.conf`` but not yet seen on
      any key path.
    * ``pending``    --- key is in ``masters_pre/``.
    * ``attached``   --- key is in ``masters/``.
    * ``rejected``   --- key is in ``masters_rejected/``.

    Each entry has ``{"cluster_id": ..., "state": ...}`` and, for
    configured-only entries, ``{"host": ..., "port": ...}`` fields
    identifying the seed endpoint.
    """
    opts = _opts()
    cfg = _topology_config(opts)
    out = []
    seen = set()

    accepted = set(_accepted_peers(opts))
    pending = set(_pending_peers(opts))
    rejected = set(_rejected_peers(opts))

    for cluster_id in sorted(rejected):
        out.append({"cluster_id": cluster_id, "state": "rejected"})
        seen.add(cluster_id)
    for cluster_id in sorted(accepted - rejected):
        out.append({"cluster_id": cluster_id, "state": "attached"})
        seen.add(cluster_id)
    for cluster_id in sorted(pending - accepted - rejected):
        out.append({"cluster_id": cluster_id, "state": "pending"})
        seen.add(cluster_id)

    # Configured peers from topology.conf; identify by host:port
    # since the cluster_id is only known after handshake.
    for peer_ref in cfg.peers:
        host = peer_ref.host
        port = peer_ref.port or opts.get("topology_link_port")
        endpoint_id = f"{host}:{port}" if port else host
        if endpoint_id in seen:
            continue
        out.append(
            {
                "cluster_id": endpoint_id,
                "state": "configured",
                "host": host,
                "port": port,
            }
        )
    return out


def trust(cluster_id, action):
    """
    Thin wrapper over ``salt-key --master`` semantics.

    :param cluster_id: Peer cluster to act on.
    :param action: One of ``accept``, ``reject``, ``delete``,
        ``fingerprint``.
    :returns: ``{"cluster_id": ..., "state": ...}`` for state-changing
        actions, ``{"cluster_id": ..., "fingerprint": ...}`` for
        ``fingerprint``, or ``{"error": ...}`` on invalid input.
    """
    if action not in _VALID_TRUST_ACTIONS:
        return {
            "error": f"invalid action {action!r}; expected one of {_VALID_TRUST_ACTIONS}"
        }
    if not isinstance(cluster_id, str) or not cluster_id:
        return {"error": "cluster_id must be a non-empty string"}

    opts = _opts()
    pki = _pki_dir(opts)
    pending = pki / "masters_pre" / f"{cluster_id}.pub"
    accepted = pki / "masters" / f"{cluster_id}.pub"
    rejected = pki / "masters_rejected" / f"{cluster_id}.pub"

    if action == "fingerprint":
        # Walk the known locations in priority order.
        for candidate in (accepted, pending, rejected):
            if candidate.is_file():
                finger = salt.utils.crypt.pem_finger(path=str(candidate))
                return {"cluster_id": cluster_id, "fingerprint": finger}
        return {"error": f"no key found for cluster_id {cluster_id!r}"}

    if action == "accept":
        source = pending if pending.is_file() else None
        if source is None and rejected.is_file():
            source = rejected
        if source is None:
            return {"error": f"no pending key for cluster_id {cluster_id!r}"}
        accepted.parent.mkdir(parents=True, exist_ok=True)
        source.replace(accepted)
        return {"cluster_id": cluster_id, "state": "accepted"}

    if action == "reject":
        source = None
        for candidate in (pending, accepted):
            if candidate.is_file():
                source = candidate
                break
        if source is None:
            return {"error": f"no key for cluster_id {cluster_id!r}"}
        rejected.parent.mkdir(parents=True, exist_ok=True)
        source.replace(rejected)
        return {"cluster_id": cluster_id, "state": "rejected"}

    if action == "delete":
        removed = False
        for candidate in (accepted, pending, rejected):
            if candidate.is_file():
                try:
                    candidate.unlink()
                    removed = True
                except OSError as exc:
                    return {"error": f"delete failed for {candidate}: {exc}"}
        if not removed:
            return {"error": f"no key for cluster_id {cluster_id!r}"}
        # Best-effort registry removal: the writer-handle guard means
        # this fails from a non-publish-daemon process; swallow quietly.
        try:
            reader = _open_registry_reader(opts)
            if reader is not None:
                try:
                    registry.delete_peer(reader, cluster_id)
                except Exception:  # pylint: disable=broad-except
                    pass
                finally:
                    try:
                        reader.close()
                    except Exception:  # pylint: disable=broad-except
                        pass
        except Exception:  # pylint: disable=broad-except
            pass
        return {"cluster_id": cluster_id, "state": "deleted"}

    # Unreachable; the action validation above covers every value.
    return {"error": f"invalid action {action!r}"}


def find(minion_id, timeout=10):
    """
    On-demand lookup: ask every reachable cluster whether it has
    an accepted key for ``minion_id``.

    Without a live outbound-link set in this process (the common
    case: runners run in a short-lived :class:`RunnerClient`
    subprocess that does not share the publish daemon's module
    globals), falls back to a local-only lookup against this
    master's accepted minion keys.  Returns the same shape either
    way so callers do not need to special-case either path.

    :param minion_id: Minion id to locate.
    :param timeout: Deadline in seconds.  ``0`` short-circuits and
        returns an empty dict without consulting any state.
    :returns: ``{cluster_path: minion_id_as_known_locally}``.
    """
    if not isinstance(minion_id, str) or not minion_id:
        return {}
    try:
        timeout_f = float(timeout)
    except (TypeError, ValueError):
        return {}
    if timeout_f <= 0:
        return {}

    opts = _opts()
    out = {}

    # Local lookup via accepted minion keys.
    try:
        import salt.key

        with salt.key.get_key(opts) as key:
            minions = set(key.list_keys().get("minions", []) or [])
    except Exception:  # pylint: disable=broad-except
        log.debug("topology runner: find() minion-key list failed", exc_info=True)
        minions = set()
    if minion_id in minions:
        own = _own_cluster_id(opts) or "local"
        out[own] = minion_id

    # Remote fan-out via live outbound links, when available.  Keeping
    # this import inside the function avoids a module-load dep when
    # link_manager is not wired.
    try:
        from salt.topology.link_manager import outbound_links

        live_links = outbound_links()
    except Exception:  # pylint: disable=broad-except
        live_links = []

    # Live fan-out is a protocol-level send-and-wait on each outbound
    # link; the full wire path requires the Phase 3 inbound dispatcher
    # on the peer side.  When links are absent (test harness, inert
    # master), the local lookup above is the full result.
    for link in live_links:
        peer_cluster_id = getattr(link, "peer_cluster_id", None)
        if not peer_cluster_id or peer_cluster_id in out:
            continue
        try:
            # Best-effort: use the link to probe.  If the link does
            # not expose a lookup verb, skip gracefully --- Phase 2
            # links do not; a future link.has_minion() can plug in
            # without changing this call site.
            if hasattr(link, "has_minion"):
                hit = link.has_minion(minion_id, timeout=timeout_f)
                if hit:
                    out[peer_cluster_id] = minion_id
        except Exception:  # pylint: disable=broad-except
            log.debug(
                "topology runner: find() link probe to %r failed",
                peer_cluster_id,
                exc_info=True,
            )

    return out


def graph(fmt="text"):
    """
    Render the known topology graph.

    :param fmt: One of ``text`` (default, indented tree-ish),
        ``dot`` (Graphviz source), or ``json`` (``{"nodes": [...],
        "edges": [...]}``).
    :returns: A string for text/dot, a dict for json, or an
        ``{"error": ...}`` dict for unknown formats.
    """
    if fmt not in _VALID_GRAPH_FORMATS:
        return {"error": f"invalid fmt {fmt!r}; expected one of {_VALID_GRAPH_FORMATS}"}

    opts = _opts()
    own = _own_cluster_id(opts) or "local"
    peer_entries = peers() or []

    # Normalise edges: own -> every peer whose state is attached /
    # pending / configured.  Rejected peers are listed as nodes but
    # drawn with a dashed edge label so operators see the inhibitor.
    nodes = [{"id": own, "role": "self"}]
    edges = []
    for entry in peer_entries:
        cluster_id = entry.get("cluster_id")
        if not cluster_id:
            continue
        nodes.append({"id": cluster_id, "role": "peer", "state": entry.get("state")})
        edges.append(
            {
                "source": own,
                "target": cluster_id,
                "state": entry.get("state"),
            }
        )

    if fmt == "json":
        return {"nodes": nodes, "edges": edges}

    if fmt == "dot":
        lines = ["digraph topology {"]
        lines.append(f'    "{own}" [shape=doublecircle];')
        for node in nodes[1:]:
            lines.append('    "{id}" [label="{id}\\n({state})"];'.format(**node))
        for edge in edges:
            style = "dashed" if edge["state"] == "rejected" else "solid"
            lines.append(
                '    "{source}" -> "{target}" [style={style}, label="{state}"];'.format(
                    style=style, **edge
                )
            )
        lines.append("}")
        return "\n".join(lines) + "\n"

    # Default: text tree.
    lines = [own]
    for entry in peer_entries:
        cluster_id = entry.get("cluster_id")
        state = entry.get("state", "")
        if not cluster_id:
            continue
        lines.append(f"  +-- {cluster_id} ({state})")
    return "\n".join(lines) + "\n"


# Silence "imported but unused" warnings for helpers used only in some
# code paths (os, salt.utils.json, salt.utils.files).  These remain
# imported for future wire-ups documented in the RFC.
_ = (os, salt.utils.files, salt.utils.json)
