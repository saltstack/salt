#!/usr/bin/env bash
#
# Salt resiliency test orchestrator.
#
# Order of operations (mirrors tests/monitoring/stress_test.sh's role in
# the nightly-stress-test.yml workflow, but scaled across topologies):
#
#   1. Resolve $TOPOLOGY -> compose files + container identifiers via
#      lib/common.sh::load_topology.
#   2. ``docker compose up -d --build`` the topology.
#   3. Topology-specific fd_exporter startup (cluster3 + multimaster
#      launch exporters inline; the "single" topology inherits them
#      from tests/monitoring/stress_test.sh's compose stack).
#   4. ``wait_initial_auth 300``; abort with exit 2 if initial auth
#      does not stabilize within 5 minutes (setup error, not a
#      resiliency finding).
#   5. Launch the background workload (``./workload.sh``) under its
#      own process group so the orchestrator can SIGTERM the whole
#      tree at teardown.
#   6. Run each scenario script in $SCENARIOS as an independent
#      subprocess.  A nonzero exit from any one scenario is recorded
#      but does NOT abort the suite -- the per-scenario verdict is
#      in results.jsonl and the analyzer is the single source of truth.
#   7. Kill the workload process group; wait for it to drain.
#   8. Pause 30s so prometheus scrapes the quiescent state (same
#      reasoning as tests/monitoring/nightly-stress-test.yml's
#      "sleep 30" before analyze_stats.py).
#   9. ``docker compose stop prometheus`` (flush TSDB), tar up the
#      prometheus_data directory for the topology.
#  10. On any failure path, snapshot ``docker compose logs`` so
#      post-mortem is possible without the containers still running.
#  11. Invoke analyze_resiliency.py; its exit code is the suite's
#      exit code.
#
# Env contract:
#   TOPOLOGY           required: single|cluster3|multimaster-failover
#                               |multimaster-hothot
#   SCENARIOS          optional: space-separated subset of
#                                "master_restart network minion_churn"
#                                (default: all three)
#   RESILIENCY_WORKDIR optional: results + logs destination
#                                (default: results/<utc timestamp>)
#   PROMETHEUS_URL     optional: analyzer prometheus endpoint
#                                (default: http://127.0.0.1:19090)
#
# Exit codes:
#   0  all scenarios recovered AND no prometheus-side leaks
#   1  at least one scenario failed OR a leak was detected
#   2  setup error (initial auth never stabilized, compose up failed,
#      or prometheus was unreachable in CI)

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -z "${TOPOLOGY:-}" ]; then
    printf 'run_resiliency: TOPOLOGY is required (single|cluster3|multimaster-failover|multimaster-hothot)\n' >&2
    exit 2
fi

# shellcheck source=lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

load_topology

: "${SCENARIOS:=baseline master_restart network_faults minion_churn signal_pause resource_pressure disk_faults clock_skew salt_ops netem_advanced fileserver_orch cluster_faults master_marathon}"
# Per-topology prometheus host port.  The multimaster stack publishes
# on :19091 to avoid collision with cluster3's :19090 (see
# compose/multimaster/docker-compose.yml).  Caller can override with
# PROMETHEUS_URL=... to force a specific endpoint.
case "${PROMETHEUS_URL:-}" in
    "")
        case "$TOPOLOGY" in
            multimaster-*) PROMETHEUS_URL="http://127.0.0.1:19091" ;;
            *)             PROMETHEUS_URL="http://127.0.0.1:19090" ;;
        esac
        ;;
esac
: "${WORKLOAD_SCRIPT:=${SCRIPT_DIR}/workload.sh}"
: "${QUIESCE_SEC:=30}"

export PROMETHEUS_URL

WORKLOAD_PID=""
WORKLOAD_PGID=""
COMPOSE_LOGS_CAPTURED=0

compose() {
    # shellcheck disable=SC2086  # COMPOSE_FILES is intentionally word-split
    docker compose $COMPOSE_FILES -p "$COMPOSE_PROJECT" "$@"
}

snapshot_logs() {
    # Idempotent: only writes compose.log once.
    if [ "$COMPOSE_LOGS_CAPTURED" = "1" ]; then
        return 0
    fi
    COMPOSE_LOGS_CAPTURED=1
    log "snapshotting docker compose logs -> ${RESILIENCY_WORKDIR}/compose.log"
    # Attempt three sources of context; concatenate them to the log so a
    # timeout during ``docker compose up --build`` (before any service
    # container exists) still leaves a breadcrumb trail.
    {
        printf '==== docker compose ps ====\n'
        compose ps 2>&1 || true
        printf '\n==== docker compose logs ====\n'
        compose logs --no-color 2>&1 || true
        printf '\n==== docker ps -a (project=%s) ====\n' "$COMPOSE_PROJECT"
        docker ps -a --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" 2>&1 || true
    } > "${RESILIENCY_WORKDIR}/compose.log" 2>&1 || true
}

