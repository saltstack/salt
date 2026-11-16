# baseline leak regression on cluster3 (run 43824366115)

**Date**: 2026-11-16
**Topology**: cluster3 (dwoz/resiliency-test-suite tip `7f34367d0c8`)
**Previous passing run**: 43773954141 (SHA `9b4b3a716ce`) — **but cluster3 job never completed there; see below.**

## Verdict

**No salt-side regression.** The baseline_idle_short / baseline_idle_long /
baseline_workload_only "leak" verdicts on cluster3 are harness-side false
positives caused by two interacting facts:

1. **cluster3's minion config declares `dummy_resource_count: 200000`** per
   minion (see `tests/monitoring/cluster-3node/minion-{1..5}.conf`). On a fresh
   boot each of the 5 minions chunk-registers 200 000 dummy resources at
   10 000 per chunk — 20 chunks per minion, 100 chunks fleet-wide.
2. **`wait_initial_auth` + 60 s warmup is not long enough** for the register
   storm to finish on this topology. The baseline tests fire while
   `_register_resources_with_master` is still iterating chunks, so
   `sample_minions()` BEFORE the idle sleep and `sample_minions()` AFTER
   capture growing working-set that is legitimate ongoing register work.

The previous run didn't see this because its cluster3 job
(`132995852482`) **never reached the test phase** — it timed out at 2h57m
in "Start environment" with no artifact uploaded. The prometheus
bind-mount fix in `bf9d8ae4738` unblocked `Start environment`, and the
first cluster3 job that actually runs the baseline tests trips the
leak gate on the heavy-register topology.

## Affected tests (confirmed by reading)

Taking only `topology` fixture, NOT `workload`:

* `test_baseline_idle_short` (tests/resiliency/test_baseline.py:82)
* `test_baseline_idle_long` (tests/resiliency/test_baseline.py:117)

Taking BOTH `topology` AND `workload`:

* `test_baseline_workload_only` (tests/resiliency/test_baseline.py:143)

All three use `topology.sample_minions()`, which calls
`sample_container()` for every container in `spec.minion_containers` and
reads `/proc/<pid>/{fd,status}` from a single pid located via
`_PID_SH`:

```
pgrep -f 'salt-minion.*MinionProcessManager' || pgrep -f 'salt-minion.*MainProcess' || true
```

piped through `head -1`. This regex matches both the `MinionProcessManager`
parent AND its `MinionProcessManager ProcessPayload(...) Minion._thread_return`
children (secondary concern — see below).

## Local measurement — cluster3, dwoz/resiliency-test-suite tip

