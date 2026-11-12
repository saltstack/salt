#!/usr/bin/env bash
#
# Resiliency scenario: network faults.
#
# Walks the minion-side network layer through a battery of transient faults
# (latency, loss, jitter+loss, full partition, TCP RST injection, container
# pause, DNS flap).  After each phase the fault is cleared and
# assert_reconnect verifies every minion in $MINION_IDS answers test.ping
# within $RECONNECT_WINDOW_SEC and that fd/rss haven't crept past the
# thresholds encoded in common.sh.
#
# Env contract: TOPOLOGY must be exported before running.  See
#   tests/resiliency/lib/common.sh
# for the topology -> container mapping.
#
# Phases (in order):
#   1. network_latency                 netem delay 200ms +/- 50ms
#   2. network_loss_10                 netem loss 10%
#   3. network_jitter_loss             netem delay 100ms +/- 40ms, loss 5%
#   4. network_partition_full          netem loss 100%
#   5. network_tcp_reset               iptables REJECT --reject-with tcp-reset
#                                      on minion OUTPUT dport 44506
#   6. network_pause_master            docker pause $PRIMARY_MASTER
#   7. network_dns_flap                rewrite /etc/hosts on each minion
#
# Skips:
#   - netem phases (1-4) are skipped with outcome=setup_error if the choke
#     container doesn't have `tc` available and we can't install iproute2.
#   - tcp_reset is skipped with outcome=setup_error if iptables install
#     fails inside any minion (usually = NET_ADMIN missing in that compose).
#   - dns_flap is recorded "skipped_for_topology" on TOPOLOGY=single because
#     the minion resolves "salt-master" via docker's embedded DNS rather than
#     /etc/hosts, so rewriting /etc/hosts doesn't actually flap resolution
#     for the single-node compose.  cluster3 + multimaster go through
#     container hostnames that we can poison via /etc/hosts entries.
#
# Don'ts:
#   - no master restart (sibling scenario)
#   - no /tmp (use $RESILIENCY_WORKDIR)
#   - no committing

set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "${HERE}/../lib/common.sh"

load_topology

: "${PHASE_DURATION_SEC:=60}"
: "${MASTER_RET_PORT:=44506}"
export PHASE_DURATION_SEC MASTER_RET_PORT

SCENARIO_WORKDIR="${RESILIENCY_WORKDIR}/network_faults"
mkdir -p "$SCENARIO_WORKDIR"

# Track whether the netem probe succeeded so cleanup doesn't blow up.
NETEM_AVAILABLE=0
# Set to 1 once we have an active netem qdisc; trap uses it to decide whether
# to try the delete.  Flipped back to 0 after a successful clear.
NETEM_ACTIVE=0

# -------------------------------------------------------------------------
# Infra helpers
# -------------------------------------------------------------------------

# Ensure the `tc` binary is present inside $CHOKE_CONTAINER.  Sets
# NETEM_AVAILABLE=1 on success, 0 otherwise.  Does not fail the script on
# apt error -- the netem phases handle the skip themselves.
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

# Apply a netem qdisc to $CHOKE_IFACE in the choke container(s).  For
# cluster3, $CHOKE_CONTAINER is the haproxy VIP so a single application
# affects all backend traffic.  For multimaster, iterate $MASTERS so each
# master's eth0 is choked symmetrically.  For single, $CHOKE_CONTAINER ==
# $PRIMARY_MASTER so a single call does the right thing.
apply_netem() {
    local netem_args="$1"
    local containers
    case "${TOPOLOGY:-}" in
        multimaster-failover|multimaster-hothot)
            containers="$MASTERS"
            ;;
        *)
            containers="$CHOKE_CONTAINER"
            ;;
    esac
    local c rc=0
    for c in $containers; do
        if ! docker exec "$c" sh -c "tc qdisc replace dev ${CHOKE_IFACE} root netem ${netem_args}" >/dev/null 2>&1; then
            log "apply_netem: tc replace failed on $c (args=${netem_args})"
            rc=1
        fi
    done
    [ "$rc" = "0" ] && NETEM_ACTIVE=1
    return "$rc"
}