kill_workload() {
    # Best-effort: the workload may never have started, may have exited,
    # or may already be gone.  Each branch tolerates the previous one
    # having succeeded.
    if [ -n "$WORKLOAD_PGID" ]; then
        log "stopping workload pgid=${WORKLOAD_PGID}"
        kill -TERM -"$WORKLOAD_PGID" 2>/dev/null || true
    fi
    if [ -n "$WORKLOAD_PID" ]; then
        wait "$WORKLOAD_PID" 2>/dev/null || true
    fi
}

on_exit() {
    local rc=$?
    # Always try to snapshot logs on nonzero exit so a crashed master
    # or OOM kill is diagnosable after the fact.  Also snapshot on a
    # SIGTERM-shaped exit (124=timeout, 143=term, 130=int) so an outer
    # ``timeout 1h`` wrapper still leaves a breadcrumb.
    if [ "$rc" -ne 0 ] || [ "$rc" = "124" ] || [ "$rc" = "130" ] || [ "$rc" = "143" ]; then
        snapshot_logs
    fi
    kill_workload
    return "$rc"
}
# Handle TERM/INT explicitly so an outer ``timeout`` wrapper's SIGTERM
# triggers log capture before the shell exits (bash only runs EXIT trap
# for signals already trapped, which TERM is not by default).
trap 'exit 143' TERM
trap 'exit 130' INT
trap on_exit EXIT

# --------------------------------------------------------------------------
# Resolve prometheus bind-mount source per topology.
# --------------------------------------------------------------------------
repo_root="$(cd "${SCRIPT_DIR}/../.." && pwd)"
case "$TOPOLOGY" in
    single)
        PROM_DATA_DIR="${repo_root}/tests/resiliency/compose/single/prometheus_data"
        ;;
    cluster3)
        PROM_DATA_DIR="${repo_root}/tests/monitoring/cluster-3node/prometheus_data"
        ;;
    cluster5)
        PROM_DATA_DIR="${repo_root}/tests/monitoring/cluster-5node/prometheus_data"
        ;;
    multimaster-failover|multimaster-hothot)
        PROM_DATA_DIR="${repo_root}/tests/resiliency/compose/multimaster/prometheus_data"
        ;;
    syndic)
        PROM_DATA_DIR="${repo_root}/tests/resiliency/compose/syndic/prometheus_data"
        ;;
    *)
        # load_topology would have already rejected an unknown topology,
        # but be explicit for grep-ability.
        printf 'run_resiliency: no prometheus_data path for TOPOLOGY=%q\n' "$TOPOLOGY" >&2
        exit 2
        ;;
esac

# Pre-create prometheus_data with nobody:nogroup ownership.  Same
# rationale as nightly-stress-test.yml's mkdir step: prometheus runs as
# uid 65534 inside the container and will fail with permission denied
# on an auto-created root-owned bind-mount source.
if [ ! -d "$PROM_DATA_DIR" ]; then
    mkdir -p "$PROM_DATA_DIR"
    # Best-effort chown; local dev without sudo is fine because the
    # directory doesn't yet exist and compose will just reuse it.
    chown 65534:65534 "$PROM_DATA_DIR" 2>/dev/null \
        || sudo chown 65534:65534 "$PROM_DATA_DIR" 2>/dev/null \
        || true
fi

# --------------------------------------------------------------------------
# Step 2: compose up
# --------------------------------------------------------------------------
log "compose up for TOPOLOGY=${TOPOLOGY} (project=${COMPOSE_PROJECT})"
if ! compose up -d --build; then
    log "compose up failed"
    snapshot_logs
    exit 2
fi

# --------------------------------------------------------------------------
# Step 3: topology-specific exporter startup
# --------------------------------------------------------------------------
case "$TOPOLOGY" in
    cluster3)
        log "launching cluster3 fd_exporters"
        if ! "${SCRIPT_DIR}/compose/cluster3/start_exporters.sh"; then
            log "start_exporters.sh returned nonzero; continuing (exporters may still be partial)"
        fi
        ;;
    multimaster-failover|multimaster-hothot)
        log "launching multimaster fd_exporters"
        for m in $MASTERS; do
            # -d = detached; the exporter is bind-mounted into the master
            # at /srv/fd_exporter.py by compose/multimaster/docker-compose.yml.
            docker exec -d "$m" python3 /srv/fd_exporter.py \
                || log "fd_exporter launch failed in $m (continuing)"
        done
        ;;
    single)
        log "launching single-topology fd_exporter"
        if ! "${SCRIPT_DIR}/compose/single/start_exporters.sh"; then
            log "start_exporters.sh returned nonzero; continuing (exporter may be unavailable)"
        fi
        ;;
    cluster5)
        log "launching cluster5 fd_exporters"
        if ! "${SCRIPT_DIR}/compose/cluster5/start_exporters.sh"; then
            log "start_exporters.sh returned nonzero; continuing (exporters may still be partial)"
        fi
        ;;
    syndic)
        log "launching syndic fd_exporters"
        if ! "${SCRIPT_DIR}/compose/syndic/start_exporters.sh"; then
            log "start_exporters.sh returned nonzero; continuing (exporter may be unavailable)"
        fi
        ;;
