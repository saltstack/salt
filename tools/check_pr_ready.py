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

By default the skipif and debug-print checks only report violations on
lines *added* by the current change set (the diff against the upstream
tracking branch, falling back to ``origin/HEAD``). This keeps the gate
focused on what the PR introduces rather than pre-existing content in the
repository. Pass ``--all-lines`` to disable that filter.

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


def _resolve_base_ref() -> str | None:
    """Return a git ref describing the base to diff against, or ``None``.

    Tries, in order:

    * ``@{upstream}`` — the local branch's tracking ref.
    * ``origin/HEAD`` — the remote's default branch.
    * ``HEAD^1`` — the first parent, which is the base branch tip on
      GitHub Actions' shallow ``refs/remotes/pull/N/merge`` checkout.

    Returns ``None`` when nothing usable is available so callers can skip
    added-line filtering rather than crash.
    """
    # 1. Named upstreams (only useful on developer workstations).
    for candidate in ("@{upstream}", "origin/HEAD"):
        ref = _run_git("rev-parse", "--abbrev-ref", candidate).strip()
        if ref and "fatal" not in ref.lower():
            merge_base = _run_git("merge-base", "HEAD", ref).strip()
            if merge_base:
                return merge_base
    # 2. GitHub Actions ``pull/N/merge`` fallback: HEAD is a synthetic
    #    merge of the PR head into the base, so HEAD^1 is the base tip.
    parent = _run_git("rev-parse", "HEAD^1").strip()
    if parent and "fatal" not in parent.lower():
        return parent
    return None


_DIFF_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _added_lines(path: pathlib.Path, base_ref: str) -> set[int]:
    """Return the set of line numbers added to *path* since *base_ref*.

    Includes both the committed diff (``base_ref..HEAD``) and the working
    tree changes on top of ``HEAD``. When git reports no diff for the
    file, the returned set is empty — meaning the caller will report
    nothing for that file, which is the intended behaviour when the PR
    did not touch it.
    """
    try:
        rel = str(path.relative_to(REPO_ROOT))
    except ValueError:
        return set()

    added: set[int] = set()
    for diff_args in (
        ("diff", "--unified=0", base_ref, "--", rel),
        ("diff", "--unified=0", "HEAD", "--", rel),
    ):
        out = _run_git(*diff_args)
        if not out:
            continue
        for line in out.splitlines():
            match = _DIFF_HUNK_RE.match(line)
            if not match:
                continue
            start = int(match.group(1))
            count = int(match.group(2)) if match.group(2) else 1
            if count == 0:
                # Pure deletion hunk; nothing added.
                continue
            for lineno in range(start, start + count):
                added.add(lineno)
    return added


def check_changelog(
    files: list[str],
    changed_only: set[str] | None = None,
) -> list[str]:
    """Require a changelog fragment when salt/ sources change.

    When ``changed_only`` is provided, only files listed there count as
    modifications for the purpose of triggering the check. Otherwise all
    passed files are considered modifications (the behaviour the unit
    tests rely on).
    """
    errors: list[str] = []
    if changed_only is not None:
        candidates = [f for f in files if f in changed_only]
    else:
        candidates = list(files)
    salt_changes = [
        f for f in candidates if f.startswith("salt/") and f.endswith(".py")
    ]
    if not salt_changes:
        return errors
    changelog_changes = [f for f in candidates if CHANGELOG_ENTRY_RE.match(f)]
    if not changelog_changes:
        errors.append(
            "No changelog fragment found. Add changelog/<issue>.<type>.md - "
            "see doc/topics/development/changelog.rst."
        )
    return errors


def check_skipif(
    paths: list[pathlib.Path],
    added_lines: dict[pathlib.Path, set[int]] | None = None,
) -> list[str]:
    """Reject ``pytest.mark.skipif`` calls that dodge real bugs.

    When ``added_lines`` is provided, only report a violation whose
    ``@pytest.mark.skipif`` line appears in the current diff's added
    lines. A file present in the mapping with an empty set is skipped
    entirely (it was not touched by the PR). A file absent from the
    mapping is scanned in full, preserving the behaviour the unit tests
    rely on when they pass ad-hoc temp files.
    """
    errors: list[str] = []
    for path in paths:
        if path.suffix != ".py":
            continue
        allowed: set[int] | None
        if added_lines is not None and path in added_lines:
            allowed = added_lines[path]
            if not allowed:
                continue
        else:
            allowed = None
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in SKIPIF_RE.finditer(text):
            reason = match.group(1)
            hit_lineno = text.count("\n", 0, match.start()) + 1
            if allowed is not None and hit_lineno not in allowed:
                continue
            for bad in SKIPIF_BAD_REASONS:
                if bad.lower() in reason.lower():
                    errors.append(
                        f"{path}: pytest.mark.skipif reason looks like a bug "
                        f"dodge ({reason!r}); fix the test instead."
                    )
                    break
    return errors


def check_debug_prints(
    paths: list[pathlib.Path],
    added_lines: dict[pathlib.Path, set[int]] | None = None,
) -> list[str]:
    """Reject stray ``print()`` calls in salt/ source files.

    When ``added_lines`` is provided, only report violations on lines
    that were added by the current diff. A file present in the mapping
    with an empty set is skipped entirely. A file absent from the
    mapping is scanned in full.
    """
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
        allowed: set[int] | None
        if added_lines is not None and path in added_lines:
            allowed = added_lines[path]
            if not allowed:
                continue
        else:
            allowed = None
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
            if not PRINT_RE.match(line):
                continue
            if allowed is not None and lineno not in allowed:
                continue
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
    parser.add_argument(
        "--all-lines",
        action="store_true",
        help=(
            "Report skipif/print violations everywhere in the passed files, "
            "not only on lines added by the current diff. Useful for a full "
            "audit of the tree."
        ),
    )
    args = parser.parse_args(argv)

    if args.files:
        rel_files = args.files
    else:
        rel_files = _staged_files()

    paths = [REPO_ROOT / f for f in rel_files]

    added_lines: dict[pathlib.Path, set[int]] | None = None
    changed_only: set[str] | None = None
    if not args.all_lines:
        base_ref = _resolve_base_ref()
        if base_ref:
            added_lines = {path: _added_lines(path, base_ref) for path in paths}
            changed_only = {
                str(path.relative_to(REPO_ROOT))
                for path, lines in added_lines.items()
                if lines
            }

    errors: list[str] = []
    if not args.skip_changelog:
        errors.extend(check_changelog(rel_files, changed_only=changed_only))
    errors.extend(check_skipif(paths, added_lines=added_lines))
    errors.extend(check_debug_prints(paths, added_lines=added_lines))

    if args.commit_msg_file is not None and args.commit_msg_file.exists():
        commit_msg = args.commit_msg_file.read_text(encoding="utf-8")
        errors.extend(check_attribution(commit_msg))

    for line in errors:
        print(line, file=sys.stderr)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
