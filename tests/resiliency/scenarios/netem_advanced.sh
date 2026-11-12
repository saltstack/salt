#!/usr/bin/env bash
#
# Resiliency scenario: advanced netem + layer-2/3 fault injection.
#
# Extends the base battery in ``network_faults.sh`` into more esoteric
# transport-layer pathologies: packet reordering, duplication, corruption,
# MTU shrink, raw-rate bottleneck (tbf), true-asymmetric egress/ingress
# loss (ingress needs ifb + mirred), a SYN flood against the master
# return port (hping3), and a cluster3-only "single backend sick" split
# horizon via tc u32 filter.
#
# Each phase applies the fault inside $CHOKE_CONTAINER on $CHOKE_IFACE,
# holds it for $PHASE_DURATION_SEC seconds, clears, then calls
# assert_reconnect and records the outcome.
#
# Env contract: TOPOLOGY must be exported before running.  See
#   tests/resiliency/lib/common.sh
#
# Phases (in order):
#   1. netem_reorder_30            netem delay 10ms reorder 30% 50%
#   2. netem_duplicate_20          netem duplicate 20%
#   3. netem_corrupt_5             netem corrupt 5%
#   4. netem_mtu_drop              ip link set dev $CHOKE_IFACE mtu 576
#                                  (NOT netem; raw link mtu shrink)
#   5. netem_rate_limit_1mbit      tbf rate 1mbit burst 32kbit latency 400ms
#   6. netem_asymmetric_outbound   netem loss 100% on egress only (default tc)
#   7. netem_asymmetric_inbound    ifb0 + mirred ingress redirect + loss 100%
#   8. netem_syn_flood_simulation  hping3 --flood --syn -p 44506 <master>
#   9. netem_split_horizon_cluster tc u32 drop to one specific backend IP
#                                  (cluster3 only; others record skipped_for_topology)
#
# Skips:
#   - Phases 1-3, 5-7, 9: skipped with outcome=setup_error if tc/iproute2
#     is unavailable in $CHOKE_CONTAINER.
#   - Phase 4 (mtu_drop): setup_error if ``ip link set`` fails
#     (missing NET_ADMIN or iproute2).
#   - Phase 7 (asymmetric_inbound): setup_error if ``modprobe ifb`` fails
#     inside the choke container -- most docker hosts have ifb available
#     but it isn't always auto-loaded, and unprivileged containers can't
#     load kernel modules.
#   - Phase 8 (syn_flood): setup_error if hping3 install fails via
#     apt/apk/dnf/yum.
#   - Phase 9 (split_horizon_cluster): outcome=skipped_for_topology on
#     every TOPOLOGY other than cluster3 (needs a VIP with multiple
#     backends to be meaningful).
#
# Don'ts:
#   - no /tmp (use $RESILIENCY_WORKDIR)
#   - no committing
#   - no touching master processes (that's master_restart.sh / signal_pause.sh)

set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "${HERE}/../lib/common.sh"

load_topology

# Scenario-local exit code: 0 = all phases recovered, 1 = at least one phase
# failed (recovery missed OR leak threshold exceeded).  Final line of this
# file is ``exit "$OVERALL_RC"`` so the orchestrator sees the aggregate.
OVERALL_RC=0

: "${PHASE_DURATION_SEC:=$TIER_STANDARD_SEC}"
: "${MASTER_RET_PORT:=44506}"
export PHASE_DURATION_SEC MASTER_RET_PORT

SCENARIO_WORKDIR="${RESILIENCY_WORKDIR}/netem_advanced"
mkdir -p "$SCENARIO_WORKDIR"

NETEM_AVAILABLE=0
NETEM_ROOT_ACTIVE=0     # qdisc installed at root (netem / tbf)
NETEM_INGRESS_ACTIVE=0  # ingress qdisc + ifb redirect installed
IFB_ACTIVE=0            # netem/loss applied to ifb0
MTU_CHANGED=0           # link MTU no longer 1500
HPING3_PID=""           # backgrounded hping3 inside $CHOKE_CONTAINER

