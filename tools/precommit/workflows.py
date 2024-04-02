"""
These commands are used for our GitHub Actions workflows.
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import logging
import shutil
import sys
from typing import TYPE_CHECKING, cast

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from ptscripts import Context, command_group

import tools.utils
from tools.utils import Linux, MacOS, Windows

if sys.version_info < (3, 11):
    from typing_extensions import TypedDict
else:
    from typing import TypedDict  # pylint: disable=no-name-in-module

log = logging.getLogger(__name__)

WORKFLOWS = tools.utils.REPO_ROOT / ".github" / "workflows"
TEMPLATES = WORKFLOWS / "templates"


class PlatformDefinitions(TypedDict):
    linux: list[Linux]
    macos: list[MacOS]
    windows: list[Windows]


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
        "Build CI Deps": {
            "template": "build-deps-ci-action.yml",
        },
    }
    test_salt_listing = PlatformDefinitions(
        {
            "linux": [
                Linux(slug="rockylinux-8", display_name="Rocky Linux 8", arch="x86_64"),
                Linux(
                    slug="rockylinux-8-arm64",
                    display_name="Rocky Linux 8 Arm64",
                    arch="arm64",
                ),
                Linux(slug="rockylinux-9", display_name="Rocky Linux 9", arch="x86_64"),
                Linux(
                    slug="rockylinux-9-arm64",
                    display_name="Rocky Linux 9 Arm64",
                    arch="arm64",
                ),
                Linux(
                    slug="amazonlinux-2", display_name="Amazon Linux 2", arch="x86_64"
                ),
                Linux(
                    slug="amazonlinux-2-arm64",
                    display_name="Amazon Linux 2 Arm64",
                    arch="arm64",
                ),
                Linux(
                    slug="amazonlinux-2023",
                    display_name="Amazon Linux 2023",
                    arch="x86_64",
                ),
                Linux(
                    slug="amazonlinux-2023-arm64",
                    display_name="Amazon Linux 2023 Arm64",
                    arch="arm64",
                ),
                Linux(
                    slug="archlinux-lts", display_name="Arch Linux LTS", arch="x86_64"
                ),
                Linux(slug="centos-7", display_name="CentOS 7", arch="x86_64"),
                Linux(slug="debian-10", display_name="Debian 10", arch="x86_64"),
                Linux(slug="debian-11", display_name="Debian 11", arch="x86_64"),
                Linux(
                    slug="debian-11-arm64", display_name="Debian 11 Arm64", arch="arm64"
                ),
                Linux(slug="debian-12", display_name="Debian 12", arch="x86_64"),
                Linux(
                    slug="debian-12-arm64", display_name="Debian 12 Arm64", arch="arm64"
                ),
                Linux(slug="fedora-39", display_name="Fedora 39", arch="x86_64"),
                Linux(slug="opensuse-15", display_name="Opensuse 15", arch="x86_64"),
                Linux(
                    slug="photonos-4",
                    display_name="Photon OS 4",
                    arch="x86_64",
                    fips=True,
                ),
                Linux(
                    slug="photonos-4-arm64",
                    display_name="Photon OS 4 Arm64",
                    arch="arm64",
                    fips=True,
                ),
                Linux(
                    slug="photonos-5",
                    display_name="Photon OS 5",
                    arch="x86_64",
                    fips=True,
                ),
                Linux(
                    slug="photonos-5-arm64",
                    display_name="Photon OS 5 Arm64",
                    arch="arm64",
                    fips=True,
                ),
                Linux(slug="ubuntu-20.04", display_name="Ubuntu 20.04", arch="x86_64"),
                Linux(
                    slug="ubuntu-20.04-arm64",
                    display_name="Ubuntu 20.04 Arm64",
                    arch="arm64",
                ),
                Linux(slug="ubuntu-22.04", display_name="Ubuntu 22.04", arch="x86_64"),
                Linux(
                    slug="ubuntu-22.04-arm64",
                    display_name="Ubuntu 22.04 Arm64",
                    arch="arm64",
                ),
            ],
            "macos": [
                MacOS(slug="macos-12", display_name="macOS 12", arch="x86_64"),
                MacOS(slug="macos-13", display_name="macOS 13", arch="x86_64"),
                MacOS(
                    slug="macos-13-arm64",
                    display_name="macOS 13 Arm64",
                    arch="arm64",
                    runner="macos-13-xlarge",
                ),
            ],
            "windows": [
                Windows(slug="windows-2016", display_name="Windows 2016", arch="amd64"),
                Windows(slug="windows-2019", display_name="Windows 2019", arch="amd64"),
                Windows(slug="windows-2022", display_name="Windows 2022", arch="amd64"),
            ],
        }
    )

    test_salt_pkg_listing = PlatformDefinitions(
        {
            "linux": [
                Linux(
                    slug="rockylinux-8",
                    display_name="Rocky Linux 8",
                    arch="x86_64",
                    pkg_type="rpm",
                ),
                Linux(
                    slug="rockylinux-8-arm64",
                    display_name="Rocky Linux 8 Arm64",
                    arch="arm64",
                    pkg_type="rpm",
                ),
                Linux(
                    slug="rockylinux-9",
                    display_name="Rocky Linux 9",
                    arch="x86_64",
                    pkg_type="rpm",
                ),
                Linux(
                    slug="rockylinux-9-arm64",
                    display_name="Rocky Linux 9 Arm64",
                    arch="arm64",
                    pkg_type="rpm",
                ),
                Linux(
                    slug="amazonlinux-2",
                    display_name="Amazon Linux 2",
                    arch="x86_64",
                    pkg_type="rpm",
                ),
                Linux(
                    slug="amazonlinux-2-arm64",
                    display_name="Amazon Linux 2 Arm64",
                    arch="arm64",
                    pkg_type="rpm",
                ),
                Linux(
                    slug="amazonlinux-2023",
                    display_name="Amazon Linux 2023",
                    arch="x86_64",
                    pkg_type="rpm",
                ),
                Linux(
                    slug="amazonlinux-2023-arm64",
                    display_name="Amazon Linux 2023 Arm64",
                    arch="arm64",
                    pkg_type="rpm",
                ),
                Linux(
                    slug="centos-7",
                    display_name="CentOS 7",
                    arch="x86_64",
                    pkg_type="rpm",
                ),
                Linux(
                    slug="debian-10",
                    display_name="Debian 10",
                    arch="x86_64",
                    pkg_type="deb",
                ),
                Linux(
                    slug="debian-11",
                    display_name="Debian 11",
                    arch="x86_64",
                    pkg_type="deb",
                ),
                Linux(
                    slug="debian-11-arm64",
                    display_name="Debian 11 Arm64",
                    arch="arm64",
                    pkg_type="deb",
                ),
                Linux(
                    slug="debian-12",
                    display_name="Debian 12",
                    arch="x86_64",
                    pkg_type="deb",
                ),
                Linux(
                    slug="debian-12-arm64",
                    display_name="Debian 12 Arm64",
                    arch="arm64",
                    pkg_type="deb",
                ),
                Linux(
                    slug="photonos-4",
                    display_name="Photon OS 4",
                    arch="x86_64",
                    pkg_type="rpm",
                    fips=True,
                ),
                Linux(
                    slug="photonos-4-arm64",
                    display_name="Photon OS 4 Arm64",
                    arch="arm64",
                    pkg_type="rpm",
                    fips=True,
                ),
                Linux(
                    slug="photonos-5",
                    display_name="Photon OS 5",
                    arch="x86_64",
                    pkg_type="rpm",
                    fips=True,
                ),
                Linux(
                    slug="photonos-5-arm64",
                    display_name="Photon OS 5 Arm64",
                    arch="arm64",
                    pkg_type="rpm",
                    fips=True,
                ),
                Linux(
                    slug="ubuntu-20.04",
                    display_name="Ubuntu 20.04",
                    arch="x86_64",
                    pkg_type="deb",
                ),
                Linux(
                    slug="ubuntu-20.04-arm64",
                    display_name="Ubuntu 20.04 Arm64",
                    arch="arm64",
                    pkg_type="deb",
                ),
                Linux(
                    slug="ubuntu-22.04",
                    display_name="Ubuntu 22.04",
                    arch="x86_64",
                    pkg_type="deb",
                ),
                Linux(
                    slug="ubuntu-22.04-arm64",
                    display_name="Ubuntu 22.04 Arm64",
                    arch="arm64",
                    pkg_type="deb",
                ),
            ],
            "macos": [
                MacOS(slug="macos-12", display_name="macOS 12", arch="x86_64"),
                MacOS(slug="macos-13", display_name="macOS 13", arch="x86_64"),
                MacOS(
                    slug="macos-13-arm64",
                    display_name="macOS 13 Arm64",
                    arch="arm64",
                    runner="macos-13-xlarge",
                ),
            ],
            "windows": [
                Windows(
                    slug="windows-2016",
                    display_name="Windows 2016",
                    arch="amd64",
                    pkg_type="NSIS",
                ),
                Windows(
                    slug="windows-2016",
                    display_name="Windows 2016",
                    arch="amd64",
                    pkg_type="MSI",
                ),
                Windows(
                    slug="windows-2019",
                    display_name="Windows 2019",
                    arch="amd64",
                    pkg_type="NSIS",
                ),
                Windows(
                    slug="windows-2019",
                    display_name="Windows 2019",
                    arch="amd64",
                    pkg_type="MSI",
                ),
                Windows(
                    slug="windows-2022",
                    display_name="Windows 2022",
                    arch="amd64",
                    pkg_type="NSIS",
                ),
                Windows(
                    slug="windows-2022",
                    display_name="Windows 2022",
                    arch="amd64",
                    pkg_type="MSI",
                ),
            ],
        }
    )

    build_ci_deps_listing = {
        "linux": [
            ("x86_64", "centos-7"),
            ("arm64", "centos-7-arm64"),
        ],
        "macos": [
            ("x86_64", "macos-12"),
            ("arm64", "macos-13-arm64"),
        ],
        "windows": [
            ("amd64", "windows-2022"),
        ],
    }
    test_salt_pkg_downloads_listing = PlatformDefinitions(
        {
            "linux": [],
            "macos": [],
            "windows": [],
        }
    )
    rpm_slugs = (
        "rockylinux",
        "amazonlinux",
        "centos",
        "fedora",
        "photon",
    )
    linux_skip_pkg_download_tests = (
        "archlinux-lts",
        "opensuse-15",
        "windows",
    )
    for slug in sorted(tools.utils.get_golden_images()):
        if slug.startswith(linux_skip_pkg_download_tests):
            continue
        if "arm64" in slug:
            arch = "arm64"
        else:
            arch = "x86_64"
        if slug.startswith(rpm_slugs) and arch == "arm64":
            # While we maintain backwards compatible urls
            test_salt_pkg_downloads_listing["linux"].append(
                Linux(
                    slug=slug,
                    arch="aarch64",
                    pkg_type="package",
                )
            )
        test_salt_pkg_downloads_listing["linux"].append(
            Linux(
                slug=slug,
                arch=arch,
                pkg_type="package",
            )
        )
        if slug.startswith("ubuntu-22"):
            test_salt_pkg_downloads_listing["linux"].append(
                Linux(
                    slug=slug,
                    arch=arch,
                    pkg_type="onedir",
                )
            )
    for mac in test_salt_listing["macos"]:
        test_salt_pkg_downloads_listing["macos"].append(
            MacOS(
                slug=mac.slug,
                arch=mac.arch,
                display_name=mac.display_name,
                pkg_type="package",
                runner=mac.runner,
            )
        )
    for mac in test_salt_listing["macos"][-1:]:
        test_salt_pkg_downloads_listing["macos"].append(
            MacOS(
                slug=mac.slug,
                arch=mac.arch,
                display_name=mac.display_name,
                pkg_type="onedir",
                runner=mac.runner,
            )
        )
    for win in test_salt_listing["windows"][-1:]:
        for pkg_type in ("nsis", "msi", "onedir"):
            test_salt_pkg_downloads_listing["windows"].append(
                Windows(
                    slug=win.slug,
                    arch=win.arch,
                    display_name=win.display_name,
                    pkg_type=pkg_type,
                )
            )

    test_salt_pkg_downloads_needs_slugs = {"build-ci-deps"}
    # for platform in test_salt_pkg_downloads_listing:
    #    for _, arch, _ in test_salt_pkg_downloads_listing[platform]:
    #        test_salt_pkg_downloads_needs_slugs.add("build-ci-deps")

    build_rpms_listing = []
    rpm_os_versions: dict[str, list[str]] = {
        "amazon": [],
        "fedora": [],
        "photon": [],
        "redhat": [],
    }
    for slug in sorted(tools.utils.get_golden_images()):
        if slug.endswith("-arm64"):
            continue
        if not slug.startswith(
            ("amazonlinux", "rockylinux", "centos", "fedora", "photonos")
        ):
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
    for slug in sorted(tools.utils.get_golden_images()):
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
            "build_rpms_listing": build_rpms_listing,
            "build_debs_listing": build_debs_listing,
        }
        shared_context = tools.utils.get_cicd_shared_context()
        for key, value in shared_context.items():
            context[key.replace("-", "_")] = value
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
