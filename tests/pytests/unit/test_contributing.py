"""Catch contributor guide syntax errors before the full Sphinx build."""

import io
from pathlib import Path

import pytest


def test_contributing_rst_has_no_warnings():
    """Treat RST warnings as failures, matching the documentation build."""
    docutils = pytest.importorskip("docutils.core")
    path = Path(__file__).resolve().parents[3] / "CONTRIBUTING.rst"
    warnings = io.StringIO()
    docutils.publish_doctree(
        path.read_text(encoding="utf-8"),
        source_path=str(path),
        settings_overrides={
            "warning_stream": warnings,
            "report_level": 2,
            "halt_level": 6,
        },
    )
    assert not warnings.getvalue(), warnings.getvalue()