# Remove any netem qdisc we installed.  Safe to call even if nothing is
# currently applied; errors from `tc qdisc del` on an empty root are
# silently swallowed.  Called from the EXIT trap.
clear_netem() {
    local containers
    case "${TOPOLOGY:-}" in
        multimaster-failover|multimaster-hothot)
            containers="$MASTERS"
            ;;
        *)
            containers="$CHOKE_CONTAINER"
            ;;
    esac
    local c
    for c in $containers; do
        docker exec "$c" sh -c "tc qdisc del dev ${CHOKE_IFACE} root 2>/dev/null" >/dev/null 2>&1 || true
    done
    NETEM_ACTIVE=0
}

# Try to install iptables inside a minion container.  Returns 0 if the
# iptables binary is present (either pre-installed or newly installed).
ensure_iptables_in_minion() {
    local m="$1"
    if docker exec "$m" sh -c 'command -v iptables >/dev/null 2>&1'; then
        return 0
    fi
    docker exec "$m" sh -c '
        (command -v apt-get >/dev/null 2>&1 \
            && apt-get update -qq >/dev/null 2>&1 \
            && apt-get install -y --no-install-recommends iptables >/dev/null 2>&1) \
        || (command -v apk >/dev/null 2>&1 \
            && apk add --no-cache iptables >/dev/null 2>&1) \
        || (command -v dnf >/dev/null 2>&1 \
            && dnf install -y iptables >/dev/null 2>&1) \
        || (command -v yum >/dev/null 2>&1 \
            && yum install -y iptables >/dev/null 2>&1) \
        || true
    ' >/dev/null 2>&1 || true
    docker exec "$m" sh -c 'command -v iptables >/dev/null 2>&1'
}

# Cleanup in case we exit mid-phase.  Netem cleanup is the critical one;
# iptables + /etc/hosts + docker-pause each phase cleans up its own state
# if we reach the end of its block.  The hooks below handle the case where
# we die before that.
on_exit() {
    local ec=$?
    # Netem: safe to attempt unconditionally; it no-ops when nothing applied.
    if [ "$NETEM_AVAILABLE" = "1" ] || [ "$NETEM_ACTIVE" = "1" ]; then
        clear_netem
    fi
    # Best-effort unpause in case phase 6 died mid-hold.
    for m in ${MASTERS:-}; do
        docker unpause "$m" >/dev/null 2>&1 || true
    done
    # Best-effort iptables flush (phase 5) for every minion we might have
    # touched.  The -D command is idempotent-ish: it fails if the rule isn't
    # there, which is fine.
    for m in ${MINION_CONTAINERS:-}; do
        docker exec "$m" sh -c "
            iptables -D OUTPUT -p tcp --dport ${MASTER_RET_PORT} -j REJECT --reject-with tcp-reset 2>/dev/null || true
        " >/dev/null 2>&1 || true
    done
    # Best-effort /etc/hosts restore (phase 7): if a *.hosts.bak file is
    # sitting in $SCENARIO_WORKDIR we drop it back in.  Each backup is
    # named <container>.hosts.bak.
    for m in ${MINION_CONTAINERS:-}; do
        local bak="${SCENARIO_WORKDIR}/${m}.hosts.bak"
        if [ -f "$bak" ]; then
            docker cp "$bak" "${m}:/etc/hosts" >/dev/null 2>&1 || true
            rm -f "$bak"
        fi
    done
    exit "$ec"
}
trap on_exit EXIT INT TERM

# -------------------------------------------------------------------------
# Phase runner for netem phases.  Takes a label and the netem argument
# string.  Handles the sample-before / apply / hold / clear / assert
# sequence and records setup_error on failure to apply.
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
    if ! apply_netem "$netem_args"; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "tc qdisc replace failed"
        clear_netem
        return 0
    fi
    sleep "$PHASE_DURATION_SEC"
    clear_netem
    assert_reconnect "$label" "$PHASE_DURATION_SEC" "$fd_before" "$rss_before" "netem ${netem_args}" || true
}

# -------------------------------------------------------------------------
# Main battery
# -------------------------------------------------------------------------
log "network_faults scenario starting topology=${TOPOLOGY} choke=${CHOKE_CONTAINER} iface=${CHOKE_IFACE}"
ensure_tc || true

# Phase 1: latency
run_netem_phase "network_latency" "delay 200ms 50ms distribution normal"

# Phase 2: packet loss 10%
run_netem_phase "network_loss_10" "loss 10%"

