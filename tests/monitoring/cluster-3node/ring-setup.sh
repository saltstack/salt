#!/bin/bash
# Ring-mode sequencing shim for the cluster-3node testbed.
#
# Runs after all 3 masters + haproxy are up (compose ``depends_on``
# ordering), creates the ``resource_index`` ring + route + ring_set,
# polls until the ring is reported ``active``, then exits 0.
#
# The minion container uses ``depends_on:
# c3-ring-setup: service_completed_successfully`` so its first
# auto-register only fires AFTER this script exits cleanly.  Without
# this gate the minion's startup auto-register races the operator's
# manual ``cluster.ring_create`` and the first 3 chunks (30K SRNs at
# 10K per chunk) land via replicate-fallback -- polluting every master
# with SRNs the subsequent ring-dispatched chunks can't prune.
#
# Any runner failure exits non-zero, which fails the compose wait so
# the minion refuses to come up -- better a fast red than a quiet
# ring-contamination that corrupts measurements.

set -euo pipefail

MASTER_HOST="${SALT_MASTER:-salt-master-1}"
VOTERS=("salt-master-1" "salt-master-2" "salt-master-3")
RING_NAME="resource_index"
POLL_ATTEMPTS="${RING_READY_ATTEMPTS:-60}"
POLL_INTERVAL="${RING_READY_INTERVAL:-2}"

log() {
    echo "[ring-setup] $(date -u +%H:%M:%S) $*"
}

# Wait for a master to accept runner calls.  The MWorker / publish-
# daemon forks take a few seconds after container start.  We retry the
# cheap ``test.version`` runner until it responds; 60 * 2s = 2 min cap.
wait_for_master() {
    local attempt=0
    while (( attempt < POLL_ATTEMPTS )); do
        if salt-run --config-dir=/etc/salt --out=raw test.version >/dev/null 2>&1; then
            log "master accepting runner calls"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep "$POLL_INTERVAL"
    done
    log "master never accepted runner calls after $((POLL_ATTEMPTS * POLL_INTERVAL))s"
    return 1
}

create_ring() {
    local voter_list
    voter_list=$(printf "'%s'," "${VOTERS[@]}")
    voter_list="[${voter_list%,}]"
    log "cluster.ring_create ${RING_NAME} voters=${voter_list}"
    salt-run --config-dir=/etc/salt cluster.ring_create \
        "name=${RING_NAME}" \
        "voters=${voter_list}" || true

    log "cluster.route_set master=${MASTER_HOST}"
    salt-run --config-dir=/etc/salt cluster.route_set \
        "name=${RING_NAME}" \
        "master=${MASTER_HOST}" || true

    log "cluster.ring_set"
    salt-run --config-dir=/etc/salt cluster.ring_set \
        "name=${RING_NAME}" || true
}

# Poll ``cluster.rings`` until the ring is reported ``active``.
wait_ring_active() {
    local attempt=0
    while (( attempt < POLL_ATTEMPTS )); do
        if salt-run --config-dir=/etc/salt --out=yaml cluster.rings 2>/dev/null \
            | grep -E "^${RING_NAME}:" -A 10 \
            | grep -q "status: active"; then
            log "ring '${RING_NAME}' is active"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep "$POLL_INTERVAL"
    done
    log "ring never reached active state after $((POLL_ATTEMPTS * POLL_INTERVAL))s"
    log "final cluster.rings output:"
    salt-run --config-dir=/etc/salt cluster.rings || true
    return 1
}

runners_available() {
    # ``cluster.ring_create`` is part of the cache-replicate WIP
    # branch; vanilla 3008.x doesn't ship it.  Probe once and bail
    # cleanly when it's missing so the compose service exits 0 and
    # the downstream minions unblock.
    salt-run --config-dir=/etc/salt -d 2>/dev/null | grep -q '^cluster\.ring_create'
}

main() {
    log "waiting for master ${MASTER_HOST}..."
    wait_for_master

    if ! runners_available; then
        log "cluster.ring_create runner not available on this salt build;"
        log "skipping ring setup (compose service exits 0; minions proceed)."
        exit 0
    fi

    log "creating ring '${RING_NAME}'"
    create_ring

    log "waiting for ring '${RING_NAME}' to become active"
    wait_ring_active

    log "ring sequencing complete; exiting 0"
}

main "$@"
