# Salt resiliency test suite

Black-box resiliency harness that drives a live Salt stack through a
battery of injected faults and asserts recovery + absence of resource
leaks. This complements, and does not replace, the pytest-based
failover / cluster coverage under `tests/pytests/scenarios/`.

## What this is

- A compose-based harness that runs real Salt containers across four
  topologies (single master, 3-master cluster, 2-master failover,
  2-master hot/hot).
- Per-topology scenario batteries (`scenarios/*.sh`) that inject
  faults — process restart, SIGKILL, haproxy kill, network partition,
  minion churn — and call `assert_reconnect` after each fault.
- A prometheus-backed leak detector that fails the run if master
  `salt_master_open_fds` or `salt_master_rss_bytes` are trending up
  across the 30-minute test window (mirrors
  `tests/monitoring/analyze_stats.py`).
- A single machine-readable verdict in `results.jsonl` +
  `analysis.txt` so CI step summaries can quote the exact row that
  failed.

Infra is **reused from `tests/monitoring/`** (compose stacks, Grafana
panels, `fd_exporter.py`, prometheus scrape config) so a nightly
resiliency run looks the same as a nightly stress run from the
operator's dashboard.

## What this is NOT

This suite deliberately does not re-implement what the pytest suite
already covers. Point your change at the pytest if you want:

- **Multimaster failover semantics** — client-side reconnect behavior,
  `master_type: failover` ordering, pub/ret channel swap, grains cache
  under failover:
  [`tests/pytests/scenarios/failover/multimaster/test_failover_master.py`](../pytests/scenarios/failover/multimaster/test_failover_master.py)
- **Cluster correctness** — cluster-mode auth, shared caches, ring
  membership, cross-master event routing:
  [`tests/pytests/scenarios/cluster/test_cluster.py`](../pytests/scenarios/cluster/test_cluster.py)
- **Haproxy + isolated file-server behavior**:
  [`tests/pytests/scenarios/cluster/test_haproxy_isolated_fs.py`](../pytests/scenarios/cluster/test_haproxy_isolated_fs.py)

If a reviewer could sensibly ask "why isn't this a pytest?", the
answer is one of:

1. The fault must be injected at the container / tc / docker-signal
   level, not inside the python test runner.
