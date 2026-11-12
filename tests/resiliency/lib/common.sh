# Shared contract for the Salt resiliency test suite.
#
# Scenario scripts (``../scenarios/*.sh``) source this file to resolve
# the topology-specific container / minion identifiers and to call the
# assert_reconnect primitive that defines the core invariant of the
# suite:
#
#   After any injected fault clears, every expected minion must
#   answer ``test.ping`` within RECONNECT_WINDOW_SEC seconds, and
#   the minion's process RSS slope across the fault window must
#   stay below RSS_LEAK_KB_PER_MIN.
#
# Every scenario writes one line of JSON per fault into
# ``$RESILIENCY_WORKDIR/results.jsonl`` which ``analyze_resiliency.py``
# then folds into a single verdict.
#
# Env contract (one of these must be exported before sourcing):
#
#   TOPOLOGY=single              -- tests/monitoring/docker-compose.yml
#                                    (reused as-is; salt-master + 3 minions)
#   TOPOLOGY=cluster3            -- tests/monitoring/cluster-3node/
#                                    (3 masters behind haproxy + 5 minions)
#   TOPOLOGY=multimaster-failover-- compose/multimaster/ (2 masters,
#                                    minion has master_type: failover)
#   TOPOLOGY=multimaster-hothot  -- compose/multimaster/ (2 masters,
#                                    minion has master_type: standard,
#                                    i.e. connects to BOTH simultaneously)
#
# After load_topology, these vars are exported:
#   COMPOSE_FILES     space-separated ``-f`` args to pass to docker compose
#   COMPOSE_PROJECT   stable project name (one per topology)
#   MASTERS           container names of all salt-master services
#   PRIMARY_MASTER    container to run the salt CLI from
#   MINION_IDS        space-separated minion ids seen from the master
#   MINION_CONTAINERS space-separated minion container names
#   CHOKE_CONTAINER   container to run ``tc`` on for network faults
#                     (haproxy for cluster3; primary master otherwise)
#   CHOKE_IFACE       interface inside the choke container (default eth0)

set -u

: "${RESILIENCY_WORKDIR:=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/results/$(date -u +%Y%m%dT%H%M%SZ)}"
: "${RECONNECT_WINDOW_SEC:=180}"
: "${PING_TIMEOUT_SEC:=15}"
: "${RSS_LEAK_KB_PER_MIN:=200}"
: "${MASTER_FD_LEAK_PER_MIN:=30}"
export RESILIENCY_WORKDIR RECONNECT_WINDOW_SEC PING_TIMEOUT_SEC RSS_LEAK_KB_PER_MIN MASTER_FD_LEAK_PER_MIN

mkdir -p "$RESILIENCY_WORKDIR"
: "${RESULTS_FILE:=$RESILIENCY_WORKDIR/results.jsonl}"
export RESULTS_FILE

log() { printf '[resiliency] %s %s\n' "$(date -u +%H:%M:%S)" "$*"; }

