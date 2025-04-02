"""
These commands are used to validate changelog entries
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import logging
import pathlib
import re
import sys

from ptscripts import Context, command_group
from ptscripts.models import VirtualEnvPipConfig

import tools.utils

log = logging.getLogger(__name__)

CHANGELOG_LIKE_RE = re.compile(r"([\d]+)\.([a-z]+)$")
CHANGELOG_TYPES = (
    "removed",
    "deprecated",
    "changed",
    "fixed",
    "added",
    "security",
)
CHANGELOG_ENTRY_RE = re.compile(
    r"([\d]+|(CVE|cve)-[\d]{{4}}-[\d]+)\.({})(\.md)?$".format("|".join(CHANGELOG_TYPES))
)

# Define the command group
changelog = command_group(
    name="changelog",
    help="Changelog tools",
    description=__doc__,
    venv_config=VirtualEnvPipConfig(
        requirements_files=[
            tools.utils.REPO_ROOT
            / "requirements"
            / "static"
            / "ci"
            / "py{}.{}".format(*sys.version_info)
            / "changelog.txt",
        ],
    ),
    parent="pre-commit",
)


@changelog.command(
    name="pre-commit-checks",
    arguments={
        "files": {
            "nargs": "*",
        }
    },
)
def check_changelog_entries(ctx: Context, files: list[pathlib.Path]):
    """
    Run pre-commit checks on changelog snippets.
    """
    docs_path = tools.utils.REPO_ROOT / "doc"
    tests_integration_files_path = (
        tools.utils.REPO_ROOT / "tests" / "integration" / "files"
    )
    changelog_entries_path = tools.utils.REPO_ROOT / "changelog"
    exitcode = 0
    for entry in files:
        path = pathlib.Path(entry).resolve()
        # Is it under changelog/
        try:
            path.relative_to(changelog_entries_path)
            if path.name in (".keep", ".template.jinja"):
                # This is the file we use so git doesn't delete the changelog/ directory
                continue
            # Is it named properly
            if not CHANGELOG_ENTRY_RE.match(path.name):
                ctx.error(
                    "The changelog entry '{}' should have one of the following extensions: {}.".format(
                        path.relative_to(tools.utils.REPO_ROOT),
                        ", ".join(f"{ext}.md" for ext in CHANGELOG_TYPES),
                    ),
                )
                exitcode = 1
                continue
            if path.suffix != ".md":
                ctx.error(
                    f"Please rename '{path.relative_to(tools.utils.REPO_ROOT)}' to "
                    f"'{path.relative_to(tools.utils.REPO_ROOT)}.md'"
                )
                exitcode = 1
                continue
        except ValueError:
            # No, carry on
            pass
        # Does it look like a changelog entry
        if CHANGELOG_LIKE_RE.match(path.name) and not CHANGELOG_ENTRY_RE.match(
            path.name
        ):
            try:
                # Is this under doc/
                path.relative_to(docs_path)
                # Yes, carry on
                continue
            except ValueError:
                # No, resume the check
                pass
            try:
                # Is this under tests/integration/files
                path.relative_to(tests_integration_files_path)
                # Yes, carry on
                continue
            except ValueError:
                # No, resume the check
                pass
            ctx.error(
                "The changelog entry '{}' should have one of the following extensions: {}.".format(
                    path.relative_to(tools.utils.REPO_ROOT),
                    ", ".join(f"{ext}.md" for ext in CHANGELOG_TYPES),
                )
            )
            exitcode = 1
            continue
        # Is it a changelog entry
        if not CHANGELOG_ENTRY_RE.match(path.name):
            # No? Carry on
            continue
        # Is the changelog entry in the right path?
        try:
            path.relative_to(changelog_entries_path)
        except ValueError:
            exitcode = 1
            ctx.error(
                "The changelog entry '{}' should be placed under '{}/', not '{}'".format(
                    path.name,
                    changelog_entries_path.relative_to(tools.utils.REPO_ROOT),
                    path.relative_to(tools.utils.REPO_ROOT).parent,
                )
            )
        if path.suffix != ".md":
            ctx.error(
                f"Please rename '{path.relative_to(tools.utils.REPO_ROOT)}' to "
                f"'{path.relative_to(tools.utils.REPO_ROOT)}.md'"
            )
            exitcode = 1
    ctx.exit(exitcode)
