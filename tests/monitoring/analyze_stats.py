#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Use the IPv4 loopback explicitly.  Newer Ubuntu runners resolve
# ``localhost`` to ``::1`` first; if prometheus only bound the IPv4
# host port (Docker's default for ``19090:9090``), the IPv6 attempt
# returns ``connection refused`` and the urllib fallback to IPv4 is
# fast enough that the failure can look like prometheus is offline
# entirely.  Going straight to ``127.0.0.1`` avoids the ambiguity.
PROM_URL = "http://127.0.0.1:19090"

# Warm-up: data from the first WARMUP_SECONDS of a stress run is ignored
# by the leak check.  While the master starts up its RSS climbs (workers
# fork, caches fill, the first highstates run) and that ramp-up looks
# like a leak to a linear fit, which made the nightly fail on RSS slope.
# The first ~5 minutes are known to be unusable; 10 minutes leaves a
# margin.  Override with ``STRESS_WARMUP_SECONDS`` if that needs tuning.
WARMUP_SECONDS = int(os.environ.get("STRESS_WARMUP_SECONDS", 10 * 60))

# Master RSS slope (bytes/sec) above which the run fails.  Master RSS is not
# flat even without a leak: it oscillates by a few hundred MB with a period
# of about 6 minutes, so the fit over a window of a few periods keeps some
# noise.  Two 30m runs measured about 13 and 7 KB/sec after the warm-up, so
# the limit is 15 KB/sec (it was 10 KB/sec).
MASTER_RSS_SLOPE_LIMIT = 15 * 1024

# Smallest slice of data (the end of the run) the check will judge on.
# Fewer points make the slope too noisy to compare with the thresholds.
MIN_ANALYSIS_SECONDS = 5 * 60

# The workflow's shortest run (nightly-stress-test.yml ``duration``
# options) must be at least WARMUP_SECONDS + MIN_ANALYSIS_SECONDS = 15m.
# Keep the two in step.
#
# The workflow exports ``STRESS_START_EPOCH`` when the stress starts; the
# slope window then covers everything after ``start + WARMUP_SECONDS``
# (a 15m run is judged on its last 5m, a 60m run on its last 50m).
# Without it the window is MIN_ANALYSIS_SECONDS, the one span that no
# allowed run overlaps with the warm-up.


def query_prom(query):
    params = urllib.parse.urlencode({"query": query})
    url = f"{PROM_URL}/api/v1/query?{params}"
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode())


def get_elapsed_seconds():
    """Seconds since the stress run started, or ``None`` if unknown."""
    start = os.environ.get("STRESS_START_EPOCH")
    if not start:
        return None
    try:
        return int(time.time() - float(start))
    except ValueError:
        return None


def get_slope_window():
    """
    Prometheus range-selector duration for the slope check: everything
    after the warm-up period at the start of the stress run.
    """
    elapsed = get_elapsed_seconds()
    if elapsed is None:
        return f"{MIN_ANALYSIS_SECONDS}s"
    return f"{max(elapsed - WARMUP_SECONDS, MIN_ANALYSIS_SECONDS)}s"


def get_linear_slope(metric_name, duration=None):
    """
    Slope (rate-of-change per second) of ``metric_name`` over the recent
    ``duration``.  Returns 0.0 if prometheus is unreachable or has no
    series for the metric, so a missing exporter doesn't crash the
    analyzer -- the threshold checks downstream will simply see no
    leak.
    """
    duration = duration or get_slope_window()
    query = f"deriv({metric_name}[{duration}])"
    try:
        data = query_prom(query)
    except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
        print(
            f"WARN: prometheus query for {metric_name!r} failed: {exc}", file=sys.stderr
        )
        return 0.0
    try:
        return float(data["data"]["result"][0]["value"][1])
    except (IndexError, KeyError, ValueError):
        return 0.0


def main():
    print("--- Salt Stress Test Analysis ---")
    print(f"Slope window (warm-up of {WARMUP_SECONDS}s excluded): {get_slope_window()}")

    # 1. Check for zombie processes (process count growth)
    master_procs_slope = get_linear_slope("salt_master_process_count")
    api_procs_slope = get_linear_slope("salt_api_process_count")

    # 2. Check for memory leaks
    master_rss_slope = get_linear_slope("salt_master_rss_bytes")
    api_rss_slope = get_linear_slope("salt_api_rss_bytes")

    # 3. Check for FD leaks
    master_fds_slope = get_linear_slope("salt_master_open_fds")
    api_fds_slope = get_linear_slope("salt_api_open_fds")

    failed = False

    print(f"Master RSS Slope: {master_rss_slope:.2f} bytes/sec")
    print(f"API RSS Slope: {api_rss_slope:.2f} bytes/sec")
    print(f"Master FD Slope: {master_fds_slope:.6f} fds/sec")
    print(f"Master Proc Slope: {master_procs_slope:.6f} procs/sec")

    # Thresholds
    # Memory: a slope above the limit after the warm-up might indicate a real leak
    if master_rss_slope > MASTER_RSS_SLOPE_LIMIT:
        print("FAIL: Master memory leak detected!")
        failed = True

    if master_procs_slope > 0.001:  # Sustained growth in process count
        print("FAIL: Master process/zombie leak detected!")
        failed = True

    if master_fds_slope > 0.01:  # Sustained growth in FDs
        print("FAIL: Master file descriptor leak detected!")
        failed = True

    if failed:
        sys.exit(1)

    print("SUCCESS: No significant resource leaks detected.")
    sys.exit(0)


if __name__ == "__main__":
    main()