# Phase 3: jitter + loss combined
run_netem_phase "network_jitter_loss" "delay 100ms 40ms distribution normal loss 5%"

# Phase 4: full partition (loss 100%)
run_netem_phase "network_partition_full" "loss 100%"

# ---------------------------------------------------------------
# Phase 5: TCP reset injection on each minion's OUTPUT dport 44506
# ---------------------------------------------------------------
{
    label="network_tcp_reset"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: iptables REJECT --reject-with tcp-reset dport ${MASTER_RET_PORT} for ${PHASE_DURATION_SEC}s"

    # Try to ensure iptables is available in every minion.  If any minion
    # can't get iptables (e.g. compose didn't grant NET_ADMIN), mark
    # setup_error for the whole phase -- partial coverage gives misleading
    # reconnect behavior.
    setup_failed=""
    for m in $MINION_CONTAINERS; do
        if ! ensure_iptables_in_minion "$m"; then
            setup_failed="$setup_failed $m"
        fi
    done

    if [ -n "$setup_failed" ]; then
        log "PHASE ${label}: iptables unavailable in${setup_failed} -- skipping"
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "iptables unavailable in${setup_failed}"
    else
        applied=""
        apply_failed=0
        for m in $MINION_CONTAINERS; do
            if docker exec "$m" sh -c "
                iptables -I OUTPUT -p tcp --dport ${MASTER_RET_PORT} -j REJECT --reject-with tcp-reset
            " >/dev/null 2>&1; then
                applied="$applied $m"
            else
                log "PHASE ${label}: iptables -I failed on $m (NET_ADMIN missing?)"
                apply_failed=1
            fi
        done

        if [ "$apply_failed" = "1" ] && [ -z "$applied" ]; then
            record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
                "iptables -I OUTPUT rejected on all minions (missing NET_ADMIN?)"
        else
            sleep "$PHASE_DURATION_SEC"
            for m in $applied; do
                docker exec "$m" sh -c "
                    iptables -D OUTPUT -p tcp --dport ${MASTER_RET_PORT} -j REJECT --reject-with tcp-reset 2>/dev/null || true
                " >/dev/null 2>&1 || true
            done
            assert_reconnect "$label" "$PHASE_DURATION_SEC" "$fd_before" "$rss_before" \
                "iptables REJECT tcp-reset dport ${MASTER_RET_PORT}" || true
        fi
    fi
    unset label fd_before rss_before setup_failed applied apply_failed m
}

# ---------------------------------------------------------------
# Phase 6: full blackhole via container pause of $PRIMARY_MASTER
# ---------------------------------------------------------------
{
    label="network_pause_master"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: docker pause ${PRIMARY_MASTER} for ${PHASE_DURATION_SEC}s"
    if ! docker pause "$PRIMARY_MASTER" >/dev/null 2>&1; then
        log "PHASE ${label}: docker pause failed"
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "docker pause $PRIMARY_MASTER failed"
    else
        sleep "$PHASE_DURATION_SEC"
        docker unpause "$PRIMARY_MASTER" >/dev/null 2>&1 || true
        assert_reconnect "$label" "$PHASE_DURATION_SEC" "$fd_before" "$rss_before" \
            "docker pause ${PRIMARY_MASTER}" || true
    fi
    unset label fd_before rss_before
}