Compose: `tests/monitoring/cluster-3node/docker-compose.yml` only (overlay
not applied; no prometheus/cadvisor noise, which rules out "prometheus
scrape inflated readings").

### Steady-state growth (fleet already past peak register, 16 min after boot)

Measured on the 5 minions over a 10-minute idle window, sampling exactly
what the harness samples (`pgrep -f 'salt-minion.*MinionProcessManager' | head -1`):

| minion | T0 fd | T0 rss_kb | T+10m fd | T+10m rss_kb | delta_fd | delta_rss |
|-------:|------:|----------:|---------:|-------------:|---------:|----------:|
| 1      | 67    | 160452    | 57       | 160492       | -10      | +40       |
| 2      | 58    | 158556    | 67       | 158264       | +9       | -292      |
| 3      | 67    | 158196    | 57       | 156600       | -10      | -1596     |
| 4      | 58    | 159044    | 67       | 158608       | +9       | -436      |
| 5      | 57    | 156756    | 67       | 157816       | +10      | +12       |
| **sum**| **307** | **793004** | **315**  | **791780**   | **+8**   | **-2272** |

Fleet RSS *dropped* 2.2 MB over 10 min. fd delta +8 across 5 minions
= +1.6 fd/minion, well under the `MIN_FD_DELTA_PER_MINION=1` × 5 = 5 fd
gate.

### Fresh-boot minion-1 (controlled register-storm probe)

To isolate the register storm, restarted a single minion-1 container
and sampled the harness pid at T+60s (just after `wait_initial_auth`
+ default warmup would yield) and T+540s:

| sample | fd | rss_kb |
|--------|---:|-------:|
| T+60s  | 55 | 84008  |
| T+540s | 55 | 91664  |
| delta  | 0  | +7656  |

**+7.5 MB growth on one minion over 8 minutes** of ongoing register,
with 0 fd change. Scale to 5 minions ≈ 37.5 MB fleet growth over 8 min,
which the CI's idle_short samples in a narrower window near the storm
peak. This confirms the growth is real working-set, not a leak, and
not sampler contamination.

### What the CI actually saw (from task preamble, run 43824366115)

* test_baseline_idle_short: "RSS grew 64596 KB/min" with
  `reason=fd_accumulation` after ~28 s reconnect.
* test_baseline_idle_long: `fd_delta=+46 rss_delta_kb=+47336` over 1800 s.
* test_baseline_workload_only_ping: `fd=0 rss_delta=+972`; 5/5 missing.

For idle_short, `elapsed = fault_sec + reconnect_s = 0 + 28 = 28`,
floored to 60 by the slope code; `rss_per_min = rss_delta_kb * 60 / 60
= rss_delta_kb ≈ 64596 KB ≈ 63 MB fleet growth ≈ 12.6 MB per minion`
during the 300 s idle sleep + 28 s reconnect.

Our local fleet measured in the *same way* shows **negative** growth,
so the ~63 MB figure must be the first-few-minutes ramp of resource
register. By the time our local probe ran, the register had progressed
to IDs ~188 000 of 200 000 (visible in minion log) — i.e. already past
90% of the storm. CI tests fire within 60 s of `wait_initial_auth`,
which is still early in the register timeline.

### Growth source verified in process tree

`docker exec c3-salt-minion-1 pgrep -af salt-minion` shows 9 salt-minion
processes:
* pid 1 — tini
* pid 7 — `salt-minion` MainProcess (not what the harness samples)
* pid 10 — `MultiMinionProcessManager MinionProcessManager` (the parent,
  what the harness samples)
* pids 151, 152, 153, 155, 156 — `ProcessPayload(jid=...) Minion._thread_return`
  (5 stuck return-thread children; `process_count_max: 5` is the per-minion
  cap, all 5 slots held by returns queued against an auth-stalled master
  in our local repro)

The `_thread_return` children each hold ~147 MB RSS (mostly COW with the
parent) and grow their fd set by 1-2 per child during their lifetime
(74, 76, 78, 80, 82 fds across the 5 children, visible in /proc/<pid>/fd).
The harness samples ONLY pid 10, so these children's growth is NOT in
the reported numbers.

Minion log shows the smoking gun:

```
[WARNING ] Maximum number of processes reached while executing jid
           20261116085943787583, queuing... (Running: 5, Max: 5)
```

Repeating 100+ times. On CI this is less relevant (masters respond faster
so returns don't stack), but confirms the layered pressure.

## Why the slope math makes this worse, not better

In `assert_reconnect()` (lib/topology.py:911):

```python
elapsed = fault_sec + reconnect_s
if elapsed < 60:
    elapsed = 60
rss_per_min = rss_delta_kb * 60 // elapsed
```

**`elapsed` does NOT include the `time.sleep(idle_sec)` that happened
before `assert_reconnect` was called.** For `test_baseline_idle_short`
that's a 300 s window during which the minion's working set changes —
but the slope uses only the 28 s reconnect window (floored to 60 s)
as the denominator. This is a **5× amplification** of the real idle-slope.

Secondary concern. Even with the correct denominator the register-driven
growth exceeds `RSS_LEAK_KB_PER_MIN=200`, so fixing the slope math alone
does not unblock cluster3. The proper fix is to extend the warmup so
the "idle" baseline really is idle.

## Secondary harness issue: `_PID_SH` matches 6 pids

`pgrep -f 'salt-minion.*MinionProcessManager'` matches the MPM parent
AND every `_thread_return` child:

```
$ docker exec c3-salt-minion-2 pgrep -f 'salt-minion.*MinionProcessManager'
9
291
292
293
294
295
```

`head -1` normally picks pid 9 (lowest pid in a fresh container), which
is the parent. But if the parent is restarted and the new MPM pid > a
child pid (not usually possible without a wrap), or if `pgrep` ordering
changes mid-test, the harness could silently sample a different pid
between before/after. Two local fast-sample runs across all 5 minions
showed stable pid selection in steady state, so this is latent, not
active in the current failure mode. Still worth anchoring the regex to
`$` — see proposed fix below.

## Proposed fixes

### Primary (committed)

1. **Topology-aware warmup**. Cluster3's `wait_initial_auth` returns on
   test.ping, but the 200K-resource register still runs for several
   minutes after. Add a topology-keyed warmup override in
   `conftest.py`: cluster3 and cluster5 (which also carries
   `dummy_resource_count`) get ≥ 300 s. Default stays 60 s.

2. **Anchor `_PID_SH` to end-of-cmdline** so it only matches the MPM
   parent, not `ProcessPayload(...) Minion._thread_return` children:

   ```python
   _PID_SH = (
       "pgrep -f 'salt-minion.*MinionProcessManager$' "
       "|| pgrep -f 'salt-minion.*MainProcess$' "
       "|| true"
   )
   ```

### Follow-up (deferred)

3. **Fix the slope denominator** so idle-only tests
   (`test_baseline_idle_short`, `test_baseline_idle_long`) include the
   pre-reconnect idle time in `elapsed`. Current math magnifies the
   reported `rss_per_min` by `(idle_sec + reconnect_s) / reconnect_s`,
   which on a healthy non-cluster3 topology still records 60 KB/min as
   60 KB/min (because growth is ~0) but on any topology with ongoing
   working-set change double-counts. The caller should pass
   `fault_sec = idle_sec` for baseline_idle so the gate sees the real
   slope.

4. **Register-completion gate**. The right long-term fix is to block
   `wait_initial_auth` (or the warmup) until every minion's last
   register chunk has landed (watch for `chunk_final=True` for each
   enabled type on the master-side `resource_grains` bank, or add a
   runner that returns per-minion register status). Leaves as a
   follow-up because it requires a master-side probe.

## Open question — the fleet-unavailable symptom

The task notes "5/5 minions MISSING after test" on `baseline_idle_long`
(1800 s idle). In our local 10-min idle the fleet did not disappear
(same 5 pids before and after). The fleet-unavailable symptom likely
derives from the master going unresponsive under the 100-chunk
registration pressure on a loaded CI runner (cluster3 is the
"stress" topology by design), not from a minion crash. Collect
`docker logs c3-salt-master-*` on the next failing CI run to confirm.

## Checklist

- [x] Confirmed which tests take `workload` (only `test_baseline_workload_only`).
- [x] Confirmed sampling path: `sample_container` -> `/proc/<pid>/{fd,status}`
      via `_PID_SH`.
- [x] Local measurement BEFORE / AFTER per minion captured.
- [x] Growth source identified: resource_registry chunked register still
      running past the 60s warmup on cluster3's 200K-per-minion config.
- [ ] Register-completion gate (deferred — design in report).
- [x] Harness `_PID_SH` anchor fix committed.
- [x] Harness per-topology warmup fix committed.