# -------------------------------------------------------------------------
# Infra helpers
# -------------------------------------------------------------------------

# Ensure the `tc` binary is present inside $CHOKE_CONTAINER.
ensure_tc() {
    if docker exec "$CHOKE_CONTAINER" sh -c 'command -v tc >/dev/null 2>&1'; then
        NETEM_AVAILABLE=1
        return 0
    fi
    log "ensure_tc: installing iproute2 in $CHOKE_CONTAINER"
    docker exec "$CHOKE_CONTAINER" sh -c '
        (command -v apt-get >/dev/null 2>&1 \
            && apt-get update -qq >/dev/null 2>&1 \
            && apt-get install -y --no-install-recommends iproute2 >/dev/null 2>&1) \
        || (command -v apk >/dev/null 2>&1 \
            && apk add --no-cache iproute2 >/dev/null 2>&1) \
        || (command -v dnf >/dev/null 2>&1 \
            && dnf install -y iproute-tc >/dev/null 2>&1) \
        || (command -v yum >/dev/null 2>&1 \
            && yum install -y iproute-tc >/dev/null 2>&1)
    ' >/dev/null 2>&1 || true
    if docker exec "$CHOKE_CONTAINER" sh -c 'command -v tc >/dev/null 2>&1'; then
        NETEM_AVAILABLE=1
        log "ensure_tc: tc available in $CHOKE_CONTAINER"
        return 0
    fi
    NETEM_AVAILABLE=0
    log "ensure_tc: tc NOT available in $CHOKE_CONTAINER after install attempt"
    return 1
}

# Ensure hping3 is present inside $CHOKE_CONTAINER.  Returns 0 if available.
ensure_hping3() {
    if docker exec "$CHOKE_CONTAINER" sh -c 'command -v hping3 >/dev/null 2>&1'; then
        return 0
    fi
    log "ensure_hping3: installing hping3 in $CHOKE_CONTAINER"
    docker exec "$CHOKE_CONTAINER" sh -c '
        (command -v apt-get >/dev/null 2>&1 \
            && apt-get update -qq >/dev/null 2>&1 \
            && apt-get install -y --no-install-recommends hping3 >/dev/null 2>&1) \
        || (command -v apk >/dev/null 2>&1 \
            && apk add --no-cache hping3 >/dev/null 2>&1) \
        || (command -v dnf >/dev/null 2>&1 \
            && dnf install -y hping3 >/dev/null 2>&1) \
        || (command -v yum >/dev/null 2>&1 \
            && yum install -y hping3 >/dev/null 2>&1)
    ' >/dev/null 2>&1 || true
    docker exec "$CHOKE_CONTAINER" sh -c 'command -v hping3 >/dev/null 2>&1'
}

# Resolve a docker container's primary IPv4 on any attached network.
# Prints empty string on failure.
container_ip() {
    local c="$1"
    docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' "$c" 2>/dev/null \
        | awk '{print $1}'
}

# Clear any root qdisc on $CHOKE_IFACE (netem, tbf).
clear_root_qdisc() {
    docker exec "$CHOKE_CONTAINER" sh -c "tc qdisc del dev ${CHOKE_IFACE} root 2>/dev/null" \
        >/dev/null 2>&1 || true
    NETEM_ROOT_ACTIVE=0
}

# Tear down ifb0 ingress mirror + qdisc.
clear_ingress_qdisc() {
    docker exec "$CHOKE_CONTAINER" sh -c "
        tc qdisc del dev ${CHOKE_IFACE} ingress 2>/dev/null || true
        tc qdisc del dev ifb0 root 2>/dev/null || true
        ip link set dev ifb0 down 2>/dev/null || true
    " >/dev/null 2>&1 || true
    NETEM_INGRESS_ACTIVE=0
    IFB_ACTIVE=0
}

