"""
These commands are related to the test suite.
"""
# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import json
import logging
import shutil
import sys
import zipfile
from typing import TYPE_CHECKING

from ptscripts import Context, command_group

import tools.utils

with tools.utils.REPO_ROOT.joinpath("cicd", "golden-images.json").open() as rfh:
    OS_SLUGS = sorted(json.load(rfh))

log = logging.getLogger(__name__)

# Define the command group
ts = command_group(name="ts", help="Test Suite Related Commands", description=__doc__)


@ts.command(
    name="download-onedir-artifact",
    arguments={
        "run_id": {
            "help": "The workflow run ID from where to download artifacts from",
            "required": True,
        },
        "platform": {
            "help": "The onedir platform artifact to download",
            "choices": ("linux", "darwin", "windows"),
            "required": True,
        },
        "arch": {
            "help": "The onedir artifact architecture",
            "choices": ("x86_64", "aarch64", "amd64", "x86"),
        },
        "repository": {
            "help": "The repository to query, e.g. saltstack/salt",
        },
    },
)
def download_onedir_artifact(
    ctx: Context,
    run_id: int = None,
    platform: str = None,
    arch: str = "x86_64",
    repository: str = "saltstack/salt",
):
    """
    Download CI onedir artifacts.
    """
    if TYPE_CHECKING:
        assert run_id is not None
        assert platform is not None

    if platform == "windows":
        if arch in ("x64", "x86_64"):
            ctx.info(f"Turning passed arch {arch!r} into 'amd64'")
            arch = "amd64"
        if arch not in ("amd64", "x86"):
            ctx.error(
                "The allowed values for '--arch' on Windows are 'amd64' and 'x86'"
            )
            ctx.exit(1)
    else:
        if arch == "arm64":
            ctx.info(f"Turning passed arch {arch!r} into 'aarch64'")
            arch = "aarch64"
        elif arch == "x64":
            ctx.info(f"Turning passed arch {arch!r} into 'x86_64'")
            arch = "x86_64"
        if arch not in ("x86_64", "aarch64"):
            ctx.error(
                f"The allowed values for '--arch' on {platform.title()} are 'x86_64', 'aarch64' or 'arm64'"
            )
            ctx.exit(1)
    artifacts_path = tools.utils.REPO_ROOT / "artifacts"
    artifacts_path.mkdir(exist_ok=True)
    if artifacts_path.joinpath("salt").exists():
        ctx.error("The 'artifacts/salt' directory already exists ...")
        ctx.exit(1)
    artifact_name = f"salt-*-onedir-{platform}-{arch}"
    if sys.platform.startswith("win"):
        artifact_name += ".zip"
    else:
        artifact_name += ".tar.xz"
    found_artifact_name = tools.utils.download_artifact(
        ctx,
        dest=artifacts_path,
        run_id=run_id,
        artifact_name=artifact_name,
        repository=repository,
    )
    found_artifact_path = artifacts_path / found_artifact_name
    artifact_expected_checksum = (
        artifacts_path.joinpath(f"{found_artifact_name}.SHA512").read_text().strip()
    )
    artifact_checksum = tools.utils.get_file_checksum(found_artifact_path, "sha512")
    if artifact_expected_checksum != artifact_checksum:
        ctx.error("The 'sha512' checksum does not match")
        ctx.error(f"{artifact_checksum!r} != {artifact_expected_checksum!r}")
        ctx.exit(1)

    if found_artifact_path.suffix == ".zip":
        with zipfile.ZipFile(found_artifact_path) as zfile:
            zfile.extractall(path=artifacts_path)
    else:
        ctx.run("tar", "xf", found_artifact_name, cwd=artifacts_path)


@ts.command(
    name="download-nox-artifact",
    arguments={
        "run_id": {
            "help": "The workflow run ID from where to download artifacts from",
            "required": True,
        },
        "slug": {
            "help": "The OS slug",
            "required": True,
            "choices": OS_SLUGS,
        },
        "nox_env": {
            "help": "The nox environment name.",
        },
        "repository": {
            "help": "The repository to query, e.g. saltstack/salt",
        },
    },
)
def download_nox_artifact(
    ctx: Context,
    run_id: int = None,
    slug: str = None,
    nox_env: str = "ci-test-onedir",
    repository: str = "saltstack/salt",
):
    """
    Download CI nox artifacts.
    """
    if TYPE_CHECKING:
        assert run_id is not None
        assert slug is not None

    artifacts_path = tools.utils.REPO_ROOT / ".nox" / nox_env
    if artifacts_path.exists():
        ctx.error("The '.nox/' directory already exists ...")
        ctx.exit(1)
    artifact_name = f"nox-{slug}-{nox_env}"
    found_artifact_name = tools.utils.download_artifact(
        ctx,
        dest=tools.utils.REPO_ROOT,
        run_id=run_id,
        artifact_name=artifact_name,
        repository=repository,
    )
    nox = shutil.which("nox")
    if nox is None:
        ctx.error("Could not find the 'nox' binary in $PATH")
        ctx.exit(1)
    ctx.run(nox, "-e", "decompress-dependencies", "--", slug)