esac

# --------------------------------------------------------------------------
# Step 4: wait for initial auth
# --------------------------------------------------------------------------
log "waiting up to 300s for initial auth of: ${MINION_IDS}"
if ! wait_initial_auth 300; then
    log "initial auth never stabilized; aborting as setup error"
    # Synthesize a results row so the analyzer surfaces this setup
    # failure.  Without it, results.jsonl is empty and the analyzer
    # exits 2 ("data missing") -- same exit code but with no hint as
    # to WHY, which is the exact invisible-failure mode the suite is
    # supposed to eliminate.
    record_result "topology_setup" "setup_error" "-1" "0" "${MINION_IDS}" "0" "0" "0" \
        "wait_initial_auth timed out after 300s; minion keys not visible on any \$MASTERS member"
    snapshot_logs
    exit 2
fi
log "initial auth OK"

# --------------------------------------------------------------------------
# Step 5: start the workload under its own process group
# --------------------------------------------------------------------------
if [ -x "$WORKLOAD_SCRIPT" ]; then
    log "starting workload: $WORKLOAD_SCRIPT"
    # ``setsid`` puts the workload in a new session so its pgid == pid
    # and we can SIGTERM the whole tree without affecting the
    # orchestrator.  Fall back to plain backgrounding if setsid is
    # unavailable (unlikely on Linux CI runners).
    if command -v setsid >/dev/null 2>&1; then
        setsid "$WORKLOAD_SCRIPT" </dev/null \
            > "${RESILIENCY_WORKDIR}/workload.log" 2>&1 &
    else
        "$WORKLOAD_SCRIPT" </dev/null \
            > "${RESILIENCY_WORKDIR}/workload.log" 2>&1 &
    fi
    WORKLOAD_PID=$!
    # The pgid equals the pid when setsid created a new session.
    WORKLOAD_PGID=$(ps -o pgid= -p "$WORKLOAD_PID" 2>/dev/null | tr -d '[:space:]')
    : "${WORKLOAD_PGID:=$WORKLOAD_PID}"
    export WORKLOAD_PID WORKLOAD_PGID
    log "workload pid=${WORKLOAD_PID} pgid=${WORKLOAD_PGID}"
else
    log "no executable ${WORKLOAD_SCRIPT}; proceeding without background workload"
fi

# --------------------------------------------------------------------------
# Step 6: run scenarios.  Each in an independent subshell so a ``set -e``
# or ``exit N`` inside the scenario can never terminate the orchestrator.
# --------------------------------------------------------------------------

scenario_enabled() {
    local name="$1"
    for s in $SCENARIOS; do
        if [ "$s" = "$name" ]; then
            return 0
        fi
    done
    return 1
}

run_scenario() {
    local name="$1"
    local script="${SCRIPT_DIR}/scenarios/${name}.sh"
    if ! scenario_enabled "$name"; then
        log "scenario '${name}' disabled (not in \$SCENARIOS), skipping"
        return 0
    fi
    if [ ! -x "$script" ]; then
        log "scenario '${name}' script missing or not executable: ${script}"
        # Record a setup_error row so the analyzer surfaces it instead
        # of silently passing.
        record_result "${name}_not_implemented" "setup_error" "-1" "0" "" "0" "0" "0" \
            "missing script: ${script}"
        return 0
    fi
    log "===== running scenario: ${name} ====="
    local scenario_log="${RESILIENCY_WORKDIR}/${name}.log"
    # Subshell + explicit pipefail so a scenario that crashes before
    # its first ``record_result`` doesn't get silently masked by
    # ``tee``'s exit 0.  Without this the orchestrator cannot tell
    # "scenario segfaulted recording nothing" from "scenario ran and
    # all phases passed" -- exactly the invisible-failure mode a
    # resiliency harness is supposed to eliminate.
    local scenario_rc=0
    set -o pipefail
    ( "$script" 2>&1 ) | tee "$scenario_log" || scenario_rc=$?
    set +o pipefail
    if [ "$scenario_rc" -ne 0 ]; then
        # Scenarios signal "a phase failed" with exit 1 but still emit
        # per-phase ``record_result`` rows, which the analyzer picks up.
        # Any other nonzero exit = an uncaught crash BEFORE the first
        # row was written; synthesise one here so the verdict is honest.
        local rows_for_scenario
        rows_for_scenario=$(grep -c "\"scenario\":\s*\"${name}" "$RESULTS_FILE" 2>/dev/null || echo 0)
        if [ "${rows_for_scenario:-0}" -eq 0 ]; then
            record_result "${name}_crashed" "setup_error" "-1" "0" "" "0" "0" "0" \
                "scenario script exited ${scenario_rc} without emitting any rows"
        fi
    fi
    log "===== scenario ${name} complete (rc=${scenario_rc}) ====="
}

