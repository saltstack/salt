#!/usr/bin/env bash
# Continuous cluster monitor. Samples every 30s and emits a one-line summary
# to stdout per sample. Flags anomalies with [ALERT] prefix.
#
# Columns:
#   ts  elapsed  leader  term  <per-master state>  errs  pings  mem_MB_total  cpu%_total

set -uo pipefail

COMPOSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$COMPOSE_DIR"

MASTERS=(c5-salt-master-1 c5-salt-master-2 c5-salt-master-3 c5-salt-master-4 c5-salt-master-5)
MINIONS=(c5-salt-minion-1 c5-salt-minion-2 c5-salt-minion-3 c5-salt-minion-4 c5-salt-minion-5)

START=$(date +%s)

# Per-master tallies carried across samples so we can detect *new* events.
declare -A prev_cand   # BECOMING CANDIDATE count
declare -A prev_leader # BECOMING LEADER count
declare -A prev_term   # last term seen
declare -A prev_errs   # ERROR/CRITICAL line count

for m in "${MASTERS[@]}"; do
    prev_cand[$m]=0
    prev_leader[$m]=0
    prev_term[$m]=0
    prev_errs[$m]=0
done

printf 'ts\telapsed_s\tleader\tterm\tcands_total\tnew_errs\tping_ok\tping_miss\tmem_MB_total\tnotes\n'

while true; do
    now_ts=$(date -Iseconds)
    elapsed=$(( $(date +%s) - START ))

    leader=""
    max_term=0
    cands_total=0
    leader_total=0
    new_errs=0
    notes=""

    for m in "${MASTERS[@]}"; do
        logs=$(docker logs "$m" 2>&1 || true)
        # Latest term observed on this master
        term=$(printf '%s' "$logs" | grep -oE "for term [0-9]+" | awk '{print $3}' | sort -n | tail -1)
        term=${term:-0}
        if (( term > max_term )); then max_term=$term; fi

        # Latest BECOMING state
        last_state=$(printf '%s' "$logs" | grep -oE "BECOMING (LEADER|CANDIDATE|FOLLOWER)" | tail -1 | awk '{print $2}')
        if [[ "$last_state" == "LEADER" ]]; then
            leader="$m"
        fi

        # Count transitions and errors
        cands=$(printf '%s' "$logs" | grep -c "BECOMING CANDIDATE" || true)
        leaders=$(printf '%s' "$logs" | grep -c "BECOMING LEADER" || true)
        errs=$(printf '%s' "$logs" | grep -cE "^\[(ERROR|CRITICAL)" || true)

        cands_total=$(( cands_total + cands ))
        leader_total=$(( leader_total + leaders ))

        # Flag deltas
        if (( cands > prev_cand[$m] )); then
            notes+="${notes:+;}${m}:+$((cands - prev_cand[$m]))cand"
        fi
        if (( leaders > prev_leader[$m] )); then
            notes+="${notes:+;}${m}:+$((leaders - prev_leader[$m]))leader"
        fi
        if (( term > prev_term[$m] )) && (( prev_term[$m] > 0 )); then
            notes+="${notes:+;}${m}:term${prev_term[$m]}->${term}"
        fi
        if (( errs > prev_errs[$m] )); then
            delta=$((errs - prev_errs[$m]))
            new_errs=$((new_errs + delta))
        fi

        prev_cand[$m]=$cands
        prev_leader[$m]=$leaders
        prev_term[$m]=$term
        prev_errs[$m]=$errs
    done

    # Ping check: use the leader if known, else master-1
    src="${leader:-c5-salt-master-1}"
    ping_json=$(docker exec "$src" salt '*' test.ping --output=json --timeout=10 2>/dev/null || true)
    ping_ok=$(printf '%s' "$ping_json" | grep -c '": true' || true)
    ping_miss=$(printf '%s' "$ping_json" | grep -c "did not return" || true)
    if (( ping_miss > 0 )); then
        notes+="${notes:+;}ping_miss=$ping_miss"
    fi

    # Memory total across containers (MB)
    mem_mb=$(docker stats --no-stream --format '{{.MemUsage}}' "${MASTERS[@]}" "${MINIONS[@]}" 2>/dev/null \
        | awk -F'[ /]' '{
            v=$1; unit=$2;
            if (unit=="GiB") v*=1024;
            else if (unit=="MiB") v*=1;
            else if (unit=="KiB") v/=1024;
            else if (unit=="B")   v/=1048576;
            sum += v
        } END { printf "%.0f", sum }')

    [[ -z "$notes" ]] && notes="-"

    line=$(printf '%s\t%d\t%s\t%d\t%d\t%d\t%d\t%d\t%s\t%s\n' \
        "$now_ts" "$elapsed" "${leader:-NONE}" "$max_term" \
        "$cands_total" "$new_errs" "$ping_ok" "$ping_miss" "$mem_mb" "$notes")

    # Flag alerts when something interesting happens
    if [[ "$notes" != "-" ]] || [[ -z "$leader" ]] || (( ping_miss > 0 )) || (( max_term > 1 )); then
        printf '[ALERT] %s' "$line"
    else
        printf '%s' "$line"
    fi

    sleep 30
done