# Restore the link MTU to 1500.
restore_mtu() {
    docker exec "$CHOKE_CONTAINER" sh -c "ip link set dev ${CHOKE_IFACE} mtu 1500 2>/dev/null" \
        >/dev/null 2>&1 || true
    MTU_CHANGED=0
}

# Kill a running hping3 (if we started one).
kill_hping3() {
    if [ -n "$HPING3_PID" ]; then
        docker exec "$CHOKE_CONTAINER" sh -c "kill -9 ${HPING3_PID} 2>/dev/null" \
            >/dev/null 2>&1 || true
    fi
    # Belt + suspenders: pkill by name too in case the PID was recycled.
    docker exec "$CHOKE_CONTAINER" sh -c 'pkill -9 -f hping3 2>/dev/null || true' \
        >/dev/null 2>&1 || true
    HPING3_PID=""
}

on_exit() {
    local ec=$?
    if [ "$NETEM_ROOT_ACTIVE" = "1" ]; then
        clear_root_qdisc
    fi
    if [ "$NETEM_INGRESS_ACTIVE" = "1" ] || [ "$IFB_ACTIVE" = "1" ]; then
        clear_ingress_qdisc
    fi
    if [ "$MTU_CHANGED" = "1" ]; then
        restore_mtu
    fi
    kill_hping3
    exit "$ec"
}
trap on_exit EXIT INT TERM

# -------------------------------------------------------------------------
# Phase runner for plain netem (root qdisc) phases.
# -------------------------------------------------------------------------
run_netem_phase() {
    local label="$1" netem_args="$2"
    local fd_before rss_before
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: netem '${netem_args}' for ${PHASE_DURATION_SEC}s"
    if [ "$NETEM_AVAILABLE" != "1" ]; then
        log "PHASE ${label}: skipped (tc unavailable)"
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "tc/iproute2 unavailable in $CHOKE_CONTAINER"
        return 0
    fi
    if ! docker exec "$CHOKE_CONTAINER" sh -c "tc qdisc replace dev ${CHOKE_IFACE} root netem ${netem_args}" >/dev/null 2>&1; then
        log "PHASE ${label}: tc qdisc replace failed"
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "tc qdisc replace netem ${netem_args} failed"
        clear_root_qdisc
        return 0
    fi
    NETEM_ROOT_ACTIVE=1
    sleep "$PHASE_DURATION_SEC"
    clear_root_qdisc
    assert_reconnect "$label" "$PHASE_DURATION_SEC" "$fd_before" "$rss_before" \
        "netem ${netem_args}"  || OVERALL_RC=1
}

# -------------------------------------------------------------------------
# Main battery
# -------------------------------------------------------------------------
log "netem_advanced scenario starting topology=${TOPOLOGY} choke=${CHOKE_CONTAINER} iface=${CHOKE_IFACE}"
ensure_tc || true

# Phase 1: reorder 30% / 50% correlation, needs a small base delay.
run_netem_phase "netem_reorder_30"   "delay 10ms reorder 30% 50%"

# Phase 2: duplicate 20%.
run_netem_phase "netem_duplicate_20" "duplicate 20%"

# Phase 3: corrupt 5% (random bit-flip in payload).
run_netem_phase "netem_corrupt_5"    "corrupt 5%"

