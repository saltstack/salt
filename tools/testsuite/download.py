"""
These commands are related to downloading test suite CI artifacts.
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import logging
import pathlib
from typing import TYPE_CHECKING

from ptscripts import Context, command_group

import tools.utils
import tools.utils.gh

log = logging.getLogger(__name__)


# Define the command group
download = command_group(
    name="download",
    help="Test Suite CI Artifacts Related Commands",
    description=__doc__,
    parent="ts",
)


@download.command(
    name="onedir-artifact",
    arguments={
        "run_id": {
            "help": "The workflow run ID from where to download artifacts from",
            "required": True,
        },
        "platform": {
            "help": "The onedir platform artifact to download",
            "choices": ("linux", "macos", "windows"),
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

    exitcode = tools.utils.gh.download_onedir_artifact(
        ctx=ctx, run_id=run_id, platform=platform, arch=arch, repository=repository
    )
    ctx.exit(exitcode)


@download.command(
    name="nox-artifact",
    arguments={
        "run_id": {
            "help": "The workflow run ID from where to download artifacts from",
            "required": True,
        },
        "platform": {
            "help": "The onedir platform artifact to download",
            "choices": ("linux", "macos", "windows"),
            "required": True,
        },
        "arch": {
            "help": "The onedir artifact architecture",
            "choices": ("x86_64", "aarch64", "amd64", "x86"),
            "required": True,
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
    platform: str = None,
    arch: str = None,
    nox_env: str = "ci-test-onedir",
    repository: str = "saltstack/salt",
):
    """
    Download CI nox artifacts.
    """
    if TYPE_CHECKING:
        assert run_id is not None
        assert arch is not None
        assert platform is not None

    exitcode = tools.utils.gh.download_nox_artifact(
        ctx=ctx,
        run_id=run_id,
        platform=platform,
        arch=arch,
        nox_env=nox_env,
        repository=repository,
    )
    ctx.exit(exitcode)


@download.command(
    name="pkgs-artifact",
    arguments={
        "run_id": {
            "help": "The workflow run ID from where to download artifacts from",
            "required": True,
        },
        "slug": {
            "help": "The OS slug",
            "required": True,
            "choices": sorted(tools.utils.get_golden_images()),
        },
        "repository": {
            "help": "The repository to query, e.g. saltstack/salt",
        },
    },
)
def download_pkgs_artifact(
    ctx: Context,
    run_id: int = None,
    slug: str = None,
    repository: str = "saltstack/salt",
):
    """
    Download CI built packages artifacts.
    """
    if TYPE_CHECKING:
        assert run_id is not None
        assert slug is not None

    exitcode = tools.utils.gh.download_pkgs_artifact(
        ctx=ctx, run_id=run_id, slug=slug, repository=repository
    )
    ctx.exit(exitcode)


@download.command(
    name="artifact",
    arguments={
        "artifact_name": {
            "help": "The name of the artifact to download",
        },
        "dest": {
            "help": "The path to the file downloaded",
        },
        "run_id": {
            "help": "The workflow run ID from where to download artifacts from",
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
        "repository": {
            "help": "The repository to query, e.g. saltstack/salt",
        },
    },
)
def download_artifact(
    ctx: Context,
    artifact_name: pathlib.Path,
    dest: pathlib.Path,
    run_id: int = None,
    branch: str = None,
    nightly: str = None,
    pr: int = None,
    repository: str = "saltstack/salt",
):
    """
    Download CI artifacts.
    """
    if TYPE_CHECKING:
        assert artifact_name is not None
        assert dest is not None

    if run_id is not None:
        actual_run_id = run_id
    else:
        potential_run_id = tools.utils.gh.discover_run_id(
            ctx, branch=branch, nightly=nightly, pr=pr, repository=repository
        )
        if potential_run_id is not None:
            actual_run_id = potential_run_id
        else:
            ctx.exit(1, "Could not discover run ID")

    succeeded = tools.utils.gh.download_artifact(
        ctx,
        dest,
        actual_run_id,
        repository=repository,
        artifact_name=str(artifact_name),
    )
    if TYPE_CHECKING:
        assert succeeded is not None
    ctx.info(succeeded)
    if succeeded:
        ctx.info(f"Downloaded {artifact_name} to {dest}")
        ctx.exit(0)
    else:
        ctx.exit(1)
