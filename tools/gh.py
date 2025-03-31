"""
These commands are used to interact and make changes to GitHub.
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import logging

from ptscripts import Context, command_group

import tools.utils
import tools.utils.gh

log = logging.getLogger(__name__)

WORKFLOWS = tools.utils.REPO_ROOT / ".github" / "workflows"
TEMPLATES = WORKFLOWS / "templates"

# Define the command group
cgroup = command_group(
    name="gh",
    help="GitHub Related Commands",
    description=__doc__,
)


@cgroup.command(
    name="sync-os-labels",
    arguments={
        "repository": {
            "help": "Github repository.",
        },
    },
)
def sync_os_labels(
    ctx: Context, repository: str = "saltstack/salt", color: str = "C2E0C6"
):
    """
    Synchronize the GitHub labels to the OS known to be tested.
    """
    description_prefix = "Run Tests Against"
    known_os = {
        "test:os:all": {
            "name": "test:os:all",
            "color": color,
            "description": f"{description_prefix} ALL OS'es",
        },
        "test:os:macos-12": {
            "name": "test:os:macos-12",
            "color": color,
            "description": f"{description_prefix} MacOS 12",
        },
        "test:os:macos-13": {
            "name": "test:os:macos-13",
            "color": color,
            "description": f"{description_prefix} MacOS 13",
        },
        "test:os:macos-13-arm64": {
            "name": "test:os:macos-13-arm64",
            "color": color,
            "description": f"{description_prefix} MacOS 13 Arm64",
        },
    }
    for slug, details in tools.utils.get_golden_images().items():
        name = f"test:os:{slug}"
        ami_description = (
            details["ami_description"]
            .replace("CI Image of ", "")
            .replace("arm64", "Arm64")
        )
        known_os[name] = {
            "name": name,
            "color": color,
            "description": f"{description_prefix} {ami_description}",
        }

    ctx.info(known_os)

    github_token = tools.utils.gh.get_github_token(ctx)
    if github_token is None:
        ctx.error("Querying labels requires being authenticated to GitHub.")
        ctx.info(
            "Either set 'GITHUB_TOKEN' to a valid token, or configure the 'gh' tool such that "
            "'gh auth token' returns a token."
        )
        ctx.exit(1)

    existing_labels = set()
    labels_to_update = []
    labels_to_delete = set()
    shared_context = tools.utils.get_cicd_shared_context()
    for slug in shared_context["mandatory_os_slugs"]:
        label = f"test:os:{slug}"
        labels_to_delete.add(label)

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with ctx.web as web:
        web.headers.update(headers)
        page = 0
        while True:
            page += 1
            params = {
                "per_page": 100,
                "page": page,
            }
            ret = web.get(
                f"https://api.github.com/repos/{repository}/labels",
                params=params,
            )
            if ret.status_code != 200:
                ctx.error(
                    f"Failed to get the labels for repository {repository!r}: {ret.reason}"
                )
                ctx.exit(1)
            data = ret.json()
            if not data:
                break
            for details in data:
                label = details["name"]
                if not label.startswith("test:os:"):
                    continue

                existing_labels.add(label)

                if label not in known_os:
                    labels_to_delete.add(details["name"])
                    continue

                if label in known_os:
                    update_details = known_os.pop(label)
                    if label in labels_to_delete:
                        continue
                    for key, value in update_details.items():
                        if details[key] != value:
                            labels_to_update.append(update_details)
                            break
                    continue

        for slug in shared_context["mandatory_os_slugs"]:
            label = f"test:os:{slug}"
            if label in known_os:
                labels_to_delete.add(label)
                known_os.pop(label)

            if label in labels_to_update:
                labels_to_delete.add(label)
                known_os.pop(label)

        for label in labels_to_delete:
            if label not in existing_labels:
                continue
            ctx.info(f"Deleting label '{label}' ...")
            ret = web.delete(
                f"https://api.github.com/repos/{repository}/labels/{label}",
            )
            if ret.status_code != 204:
                ctx.error(
                    f"Failed to delete label '{label}' for repository {repository!r}: {ret.reason}"
                )

        ctx.info("Updating OS Labels in GitHub...")
        for details in labels_to_update:
            label = details["name"]
            ctx.info(f"Updating label '{label}' ...")
            ret = web.patch(
                f"https://api.github.com/repos/{repository}/labels/{label}",
                params=details,
            )
            if ret.status_code != 200:
                ctx.error(
                    f"Failed to update label '{details['name']}' for repository {repository!r}: {ret.reason}"
                )

        for label, details in known_os.items():
            details["name"] = label
            ctx.info(f"Creating label: {details} ...")
            ret = web.post(
                f"https://api.github.com/repos/{repository}/labels",
                json=details,
            )
            if ret.status_code != 201:
                ctx.error(
                    f"Failed to create label '{details['name']}' for repository {repository!r}: {ret.reason}"
                )
                print(ret.content)
