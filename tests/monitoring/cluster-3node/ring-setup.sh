#!/bin/sh
# Ring-mode sequencing shim for the cluster-3node testbed.
#
# Runs after all 3 masters + haproxy are up (compose ``depends_on``
# ordering), creates the ``resource_index`` ring + route + ring_set
# INSIDE master-1 via ``docker exec``, polls until the ring is reported
# ``active``, then exits 0.
#
# Rationale for ``docker exec`` rather than a local ``salt-run``:
# the ring runners publish events through the live master's IPC
# socket (``/var/run/salt/master/master_event_pull.ipc``) and write
# per-jid trackers under the master's cache dir.  A sidecar that
# only mounts ``master-1.conf`` runs the runners in its own local
# state, so ``cluster.ring_create`` "succeeds" in the sidecar but
# never reaches the running master-1 process.  Executing inside
# master-1 is the only path that lets the runner publish to its
# own publisher daemon.
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

set -eu

MASTER_CONTAINER="${SALT_MASTER_CONTAINER:-c3-salt-master-1}"
MASTER_HOST="${SALT_MASTER:-salt-master-1}"
RING_NAME="resource_index"
POLL_ATTEMPTS="${RING_READY_ATTEMPTS:-60}"
POLL_INTERVAL="${RING_READY_INTERVAL:-2}"

log() {
    echo "[ring-setup] $(date -u +%H:%M:%S) $*"
}

m_exec() {
    docker exec "$MASTER_CONTAINER" "$@"
}

# Wait for master-1 to accept runner calls AND have RaftService wired up.
# The MWorker / publish-daemon forks take a few seconds after container
# start; RaftService start waits for the leader-election handshake on
# top of that.  A ``cluster.ring_create`` event that arrives before
# RaftService is wired is dropped on the floor with a WARNING in the
# master log (``Multi-ring runner event ... arrived but RaftService
# is not wired up on this master; dropping``), which is silent at the
# shim's abstraction layer.  We gate on ``cluster.members`` returning
# ``membership_version != -1`` (a committed CONFIG entry means the
# Raft log is accepting writes).
wait_for_master() {
    attempt=0
    while [ "$attempt" -lt "$POLL_ATTEMPTS" ]; do
        if m_exec salt-run --out=raw test.version >/dev/null 2>&1; then
            log "master ${MASTER_CONTAINER} accepting runner calls"
            break
        fi
        attempt=$((attempt + 1))
        sleep "$POLL_INTERVAL"
    done
    if [ "$attempt" -ge "$POLL_ATTEMPTS" ]; then
        log "master never accepted runner calls after $((POLL_ATTEMPTS * POLL_INTERVAL))s"
        return 1
    fi

    log "waiting for RaftService on ${MASTER_CONTAINER} (cluster.members membership_version != -1)"
    attempt=0
    while [ "$attempt" -lt "$POLL_ATTEMPTS" ]; do
        mv_line=$(m_exec salt-run --out=yaml cluster.members 2>/dev/null \
            | grep -E '^membership_version:' || true)
        case "$mv_line" in
            *': -1'|'')
                ;;
            *)
                log "RaftService wired up (${mv_line})"
                return 0
                ;;
        esac
        attempt=$((attempt + 1))
        sleep "$POLL_INTERVAL"
    done
    log "RaftService never came up after $((POLL_ATTEMPTS * POLL_INTERVAL))s"
    log "final cluster.members output:"
    m_exec salt-run cluster.members || true
    return 1
}

create_ring() {
    voter_list="['salt-master-1','salt-master-2','salt-master-3']"
    log "cluster.ring_create name=${RING_NAME} voters=${voter_list}"
    m_exec salt-run cluster.ring_create \
        "name=${RING_NAME}" \
        "voters=${voter_list}" || true

    log "cluster.route_set data_type=${RING_NAME} ring=${RING_NAME}"
    m_exec salt-run cluster.route_set \
        "data_type=${RING_NAME}" \
        "ring=${RING_NAME}" || true

    log "cluster.ring_set name=${RING_NAME} members=voters"
    m_exec salt-run cluster.ring_set \
        "name=${RING_NAME}" \
        "members=voters" || true
}

# Poll ``cluster.rings`` until the ring appears in ``active_rings``.
# ``active_rings`` is the runner's own sorted list of ``status=active``
# ring_ids -- a single check against that is simpler and less brittle
# than parsing the nested ``rings.<name>.status`` layout.
wait_ring_active() {
    attempt=0
    while [ "$attempt" -lt "$POLL_ATTEMPTS" ]; do
        if m_exec salt-run --out=yaml cluster.rings 2>/dev/null \
            | grep -E "^active_rings:" -A 5 \
            | grep -qE "^[[:space:]]*-[[:space:]]+${RING_NAME}[[:space:]]*\$"; then
            log "ring '${RING_NAME}' is active"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep "$POLL_INTERVAL"
    done
    log "ring never reached active state after $((POLL_ATTEMPTS * POLL_INTERVAL))s"
    log "final cluster.rings output:"
    m_exec salt-run cluster.rings || true
    return 1
}

main() {
    log "waiting for master ${MASTER_CONTAINER}..."
    wait_for_master

    log "creating ring '${RING_NAME}'"
    create_ring

    log "waiting for ring '${RING_NAME}' to become active"
    wait_ring_active

    log "ring sequencing complete; exiting 0"
}

main "$@"
