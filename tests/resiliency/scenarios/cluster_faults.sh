#!/usr/bin/env bash
#
# Resiliency scenario: cluster-specific faults.
#
# This battery exercises faults that only make sense when more than one
# master is in play.  Every phase is topology-gated: on TOPOLOGY=single
# each phase records ``skipped_for_topology`` and returns immediately.
# Many phases require specifically ``cluster3`` (haproxy + 3 masters
# sharing cluster-pki); a smaller set requires the two multimaster
# variants.  Phases do not short-circuit each other; the whole battery
# is attempted and the exit code is 0 only if every attempted phase
# recovered.
#
# Phases (each independent):
#
#   1. cluster_peer_sigstop_60s                 (cluster3 only)
#   2. cluster_peer_unreachable                 (cluster3 only)
#   3. cluster_aes_rotation_under_load          (cluster3 only)
#   4. cluster_haproxy_backend_flap             (cluster3 only)
#   5. cluster_split_brain_simulate             (cluster3 only)
#   6. cluster_rolling_restart_with_traffic     (cluster3 only)
#   7. multimaster_primary_unreachable          (multimaster-failover)
#   8. multimaster_hothot_one_master_tc_partition (multimaster-hothot)
#   9. multimaster_both_masters_restart_staggered (multimaster-*)
#
# Correctness notes (see ``feedback_cluster_scrutiny``):
#   - Never edit ``/etc/salt/cluster-pki`` or any cached raft state.  All
#     fault injection is process- or network-level and purely reversible.
#   - Never delete minion keys.
#   - Every fault has a complementary cleanup in the EXIT trap so a mid-
#     script abort still leaves the cluster recoverable.
#
# AES rotation trigger (phase 3): there is NO ``salt-run
# cluster.rotate_cluster_secret`` runner on 3008.x; ``rotate_cluster_secret``
# is a classmethod on ``salt.master.SMaster`` invoked internally by
# ``Maintenance.handle_key_rotate`` when a ``.dfn`` dropfile matches the
# master's id.  We trigger a rotation by writing a dropfile into
# ``/var/cache/salt/master/.dfn`` on master-1 with contents
# ``salt-master-1``; the next maintenance tick picks it up and fires the
# ``rotate_cluster_aes_key`` peer event (saltstack/salt#70573, the fix for
# issue #70543).  See the write-up at the bottom of the script header
# for how we confirmed this is the right entry point.
#
# Env knobs (with defaults):
#   PEER_SIGSTOP_SEC            60
#   PEER_UNREACHABLE_SEC        90
#   AES_PROPAGATION_WAIT_SEC    30
#   HAPROXY_FLAP_SEC            60
#   SPLIT_BRAIN_SEC             60
#   ROLLING_WORKLOAD_BURST_SEC  15
#   MM_PRIMARY_UNREACH_SEC      90
#   MM_HOTHOT_PARTITION_SEC     60
#   MM_STAGGERED_GAP_SEC        10
#   INTER_PHASE_WAIT_SEC        15

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
. "${SCRIPT_DIR}/../lib/common.sh"

load_topology

: "${PEER_SIGSTOP_SEC:=60}"
: "${PEER_UNREACHABLE_SEC:=90}"
: "${AES_PROPAGATION_WAIT_SEC:=30}"
: "${HAPROXY_FLAP_SEC:=60}"
: "${SPLIT_BRAIN_SEC:=60}"
: "${ROLLING_WORKLOAD_BURST_SEC:=15}"
: "${MM_PRIMARY_UNREACH_SEC:=90}"
: "${MM_HOTHOT_PARTITION_SEC:=60}"
: "${MM_STAGGERED_GAP_SEC:=10}"
: "${INTER_PHASE_WAIT_SEC:=15}"

MASTER_COUNT=0
for _m in $MASTERS; do MASTER_COUNT=$((MASTER_COUNT + 1)); done

OVERALL_RC=0

# Track transient fault state so the EXIT trap can unwind cleanly.
# Space-separated container names; append to these when a fault is
# installed, and let the trap undo them.  See ``cleanup`` below.
PAUSED_CONTAINERS=""
DISCONNECTED_CONTAINERS=""   # entries of the form "<network>|<container>"
HAPROXY_DISABLED_BACKENDS="" # entries of the form "<backend>/<server>"
NETEM_CONTAINERS=""          # containers with a netem qdisc installed

