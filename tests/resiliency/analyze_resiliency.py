#!/usr/bin/env python3
"""
Analyze a resiliency run and emit a single verdict.

Reads:
  - The JSONL results file written by lib/common.sh::record_result,
    one record per fault.  Schema (defined in common.sh):
        ts                  float    unix epoch at record time
        topology            str      single|cluster3|multimaster-*
        scenario            str      human label, e.g. master_restart_sigkill
        outcome             str      recovered | failed | setup_error
                                     | skipped_for_topology
        reconnect_seconds   int      seconds to full recovery; -1 if never
        attempts            int      number of test.ping rounds issued
        missing             list[str] minion ids that didn't answer
        fd_delta            int      sum(fd_after - fd_before) across minions
        rss_kb_delta        int      sum(rss_after - rss_before) across minions
        fault_seconds       int      how long the fault was held
        notes               str      free-text

  - Prometheus (via --prometheus-url) for master-side leak detection.
    Mirrors tests/monitoring/analyze_stats.py: deriv() over a 30m window
    on salt_master_open_fds and salt_master_rss_bytes.

Verdict rules:
  * FAIL if any JSONL record has outcome not in {recovered,
    skipped_for_topology}.
  * FAIL if master fd slope > MASTER_FD_LEAK_PER_MIN / 60 fds/sec
    (env tunable; default 0.5 fds/sec == 30 fds/min).
  * FAIL if master rss slope > 10240 bytes/sec sustained over 30m
    (matches analyze_stats.py).
  * WARN (not FAIL) if any recovered scenario's reconnect_seconds
    exceeds RECONNECT_WARN_SEC (default 60s).

Exit codes:
  0  all scenarios recovered and no leaks detected
  1  at least one scenario failed OR a leak was detected
  2  data missing (results file empty / unreadable, OR prometheus
     unreachable in a CI context where panels would also be empty)

Prometheus-unreachable handling mirrors analyze_stats.py: a single
query failure logs a WARN and is treated as "no data for this metric"
(slope == 0.0).  BUT: if EVERY master-side query comes back empty,
we treat that as the "prometheus is down entirely" signal and exit 2
instead of silently passing -- a CI run with no prometheus produces
blank Grafana panels and a useless step summary, so failing explicitly
is friendlier than a false green.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_PROM_URL = "http://127.0.0.1:19090"
RSS_LEAK_BYTES_PER_SEC = 10240  # same as analyze_stats.py
# Reconnect SLO: a slow-but-recovered run is yellow, not red.
DEFAULT_RECONNECT_WARN_SEC = int(os.environ.get("RECONNECT_WARN_SEC", "60"))
# Master fd leak threshold: expressed as fds/min for operator-friendliness
# in lib/common.sh ($MASTER_FD_LEAK_PER_MIN, default 30) but checked in
# fds/sec against deriv().  30 fds/min / 60 = 0.5 fds/sec.
DEFAULT_MASTER_FD_LEAK_PER_MIN = float(os.environ.get("MASTER_FD_LEAK_PER_MIN", "30"))


def query_prom(prom_url, promql):
    params = urllib.parse.urlencode({"query": promql})
    url = f"{prom_url}/api/v1/query?{params}"
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode())


class PromState:
    """Tracks whether prometheus is reachable at all.

    One ``unreachable`` flag is set the first time a query throws a
    URLError/ConnectionError/TimeoutError; subsequent ``get_slope`` calls
    return 0.0 without re-attempting the network.  ``any_data_seen``
    distinguishes "prometheus responded but has no series for X" from
    "prometheus itself is down".
    """

    def __init__(self, url):
        self.url = url
        self.unreachable = False
        self.any_data_seen = False

    def get_slope(self, metric, duration="30m"):
        if self.unreachable:
            return 0.0
        promql = f"deriv({metric}[{duration}])"
        try:
            data = query_prom(self.url, promql)
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            print(
                f"WARN: prometheus query for {metric!r} failed: {exc}",
                file=sys.stderr,
            )
            self.unreachable = True
            return 0.0
        # ``data.data.result`` is a list of series; we return the max
        # slope seen across series (a leak in ANY master is a leak).
        try:
            results = data["data"]["result"]
        except (KeyError, TypeError):
            return 0.0
        if not results:
            return 0.0
        self.any_data_seen = True
        slopes = []
        for series in results:
            try:
                slopes.append(float(series["value"][1]))
            except (KeyError, IndexError, ValueError):
                continue
        return max(slopes) if slopes else 0.0


def load_results(path):
    """Yield parsed JSON records from a JSONL file.

    Skips blank lines; raises on malformed JSON (a corrupted results
    file is a setup error, not a test failure).
    """
    records = []
    # pylint: disable=resource-leakage
    # Standalone CI analyzer: reads a local JSONL file written by the
    # orchestrator in the same workspace.  Importing salt.utils.files
    # just to get fopen() would pull the full salt stack into this
    # otherwise-dependency-free analyzer script.  The context manager
    # already guarantees close.
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(
                    f"analyze_resiliency: {path}:{lineno}: bad JSON: {exc}"
                )
    return records


def format_table(records):
    """Render the per-scenario table.  Mirrors analyze_stats.py's prose
    style: one line per metric, no box-drawing, grep-friendly."""
    headers = [
        "scenario",
        "outcome",
        "reconnect_s",
        "missing",
        "fd_delta",
        "rss_kb_delta",
    ]
    rows = []
    for r in records:
        missing = r.get("missing") or []
        if isinstance(missing, list):
            missing_s = ",".join(missing) if missing else "-"
        else:
            missing_s = str(missing)
        rows.append(
            [
                r.get("scenario", "?"),
                r.get("outcome", "?"),
                str(r.get("reconnect_seconds", "?")),
                missing_s,
                str(r.get("fd_delta", "?")),
                str(r.get("rss_kb_delta", "?")),
            ]
        )
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [fmt.format(*headers), fmt.format(*["-" * w for w in widths])]
    for row in rows:
        lines.append(fmt.format(*row))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--results", required=True, help="path to results.jsonl")
    ap.add_argument("--topology", required=True, help="topology name (metadata)")
    ap.add_argument(
        "--prometheus-url",
        default=os.environ.get("PROMETHEUS_URL", DEFAULT_PROM_URL),
        help=f"prometheus base URL (default: {DEFAULT_PROM_URL})",
    )
    ap.add_argument(
        "--reconnect-warn-sec",
        type=int,
        default=DEFAULT_RECONNECT_WARN_SEC,
        help="reconnect_seconds above this value emit a WARN (default: 60)",
    )
    ap.add_argument(
        "--master-fd-leak-per-min",
        type=float,
        default=DEFAULT_MASTER_FD_LEAK_PER_MIN,
        help="master open_fds slope FAIL threshold in fds/min (default: 30)",
    )
    # ``--ci`` is set by the GitHub Actions wrapper; it changes the
    # prometheus-unreachable path from "graceful degrade" to "exit 2".
    ap.add_argument(
        "--ci",
        action="store_true",
        default=bool(os.environ.get("CI")),
        help="treat prometheus-unreachable as a setup error (exit 2) "
        "instead of silently degrading (default: CI env var)",
    )
    args = ap.parse_args()

    print(f"--- Salt Resiliency Analysis (topology={args.topology}) ---")

    if not os.path.exists(args.results):
        print(f"FAIL: results file not found: {args.results}", file=sys.stderr)
        return 2
    records = load_results(args.results)
    if not records:
        print(
            f"FAIL: results file empty (no scenarios recorded): {args.results}",
            file=sys.stderr,
        )
        return 2

    print()
    print(format_table(records))
    print()

    # -----------------------------------------------------------------
    # JSONL-level verdict
    # -----------------------------------------------------------------
    PASS_OUTCOMES = {"recovered", "skipped_for_topology"}
    failed_records = [r for r in records if r.get("outcome") not in PASS_OUTCOMES]
    warn_records = [
        r
        for r in records
        if r.get("outcome") == "recovered"
        and isinstance(r.get("reconnect_seconds"), int)
        and r["reconnect_seconds"] > args.reconnect_warn_sec
    ]

    verdict_fail = False

    if failed_records:
        verdict_fail = True
        print("FAIL: scenarios with non-pass outcome:")
        for r in failed_records:
            print(
                f"  - {r.get('scenario','?')}: outcome={r.get('outcome','?')} "
                f"reconnect_s={r.get('reconnect_seconds','?')} "
                f"missing={r.get('missing') or '-'}"
            )

    if warn_records:
        print(
            "WARN: slow recoveries (reconnect_seconds > "
            f"{args.reconnect_warn_sec}s):"
        )
        for r in warn_records:
            print(
                f"  - {r.get('scenario','?')}: reconnect_s="
                f"{r.get('reconnect_seconds','?')}"
            )

    # -----------------------------------------------------------------
    # Prometheus-level verdict (master-side leaks).
    # -----------------------------------------------------------------
    prom = PromState(args.prometheus_url)
    master_fd_slope = prom.get_slope("salt_master_open_fds")
    master_rss_slope = prom.get_slope("salt_master_rss_bytes")

    fd_fail_threshold = args.master_fd_leak_per_min / 60.0
    print(
        f"Master FD slope:  {master_fd_slope:.6f} fds/sec "
        f"(FAIL threshold: {fd_fail_threshold:.6f})"
    )
    print(
        f"Master RSS slope: {master_rss_slope:.2f} bytes/sec "
        f"(FAIL threshold: {RSS_LEAK_BYTES_PER_SEC})"
    )

    if prom.unreachable:
        msg = (
            f"prometheus unreachable at {args.prometheus_url}; "
            "master-side leak checks were skipped"
        )
        if args.ci:
            print(f"FAIL: {msg} (--ci)", file=sys.stderr)
            return 2
        print(f"WARN: {msg}", file=sys.stderr)
    elif not prom.any_data_seen:
        # Prometheus is up but has no series for any master metric.
        # That's the "exporter never started" case; in CI it means the
        # Grafana panels would be blank too, so it's a setup error.
        msg = (
            "prometheus has no salt_master_* series "
            "(fd_exporter likely never started)"
        )
        if args.ci:
            print(f"FAIL: {msg} (--ci)", file=sys.stderr)
            return 2
        print(f"WARN: {msg}", file=sys.stderr)
    else:
        if master_fd_slope > fd_fail_threshold:
            verdict_fail = True
            print(
                f"FAIL: master fd leak: {master_fd_slope:.6f} fds/sec > "
                f"{fd_fail_threshold:.6f}"
            )
        if master_rss_slope > RSS_LEAK_BYTES_PER_SEC:
            verdict_fail = True
            print(
                f"FAIL: master rss leak: {master_rss_slope:.2f} bytes/sec > "
                f"{RSS_LEAK_BYTES_PER_SEC}"
            )

    if verdict_fail:
        print()
        print("VERDICT: FAIL")
        return 1

    print()
    print("VERDICT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
