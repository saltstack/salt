"""Instrument a minion to find what state.apply retains.

Replicates the minion-side path of a state.apply call locally (no
master/publisher channel), surrounding it with tracemalloc snapshots.
Prints the top retention sources after the call returns + 60s of
settle time so we see what's still held past the worker's death.

Run INSIDE the minion container with salt mounted editably:

    docker exec rs-single-salt-minion-1 python3 /tmp/retention_probe.py
"""

from __future__ import annotations

import gc
import linecache
import time
import tracemalloc


def human(n):
    for unit in ("B", "KB", "MB"):
        if abs(n) < 1024:
            return f"{n:7.1f} {unit}"
        n /= 1024
    return f"{n:7.1f} GB"


def report(label, baseline_snap, after_snap, top_n=20):
    stats = after_snap.compare_to(baseline_snap, "lineno")
    print(f"\n=== {label}: top {top_n} by size diff ===")
    total_delta = 0
    for stat in stats[:top_n]:
        total_delta += stat.size_diff
        frame = stat.traceback[0]
        line = linecache.getline(frame.filename, frame.lineno).strip()[:60]
        print(
            f"  {human(stat.size_diff):>12}  +{stat.count_diff:>6} objs  "
            f"{frame.filename.rsplit('salt/', 1)[-1]}:{frame.lineno}  {line}"
        )
    print(f"  --- top-{top_n} total: {human(total_delta)}")


def main():
    # Import salt lazily so tracemalloc catches the state.apply allocations.
    tracemalloc.start(25)
    # Warm salt enough that the FIRST allocation isn't the module import.
    import salt.client
    import salt.config
    import salt.loader
    import salt.state

    opts = salt.config.minion_config("/etc/salt/minion")
    opts["file_client"] = "local"  # bypass master for a clean per-call measurement
    opts["file_roots"] = {"base": ["/srv/salt"]}

    # Force loader + grains init before the baseline so we don't count them.
    _ = salt.loader.grains(opts)

    gc.collect()
    gc.collect()
    gc.collect()
    baseline = tracemalloc.take_snapshot()
    rss_before = _rss_kb()

    # Invoke state.apply the same way the minion worker does.  Using
    # salt.client.Caller mimics ``state.apply`` dispatch through the
    # loader.
    caller = salt.client.Caller(mopts=opts)
    try:
        caller.cmd("test.ping")
        # state.apply against one of the SLS files we have; won't error on
        # dry-run mode.
        caller.cmd("state.apply", test=True)
    except Exception as exc:  # noqa: BLE001
        print(f"state.apply raised {exc!r}; measuring retention anyway")

    # Immediate post-call snapshot: captures everything still live right
    # after state.apply returns to the caller.
    gc.collect()
    gc.collect()
    gc.collect()
    immediately = tracemalloc.take_snapshot()
    rss_immed = _rss_kb()
    print(
        f"\nRSS baseline={rss_before} KB  immediately={rss_immed} KB  "
        f"delta={rss_immed - rss_before:+} KB"
    )
    report("state.apply immediately after return", baseline, immediately)

    # +60s snapshot: lets any 60s-TTL cache expire.
    time.sleep(60)
    gc.collect()
    gc.collect()
    gc.collect()
    after60 = tracemalloc.take_snapshot()
    rss_60 = _rss_kb()
    print(f"\nRSS +60s={rss_60} KB  delta_from_baseline={rss_60 - rss_before:+} KB")
    report("state.apply + 60s settle", baseline, after60)

    # +120s snapshot: matches the CI leak-gate window.
    time.sleep(60)
    gc.collect()
    gc.collect()
    gc.collect()
    after120 = tracemalloc.take_snapshot()
    rss_120 = _rss_kb()
    print(f"\nRSS +120s={rss_120} KB  delta_from_baseline={rss_120 - rss_before:+} KB")
    report("state.apply + 120s settle", baseline, after120)


def _rss_kb():
    with open(f"/proc/{__import__('os').getpid()}/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    return -1


if __name__ == "__main__":
    main()
