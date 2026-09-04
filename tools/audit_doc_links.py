"""
Audit external URLs referenced in the Salt documentation.

This wraps ``sphinx-build -b linkcheck`` so the result can be consumed
as a CSV (for spreadsheets / CI reports) rather than the human readable
``output.txt`` Sphinx ships with.

The default ``doc/conf.py`` ships with ``r"https?://"`` in
``linkcheck_ignore`` so the in-tree ``make linkcheck`` target stays
quiet during a normal build.  This script deliberately strips that
catch-all (and any pattern provided via ``--strip-ignore``) so that
real external links are actually fetched.

A small curated allowlist of intentionally non-checked URLs (for
example, ``example.com`` placeholders or private endpoints) is honored.

The script is intentionally self-contained: it has no Salt imports so
it can be run from a thin Sphinx-only virtualenv in CI.
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

# URLs we intentionally do not want to flag.  Each entry is a Python
# regular expression that must fully match (``re.fullmatch``) the URL
# Sphinx is about to check.  Keep this list short and document why each
# entry is here in the in-line comment.
DEFAULT_ALLOWLIST: tuple[str, ...] = (
    # Placeholder hostnames used as configuration examples.
    r"https?://example\.com(/.*)?",
    r"https?://example\.org(/.*)?",
    r"https?://example\.net(/.*)?",
    # Loopback / local development addresses.
    r"https?://localhost(:\d+)?(/.*)?",
    r"https?://127\.0\.0\.1(:\d+)?(/.*)?",
    # Documented placeholder used throughout RFCs / docs.
    r"https?://\d+\.\d+\.\d+\.\d+(:\d+)?(/.*)?",
    # Private intranet markers we already use in examples.
    r"https?://INFOBLOX(/.*)?",
    r"https?://SOMESERVERIP(:\d+)?(/.*)?",
)

# Default ignore patterns we want to *strip* from doc/conf.py before
# running the linkcheck.  The shipped configuration uses a catch-all
# ``https?://`` ignore that suppresses every external URL; that pattern
# is the whole reason this audit script exists.
DEFAULT_STRIP_IGNORE: tuple[str, ...] = (r"https?://",)

CSV_COLUMNS: tuple[str, ...] = (
    "filename",
    "lineno",
    "status",
    "code",
    "uri",
    "info",
)


def _load_allowlist(path: pathlib.Path | None) -> list[str]:
    """Return the configured allowlist patterns.

    The default tuple above is always included.  If ``path`` is given,
    any non-comment, non-blank line is appended to the result.
    """
    patterns = list(DEFAULT_ALLOWLIST)
    if path is None:
        return patterns
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def _strip_catchall_ignores(conf_py: pathlib.Path, strip: list[str]) -> str:
    """Return the contents of conf.py with the given ignore patterns removed.

    We only mutate string literals that appear inside the
    ``linkcheck_ignore`` list.  Anything else is left exactly as is so
    the rest of the Sphinx build is unaffected.
    """
    source = conf_py.read_text(encoding="utf-8")
    start = source.find("linkcheck_ignore")
    if start == -1:
        return source
    # Find the matching closing bracket of the list literal.
    bracket = source.find("[", start)
    if bracket == -1:
        return source
    depth = 0
    end = bracket
    for idx in range(bracket, len(source)):
        ch = source[idx]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = idx
                break
    block = source[bracket : end + 1]
    new_block = block
    for pattern in strip:
        # Match the raw-string literal exactly (single or double quote).
        regex = re.compile(
            r'^\s*r"' + re.escape(pattern) + r'",?\s*$',
            re.MULTILINE,
        )
        new_block = regex.sub("", new_block)
        regex = re.compile(
            r"^\s*r'" + re.escape(pattern) + r"',?\s*$",
            re.MULTILINE,
        )
        new_block = regex.sub("", new_block)
    return source[:bracket] + new_block + source[end + 1 :]


def _is_allowed(uri: str, allowlist: list[re.Pattern[str]]) -> bool:
    return any(pat.fullmatch(uri) for pat in allowlist)


def _read_linkcheck_results(output_json: pathlib.Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not output_json.exists():
        return rows
    with output_json.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows.append(row)
    return rows


def _write_csv(rows: list[dict[str, object]], dest: pathlib.Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in CSV_COLUMNS})


def run_audit(
    doc_dir: pathlib.Path,
    build_dir: pathlib.Path,
    csv_path: pathlib.Path,
    *,
    allowlist_file: pathlib.Path | None = None,
    strip_ignore: list[str] | None = None,
    sphinx_build: str = "sphinx-build",
    extra_args: list[str] | None = None,
) -> int:
    """Run the linkcheck audit.

    Returns the count of rows classified as broken (after the allowlist
    has been applied).  The caller can decide whether non-zero is a
    failure (informational mode = always 0).
    """
    if strip_ignore is None:
        strip_ignore = list(DEFAULT_STRIP_IGNORE)
    allowlist_patterns = _load_allowlist(allowlist_file)
    allowlist = [re.compile(p) for p in allowlist_patterns]

    work = pathlib.Path(tempfile.mkdtemp(prefix="salt-doc-audit-"))
    try:
        # Mirror the docs tree without copying _build artefacts.
        shutil.copytree(
            doc_dir,
            work / "doc",
            ignore=shutil.ignore_patterns("_build", "_build.*"),
        )
        conf_py = work / "doc" / "conf.py"
        conf_py.write_text(
            _strip_catchall_ignores(conf_py, strip_ignore),
            encoding="utf-8",
        )
        build_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            sphinx_build,
            "-b",
            "linkcheck",
            "-d",
            str(build_dir / "doctrees"),
            str(work / "doc"),
            str(build_dir / "linkcheck"),
        ]
        if extra_args:
            cmd.extend(extra_args)
        subprocess.run(cmd, check=False)
        rows = _read_linkcheck_results(build_dir / "linkcheck" / "output.json")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    broken = 0
    final_rows: list[dict[str, object]] = []
    for row in rows:
        uri = str(row.get("uri", ""))
        status = str(row.get("status", ""))
        if status == "broken" and _is_allowed(uri, allowlist):
            row["status"] = "allowlisted"
        final_rows.append(row)
        if row["status"] == "broken":
            broken += 1
    _write_csv(final_rows, csv_path)
    return broken


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit external URLs in the Salt documentation."
    )
    parser.add_argument(
        "--doc-dir",
        type=pathlib.Path,
        default=pathlib.Path(__file__).resolve().parent.parent / "doc",
        help="Path to the doc/ source tree.",
    )
    parser.add_argument(
        "--build-dir",
        type=pathlib.Path,
        default=pathlib.Path(__file__).resolve().parent.parent
        / "doc"
        / "_build"
        / "linkcheck-audit",
        help="Output build directory.",
    )
    parser.add_argument(
        "--csv",
        type=pathlib.Path,
        default=pathlib.Path(__file__).resolve().parent.parent
        / "doc"
        / "_build"
        / "linkcheck-audit"
        / "report.csv",
        help="Destination CSV path.",
    )
    parser.add_argument(
        "--allowlist",
        type=pathlib.Path,
        default=None,
        help="Optional file containing extra allowlist regex patterns.",
    )
    parser.add_argument(
        "--sphinx-build",
        default="sphinx-build",
        help="sphinx-build executable to invoke.",
    )
    parser.add_argument(
        "--strip-ignore",
        action="append",
        default=None,
        help=(
            "Additional linkcheck_ignore raw-string patterns to remove. "
            "Defaults to the catch-all 'https?://' entry."
        ),
    )
    parser.add_argument(
        "--fail-on-broken",
        action="store_true",
        help="Exit non-zero if any URL is reported as broken.",
    )
    args = parser.parse_args(argv)

    broken = run_audit(
        args.doc_dir,
        args.build_dir,
        args.csv,
        allowlist_file=args.allowlist,
        strip_ignore=args.strip_ignore,
        sphinx_build=args.sphinx_build,
    )
    print(f"Audit complete. Broken URLs: {broken}. Report: {args.csv}")
    return 1 if (args.fail_on_broken and broken) else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
