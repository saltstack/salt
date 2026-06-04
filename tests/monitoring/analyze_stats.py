#!/usr/bin/env python3
import json
import sys
import urllib.parse
import urllib.request

PROM_URL = "http://localhost:19090"


def query_prom(query):
    params = urllib.parse.urlencode({"query": query})
    url = f"{PROM_URL}/api/v1/query?{params}"
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode())


def get_linear_slope(metric_name, duration="30m"):
    # Returns the slope (rate of change per second) over the duration
    query = f"deriv({metric_name}[{duration}])"
    data = query_prom(query)
    try:
        return float(data["data"]["result"][0]["value"][1])
    except (IndexError, KeyError, ValueError):
        return 0.0


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
