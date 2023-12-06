"""
These commands are used for our GitHub Actions workflows.
"""
# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import logging
import shutil
from typing import TYPE_CHECKING, cast

import yaml
from jinja2 import Environment, FileSystemLoader
from ptscripts import Context, command_group

import tools.utils

log = logging.getLogger(__name__)

WORKFLOWS = tools.utils.REPO_ROOT / ".github" / "workflows"
TEMPLATES = WORKFLOWS / "templates"


# Define the command group
cgroup = command_group(
    name="workflows",
    help="Pre-Commit GH Actions Workflows Related Commands",
    description=__doc__,
    parent="pre-commit",
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
        "Release": {
            "template": "release.yml",
            "includes": {
                "pre-commit": False,
                "lint": False,
                "pkg-tests": False,
                "salt-tests": False,
                "test-pkg-downloads": True,
            },
        },
        "Test Package Downloads": {
            "template": "test-package-downloads-action.yml",
        },
    }
    test_salt_listing = {
        "linux": [
            ("almalinux-8", "Alma Linux 8", "x86_64", "no-fips"),
            ("almalinux-9", "Alma Linux 9", "x86_64", "no-fips"),
            ("amazonlinux-2", "Amazon Linux 2", "x86_64", "no-fips"),
            ("amazonlinux-2-arm64", "Amazon Linux 2 Arm64", "aarch64", "no-fips"),
            ("amazonlinux-2023", "Amazon Linux 2023", "x86_64", "no-fips"),
            ("amazonlinux-2023-arm64", "Amazon Linux 2023 Arm64", "aarch64", "no-fips"),
            ("archlinux-lts", "Arch Linux LTS", "x86_64", "no-fips"),
            ("centos-7", "CentOS 7", "x86_64", "no-fips"),
            ("centosstream-8", "CentOS Stream 8", "x86_64", "no-fips"),
            ("centosstream-9", "CentOS Stream 9", "x86_64", "no-fips"),
            ("debian-10", "Debian 10", "x86_64", "no-fips"),
            ("debian-11", "Debian 11", "x86_64", "no-fips"),
            ("debian-11-arm64", "Debian 11 Arm64", "aarch64", "no-fips"),
            ("debian-12", "Debian 12", "x86_64", "no-fips"),
            ("debian-12-arm64", "Debian 12 Arm64", "aarch64", "no-fips"),
            ("fedora-37", "Fedora 37", "x86_64", "no-fips"),
            ("fedora-38", "Fedora 38", "x86_64", "no-fips"),
            ("opensuse-15", "Opensuse 15", "x86_64", "no-fips"),
            ("photonos-3", "Photon OS 3", "x86_64", "no-fips"),
            ("photonos-3-arm64", "Photon OS 3 Arm64", "aarch64", "no-fips"),
            ("photonos-4", "Photon OS 4", "x86_64", "fips"),
            ("photonos-4-arm64", "Photon OS 4 Arm64", "aarch64", "fips"),
            ("photonos-5", "Photon OS 5", "x86_64", "fips"),
            ("photonos-5-arm64", "Photon OS 5 Arm64", "aarch64", "fips"),
            ("ubuntu-20.04", "Ubuntu 20.04", "x86_64", "no-fips"),
            ("ubuntu-20.04-arm64", "Ubuntu 20.04 Arm64", "aarch64", "no-fips"),
            ("ubuntu-22.04", "Ubuntu 22.04", "x86_64", "no-fips"),
            ("ubuntu-22.04-arm64", "Ubuntu 22.04 Arm64", "aarch64", "no-fips"),
        ],
        "macos": [
            ("macos-12", "macOS 12", "x86_64"),
            ("macos-13", "macOS 13", "x86_64"),
            ("macos-13-xlarge", "macOS 13 Arm64", "aarch64"),
        ],
        "windows": [
            ("windows-2016", "Windows 2016", "amd64"),
            ("windows-2019", "Windows 2019", "amd64"),
            ("windows-2022", "Windows 2022", "amd64"),
        ],
    }

    test_salt_pkg_listing = {
        "linux": [
            ("amazonlinux-2", "Amazon Linux 2", "x86_64", "rpm", "no-fips"),
            (
                "amazonlinux-2-arm64",
                "Amazon Linux 2 Arm64",
                "aarch64",
                "rpm",
                "no-fips",
            ),
            ("amazonlinux-2023", "Amazon Linux 2023", "x86_64", "rpm", "no-fips"),
            (
                "amazonlinux-2023-arm64",
                "Amazon Linux 2023 Arm64",
                "aarch64",
                "rpm",
                "no-fips",
            ),
            ("centos-7", "CentOS 7", "x86_64", "rpm", "no-fips"),
            ("centosstream-8", "CentOS Stream 8", "x86_64", "rpm", "no-fips"),
            ("centosstream-9", "CentOS Stream 9", "x86_64", "rpm", "no-fips"),
            (
                "centosstream-9-arm64",
                "CentOS Stream 9 Arm64",
                "aarch64",
                "rpm",
                "no-fips",
            ),
            ("debian-10", "Debian 10", "x86_64", "deb", "no-fips"),
            ("debian-11", "Debian 11", "x86_64", "deb", "no-fips"),
            ("debian-11-arm64", "Debian 11 Arm64", "aarch64", "deb", "no-fips"),
            ("debian-12", "Debian 12", "x86_64", "deb", "no-fips"),
            ("debian-12-arm64", "Debian 12 Arm64", "aarch64", "deb", "no-fips"),
            ("photonos-3", "Photon OS 3", "x86_64", "rpm", "no-fips"),
            ("photonos-3-arm64", "Photon OS 3 Arm64", "aarch64", "rpm", "no-fips"),
            ("photonos-4", "Photon OS 4", "x86_64", "rpm", "fips"),
            ("photonos-4-arm64", "Photon OS 4 Arm64", "aarch64", "rpm", "fips"),
            ("photonos-5", "Photon OS 5", "x86_64", "rpm", "fips"),
            ("photonos-5-arm64", "Photon OS 5 Arm64", "aarch64", "rpm", "fips"),
            ("ubuntu-20.04", "Ubuntu 20.04", "x86_64", "deb", "no-fips"),
            ("ubuntu-20.04-arm64", "Ubuntu 20.04 Arm64", "aarch64", "deb", "no-fips"),
            ("ubuntu-22.04", "Ubuntu 22.04", "x86_64", "deb", "no-fips"),
            ("ubuntu-22.04-arm64", "Ubuntu 22.04 Arm64", "aarch64", "deb", "no-fips"),
        ],
        "macos": [
            ("macos-12", "macOS 12", "x86_64"),
            ("macos-13", "macOS 13", "x86_64"),
            ("macos-13-xlarge", "macOS 13 Arm64", "aarch64"),
        ],
        "windows": [
            ("windows-2016", "Windows 2016", "amd64"),
            ("windows-2019", "Windows 2019", "amd64"),
            ("windows-2022", "Windows 2022", "amd64"),
        ],
    }

    build_ci_deps_listing = {
        "linux": [
            ("almalinux-8", "Alma Linux 8", "x86_64"),
            ("almalinux-8-arm64", "Alma Linux 8 Arm64", "aarch64"),
            ("almalinux-9", "Alma Linux 9", "x86_64"),
            ("almalinux-9-arm64", "Alma Linux 9 Arm64", "aarch64"),
            ("amazonlinux-2", "Amazon Linux 2", "x86_64"),
            ("amazonlinux-2-arm64", "Amazon Linux 2 Arm64", "aarch64"),
            ("amazonlinux-2023", "Amazon Linux 2023", "x86_64"),
            ("amazonlinux-2023-arm64", "Amazon Linux 2023 Arm64", "aarch64"),
            ("archlinux-lts", "Arch Linux LTS", "x86_64"),
            ("centos-7", "CentOS 7", "x86_64"),
            ("centos-7-arm64", "CentOS 7 Arm64", "aarch64"),
            ("centosstream-8", "CentOS Stream 8", "x86_64"),
            ("centosstream-8-arm64", "CentOS Stream 8 Arm64", "aarch64"),
            ("centosstream-9", "CentOS Stream 9", "x86_64"),
            ("centosstream-9-arm64", "CentOS Stream 9 Arm64", "aarch64"),
            ("debian-10", "Debian 10", "x86_64"),
            ("debian-11", "Debian 11", "x86_64"),
            ("debian-11-arm64", "Debian 11 Arm64", "aarch64"),
            ("debian-12", "Debian 12", "x86_64"),
            ("debian-12-arm64", "Debian 12 Arm64", "aarch64"),
            ("fedora-37", "Fedora 37", "x86_64"),
            ("fedora-37-arm64", "Fedora 37 Arm64", "aarch64"),
            ("fedora-38", "Fedora 38", "x86_64"),
            ("fedora-38-arm64", "Fedora 38 Arm64", "aarch64"),
            ("opensuse-15", "Opensuse 15", "x86_64"),
            ("photonos-3", "Photon OS 3", "x86_64"),
            ("photonos-3-arm64", "Photon OS 3 Arm64", "aarch64"),
            ("photonos-4", "Photon OS 4", "x86_64"),
            ("photonos-4-arm64", "Photon OS 4 Arm64", "aarch64"),
            ("photonos-5", "Photon OS 5", "x86_64"),
            ("photonos-5-arm64", "Photon OS 5 Arm64", "aarch64"),
            ("ubuntu-20.04", "Ubuntu 20.04", "x86_64"),
            ("ubuntu-20.04-arm64", "Ubuntu 20.04 Arm64", "aarch64"),
            ("ubuntu-22.04", "Ubuntu 22.04", "x86_64"),
            ("ubuntu-22.04-arm64", "Ubuntu 22.04 Arm64", "aarch64"),
        ],
        "macos": [
            ("macos-12", "macOS 12", "x86_64"),
            ("macos-13", "macOS 13", "x86_64"),
            ("macos-13-xlarge", "macOS 13 Arm64", "aarch64"),
        ],
        "windows": [
            ("windows-2016", "Windows 2016", "amd64"),
            ("windows-2019", "Windows 2019", "amd64"),
            ("windows-2022", "Windows 2022", "amd64"),
        ],
    }
    test_salt_pkg_downloads_listing: dict[str, list[tuple[str, str, str]]] = {
        "linux": [],
        "macos": [],
        "windows": [],
    }
    rpm_slugs = [
        "almalinux",
        "amazonlinux",
        "centos",
        "centosstream",
        "fedora",
        "photon",
    ]
    for slug, display_name, arch in build_ci_deps_listing["linux"]:
        if slug in ("archlinux-lts", "opensuse-15"):
            continue
        test_salt_pkg_downloads_listing["linux"].append((slug, arch, "package"))
        # Account for old arm64 repo paths
        if arch == "aarch64":
            for test_slug in rpm_slugs:
                if slug.startswith(test_slug):
                    test_salt_pkg_downloads_listing["linux"].append(
                        (slug, "arm64", "package")
                    )
                    break
    for slug, display_name, arch in build_ci_deps_listing["linux"][-2:]:
        if slug in ("archlinux-lts", "opensuse-15"):
            continue
        test_salt_pkg_downloads_listing["linux"].append((slug, arch, "onedir"))
    for slug, display_name, arch in build_ci_deps_listing["macos"]:
        if arch == "aarch64":
            arch = "arm64"
        test_salt_pkg_downloads_listing["macos"].append((slug, arch, "package"))
    for slug, display_name, arch in build_ci_deps_listing["macos"][-1:]:
        test_salt_pkg_downloads_listing["macos"].append((slug, arch, "onedir"))
    for slug, display_name, arch in build_ci_deps_listing["windows"][-1:]:
        for pkg_type in ("nsis", "msi", "onedir"):
            test_salt_pkg_downloads_listing["windows"].append((slug, arch, pkg_type))

    test_salt_pkg_downloads_needs_slugs = set()
    for platform in test_salt_pkg_downloads_listing:
        for slug, _, _ in test_salt_pkg_downloads_listing[platform]:
            test_salt_pkg_downloads_needs_slugs.add(f"{slug.replace('.', '')}-ci-deps")

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
        template_path = TEMPLATES / f"{template}.jinja"
        ctx.info(
            f"Generating '{workflow_path.relative_to(tools.utils.REPO_ROOT)}' from "
            f"template '{template_path.relative_to(tools.utils.REPO_ROOT)}' ..."
        )
        context = {
            "template": template_path.relative_to(tools.utils.REPO_ROOT),
            "workflow_name": workflow_name,
            "workflow_slug": (
                details.get("slug") or workflow_name.lower().replace(" ", "-")
            ),
            "includes": includes,
            "conclusion_needs": NeedsTracker(),
            "test_salt_needs": NeedsTracker(),
            "test_salt_pkg_needs": NeedsTracker(),
            "test_repo_needs": NeedsTracker(),
            "prepare_workflow_needs": NeedsTracker(),
            "build_repo_needs": NeedsTracker(),
            "test_salt_listing": test_salt_listing,
            "test_salt_pkg_listing": test_salt_pkg_listing,
            "build_ci_deps_listing": build_ci_deps_listing,
            "test_salt_pkg_downloads_listing": test_salt_pkg_downloads_listing,
            "test_salt_pkg_downloads_needs_slugs": sorted(
                test_salt_pkg_downloads_needs_slugs
            ),
        }
        shared_context = yaml.safe_load(
            tools.utils.SHARED_WORKFLOW_CONTEXT_FILEPATH.read_text()
        )
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