# ---------------------------------------------------------------
# Phase 7: DNS-level flap via /etc/hosts rewrite.  Skipped on single.
# ---------------------------------------------------------------
{
    label="network_dns_flap"
    case "${TOPOLOGY:-}" in
        single)
            log "PHASE ${label}: skipped (single topology has no DNS indirection)"
            record_result "$label" "skipped_for_topology" "-1" "0" "" "0" "0" "0" \
                "skipped_for_topology: single uses docker embedded DNS for salt-master"
            ;;
        *)
            read -r fd_before rss_before < <(sample_all_minions)
            log "PHASE ${label}: poisoning /etc/hosts for ${PHASE_DURATION_SEC}s"

            setup_failed=""
            backed_up=""
            for m in $MINION_CONTAINERS; do
                bak="${SCENARIO_WORKDIR}/${m}.hosts.bak"
                if docker cp "${m}:/etc/hosts" "$bak" >/dev/null 2>&1; then
                    backed_up="$backed_up $m"
                else
                    setup_failed="$setup_failed $m"
                fi
            done

            if [ -n "$setup_failed" ]; then
                log "PHASE ${label}: hosts backup failed in${setup_failed} -- skipping"
                record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
                    "unable to read /etc/hosts in${setup_failed}"
                # Restore anything we did back up, defensively.
                for m in $backed_up; do
                    docker cp "${SCENARIO_WORKDIR}/${m}.hosts.bak" "${m}:/etc/hosts" >/dev/null 2>&1 || true
                    rm -f "${SCENARIO_WORKDIR}/${m}.hosts.bak"
                done
            else
                # Build the poisoned hosts file: original contents + a
                # 127.0.0.1 entry for every master hostname (short + any
                # relevant alias).  Appending is enough because the resolver
                # scans top-down but with multiple entries for the same
                # name the FIRST match wins; for safety we also strip any
                # pre-existing lines mentioning master hostnames.
                poison_names=""
                for mstr in $MASTERS; do
                    # Derive the "short" hostname cluster3 masters resolve
                    # as from inside the compose network.  c3-salt-master-1
                    # is reachable as both the container name and its
                    # compose-service name "salt-master-1".
                    short="${mstr#c3-}"
                    short="${short#mm-}"
                    poison_names="$poison_names $mstr $short"
                    # haproxy VIP (cluster3) also gets poisoned so minions
                    # that target the VIP can't resolve it either.
                    if [ "${TOPOLOGY}" = "cluster3" ]; then
                        poison_names="$poison_names c3-salt-haproxy salt-haproxy"
                    fi
                done

                poison_apply_failed=""
                for m in $MINION_CONTAINERS; do
                    bak="${SCENARIO_WORKDIR}/${m}.hosts.bak"
                    new="${SCENARIO_WORKDIR}/${m}.hosts.new"
                    # Strip any existing master-hostname lines from the
                    # backup, then append 127.0.0.1 for each poison name.
                    python3 - "$bak" "$new" $poison_names <<'PY' || true
import sys
src, dst = sys.argv[1], sys.argv[2]
names = set(sys.argv[3:])
with open(src) as f:
    lines = f.readlines()
out = []
for ln in lines:
    stripped = ln.strip()
    if not stripped or stripped.startswith('#'):
        out.append(ln)
        continue
    parts = stripped.split()
    # /etc/hosts line: ip host [aliases...]
    if any(p in names for p in parts[1:]):
        continue
    out.append(ln)
# Append poison entries, one per line, 127.0.0.1 -> each name.
for n in sorted(names):
    out.append(f"127.0.0.1\t{n}\n")
with open(dst, 'w') as f:
    f.writelines(out)
PY
                    if [ ! -s "$new" ]; then
                        poison_apply_failed="$poison_apply_failed $m"
                        continue
                    fi
                    if ! docker cp "$new" "${m}:/etc/hosts" >/dev/null 2>&1; then
                        poison_apply_failed="$poison_apply_failed $m"
                    fi
                    rm -f "$new"
                done

                if [ -n "$poison_apply_failed" ]; then
                    log "PHASE ${label}: hosts poison failed in${poison_apply_failed} -- restoring and skipping"
                    for m in $MINION_CONTAINERS; do
                        bak="${SCENARIO_WORKDIR}/${m}.hosts.bak"
                        [ -f "$bak" ] && docker cp "$bak" "${m}:/etc/hosts" >/dev/null 2>&1 || true
                        rm -f "$bak"
                    done
                    record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
                        "unable to write /etc/hosts in${poison_apply_failed}"
                else
                    sleep "$PHASE_DURATION_SEC"
                    for m in $MINION_CONTAINERS; do
                        bak="${SCENARIO_WORKDIR}/${m}.hosts.bak"
                        docker cp "$bak" "${m}:/etc/hosts" >/dev/null 2>&1 || true
                        rm -f "$bak"
                    done
                    assert_reconnect "$label" "$PHASE_DURATION_SEC" "$fd_before" "$rss_before" \
                        "/etc/hosts poisoned with 127.0.0.1 for master hostnames" || true
                fi
            fi
            unset fd_before rss_before setup_failed backed_up poison_names \
                  poison_apply_failed bak new short mstr m
            ;;
    esac
    unset label
}

log "network_faults scenario complete; results in ${RESULTS_FILE}"
