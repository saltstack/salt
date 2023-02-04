"""
These commands are used by pre-commit.
"""
# pylint: disable=resource-leakage,broad-except
from __future__ import annotations

import logging
import pathlib
import shutil
from typing import TYPE_CHECKING, cast

from jinja2 import Environment, FileSystemLoader
from ptscripts import Context, command_group

log = logging.getLogger(__name__)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
TEMPLATES = WORKFLOWS / "templates"

# Define the command group
cgroup = command_group(
    name="pre-commit", help="Pre-Commit Related Commands", description=__doc__
)


class NeedsTracker:
    def __init__(self):
        self._needs = []

    def append(self, need):
        if need not in self._needs:
            self._needs.append(need)

    def iter(self, consume=False):
        if consume is False:
            for need in self._needs:
                yield need
            return
        while self._needs:
            need = self._needs.pop(0)
            yield need


@cgroup.command(
    name="generate-workflows",
)
def generate_workflows(ctx: Context):
    """
    Generate GitHub Actions Workflows
    """
    workflows = {
        "CI": {
            "template": "ci.yml",
        },
        "Nightly": {
            "template": "nightly.yml",
        },
        "Scheduled": {
            "template": "scheduled.yml",
        },
    }
    env = Environment(
        block_start_string="<%",
        block_end_string="%>",
        variable_start_string="<{",
        variable_end_string="}>",
        extensions=[
            "jinja2.ext.do",
        ],
        loader=FileSystemLoader(str(TEMPLATES)),
    )
    for workflow_name, details in workflows.items():
        if TYPE_CHECKING:
            assert isinstance(details, dict)
        template: str = cast(str, details["template"])
        includes: dict[str, bool] = cast(dict, details.get("includes") or {})
        workflow_path = WORKFLOWS / template
        template_path = TEMPLATES / f"{template}.j2"
        ctx.info(
            f"Generating '{workflow_path.relative_to(REPO_ROOT)}' from "
            f"template '{template_path.relative_to(REPO_ROOT)}' ..."
        )
        context = {
            "template": template_path.relative_to(REPO_ROOT),
            "workflow_name": workflow_name,
            "includes": includes,
            "conclusion_needs": NeedsTracker(),
            "test_salt_needs": NeedsTracker(),
        }
        loaded_template = env.get_template(f"{template}.j2")
        rendered_template = loaded_template.render(**context)
        workflow_path.write_text(rendered_template.rstrip() + "\n")


@cgroup.command(
    name="actionlint",
    arguments={
        "files": {
            "help": "Files to run actionlint against",
            "nargs": "*",
        },
        "no_color": {
            "help": "Disable colors in output",
        },
    },
)
def actionlint(ctx: Context, files: list[str], no_color: bool = False):
    """
    Run `actionlint`
    """
    actionlint = shutil.which("actionlint")
    if not actionlint:
        ctx.warn("Could not find the 'actionlint' binary")
        ctx.exit(0)
    cmdline = [actionlint]
    if no_color is False:
        cmdline.append("-color")
    shellcheck = shutil.which("shellcheck")
    if shellcheck:
        cmdline.append(f"-shellcheck={shellcheck}")
    pyflakes = shutil.which("pyflakes")
    if pyflakes:
        cmdline.append(f"-pyflakes={pyflakes}")
    ret = ctx.run(*cmdline, *files, check=False)
    ctx.exit(ret.returncode)