# ---------------------------------------------------------------
# Phase 4: MTU shrink to 576 (IPv4 minimum).  Not netem; raw link.
# ---------------------------------------------------------------
{
    label="netem_mtu_drop"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: ip link set dev ${CHOKE_IFACE} mtu 576 for ${PHASE_DURATION_SEC}s"
    if ! docker exec "$CHOKE_CONTAINER" sh -c 'command -v ip >/dev/null 2>&1'; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "iproute2 (ip) unavailable in $CHOKE_CONTAINER"
    elif ! docker exec "$CHOKE_CONTAINER" sh -c "ip link set dev ${CHOKE_IFACE} mtu 576" >/dev/null 2>&1; then
        log "PHASE ${label}: mtu change failed (missing NET_ADMIN?)"
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "ip link set mtu 576 failed on $CHOKE_CONTAINER"
    else
        MTU_CHANGED=1
        sleep "$PHASE_DURATION_SEC"
        restore_mtu
        assert_reconnect "$label" "$PHASE_DURATION_SEC" "$fd_before" "$rss_before" \
            "link mtu dropped to 576 on $CHOKE_CONTAINER"  || OVERALL_RC=1
    fi
    unset label fd_before rss_before
}

# ---------------------------------------------------------------
# Phase 5: tbf 1mbit rate limit.
# ---------------------------------------------------------------
{
    label="netem_rate_limit_1mbit"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: tbf rate 1mbit burst 32kbit latency 400ms for ${PHASE_DURATION_SEC}s"
    if [ "$NETEM_AVAILABLE" != "1" ]; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "tc/iproute2 unavailable in $CHOKE_CONTAINER"
    elif ! docker exec "$CHOKE_CONTAINER" sh -c "
        tc qdisc replace dev ${CHOKE_IFACE} root tbf rate 1mbit burst 32kbit latency 400ms
    " >/dev/null 2>&1; then
        log "PHASE ${label}: tbf replace failed"
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "tc qdisc replace tbf failed"
        clear_root_qdisc
    else
        NETEM_ROOT_ACTIVE=1
        sleep "$PHASE_DURATION_SEC"
        clear_root_qdisc
        assert_reconnect "$label" "$PHASE_DURATION_SEC" "$fd_before" "$rss_before" \
            "tbf rate 1mbit burst 32kbit latency 400ms"  || OVERALL_RC=1
    fi
    unset label fd_before rss_before
}

# ---------------------------------------------------------------
# Phase 6: asymmetric outbound (egress-only) loss 100%.
# tc's root qdisc is egress-only by default, so applying netem loss 100%
# at the root drops outbound packets while inbound traffic still reaches
# the choke container.  From the minion-POV (CHOKE is the master or
# haproxy), this means minion -> master publishes/replies get dropped on
# egress but inbound SYN/ACKs on new master-side connections survive.
# ---------------------------------------------------------------
{
    label="netem_asymmetric_outbound"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: netem loss 100% egress-only for ${PHASE_DURATION_SEC}s"
    if [ "$NETEM_AVAILABLE" != "1" ]; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "tc/iproute2 unavailable in $CHOKE_CONTAINER"
    elif ! docker exec "$CHOKE_CONTAINER" sh -c "
        tc qdisc replace dev ${CHOKE_IFACE} root netem loss 100%
    " >/dev/null 2>&1; then
        log "PHASE ${label}: tc qdisc replace failed"
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "tc qdisc replace netem loss 100% (egress) failed"
        clear_root_qdisc
    else
        NETEM_ROOT_ACTIVE=1
        sleep "$PHASE_DURATION_SEC"
        clear_root_qdisc
        assert_reconnect "$label" "$PHASE_DURATION_SEC" "$fd_before" "$rss_before" \
            "egress-only loss 100% via root netem"  || OVERALL_RC=1
    fi
    unset label fd_before rss_before
}

