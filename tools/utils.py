# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import json
import os
import pathlib
import sys
from datetime import datetime
from typing import Any

import packaging.version
from ptscripts import Context
from rich.progress import (
    BarColumn,
    Column,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

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

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
GPG_KEY_FILENAME = "SALT-PROJECT-GPG-PUBKEY-2023"
SPB_ENVIRONMENT = os.environ.get("SPB_ENVIRONMENT") or "prod"
STAGING_BUCKET_NAME = f"salt-project-{SPB_ENVIRONMENT}-salt-artifacts-staging"
RELEASE_BUCKET_NAME = f"salt-project-{SPB_ENVIRONMENT}-salt-artifacts-release"
BACKUP_BUCKET_NAME = f"salt-project-{SPB_ENVIRONMENT}-salt-artifacts-backup"
SHARED_WORKFLOW_CONTEXT_FILEPATH = (
    REPO_ROOT / "cicd" / "shared-gh-workflows-context.yml"
)


class UpdateProgress:
    def __init__(self, progress, task):
        self.progress = progress
        self.task = task

    def __call__(self, chunk_size):
        self.progress.update(self.task, advance=chunk_size)


def create_progress_bar(file_progress: bool = False, **kwargs):
    if file_progress:
        return Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TextColumn("eta"),
            TimeRemainingColumn(),
            **kwargs,
        )
    return Progress(
        TextColumn(
            "[progress.description]{task.description}", table_column=Column(ratio=3)
        ),
        BarColumn(),
        expand=True,
        **kwargs,
    )


def export_gpg_key(ctx: Context, key_id: str, export_path: pathlib.Path):
    keyfile_gpg = export_path.joinpath(GPG_KEY_FILENAME).with_suffix(".gpg")
    if keyfile_gpg.exists():
        keyfile_gpg.unlink()
    ctx.info(f"Exporting GnuPG Key '{key_id}' to {keyfile_gpg} ...")
    ctx.run("gpg", "--output", str(keyfile_gpg), "--export", key_id)
    keyfile_pub = export_path.joinpath(GPG_KEY_FILENAME).with_suffix(".pub")
    if keyfile_pub.exists():
        keyfile_pub.unlink()
    ctx.info(f"Exporting GnuPG Key '{key_id}' to {keyfile_pub} ...")
    ctx.run("gpg", "--armor", "--output", str(keyfile_pub), "--export", key_id)


def gpg_sign(ctx: Context, key_id: str, path: pathlib.Path):
    ctx.info(f"GPG Signing '{path}' ...")
    signature_fpath = path.parent / f"{path.name}.asc"
    if signature_fpath.exists():
        signature_fpath.unlink()
    ctx.run(
        "gpg",
        "--local-user",
        key_id,
        "--output",
        str(signature_fpath),
        "--armor",
        "--detach-sign",
        "--sign",
        str(path),
    )


class Version(packaging.version.Version):
    def __lt__(self, other):
        if not isinstance(other, self.__class__):
            other = self.__class__(other)
        return super().__lt__(other)

    def __le__(self, other):
        if not isinstance(other, self.__class__):
            other = self.__class__(other)
        return super().__le__(other)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            other = self.__class__(other)
        return super().__eq__(other)

    def __ge__(self, other):
        if not isinstance(other, self.__class__):
            other = self.__class__(other)
        return super().__ge__(other)

    def __gt__(self, other):
        if not isinstance(other, self.__class__):
            other = self.__class__(other)
        return super().__gt__(other)

    def __ne__(self, other):
        if not isinstance(other, self.__class__):
            other = self.__class__(other)
        return super().__ne__(other)

    def __str__(self):
        return super().__str__().replace(".post", "-")

    def __hash__(self):
        return hash(str(self))


def get_salt_releases(ctx: Context, repository: str) -> list[Version]:
    """
    Return a list of salt versions
    """
    versions = set()
    with ctx.web as web:
        headers = {
            "Accept": "application/vnd.github+json",
        }
        if "GITHUB_TOKEN" in os.environ:
            headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
        web.headers.update(headers)
        ret = web.get(f"https://api.github.com/repos/{repository}/tags")
        if ret.status_code != 200:
            ctx.error(
                f"Failed to get the tags for repository {repository!r}: {ret.reason}"
            )
            ctx.exit(1)
        for tag in ret.json():
            name = tag["name"]
            if name.startswith("v"):
                name = name[1:]
            if "docs" in name:
                # We're not going to consider doc tags
                continue
            versions.add(Version(name))

        # Now let's go through the github releases
        ret = web.get(f"https://api.github.com/repos/{repository}/releases")
        if ret.status_code != 200:
            ctx.error(
                f"Failed to get the releases for repository {repository!r}: {ret.reason}"
            )
            ctx.exit(1)
        for release in ret.json():
            name = release["name"]
            if name.startswith("v"):
                name = name[1:]
            if name and "docs" not in name:
                # We're not going to parse docs releases
                versions.add(Version(name))
            name = release["tag_name"]
            if "docs" not in name:
                # We're not going to parse docs releases
                versions.add(Version(name))
    return sorted(versions)


def parse_versions(*versions: str) -> list[Version]:
    _versions = []
    for version in set(versions):
        if version == "latest":
            continue
        _versions.append(Version(version))
    if _versions:
        _versions.sort(reverse=True)
    return _versions


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
            with create_progress_bar(file_progress=True) as progress:
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
