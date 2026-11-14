#!/usr/bin/env bash
# Bring up the 5-master cluster + 5 minions, wait for Raft to converge, and run
# a basic test.ping across the cluster.
#
# Exits non-zero on any failed smoke check. Intended for manual + CI runs.

set -euo pipefail

COMPOSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$COMPOSE_DIR"

MASTERS=(c5-salt-master-1 c5-salt-master-2 c5-salt-master-3 c5-salt-master-4 c5-salt-master-5)
MINIONS=(c5-salt-minion-1 c5-salt-minion-2 c5-salt-minion-3 c5-salt-minion-4 c5-salt-minion-5)

log() { printf '[smoke] %s\n' "$*"; }
fail() { printf '[smoke][FAIL] %s\n' "$*" >&2; exit 1; }

log "bringing stack up (image must be pre-built as cluster-5node-salt:latest)"
docker compose up -d

log "waiting for all 5 master containers to be running"
for m in "${MASTERS[@]}"; do
    for _ in $(seq 1 30); do
        state=$(docker inspect -f '{{.State.Status}}' "$m" 2>/dev/null || echo missing)
        [[ "$state" == running ]] && break
        sleep 1
    done
    [[ "$state" == running ]] || fail "$m not running (state=$state)"
done
log "all masters up"

log "waiting up to 60s for each master's publish socket to be bound"
for m in "${MASTERS[@]}"; do
    for _ in $(seq 1 60); do
        bound=$(docker exec "$m" sh -c "ss -tln 2>/dev/null | grep -c ':44505' || true")
        [[ "$bound" -ge 1 ]] && break
        sleep 1
    done
    bound=$(docker exec "$m" sh -c "ss -tln 2>/dev/null | grep -c ':44505' || true")
    [[ "$bound" -ge 1 ]] || fail "$m publish_port 44505 never bound"
done
log "all masters bound publish_port"

log "waiting up to 90s for a Raft LEADER to be elected"
leader=""
for _ in $(seq 1 90); do
    for m in "${MASTERS[@]}"; do
        n=$(docker logs "$m" 2>&1 | grep -c "BECOMING LEADER" || true)
        if [[ "$n" -ge 1 ]]; then
            leader="$m"
            break 2
        fi
    done
    sleep 1
done
[[ -n "$leader" ]] || fail "no master reached BECOMING LEADER within 90s"
log "observed LEADER: $leader"

log "checking for election storm (CANDIDATE count per master)"
for m in "${MASTERS[@]}"; do
    count=$(docker logs "$m" 2>&1 | grep -c "BECOMING CANDIDATE" || true)
    log "  $m: BECOMING CANDIDATE x$count"
    (( count <= 8 )) || fail "$m: $count CANDIDATE transitions (likely election storm)"
done

log "waiting up to 60s for all 5 minions to appear on the LEADER"
for _ in $(seq 1 60); do
    up=$(docker exec "$leader" salt-run manage.up 2>/dev/null | grep -c '^- salt-minion-' || true)
    [[ "$up" -ge 5 ]] && break
    sleep 2
done
[[ "$up" -ge 5 ]] || fail "only $up/5 minions reachable from $leader"
log "all 5 minions up on leader"

log "letting minion connections settle for 15s"
sleep 15

ping_all() {
    # Return 0 if every minion returned True, else dump output and return 1.
    local src="$1"
    local out
    out=$(docker exec "$src" salt '*' test.ping --output=json 2>/dev/null || true)
    local n_true
    n_true=$(printf '%s' "$out" | grep -c 'true' || true)
    if [[ "$n_true" -eq 5 ]]; then
        return 0
    fi
    printf '%s\n' "$out" >&2
    return 1
}

log "salt '*' test.ping from leader (up to 3 attempts, failover can churn briefly)"
for attempt in 1 2 3; do
    if ping_all "$leader"; then
        log "  attempt $attempt: all 5 responded"
        break
    fi
    log "  attempt $attempt: not all 5 responded, retrying in 10s"
    sleep 10
    [[ "$attempt" -eq 3 ]] && fail "test.ping failed from leader after 3 attempts"
done

log "salt '*' test.ping from a follower (c5-salt-master-2, up to 3 attempts)"
for attempt in 1 2 3; do
    if ping_all c5-salt-master-2; then
        log "  attempt $attempt: all 5 responded"
        break
    fi
    sleep 10
    [[ "$attempt" -eq 3 ]] && fail "test.ping failed from follower after 3 attempts"
done

log "verifying cluster_pki_dir contents are identical across masters"
ref_sum=""
for m in "${MASTERS[@]}"; do
    s=$(docker exec "$m" sh -c "ls -1 /etc/salt/cluster-pki/ | sort | md5sum | awk '{print \$1}'")
    log "  $m: pki dir md5=$s"
    if [[ -z "$ref_sum" ]]; then
        ref_sum="$s"
    elif [[ "$s" != "$ref_sum" ]]; then
        fail "$m has divergent cluster_pki_dir contents"
    fi
done

log "SUCCESS - cluster is up, leader=$leader, all minions responded"
