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

Test outcomes are classified per <testcase>:
  - failed:  has <failure> or <error>
  - flaky:   either
             (a) passed but has <rerunFailure>/<rerunError> children
                 (pytest-rerunfailures embeds retry outcomes inline), or
             (b) failed in the main JUnit file but the sibling
                 test-results-<X>-rerun.xml re-ran the same (classname, name)
                 and it passed or was skipped. This is Salt CI's convention:
                 the initial pytest process emits failures; a follow-up
                 pytest --last-failed run uploads a `-rerun.xml`, and the
                 overall pipeline is considered green when the rerun clears
                 the failure. Ignoring the rerun would show green nightlies
                 with false "failed" counts.
  - skipped: has <skipped>
  - passed:  none of the above

`tests` is the count of every <testcase> across all JUnit files (executions).
The same logical test running on N OS slugs / transports / FIPS variants
contributes N to `tests`. `unique` is the deduplicated count of distinct
(classname, name) tuples across all artifacts -- suite coverage rather than
throughput.

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


def _empty_bucket() -> dict:
    # tests    = total testcase executions (sum across all suites/artifacts)
    # failed   = testcase had <failure> or <error> and no successful rerun
    # flaky    = testcase passed but has <rerunFailure> / <rerunError> children
    #            (pytest-rerunfailures marks tests that failed then passed on retry)
    # skipped  = testcase has <skipped>
    # passed   = tests - failed - flaky - skipped (derived, kept for clarity)
    return {"tests": 0, "failed": 0, "flaky": 0, "skipped": 0, "passed": 0}


def _classify_testcase(tc: ET.Element) -> str:
    """Return one of: failed, flaky, skipped, passed."""
    if tc.find("failure") is not None or tc.find("error") is not None:
        return "failed"
    if tc.find("skipped") is not None:
        return "skipped"
    # rerunFailure / rerunError present but no final failure => flaky pass
    # (pytest-rerunfailures embeds the retry outcomes inside a single testcase).
    if tc.find("rerunFailure") is not None or tc.find("rerunError") is not None:
        return "flaky"
    return "passed"


def _pair_xml_files(artifact_dir: Path):
    """Group XML files in artifact_dir into (main_xml, rerun_xml_or_none) pairs.

    Salt CI re-runs failed tests separately and uploads a sibling
    `test-results-<X>-rerun.xml` alongside the initial `test-results-<X>.xml`.
    Walking `*.xml` naively would count the retried tests twice and record
    every original failure even when the rerun made the overall job succeed.
    """
    mains: dict = {}
    reruns: dict = {}
    for xml in artifact_dir.rglob("*.xml"):
        name = xml.name
        if name.endswith("-rerun.xml"):
            reruns[name[: -len("-rerun.xml")]] = xml
        elif name.endswith(".xml"):
            mains[name[: -len(".xml")]] = xml
    for base, main in mains.items():
        yield main, reruns.get(base)
    # Rerun files without a matching main are unusual; count them standalone.
    for base, rerun in reruns.items():
        if base not in mains:
            yield rerun, None


