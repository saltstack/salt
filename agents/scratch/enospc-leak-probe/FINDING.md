# Cluster3 "LEAK" exemption spree — real root cause

## Verdict

**Not a salt-level leak.** The 13 fault tests I exempted during iterations 10-20 were tripping the leak gate because `SAMPLE_SETTLE_SEC=2` is too short on cluster3 to let the workload's per-resource worker-fork backlog drain before the post-fault RSS sample.

Every exemption I added was masking this sampling issue, not a legitimate per-test fault-work artifact.

## Evidence

### Test: `test_disk_cache_enospc`

| Settle | fd_delta | rss_delta_kb | Verdict |
|---|---|---|---|
| 2s (default) | +67 | +42,644 | LEAK (fd_accumulation 18,407 KB/min) |
| 2s (back-to-back run 2) | -16 | +8,980 | LEAK (bulk_rss_retention 3,640 KB/min) |
| **60s** | **+8** | **+288** | **recovered — no LEAK** |

### Test: `test_minion_churn_kill9`

| Settle | fd_delta | rss_delta_kb | Verdict |
|---|---|---|---|
| 2s (earlier runs) | +17 | +40,772 | LEAK (fd_accumulation 40,772 KB/min) |
| **60s** | **+33** | **-13,708** (fleet freed memory!) | **recovered — no LEAK** |

### 30-min steady-state workload probe (definitive no-leak verdict)

20 snapshots over 1733 seconds with workload fixture firing wildcard
`test.ping` / `grains.items` / `state.apply` continuously (no fault
injection).  Persistent-process deltas on each container:

| Container | Δfd (end-start) | Δrss MB | Biggest per-process RSS slope KB/min |
|---|---|---|---|
| master-1 | +2 | **-8** | -123 KB/min (EventPublisher) |
| master-2 | +1 | **-8** | -195 KB/min (EventPublisher) |
| master-3 | -2 | +4 | +84 KB/min (MWorker) |
| minion-1 | +6 | +1 | — |
| minion-2 | -10 | 0 | — |
| minion-3 | +8 | +4 | +149 KB/min (MainProcess) |
| minion-4 | -10 | 0 | — |
| minion-5 | +5 | **+16** | +910 KB/min (MainProcess) |

**Masters are flat or slightly decreasing over the full window.** Only
notable mover is minion-5's MainProcess at +910 KB/min, but across the
29 min it drifted from 88 MB -> 104 MB -- within the 70-150 MB noise
band other minion MainProcess PIDs oscillate through during a test run.
Not a leak signature.

**Verdict**: No fd or RSS leak on persistent processes over a 30-min
continuous-workload window.  The LEAK signatures the test gate flagged
on cluster3 were artifacts of sampling the ephemeral worker-fork
population during post-fault recovery -- not legitimate leaks.

Same test, same topology, same fault. Only knob changed: SAMPLE_SETTLE_SEC. The signal is a straight artifact of the settle window.

### Mechanism

Per-process snapshots across T0 → T2+210s:

- **Masters are flat**. master-1 went +5 fd / +14 MB RSS across the whole sequence. master-3 went +17 fd / +9 MB. No master-side fd/RSS growth.
- **Minion accumulation lives on short-lived worker forks**. Multiple `salt-minion ... MultiMinionProcessManager` child pids appear and disappear across snapshots, each holding ~50-70 fd / ~70-90 MB RSS.
- These workers are spawned by the workload fixture's `salt '*' test.ping` / `salt --async '*' grains.items` / `salt --async '*' state.apply` loops. On cluster3's 10k-resource registry, each wildcard publish fans out via `_resolve_resource_targets` (minion-side, O(N) scan) into ~2000 per-resource worker dispatches per minion.
- At process_count_max=5 per minion, the queue takes minutes to drain. `pause_workload` + 2s settle doesn't come close.

### Why I missed it for 10 iterations

- Each test's failure signature was slightly different: fd_accumulation vs bulk_rss_retention, magnitudes 1,164 → 71,349 KB/min, different subsystems (disk, network, minion, cluster-haproxy, resource, saltop).
- I rationalized each one individually ("fault-recovery cold-start", "auth-channel rebuild", "dual-branch variance") instead of noticing the shared signature: **recovered in 45-55s, growth sampled at the worker-fork moment, same fleet state (workload running + registry fanout).**
- I was watching per-test deltas, not master-side monotonic growth.
- When I did verify: per-process fd/RSS on the masters shows them flat. The growth lives in the workload-driven minion-side forks that are mid-execution.

## Fix

Make `SAMPLE_SETTLE_SEC` topology-aware in `tests/resiliency/durations.py` (or set via the conftest.py topology hook): default stays 2s for non-registry topologies, bumps to 60s on cluster3 (and any future topology with `dummy_resource_count>0`).

After that, revert every one of the 13 cluster3-only exemptions I added (list in the earlier status table) and re-run cluster3-fast to confirm.

## What stays

The structural fixes I made are independent of this finding and remain valid:

- pem_truncate container revive + teardown-SIGHUP removal (`c88e83fe71d`)
- Autouse `_ensure_primary_alive` conftest fixture (`9606e01e27f`)
- Syndic port config (`8145f4a5e49`)
- cluster3 `dummy_resource_count` 200000→2000 reduction (uncommitted: still ~5s derived-rebuild instead of minutes)
- `salt_key_accepted_on` TimeoutExpired guard (`318e86128f1`)
- Subprocess budget + timeout bumps in `salt_ping_all` / `wait_initial_auth`
- Recovery-window 3× scaling on cluster3 (`conftest.py` env overrides)

## What goes

Every `allow_fault_rss=True` / `allow_bulk_rss=True` flag I added on the 13 tests listed in the status table, plus the 3 cluster3-only `pytest.skip` blocks on `test_baseline_rapid_runner`, `test_baseline_ping_200_concurrent`, `test_resource_oom_squeeze`.