# ---------------------------------------------------------------
# Phase 7: asymmetric inbound via ifb + mirred ingress redirect.
# Mirror ingress to ifb0 and apply netem loss 100% on ifb0 egress.
# This drops packets arriving at $CHOKE_IFACE while egress from the
# choke container still works -- the inverse of phase 6.
# ---------------------------------------------------------------
{
    label="netem_asymmetric_inbound"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: ifb + mirred ingress redirect + netem loss 100% for ${PHASE_DURATION_SEC}s"
    if [ "$NETEM_AVAILABLE" != "1" ]; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "tc/iproute2 unavailable in $CHOKE_CONTAINER"
    elif ! docker exec "$CHOKE_CONTAINER" sh -c '
        modprobe ifb numifbs=1 2>/dev/null \
        || (ls /sys/class/net/ifb0 >/dev/null 2>&1)
    ' >/dev/null 2>&1; then
        log "PHASE ${label}: modprobe ifb failed"
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "modprobe ifb failed in $CHOKE_CONTAINER (unprivileged container?)"
    else
        setup_rc=0
        docker exec "$CHOKE_CONTAINER" sh -c "
            set -e
            ip link set dev ifb0 up
            tc qdisc add dev ${CHOKE_IFACE} ingress
            tc filter add dev ${CHOKE_IFACE} parent ffff: protocol all u32 \
                match u32 0 0 action mirred egress redirect dev ifb0
            tc qdisc replace dev ifb0 root netem loss 100%
        " >/dev/null 2>&1 || setup_rc=$?

        if [ "$setup_rc" != "0" ]; then
            log "PHASE ${label}: tc setup failed (rc=${setup_rc})"
            record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
                "ifb/mirred ingress setup failed in $CHOKE_CONTAINER"
            clear_ingress_qdisc
        else
            NETEM_INGRESS_ACTIVE=1
            IFB_ACTIVE=1
            sleep "$PHASE_DURATION_SEC"
            clear_ingress_qdisc
            assert_reconnect "$label" "$PHASE_DURATION_SEC" "$fd_before" "$rss_before" \
                "ingress-only loss 100% via ifb0 mirred redirect"  || OVERALL_RC=1
        fi
        unset setup_rc
    fi
    unset label fd_before rss_before
}

# ---------------------------------------------------------------
# Phase 7a: asymmetric outbound (egress) loss 100% held through
# multiple auth_timeout retries (DEEPREC tier).
# ---------------------------------------------------------------
{
    label="netem_asymmetric_outbound_deep"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: netem loss 100% egress-only for ${TIER_DEEPREC_SEC}s"
    if [ "$NETEM_AVAILABLE" != "1" ]; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "tc/iproute2 unavailable in $CHOKE_CONTAINER"
    elif ! docker exec "$CHOKE_CONTAINER" sh -c "
        tc qdisc replace dev ${CHOKE_IFACE} root netem loss 100%
    " >/dev/null 2>&1; then
        log "PHASE ${label}: tc qdisc replace failed"
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "tc qdisc replace netem loss 100% (egress, deep) failed"
        clear_root_qdisc
    else
        NETEM_ROOT_ACTIVE=1
        _saved_window="$RECONNECT_WINDOW_SEC"
        RECONNECT_WINDOW_SEC="$RECOVER_STANDARD_SEC"
        export RECONNECT_WINDOW_SEC
        sleep "$TIER_DEEPREC_SEC"
        clear_root_qdisc
        assert_reconnect "$label" "$TIER_DEEPREC_SEC" "$fd_before" "$rss_before" \
            "egress-only loss 100% via root netem (deep)"  || OVERALL_RC=1
        RECONNECT_WINDOW_SEC="$_saved_window"
        export RECONNECT_WINDOW_SEC
        unset _saved_window
    fi
    unset label fd_before rss_before
}

