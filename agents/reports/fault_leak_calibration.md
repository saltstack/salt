# Fault-scenario leak-gate calibration (run 44002386163)

**Date**: 2026-11-17
**Topology**: single + syndic + cluster5 (dwoz/resiliency-test-suite tip `0a07b8d41ad`)
**Context**: run 44002386163 produced 12 LEAK-fail verdicts across fault
scenarios after Agent J (`76eaf5b364b`) paused the workload pgroup during
the AFTER sample. The remaining growth signal is pure fault-work; the
workload was quiesced for the AFTER sample.

## The 12 failing cases, grouped

| Group | Cases | Reason |
|---|---|---|
| Disk-cache mutation on master | `disk_cache_readonly`, `orch_volume_remount_simulate` | master re-populates cachedir after remount/wipe → minions re-auth / re-subscribe → +fd per minion |
| Pillar/fileserver retargeting | `fs_pillar_flip_mid_run`, `fs_large_file_mid_cache`, `fs_master_srv_remount` | top.sls swap or source file churn triggers pillar refetch; minion holds sockets to multiple masters mid-flip |
| Clock skew | `clock_master_fwd_60s`, `clock_minion_back_300s` | aes-key rotation on wall-clock transition; minion re-handshakes against its peer master |
| Cluster peer disruption | `cluster_peer_sigstop_standard`, `cluster_peer_sigstop_backoff`, `cluster_peer_unreachable` | minion still holds the paused peer's socket until TCP keepalive fires; fd accumulates briefly during fleet reconnect |
| AES rotation | `cluster_aes_rotation_under_load` | .dfn dropfile triggers cluster rotation → every minion re-auths → fd count climbs during drain |

All share the same signature: BOTH gates trip (slope > 200 KB/min AND fd_delta
> `MIN_FD_DELTA_PER_MINION * n_minions`). RSS retention is not the issue —
none of these cases crossed the 5 MB bulk gate. The fd gate is what pushes
them over.

## Approach chosen: per-fault opt-out via `allow_fault_rss=True`

Approach 1 from the task brief, with a combined convenience flag.

### Changes

1. `tests/resiliency/lib/topology.py::assert_reconnect`:
    * Add `allow_fd_accumulation: bool = False` — mirrors `allow_bulk_rss`,
      disables the fd-threshold branch of the leak gate.
    * Add `allow_fault_rss: bool = False` — convenience: sets BOTH
      `allow_bulk_rss` and `allow_fd_accumulation` True. Documented as
      "the fault-work opt-out — use for scenarios where cache/auth/pillar
      repopulation legitimately holds state for one to several seconds
      past the fleet-ping bar".
2. 12 failing test sites get `allow_fault_rss=True`.

### Why this over the alternatives

* **Approach 2 (raise `RSS_LEAK_KB_PER_MIN`)**: hides slow-leak signal
  across the whole suite. A 5000 KB/min floor would mask a real
  200 KB/min accumulation bug in any non-opted-out test.
* **Approach 3 (scale by `fault_sec`)**: addresses only the slope, not the
  fd gate — but fd is what trips all 12 cases. Also not discoverable
  (hidden in a computed threshold).
* **Approach 4 (drop slope for fault tests)**: fd gate still trips. Would
  need combination with raising the fd threshold, which then masks real
  signals in non-fault tests that reuse the gate.
* **User's recommended `settle_before`**: makes BEFORE a low-watermark by
  pausing workload around the BEFORE sample too. Helps RSS slope for
  workload-driven growth, but the fault tests' fd_accum comes from the
  *minion-side* reconnect work, not host workload pgroup. The minion's
  fd count doesn't drop when we SIGSTOP the host workload.sh.

### Preservation of real-leak signal

* Agent C's catalogue of real-leak signatures is unaffected because those
  tests (`ping_200_concurrent`, `resource_oom`, mm `minion_churn_*`) do
  not set `allow_fault_rss=True`. They continue to fail on fd+N.
* `baseline_*` tests still assert the full gate — a genuine background-leak
  signal still trips both branches.
* The opt-out is per-call, visible in the test body as a documented flag;
  there is no hidden global knob.

### Discoverability

* The flag names (`allow_fd_accumulation`, `allow_fault_rss`) are
  self-describing and parallel to the existing `allow_bulk_rss`.
* Each opted-out test site carries the flag inline with a `notes=` string
  that still records the fault parameters — triage can grep
  `allow_fault_rss=True` to see every scenario that's intentionally
  waiving fd/RSS checks.
* The docstring on `assert_reconnect` enumerates when to use each.

## Verification plan

1. Bring up single stack, repro `test_fs_master_srv_remount` on the
   current tip to confirm it fails with `fd_accumulation`.
2. Apply the `allow_fault_rss=True` patch to that one test.
3. Re-run on the same stack; confirm it now records RECOVERED.
4. Unit-level: craft a `MinionSample` pair simulating Agent C's
   `ping_200_concurrent` fd+53 scenario and confirm `assert_reconnect`
   still trips when `allow_fault_rss=False` (the default).

## Follow-up

If a future fault class produces genuine growth AND we want the gate to
retain some teeth, we can raise `MIN_FD_DELTA_PER_MINION` (currently 2)
on a per-test basis via the existing env knob rather than opting out
entirely. The `allow_fault_rss=True` flag is the full opt-out; a future
`fd_threshold_per_minion=<int>` kwarg could offer a middle ground.
