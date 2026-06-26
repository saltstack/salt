#!/usr/bin/env python3
"""
Render each timeseries panel from the Salt Monitoring Grafana dashboard to
a PNG, going straight to Prometheus.  Optionally emit a markdown summary
suitable for GitHub Actions' ``$GITHUB_STEP_SUMMARY``.

Why we render here instead of asking Grafana:
  Grafana's "render panel as PNG" endpoint requires the image-renderer
  plugin or a sidecar Chromium container -- both heavy dependencies for
  what is otherwise a fully self-contained CI workflow.  Every metric
  the dashboard displays is in Prometheus already; matplotlib is plenty.

Inputs (all overridable via env / args):
  PROM_URL                 http://127.0.0.1:19090
  DASHBOARD_PATH           grafana/provisioning/dashboards/salt_monitoring.json
  PANELS_DIR               panels/   (output directory for PNGs)
  WINDOW_SECONDS           1800      (range query window, default 30 min)

Outputs:
  * ``{PANELS_DIR}/{id:03d}_{title}.png`` per timeseries panel.
  * With ``--summary`` and ``$GITHUB_STEP_SUMMARY`` set, a markdown
    report listing each rendered panel alongside its path inside the
    workflow's uploaded artifact bundle (with a link to the bundle if
    ``--artifact-url`` was given).  GitHub's step-summary sanitizer
    strips ``data:`` URIs, so inline embedding is not viable -- the
    artifact link is the canonical way to view the rendered graphs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

# matplotlib is required at runtime but only installed in the CI workflow
# (see ``Render Dashboard Panels`` in nightly-stress-test.yml).  The
# salt pylint config insists 3rd-party imports be try/except-gated, but
# this is a standalone helper -- a missing import here is a clear
# user-error and the traceback is the right message.
try:
    import matplotlib  # pylint: disable=3rd-party-module-not-gated

    matplotlib.use("Agg")

    import matplotlib.pyplot as plt  # noqa: E402 pylint: disable=3rd-party-module-not-gated
    from matplotlib.dates import (  # noqa: E402 pylint: disable=3rd-party-module-not-gated
        DateFormatter,
    )
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(
        f"render_panels.py: matplotlib is required but missing ({exc}).  "
        f"Install with: python3 -m pip install matplotlib\n"
    )
    raise

PROM = os.environ.get("PROM_URL", "http://127.0.0.1:19090")
DASHBOARD = Path(
    os.environ.get(
        "DASHBOARD_PATH",
        Path(__file__).parent
        / "grafana"
        / "provisioning"
        / "dashboards"
        / "salt_monitoring.json",
    )
)
OUT_DIR = Path(os.environ.get("PANELS_DIR", "panels"))
WINDOW = int(os.environ.get("WINDOW_SECONDS", "1800"))
STEP = os.environ.get("PROM_STEP", "15s")


def query_range(expr: str, end_ts: float):
    """Run a Prometheus range query.  Returns ``[]`` on any error so a
    missing exporter doesn't abort the whole render."""
    params = urllib.parse.urlencode(
        {
            "query": expr,
            "start": end_ts - WINDOW,
            "end": end_ts,
            "step": STEP,
        }
    )
    url = f"{PROM}/api/v1/query_range?{params}"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            body = json.loads(response.read())
    except (urllib.error.URLError, ConnectionError, TimeoutError, ValueError) as exc:
        print(f"  WARN: {expr!r}: {exc}", file=sys.stderr)
        return []
    if body.get("status") != "success":
        print(f"  WARN: {expr!r}: prometheus returned {body!r}", file=sys.stderr)
        return []
    return body.get("data", {}).get("result", [])


_LEGEND_TOKEN = re.compile(r"\{\{\s*([^{}\s]+)\s*\}\}")


def render_legend(legend_fmt: str, metric: dict) -> str:
    """Apply Grafana's ``{{label}}`` substitution.  Falls back to the
    metric name when no template is given."""
    if not legend_fmt:
        return metric.get("__name__") or ""

    def _repl(match):
        return metric.get(match.group(1), match.group(0))

    return _LEGEND_TOKEN.sub(_repl, legend_fmt)


def _bytes_unit(unit_hint: str) -> bool:
    return unit_hint.lower() in ("bytes", "decbytes", "kbytes", "mbytes", "gbytes")