# ---------------------------------------------------------------
# Phase 7b: asymmetric inbound (ifb+mirred) loss 100% held through
# multiple auth_timeout retries (DEEPREC tier).
# ---------------------------------------------------------------
{
    label="netem_asymmetric_inbound_deep"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: ifb + mirred ingress redirect + netem loss 100% for ${TIER_DEEPREC_SEC}s"
    if [ "$NETEM_AVAILABLE" != "1" ]; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "tc/iproute2 unavailable in $CHOKE_CONTAINER"
    elif ! docker exec "$CHOKE_CONTAINER" sh -c '
        modprobe ifb numifbs=1 2>/dev/null \
        || (ls /sys/class/net/ifb0 >/dev/null 2>&1)
    ' >/dev/null 2>&1; then
        log "PHASE ${label}: modprobe ifb failed"
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "modprobe ifb failed in $CHOKE_CONTAINER (unprivileged container?)"
    else
        setup_rc=0
        docker exec "$CHOKE_CONTAINER" sh -c "
            set -e
            ip link set dev ifb0 up
            tc qdisc add dev ${CHOKE_IFACE} ingress
            tc filter add dev ${CHOKE_IFACE} parent ffff: protocol all u32 \
                match u32 0 0 action mirred egress redirect dev ifb0
            tc qdisc replace dev ifb0 root netem loss 100%
        " >/dev/null 2>&1 || setup_rc=$?

        if [ "$setup_rc" != "0" ]; then
            log "PHASE ${label}: tc setup failed (rc=${setup_rc})"
            record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
                "ifb/mirred ingress setup failed in $CHOKE_CONTAINER (deep)"
            clear_ingress_qdisc
        else
            NETEM_INGRESS_ACTIVE=1
            IFB_ACTIVE=1
            _saved_window="$RECONNECT_WINDOW_SEC"
            RECONNECT_WINDOW_SEC="$RECOVER_STANDARD_SEC"
            export RECONNECT_WINDOW_SEC
            sleep "$TIER_DEEPREC_SEC"
            clear_ingress_qdisc
            assert_reconnect "$label" "$TIER_DEEPREC_SEC" "$fd_before" "$rss_before" \
                "ingress-only loss 100% via ifb0 mirred redirect (deep)"  || OVERALL_RC=1
            RECONNECT_WINDOW_SEC="$_saved_window"
            export RECONNECT_WINDOW_SEC
            unset _saved_window
        fi
        unset setup_rc
    fi
    unset label fd_before rss_before
}

# ---------------------------------------------------------------
# Phase 8: SYN flood against the master return port (44506).
# hping3 --flood --syn from the choke container.  For cluster3 this
# comes from haproxy (so it floods its own backends); for single /
# multimaster it comes from the master itself at its own return port
# -- still exercises the master's accept() path under TCP SYN pressure.
# ---------------------------------------------------------------
{
    label="netem_syn_flood_simulation"
    read -r fd_before rss_before < <(sample_all_minions)
    target_ip="$(container_ip "$PRIMARY_MASTER")"
    log "PHASE ${label}: hping3 --flood --syn -p ${MASTER_RET_PORT} ${target_ip} for ${PHASE_DURATION_SEC}s"
    if [ -z "$target_ip" ]; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "could not resolve IP for $PRIMARY_MASTER"
    elif ! ensure_hping3; then
        log "PHASE ${label}: hping3 install failed -- skipping"
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "hping3 unavailable in $CHOKE_CONTAINER (install failed)"
    else
        # Start hping3 in the background inside the container.  We capture
        # the PID via docker exec + ``echo $!`` in the same shell so the
        # PID is visible to subsequent docker execs.
        HPING3_PID="$(docker exec -d "$CHOKE_CONTAINER" sh -c "
            hping3 --flood --syn -p ${MASTER_RET_PORT} ${target_ip} >/dev/null 2>&1 &
            echo \$!
        " 2>/dev/null || true)"
        # ``docker exec -d`` detaches; we need pgrep to find the actual PID.
        sleep 1
        HPING3_PID="$(docker exec "$CHOKE_CONTAINER" sh -c 'pgrep -f "hping3 --flood" | head -1' 2>/dev/null | tr -d '[:space:]')"
        if [ -z "$HPING3_PID" ]; then
            log "PHASE ${label}: hping3 failed to start"
            record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
                "hping3 did not start in $CHOKE_CONTAINER"
        else
            log "PHASE ${label}: hping3 running pid=${HPING3_PID}"
            sleep "$PHASE_DURATION_SEC"
            kill_hping3
            assert_reconnect "$label" "$PHASE_DURATION_SEC" "$fd_before" "$rss_before" \
                "hping3 --flood --syn -p ${MASTER_RET_PORT} ${target_ip}"  || OVERALL_RC=1
        fi
    fi
    unset label fd_before rss_before target_ip
}