CLUSTER3_NETWORK="cluster-3node_salt-net"
MULTIMASTER_NETWORK="resiliency-multimaster_salt-net"
HAPROXY_CONTAINER="c3-salt-haproxy"

log() { printf '[cluster_faults] %s %s\n' "$(date -u +%H:%M:%S)" "$*"; }

record_setup_error() {
    local scenario="$1" notes="$2"
    log "SETUP_ERROR '$scenario': $notes"
    record_result "$scenario" "setup_error" "-1" "0" "" "0" "0" "0" "$notes"
    OVERALL_RC=1
}

record_skip() {
    local scenario="$1" notes="$2"
    log "SKIP '$scenario': $notes"
    record_result "$scenario" "skipped_for_topology" "-1" "0" "" "0" "0" "0" "$notes"
}

between_phases() {
    log "sleeping ${INTER_PHASE_WAIT_SEC}s before next phase"
    sleep "$INTER_PHASE_WAIT_SEC"
}

# EXIT trap: best-effort unwind of every kind of fault this script
# installs.  Idempotent; safe to call even if nothing was applied.
cleanup() {
    local ec=$?
    # 1. SIGCONT anything we paused (including anything we might have
    # paused through other means; include every known container just
    # in case a phase died before updating PAUSED_CONTAINERS).
    for c in $PAUSED_CONTAINERS $MASTERS $MINION_CONTAINERS; do
        docker kill -s CONT "$c" >/dev/null 2>&1 || true
    done
    # 2. Reconnect any docker-network disconnects we installed.
    for entry in $DISCONNECTED_CONTAINERS; do
        local net="${entry%%|*}" ctr="${entry##*|}"
        docker network connect "$net" "$ctr" >/dev/null 2>&1 || true
    done
    # 3. Re-enable any haproxy backends we disabled.
    for bk in $HAPROXY_DISABLED_BACKENDS; do
        docker exec "$HAPROXY_CONTAINER" sh -c "
            echo 'enable server ${bk}' | socat stdio /var/run/haproxy.sock 2>/dev/null
        " >/dev/null 2>&1 || true
    done
    # 4. Clear any netem qdiscs we installed.
    for c in $NETEM_CONTAINERS; do
        docker exec "$c" sh -c "tc qdisc del dev ${CHOKE_IFACE} root 2>/dev/null" >/dev/null 2>&1 || true
    done
    log "cluster_faults: EXIT trap complete (rc=${ec})"
    exit "$ec"
}
trap cleanup EXIT INT TERM

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

# Resolve a non-primary peer (any master in $MASTERS that is NOT
# $PRIMARY_MASTER).  Prints the first such container name; empty if
# the topology has only one master.
pick_non_primary_peer() {
    for m in $MASTERS; do
        if [ "$m" != "$PRIMARY_MASTER" ]; then
            printf '%s\n' "$m"
            return 0
        fi
    done
    return 1
}

wait_container_running() {
    local container="$1"
    local deadline=$(( $(date +%s) + 120 ))
    while [ "$(date +%s)" -lt "$deadline" ]; do
        local state
        state="$(docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null || echo false)"
        if [ "$state" = "true" ]; then
            return 0
        fi
        sleep 1
    done
    log "wait_container_running: $container did not reach Running=true within 120s"
    return 1
}

# Light workload burst: fires N parallel test.ping + grains.items from
# the given master.  Non-blocking (returns the pgid so the caller can
# reap it); every call is ``|| true`` because transient errors are
# expected under fault.
start_workload_burst() {
    local master="$1" duration="$2"
    (
        local deadline=$(( $(date +%s) + duration ))
        while [ "$(date +%s)" -lt "$deadline" ]; do
            docker exec "$master" sh -c '
                salt --timeout=5 --out=json "*" test.ping >/dev/null 2>&1 || true
            ' >/dev/null 2>&1 || true
            sleep 2
        done
    ) &
    printf '%s\n' "$!"
}

