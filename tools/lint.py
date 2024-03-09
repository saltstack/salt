"""
Run PyLint against the code base.
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import logging
from typing import Iterable

from ptscripts import Context, command_group
from ptscripts.models import VirtualEnvPoetryConfig

log = logging.getLogger(__name__)

# Define the command group
cgroup = command_group(
    name="lint",
    help="Lint Related Commands",
    description=__doc__,
    venv_config=VirtualEnvPoetryConfig(groups=["lint"], no_root=False),
)


@cgroup.command(
    name="salt",
    arguments={
        "files": {
            "nargs": "*",
            "help": "Files to lint",
        }
    },
)
def lint_salt(ctx: Context, files: list[str]):
    """
    Run PyLint against the salt code base.
    """
    if not files:
        files.extend(["noxfile.py", "salt/", "tools/"])
    _run_lint(ctx, files, flags=["--disable=I"])


@cgroup.command(
    name="tests",
    arguments={
        "files": {
            "nargs": "*",
            "help": "Files to lint",
        }
    },
)
def lint_tests(ctx: Context, files: list[str]):
    """
    Run PyLint against the salt test suite.
    """
    if not files:
        files.append("tests/")
    _run_lint(
        ctx, files, flags=["-disable=I,unused-argument,3rd-party-module-not-gated"]
    )


def _run_lint(
    ctx: Context,
    paths: Iterable[str],
    rcfile: str = ".pylintrc",
    flags: Iterable[str] = (),
):
    ctx.run("pylint", f"--rcfile={rcfile}", *flags, *paths)
