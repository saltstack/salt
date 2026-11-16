# `test_baseline_workload_only` silent failure on single/syndic/cluster5

## CI signature (run 43824366115, single topology)

```
test_baseline.py::test_baseline_workload_only FAILED                     [  3%]
```

One line, no `live log call` block, no `--tb=line` output.  The suite then
ran to completion (another ~4 hours) and was finally SIGTERMed at exit 124
before pytest emitted its end-of-session short summary, so the only clue in
CI stdout is that single line.

## Root cause

**Not a failure of `test_baseline_workload_only`.  The test was almost
certainly passing**; what was failing was the results.jsonl recording hook.

`pytest_runtest_makereport` in `tests/resiliency/conftest.py` fired for
every runtest phase (setup / call / teardown) and, on a passing setup phase
(`report.when == "setup" and report.passed == True`), fell through to
the generic "write a row" path:

```python
elif report.passed:
    outcome_str = "recovered"
...
_append_jsonl_row(row)
item._resiliency_recorded = True
```

This wrote an empty-sentinel row (`fd_delta=0, rss_kb_delta=0,
outcome="recovered"`) and then set `_resiliency_recorded = True`.  When the
call phase then fired, the hook's own guard early-returned:

```python
if report.when == "call" and getattr(item, "_resiliency_recorded", False):
    return
```

So **every test with a passing setup had its real deltas and verdict
silently dropped**.  Evidence: `grep -c '"fd_delta": 0' hothot/results.jsonl`
returns `95 / 95` even though the console log shows non-zero deltas for
many scenarios.

The `test_baseline_workload_only` row in results.jsonl shows
`outcome="recovered" reconnect_seconds=-1 fd_delta=0 rss_kb_delta=0 notes=""`
— the empty-sentinel pattern.  The test on hothot PASSED by pytest's
accounting (console shows `baseline_workload_only_600s_ping` RECOVERED +
`PASSED [3%]`).  On single, the pytest banner shows the test FAILED, but
the results.jsonl row has no deltas and no notes because the hook already
wrote the empty-sentinel row during setup phase.

The actual reason single reports `FAILED` where hothot reports `PASSED`
for this test could not be determined from the CI logs we have, because:
  * the per-test `--tb=line` traceback only renders in pytest's
    end-of-session summary, which was cut off by the exit-124 SIGTERM;
  * the live-log `INFO resiliency.topology LEAK` / `RECOVERED` banners
    normally emitted by `assert_reconnect` were not present, meaning the
    test body never reached its second `assert_reconnect(_ping)` call
    before raising.

The most likely scenario: `pytest.fail(f"{label}: LEAK -- {notes}")` at
line 212 of `test_baseline.py` raised, which emits no live-log INFO
message.  The full traceback only renders in the end-of-session summary,
which the SIGTERM ate.

## Fix

Already landed as commit `a6fc74c5d06`:

```diff
-    if report.when not in ("call", "setup"):
+    if report.when == "setup":
+        if not report.failed:
+            return
+    elif report.when != "call":
         return
```

This matches my local-fix diff exactly.  Parallel agent push collision —
discovered on git-fetch.  The sibling fix is identical and correct.

## My additional contribution

Added hook-phase regression tests to
`tests/resiliency/lib/test_stash_merge.py` that pin:

  * passing setup phase writes nothing;
  * failing setup phase writes a `setup_error` row;
  * call phase emits the real deltas from the stash even when prior
    phases fired.

The parallel conftest fix did NOT add this test coverage.  Without the
pin, a future refactor could silently resurrect the empty-sentinel bug.

Verified via `python3 agents/scratch/verify_fix.py`:

```
OK: passing setup writes nothing
OK: failing setup writes setup_error
OK: call phase emits real deltas
OK: passing call emits recovered with real deltas
```

## Outstanding question

Once results.jsonl correctly carries deltas in the next CI run, we will
see WHICH leak-gate path `test_baseline_workload_only` tripped on single
(the in-test slope check at line 198-212, or the second `assert_reconnect`
at line 236-243).  Until then the single-topology failure's root cause is
undetermined — but it's downstream of the recording bug, not the test
itself.