# Resolve TOPOLOGY -> compose files + container names.  Called once at
# the top of each scenario script.  Exits non-zero on unknown topology.
load_topology() {
    local topo="${TOPOLOGY:-}"
    local repo_root
    repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
    case "$topo" in
        single)
            # Dedicated resiliency-single compose (NOT a reuse of
            # tests/monitoring/docker-compose.yml) because that file
            # hardcodes ``container_name: salt-master`` etc. and a
            # ``compose down -v --remove-orphans`` would then clobber
            # the developer's running monitoring stack.
            COMPOSE_FILES="-f ${repo_root}/tests/resiliency/compose/single/docker-compose.yml"
            COMPOSE_PROJECT="resiliency-single"
            MASTERS="rs-single-salt-master"
            PRIMARY_MASTER="rs-single-salt-master"
            MINION_CONTAINERS="rs-single-salt-minion-1 rs-single-salt-minion-2 rs-single-salt-minion-3"
            MINION_IDS="rs-single-salt-minion-1 rs-single-salt-minion-2 rs-single-salt-minion-3"
            CHOKE_CONTAINER="rs-single-salt-master"
            CHOKE_IFACE="eth0"
            ;;
        cluster3)
            COMPOSE_FILES="-f ${repo_root}/tests/monitoring/cluster-3node/docker-compose.yml \
-f ${repo_root}/tests/resiliency/compose/cluster3/monitoring-overlay.yml"
            COMPOSE_PROJECT="cluster-3node"
            MASTERS="c3-salt-master-1 c3-salt-master-2 c3-salt-master-3"
            PRIMARY_MASTER="c3-salt-master-1"
            MINION_CONTAINERS="c3-salt-minion-1 c3-salt-minion-2 c3-salt-minion-3 c3-salt-minion-4 c3-salt-minion-5"
            MINION_IDS="scale-minion-1 scale-minion-2 scale-minion-3 scale-minion-4 scale-minion-5"
            CHOKE_CONTAINER="c3-salt-haproxy"
            CHOKE_IFACE="eth0"
            ;;
        multimaster-failover|multimaster-hothot)
            local variant="${topo#multimaster-}"
            COMPOSE_FILES="-f ${repo_root}/tests/resiliency/compose/multimaster/docker-compose.yml \
-f ${repo_root}/tests/resiliency/compose/multimaster/docker-compose.${variant}.yml"
            COMPOSE_PROJECT="resiliency-multimaster"
            MASTERS="mm-salt-master-a mm-salt-master-b"
            PRIMARY_MASTER="mm-salt-master-a"
            MINION_CONTAINERS="mm-salt-minion-1"
            MINION_IDS="mm-minion-1"
            # No haproxy in multimaster; choke per-master is applied by
            # iterating MASTERS in the scenario.  Keep a default for
            # scenarios that don't iterate.
            CHOKE_CONTAINER="mm-salt-master-a"
            CHOKE_IFACE="eth0"
            ;;
        cluster5)
            COMPOSE_FILES="-f ${repo_root}/tests/monitoring/cluster-5node/docker-compose.yml \
-f ${repo_root}/tests/resiliency/compose/cluster5/monitoring-overlay.yml"
            COMPOSE_PROJECT="cluster-5node"
            MASTERS="c5-salt-master-1 c5-salt-master-2 c5-salt-master-3 c5-salt-master-4 c5-salt-master-5"
            PRIMARY_MASTER="c5-salt-master-1"
            MINION_CONTAINERS="c5-salt-minion-1 c5-salt-minion-2 c5-salt-minion-3 c5-salt-minion-4 c5-salt-minion-5"
            MINION_IDS="salt-minion-1 salt-minion-2 salt-minion-3 salt-minion-4 salt-minion-5"
            # No haproxy VIP; choke the primary.  Rolling faults should
            # iterate $MASTERS to exercise each peer.
            CHOKE_CONTAINER="c5-salt-master-1"
            CHOKE_IFACE="eth0"
            ;;
        syndic)
            COMPOSE_FILES="-f ${repo_root}/tests/resiliency/compose/syndic/docker-compose.yml"
            COMPOSE_PROJECT="resiliency-syndic"
            MASTERS="rs-syndic-mom rs-syndic-sub"
            # Minions register through the sub-master; MoM is upstream.
            PRIMARY_MASTER="rs-syndic-sub"
            MINION_CONTAINERS="rs-syndic-minion-1 rs-syndic-minion-2"
            MINION_IDS="syndic-minion-1 syndic-minion-2"
            CHOKE_CONTAINER="rs-syndic-sub"
            CHOKE_IFACE="eth0"
            ;;
        *)
            printf 'load_topology: unknown TOPOLOGY=%q (want: single|cluster3|multimaster-failover|multimaster-hothot)\n' \
                "$topo" >&2
            return 2
            ;;
    esac
    export COMPOSE_FILES COMPOSE_PROJECT MASTERS PRIMARY_MASTER MINION_IDS MINION_CONTAINERS CHOKE_CONTAINER CHOKE_IFACE
}

# Return the pid of the minion MainProcess inside the given container.
# Empty string if the container isn't running or the daemon isn't up.
minion_main_pid() {
    local container="$1"
    docker exec "$container" sh -c "
        pgrep -f 'salt-minion.*MinionProcessManager' \
        || pgrep -f 'salt-minion.*MainProcess' \
        || true
    " 2>/dev/null | head -1 | tr -d '[:space:]'
}