2. The leak check needs a 30-minute prometheus time window.
3. The invariant is operator-facing ("after SIGKILL does every minion
   come back?") rather than a Salt-API contract.

## Topologies

| `TOPOLOGY` value          | Compose files                                                                 | Masters | Minions |
|---------------------------|-------------------------------------------------------------------------------|---------|---------|
| `single`                  | `tests/monitoring/docker-compose.yml`                                         | 1       | 3       |
| `cluster3`                | `tests/monitoring/cluster-3node/docker-compose.yml` + monitoring overlay      | 3 behind haproxy | 5 |
| `multimaster-failover`    | `tests/resiliency/compose/multimaster/{docker-compose.yml,docker-compose.failover.yml}` | 2 (`master_type: failover`) | 1 |
| `multimaster-hothot`      | `tests/resiliency/compose/multimaster/{docker-compose.yml,docker-compose.hothot.yml}`   | 2 (both active)             | 1 |

The orchestrator resolves topology → compose-files → container-names
via `lib/common.sh::load_topology`; that function is the single source
of truth and the only place to edit when adding a new topology.

## How to run locally

```bash
cd tests/resiliency

# cluster3 — the richest topology, exercises haproxy failover and
# ring replication alongside the scenario battery.
TOPOLOGY=cluster3 ./run_resiliency.sh

# single — fastest, only covers restart / churn scenarios because
# rolling + simultaneous master restart auto-skip on 1-master topologies.
TOPOLOGY=single ./run_resiliency.sh

# Run just the master-restart battery, skip network + churn:
TOPOLOGY=cluster3 SCENARIOS="master_restart" ./run_resiliency.sh

# Override results destination:
TOPOLOGY=cluster3 RESILIENCY_WORKDIR=/var/tmp/salt-resil-$(date -u +%s) \
  ./run_resiliency.sh
```

Requirements: docker + docker compose plugin, python3, enough
disk under `tests/monitoring/*/prometheus_data` for a 30-minute TSDB
(~100MB).

## Env tunables

Every tunable has a sensible default. Common overrides:

| Env var                   | Default                                       | Effect                                     |
|---------------------------|-----------------------------------------------|--------------------------------------------|
| `TOPOLOGY`                | (required)                                    | which topology to run                      |
| `SCENARIOS`               | full 12-scenario battery                      | space-separated subset                     |
| `RESILIENCY_WORKDIR`      | `results/<utc-timestamp>`                     | results + log destination                  |
| `RECONNECT_WINDOW_SEC`    | 180                                           | max seconds to wait for post-fault recovery before calling it a FAIL |
| `PING_TIMEOUT_SEC`        | 15                                            | per-attempt `test.ping` timeout            |
| `RECONNECT_WARN_SEC`      | 60                                            | recovered-but-slow threshold (WARN in analyzer) |
| `MASTER_FD_LEAK_PER_MIN`  | 30                                            | master open_fds slope FAIL threshold (fds/min) |
| `RSS_LEAK_KB_PER_MIN`     | 200                                           | minion RSS slope WARN threshold (used in-script) |
| `PROMETHEUS_URL`          | per-topology (see `run_resiliency.sh`)        | analyzer prometheus endpoint               |
| `PROM_HOST_PORT`          | 19090                                         | single-topology prometheus host port (set to avoid monitoring-sandbox collision) |
| `CADVISOR_HOST_PORT`      | 18081                                         | single-topology cadvisor host port         |

### Fast-smoke env

For CI-free structural smoke runs that just verify the harness is wired
up correctly, use these shorter defaults:

```bash
TOPOLOGY=single \
  SCENARIOS="baseline master_restart signal_pause" \
  RECONNECT_WINDOW_SEC=60 RESTART_IDLE_SEC=5 INTER_PHASE_WAIT_SEC=5 \
  BASELINE_WORKLOAD_SEC=60 BASELINE_IDLE_SHORT_SEC=30 \
  BASELINE_LONG_IDLE=0 BASELINE_BURST_SEC=20 BASELINE_CONCURRENT_N=50 \
  timeout 900 ./run_resiliency.sh
```

## Results

One run writes:

```
$RESILIENCY_WORKDIR/
├── results.jsonl              # one JSON record per fault (see schema below)
├── analysis.txt               # verdict table from analyze_resiliency.py
├── compose.log                # `docker compose logs` snapshot (always)
├── workload.log               # stdout/stderr of the background workload
├── master_restart.log         # per-scenario stdout/stderr
├── network.log
├── minion_churn.log
└── prometheus-data.tar.gz     # TSDB snapshot for offline Grafana
```

### `results.jsonl` schema

Each line is a self-contained JSON object:

| Field               | Type       | Meaning                                                          |
|---------------------|------------|------------------------------------------------------------------|
| `ts`                | float      | unix epoch at record time                                        |
| `topology`          | str        | topology name                                                    |
| `scenario`          | str        | human label, e.g. `master_restart_sigkill_rolling_c3-salt-master-2` |
| `outcome`           | str        | `recovered` / `failed` / `setup_error` / `skipped_for_topology`  |
| `reconnect_seconds` | int        | seconds from fault-clear to full-minion recovery; `-1` if never  |
| `attempts`          | int        | how many `test.ping` rounds the asserter issued                  |
| `missing`           | list[str]  | minion ids that never answered within the window                 |
| `fd_delta`          | int        | sum(minion fd_after - fd_before) across the fault window         |
| `rss_kb_delta`      | int        | sum(minion rss_after - rss_before) in KB across the fault window |
| `fault_seconds`     | int        | how long the fault was held                                      |
| `notes`             | str        | free-text                                                        |

## Verdict rules

The analyzer (`analyze_resiliency.py`) produces exactly one of three exit codes:

- **`0` — PASS**: every record has `outcome in {recovered, skipped_for_topology}`
  AND master-side prometheus slopes are below threshold.
- **`1` — FAIL**: at least one of:
  - any JSONL record with `outcome` not in the pass set;
  - master `salt_master_open_fds` slope > `MASTER_FD_LEAK_PER_MIN / 60`
    fds/sec (default `0.5` fds/sec == 30 fds/min);
  - master `salt_master_rss_bytes` slope > `10240` bytes/sec sustained
    over 30m (same threshold as `analyze_stats.py`).
- **`2` — data missing**: results file absent/empty, OR (with `--ci` /
  the `CI` env var set) prometheus is unreachable or has no
  `salt_master_*` series. Rationale: a CI run without prometheus
  produces blank Grafana panels and a useless step summary, so a hard
  fail is friendlier than a false green.

A WARN is emitted but does not FAIL the run when any recovered
scenario's `reconnect_seconds` exceeds `RECONNECT_WARN_SEC` (default
60s) — slow is yellow, missing is red.

## Adding a scenario

1. Create `scenarios/<name>.sh`.
2. `set -u`, source `lib/common.sh`, call `load_topology`.
3. For every fault:
   - `read -r fd_before rss_before < <(sample_all_minions)`
   - inject the fault
   - clear the fault
   - `assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before"`
4. Make the script executable; add its basename to the default
   `$SCENARIOS` list in `run_resiliency.sh` if it should run by
   default.
5. Record `skipped_for_topology` (not `setup_error`) when the scenario
   doesn't apply to the current topology — the analyzer counts the
   former as PASS.
