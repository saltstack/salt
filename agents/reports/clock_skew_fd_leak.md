# mm-hothot `test_clock_master_fwd_60s`: minion fd leak during forward master skew

## CI signature

Run `43824366115` job `133154587303` (topology `multimaster-hothot`):

```
08:28:36 ERROR resiliency.topology LEAK 'clock_master_fwd_60s' recovered after 0s
  via mm-salt-master-a but RSS grew 418 KB/min > 200 KB/min (reason=fd_accumulation)
FAILED test_clock_skew.py::test_clock_master_fwd_60s
  - Failed: clock_master_fwd_60s: recovered after 0s but RSS slope 418 KB/min
    exceeds threshold 200 KB/min (fd_delta=66 rss_delta_kb=628 reason=fd_accumulation)
```

The compound leak gate (`tests/resiliency/lib/topology.py:947`) fires because both
conditions trip:

  * `fd_delta = 66` > `MIN_FD_DELTA_PER_MINION * len(minions) = 1 * 1 = 1`
  * `rss_per_min = 418` > `RSS_LEAK_KB_PER_MIN = 200`

## What the test injects

`test_clock_skew.py::test_clock_master_fwd_60s` (lines 200-212):

```python
scenario = "clock_master_fwd_60s"
container = topology.spec.primary_master  # mm-salt-master-a
before = topology.sample_minions()
with _clock_skewed(topology, container, 60):
    time.sleep(PHASE_DURATION_SEC)   # TIER_STANDARD_SEC == 90s
topology.assert_reconnect(scenario, fault_sec=PHASE_DURATION_SEC, before=before, ...)
```

`_clock_skewed` applies `date -u -s @<host_now+60>` on the master container and
restores on exit.  The minion (`mm-salt-minion-1`) is unperturbed on the host
side; what it sees is the master's event-stream timestamps jumping +60s forward.

## Comparison across topologies and phases

Same run, from CI log:

| scenario                 | topology           | fd_delta | rss_delta_kb | rss_kb/min | verdict   |
| ------------------------ | ------------------ | -------: | -----------: | ---------: | --------- |
| `clock_master_fwd_60s`   | multimaster-hothot |      +66 |         +628 |       +418 | LEAK FAIL |
| `clock_master_fwd_60s`   | single             |     +192 |      -13 132 |      -8755 | recovered |
| `clock_master_back_3600s`| multimaster-hothot |     -126 |       -4 056 |      -2704 | recovered |
| `clock_minion_fwd_60s`   | multimaster-hothot |        0 |         +388 |       +258 | recovered |
| `clock_minion_back_300s` | multimaster-hothot |      +62 |           -4 |         -3 | recovered |

Key observations:

  1. Forward master-skew on hothot (+66 fd, +628 KB) is the only phase where
     the fd-delta is positive AND the RSS slope is positive.  Both other
     hothot clock phases either shed fds (`-126`) or produced negative RSS.
  2. Single topology under the same +60s master skew acquired FOUR TIMES as
     many fds (+192) but net-released memory and so passed the compound
     gate.  The +192 is NOT a coincidence; it is the minion's response to
     the skew.  On single the minion only talks to one master and the fd
     growth is one process-family's worth.  On hothot the minion talks to
     two masters but only ONE's clock moved, so the fd-growth is smaller
     but is NOT offset by the normal negative RSS slope that follows a
     connection recycle on the other sibling minion.

## Hypothesis: scheduler catch-up on wall-clock jump

`salt.utils.schedule` uses `datetime.datetime.now()` (wall clock) and the
minion registers `status.master` as a recurring job at
`master_alive_interval` (default 30s, hothot inherits the default).  When the
MASTER wall clock jumps +60s forward, the minion sees:

  * events from the master carrying timestamps 60s in the future;
  * event-timestamp comparisons that treat the minion as "stale" relative to
    the master.

What the minion itself does is less clear without a repro:

  * `master_alive` scheduling on the minion uses the MINION's wall clock,
    which is unchanged.  So minion-side scheduler catch-up is unlikely to
    be the cause.
  * `AsyncAuth` reads the master's cached pubkey; a timestamp mismatch
    between master-returned AES key rotation metadata and minion wall
    clock could force a re-auth cycle.  Each cycle allocates a transient
    ReqChannel + PubChannel, each with its own socket pair.  Agent M's
    commit `256d01db487` shards `minion_master.pub` per-master in
    multimaster mode; in a re-auth burst, both shards get rewritten,
    each operation holding a file fd briefly.

The data (`fd_delta=66` on a single minion over 90s) is consistent with a
burst of ~5-10 re-auth cycles during the skew window, each one leaving a
small number of fds unreleased.  But this is speculation until we see the
actual minion log for the failing window.

## Local reproduction attempt

Failed.  Host's `systemd-timesyncd` / NTP service is active (`timedatectl`
reports "System clock synchronized: yes").  Linux containers without an
unshared time namespace (confirmed via `readlink /proc/self/ns/time` showing
the same inode `4026531834` in container and on host) share the kernel
clock, so `date -u -s` in the container momentarily changes the clock and
the host NTP daemon immediately reverts it within <1s.  The test's
`_can_set_clock` probe would skip the test on this host.

```bash
docker exec mm-salt-master-a sh -c "
  date -u +%s                             # 1794859335
  date -u -s '@'\$((\$(date -u +%s) + 60)) # applied
  date -u +%s                             # 1794859395  (+60s applied)
  sleep 1
  date -u +%s                             # 1794859336  (reverted by host NTP)
"
```

To reproduce this locally would require stopping `systemd-timesyncd` on the
host (which affects every other container on the box) or putting the
container in its own time namespace via `unshare --time`.  Neither is
appropriate on a shared workstation.

## Classification

**Not a harness bug; needs upstream investigation.**

The compound leak gate is firing correctly: +66 fd on a 1-minion topology in
90s IS accumulation, not noise.  The gate's `MIN_FD_DELTA_PER_MINION=1`
threshold is exactly the signal the gate was designed to catch.

Two paths forward:

  1. **Classify as pre-existing symptom exposed by the gate.**  Before the
     compound-gate commits (`b0e09091475`, `c11bb935cd9`, `a6fc74c5d06`),
     this fd leak was invisible because:
        - old gate was RSS-only, and hothot's +628 KB wouldn't have fired
          the 200 KB/min single-criterion threshold either (it only trips
          when both are positive);
        - results.jsonl recorded empty sentinels, so analyze_resiliency
          wouldn't have flagged it anyway.
     The symptom is likely present on all branches with `master_alive_interval
     > 0` and multimaster mode.

  2. **File saltstack/salt issue after reproducing.**  Minimum viable repro:
        - two-master compose stack (hothot overlay);
        - one minion with master_type: failover (default) or an explicit list;
        - stop host NTP, apply `date -s '+60s'` on master-a, wait 90s;
        - sample minion's `/proc/<pid>/fd` count every 5s and the open
          file descriptor map (`ls -l /proc/<pid>/fd`) to see which type
          grows (socket vs file).

## Interim: no harness change recommended

The gate is correct.  Lowering `MIN_FD_DELTA_PER_MINION` or raising the
`RSS_LEAK_KB_PER_MIN` ceiling would mask a real signal.  The test should
stay red on mm-hothot until the underlying minion fd behavior under
forward master-clock skew is understood.

If this blocks the nightly from being green while the investigation is
in flight, the hothot-only xfail is the right next step.  We should NOT
xfail across all topologies — single/syndic/cluster pass this scenario
and should keep being guarded.
