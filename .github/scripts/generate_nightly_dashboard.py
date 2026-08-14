#!/usr/bin/env python3
"""Generate the salt-nightlies visibility dashboard.

Called from publish-nightly-release.yml on saltstack/salt-nightlies AFTER a
GitHub release for a nightly build has been created. Reads:

  - JUnit XML test-run artifacts downloaded from the triggering nightly.yml
    run (in $JUNIT_DIR, walk recursively for *.xml).
  - Existing history.json on the current branch (gh-pages), if any.
  - Environment variables describing the release being appended.

Produces:

  - Updated history.json (append newest, trim to KEEP_PER_BRANCH per branch).
  - index.html rendered from an inline template.

Trim policy: keep the newest KEEP_PER_BRANCH entries per branch by date.

Test-count parsing is best-effort. Artifact directory names look like:

    testrun-junit-artifacts-<slug>-ci-test-onedir-<transport>-<chunk>-<group>-<ts>

We split by `-` and pull the chunk out by known-position heuristics. If a name
doesn't match, its tests are still counted but under (chunk="unknown",
os="unknown"). Failure to parse never aborts dashboard generation.

No non-stdlib dependencies. Python 3.8+ (stdlib xml.etree, argparse, json).
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

KEEP_PER_BRANCH = 30

# Extract chunk + os slug from artifact directory name.
# Example dirs (actions/download-artifact@v4 creates one dir per artifact):
#   testrun-junit-artifacts-photonos-5-ci-test-onedir-zeromq-unit-1-1786614358
#   testrun-junit-artifacts-ubuntu-22.04-arm64-ci-test-onedir-tcp-functional-2-1786614358
# The <slug> can contain hyphens (photonos-5, ubuntu-22.04-arm64).
# The nox-session `ci-test-onedir` is a fixed literal.
# So: strip prefix + literal session, split remainder.
ARTIFACT_RE = re.compile(
    r"^testrun-junit-artifacts-"
    r"(?P<slug>.+?)"
    r"-(?:ci-test-onedir|ci-test-pkg-download)"
    r"(?:-(?P<transport>zeromq|tcp))?"
    r"(?:\(fips\))?"
    r"-(?P<chunk>[^-]+)"
    r"-(?P<group>\d+)"
    r"-(?P<ts>\d+)"
    r"$"
)


def parse_junit_counts(junit_dir: Path) -> dict:
    """Walk junit_dir, sum test counts per (chunk, slug) bucket.

    Returns:
        {
          "totals": {"tests": N, "failures": N, "errors": N, "skipped": N},
          "by_suite_os": {
             (chunk, slug): {"tests": N, "failures": N, "errors": N, "skipped": N}
          }
        }
    """
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    by_bucket = defaultdict(lambda: {"tests": 0, "failures": 0, "errors": 0, "skipped": 0})

    if not junit_dir.exists():
        return {"totals": totals, "by_suite_os": {}}

    for artifact_dir in sorted(p for p in junit_dir.iterdir() if p.is_dir()):
        m = ARTIFACT_RE.match(artifact_dir.name)
        if m:
            chunk = m.group("chunk")
            slug = m.group("slug")
        else:
            chunk = "unknown"
            slug = "unknown"

        for xml_path in artifact_dir.rglob("*.xml"):
            try:
                root = ET.parse(xml_path).getroot()
            except ET.ParseError:
                continue
            # Root can be <testsuites> (aggregate) or single <testsuite>.
            if root.tag == "testsuites":
                suites = root.findall("testsuite")
            elif root.tag == "testsuite":
                suites = [root]
            else:
                continue
            for ts in suites:
                for k in ("tests", "failures", "errors", "skipped"):
                    n = int(ts.get(k, "0") or "0")
                    totals[k] += n
                    by_bucket[(chunk, slug)][k] += n

    return {
        "totals": totals,
        "by_suite_os": {
            f"{chunk}|{slug}": counts for (chunk, slug), counts in sorted(by_bucket.items())
        },
    }


def load_history(path: Path) -> list:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        if isinstance(data, list):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return []


def trim_history(history: list, keep_per_branch: int) -> list:
    """Keep newest N entries per branch, sorted by date desc within branch."""
    per_branch = defaultdict(list)
    for entry in history:
        per_branch[entry.get("branch", "unknown")].append(entry)

    trimmed = []
    for branch, entries in per_branch.items():
        entries.sort(key=lambda e: e.get("date", ""), reverse=True)
        trimmed.extend(entries[:keep_per_branch])

    # Return sorted by date desc across branches (newest first for display).
    trimmed.sort(key=lambda e: e.get("date", ""), reverse=True)
    return trimmed


def render_index_html(history: list) -> str:
    """Compact table with per-row expand for suite×os breakdown."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows_html_parts = []
    for idx, e in enumerate(history):
        overall_status = e.get("overall_status", "unknown")
        status_cls = "ok" if overall_status == "success" else ("fail" if overall_status == "failure" else "pending")
        counts = e.get("test_counts", {}) or {}
        totals = counts.get("totals", {}) or {}
        tests = totals.get("tests", 0)
        failures = totals.get("failures", 0)
        errors = totals.get("errors", 0)
        by_suite_os = counts.get("by_suite_os", {}) or {}

        # Compact per-suite pills (aggregate over OS)
        per_suite = defaultdict(lambda: {"tests": 0, "failures": 0, "errors": 0})
        for key, c in by_suite_os.items():
            suite = key.split("|", 1)[0]
            per_suite[suite]["tests"] += c.get("tests", 0)
            per_suite[suite]["failures"] += c.get("failures", 0)
            per_suite[suite]["errors"] += c.get("errors", 0)

        pills = " ".join(
            f'<span class="pill" title="{html.escape(s)}: {c["tests"]} tests, {c["failures"]} fail, {c["errors"]} err">'
            f'{html.escape(s[:1].upper())}:{c["tests"]}</span>'
            for s, c in sorted(per_suite.items())
        )

        # Detail table
        detail_rows = "".join(
            f'<tr><td>{html.escape(k.split("|", 1)[0])}</td><td>{html.escape(k.split("|", 1)[1] if "|" in k else "unknown")}</td>'
            f'<td>{c.get("tests", 0)}</td><td>{c.get("failures", 0)}</td><td>{c.get("errors", 0)}</td><td>{c.get("skipped", 0)}</td></tr>'
            for k, c in sorted(by_suite_os.items())
        )
        detail_html = (
            f'<table class="detail"><thead><tr><th>suite</th><th>os</th>'
            f'<th>tests</th><th>fail</th><th>err</th><th>skip</th></tr></thead>'
            f'<tbody>{detail_rows}</tbody></table>'
            if by_suite_os else '<em>no test-run artifacts parsed</em>'
        )

        release_url = html.escape(e.get("release_url", "#"))
        run_url = html.escape(e.get("nightly_run_url", "#"))
        rows_html_parts.append(
            f'<tr class="row {status_cls}" onclick="toggle(\'d{idx}\')">'
            f'<td>{html.escape(e.get("date", ""))}</td>'
            f'<td>{html.escape(e.get("branch", ""))}</td>'
            f'<td><code>{html.escape(e.get("salt_version", ""))}</code></td>'
            f'<td class="status">{html.escape(overall_status)}</td>'
            f'<td>{tests:,}</td>'
            f'<td>{failures + errors}</td>'
            f'<td class="pills">{pills}</td>'
            f'<td><a href="{release_url}" onclick="event.stopPropagation()">release</a> · '
            f'<a href="{run_url}" onclick="event.stopPropagation()">run</a></td>'
            f'</tr>'
            f'<tr id="d{idx}" class="detail-row" style="display:none"><td colspan="8">{detail_html}</td></tr>'
        )

    rows_html = "\n".join(rows_html_parts) if rows_html_parts else '<tr><td colspan="8"><em>no history yet</em></td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Salt Nightlies</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2em; color: #222; }}
  h1 {{ font-size: 1.5em; margin-bottom: 0.3em; }}
  .subhead {{ color: #666; font-size: 0.9em; margin-bottom: 1.5em; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.9em; }}
  th, td {{ padding: 0.4em 0.6em; text-align: left; border-bottom: 1px solid #eee; }}
  th {{ background: #f6f8fa; font-weight: 600; }}
  tr.row {{ cursor: pointer; }}
  tr.row:hover {{ background: #f9fafb; }}
  tr.row.ok .status {{ color: #1a7f37; font-weight: 600; }}
  tr.row.fail .status {{ color: #cf222e; font-weight: 600; }}
  tr.row.pending .status {{ color: #9a6700; }}
  .pill {{ display: inline-block; padding: 1px 6px; margin-right: 3px; background: #eaeef2; border-radius: 8px; font-size: 0.8em; font-family: monospace; }}
  .pills {{ min-width: 200px; }}
  code {{ font-size: 0.85em; background: #f6f8fa; padding: 1px 4px; border-radius: 3px; }}
  a {{ color: #0969da; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .detail {{ margin: 0.5em 0 0.5em 1em; width: auto; font-size: 0.85em; }}
  .detail th, .detail td {{ border-bottom: 1px solid #f0f0f0; }}
</style>
<script>
  function toggle(id) {{
    var el = document.getElementById(id);
    el.style.display = el.style.display === 'none' ? 'table-row' : 'none';
  }}
</script>
</head>
<body>
<h1>Salt Nightlies</h1>
<div class="subhead">Recent nightly builds. Click a row to expand suite × OS breakdown. Updated {now}.</div>
<table>
<thead>
<tr>
  <th>date</th><th>branch</th><th>salt version</th><th>status</th>
  <th>tests</th><th>fail+err</th><th>by suite</th><th>links</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", type=Path, required=True, help="Path to history.json (read/write)")
    ap.add_argument("--index", type=Path, required=True, help="Path to index.html (write)")
    ap.add_argument("--junit-dir", type=Path, required=True, help="Directory of downloaded JUnit artifacts")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--branch", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--salt-version", default="")
    ap.add_argument("--nightly-run-url", required=True)
    ap.add_argument("--release-url", required=True)
    ap.add_argument("--overall-status", required=True, help="success | failure | pending")
    ap.add_argument("--artifact-count", type=int, default=0)
    args = ap.parse_args()

    counts = parse_junit_counts(args.junit_dir)
    entry = {
        "date": args.date,
        "branch": args.branch,
        "tag": args.tag,
        "commit": args.commit,
        "salt_version": args.salt_version,
        "nightly_run_url": args.nightly_run_url,
        "release_url": args.release_url,
        "overall_status": args.overall_status,
        "artifact_count": args.artifact_count,
        "test_counts": counts,
    }

    history = load_history(args.history)
    # Replace any existing entry with same tag (idempotent re-runs).
    history = [e for e in history if e.get("tag") != args.tag]
    history.append(entry)
    history = trim_history(history, KEEP_PER_BRANCH)

    args.history.write_text(json.dumps(history, indent=2) + "\n")
    args.index.write_text(render_index_html(history))
    print(f"wrote {args.history} ({len(history)} entries)")
    print(f"wrote {args.index}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