@ts.command(
    name="setup",
    arguments={
        "run_id": {
            "help": "The workflow run ID from where to download artifacts from",
            "metavar": "RUN_ID_NUMBER",
        },
        "branch": {
            "help": "The branch from where to look for artifacts.",
            "metavar": "BRANCH_NAME",
        },
        "pr": {
            "help": "The pull-request from where to look for artifacts.",
            "metavar": "PR_NUMBER",
        },
        "nightly": {
            "help": "The nightly build branch from where to look for artifacts.",
            "metavar": "BRANCH_NAME",
        },
        "platform": {
            "help": "The onedir platform artifact to download",
            "choices": ("linux", "darwin", "windows"),
            "required": True,
        },
        "arch": {
            "help": "The onedir artifact architecture",
            "choices": ("x86_64", "aarch64", "amd64", "x86"),
        },
        "slug": {
            "help": "The OS slug",
            "required": True,
            "choices": OS_SLUGS,
        },
        "repository": {
            "help": "The repository to query, e.g. saltstack/salt",
        },
        "nox_env": {
            "help": "The nox environment name.",
        },
    },
)
def setup_testsuite(
    ctx: Context,
    run_id: int = None,
    branch: str = None,
    nightly: str = None,
    pr: int = None,
    platform: str = None,
    arch="x86_64",
    slug: str = None,
    repository: str = "saltstack/salt",
    nox_env: str = "ci-test-onedir",
):
    """
    Setup the local test suite.
    """
    if TYPE_CHECKING:
        assert platform is not None
        assert slug is not None

    mutually_exclusive_flags = [
        run_id is not None,
        branch is not None,
        pr is not None,
        nightly is not None,
    ]
    if not any(mutually_exclusive_flags):
        ctx.error("Pass one of '--run-id', '--branch', '--pr' or '--nightly'")
        ctx.exit(1)
    if len(list(filter(None, mutually_exclusive_flags))) > 1:
        ctx.error("Pass only one of '--run-id', '--branch', '--pr' or '--nightly'")
        ctx.exit(1)

    if run_id is None:
        run_id = _discover_run_id(ctx, branch=branch, nightly=nightly, pr=pr)

    if run_id is None:
        ctx.error("Unable to find the appropriate workflow run ID")
        ctx.exit(1)

    download_onedir_artifact(
        ctx, run_id=run_id, platform=platform, arch=arch, repository=repository
    )
    download_nox_artifact(
        ctx, run_id=run_id, slug=slug, nox_env=nox_env, repository=repository
    )


def _discover_run_id(
    ctx: Context,
    branch: str = None,
    nightly: str = None,
    pr: int = None,
    repository: str = "saltstack/salt",
):
    run_id: int | None = None
    with ctx.web as web:
        headers = {
            "Accept": "application/vnd.github+json",
        }
        github_token = tools.utils.get_github_token(ctx)
        if github_token is not None:
            headers["Authorization"] = f"Bearer {github_token}"
        web.headers.update(headers)

        if branch is not None:
            event = "push"
            ret = web.get(
                f"https://api.github.com/repos/{repository}/git/ref/heads/{branch}"
            )
            data = ret.json()
            if "message" in data:
                ctx.error(f"Could not find HEAD commit for branch {branch}")
                ctx.exit(1)
            head_sha = data["object"]["sha"]
        elif pr is not None:
            event = "pull_request"
            ret = web.get(f"https://api.github.com/repos/{repository}/pulls/{pr}")
            data = ret.json()
            head_sha = data["head"]["sha"]
        elif nightly == "master":
            event = "schedule"
            ret = web.get(
                f"https://api.github.com/repos/{repository}/git/ref/heads/{nightly}"
            )
            data = ret.json()
            if "message" in data:
                ctx.error(f"Could not find HEAD commit for branch {nightly}")
                ctx.exit(1)
            head_sha = data["object"]["sha"]
        else:
            event = "workflow_dispatch"
            ret = web.get(
                f"https://api.github.com/repos/{repository}/git/ref/heads/{nightly}"
            )
            data = ret.json()
            if "message" in data:
                ctx.error(f"Could not find HEAD commit for branch {nightly}")
                ctx.exit(1)
            head_sha = data["object"]["sha"]

        page = 0
        while True:
            page += 1
            ret = web.get(
                f"https://api.github.com/repos/{repository}/actions/runs?per_page=100&page={page}&event={event}&head_sha={head_sha}"
            )
            data = ret.json()
            if not data["workflow_runs"]:
                break
            workflow_runs = data["workflow_runs"]
            for workflow_run in workflow_runs:
                run_id = workflow_run["id"]
                break

    if run_id:
        ctx.info(f"Discovered run_id: {run_id}")
    return run_id