def render_panel(panel: dict, end_ts: float) -> plt.Figure | None:
    """Return a matplotlib Figure for ``panel``, or ``None`` if no series."""
    targets = panel.get("targets") or []
    if not targets:
        return None

    unit_hint = panel.get("fieldConfig", {}).get("defaults", {}).get("unit") or ""
    is_bytes = _bytes_unit(unit_hint)

    fig, ax = plt.subplots(figsize=(11, 4))
    series_count = 0

    for target in targets:
        expr = (target.get("expr") or "").strip()
        if not expr:
            continue
        legend_fmt = target.get("legendFormat") or ""
        for series in query_range(expr, end_ts):
            metric = series.get("metric", {})
            values = series.get("values", [])
            if not values:
                continue
            label = render_legend(legend_fmt, metric)
            xs = [datetime.fromtimestamp(float(v[0])) for v in values]
            ys = []
            for _, sample in values:
                try:
                    y = float(sample)
                except (TypeError, ValueError):
                    y = float("nan")
                ys.append(y)
            if is_bytes:
                ys = [y / (1024 * 1024) for y in ys]
            ax.plot(xs, ys, label=label, linewidth=1.0)
            series_count += 1

    if series_count == 0:
        plt.close(fig)
        return None

    ax.set_title(panel.get("title") or "panel", fontsize=11)
    if is_bytes:
        ax.set_ylabel("MB")
    ax.xaxis.set_major_formatter(DateFormatter("%H:%M"))
    ax.tick_params(axis="x", rotation=30, labelsize=8)
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(alpha=0.3)
    if series_count <= 15:
        ax.legend(fontsize=7, loc="best", framealpha=0.7)
    fig.tight_layout()
    return fig


def _safe_filename(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text)[:80] or "panel"


def render_all(end_ts: float) -> list[tuple[str, Path]]:
    """Render every timeseries panel.  Returns ``[(title, png_path), ...]``."""
    dash = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rendered: list[tuple[str, Path]] = []
    for panel in dash.get("panels", []):
        if panel.get("type") != "timeseries":
            continue
        title = panel.get("title") or f"panel-{panel.get('id')}"
        print(f"rendering [{panel.get('id')}] {title!r}")
        fig = render_panel(panel, end_ts)
        if fig is None:
            print("  (no data)")
            continue
        path = OUT_DIR / f"{int(panel.get('id', 0)):03d}_{_safe_filename(title)}.png"
        fig.savefig(path, dpi=85, bbox_inches="tight")
        plt.close(fig)
        rendered.append((title, path))
    print(f"\nrendered {len(rendered)} panel(s) to {OUT_DIR}/")
    return rendered


def discover_existing(panels_dir: Path) -> list[tuple[str, Path]]:
    """Walk ``panels_dir`` for PNGs produced by an earlier render step.

    Used by the workflow's separate ``Panel Summary`` step: by the time
    the summary runs, prometheus has already been stopped by the
    ``Snapshot Metrics`` step, so the script cannot re-render --
    instead it reads the PNGs the previous render step produced and
    builds the summary from those.

    Filename convention from :func:`render_all` is
    ``{panel_id:03d}_{safe_title}.png``; the dashboard JSON is used to
    recover the original panel titles so the summary matches the
    Grafana labels exactly.
    """
    if not panels_dir.is_dir():
        print(f"discover_existing: {panels_dir} is not a directory")
        return []
    dash = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    title_by_id: dict[int, str] = {}
    for panel in dash.get("panels", []):
        if panel.get("type") != "timeseries":
            continue
        try:
            pid = int(panel.get("id"))
        except (TypeError, ValueError):
            continue
        title_by_id[pid] = panel.get("title") or f"panel-{pid}"
    found: list[tuple[str, Path]] = []
    for path in sorted(panels_dir.glob("*.png")):
        prefix = path.name.split("_", 1)[0]
        try:
            pid = int(prefix)
        except ValueError:
            # Fall back to filename stem if the prefix isn't a panel id.
            found.append((path.stem, path))
            continue
        title = title_by_id.get(pid, path.stem)
        found.append((title, path))
    print(f"discover_existing: {len(found)} PNG(s) under {panels_dir}/")
    return found