def parse_junit_counts(junit_dir: Path) -> dict:
    """Walk junit_dir, aggregate test counts per (chunk, slug) bucket.

    Returns:
        {
          "totals":     {tests, failed, flaky, skipped, passed, unique},
          "by_suite_os": {
             "<chunk>|<slug>": {tests, failed, flaky, skipped, passed}
          }
        }

    Notes:
      - `tests` counts every `<testcase>` occurrence that actually ran --
        passed, failed, or flaky. Skipped testcases are counted separately
        under `skipped` and are NOT included in `tests` (they never
        executed a test body; pytest skipped them due to a marker or
        missing fixture). This matches how CI operators think of "tests
        that ran" vs "tests that were collected but excluded".
      - The same logical test running on multiple OS slugs / transports /
        FIPS variants each add to `tests`.
      - `unique` is the deduplicated count of distinct `(classname, name)`
        tuples across ALL artifacts (excluding skipped). It is a top-level
        total only; the per-bucket breakdown stays as executions since
        that maps cleanly onto how CI is scheduled.
    """
    totals = _empty_bucket()
    by_bucket: dict = defaultdict(_empty_bucket)
    unique_ids: set = set()

    if not junit_dir.exists():
        return {"totals": {**totals, "unique": 0}, "by_suite_os": {}}

    # Dedupe re-run job artifact uploads. When a GH Actions test job is retried
    # (either by the workflow's re-run of failed jobs, or by an operator
    # clicking "Re-run failed jobs"), the second attempt uploads its JUnit
    # results as a *new* artifact directory with the same
    # (slug, transport, chunk, group) but a fresher <ts>. Walking both would
    # double-count that chunk's tests. Keep only the highest-<ts> upload per
    # (slug, transport, chunk, group). Dirs whose names don't match the schema
    # are always kept (their content classification falls into the "unknown"
    # bucket which we don't try to dedupe).
    latest_dir: dict = {}
    unmatched_dirs: list = []
    for d in sorted(p for p in junit_dir.iterdir() if p.is_dir()):
        m = ARTIFACT_RE.match(d.name)
        if not m:
            unmatched_dirs.append(d)
            continue
        key = (
            m.group("slug"),
            m.group("transport") or "",
            m.group("chunk"),
            m.group("group"),
        )
        ts = int(m.group("ts"))
        existing = latest_dir.get(key)
        if existing is None or ts > existing[0]:
            latest_dir[key] = (ts, d, m)
    ordered = [(d, m) for (_ts, d, m) in latest_dir.values()]
    ordered += [(d, None) for d in unmatched_dirs]

    for artifact_dir, m in ordered:
        if m:
            chunk = m.group("chunk")
            slug = m.group("slug")
        else:
            chunk = "unknown"
            slug = "unknown"

        for main_xml, rerun_xml in _pair_xml_files(artifact_dir):
            # Build (classname, name) -> classification map from the rerun
            # file first; then when we see a `failed` in the main file whose
            # (classname, name) also appears in the rerun with a non-failed
            # outcome, reclassify it as `flaky` -- the retry succeeded (or
            # was skipped due to an environmental condition), which is why
            # Salt CI considers the pipeline green.
            rerun_outcomes: dict = {}
            if rerun_xml is not None:
                try:
                    rroot = ET.parse(rerun_xml).getroot()
                except ET.ParseError:
                    rroot = None
                if rroot is not None:
                    for tc in rroot.iter("testcase"):
                        key = (tc.get("classname") or "", tc.get("name") or "")
                        rerun_outcomes[key] = _classify_testcase(tc)

            try:
                root = ET.parse(main_xml).getroot()
            except ET.ParseError:
                continue
            for tc in root.iter("testcase"):
                outcome = _classify_testcase(tc)
                key = (tc.get("classname") or "", tc.get("name") or "")
                if outcome == "failed" and key in rerun_outcomes:
                    rer = rerun_outcomes[key]
                    if rer in ("passed", "skipped"):
                        outcome = "flaky"
                    # rer == "failed" -> keep as failed
                # `tests` = testcases that actually ran (passed/failed/flaky).
                # Skipped are counted in the `skipped` bucket but not `tests`.
                if outcome != "skipped":
                    totals["tests"] += 1
                    by_bucket[(chunk, slug)]["tests"] += 1
                totals[outcome] += 1
                by_bucket[(chunk, slug)][outcome] += 1
                cls, name = key
                if outcome != "skipped" and (cls or name):
                    unique_ids.add(key)

    return {
        "totals": {**totals, "unique": len(unique_ids)},
        "by_suite_os": {
            f"{chunk}|{slug}": counts
            for (chunk, slug), counts in sorted(by_bucket.items())
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
        status_cls = (
            "ok"
            if overall_status == "success"
            else ("fail" if overall_status == "failure" else "pending")
        )
        counts = e.get("test_counts", {}) or {}
        totals = counts.get("totals", {}) or {}
        tests = totals.get("tests", 0)
        unique = totals.get("unique", 0)
        by_suite_os = counts.get("by_suite_os", {}) or {}

        # Per-OS table: aggregate every "chunk|slug" bucket by the slug
        # (i.e. sum all suite chunks that ran on the same OS).
        per_os: dict = defaultdict(
            lambda: {"tests": 0, "flaky": 0, "failed": 0, "skipped": 0}
        )
        for key, c in by_suite_os.items():
            os_name = key.split("|", 1)[1] if "|" in key else "unknown"
            per_os[os_name]["tests"] += c.get("tests", 0)
            per_os[os_name]["flaky"] += c.get("flaky", 0)
            per_os[os_name]["failed"] += c.get(
                "failed", c.get("failures", 0) + c.get("errors", 0)
            )
            per_os[os_name]["skipped"] += c.get("skipped", 0)
        per_os_rows = "".join(
            f"<tr>"
            f"<td>{html.escape(os_name)}</td>"
            f'<td>{c["tests"]:,}</td>'
            f'<td class="num-flaky">{c["flaky"]}</td>'
            f'<td class="num-fail">{c["failed"]}</td>'
            f'<td>{c["skipped"]:,}</td>'
            f"</tr>"
            for os_name, c in sorted(per_os.items())
        )
        per_os_html = (
            f'<table class="detail"><thead><tr>'
            f"<th>os</th><th>tests</th><th>flaky</th><th>failed</th><th>skip</th>"
            f"</tr></thead>"
            f"<tbody>{per_os_rows}</tbody></table>"
            if per_os
            else ""
        )

        # Detail table (per suite × os).
        detail_rows = "".join(
            f"<tr>"
            f'<td>{html.escape(k.split("|", 1)[0])}</td>'
            f'<td>{html.escape(k.split("|", 1)[1] if "|" in k else "unknown")}</td>'
            f'<td>{c.get("tests", 0):,}</td>'
            f'<td class="num-flaky">{c.get("flaky", 0)}</td>'
            f'<td class="num-fail">{c.get("failed", c.get("failures", 0) + c.get("errors", 0))}</td>'
            f'<td>{c.get("skipped", 0)}</td>'
            f"</tr>"
            for k, c in sorted(by_suite_os.items())
        )
        detail_by_suite_html = (
            f'<table class="detail"><thead><tr>'
            f"<th>suite</th><th>os</th>"
            f"<th>tests</th><th>flaky</th><th>failed</th><th>skip</th>"
            f"</tr></thead>"
            f"<tbody>{detail_rows}</tbody></table>"
            if by_suite_os
            else "<em>no test-run artifacts parsed</em>"
        )

        # Side-by-side: suite × OS on the left, per-OS on the right.
        left_pane = (
            '<div class="detail-pane">'
            '<div class="detail-section-title">Per suite &times; OS</div>'
            f"{detail_by_suite_html}"
            "</div>"
        )
        right_pane = (
            (
                '<div class="detail-pane">'
                '<div class="detail-section-title">Per OS</div>'
                f"{per_os_html}"
                "</div>"
            )
            if per_os_html
            else ""
        )
        detail_html = f'<div class="detail-flex">{left_pane}{right_pane}</div>'

        release_url = html.escape(e.get("release_url", "#"))
        run_url = html.escape(e.get("nightly_run_url", "#"))
        salt_version = e.get("salt_version") or "unknown"
        # `unique` cell: only render a value when we have it; older rows show —.
        unique_cell = f"{unique:,}" if unique else '<span class="dim">—</span>'
        rows_html_parts.append(
            f'<tr class="row {status_cls}" onclick="toggle(\'d{idx}\')">'
            f'<td>{html.escape(e.get("date", ""))}</td>'
            f'<td>{html.escape(e.get("branch", ""))}</td>'
            f"<td><code>{html.escape(salt_version)}</code></td>"
            f'<td class="status">{html.escape(overall_status)}</td>'
            f"<td>{tests:,}</td>"
            f"<td>{unique_cell}</td>"
            f'<td><a href="{release_url}" onclick="event.stopPropagation()">release</a> · '
            f'<a href="{run_url}" onclick="event.stopPropagation()">run</a></td>'
            f"</tr>"
            f'<tr id="d{idx}" class="detail-row" style="display:none"><td colspan="7">{detail_html}</td></tr>'
        )

    rows_html = (
        "\n".join(rows_html_parts)
        if rows_html_parts
        else '<tr><td colspan="7"><em>no history yet</em></td></tr>'
    )

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
  .num-fail {{ color: #cf222e; font-weight: 600; }}
  .num-flaky {{ color: #9a6700; }}
  .dim {{ color: #999; }}
  code {{ font-size: 0.85em; background: #f6f8fa; padding: 1px 4px; border-radius: 3px; }}
  a {{ color: #0969da; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .detail {{ margin: 0.5em 0 0.5em 0; width: auto; font-size: 0.85em; }}
  .detail th, .detail td {{ border-bottom: 1px solid #f0f0f0; }}
  .detail-section-title {{ margin: 0.75em 0 0.25em 0; font-weight: 600; font-size: 0.85em; color: #57606a; }}
  .detail-flex {{ display: flex; gap: 2em; align-items: flex-start; margin-left: 1em; flex-wrap: wrap; }}
  .detail-pane {{ min-width: 20em; }}
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
<div class="subhead">Recent nightly builds. `tests` = total testcase executions across all axes (OS &times; transport &times; FIPS &times; chunk); `unique` = distinct (classname, name) tuples. Click a row to expand the per-suite&nbsp;&times;&nbsp;OS breakdown (tests, flaky, failed, skip). Updated {now}.</div>
<table>
<thead>
<tr>
  <th>date</th><th>branch</th><th>salt version</th><th>status</th>
  <th>tests</th><th>unique</th><th>links</th>
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
    ap.add_argument(
        "--history", type=Path, required=True, help="Path to history.json (read/write)"
    )
    ap.add_argument(
        "--index", type=Path, required=True, help="Path to index.html (write)"
    )
    ap.add_argument(
        "--junit-dir",
        type=Path,
        required=True,
        help="Directory of downloaded JUnit artifacts",
    )
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--branch", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--salt-version", default="")
    ap.add_argument("--nightly-run-url", required=True)
    ap.add_argument("--release-url", required=True)
    ap.add_argument(
        "--overall-status", required=True, help="success | failure | pending"
    )
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