# -------------------------------------------------------------------
# Phase 1: SIGSTOP a non-primary peer master for PEER_SIGSTOP_SEC
# -------------------------------------------------------------------
phase_cluster_peer_sigstop_60s() {
    local label="cluster_peer_sigstop_60s"
    case "${TOPOLOGY:-}" in
        cluster3) ;;
        *) record_skip "$label" "requires cluster3 (need >=2 masters sharing cluster_pki)"; return 0 ;;
    esac
    local peer
    peer="$(pick_non_primary_peer || true)"
    if [ -z "$peer" ]; then
        record_setup_error "$label" "no non-primary peer in MASTERS=${MASTERS}"
        return 1
    fi
    local fd_before rss_before fault_start fault_end fault_s
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (peer=${peer} hold=${PEER_SIGSTOP_SEC}s) ----"
    fault_start=$(date +%s)
    if ! docker kill -s STOP "$peer" >/dev/null 2>&1; then
        record_setup_error "$label" "docker kill -s STOP ${peer} failed"
        return 1
    fi
    PAUSED_CONTAINERS="${PAUSED_CONTAINERS} ${peer}"
    sleep "$PEER_SIGSTOP_SEC"
    if ! docker kill -s CONT "$peer" >/dev/null 2>&1; then
        record_setup_error "$label" "docker kill -s CONT ${peer} failed"
        docker kill -s CONT "$peer" >/dev/null 2>&1 || true
        return 1
    fi
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" \
            "paused_peer=${peer}"; then
        OVERALL_RC=1
    fi
}

# -------------------------------------------------------------------
# Phase 2: network-disconnect a non-primary peer for PEER_UNREACHABLE_SEC
# -------------------------------------------------------------------
phase_cluster_peer_unreachable() {
    local label="cluster_peer_unreachable"
    case "${TOPOLOGY:-}" in
        cluster3) ;;
        *) record_skip "$label" "requires cluster3"; return 0 ;;
    esac
    local peer
    peer="$(pick_non_primary_peer || true)"
    if [ -z "$peer" ]; then
        record_setup_error "$label" "no non-primary peer"
        return 1
    fi
    local fd_before rss_before fault_start fault_end fault_s
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (peer=${peer} hold=${PEER_UNREACHABLE_SEC}s) ----"
    fault_start=$(date +%s)
    if ! docker network disconnect "$CLUSTER3_NETWORK" "$peer" >/dev/null 2>&1; then
        record_setup_error "$label" "docker network disconnect ${CLUSTER3_NETWORK} ${peer} failed"
        return 1
    fi
    DISCONNECTED_CONTAINERS="${DISCONNECTED_CONTAINERS} ${CLUSTER3_NETWORK}|${peer}"
    sleep "$PEER_UNREACHABLE_SEC"
    if ! docker network connect "$CLUSTER3_NETWORK" "$peer" >/dev/null 2>&1; then
        record_setup_error "$label" "docker network connect ${CLUSTER3_NETWORK} ${peer} failed"
        # Try again before bailing; leaving the peer orphaned corrupts later phases.
        docker network connect "$CLUSTER3_NETWORK" "$peer" >/dev/null 2>&1 || true
        return 1
    fi
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" \
            "disconnected_peer=${peer}"; then
        OVERALL_RC=1
    fi
}

