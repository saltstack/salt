# resource_oom_squeeze: suspicious LEAK verdict, NOT auto-exempted

**Date**: 2026-11-18
**Topology**: single
**Branch**: dwoz/resiliency-test-suite tip `c77d2a96c5f`
**CI run**: 44267471361
**Observed**: `bulk_rss_retention` 12828 KB/min

## Why this is flagged, not exempted

Every other LEAK verdict from run 44267471361 fits a known cold-start /
reauth fault-work pattern. `test_resource_oom_squeeze` has three
anomalies:

1. **Magnitude**: 12828 KB/min is 2-3x larger than any other LEAK-verdict
   fault test in this run (next-highest is `test_master_restart_docker_restart`
   at 11840, which is a full master restart on syndic -- by far a larger
   fault than master-OOM on single).
2. **Already revives + resamples**: the test revives the master if the
   OOM cascade dropped tini and calls `wait_initial_auth(180)` before
   resampling `before` (see `test_resource_pressure.py:179`). The
   intent is specifically to zero out the cold-start baseline and
   capture only post-steady-state growth. 12828 KB/min AFTER the
   resample is either:
   * `_load_modules()` cache repopulation that's still lazy at the
     `wait_initial_auth` bar (first-grains publish not yet triggered),
     in which case this IS fault-work and would be legitimately
     exempted on the same grounds as test_minion_churn_single_restart;
     OR
   * A real retention bug triggered specifically by master-side OOM
     cascade: zombie fds held by a child process that exited abnormally,
     or a minion-side buffer that doesn't release when the publish
     channel drops mid-send.
3. **OOM-specific stress**: the fault isn't just "master absent for
   TIER_STANDARD_SEC" -- it's "master's child processes selectively
   die via SIGKILL". Anything that relied on orderly teardown in a
   signal handler leaks here.

## What to do before exempting

- Run `test_resource_oom_squeeze` 3x on a single stack with
  `agents/scratch/track_oom_sample.py` (not yet written) or via the
  built-in `fd_exporter` histogram to split the 12828 KB/min between:
  * Master-side growth (expected if the revive repopulated fresh
    worker pool -- exempt on `allow_bulk_rss`).
  * Per-minion growth (unexpected -- real leak, needs a Python-level
    fix per `feedback_no_malloc_trim.md`).
- If per-minion growth dominates, reproduce with workload stopped and
  only the OOM squeeze running -- isolates whether workload traffic
  during the squeeze is the amplifier.
- If master growth dominates AND survives a second identical squeeze
  (ie. a re-run grows < noise), it's a one-shot cold-start artifact of
  the revive path and `allow_bulk_rss=True` is the correct fix
  (consistent with Agent BB's pattern for mm-hothot minion restarts).

## Interim

Do NOT apply `allow_fault_rss=True` on the next CI run. Let this test
stay RED so the signal remains visible. Revisit after a dedicated
local repro per the plan above.
