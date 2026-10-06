"""
Multi-ring migration helpers shared between the runner subprocess
and the publish daemon.

Both surfaces need the same "drop unowned keys" logic:

* ``salt.runners.cluster.shed_unowned`` runs it from the operator's
  ``salt-run`` invocation.
* ``salt.channel.server.MasterPubServerChannel`` runs it on the
  daemon side when a peer's ``cluster/peer/shed-request`` event
  arrives (the fan-out path triggered by
  ``cluster.shed_unowned_all``).

Centralising the implementation here avoids the runner and the
daemon drifting apart on bank layout, cascade rules, or storage
replay quirks.  Both call sites pass their own ``__opts__`` dict in
explicitly so the helper has no loader dependency.
"""

import logging
import os
import time

log = logging.getLogger(__name__)


SHED_STATUS_FILENAME = "cluster-shed-status.json"


def perform_shed(
    opts,
    ring,
    banks=("jobs/loads", "jobs/minions", "jobs/endtimes", "jobs/nocache"),
    subbank_template="jobs/returns/{key}",
    driver=None,
    dry_run=False,
):
    """
    Drop the cache entries this master no longer owns under *ring*.

    Mirrors the operator-runner contract of
    ``salt.runners.cluster.shed_unowned`` but takes *opts* as an
    explicit argument so the publish daemon can call it without the
    loader's ``__opts__`` injection.

    Returns the same structured dict :func:`shed_unowned` returns
    (status / dropped / kept / subbanks_dropped / dry_run / ring).
    A "skipped" status carries a ``reason`` field; an "ok" status
    means the walk completed.
    """
    # Lazy imports — this module is loaded by the runner subprocess
    # which doesn't always have consensus deps available.
    import salt.cache  # pylint: disable=import-outside-toplevel
    from salt.cluster.consensus.raft.log import (  # pylint: disable=import-outside-toplevel
        RING_STATUS_ACTIVE,
        Log,
        LogEntryType,
        MembershipStateMachine,
        RingRegistryStateMachine,
    )
    from salt.cluster.consensus.storage import (  # pylint: disable=import-outside-toplevel
        SaltStorage,
    )
    from salt.cluster.ring import HashRing  # pylint: disable=import-outside-toplevel

    if not ring:
        raise ValueError("perform_shed requires a non-empty 'ring'")
    if not banks:
        raise ValueError("perform_shed requires at least one bank")

    node_id = opts.get("interface") or opts.get("id") or "unknown"

    # Cluster registry replay — same shape the runner uses.
    cluster_storage = SaltStorage(node_id, opts, ring_id="cluster")
    registry_sm = RingRegistryStateMachine()
    Log(
        storage=cluster_storage,
        state_machines={"ring_registry_sm": registry_sm},
    )
    for entry in cluster_storage.load_log():
        if entry.type == LogEntryType.RING_REGISTRY:
            registry_sm.apply(entry.cmd, index=entry.index)
    registry_entry = registry_sm.get(ring)
    if not registry_entry or registry_entry.get("status") != RING_STATUS_ACTIVE:
        return {
            "status": "skipped",
            "reason": f"ring {ring!r} is not active in the registry",
            "ring": ring,
            "dropped": 0,
            "kept": 0,
            "subbanks_dropped": 0,
            "dry_run": dry_run,
        }
    if node_id not in registry_entry.get("founding_voters", []):
        return {
            "status": "skipped",
            "reason": (
                f"this master ({node_id}) is not a founding voter of ring {ring!r}"
            ),
            "ring": ring,
            "dropped": 0,
            "kept": 0,
            "subbanks_dropped": 0,
            "dry_run": dry_run,
        }

    # Per-ring membership replay.
    ring_storage = SaltStorage(node_id, opts, ring_id=ring)
    ring_membership_sm = MembershipStateMachine()
    Log(
        storage=ring_storage,
        state_machines={"membership_sm": ring_membership_sm},
    )
    for entry in ring_storage.load_log():
        if entry.type == LogEntryType.CONFIG:
            ring_membership_sm.apply(entry.cmd, index=entry.index)
    voters = ring_membership_sm.current_voters() or registry_entry.get(
        "founding_voters", []
    )
    if not voters:
        return {
            "status": "skipped",
            "reason": f"ring {ring!r} has no committed voters yet",
            "ring": ring,
            "dropped": 0,
            "kept": 0,
            "subbanks_dropped": 0,
            "dry_run": dry_run,
        }

    hash_ring = HashRing()
    hash_ring.rebuild(voters)

    if driver is None:
        driver = opts.get("cache") or opts.get("keys.cache_driver")
    cache = salt.cache.Cache(opts, driver=driver)

    primary_bank = banks[0]
    unowned_primary_keys = []
    dropped, kept = 0, 0
    for idx, bank in enumerate(banks):
        try:
            keys = list(cache.list(bank))
        except Exception:  # pylint: disable=broad-except
            continue
        for key in keys:
            if hash_ring.owns(key, node_id):
                kept += 1
                continue
            if idx == 0:
                unowned_primary_keys.append(key)
            if not dry_run:
                try:
                    cache.flush(bank, key)
                except Exception:  # pylint: disable=broad-except
                    continue
            dropped += 1

    subbanks_dropped = 0
    if subbank_template and unowned_primary_keys:
        for key in unowned_primary_keys:
            subbank = subbank_template.format(key=key)
            if not dry_run:
                try:
                    cache.flush(subbank)
                except Exception:  # pylint: disable=broad-except
                    continue
            subbanks_dropped += 1

    log.info(
        "perform_shed: ring=%s dropped=%d kept=%d subbanks_dropped=%d "
        "dry_run=%s (primary_bank=%s)",
        ring,
        dropped,
        kept,
        subbanks_dropped,
        dry_run,
        primary_bank,
    )
    return {
        "status": "ok",
        "ring": ring,
        "dropped": dropped,
        "kept": kept,
        "subbanks_dropped": subbanks_dropped,
        "dry_run": dry_run,
    }


def write_shed_status(opts, result, source):
    """
    Persist a shed result for ``cluster.shed_status`` to surface.

    *source* explains who triggered the shed:

    * ``"runner"`` — this master ran ``cluster.shed_unowned``
      directly.
    * ``"runner_originator"`` — this master is the originator of a
      ``cluster.shed_unowned_all`` fan-out and ran its local pass.
    * ``"peer_request"`` — a peer's ``shed-request`` event reached
      this master.

    The sentinel is rewritten on every shed run.  Operators
    inspecting it always see the most-recent result.

    Writes are atomic — tmp file + rename — so a concurrent reader
    or a second writer mid-write never sees a partial JSON document.
    The bug this fixes: ``shed_unowned_all`` fan-out occasionally
    arrives twice at the same peer (see the ``self.pushers``
    duplication note in MULTI_RING_DESIGN.md), and the second write
    used to overwrite mid-stream and produce invalid JSON.
    """
    import json  # pylint: disable=import-outside-toplevel

    import salt.utils.atomicfile  # pylint: disable=import-outside-toplevel

    cachedir = opts.get("cachedir")
    if not cachedir:
        return
    path = os.path.join(cachedir, SHED_STATUS_FILENAME)
    body = dict(result)
    body["source"] = source
    body["updated_at"] = time.time()
    try:
        with salt.utils.atomicfile.atomic_open(path, "w") as fp:
            json.dump(body, fp)
    except OSError as exc:
        log.warning("shed-status: failed to write sentinel %s: %s", path, exc)