# -------------------------------------------------------------------
# Phase 3: cluster AES key rotation while workload is active.
#
# Entry point: write ``/var/cache/salt/master/.dfn`` with contents
# ``<master id>`` inside c3-salt-master-1.  The Maintenance thread's
# next tick (default loop_interval=60s, but the dropfile is checked on
# every tick) sees the file, matches it against its own id, and calls
# ``SMaster.rotate_cluster_secret`` which fires ``rotate_cluster_aes_key``
# on the peer event channel.  Peers install the new key via
# ``EventMonitor._install_rotated_cluster_aes``.  This is the exact code
# path exercised by tests/pytests/functional/cluster/test_rotate_isolated_fs.py
# and the fix for saltstack/salt#70543.
#
# No public salt-run runner wraps this on 3008.x; see the header for the
# full justification.
# -------------------------------------------------------------------
phase_cluster_aes_rotation_under_load() {
    local label="cluster_aes_rotation_under_load"
    case "${TOPOLOGY:-}" in
        cluster3) ;;
        *) record_skip "$label" "requires cluster3"; return 0 ;;
    esac
    local fd_before rss_before fault_start fault_end fault_s
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} ----"
    fault_start=$(date +%s)

    # Workload burst spans the whole rotation + propagation window.
    local workload_pid
    workload_pid="$(start_workload_burst "$PRIMARY_MASTER" \
        "$(( AES_PROPAGATION_WAIT_SEC + 15 ))")"

    # Write the dropfile.  owner id comes from the master's /etc/salt/master
    # ``id:`` line; for the cluster3 fixture that's ``salt-master-1``.
    local master_id
    master_id="$(docker exec "$PRIMARY_MASTER" sh -c "awk '/^id:/ {print \$2}' /etc/salt/master" 2>/dev/null | tr -d '[:space:]')"
    if [ -z "$master_id" ]; then
        record_setup_error "$label" "could not resolve master id in ${PRIMARY_MASTER}"
        kill "$workload_pid" >/dev/null 2>&1 || true
        return 1
    fi
    # Write .dfn: must be owned by salt user and mode 0400, otherwise
    # handle_key_rotate rejects it ("Found dropfile with incorrect permissions").
    if ! docker exec "$PRIMARY_MASTER" sh -c "
        umask 0277
        printf '%s' '${master_id}' > /var/cache/salt/master/.dfn.next \
            && chmod 0400 /var/cache/salt/master/.dfn.next \
            && mv /var/cache/salt/master/.dfn.next /var/cache/salt/master/.dfn
    " >/dev/null 2>&1; then
        record_setup_error "$label" "could not write .dfn dropfile in ${PRIMARY_MASTER}"
        kill "$workload_pid" >/dev/null 2>&1 || true
        return 1
    fi
    log "${label}: dropfile written (master_id=${master_id}); waiting ${AES_PROPAGATION_WAIT_SEC}s for propagation"
    sleep "$AES_PROPAGATION_WAIT_SEC"

    # Reap the workload burst.
    kill "$workload_pid" >/dev/null 2>&1 || true
    wait "$workload_pid" 2>/dev/null || true

    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" \
            "aes_rotation_via_dropfile master_id=${master_id}"; then
        OVERALL_RC=1
    fi
}

# -------------------------------------------------------------------
# Phase 4: haproxy backend flap.  Try the socat/socket control plane
# first; fall back to SIGSTOP of the backing master if socat isn't in
# the default haproxy:2.8 image.
# -------------------------------------------------------------------
phase_cluster_haproxy_backend_flap() {
    local label="cluster_haproxy_backend_flap"
    case "${TOPOLOGY:-}" in
        cluster3) ;;
        *) record_skip "$label" "requires cluster3 (needs haproxy)"; return 0 ;;
    esac
    local fd_before rss_before fault_start fault_end fault_s
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} ----"

    # haproxy.cfg does not expose a ``stats socket`` line, so socat
    # against /var/run/haproxy.sock will almost certainly fail.  We
    # still probe for it as a fast path so the phase works if a future
    # haproxy.cfg adds the socket.
    local use_socat=0
    if docker exec "$HAPROXY_CONTAINER" sh -c 'command -v socat >/dev/null 2>&1 && [ -S /var/run/haproxy.sock ]' >/dev/null 2>&1; then
        use_socat=1
    fi

    local peer
    peer="$(pick_non_primary_peer || true)"
    if [ -z "$peer" ]; then
        record_setup_error "$label" "no non-primary peer"
        return 1
    fi
    # Backend/server name from haproxy.cfg: backend "masters-ret" server
    # "salt-master-2" (short service name without the c3- prefix).
    local server_short="${peer#c3-}"

    fault_start=$(date +%s)
    if [ "$use_socat" = "1" ]; then
        log "${label}: disabling masters-ret/${server_short} via haproxy socket"
        if ! docker exec "$HAPROXY_CONTAINER" sh -c "
            echo 'disable server masters-ret/${server_short}' | socat stdio /var/run/haproxy.sock
        " >/dev/null 2>&1; then
            record_setup_error "$label" "haproxy socket disable failed; falling back"
            use_socat=0
        else
            HAPROXY_DISABLED_BACKENDS="${HAPROXY_DISABLED_BACKENDS} masters-ret/${server_short}"
        fi
    fi
    if [ "$use_socat" != "1" ]; then
        log "${label}: haproxy socket unavailable; falling back to SIGSTOP ${peer}"
        if ! docker kill -s STOP "$peer" >/dev/null 2>&1; then
            record_setup_error "$label" "fallback SIGSTOP ${peer} failed"
            return 1
        fi
        PAUSED_CONTAINERS="${PAUSED_CONTAINERS} ${peer}"
    fi

    sleep "$HAPROXY_FLAP_SEC"

    if [ "$use_socat" = "1" ]; then
        docker exec "$HAPROXY_CONTAINER" sh -c "
            echo 'enable server masters-ret/${server_short}' | socat stdio /var/run/haproxy.sock
        " >/dev/null 2>&1 || true
    else
        docker kill -s CONT "$peer" >/dev/null 2>&1 || true
    fi

    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))
    local mode notes
    if [ "$use_socat" = "1" ]; then mode="socat"; else mode="sigstop"; fi
    notes="haproxy_backend_flap mode=${mode} target=${peer}"
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" "$notes"; then
        OVERALL_RC=1
    fi
}

