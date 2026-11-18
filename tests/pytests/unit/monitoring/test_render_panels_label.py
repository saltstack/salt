"""
Regression tests for the run-provenance labeling in
``tests/monitoring/render_panels.py``.

These tests load ``render_panels.py`` as a module directly (it's a
standalone CI helper, not part of the ``salt`` package), stub the
Prometheus range query so no HTTP traffic is required, and exercise
three contracts:

1. With the ``RESILIENCY_PANEL_*`` env vars set, ``render_panel``
   returns a Figure whose ``_suptitle`` matches the documented
   ``<topology> / run <run_id> / <sha[:12]> / started <iso>`` format.
2. With none of the env vars set (local-dev), ``render_panel`` returns
   a Figure with no suptitle so local renders don't carry bogus
   "unknown / unknown" headers.
3. ``write_step_summary`` writes a provenance block header
   (``## Resiliency Run — ...``) when envs are set, and falls back to
   ``## Stress test panels`` otherwise.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")


REPO_ROOT = Path(__file__).resolve().parents[4]
RENDER_PANELS_PATH = REPO_ROOT / "tests" / "monitoring" / "render_panels.py"


@pytest.fixture(scope="module")
def render_panels():
    """Load render_panels.py as a module from its path."""
    spec = importlib.util.spec_from_file_location(
        "render_panels_module", RENDER_PANELS_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def clean_env(monkeypatch):
    """Scrub the provenance env vars so each test starts from a known state."""
    for name in (
        "RESILIENCY_PANEL_TOPOLOGY",
        "RESILIENCY_PANEL_RUN_ID",
        "RESILIENCY_PANEL_SHA",
        "RESILIENCY_PANEL_STARTED_AT",
        "TOPOLOGY",
        "GITHUB_RUN_ID",
        "GITHUB_SHA",
        "GITHUB_REPOSITORY",
        "GITHUB_STEP_SUMMARY",
    ):
        monkeypatch.delenv(name, raising=False)


def _synthetic_series():
    """Return a 1-series, 3-sample response matching Prometheus' range-query
    JSON shape so ``render_panel`` has a figure to draw."""
    return [
        {
            "metric": {"instance": "fake:9100"},
            "values": [
                ["1700000000", "1.0"],
                ["1700000030", "2.0"],
                ["1700000060", "3.0"],
            ],
        }
    ]


def _minimal_panel():
    return {
        "title": "Master Memory (Process vs Container)",
        "type": "timeseries",
        "fieldConfig": {"defaults": {"unit": "bytes"}},
        "targets": [
            {"expr": "process_resident_memory_bytes", "legendFormat": "{{instance}}"}
        ],
    }


def test_render_panel_stamps_suptitle_from_env(render_panels, clean_env, monkeypatch):
    monkeypatch.setenv("RESILIENCY_PANEL_TOPOLOGY", "cluster3")
    monkeypatch.setenv("RESILIENCY_PANEL_RUN_ID", "44002386163")
    monkeypatch.setenv(
        "RESILIENCY_PANEL_SHA", "88d8ce71f58cDEADBEEFCAFE1234567890ABCDEF"
    )
    monkeypatch.setenv("RESILIENCY_PANEL_STARTED_AT", "2026-11-17T02:21:43Z")
    monkeypatch.setattr(
        render_panels, "query_range", lambda expr, end_ts: _synthetic_series()
    )

    fig = render_panels.render_panel(_minimal_panel(), end_ts=1700000060.0)
    assert fig is not None
    assert fig._suptitle is not None
    text = fig._suptitle.get_text()
    assert text == (
        "cluster3 / run 44002386163 / 88d8ce71f58c / started 2026-11-17T02:21:43Z"
    ), text
    matplotlib.pyplot.close(fig)


def test_render_panel_falls_back_to_github_envs(render_panels, clean_env, monkeypatch):
    monkeypatch.setenv("TOPOLOGY", "single")
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")
    monkeypatch.setenv("GITHUB_SHA", "abcdef0123456789aaaaaaaaaaaaaaaaaaaaaaaa")
    monkeypatch.setenv("RESILIENCY_PANEL_STARTED_AT", "2026-01-02T03:04:05Z")
    monkeypatch.setattr(
        render_panels, "query_range", lambda expr, end_ts: _synthetic_series()
    )

    fig = render_panels.render_panel(_minimal_panel(), end_ts=1700000060.0)
    assert fig is not None
    text = fig._suptitle.get_text()
    assert text == (
        "single / run 12345 / abcdef012345 / started 2026-01-02T03:04:05Z"
    ), text
    matplotlib.pyplot.close(fig)


def test_render_panel_no_env_no_suptitle(render_panels, clean_env, monkeypatch):
    monkeypatch.setattr(
        render_panels, "query_range", lambda expr, end_ts: _synthetic_series()
    )
    fig = render_panels.render_panel(_minimal_panel(), end_ts=1700000060.0)
    assert fig is not None
    # Suptitle is skipped entirely when no provenance env is set so local
    # dev renders don't carry a bogus "unknown / unknown" banner.
    assert fig._suptitle is None
    matplotlib.pyplot.close(fig)


def test_render_panel_defaults_started_at_when_other_envs_set(
    render_panels, clean_env, monkeypatch
):
    # At least one provenance env set => started_at defaults to "now"
    # (ISO-8601 UTC with ``Z`` suffix) instead of empty.
    monkeypatch.setenv("RESILIENCY_PANEL_RUN_ID", "99")
    monkeypatch.setattr(
        render_panels, "query_range", lambda expr, end_ts: _synthetic_series()
    )

    fig = render_panels.render_panel(_minimal_panel(), end_ts=1700000060.0)
    assert fig is not None
    text = fig._suptitle.get_text()
    # Shape: "unknown / run 99 / unknown / started 2026-...Z"
    assert text.startswith("unknown / run 99 / unknown / started ")
    assert text.endswith("Z")
    matplotlib.pyplot.close(fig)


def test_write_step_summary_provenance_header(
    render_panels, clean_env, monkeypatch, tmp_path
):
    summary_path = tmp_path / "step_summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))
    monkeypatch.setenv("RESILIENCY_PANEL_TOPOLOGY", "cluster3")
    monkeypatch.setenv("RESILIENCY_PANEL_RUN_ID", "44002386163")
    monkeypatch.setenv(
        "RESILIENCY_PANEL_SHA", "88d8ce71f58cDEADBEEFCAFE1234567890ABCDEF"
    )
    monkeypatch.setenv("RESILIENCY_PANEL_STARTED_AT", "2026-11-17T02:21:43Z")

    rendered = [("Master Memory", tmp_path / "001_Master_Memory.png")]
    render_panels.write_step_summary(
        rendered,
        artifact_link="https://example.invalid/artifact",
        image_url_prefix="https://raw.githubusercontent.com/foo/bar/resiliency-snapshots/runs/44002386163/cluster3/",
        repo="foo/bar",
    )
    text = summary_path.read_text(encoding="utf-8")
    assert "## Resiliency Run — cluster3 / 44002386163" in text
    assert "- **SHA**: `88d8ce71f58cDEADBEEFCAFE1234567890ABCDEF`" in text
    assert "- **Started**: 2026-11-17T02:21:43Z" in text
    assert "- **Run**: https://github.com/foo/bar/actions/runs/44002386163" in text
    assert (
        "- **Artifact**: [workflow artifact](https://example.invalid/artifact)" in text
    )
    # Panels are embedded in a two-column HTML table so GitHub renders
    # at least two per row.  Width-capped so they don't blow out the
    # step-summary pane; links wrap back to the full-resolution PNG.
    assert "<table>" in text
    assert "<b>Master Memory</b>" in text
    assert 'alt="Master Memory"' in text
    assert 'width="480"' in text


def test_write_step_summary_grid_pairs_panels_per_row(
    render_panels, clean_env, monkeypatch, tmp_path
):
    """Three panels → two full rows with a trailing empty <td> pad."""
    summary_path = tmp_path / "step_summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))

    rendered = [
        ("Panel A", tmp_path / "001_A.png"),
        ("Panel B", tmp_path / "002_B.png"),
        ("Panel C", tmp_path / "003_C.png"),
    ]
    render_panels.write_step_summary(
        rendered,
        artifact_link=None,
        image_url_prefix="https://example.invalid/snaps/",
    )
    text = summary_path.read_text(encoding="utf-8")
    # Two <tr> rows wrapping three cells + one padding <td></td>.
    assert text.count("<tr>") == 2
    # First row: A and B share a row.
    first_tr = text.split("<tr>")[1].split("</tr>")[0]
    assert "<b>Panel A</b>" in first_tr and "<b>Panel B</b>" in first_tr
    # Second row: C alone, padded with empty cell to keep grid rectangular.
    second_tr = text.split("<tr>")[2].split("</tr>")[0]
    assert "<b>Panel C</b>" in second_tr
    assert "<td></td>" in second_tr


def test_write_step_summary_no_env_keeps_old_header(
    render_panels, clean_env, monkeypatch, tmp_path
):
    summary_path = tmp_path / "step_summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))

    rendered = [("Master Memory", tmp_path / "001_Master_Memory.png")]
    render_panels.write_step_summary(
        rendered,
        artifact_link=None,
        image_url_prefix=None,
    )
    text = summary_path.read_text(encoding="utf-8")
    assert "## Stress test panels" in text
    assert "## Resiliency Run" not in text


def test_png_output_is_valid(render_panels, clean_env, monkeypatch, tmp_path):
    monkeypatch.setenv("RESILIENCY_PANEL_TOPOLOGY", "cluster3")
    monkeypatch.setenv("RESILIENCY_PANEL_RUN_ID", "44002386163")
    monkeypatch.setenv(
        "RESILIENCY_PANEL_SHA", "88d8ce71f58c0000000000000000000000000000"
    )
    monkeypatch.setenv("RESILIENCY_PANEL_STARTED_AT", "2026-11-17T02:21:43Z")
    monkeypatch.setattr(
        render_panels, "query_range", lambda expr, end_ts: _synthetic_series()
    )

    fig = render_panels.render_panel(_minimal_panel(), end_ts=1700000060.0)
    out = tmp_path / "panel.png"
    fig.savefig(out, dpi=85, bbox_inches="tight")
    matplotlib.pyplot.close(fig)
    # PNG magic: 89 50 4E 47 0D 0A 1A 0A
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
