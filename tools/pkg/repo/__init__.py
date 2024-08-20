"""
These commands are used to build the package repository files.
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import logging
import os
import pathlib
import shutil
from typing import TYPE_CHECKING

import boto3
from botocore.exceptions import ClientError
from ptscripts import Context, command_group

import tools.pkg
import tools.utils
from tools.utils import Version, get_salt_releases

log = logging.getLogger(__name__)

# Define the command group
repo = command_group(
    name="repo",
    help="Packaging Repository Related Commands",
    description=__doc__,
    parent="pkg",
)


@repo.command(name="backup-previous-releases")
def backup_previous_releases(ctx: Context):
    """
    Backup release bucket.
    """
    _rclone(ctx, tools.utils.RELEASE_BUCKET_NAME, tools.utils.BACKUP_BUCKET_NAME)
    ctx.info("Done")


@repo.command(name="restore-previous-releases")
def restore_previous_releases(ctx: Context):
    """
    Restore release bucket from backup.
    """
    _rclone(ctx, tools.utils.BACKUP_BUCKET_NAME, tools.utils.RELEASE_BUCKET_NAME)
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is not None:
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write("backup-complete=true\n")
    ctx.info("Done")


def _rclone(ctx: Context, src: str, dst: str):
    rclone = shutil.which("rclone")
    if not rclone:
        ctx.error("Could not find the rclone binary")
        ctx.exit(1)

    if TYPE_CHECKING:
        assert rclone

    env = os.environ.copy()
    env["RCLONE_CONFIG_S3_TYPE"] = "s3"
    cmdline: list[str] = [
        rclone,
        "sync",
        "--auto-confirm",
        "--human-readable",
        "--checksum",
        "--color=always",
        "--metadata",
        "--s3-env-auth",
        "--s3-location-constraint=us-west-2",
        "--s3-provider=AWS",
        "--s3-region=us-west-2",
        "--stats-file-name-length=0",
        "--stats-one-line",
        "--stats=5s",
        "--transfers=50",
        "--fast-list",
        "--verbose",
        "--exclude=salt-dev/*",
    ]
    if src == tools.utils.RELEASE_BUCKET_NAME:
        cmdline.append("--s3-storage-class=INTELLIGENT_TIERING")
    cmdline.extend([f"s3://{src}", f"s3://{dst}"])
    ctx.info(f"Running: {' '.join(cmdline)}")
    ret = ctx.run(*cmdline, env=env, check=False)
    if ret.returncode:
        ctx.error(f"Failed to sync from s3://{src} to s3://{dst}")
        ctx.exit(1)


@repo.command(
    name="confirm-unreleased",
    arguments={
        "salt_version": {
            "help": "The salt version to check",
        },
        "repository": {
            "help": (
                "The full repository name, ie, 'saltstack/salt' on GitHub "
                "to run the checks against."
            )
        },
    },
)
def confirm_unreleased(
    ctx: Context, salt_version: str, repository: str = "saltstack/salt"
):
    """
    Confirm that the passed version is not yet tagged and/or released.
    """
    releases = get_salt_releases(ctx, repository)
    if Version(salt_version) in releases:
        ctx.error(f"There's already a '{salt_version}' tag or github release.")
        ctx.exit(1)
    ctx.info(f"Could not find a release for Salt Version '{salt_version}'")
    ctx.exit(0)


@repo.command(
    name="confirm-staged",
    arguments={
        "salt_version": {
            "help": "The salt version to check",
        },
        "repository": {
            "help": (
                "The full repository name, ie, 'saltstack/salt' on GitHub "
                "to run the checks against."
            )
        },
    },
)
def confirm_staged(ctx: Context, salt_version: str, repository: str = "saltstack/salt"):
    """
    Confirm that the passed version has been staged for release.
    """
    s3 = boto3.client("s3")
    repo_release_files_path = pathlib.Path(
        f"release-artifacts/{salt_version}/.release-files.json"
    )
    repo_release_symlinks_path = pathlib.Path(
        f"release-artifacts/{salt_version}/.release-symlinks.json"
    )
    for remote_path in (repo_release_files_path, repo_release_symlinks_path):
        try:
            bucket_name = tools.utils.STAGING_BUCKET_NAME
            ctx.info(
                f"Checking for the presence of {remote_path} on bucket {bucket_name} ..."
            )
            s3.head_object(
                Bucket=bucket_name,
                Key=str(remote_path),
            )
        except ClientError as exc:
            if "Error" not in exc.response:
                log.exception(
                    "Could not get information about %s: %s", remote_path, exc
                )
                ctx.exit(1)
            if exc.response["Error"]["Code"] == "404":
                ctx.error(f"Could not find {remote_path} in bucket.")
                ctx.exit(1)
            if exc.response["Error"]["Code"] == "400":
                ctx.error(f"Could get information about {remote_path}: {exc}")
                ctx.exit(1)
            log.exception("Error getting information about %s: %s", remote_path, exc)
            ctx.exit(1)
    ctx.info(f"Version {salt_version} has been staged for release")
    ctx.exit(0)
