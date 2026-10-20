"""
Unit tests for ``tools/audit_doc_links.py``.

These tests deliberately stay self-contained and do not run a real
``sphinx-build``; they exercise the helpers that:

* strip the catch-all ``https?://`` pattern from ``doc/conf.py``
* honor a curated allowlist of intentionally non-checked URLs
* turn the JSON-lines output of ``sphinx-build -b linkcheck`` into a
  CSV with the expected columns
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
AUDIT_SCRIPT = REPO_ROOT / "tools" / "audit_doc_links.py"


@pytest.fixture(scope="module")
def audit_module():
    if not AUDIT_SCRIPT.exists():
        pytest.fail(
            f"audit script missing at {AUDIT_SCRIPT}; "
            "tools/audit_doc_links.py must exist"
        )
    spec = importlib.util.spec_from_file_location("audit_doc_links", AUDIT_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["audit_doc_links"] = module
    spec.loader.exec_module(module)
    return module


def test_csv_columns_are_documented(audit_module):
    """The CSV column order is part of the public contract."""
    assert audit_module.CSV_COLUMNS == (
        "filename",
        "lineno",
        "status",
        "code",
        "uri",
        "info",
    )


def test_strip_catchall_removes_https_pattern(audit_module, tmp_path):
    conf = tmp_path / "conf.py"
    conf.write_text(
        "linkcheck_ignore = [\n"
        '    r"http://127.0.0.1",\n'
        '    r"https?://",\n'
        '    r"https://INFOBLOX/.*",\n'
        "]\n",
        encoding="utf-8",
    )
    stripped = audit_module._strip_catchall_ignores(conf, [r"https?://"])
    assert 'r"https?://"' not in stripped
    # Other patterns are preserved.
    assert 'r"http://127.0.0.1"' in stripped
    assert 'r"https://INFOBLOX/.*"' in stripped


def test_strip_catchall_handles_single_quotes(audit_module, tmp_path):
    conf = tmp_path / "conf.py"
    conf.write_text(
        "linkcheck_ignore = [\n"
        "    r'https?://',\n"
        "    r'http://localhost',\n"
        "]\n",
        encoding="utf-8",
    )
    stripped = audit_module._strip_catchall_ignores(conf, [r"https?://"])
    assert "r'https?://'" not in stripped
    assert "r'http://localhost'" in stripped


def test_allowlist_honors_placeholder_examples(audit_module):
    """example.com / localhost placeholders must not be reported broken."""
    patterns = [pattern for pattern in audit_module.DEFAULT_ALLOWLIST]
    compiled = [audit_module.re.compile(p) for p in patterns]
    assert audit_module._is_allowed("https://example.com/foo", compiled)
    assert audit_module._is_allowed("http://example.org", compiled)
    assert audit_module._is_allowed("http://localhost:8080/x", compiled)
    assert audit_module._is_allowed("http://127.0.0.1:4506/", compiled)
    assert audit_module._is_allowed("https://INFOBLOX/api", compiled)
    # A real URL must NOT be silently allowlisted.
    assert not audit_module._is_allowed("https://github.com/saltstack/salt", compiled)


def test_load_extra_allowlist_skips_blank_and_comments(audit_module, tmp_path):
    extra = tmp_path / "extra.txt"
    extra.write_text(
        "# this is a comment\n" "\n" r"https?://intranet\.corp(/.*)?" + "\n",
        encoding="utf-8",
    )
    patterns = audit_module._load_allowlist(extra)
    assert r"https?://intranet\.corp(/.*)?" in patterns
    # Defaults stay.
    assert r"https?://example\.com(/.*)?" in patterns
    # Comments and blank lines are not loaded.
    assert all(not p.startswith("#") for p in patterns)


def test_write_csv_produces_expected_columns(audit_module, tmp_path):
    out_json = tmp_path / "output.json"
    rows = [
        {
            "filename": "doc/topics/foo.rst",
            "lineno": 12,
            "status": "broken",
            "code": 404,
            "uri": "https://gone.example/path",
            "info": "404 Client Error",
        },
        {
            "filename": "doc/topics/bar.rst",
            "lineno": 3,
            "status": "working",
            "code": 200,
            "uri": "https://github.com/saltstack/salt",
            "info": "",
        },
    ]
    out_json.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    csv_path = tmp_path / "report.csv"
    loaded = audit_module._read_linkcheck_results(out_json)
    audit_module._write_csv(loaded, csv_path)
    content = csv_path.read_text(encoding="utf-8").splitlines()
    header = content[0].split(",")
    assert header == list(audit_module.CSV_COLUMNS)
    # Both data rows are written.
    assert len(content) == 1 + len(rows)


def test_audit_marks_allowlisted_urls(audit_module, tmp_path):
    """Allowlisted URLs that linkcheck reports as broken become
    ``allowlisted`` in the CSV (not ``broken``)."""
    fake_build = tmp_path / "build"
    (fake_build / "linkcheck").mkdir(parents=True)
    fake_json = fake_build / "linkcheck" / "output.json"
    fake_json.write_text(
        json.dumps(
            {
                "filename": "doc/x.rst",
                "lineno": 1,
                "status": "broken",
                "code": 0,
                "uri": "https://example.com/missing",
                "info": "",
            }
        )
        + "\n"
        + json.dumps(
            {
                "filename": "doc/y.rst",
                "lineno": 2,
                "status": "broken",
                "code": 0,
                "uri": "https://truly-dead.example.invalid/",
                "info": "",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    rows = audit_module._read_linkcheck_results(fake_json)
    allowlist = [audit_module.re.compile(p) for p in audit_module.DEFAULT_ALLOWLIST]
    csv_path = tmp_path / "report.csv"
    broken = 0
    final_rows = []
    for row in rows:
        if row["status"] == "broken" and audit_module._is_allowed(
            row["uri"], allowlist
        ):
            row["status"] = "allowlisted"
        final_rows.append(row)
        if row["status"] == "broken":
            broken += 1
    audit_module._write_csv(final_rows, csv_path)
    content = csv_path.read_text(encoding="utf-8")
    assert "allowlisted" in content
    assert broken == 1
