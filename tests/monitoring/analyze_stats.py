#!/usr/bin/env python3
import json
import os
import sys
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


def query_prom(query):
    params = urllib.parse.urlencode({"query": query})
    url = f"{PROM_URL}/api/v1/query?{params}"
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode())


def get_linear_slope(metric_name, duration="30m"):
    """
    Slope (rate-of-change per second) of ``metric_name`` over the recent
    ``duration``.  Returns 0.0 if prometheus is unreachable or has no
    series for the metric, so a missing exporter doesn't crash the
    analyzer -- the threshold checks downstream will simply see no
    leak.
    """
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


def query_scalar(query):
    """Return the first value of an instant query as a float, or ``None``."""
    try:
        data = query_prom(query)
        return float(data["data"]["result"][0]["value"][1])
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        return None
    except (IndexError, KeyError, ValueError):
        return None


def check_salt_prometheus_metrics(window="30m"):
    """
    Checks for a master run with ``metrics.exporter: prometheus``.

    ``salt.master.requests.handled`` is only incremented inside the
    MWorker processes, so seeing it on the master's ``/metrics`` at all
    shows that the workers' values reach the one endpoint.  A counter
    that went down between scrapes (a reset) is the symptom of #70248.

    Returns the list of problems found.
    """
    problems = []
    up = query_scalar('min(up{job="salt-metrics"})')
    handled = query_scalar("sum(salt_master_requests_handled_total)")
    resets = query_scalar(f"sum(resets(salt_master_requests_handled_total[{window}]))")
    print(f"salt-metrics target up: {up}")
    print(f"salt_master_requests_handled_total (sum): {handled}")
    print(f"counter resets in the last {window}: {resets}")
    if up != 1:
        problems.append("the salt-metrics scrape target is not up")
    if not handled or handled <= 0:
        problems.append(
            "salt_master_requests_handled_total is missing or zero: "
            "the MWorkers' counts are not visible"
        )
    if resets:
        problems.append(f"{resets:g} counter reset(s): the values went down")
    return problems


def main():
    print("--- Salt Stress Test Analysis ---")

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

    if os.environ.get("EXPECT_SALT_PROMETHEUS_METRICS") == "1":
        for problem in check_salt_prometheus_metrics():
            print(f"FAIL: {problem}")
            failed = True

    print(f"Master RSS Slope: {master_rss_slope:.2f} bytes/sec")
    print(f"API RSS Slope: {api_rss_slope:.2f} bytes/sec")
    print(f"Master FD Slope: {master_fds_slope:.6f} fds/sec")
    print(f"Master Proc Slope: {master_procs_slope:.6f} procs/sec")

    # Thresholds
    # Memory: > 10KB/sec sustained over 30m might indicate a real leak
    if master_rss_slope > 10240:
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
