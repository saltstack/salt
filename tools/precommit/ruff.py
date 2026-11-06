"""Report Ruff violations introduced since a Git revision, without fixing files."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TypedDict, cast


class Location(TypedDict):
    """A one-based source position in Ruff's JSON output."""

    row: int
    column: int


class Diagnostic(TypedDict):
    """Fields used from Ruff's JSON output."""

    code: str
    filename: str
    message: str
    location: Location


def git(root: Path, *args: str) -> bytes:
    """Run Git, failing rather than silently ignoring an unavailable base."""
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def changed_files(root: Path, base: str) -> dict[str, str | None]:
    """Map changed paths to their base paths, including renames and new files."""
    entries = (
        git(root, "diff", "--name-status", "-z", "--find-renames", base, "--")
        .decode("utf-8", errors="surrogateescape")
        .split("\0")
    )
    changed: dict[str, str | None] = {}
    index = 0
    while index < len(entries) - 1:
        status, path = entries[index : index + 2]
        index += 2
        if status.startswith(("R", "C")):
            new_path = entries[index]
            index += 1
            changed[new_path] = path
        elif status != "D":
            changed[path] = None if status == "A" else path
    for path in (
        git(root, "ls-files", "--others", "--exclude-standard", "-z")
        .decode("utf-8", errors="surrogateescape")
        .split("\0")
    ):
        if path:
            changed[path] = None
    return changed


def lint(root: Path, paths: list[str], source: bytes | None = None) -> list[Diagnostic]:
    """Use the same current configuration for both revisions, never applying fixes."""
    command = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "--config",
        str(root / "pyproject.toml"),
        "--output-format=json",
        "--no-fix",
        "--no-cache",
        "--force-exclude",
    ]
    if source is None:
        command.extend(["--", *paths])
    else:
        command.extend(["--stdin-filename", paths[0], "-"])
    result = subprocess.run(
        command, cwd=root, input=source, capture_output=True, check=False
    )
    if result.returncode not in (0, 1) or not result.stdout:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    return cast("list[Diagnostic]", json.loads(result.stdout))


def existing_diagnostics(
    before: bytes, after: bytes, diagnostics: list[Diagnostic]
) -> set[tuple[str, str, int, int]]:
    """Relocate baseline diagnostics on unchanged lines as edits shift them."""
    lines = {}
    matcher = difflib.SequenceMatcher(
        None, before.splitlines(), after.splitlines(), autojunk=False
    )
    for old_start, new_start, size in matcher.get_matching_blocks():
        for offset in range(size):
            lines[old_start + offset + 1] = new_start + offset + 1
    return {
        (
            diagnostic["code"],
            diagnostic["message"],
            lines[diagnostic["location"]["row"]],
            diagnostic["location"]["column"],
        )
        for diagnostic in diagnostics
        if diagnostic["location"]["row"] in lines
    }


def check(root: Path, base: str, filenames: list[str]) -> int:
    """Check changed Python files; unchanged code keeps its existing diagnostics."""
    base = git(root, "rev-parse", "--verify", f"{base}^{{commit}}").decode().strip()
    changed = changed_files(root, base)
    if filenames:
        selected = set()
        for filename in filenames:
            requested_path = (root / filename).resolve()
            selected.add(requested_path.relative_to(root).as_posix())
        changed = {path: old for path, old in changed.items() if path in selected}
    changed = {
        path: old
        for path, old in changed.items()
        if Path(path).suffix in (".py", ".pyi") and (root / path).is_file()
    }
    if not changed:
        print("Ruff: no changed Python files to check.")
        return 0

    current = lint(root, sorted(changed))
    baseline: dict[str, set[tuple[str, str, int, int]]] = {}
    for path in sorted({diagnostic["filename"] for diagnostic in current}):
        relative = Path(path).relative_to(root).as_posix()
        old_path = changed[relative]
        if old_path is None:
            baseline[relative] = set()
            continue
        before = git(root, "show", f"{base}:{old_path}")
        baseline[relative] = existing_diagnostics(
            before, (root / relative).read_bytes(), lint(root, [relative], before)
        )

    errors = 0
    for diagnostic in current:
        path = Path(diagnostic["filename"]).relative_to(root).as_posix()
        row = diagnostic["location"]["row"]
        column = diagnostic["location"]["column"]
        if (diagnostic["code"], diagnostic["message"], row, column) in baseline[path]:
            continue
        print(f"{path}:{row}:{column}: {diagnostic['code']} {diagnostic['message']}")
        errors += 1
    print(f"Ruff: {errors} new violation(s); existing violations are not enforced.")
    return int(bool(errors))


def main() -> int:
    """Run as a standalone script so the hook needs only Ruff and the stdlib."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-ref",
        default=os.environ.get("RUFF_BASE_REF", "HEAD"),
        help="Comparison revision (default: RUFF_BASE_REF, or HEAD for local edits)",
    )
    parser.add_argument("filenames", nargs="*")
    args = parser.parse_args()
    try:
        root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").decode().strip())
        return check(root, args.base_ref, args.filenames)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Ruff incremental check failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
