# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated,bad-whitespace
from __future__ import annotations

import json
import pathlib
import sys
from datetime import datetime
from typing import Any

from ptscripts import Context

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


class UpdateProgress:
    def __init__(self, progress, task):
        self.progress = progress
        self.task = task

    def __call__(self, chunk_size):
        self.progress.update(self.task, advance=chunk_size)


def get_repo_json_file_contents(
    ctx: Context,
    bucket_name: str,
    repo_path: pathlib.Path,
    repo_json_path: pathlib.Path,
) -> dict[str, Any]:
    s3 = boto3.client("s3")
    repo_json: dict[str, Any] = {}
    try:
        ret = s3.head_object(
            Bucket=bucket_name, Key=str(repo_json_path.relative_to(repo_path))
        )
        ctx.info(
            f"Downloading existing '{repo_json_path.relative_to(repo_path)}' file "
            f"from bucket {bucket_name}"
        )
        size = ret["ContentLength"]
        with repo_json_path.open("wb") as wfh:
            with tools.utils.create_progress_bar(file_progress=True) as progress:
                task = progress.add_task(description="Downloading...", total=size)
            s3.download_fileobj(
                Bucket=bucket_name,
                Key=str(repo_json_path.relative_to(repo_path)),
                Fileobj=wfh,
                Callback=UpdateProgress(progress, task),
            )
        with repo_json_path.open() as rfh:
            repo_json = json.load(rfh)
    except ClientError as exc:
        if "Error" not in exc.response:
            raise
        if exc.response["Error"]["Code"] != "404":
            raise
        ctx.info(f"Could not find {repo_json_path} in bucket {bucket_name}")
    if repo_json:
        ctx.print(repo_json, soft_wrap=True)
    return repo_json


def create_top_level_repo_path(
    ctx: Context,
    repo_path: pathlib.Path,
    salt_version: str,
    distro: str,
    distro_version: str | None = None,  # pylint: disable=bad-whitespace
    distro_arch: str | None = None,  # pylint: disable=bad-whitespace
    nightly_build_from: str | None = None,  # pylint: disable=bad-whitespace
):
    create_repo_path = repo_path
    if nightly_build_from:
        create_repo_path = (
            create_repo_path
            / "salt-dev"
            / nightly_build_from
            / datetime.utcnow().strftime("%Y-%m-%d")
        )
        create_repo_path.mkdir(exist_ok=True, parents=True)
        with ctx.chdir(create_repo_path.parent):
            latest_nightly_symlink = pathlib.Path("latest")
            if not latest_nightly_symlink.exists():
                ctx.info(
                    f"Creating 'latest' symlink to '{create_repo_path.relative_to(repo_path)}' ..."
                )
                latest_nightly_symlink.symlink_to(
                    create_repo_path.name, target_is_directory=True
                )
    elif "rc" in salt_version:
        create_repo_path = create_repo_path / "salt_rc"
    create_repo_path = create_repo_path / "salt" / "py3" / distro
    if distro_version:
        create_repo_path = create_repo_path / distro_version
    if distro_arch:
        create_repo_path = create_repo_path / distro_arch
    create_repo_path.mkdir(exist_ok=True, parents=True)
    return create_repo_path


def create_full_repo_path(
    ctx: Context,
    repo_path: pathlib.Path,
    salt_version: str,
    distro: str,
    distro_version: str | None = None,  # pylint: disable=bad-whitespace
    distro_arch: str | None = None,  # pylint: disable=bad-whitespace
    nightly_build_from: str | None = None,  # pylint: disable=bad-whitespace
):
    create_repo_path = create_top_level_repo_path(
        ctx,
        repo_path,
        salt_version,
        distro,
        distro_version,
        distro_arch,
        nightly_build_from=nightly_build_from,
    )
    create_repo_path = create_repo_path / "minor" / salt_version
    create_repo_path.mkdir(exist_ok=True, parents=True)
    return create_repo_path