# ---------------------------------------------------------------
# Phase 9: cluster3-only split horizon.  Apply a tc u32 filter on the
# haproxy egress that drops packets destined to one specific backend
# master's IP; the other two backends keep flowing.  Simulates a single
# backend's network going bad while the VIP and the other peers stay
# healthy.
# ---------------------------------------------------------------
{
    label="netem_split_horizon_cluster"
    if [ "${TOPOLOGY:-}" != "cluster3" ]; then
        log "PHASE ${label}: skipped (topology ${TOPOLOGY} has no multi-backend VIP)"
        record_result "$label" "skipped_for_topology" "-1" "0" "" "0" "0" "0" \
            "skipped_for_topology: split-horizon requires cluster3 (multi-backend VIP)"
    else
        read -r fd_before rss_before < <(sample_all_minions)
        # Choose the *last* master in $MASTERS as the "sick" backend so
        # the primary used for the salt CLI (first in the list) keeps
        # working.  This matters because assert_reconnect runs the salt
        # CLI on $PRIMARY_MASTER -- it must stay reachable.
        sick_master=""
        for m in $MASTERS; do sick_master="$m"; done
        sick_ip="$(container_ip "$sick_master")"
        log "PHASE ${label}: tc u32 drop to ${sick_master} (${sick_ip}) via haproxy for ${TIER_DEEPREC_SEC}s"
        if [ "$NETEM_AVAILABLE" != "1" ]; then
            record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
                "tc/iproute2 unavailable in $CHOKE_CONTAINER"
        elif [ -z "$sick_ip" ]; then
            record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
                "could not resolve IP for $sick_master"
        else
            # Build a u32 filter: prio HTB-ish root with a drop class
            # targeting dst = $sick_ip.  Simpler form: use a plain prio
            # qdisc with a u32 filter that matches dst and uses action
            # drop.  Needs a classful parent, so install ``prio`` first.
            setup_rc=0
            docker exec "$CHOKE_CONTAINER" sh -c "
                set -e
                tc qdisc replace dev ${CHOKE_IFACE} root handle 1: prio
                tc filter add dev ${CHOKE_IFACE} parent 1: protocol ip prio 1 u32 \
                    match ip dst ${sick_ip}/32 action drop
            " >/dev/null 2>&1 || setup_rc=$?

            if [ "$setup_rc" != "0" ]; then
                log "PHASE ${label}: tc filter setup failed (rc=${setup_rc})"
                record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
                    "tc u32 drop filter for ${sick_ip} failed on $CHOKE_CONTAINER"
                clear_root_qdisc
            else
                NETEM_ROOT_ACTIVE=1
                _saved_window="$RECONNECT_WINDOW_SEC"
                RECONNECT_WINDOW_SEC="$RECOVER_STANDARD_SEC"
                export RECONNECT_WINDOW_SEC
                sleep "$TIER_DEEPREC_SEC"
                clear_root_qdisc
                assert_reconnect "$label" "$TIER_DEEPREC_SEC" "$fd_before" "$rss_before" \
                    "tc u32 drop to ${sick_master} ${sick_ip} via $CHOKE_CONTAINER (deep)"  || OVERALL_RC=1
                RECONNECT_WINDOW_SEC="$_saved_window"
                export RECONNECT_WINDOW_SEC
                unset _saved_window
            fi
            unset setup_rc
        fi
        unset fd_before rss_before sick_master sick_ip m
    fi
    unset label
}

log "netem_advanced scenario complete; results in ${RESULTS_FILE}"

exit "$OVERALL_RC"
