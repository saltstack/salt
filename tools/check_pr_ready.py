"""
Lightweight pre-commit gate for contributor PRs.

This script checks the staged Salt repository for the gates documented in
:ref:`contributing-what-a-pr-needs`. It is intentionally minimal and uses
only the Python standard library so it can run inside the pre-commit
``language: python`` environment without extra dependencies.

The script reports every violation it finds and exits non-zero if any
check fails.

Checks performed
----------------

1. **Changelog fragment present.** When the working tree contains modified
   ``salt/`` source files, at least one ``changelog/*.<type>.md`` file must
   be added or modified in the same diff. The allowed types come from the
   ``towncrier`` config in ``pyproject.toml``.

2. **No skipif-as-a-bug-dodge.** ``pytest.mark.skipif`` calls whose
   ``reason=`` contains ``TODO``, ``FIXME``, ``XXX``, or ``broken``
   are rejected. Real platform/version skips are fine.

3. **No debug ``print()`` left in production code.** Any ``print(`` in a
   file under ``salt/`` that is not gated by ``if __name__ ==`` is
   reported.

4. **No commit attribution trailers.** The latest commit message must not
   contain ``Co-Authored-By:`` or similar AI attribution trailers.

Run manually::

    python tools/check_pr_ready.py

Or via the project's pre-commit configuration::

    pre-commit run check-pr-ready --all-files
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

CHANGELOG_TYPES = (
    "removed",
    "deprecated",
    "changed",
    "fixed",
    "added",
    "security",
)
CHANGELOG_ENTRY_RE = re.compile(
    r"^changelog/(\d+|(?:CVE|cve)-\d{4}-\d+)\.(?:"
    + "|".join(CHANGELOG_TYPES)
    + r")\.md$"
)

SKIPIF_RE = re.compile(
    r"^\s*@pytest\.mark\.skipif\s*\([^)]*?reason\s*=\s*[\"']([^\"']+)[\"']",
    re.DOTALL | re.MULTILINE,
)
SKIPIF_BAD_REASONS = ("TODO", "FIXME", "XXX", "broken")

PRINT_RE = re.compile(r"^\s*print\s*\(")

ATTRIBUTION_PATTERNS = (
    re.compile(r"^Co-Authored-By:", re.MULTILINE),
    re.compile(r"^Co-authored-by:", re.MULTILINE),
    re.compile(r"Generated with .{0,40}Claude", re.IGNORECASE),
)


def _run_git(*args: str) -> str:
    """Run a git command relative to the repo root and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _staged_files() -> list[str]:
    """Return the list of files staged for commit, relative to the repo root."""
    out = _run_git("diff", "--cached", "--name-only", "--diff-filter=ACM")
    return [line.strip() for line in out.splitlines() if line.strip()]


def check_changelog(files: list[str]) -> list[str]:
    """Require a changelog fragment when salt/ sources change."""
    errors: list[str] = []
    salt_changes = [f for f in files if f.startswith("salt/") and f.endswith(".py")]
    if not salt_changes:
        return errors
    changelog_changes = [f for f in files if CHANGELOG_ENTRY_RE.match(f)]
    if not changelog_changes:
        errors.append(
            "No changelog fragment found. Add changelog/<issue>.<type>.md - "
            "see doc/topics/development/changelog.rst."
        )
    return errors


def check_skipif(paths: list[pathlib.Path]) -> list[str]:
    """Reject ``pytest.mark.skipif`` calls that dodge real bugs."""
    errors: list[str] = []
    for path in paths:
        if path.suffix != ".py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in SKIPIF_RE.finditer(text):
            reason = match.group(1)
            for bad in SKIPIF_BAD_REASONS:
                if bad.lower() in reason.lower():
                    errors.append(
                        f"{path}: pytest.mark.skipif reason looks like a bug "
                        f"dodge ({reason!r}); fix the test instead."
                    )
                    break
    return errors


def check_debug_prints(paths: list[pathlib.Path]) -> list[str]:
    """Reject stray ``print()`` calls in salt/ source files."""
    errors: list[str] = []
    for path in paths:
        if path.suffix != ".py":
            continue
        try:
            rel = path.relative_to(REPO_ROOT)
        except ValueError:
            rel = path
        if not str(rel).startswith("salt/"):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        in_main_guard = False
        for lineno, line in enumerate(lines, start=1):
            if "if __name__" in line and "__main__" in line:
                in_main_guard = True
                continue
            if in_main_guard:
                # Only the immediate block is exempt; very rough heuristic.
                if line and not line[0].isspace():
                    in_main_guard = False
            if in_main_guard:
                continue
            if PRINT_RE.match(line):
                errors.append(
                    f"{rel}:{lineno}: stray print() in production source; "
                    "use log.debug() or remove."
                )
    return errors


def check_attribution(commit_msg: str) -> list[str]:
    """Reject Co-Authored-By and AI attribution trailers."""
    errors: list[str] = []
    for pattern in ATTRIBUTION_PATTERNS:
        if pattern.search(commit_msg):
            errors.append(
                "Commit message contains AI/co-author attribution trailer; "
                "remove it before pushing."
            )
            break
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "files",
        nargs="*",
        help=(
            "Optional explicit list of files to check. When omitted, the "
            "script inspects the currently staged files."
        ),
    )
    parser.add_argument(
        "--commit-msg-file",
        type=pathlib.Path,
        default=None,
        help="Path to a commit message file to scan for attribution trailers.",
    )
    parser.add_argument(
        "--skip-changelog",
        action="store_true",
        help="Skip the changelog-fragment check (used by tests).",
    )
    args = parser.parse_args(argv)

    if args.files:
        rel_files = args.files
    else:
        rel_files = _staged_files()

    paths = [REPO_ROOT / f for f in rel_files]

    errors: list[str] = []
    if not args.skip_changelog:
        errors.extend(check_changelog(rel_files))
    errors.extend(check_skipif(paths))
    errors.extend(check_debug_prints(paths))

    if args.commit_msg_file is not None and args.commit_msg_file.exists():
        commit_msg = args.commit_msg_file.read_text(encoding="utf-8")
        errors.extend(check_attribution(commit_msg))

    for line in errors:
        print(line, file=sys.stderr)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