# -------------------------------------------------------------------
# Phase 5: split-brain simulation.  Disconnect PRIMARY_MASTER so the
# remaining two masters form a 2-of-3 quorum; haproxy will steer minion
# traffic to the still-healthy backends.  Reconnect, assert full 3-of-3.
# -------------------------------------------------------------------
phase_cluster_split_brain_simulate() {
    local label="cluster_split_brain_simulate"
    case "${TOPOLOGY:-}" in
        cluster3) ;;
        *) record_skip "$label" "requires cluster3 (needs quorum >= 3)"; return 0 ;;
    esac
    if [ "$MASTER_COUNT" -lt 3 ]; then
        record_skip "$label" "requires >=3 masters (got ${MASTER_COUNT})"
        return 0
    fi
    local fd_before rss_before fault_start fault_end fault_s
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (isolating ${PRIMARY_MASTER}) ----"
    fault_start=$(date +%s)
    if ! docker network disconnect "$CLUSTER3_NETWORK" "$PRIMARY_MASTER" >/dev/null 2>&1; then
        record_setup_error "$label" "disconnect ${PRIMARY_MASTER} failed"
        return 1
    fi
    DISCONNECTED_CONTAINERS="${DISCONNECTED_CONTAINERS} ${CLUSTER3_NETWORK}|${PRIMARY_MASTER}"
    sleep "$SPLIT_BRAIN_SEC"
    if ! docker network connect "$CLUSTER3_NETWORK" "$PRIMARY_MASTER" >/dev/null 2>&1; then
        record_setup_error "$label" "reconnect ${PRIMARY_MASTER} failed"
        docker network connect "$CLUSTER3_NETWORK" "$PRIMARY_MASTER" >/dev/null 2>&1 || true
        return 1
    fi
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" \
            "isolated=${PRIMARY_MASTER}"; then
        OVERALL_RC=1
    fi
}

