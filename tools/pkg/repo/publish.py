"""
These commands are used to build the package repository files.
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import fnmatch
import json
import logging
import os
import pathlib
import re
import tempfile
import textwrap
from typing import TYPE_CHECKING, Any

import boto3
import packaging.version
from botocore.exceptions import ClientError
from ptscripts import Context, command_group

import tools.pkg
import tools.utils
import tools.utils.repo
from tools.utils import Version, get_salt_releases, parse_versions
from tools.utils.repo import create_full_repo_path, get_repo_json_file_contents

log = logging.getLogger(__name__)

publish = command_group(
    name="publish",
    help="Packaging Repository Publication Related Commands",
    parent=["pkg", "repo"],
)


@publish.command(
    arguments={
        "repo_path": {
            "help": "Local path for the repository that shall be published.",
        },
        "salt_version": {
            "help": "The salt version of the repository to publish",
            "required": True,
        },
    }
)
def nightly(ctx: Context, repo_path: pathlib.Path, salt_version: str = None):
    """
    Publish to the nightly bucket.
    """
    if TYPE_CHECKING:
        assert salt_version is not None
    _publish_repo(
        ctx, repo_path=repo_path, nightly_build=True, salt_version=salt_version
    )


@publish.command(
    arguments={
        "repo_path": {
            "help": "Local path for the repository that shall be published.",
        },
        "salt_version": {
            "help": "The salt version of the repository to publish",
            "required": True,
        },
    }
)
def staging(ctx: Context, repo_path: pathlib.Path, salt_version: str = None):
    """
    Publish to the staging bucket.
    """
    if TYPE_CHECKING:
        assert salt_version is not None
    _publish_repo(ctx, repo_path=repo_path, stage=True, salt_version=salt_version)


@publish.command(
    arguments={
        "salt_version": {
            "help": "The salt version to release.",
        },
    }
)
def release(ctx: Context, salt_version: str):
    """
    Publish to the release bucket.
    """
    if "rc" in salt_version:
        bucket_folder = "salt_rc/salt/py3"
    else:
        bucket_folder = "salt/py3"

    files_to_copy: list[str]
    directories_to_delete: list[str] = []

    ctx.info("Grabbing remote file listing of files to copy...")
    s3 = boto3.client("s3")
    repo_release_files_path = pathlib.Path(
        f"release-artifacts/{salt_version}/.release-files.json"
    )
    repo_release_symlinks_path = pathlib.Path(
        f"release-artifacts/{salt_version}/.release-symlinks.json"
    )
    with tempfile.TemporaryDirectory(prefix=f"{salt_version}_release_") as tsd:
        local_release_files_path = pathlib.Path(tsd) / repo_release_files_path.name
        try:
            bucket_name = tools.utils.STAGING_BUCKET_NAME
            with local_release_files_path.open("wb") as wfh:
                ctx.info(
                    f"Downloading {repo_release_files_path} from bucket {bucket_name} ..."
                )
                s3.download_fileobj(
                    Bucket=bucket_name,
                    Key=str(repo_release_files_path),
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
        local_release_symlinks_path = (
            pathlib.Path(tsd) / repo_release_symlinks_path.name
        )
        try:
            with local_release_symlinks_path.open("wb") as wfh:
                ctx.info(
                    f"Downloading {repo_release_symlinks_path} from bucket {bucket_name} ..."
                )
                s3.download_fileobj(
                    Bucket=bucket_name,
                    Key=str(repo_release_symlinks_path),
                    Fileobj=wfh,
                )
            directories_to_delete = json.loads(local_release_symlinks_path.read_text())
        except ClientError as exc:
            if "Error" not in exc.response:
                log.exception(
                    "Error downloading %s: %s", repo_release_symlinks_path, exc
                )
                ctx.exit(1)
            if exc.response["Error"]["Code"] == "404":
                ctx.error(f"Could not find {repo_release_symlinks_path} in bucket.")
                ctx.exit(1)
            if exc.response["Error"]["Code"] == "400":
                ctx.error(
                    f"Could not download {repo_release_symlinks_path} from bucket: {exc}"
                )
                ctx.exit(1)
            log.exception("Error downloading %s: %s", repo_release_symlinks_path, exc)
            ctx.exit(1)

        if directories_to_delete:
            with tools.utils.create_progress_bar() as progress:
                task = progress.add_task(
                    "Deleting directories to override.",
                    total=len(directories_to_delete),
                )
                for directory in directories_to_delete:
                    try:
                        objects_to_delete: list[dict[str, str]] = []
                        for path in _get_repo_file_list(
                            bucket_name=tools.utils.RELEASE_BUCKET_NAME,
                            bucket_folder=bucket_folder,
                            glob_match=f"{directory}/**",
                        ):
                            objects_to_delete.append({"Key": path})
                        if objects_to_delete:
                            s3.delete_objects(
                                Bucket=tools.utils.RELEASE_BUCKET_NAME,
                                Delete={"Objects": objects_to_delete},
                            )
                    except ClientError:
                        log.exception("Failed to delete remote files")
                    finally:
                        progress.update(task, advance=1)

    already_copied_files: list[str] = []
    s3 = boto3.client("s3")
    dot_repo_files = []
    with tools.utils.create_progress_bar() as progress:
        task = progress.add_task(
            "Copying files between buckets", total=len(files_to_copy)
        )
        for fpath in files_to_copy:
            if fpath in already_copied_files:
                continue
            if fpath.endswith(".repo"):
                dot_repo_files.append(fpath)
            ctx.info(f" * Copying {fpath}")
            try:
                s3.copy_object(
                    Bucket=tools.utils.RELEASE_BUCKET_NAME,
                    Key=fpath,
                    CopySource={
                        "Bucket": tools.utils.STAGING_BUCKET_NAME,
                        "Key": fpath,
                    },
                    MetadataDirective="COPY",
                    TaggingDirective="COPY",
                    ServerSideEncryption="AES256",
                )
                already_copied_files.append(fpath)
            except ClientError:
                log.exception("Failed to copy %s", fpath)
            finally:
                progress.update(task, advance=1)

    # Now let's get the onedir based repositories where we need to update several repo.json
    major_version = packaging.version.parse(salt_version).major
    with tempfile.TemporaryDirectory(prefix=f"{salt_version}_release_") as tsd:
        repo_path = pathlib.Path(tsd)
        for distro in ("windows", "macos", "onedir"):

            create_repo_path = create_full_repo_path(
                ctx,
                repo_path,
                salt_version,
                distro=distro,
            )
            repo_json_path = create_repo_path.parent.parent / "repo.json"

            release_repo_json = get_repo_json_file_contents(
                ctx,
                bucket_name=tools.utils.RELEASE_BUCKET_NAME,
                repo_path=repo_path,
                repo_json_path=repo_json_path,
            )
            minor_repo_json_path = create_repo_path.parent / "repo.json"

            staging_minor_repo_json = get_repo_json_file_contents(
                ctx,
                bucket_name=tools.utils.STAGING_BUCKET_NAME,
                repo_path=repo_path,
                repo_json_path=minor_repo_json_path,
            )
            release_minor_repo_json = get_repo_json_file_contents(
                ctx,
                bucket_name=tools.utils.RELEASE_BUCKET_NAME,
                repo_path=repo_path,
                repo_json_path=minor_repo_json_path,
            )

            release_json = staging_minor_repo_json[salt_version]

            major_version = Version(salt_version).major
            versions = parse_versions(*list(release_minor_repo_json))
            ctx.info(
                f"Collected versions from {minor_repo_json_path.relative_to(repo_path)}: "
                f"{', '.join(str(vs) for vs in versions)}"
            )
            minor_versions = [v for v in versions if v.major == major_version]
            ctx.info(
                f"Collected versions(Matching major: {major_version}) from "
                f"{minor_repo_json_path.relative_to(repo_path)}: "
                f"{', '.join(str(vs) for vs in minor_versions)}"
            )
            if not versions:
                latest_version = Version(salt_version)
            else:
                latest_version = versions[0]
            if not minor_versions:
                latest_minor_version = Version(salt_version)
            else:
                latest_minor_version = minor_versions[0]

            ctx.info(f"Release Version: {salt_version}")
            ctx.info(f"Latest Repo Version: {latest_version}")
            ctx.info(f"Latest Release Minor Version: {latest_minor_version}")

            # Add the minor version
            release_minor_repo_json[salt_version] = release_json

            if latest_version <= salt_version:
                release_repo_json["latest"] = release_json

            if latest_minor_version <= salt_version:
                release_minor_repo_json["latest"] = release_json

            ctx.info(f"Writing {minor_repo_json_path} ...")
            minor_repo_json_path.write_text(
                json.dumps(release_minor_repo_json, sort_keys=True)
            )
            ctx.info(f"Writing {repo_json_path} ...")
            repo_json_path.write_text(json.dumps(release_repo_json, sort_keys=True))

        # And now, let's get the several rpm "*.repo" files to update the base
        # domain from staging to release
        release_domain = os.environ.get(
            "SALT_REPO_DOMAIN_RELEASE", "repo.saltproject.io"
        )
        for path in dot_repo_files:
            repo_file_path = repo_path.joinpath(path)
            repo_file_path.parent.mkdir(exist_ok=True, parents=True)
            bucket_name = tools.utils.STAGING_BUCKET_NAME
            try:
                ret = s3.head_object(Bucket=bucket_name, Key=path)
                ctx.info(
                    f"Downloading existing '{repo_file_path.relative_to(repo_path)}' "
                    f"file from bucket {bucket_name}"
                )
                size = ret["ContentLength"]
                with repo_file_path.open("wb") as wfh:
                    with tools.utils.create_progress_bar(
                        file_progress=True
                    ) as progress:
                        task = progress.add_task(
                            description="Downloading...", total=size
                        )
                    s3.download_fileobj(
                        Bucket=bucket_name,
                        Key=path,
                        Fileobj=wfh,
                        Callback=tools.utils.repo.UpdateProgress(progress, task),
                    )
                updated_contents = re.sub(
                    r"^(baseurl|gpgkey)=https://([^/]+)/(.*)$",
                    rf"\1=https://{release_domain}/\3",
                    repo_file_path.read_text(encoding="utf-8"),
                    flags=re.MULTILINE,
                )
                ctx.info(f"Updated '{repo_file_path.relative_to(repo_path)}:")
                ctx.print(updated_contents)
                repo_file_path.write_text(updated_contents, encoding="utf-8")
            except ClientError as exc:
                if "Error" not in exc.response:
                    raise
                if exc.response["Error"]["Code"] != "404":
                    raise
                ctx.info(f"Could not find {repo_file_path} in bucket {bucket_name}")

        for dirpath, dirnames, filenames in os.walk(repo_path, followlinks=True):
            for path in filenames:
                upload_path = pathlib.Path(dirpath, path)
                relpath = upload_path.relative_to(repo_path)
                size = upload_path.stat().st_size
                ctx.info(f"  {relpath}")
                with tools.utils.create_progress_bar(file_progress=True) as progress:
                    task = progress.add_task(description="Uploading...", total=size)
                    s3.upload_file(
                        str(upload_path),
                        tools.utils.RELEASE_BUCKET_NAME,
                        str(relpath),
                        Callback=tools.utils.repo.UpdateProgress(progress, task),
                    )


@publish.command(
    arguments={
        "salt_version": {
            "help": "The salt version to release.",
        },
        "key_id": {
            "help": "The GnuPG key ID used to sign.",
            "required": True,
        },
        "repository": {
            "help": (
                "The full repository name, ie, 'saltstack/salt' on GitHub "
                "to run the checks against."
            )
        },
    }
)
def github(
    ctx: Context,
    salt_version: str,
    key_id: str = None,
    repository: str = "saltstack/salt",
):
    """
    Publish the release on GitHub releases.
    """
    if TYPE_CHECKING:
        assert key_id is not None

    s3 = boto3.client("s3")

    # Let's download the release artifacts stored in staging
    artifacts_path = pathlib.Path.cwd() / "release-artifacts"
    artifacts_path.mkdir(exist_ok=True)
    release_artifacts_listing: dict[pathlib.Path, int] = {}
    continuation_token = None
    while True:
        kwargs: dict[str, str] = {}
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token
        ret = s3.list_objects_v2(
            Bucket=tools.utils.STAGING_BUCKET_NAME,
            Prefix=f"release-artifacts/{salt_version}",
            FetchOwner=False,
            **kwargs,
        )
        contents = ret.pop("Contents", None)
        if contents is None:
            break
        for entry in contents:
            entry_path = pathlib.Path(entry["Key"])
            if entry_path.name.startswith("."):
                continue
            release_artifacts_listing[entry_path] = entry["Size"]
        if not ret["IsTruncated"]:
            break
        continuation_token = ret["NextContinuationToken"]

    for entry_path, size in release_artifacts_listing.items():
        ctx.info(f" * {entry_path.name}")
        local_path = artifacts_path / entry_path.name
        with local_path.open("wb") as wfh:
            with tools.utils.create_progress_bar(file_progress=True) as progress:
                task = progress.add_task(description="Downloading...", total=size)
            s3.download_fileobj(
                Bucket=tools.utils.STAGING_BUCKET_NAME,
                Key=str(entry_path),
                Fileobj=wfh,
                Callback=tools.utils.repo.UpdateProgress(progress, task),
            )

    for artifact in artifacts_path.iterdir():
        if artifact.suffix in (".patch", ".asc", ".gpg", ".pub"):
            continue
        tools.utils.gpg_sign(ctx, key_id, artifact)

    # Export the GPG key in use
    tools.utils.export_gpg_key(ctx, key_id, artifacts_path)

    release_message = f"""\
    # Welcome to Salt v{salt_version}

    | :exclamation: ATTENTION                                                                                                  |
    |:-------------------------------------------------------------------------------------------------------------------------|
    | The archives generated by GitHub(`Source code(zip)`, `Source code(tar.gz)`) will not report Salt's version properly.     |
    | Please use the tarball generated by The Salt Project Team(`salt-{salt_version}.tar.gz`).
    """
    release_message_path = artifacts_path / "gh-release-body.md"
    release_message_path.write_text(textwrap.dedent(release_message).strip())

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is None:
        ctx.warn("The 'GITHUB_OUTPUT' variable is not set. Stop processing.")
        ctx.exit(0)

    if TYPE_CHECKING:
        assert github_output is not None

    with open(github_output, "a", encoding="utf-8") as wfh:
        wfh.write(f"release-messsage-file={release_message_path.resolve()}\n")

    try:
        releases = get_salt_releases(ctx, repository)
    except SystemExit:
        ctx.warn(f"Failed to get salt releases from repository '{repository}'")
        releases = get_salt_releases(ctx, "saltstack/salt")

    if Version(salt_version) >= releases[-1]:
        make_latest = True
    else:
        make_latest = False
    with open(github_output, "a", encoding="utf-8") as wfh:
        wfh.write(f"make-latest={json.dumps(make_latest)}\n")

    artifacts_to_upload = []
    for artifact in artifacts_path.iterdir():
        if artifact.suffix == ".patch":
            continue
        if artifact.name == release_message_path.name:
            continue
        artifacts_to_upload.append(str(artifact.resolve()))

    with open(github_output, "a", encoding="utf-8") as wfh:
        wfh.write(f"release-artifacts={','.join(artifacts_to_upload)}\n")
    ctx.exit(0)


def _get_repo_detailed_file_list(
    bucket_name: str,
    bucket_folder: str = "",
    glob_match: str = "**",
) -> list[dict[str, Any]]:
    s3 = boto3.client("s3")
    listing: list[dict[str, Any]] = []
    continuation_token = None
    while True:
        kwargs: dict[str, str] = {}
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token
        ret = s3.list_objects_v2(
            Bucket=bucket_name,
            Prefix=bucket_folder,
            FetchOwner=False,
            **kwargs,
        )
        contents = ret.pop("Contents", None)
        if contents is None:
            break
        for entry in contents:
            if fnmatch.fnmatch(entry["Key"], glob_match):
                listing.append(entry)
        if not ret["IsTruncated"]:
            break
        continuation_token = ret["NextContinuationToken"]
    return listing


def _get_repo_file_list(
    bucket_name: str, bucket_folder: str, glob_match: str
) -> list[str]:
    return [
        entry["Key"]
        for entry in _get_repo_detailed_file_list(
            bucket_name, bucket_folder, glob_match=glob_match
        )
    ]


def _publish_repo(
    ctx: Context,
    repo_path: pathlib.Path,
    salt_version: str,
    nightly_build: bool = False,
    stage: bool = False,
):
    """
    Publish packaging repositories.
    """
    if nightly_build:
        bucket_name = tools.utils.RELEASE_BUCKET_NAME
    elif stage:
        bucket_name = tools.utils.STAGING_BUCKET_NAME
    else:
        bucket_name = tools.utils.RELEASE_BUCKET_NAME

    ctx.info("Preparing upload ...")
    s3 = boto3.client("s3")
    to_delete_paths: dict[pathlib.Path, list[dict[str, str]]] = {}
    to_upload_paths: list[pathlib.Path] = []
    symlink_paths: list[str] = []
    uploaded_files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(repo_path, followlinks=True):
        for dirname in dirnames:
            path = pathlib.Path(dirpath, dirname)
            if not path.is_symlink():
                continue
            # This is a symlink, then we need to delete all files under
            # that directory in S3 because S3 does not understand symlinks
            # and we would end up adding files to that folder instead of
            # replacing it.
            try:
                relpath = path.relative_to(repo_path)
                ret = s3.list_objects(
                    Bucket=bucket_name,
                    Prefix=str(relpath),
                )
                if "Contents" not in ret:
                    continue
                objects = []
                for entry in ret["Contents"]:
                    objects.append({"Key": entry["Key"]})
                to_delete_paths[path] = objects
                symlink_paths.append(str(relpath))
            except ClientError as exc:
                if "Error" not in exc.response:
                    raise
                if exc.response["Error"]["Code"] != "404":
                    raise

        for fpath in filenames:
            path = pathlib.Path(dirpath, fpath)
            to_upload_paths.append(path)

    with tools.utils.create_progress_bar() as progress:
        task = progress.add_task(
            "Deleting directories to override.", total=len(to_delete_paths)
        )
        for base, objects in to_delete_paths.items():
            relpath = base.relative_to(repo_path)
            bucket_uri = f"s3://{bucket_name}/{relpath}"
            progress.update(task, description=f"Deleting {bucket_uri}")
            try:
                ret = s3.delete_objects(
                    Bucket=bucket_name,
                    Delete={"Objects": objects},
                )
            except ClientError:
                log.exception("Failed to delete %s", bucket_uri)
            finally:
                progress.update(task, advance=1)

    try:
        ctx.info("Uploading repository ...")
        for upload_path in to_upload_paths:
            relpath = upload_path.relative_to(repo_path)
            size = upload_path.stat().st_size
            ctx.info(f"  {relpath}")
            with tools.utils.create_progress_bar(file_progress=True) as progress:
                task = progress.add_task(description="Uploading...", total=size)
                s3.upload_file(
                    str(upload_path),
                    bucket_name,
                    str(relpath),
                    Callback=tools.utils.repo.UpdateProgress(progress, task),
                    ExtraArgs={
                        "Metadata": {
                            "x-amz-meta-salt-release-version": salt_version,
                        }
                    },
                )
            uploaded_files.append(str(relpath))
        if stage is True:
            repo_files_path = f"release-artifacts/{salt_version}/.release-files.json"
            ctx.info(f"Uploading {repo_files_path} ...")
            s3.put_object(
                Key=repo_files_path,
                Bucket=bucket_name,
                Body=json.dumps(uploaded_files).encode(),
                Metadata={
                    "x-amz-meta-salt-release-version": salt_version,
                },
            )
            repo_symlinks_path = (
                f"release-artifacts/{salt_version}/.release-symlinks.json"
            )
            ctx.info(f"Uploading {repo_symlinks_path} ...")
            s3.put_object(
                Key=repo_symlinks_path,
                Bucket=bucket_name,
                Body=json.dumps(symlink_paths).encode(),
                Metadata={
                    "x-amz-meta-salt-release-version": salt_version,
                },
            )
    except KeyboardInterrupt:
        pass