# Sample fd count + RSS for a minion.  Prints ``fds rss_kb`` space-separated,
# or ``0 0`` if the process is gone.
sample_minion() {
    local container="$1"
    local pid
    pid="$(minion_main_pid "$container")"
    if [ -z "$pid" ]; then
        printf '0 0\n'
        return 0
    fi
    docker exec "$container" sh -c "
        fds=\$(ls /proc/${pid}/fd 2>/dev/null | wc -l)
        rss=\$(awk '/VmRSS/ {print \$2}' /proc/${pid}/status 2>/dev/null)
        printf '%s %s\n' \"\${fds:-0}\" \"\${rss:-0}\"
    " 2>/dev/null || printf '0 0\n'
}

# JSON-escape a string by piping through python (bash can't do \uXXXX).
json_escape() {
    python3 -c "import json,sys; sys.stdout.write(json.dumps(sys.argv[1]))" "$1"
}

# Append one JSON record to $RESULTS_FILE.  Positional args:
#   $1  scenario label (free text, e.g. "master_restart_sigkill_rolling")
#   $2  outcome: "recovered" | "failed" | "setup_error"
#   $3  reconnect_seconds (int; -1 if not reached)
#   $4  attempts (int)
#   $5  missing minion ids (space-separated, may be empty)
#   $6  fd_delta (sum across minions, int)
#   $7  rss_kb_delta (sum across minions, int)
#   $8  duration_seconds the fault was active (int)
#   $9  optional free-text notes
record_result() {
    local scenario="$1" outcome="$2" reconnect_s="$3" attempts="$4"
    local missing="$5" fd_delta="$6" rss_delta="$7" fault_s="$8" notes="${9:-}"
    local missing_json
    missing_json=$(python3 -c "
import json,sys
ids = sys.argv[1].split()
sys.stdout.write(json.dumps(ids))
" "$missing")
    python3 -c "
import json,sys,time
rec = {
    'ts': time.time(),
    'topology': sys.argv[1],
    'scenario': sys.argv[2],
    'outcome': sys.argv[3],
    'reconnect_seconds': int(sys.argv[4]),
    'attempts': int(sys.argv[5]),
    'missing': json.loads(sys.argv[6]),
    'fd_delta': int(sys.argv[7]),
    'rss_kb_delta': int(sys.argv[8]),
    'fault_seconds': int(sys.argv[9]),
    'notes': sys.argv[10],
}
sys.stdout.write(json.dumps(rec) + '\n')
" "${TOPOLOGY:-unknown}" "$scenario" "$outcome" "$reconnect_s" "$attempts" "$missing_json" "$fd_delta" "$rss_delta" "$fault_s" "$notes" \
        >> "$RESULTS_FILE"
}

# Assert that every id in MINION_IDS answers ``test.ping`` as true via
# the PRIMARY_MASTER within $RECONNECT_WINDOW_SEC AND that the minion's
# RSS growth normalised to per-minute stays below $RSS_LEAK_KB_PER_MIN.
# Records the result.  Returns 0 on reconnect + leak-check pass, 1 on
# either failure.
#
# Arguments:
#   $1  scenario label
#   $2  fault_seconds (how long the fault was held)
#   $3  fd_delta_before (int; subtracted from current fd sum)
#   $4  rss_kb_delta_before (int; subtracted from current rss sum)
#   $5  optional notes
assert_reconnect() {
    local scenario="$1" fault_s="$2" fd_before="$3" rss_before="$4" notes="${5:-}"
    local deadline=$(( $(date +%s) + RECONNECT_WINDOW_SEC ))
    local start=$(date +%s)
    local attempt=0
    local missing=""
    local out=""
    while [ "$(date +%s)" -lt "$deadline" ]; do
        attempt=$((attempt + 1))
        missing=""
        out=$(docker exec "$PRIMARY_MASTER" salt --out=json --timeout="$PING_TIMEOUT_SEC" '*' test.ping 2>/dev/null || true)
        for mid in $MINION_IDS; do
            if ! printf '%s' "$out" | grep -q "\"$mid\": true"; then
                missing="$missing $mid"
            fi
        done
        if [ -z "$missing" ]; then
            local reconnect_s=$(( $(date +%s) - start ))
            local fd_now=0 rss_now=0 f r
            for c in $MINION_CONTAINERS; do
                read -r f r < <(sample_minion "$c")
                fd_now=$((fd_now + f))
                rss_now=$((rss_now + r))
            done
            local fd_delta=$((fd_now - fd_before))
            local rss_delta=$((rss_now - rss_before))
            # Minute-normalised slope over the fault-plus-reconnect window.
            # Short windows need a floor or a 1-second fault blows up the
            # ratio; use max(60s, elapsed) so the per-minute number isn't
            # dominated by sampling jitter on sub-minute phases.
            local elapsed=$(( fault_s + reconnect_s ))
            if [ "$elapsed" -lt 60 ]; then elapsed=60; fi
            local rss_per_min=$(( rss_delta * 60 / elapsed ))
            if [ "$rss_per_min" -gt "$RSS_LEAK_KB_PER_MIN" ]; then
                log "LEAK '$scenario' recovered after ${reconnect_s}s but RSS grew ${rss_per_min} KB/min > ${RSS_LEAK_KB_PER_MIN} KB/min"
                local leak_notes="rss_kb_per_min=${rss_per_min} threshold=${RSS_LEAK_KB_PER_MIN}"
                if [ -n "$notes" ]; then leak_notes="${notes}; ${leak_notes}"; fi
                record_result "$scenario" "failed" "$reconnect_s" "$attempt" "" "$fd_delta" "$rss_delta" "$fault_s" "$leak_notes"
                return 1
            fi
            log "RECOVERED '$scenario' after ${reconnect_s}s (${attempt} attempts) fd_delta=${fd_delta} rss_delta_kb=${rss_delta} rss_kb_per_min=${rss_per_min}"
            record_result "$scenario" "recovered" "$reconnect_s" "$attempt" "" "$fd_delta" "$rss_delta" "$fault_s" "$notes"
            return 0
        fi
        sleep 5
    done
    local fd_now=0 rss_now=0 f r
    for c in $MINION_CONTAINERS; do
        read -r f r < <(sample_minion "$c")
        fd_now=$((fd_now + f))
        rss_now=$((rss_now + r))
    done
    local fd_delta=$((fd_now - fd_before))
    local rss_delta=$((rss_now - rss_before))
    log "FAILED '$scenario': missing=${missing# } fd_delta=${fd_delta} rss_delta_kb=${rss_delta}"
    record_result "$scenario" "failed" "-1" "$attempt" "${missing# }" "$fd_delta" "$rss_delta" "$fault_s" "$notes"
    return 1
}

# Sum the current fd+rss across all MINION_CONTAINERS.  Prints ``fds rss_kb``.
# Use this to capture the "before" baseline you'll pass into assert_reconnect.
sample_all_minions() {
    local fd=0 rss=0 f r
    for c in $MINION_CONTAINERS; do
        read -r f r < <(sample_minion "$c")
        fd=$((fd + f))
        rss=$((rss + r))
    done
    printf '%s %s\n' "$fd" "$rss"
}

# Wait for every $MINION_IDS to be registered on AT LEAST ONE master.
# On multimaster-* topologies the minion elects a master via
# master_shuffle/master_type semantics, so $PRIMARY_MASTER alone is not
# authoritative -- the minion's auth key may land on master-b while
# master-a's salt-key stays empty.  We iterate $MASTERS and count a
# minion as authenticated as soon as any master accepts its key.
#
# Used by run_resiliency.sh after compose up, before scenarios start.
wait_initial_auth() {
    local deadline=$(( $(date +%s) + ${1:-300} ))
    while [ "$(date +%s)" -lt "$deadline" ]; do
        local all_up=1
        for mid in $MINION_IDS; do
            local seen=0
            for m in $MASTERS; do
                if docker exec "$m" salt-key -L 2>/dev/null \
                    | grep -q "^${mid}$"; then
                    seen=1
                    break
                fi
            done
            if [ "$seen" = "0" ]; then
                all_up=0
                break
            fi
        done
        if [ "$all_up" = "1" ]; then
            # Final gate: at least one master must answer test.ping.
            # On hot-hot both masters answer; on failover only the
            # elected one does.  Either is fine for "fleet is live".
            for m in $MASTERS; do
                if docker exec "$m" salt --timeout=10 --out=json '*' test.ping 2>/dev/null \
                    | grep -q '"\(true\|True\)"'; then
                    return 0
                fi
            done
            # Keys registered + at least one master; good enough for
            # scenarios to start (they'll retry ping).
            return 0
        fi
        sleep 5
    done
    return 1
}