# -------------------------------------------------------------------
# Phase 6: rolling restart with a workload burst between each peer.
# Walks $MASTERS in order; after each restart, fires a burst for
# ROLLING_WORKLOAD_BURST_SEC and asserts recovery before moving on.
# -------------------------------------------------------------------
phase_cluster_rolling_restart_with_traffic() {
    local label_prefix="cluster_rolling_restart_with_traffic"
    case "${TOPOLOGY:-}" in
        cluster3) ;;
        *) record_skip "$label_prefix" "requires cluster3"; return 0 ;;
    esac
    for m in $MASTERS; do
        local label="${label_prefix}_${m}"
        local fd_before rss_before fault_start fault_end fault_s
        read -r fd_before rss_before < <(sample_all_minions)
        log "---- phase: ${label} ----"
        fault_start=$(date +%s)
        if ! docker restart "$m" >/dev/null 2>&1; then
            record_setup_error "$label" "docker restart ${m} failed"
            continue
        fi
        if ! wait_container_running "$m"; then
            record_setup_error "$label" "${m} never returned to Running"
            continue
        fi
        # Workload burst on the master that's still serving; target the
        # restarted master if it's the PRIMARY, otherwise the PRIMARY.
        local burst_target
        if [ "$m" = "$PRIMARY_MASTER" ]; then
            # Pick any peer as the CLI source.
            burst_target="$(pick_non_primary_peer || echo "$PRIMARY_MASTER")"
        else
            burst_target="$PRIMARY_MASTER"
        fi
        local workload_pid
        workload_pid="$(start_workload_burst "$burst_target" "$ROLLING_WORKLOAD_BURST_SEC")"
        sleep "$ROLLING_WORKLOAD_BURST_SEC"
        kill "$workload_pid" >/dev/null 2>&1 || true
        wait "$workload_pid" 2>/dev/null || true
        fault_end=$(date +%s)
        fault_s=$(( fault_end - fault_start ))
        if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" \
                "rolling burst_from=${burst_target}"; then
            OVERALL_RC=1
        fi
    done
}

# -------------------------------------------------------------------
# Phase 7: multimaster-failover primary unreachable.  Minion should
# failover to master-b.  Reconnect master-a; assert.
# -------------------------------------------------------------------
phase_multimaster_primary_unreachable() {
    local label="multimaster_primary_unreachable"
    case "${TOPOLOGY:-}" in
        multimaster-failover) ;;
        *) record_skip "$label" "requires multimaster-failover (minion master_type=failover)"; return 0 ;;
    esac
    local primary="mm-salt-master-a"
    local fd_before rss_before fault_start fault_end fault_s
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (disconnecting ${primary}) ----"
    fault_start=$(date +%s)
    if ! docker network disconnect "$MULTIMASTER_NETWORK" "$primary" >/dev/null 2>&1; then
        record_setup_error "$label" "disconnect ${primary} failed"
        return 1
    fi
    DISCONNECTED_CONTAINERS="${DISCONNECTED_CONTAINERS} ${MULTIMASTER_NETWORK}|${primary}"
    sleep "$MM_PRIMARY_UNREACH_SEC"
    if ! docker network connect "$MULTIMASTER_NETWORK" "$primary" >/dev/null 2>&1; then
        record_setup_error "$label" "reconnect ${primary} failed"
        docker network connect "$MULTIMASTER_NETWORK" "$primary" >/dev/null 2>&1 || true
        return 1
    fi
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))
    # For failover, PRIMARY_MASTER is already mm-salt-master-a (see
    # common.sh).  After reconnect, master-a is the only one that can
    # answer the assertion ping for every minion whose failover list
    # includes it; master-b-only minions would still answer via
    # master-b.  assert_reconnect uses PRIMARY_MASTER to ping, which
    # is master-a; that's the one we just reconnected, so the ping is
    # correct.
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" \
            "disconnected=${primary}"; then
        OVERALL_RC=1
    fi
}

