"""
These commands are related to the test suite.
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from ptscripts import Context, command_group

import tools.utils
import tools.utils.gh
from tools.utils import ExitCode

with tools.utils.REPO_ROOT.joinpath("cicd", "golden-images.json").open(
    "r", encoding="utf-8"
) as rfh:
    OS_SLUGS = sorted(json.load(rfh))

log = logging.getLogger(__name__)

# Define the command group
ts = command_group(name="ts", help="Test Suite Related Commands", description=__doc__)


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
            "choices": ("linux", "macos", "windows"),
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
        "pkg": {
            "help": "Also download package test artifacts",
        },
        "repository": {
            "help": "The repository to query, e.g. saltstack/salt",
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
    pkg: bool = False,
    repository: str = "saltstack/salt",
):
    """
    Setup the local test suite.

    Examples:

     * Setup the local checkout for running tests in Photon OS 4, from the artifacts
       in a pull request, including the built packages to run package tests:

         tools ts setup --platform linux --slug photonos-4 --pr 64991 --pkg

     * Setup the local checkout for running the tests in Windows 2019, from the
       artifacts in the latest nightly build from branch 3006.x

         tools ts setup --platform linux --slug windows-2019 --nightly 3006.x
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

    if "arm64" in slug:
        arch = "aarch64"

    ctx.warn(
        "Consider this in preliminary support. There are most likely things to iron out still."
    )

    if run_id is None:
        run_id = tools.utils.gh.discover_run_id(
            ctx, branch=branch, nightly=nightly, pr=pr
        )

    if run_id is None:
        run_id = tools.utils.gh.discover_run_id(
            ctx,
            branch=branch,
            nightly=nightly,
            pr=pr,
            completed_status=False,
        )
        if run_id is None:
            ctx.error("Unable to find the appropriate workflow run ID")
        else:
            ctx.warn(
                f"Looks like we found run_id {run_id} but it's not yet in the completed state"
            )
        ctx.exit(1)

    exitcode = tools.utils.gh.download_onedir_artifact(
        ctx, run_id=run_id, platform=platform, arch=arch, repository=repository
    )
    if exitcode and exitcode != ExitCode.SOFT_FAIL:
        ctx.exit(exitcode)
    exitcode = tools.utils.gh.download_nox_artifact(
        ctx,
        run_id=run_id,
        platform=platform,
        arch=arch,
        nox_env="ci-test-onedir",
        repository=repository,
    )
    if exitcode and exitcode != ExitCode.SOFT_FAIL:
        ctx.exit(exitcode)
    if pkg:
        exitcode = tools.utils.gh.download_pkgs_artifact(
            ctx,
            run_id=run_id,
            slug=slug,
            arch=arch,
            repository=repository,
        )
        if exitcode and exitcode != ExitCode.SOFT_FAIL:
            ctx.exit(exitcode)
