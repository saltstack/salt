"""
These commands are related to running pytest directly for quick local testing.
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import logging
import pathlib
import shutil
from typing import TYPE_CHECKING

from ptscripts import Context, command_group

import tools.utils

log = logging.getLogger(__name__)

# Define the command group
pytest_cmd = command_group(
    name="pytest",
    help="Direct pytest execution commands",
    description=__doc__,
    parent="ts",
)


def get_pytest_path(ctx: Context, venv_path: str = None) -> pathlib.Path | None:
    """
    Get the pytest executable path from venv or system.
    """
    if venv_path:
        pytest_bin = pathlib.Path(venv_path) / "bin" / "pytest"
        if pytest_bin.exists():
            return pytest_bin
        else:
            ctx.error(f"pytest not found in venv: {pytest_bin}")
            return None

    # Try to find pytest in PATH
    pytest_bin_str = shutil.which("pytest")
    if pytest_bin_str:
        return pathlib.Path(pytest_bin_str)

    # Try default venv310
    default_venv = tools.utils.REPO_ROOT / "venv310" / "bin" / "pytest"
    if default_venv.exists():
        ctx.info(f"Using pytest from default venv: {default_venv}")
        return default_venv

    ctx.error("pytest not found. Install pytest or provide --venv path")
    return None


@pytest_cmd.command(
    name="run",
    arguments={
        "test_path": {
            "help": "Test path to run (file, directory, or specific test)",
        },
        "venv": {
            "help": "Path to virtual environment (defaults to ./venv310 or system pytest)",
        },
        "args": {
            "help": "Additional pytest arguments (e.g., '-v -x')",
            "nargs": "*",
        },
    },
)
def run_pytest(
    ctx: Context,
    test_path: str,
    venv: str = None,
    args: list[str] = None,
):
    """
    Run pytest directly with the specified test path.

    Examples:

     * Run a specific test file:

         tools ts pytest run tests/pytests/unit/test_loader.py

     * Run a specific test with verbose output:

         tools ts pytest run tests/pytests/unit/test_loader.py::test_load_modules --args -v -x

     * Run using a custom venv:

         tools ts pytest run tests/pytests/unit/test_loader.py --venv ./my_venv
    """
    if TYPE_CHECKING:
        assert test_path is not None

    pytest_bin = get_pytest_path(ctx, venv)
    if pytest_bin is None:
        ctx.exit(1)

    # Build pytest command
    cmd = [str(pytest_bin), test_path]
    if args:
        cmd.extend(args)

    ctx.info(f"Running: {' '.join(cmd)}")
    ret = ctx.run(*cmd, check=False, cwd=tools.utils.REPO_ROOT)
    ctx.exit(ret.returncode)


@pytest_cmd.command(
    name="last-failed",
    arguments={
        "venv": {
            "help": "Path to virtual environment (defaults to ./venv310 or system pytest)",
        },
        "args": {
            "help": "Additional pytest arguments",
            "nargs": "*",
        },
    },
)
def last_failed(
    ctx: Context,
    venv: str = None,
    args: list[str] = None,
):
    """
    Re-run only the tests that failed in the last pytest run.

    Examples:

     * Re-run last failed tests:

         tools ts pytest last-failed

     * Re-run last failed with verbose output:

         tools ts pytest last-failed --args -v
    """
    pytest_bin = get_pytest_path(ctx, venv)
    if pytest_bin is None:
        ctx.exit(1)

    cmd = [str(pytest_bin), "--lf"]
    if args:
        cmd.extend(args)

    ctx.info(f"Running: {' '.join(cmd)}")
    ret = ctx.run(*cmd, check=False, cwd=tools.utils.REPO_ROOT)
    ctx.exit(ret.returncode)


@pytest_cmd.command(
    name="pattern",
    arguments={
        "pattern": {
            "help": "Test name pattern to match (passed to pytest -k)",
        },
        "venv": {
            "help": "Path to virtual environment (defaults to ./venv310 or system pytest)",
        },
        "test_path": {
            "help": "Optional test path to search within (defaults to tests/pytests)",
        },
        "args": {
            "help": "Additional pytest arguments",
            "nargs": "*",
        },
    },
)
def run_pattern(
    ctx: Context,
    pattern: str,
    venv: str = None,
    test_path: str = None,
    args: list[str] = None,
):
    """
    Run tests matching a pattern (uses pytest -k).

    Examples:

     * Run all tests with 'auth' in the name:

         tools ts pytest pattern auth

     * Run pattern in specific directory:

         tools ts pytest pattern loader --test-path tests/pytests/unit

     * Run pattern with verbose output:

         tools ts pytest pattern auth --args -v -x
    """
    if TYPE_CHECKING:
        assert pattern is not None

    pytest_bin = get_pytest_path(ctx, venv)
    if pytest_bin is None:
        ctx.exit(1)

    # Default to pytests directory if no path specified
    if test_path is None:
        test_path = "tests/pytests"

    cmd = [str(pytest_bin), test_path, "-k", pattern]
    if args:
        cmd.extend(args)

    ctx.info(f"Running: {' '.join(cmd)}")
    ret = ctx.run(*cmd, check=False, cwd=tools.utils.REPO_ROOT)
    ctx.exit(ret.returncode)


@pytest_cmd.command(
    name="list",
    arguments={
        "pattern": {
            "help": "Glob pattern to search for test files (e.g., '**/test_loader*.py')",
        },
        "path": {
            "help": "Base path to search in (defaults to tests/pytests)",
        },
    },
)
def list_tests(
    ctx: Context,
    pattern: str = "test_*.py",
    path: str = None,
):
    """
    List test files matching a pattern.

    Examples:

     * List all test files:

         tools ts pytest list

     * Find loader tests:

         tools ts pytest list --pattern '**/test_loader*.py'

     * Search in specific directory:

         tools ts pytest list --pattern 'test_*.py' --path tests/pytests/unit
    """
    if path is None:
        search_path = tools.utils.REPO_ROOT / "tests" / "pytests"
    else:
        search_path = tools.utils.REPO_ROOT / path

    if not search_path.exists():
        ctx.error(f"Path does not exist: {search_path}")
        ctx.exit(1)

    ctx.info(
        f"Searching for '{pattern}' in {search_path.relative_to(tools.utils.REPO_ROOT)}"
    )

    # Use glob to find matching files
    matches = sorted(search_path.glob(pattern))

    if not matches:
        ctx.warn(f"No test files found matching '{pattern}'")
        ctx.exit(0)

    ctx.info(f"Found {len(matches)} test file(s):")
    for match in matches:
        # Print relative to repo root
        relative_path = match.relative_to(tools.utils.REPO_ROOT)
        ctx.print(f"  {relative_path}")

    ctx.exit(0)