def write_step_summary(
    rendered: list[tuple[str, Path]], artifact_link: str | None
) -> None:
    """Append a markdown report to ``$GITHUB_STEP_SUMMARY`` if set.

    GitHub's step-summary sanitizer **strips ``data:`` URIs** from image
    src attributes (both Markdown ``![](data:...)`` and HTML
    ``<img src="data:...">``), so we cannot reliably embed the PNGs
    inline.  Instead the summary lists each panel alongside its path
    inside the uploaded artifact, and links to the artifact download
    page when one was supplied via ``--artifact-url`` / ``--artifact-name``.

    Future option if GitHub ever allows it: rebuild this to do real
    inline embedding via the Markdown image tag; the tests are
    already in test_dashboard_data.py.
    """
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if not target:
        print("GITHUB_STEP_SUMMARY not set; skipping markdown emit")
        return

    lines = ["## Stress test panels", ""]
    if artifact_link and artifact_link.startswith(("http://", "https://")):
        lines.append(
            f"[Download the full-resolution PNGs from the workflow "
            f"artifact]({artifact_link}) — extract the ZIP and open "
            f"``panels/`` for the images below."
        )
    elif artifact_link:
        lines.append(
            f"Full-resolution PNGs are in the **{artifact_link}** "
            f"workflow artifact -- download it from the run's *Artifacts* "
            f"tab and extract ``panels/``."
        )
    else:
        lines.append(
            "Full-resolution PNGs are in the workflow artifact bundle -- "
            "download it from the run's *Artifacts* tab and extract "
            "``panels/``."
        )
    lines.append("")
    lines.append(
        "_(Inline images are intentionally omitted: GitHub strips "
        "``data:`` URIs from step summaries.  See the artifact above for "
        "the rendered graphs.)_"
    )
    lines.append("")
    lines.append("| Panel | File |")
    lines.append("|-------|------|")
    for title, path in rendered:
        # Use only the basename so it lines up with the artifact's
        # internal ``panels/`` directory regardless of where the
        # workflow happened to write the PNG on the runner.
        lines.append(f"| {title} | `panels/{path.name}` |")
    lines.append("")
    lines.append(f"_{len(rendered)} panel(s) rendered._")

    body = "\n".join(lines) + "\n"
    # pylint: disable=resource-leakage,unspecified-encoding
    # This is a standalone CI helper that doesn't import salt; the
    # salt.utils.files.fopen() guidance does not apply.
    with open(target, "a", encoding="utf-8") as fh:
        fh.write(body)
    print(f"step summary updated: {len(rendered)} panel(s) listed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--end",
        type=float,
        default=None,
        help="end-of-window unix timestamp (default: now)",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="also append a markdown report to $GITHUB_STEP_SUMMARY",
    )
    parser.add_argument(
        "--from-existing",
        action="store_true",
        help=(
            "skip rendering and pick up PNGs already produced by an "
            "earlier render step under PANELS_DIR.  Used by the "
            "workflow's ``Panel Summary`` step, which runs after "
            "prometheus has been stopped"
        ),
    )
    parser.add_argument(
        "--artifact-name",
        default=None,
        help="name of the upload-artifact bundle that carries the PNGs",
    )
    parser.add_argument(
        "--artifact-url",
        default=None,
        help=(
            "absolute URL to the workflow artifact bundle "
            "(e.g. actions/upload-artifact's `artifact-url` output) -- "
            "if given, the summary embeds it as a clickable download link"
        ),
    )
    args = parser.parse_args()

    if args.from_existing:
        rendered = discover_existing(OUT_DIR)
    else:
        end_ts = args.end if args.end is not None else time.time()
        rendered = render_all(end_ts)

    if args.summary:
        # Prefer a real URL when one was passed in (the workflow's
        # actions/upload-artifact ``artifact-url`` output is the
        # canonical source).  Fall back to the artifact bundle name.
        link = args.artifact_url or args.artifact_name
        write_step_summary(rendered, link)

    if args.from_existing or args.summary:
        # Summary-only / discover-only runs never fail the step on an
        # empty result; that information is in the summary text itself.
        return 0
    return 0 if rendered else 1


if __name__ == "__main__":
    sys.exit(main())
