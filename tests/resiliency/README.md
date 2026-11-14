# Salt resiliency test suite

Pytest-driven resiliency harness that brings up a live Salt stack and
subjects it to a battery of injected faults.  Every phase asserts the
same two invariants:

1. **Minions always reconnect** within a bounded window after the
   fault clears.
2. **No per-minute RSS leak** across the fault+recovery window.

Prometheus provides a second-order verdict on the master side (FD and
RSS slope across the 30-minute test window).

This complements, and does not replace, the pytest-based failover /
cluster coverage under `tests/pytests/scenarios/`.

## What this is NOT

This suite deliberately does not re-implement what the broader pytest
suite already covers.  Point your change at the pytest if you want:

- **Multimaster failover semantics** — client-side reconnect
  behavior, `master_type: failover` ordering, pub/ret channel swap,
  grains cache under failover:
  [`tests/pytests/scenarios/failover/multimaster/test_failover_master.py`](../pytests/scenarios/failover/multimaster/test_failover_master.py)
- **Cluster correctness** — cluster-mode auth, shared caches, ring
  membership, cross-master event routing:
  [`tests/pytests/scenarios/cluster/test_cluster.py`](../pytests/scenarios/cluster/test_cluster.py)
- **Haproxy + isolated file-server behavior**:
  [`tests/pytests/scenarios/cluster/test_haproxy_isolated_fs.py`](../pytests/scenarios/cluster/test_haproxy_isolated_fs.py)

If a reviewer could sensibly ask "why isn't this a pytest under
`tests/pytests/`?", the answer is one of:

1. The fault must be injected at the container / tc / docker-signal
   level, not inside the python test runner.
