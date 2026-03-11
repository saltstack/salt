"""
These commands are used for our GitHub Actions workflows.
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import logging
import shutil
from typing import TYPE_CHECKING, Literal, cast

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from ptscripts import Context, command_group

import tools.utils
from tools.utils import (
    Linux,
    LinuxPkg,
    MacOS,
    MacOSPkg,
    PlatformDefinitions,
    Windows,
    WindowsPkg,
)

log = logging.getLogger(__name__)

PLATFORMS: list[Literal["linux", "macos", "windows"]] = [
    "linux",
    "macos",
    "windows",
]
WORKFLOWS = tools.utils.REPO_ROOT / ".github" / "workflows"
TEMPLATES = WORKFLOWS / "templates"

# Define the command group
cgroup = command_group(
    name="workflows",
    help="Pre-Commit GH Actions Workflows Related Commands",
    description=__doc__,
    parent="pre-commit",
)

# Testing platforms
_shared_context = tools.utils.get_cicd_shared_context()

TEST_SALT_LISTING = PlatformDefinitions({"linux": [], "macos": [], "windows": []})
for _platform, _defs in _shared_context["test-salt-listing"].items():
    for _d in _defs:
        if _platform == "linux":
            TEST_SALT_LISTING["linux"].append(Linux(**_d))
        elif _platform == "macos":
            TEST_SALT_LISTING["macos"].append(MacOS(**_d))
        elif _platform == "windows":
            TEST_SALT_LISTING["windows"].append(Windows(**_d))

TEST_SALT_PKG_LISTING = PlatformDefinitions({"linux": [], "macos": [], "windows": []})
for _platform, _defs in _shared_context["test-salt-pkg-listing"].items():
    for _d in _defs:
        if _platform == "linux":
            TEST_SALT_PKG_LISTING["linux"].append(LinuxPkg(**_d))
        elif _platform == "macos":
            TEST_SALT_PKG_LISTING["macos"].append(MacOSPkg(**_d))
        elif _platform == "windows":
            TEST_SALT_PKG_LISTING["windows"].append(WindowsPkg(**_d))


def slugs():
    """
    List of supported test slugs
    """
    all_slugs = []
    for platform in TEST_SALT_LISTING:
        for osdef in TEST_SALT_LISTING[platform]:
            if osdef.enabled:
                all_slugs.append(osdef.slug)
    return all_slugs


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

    def __bool__(self):
        return bool(self._needs)


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
        "Stage Release": {
            "slug": "staging",
            "template": "staging.yml",
            "includes": {
                "test-pkg-downloads": True,
            },
        },
        "Scheduled": {
            "template": "scheduled.yml",
        },
    }
    test_salt_pkg_listing = TEST_SALT_PKG_LISTING

    build_rpms_listing = []
    rpm_os_versions: dict[str, list[str]] = {
        "amazon": [],
        "fedora": [],
        "photon": [],
        "redhat": [],
    }
    for slug in sorted(slugs()):
        if slug.endswith("-arm64"):
            continue
        if not slug.startswith(("amazonlinux", "rockylinux", "fedora", "photonos")):
            continue
        os_name, os_version = slug.split("-")
        if os_name == "amazonlinux":
            rpm_os_versions["amazon"].append(os_version)
        elif os_name == "photonos":
            rpm_os_versions["photon"].append(os_version)
        elif os_name == "fedora":
            rpm_os_versions["fedora"].append(os_version)
        else:
            rpm_os_versions["redhat"].append(os_version)

    for distro, releases in sorted(rpm_os_versions.items()):
        for release in sorted(set(releases)):
            for arch in ("x86_64", "arm64", "aarch64"):
                build_rpms_listing.append((distro, release, arch))

    build_debs_listing = []
    for slug in sorted(slugs()):
        if not slug.startswith(("debian-", "ubuntu-")):
            continue
        if slug.endswith("-arm64"):
            continue
        os_name, os_version = slug.split("-")
        for arch in ("x86_64", "arm64"):
            build_debs_listing.append((os_name, os_version, arch))

    env = Environment(
        block_start_string="<%",
        block_end_string="%>",
        variable_start_string="<{",
        variable_end_string="}>",
        extensions=[
            "jinja2.ext.do",
        ],
        loader=FileSystemLoader(str(TEMPLATES)),
        undefined=StrictUndefined,
    )
    for workflow_name, details in workflows.items():
        if TYPE_CHECKING:
            assert isinstance(details, dict)
        template: str = cast(str, details["template"])
        includes: dict[str, bool] = cast(dict, details.get("includes") or {})
        workflow_path = WORKFLOWS / template
        template_path = TEMPLATES / f"{template}.jinja"
        ctx.info(
            f"Generating '{workflow_path.relative_to(tools.utils.REPO_ROOT)}' from "
            f"template '{template_path.relative_to(tools.utils.REPO_ROOT)}' ..."
        )
        workflow_slug = details.get("slug") or workflow_name.lower().replace(" ", "-")
        context = {
            "template": template_path.relative_to(tools.utils.REPO_ROOT),
            "workflow_name": workflow_name,
            "workflow_slug": workflow_slug,
            "includes": includes,
            "conclusion_needs": NeedsTracker(),
            "test_salt_needs": NeedsTracker(),
            "test_salt_linux_needs": NeedsTracker(),
            "test_salt_macos_needs": NeedsTracker(),
            "test_salt_windows_needs": NeedsTracker(),
            "test_salt_pkg_needs": NeedsTracker(),
            "test_repo_needs": NeedsTracker(),
            "prepare_workflow_needs": NeedsTracker(),
            "build_repo_needs": NeedsTracker(),
            "test_salt_listing": TEST_SALT_LISTING,
            "test_salt_pkg_listing": test_salt_pkg_listing,
            "build_rpms_listing": build_rpms_listing,
            "build_debs_listing": build_debs_listing,
        }
        shared_context = tools.utils.get_cicd_shared_context()
        for key, value in shared_context.items():
            context[key] = value
        loaded_template = env.get_template(template_path.name)
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
