"""
These commands are used to release Salt.
"""
# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import logging
import pathlib
import sys

from ptscripts import Context, command_group

import tools.utils

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print(
        "\nPlease run 'python -m pip install -r "
        "requirements/static/ci/py{}.{}/tools.txt'\n".format(*sys.version_info),
        file=sys.stderr,
        flush=True,
    )
    raise

log = logging.getLogger(__name__)

# Define the command group
release = command_group(
    name="release",
    help="Release Related Commands",
    description=__doc__,
)


@release.command(
    name="upload-artifacts",
    arguments={
        "salt_version": {
            "help": "The salt version to release.",
        },
        "artifacts_path": {
            "help": "Local path to directory containing release artifacts",
        },
    },
)
def upload_artifacts(ctx: Context, salt_version: str, artifacts_path: pathlib.Path):
    """
    Upload release artifacts to staging bucket folder `release-artifacts/<salt-version>`.

    These will be used when we later actually publish the release.
    """
    ctx.info("Preparing upload ...")
    s3 = boto3.client("s3")
    to_delete_paths: list[dict[str, str]] = []
    remote_path = f"release-artifacts/{salt_version}"
    try:
        ret = s3.list_objects(
            Bucket=tools.utils.STAGING_BUCKET_NAME,
            Prefix=remote_path,
        )
        if "Contents" in ret:
            objects = []
            for entry in ret["Contents"]:
                objects.append({"Key": entry["Key"]})
            to_delete_paths.extend(objects)
    except ClientError as exc:
        if "Error" not in exc.response:
            raise
        if exc.response["Error"]["Code"] != "404":
            raise

    if to_delete_paths:
        with tools.utils.create_progress_bar() as progress:
            bucket_uri = f"s3://{tools.utils.STAGING_BUCKET_NAME}/{remote_path}"
            task = progress.add_task(f"Deleting '{bucket_uri}'", total=1)
            try:
                ret = s3.delete_objects(
                    Bucket=tools.utils.STAGING_BUCKET_NAME,
                    Delete={"Objects": objects},
                )
            except ClientError:
                log.exception(f"Failed to delete '{bucket_uri}'")
            finally:
                progress.update(task, advance=1)

    ctx.info("Uploading release artifacts ...")
    to_upload_paths: list[pathlib.Path] = []
    copy_exclusions = [
        ".json",
    ]
    for fpath in artifacts_path.iterdir():
        if fpath.suffix in copy_exclusions:
            continue
        to_upload_paths.append(fpath)

    try:
        for fpath in to_upload_paths:
            upload_path = f"{remote_path}/{fpath.name}"
            size = fpath.stat().st_size
            ctx.info(f"  {upload_path}")
            with tools.utils.create_progress_bar(file_progress=True) as progress:
                task = progress.add_task(description="Uploading...", total=size)
                s3.upload_file(
                    str(fpath),
                    tools.utils.STAGING_BUCKET_NAME,
                    upload_path,
                    Callback=tools.utils.UpdateProgress(progress, task),
                )
    except KeyboardInterrupt:
        pass