# Order: baseline first so its "no-fault" sanity establishes a clean
# reference for the fault-injection phases.  Fault scenarios after,
# grouped loosely by blast radius (restart > network > resource >
# pressure > disk > clock > salt-ops > cluster-specific).
run_scenario baseline
run_scenario master_restart
run_scenario network_faults
run_scenario minion_churn
run_scenario signal_pause
run_scenario resource_pressure
run_scenario disk_faults
run_scenario clock_skew
run_scenario salt_ops
run_scenario netem_advanced
run_scenario fileserver_orch
run_scenario cluster_faults
# master_marathon is multi-hour; it's a no-op unless MARATHON_ENABLED=1
# (the script itself emits skip rows and exits cleanly when disabled).
# Keeping it in the default list means the accounting stays consistent
# across nightly runs and MARATHON-opt-in weeklies.
run_scenario master_marathon

# --------------------------------------------------------------------------
# Step 7: stop the workload
# --------------------------------------------------------------------------
kill_workload
WORKLOAD_PID=""
WORKLOAD_PGID=""

# --------------------------------------------------------------------------
# Step 8: quiescence pause so prometheus has fresh samples when the
# analyzer queries deriv() over the trailing 30m window.
# --------------------------------------------------------------------------
log "quiescing for ${QUIESCE_SEC}s before prometheus snapshot"
sleep "$QUIESCE_SEC"

# --------------------------------------------------------------------------
# Step 9: snapshot prometheus TSDB.  Stop first so the write-ahead log is
# flushed; the analyzer has already been run after this point would be
# too late because TSDB is sealed.  Instead we run the analyzer BEFORE
# stopping prometheus (step 11 below), then snapshot.
# --------------------------------------------------------------------------

# Snapshot compose logs for every run (success or failure); useful for
# post-mortem even on a green run and cheap on disk.
snapshot_logs

# --------------------------------------------------------------------------
# Step 11: analyze.  Run BEFORE stopping prometheus so the analyzer can
# still query the HTTP API.
# --------------------------------------------------------------------------
ANALYZE_RC=0
log "running analyzer: results=${RESULTS_FILE} prometheus=${PROMETHEUS_URL}"
python3 "${SCRIPT_DIR}/analyze_resiliency.py" \
    --results "$RESULTS_FILE" \
    --topology "$TOPOLOGY" \
    --prometheus-url "$PROMETHEUS_URL" \
    | tee "${RESILIENCY_WORKDIR}/analysis.txt"
ANALYZE_RC=${PIPESTATUS[0]}
log "analyzer exit code: ${ANALYZE_RC}"

# --------------------------------------------------------------------------
# Step 9 (continued): now that the analyzer has queried the TSDB, stop
# prometheus so the data on disk is complete, and tar it up.
# --------------------------------------------------------------------------
log "stopping prometheus to flush TSDB"
compose stop prometheus || true

if [ -d "$PROM_DATA_DIR" ]; then
    log "snapshotting prometheus_data from ${PROM_DATA_DIR}"
    # ``tar`` is invoked via sudo only when the data dir isn't owned by us,
    # which is the normal CI case (uid 65534 inside the container).
    if tar -czf "${RESILIENCY_WORKDIR}/prometheus-data.tar.gz" \
            -C "$(dirname "$PROM_DATA_DIR")" "$(basename "$PROM_DATA_DIR")" 2>/dev/null; then
        :
    elif sudo tar -czf "${RESILIENCY_WORKDIR}/prometheus-data.tar.gz" \
            -C "$(dirname "$PROM_DATA_DIR")" "$(basename "$PROM_DATA_DIR")"; then
        :
    else
        log "prometheus_data snapshot failed; continuing"
    fi
else
    log "prometheus_data dir not found at ${PROM_DATA_DIR}; skipping tar"
fi

log "run complete; results=${RESILIENCY_WORKDIR}"
exit "$ANALYZE_RC"