2. The leak check needs a 30-minute prometheus time window.
3. The invariant is operator-facing ("after SIGKILL does every minion
   reconnect?") rather than code-semantic.

## Layout

```
tests/resiliency/
├── conftest.py              # pytest fixtures: topology (session), workload,
│                             # JSONL-row-writing hook, --topology/--marathon flags
├── pytest.ini               # isolates from parent tests/conftest.py gate
├── durations.py             # tier constants (TIER_SUBKEEPALIVE..UPGRADE, RECOVER_*)
├── lib/
│   ├── topology.py          # Topology class + load_topology (6 topologies)
│   ├── injectors.py         # 15 context managers (netem, iptables, SIGSTOP,
│   │                         # pause, remount-ro, docker-net disconnect, ...)
│   └── metrics.py           # prometheus slope queries (stdlib urllib)
├── test_baseline.py         # 7 tests: idle/workload-only/ping-burst/etc
├── test_master_restart.py   # SIGTERM/SIGKILL/restart/rolling/simultaneous
├── test_minion_churn.py     # single/rolling/simultaneous/kill9/stop-start
├── test_network_faults.py   # latency/loss/jitter/partition×4/tcp-reset/pause/DNS
├── test_netem_advanced.py   # reorder/duplicate/corrupt/MTU/tbf/asymmetric/SYN/split
├── test_signal_pause.py     # SIGSTOP/SIGHUP/SIGUSR1/worker-kill/publisher-kill
├── test_resource_pressure.py # OOM/FD/CPU/inode/write-amplify
├── test_disk_faults.py      # cache ENOSPC/RO/slow-io, log fill, PKI RO
├── test_clock_skew.py       # minion/master fwd+back, drift-during-auth
├── test_salt_ops.py         # key reject, master.pem truncate+recover,
│                             # grain mutation, pillar flip, kill_job,
│                             # event storm, beacon flood, mine burst
├── test_fileserver_orch.py  # SLS swap/pillar flip/net disconnect/iface down/...
├── test_cluster_faults.py   # peer SIGSTOP/unreachable/AES rotation/haproxy flap/
│                             # split-brain/rolling+traffic/mm_* variants
├── test_master_marathon.py  # opt-in: 30m/60m/120m outages + flap-during-auth-wave
├── workload.sh              # bash: background traffic loop (ping/state/grains)
├── run_resiliency.sh        # bash: thin pytest wrapper that handles the
│                             # --confcutdir + plugin-disable boilerplate
├── analyze_resiliency.py    # standalone verdict analyzer (reads results.jsonl)
├── compose/                 # docker compose stacks per topology
│   ├── single/
│   ├── cluster3/            # monitoring overlay for tests/monitoring/cluster-3node/
│   ├── cluster5/            # monitoring overlay for tests/monitoring/cluster-5node/
│   ├── multimaster/         # 2 independent masters + failover|hothot overlays
│   └── syndic/              # master-of-masters + sub-syndic + 2 minions
└── results/                 # per-run output (gitignored)
```

## Topologies

| Name | Masters | Minions | Notes |
|---|---|---|---|
| `single` | 1 (`rs-single-salt-master`) | 3 (`rs-single-salt-minion-{1..3}`) | Self-contained compose with aggressive-reconnect `minion.conf`.  Prom :19090 |
| `cluster3` | 3 (`c3-salt-master-{1..3}`) + haproxy VIP | 5 (`c3-salt-minion-{1..5}`) | Overlays `tests/monitoring/cluster-3node/`.  Prom :19090 |
| `cluster5` | 5 (`c5-salt-master-{1..5}`) | 5 (`c5-salt-minion-{1..5}`) | Overlays `tests/monitoring/cluster-5node/`.  Prom :19093 |
| `multimaster-failover` | 2 (`mm-salt-master-{a,b}`) | 1 (`mm-minion-1`) | `master_type: failover` on the minion.  Prom :19091 |
| `multimaster-hothot` | 2 (`mm-salt-master-{a,b}`) | 1 (`mm-minion-1`) | `master_type: str` + list (connects to both).  Prom :19091 |
| `syndic` | 2 (`rs-syndic-{mom,sub}`) | 2 (`rs-syndic-minion-{1,2}`) | MoM + sub-syndic + minions.  Prom :19092 |

## How to run

```bash
# Full battery on single:
TOPOLOGY=single ./run_resiliency.sh

# Subset against the 3-master cluster:
TOPOLOGY=cluster3 SCENARIOS="baseline master_restart signal_pause" \
  ./run_resiliency.sh

# Marathon phases on multimaster-failover (opt-in; ~90 min):
TOPOLOGY=multimaster-failover MARATHON_ENABLED=1 \
  SCENARIOS="baseline master_marathon" \
  ./run_resiliency.sh

# Same with the 2-hour phase (~3.5h total):
TOPOLOGY=multimaster-failover MARATHON_ENABLED=1 MARATHON_120M=1 \
  SCENARIOS="baseline master_marathon" \
  ./run_resiliency.sh

# Direct pytest invocation (for ad-hoc filtering):
venv314/bin/pytest -c tests/resiliency/pytest.ini \
    --confcutdir=tests/resiliency \
    -p no:system-statistics -p no:salt-factories \
    --topology=cluster3 \
    tests/resiliency/test_network_faults.py::test_network_partition
```

Requirements: docker + docker compose plugin, python 3.10+ with
pytest (the repo's `venv314` or `venv310`), enough disk under the
compose project's `prometheus_data/` for a 30-min TSDB (~100 MB).

## Env tunables

Every tunable has a sensible default; the duration tiers in
`durations.py` are keyed to salt's own default timeouts.  Common
overrides:

| Env var | Default | Effect |
|---|---|---|
| `TOPOLOGY` | (required) | which topology to run |
| `SCENARIOS` | full 13-scenario battery | space-separated stems → pytest `-k` filter |
| `RESILIENCY_WORKDIR` | `results/<utc-timestamp>` | results + log destination |
| `MARATHON_ENABLED` | 0 | 1 to run the 30m/60m marathon phases |
| `MARATHON_120M` | 0 | 1 to also run the 2-hour phase |
| `PROM_HOST_PORT` | 19090 | single-topology prometheus host port (set to avoid collision) |
| `CADVISOR_HOST_PORT` | 18081 | single-topology cadvisor host port |
| `PROMETHEUS_URL` | per-topology | analyzer prometheus endpoint |
| `RESILIENCY_TIER_STANDARD_SEC` | 90 | override the "standard" fault-hold tier (every tier is env-overridable) |
| `RESILIENCY_RECOVER_STANDARD_SEC` | 180 | override the "standard" recovery window |
| `RESILIENCY_RSS_LEAK_KB_PER_MIN` | 200 | minion RSS slope leak threshold |

See `durations.py` for the full tier table.

## Fast-smoke env

For CI-free structural smoke runs that just verify the harness is
wired up, use these shorter defaults:

```bash
TOPOLOGY=single \
  SCENARIOS="baseline master_restart signal_pause" \
  RESILIENCY_TIER_STANDARD_SEC=20 \
  RESILIENCY_RECOVER_STANDARD_SEC=60 \
  RESILIENCY_PACING_INTER_PHASE_SEC=5 \
  ./run_resiliency.sh
```

## Results

One run writes:

```
$RESILIENCY_WORKDIR/
├── results.jsonl              # one JSON record per fault
├── compose.log                # docker compose logs snapshot on teardown
├── compose-up.log             # compose up --build output
├── exporters.log              # fd_exporter launch output
└── workload.log               # background workload stdout/stderr
```

### JSONL schema (one record per phase)

```json
{
  "ts": 1731494400.0,
  "topology": "cluster3",
  "scenario": "network_partition_deep",
  "outcome": "recovered",
  "reconnect_seconds": 42,
  "attempts": 9,
  "missing": [],
  "fd_delta": 0,
  "rss_kb_delta": 1024,
  "fault_seconds": 300,
  "notes": ""
}
```

`outcome` is one of: `recovered`, `failed`, `setup_error`,
`skipped_for_topology`.

The `scenario` field is the authoritative phase label (first arg
passed to `Topology.assert_reconnect`), not the pytest nodeid —
preserved across the bash-to-pytest port for analyzer compatibility.

## Verdict

`analyze_resiliency.py` turns the JSONL into a pass/fail verdict:

- **FAIL** if any row has `outcome` in `{failed, setup_error}` (skips
  don't count).
- **FAIL** if master FD slope > `MASTER_FD_LEAK_PER_MIN / 60` fds/sec
  (default: 0.5).
- **FAIL** if master RSS slope > `MASTER_RSS_LEAK_BYTES_PER_SEC`
  (default: 10 KB/sec sustained over 30 min).
- **WARN** if any `recovered` row's `reconnect_seconds` exceeds the
  WARN threshold (default: 60s).

`run_resiliency.sh` exits with pytest's exit code; the workflow
re-runs `analyze_resiliency.py` after the pytest pass as an
idempotent verdict check.

## Adding a new scenario

1. Write `tests/resiliency/test_<name>.py` following the pattern of
   the existing files: import a tier from `durations.py`, grab a
   context manager from `lib/injectors.py`, call
   `topology.assert_reconnect(label, fault_sec=..., before=...,
   item=request.node)` with the bash phase label as the first arg.
2. If the scenario is topology-specific, add
   `@pytest.mark.topology("cluster3", ...)`.
3. If it needs the opt-in long-runtime gate, add
   `@pytest.mark.marathon`.
4. No orchestrator edits needed; pytest auto-discovers the new file.
