"""
These commands are used to release Salt.
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import json
import logging
import os
import pathlib
import tempfile
import time

import boto3
import virustotal3.core
from botocore.exceptions import ClientError
from ptscripts import Context, command_group

import tools.utils
import tools.utils.repo

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
                if entry["Key"].endswith(".release-backup-done"):
                    continue
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
                log.exception("Failed to delete '%s'", bucket_uri)
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
                    Callback=tools.utils.repo.UpdateProgress(progress, task),
                )
    except KeyboardInterrupt:
        pass


@release.command(
    name="download-onedir-artifact",
    arguments={
        "salt_version": {
            "help": "The salt version to release.",
        },
        "platform": {
            "help": "The onedir platform archive to download.",
            "required": True,
            "choices": ("linux", "windows", "darwin", "macos"),
        },
        "arch": {
            "help": "The onedir arch archive to download.",
            "required": True,
        },
    },
)
def download_onedir_artifact(
    ctx: Context, salt_version: str, platform: str = "linux", arch: str = "x86_64"
):
    """
    Download onedir artifact from staging bucket.
    """
    s3 = boto3.client("s3")
    if platform == "darwin":
        platform = "macos"
    if arch == "aarch64":
        arch = "arm64"
    arch = arch.lower()
    platform = platform.lower()
    if platform in ("linux", "macos") and arch not in ("x86_64", "arm64"):
        ctx.error(
            f"The 'arch' value for {platform} must be one of: 'x86_64', 'aarch64', 'aarch64'"
        )
        ctx.exit(1)
    if platform == "windows" and arch not in ("x86", "amd64"):
        ctx.error(f"The 'arch' value for {platform} must be one of: 'x86', 'amd64'")
        ctx.exit(1)

    archive_name = f"salt-{salt_version}-onedir-{platform}-{arch}.tar.xz"
    archive_path = tools.utils.REPO_ROOT / "artifacts" / archive_name
    if "rc" in salt_version:
        prefix = "salt_rc/salt"
    else:
        prefix = "salt"
    remote_path = f"{prefix}/py3/onedir/minor/{salt_version}/{archive_name}"
    archive_path.parent.mkdir()
    try:
        ret = s3.head_object(Bucket=tools.utils.STAGING_BUCKET_NAME, Key=remote_path)
        size = ret["ContentLength"]
        with archive_path.open("wb") as wfh:
            ctx.info(
                f"Downloading s3://{tools.utils.STAGING_BUCKET_NAME}/{remote_path} to {archive_path} ..."
            )
            with tools.utils.create_progress_bar(file_progress=True) as progress:
                task = progress.add_task(
                    description="Downloading ...",
                    total=size,
                )
                s3.download_fileobj(
                    Bucket=tools.utils.STAGING_BUCKET_NAME,
                    Key=remote_path,
                    Fileobj=wfh,
                    Callback=tools.utils.repo.UpdateProgress(progress, task),
                )
    except ClientError as exc:
        if "Error" not in exc.response:
            log.exception("Error downloading %s: %s", remote_path, exc)
            ctx.exit(1)
        if exc.response["Error"]["Code"] == "404":
            ctx.error(f"Could not find {remote_path} in bucket.")
            ctx.exit(1)
        elif exc.response["Error"]["Code"].startswith("4"):
            ctx.error(f"Could not download {remote_path} from bucket: {exc}")
            ctx.exit(1)
        else:
            log.exception("Failed to download %s: %s", remote_path, exc)
            ctx.exit(1)

    if not archive_path.exists():
        ctx.error(f"The {archive_path} does not exist")
        ctx.exit(1)
    if not archive_path.stat().st_size:
        ctx.error(f"The {archive_path} size is zero!")
        ctx.exit(1)


@release.command(
    name="upload-virustotal",
    arguments={
        "salt_version": {
            "help": "The salt version to release.",
        },
    },
)
def upload_virustotal(ctx: Context, salt_version: str):

    # Get a list of files to upload
    files_to_copy: list[str]

    if salt_version.startswith("v"):
        salt_version = salt_version[1:]

    ctx.info("Grabbing remote file listing of files in staging ...")
    s3 = boto3.client("s3")
    repo_release_files_path = pathlib.Path(
        f"release-artifacts/{salt_version}/.release-files.json"
    )
    with tempfile.TemporaryDirectory(prefix=f"{salt_version}_release_") as tsd:
        local_release_files_path = pathlib.Path(tsd) / repo_release_files_path.name
        try:
            with local_release_files_path.open("wb") as wfh:
                ctx.info(f"Downloading file: {repo_release_files_path}")
                s3.download_fileobj(
                    Bucket=tools.utils.STAGING_BUCKET_NAME,
                    Key=str(repo_release_files_path.as_posix()),
                    Fileobj=wfh,
                )
            files_to_copy = json.loads(local_release_files_path.read_text())
        except ClientError as exc:
            if "Error" not in exc.response:
                log.exception("Error downloading %s: %s", repo_release_files_path, exc)
                ctx.exit(1)
            if exc.response["Error"]["Code"] == "404":
                ctx.error(f"Could not find {repo_release_files_path} in bucket.")
                ctx.exit(1)
            if exc.response["Error"]["Code"] == "400":
                ctx.error(
                    f"Could not download {repo_release_files_path} from bucket: {exc}"
                )
                ctx.exit(1)
            log.exception("Error downloading %s: %s", repo_release_files_path, exc)
            ctx.exit(1)

    # If we get approval, we can add RPM and DEB
    file_types = [".msi", ".exe", ".pkg"]
    files_to_upload = []
    for file in sorted(files_to_copy):
        if f"minor/{salt_version}" in file:
            if os.path.splitext(file)[1] in file_types:
                files_to_upload.append(file)
        # These are showing errors for Windows and macOS
        # if f"onedir/minor/{salt_version}" in file:
        #     if file.endswith("tar.xz"):
        #         files_to_upload.append(file)

    ctx.info("Found the following files to upload:")
    for file in files_to_upload:
        ctx.info(f"- {os.path.basename(file)}")

    # download each file, then upload to VirusTotal
    # This takes around 4 minutes per file
    # Maybe we could do this asynchronously
    failed_files = {}
    for file in files_to_upload:
        ctx.info("-" * 80)
        download_file = pathlib.Path(file)
        with tempfile.TemporaryDirectory(prefix=f"{salt_version}_release_") as tsd:
            local_download_file = pathlib.Path(tsd) / download_file.name
            try:
                with local_download_file.open("wb") as wfh:
                    ctx.info(f"Downloading from repo: {download_file}")
                    s3.download_fileobj(
                        Bucket=tools.utils.STAGING_BUCKET_NAME,
                        Key=str(download_file.as_posix()),
                        Fileobj=wfh,
                    )
            except ClientError as exc:
                if "Error" not in exc.response:
                    log.exception("Error downloading %s: %s", download_file, exc)
                    ctx.exit(1)
                if exc.response["Error"]["Code"] == "404":
                    ctx.error(f"Could not find {download_file} in bucket.")
                    ctx.exit(1)
                if exc.response["Error"]["Code"] == "400":
                    ctx.error(f"Could not download {download_file} from bucket: {exc}")
                    ctx.exit(1)
                log.exception("Error downloading %s: %s", download_file, exc)
                ctx.exit(1)

            # API key should be an environment variable
            api_key = os.environ.get("VIRUSTOTAL_API_KEY")

            ctx.info(
                f"Uploading to VirusTotal: {os.path.basename(local_download_file)}"
            )
            vt = virustotal3.core.Files(api_key)
            response = vt.upload(local_download_file)

            # We want the id
            analysis_id = response["data"]["id"]

            # Lets check the results
            results = virustotal3.core.get_analysis(api_key, analysis_id)

            status = results["data"]["attributes"]["status"]

            ctx.info("Waiting for results from VirusTotal (takes a few minutes)")
            while "completed" not in status:
                time.sleep(10)
                results = virustotal3.core.get_analysis(api_key, analysis_id)
                status = results["data"]["attributes"]["status"]

            ctx.info("Results summary:")
            stats = results["data"]["attributes"]["stats"]

            failures = False
            for field in stats:
                ctx.info(f"- {field}: {stats[field]}")
                if field in ["malicious", "suspicious"]:
                    if stats[field] > 0:
                        failures = True

            sha256 = results["meta"]["file_info"]["sha256"]

            if failures:
                ctx.info("ERROR: VirusTotal scan encountered failures")
                failed_files[os.path.basename(local_download_file)] = sha256

            ctx.info("See details here:")
            ctx.info(f"- File: {os.path.basename(local_download_file)}")
            ctx.info(f"- URL: https://www.virustotal.com/gui/file/{sha256}")

    if failed_files:
        # We want to exit with errors if there are failures
        ctx.info("-" * 80)
        ctx.info("VirusTotal flagged the following files:")
        for file in failed_files:
            ctx.info(f"- {file}")
            ctx.info(f"  https://www.virustotal.com/gui/file/{failed_files[file]}")
        ctx.exit(1)