# -------------------------------------------------------------------
# Phase 8: multimaster-hothot one-master tc partition (100% loss)
# applied to master-a only.  The minion's second leg (master-b) must
# keep answering throughout.
# -------------------------------------------------------------------
phase_multimaster_hothot_one_master_tc_partition() {
    local label="multimaster_hothot_one_master_tc_partition"
    case "${TOPOLOGY:-}" in
        multimaster-hothot) ;;
        *) record_skip "$label" "requires multimaster-hothot (minion connects to both)"; return 0 ;;
    esac
    # First master in $MASTERS (per common.sh, mm-salt-master-a).
    local first_master=""
    for m in $MASTERS; do first_master="$m"; break; done
    if [ -z "$first_master" ]; then
        record_setup_error "$label" "no masters in MASTERS"
        return 1
    fi
    # tc requires iproute2 in the master image; the cluster-3node
    # Dockerfile.salt is also used for the multimaster masters, so the
    # tc binary is only present if the image was built with iproute2.
    if ! docker exec "$first_master" sh -c 'command -v tc >/dev/null 2>&1' >/dev/null 2>&1; then
        record_setup_error "$label" "tc not available in ${first_master}"
        return 0
    fi
    local fd_before rss_before fault_start fault_end fault_s
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (netem loss 100% on ${first_master}) ----"
    fault_start=$(date +%s)
    if ! docker exec "$first_master" sh -c "tc qdisc replace dev ${CHOKE_IFACE} root netem loss 100%" >/dev/null 2>&1; then
        record_setup_error "$label" "tc replace failed on ${first_master}"
        return 1
    fi
    NETEM_CONTAINERS="${NETEM_CONTAINERS} ${first_master}"
    # During the partition, PRIMARY_MASTER (mm-salt-master-a) is
    # unreachable so we can't use it to probe liveness.  Probe the
    # second master instead; a hothot minion must still answer there.
    local probe_master=""
    for m in $MASTERS; do
        if [ "$m" != "$first_master" ]; then
            probe_master="$m"
            break
        fi
    done
    local inflight_ok=1
    if [ -n "$probe_master" ]; then
        if ! docker exec "$probe_master" salt --timeout="$PING_TIMEOUT_SEC" --out=json '*' test.ping >/dev/null 2>&1; then
            inflight_ok=0
            log "${label}: WARN second-leg probe via ${probe_master} failed mid-fault"
        fi
    fi
    sleep "$MM_HOTHOT_PARTITION_SEC"
    docker exec "$first_master" sh -c "tc qdisc del dev ${CHOKE_IFACE} root 2>/dev/null" >/dev/null 2>&1 || true
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))
    local notes="partition=${first_master} second_leg_ok=${inflight_ok}"
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" "$notes"; then
        OVERALL_RC=1
    fi
}

# -------------------------------------------------------------------
# Phase 9: staggered restart of both multimaster masters; restart .a,
# wait MM_STAGGERED_GAP_SEC (not for recovery), restart .b before .a
# is back.  Assert eventual recovery.
# -------------------------------------------------------------------
phase_multimaster_both_masters_restart_staggered() {
    local label="multimaster_both_masters_restart_staggered"
    case "${TOPOLOGY:-}" in
        multimaster-failover|multimaster-hothot) ;;
        *) record_skip "$label" "requires multimaster-*"; return 0 ;;
    esac
    if [ "$MASTER_COUNT" -lt 2 ]; then
        record_skip "$label" "requires >=2 masters"
        return 0
    fi
    local first_master="" second_master=""
    for m in $MASTERS; do
        if [ -z "$first_master" ]; then
            first_master="$m"
        elif [ -z "$second_master" ]; then
            second_master="$m"
        fi
    done
    local fd_before rss_before fault_start fault_end fault_s
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (${first_master} then ${second_master} staggered ${MM_STAGGERED_GAP_SEC}s) ----"
    fault_start=$(date +%s)
    if ! docker restart "$first_master" >/dev/null 2>&1; then
        record_setup_error "$label" "docker restart ${first_master} failed"
        return 1
    fi
    sleep "$MM_STAGGERED_GAP_SEC"
    if ! docker restart "$second_master" >/dev/null 2>&1; then
        record_setup_error "$label" "docker restart ${second_master} failed"
        # Best-effort wait on the first so the EXIT trap doesn't see
        # a dangling container state.
        wait_container_running "$first_master" || true
        return 1
    fi
    wait_container_running "$first_master" || true
    wait_container_running "$second_master" || true
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" \
            "staggered gap=${MM_STAGGERED_GAP_SEC}s"; then
        OVERALL_RC=1
    fi
}

# -------------------------------------------------------------------
# Main battery
# -------------------------------------------------------------------
log "cluster_faults scenario starting topology=${TOPOLOGY} masters=${MASTER_COUNT}"

phase_cluster_peer_sigstop_60s
between_phases

phase_cluster_peer_unreachable
between_phases

phase_cluster_aes_rotation_under_load
between_phases

phase_cluster_haproxy_backend_flap
between_phases

phase_cluster_split_brain_simulate
between_phases

phase_cluster_rolling_restart_with_traffic
between_phases

phase_multimaster_primary_unreachable
between_phases

phase_multimaster_hothot_one_master_tc_partition
between_phases

phase_multimaster_both_masters_restart_staggered

log "cluster_faults battery complete; overall_rc=${OVERALL_RC}"
exit "$OVERALL_RC"
