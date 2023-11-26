# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated,bad-whitespace
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import pathlib
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from enum import IntEnum
from typing import Any

import boto3
import packaging.version
from botocore.exceptions import ClientError
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

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
GPG_KEY_FILENAME = "SALT-PROJECT-GPG-PUBKEY-2023"
SPB_ENVIRONMENT = os.environ.get("SPB_ENVIRONMENT") or "test"
STAGING_BUCKET_NAME = f"salt-project-{SPB_ENVIRONMENT}-salt-artifacts-staging"
RELEASE_BUCKET_NAME = f"salt-project-{SPB_ENVIRONMENT}-salt-artifacts-release"
BACKUP_BUCKET_NAME = f"salt-project-{SPB_ENVIRONMENT}-salt-artifacts-backup"
SHARED_WORKFLOW_CONTEXT_FILEPATH = (
    REPO_ROOT / "cicd" / "shared-gh-workflows-context.yml"
)


class ExitCode(IntEnum):
    OK = 0
    FAIL = 1
    SOFT_FAIL = 2


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
    # Deferred import
    import tools.utils.gh

    ctx.info(f"Collecting salt releases from repository '{repository}'")

    versions = set()
    with ctx.web as web:
        headers = {
            "Accept": "application/vnd.github+json",
        }
        github_token = tools.utils.gh.get_github_token(ctx)
        if github_token is not None:
            headers["Authorization"] = f"Bearer {github_token}"
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


def get_file_checksum(fpath: pathlib.Path, hash_name: str) -> str:
    with fpath.open("rb") as rfh:
        try:
            digest = hashlib.file_digest(rfh, hash_name)  # type: ignore[attr-defined]
        except AttributeError:
            # Python < 3.11
            buf = bytearray(2**18)  # Reusable buffer to reduce allocations.
            view = memoryview(buf)
            digest = getattr(hashlib, hash_name)()
            while True:
                size = rfh.readinto(buf)
                if size == 0:
                    break  # EOF
                digest.update(view[:size])
    hexdigest: str = digest.hexdigest()
    return hexdigest


def download_file(
    ctx: Context,
    url: str,
    dest: pathlib.Path,
    auth: tuple[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> pathlib.Path:
    ctx.info(f"Downloading {dest.name!r} @ {url} ...")
    curl = shutil.which("curl")
    if curl is not None:
        command = [curl, "-sS", "-L"]
        if headers:
            for key, value in headers.items():
                command.extend(["-H", f"{key}: {value}"])
        command.extend(["-o", str(dest), url])
        ret = ctx.run(*command)
        if ret.returncode:
            ctx.error(f"Failed to download {url}")
            ctx.exit(1)
        return dest
    wget = shutil.which("wget")
    if wget is not None:
        with ctx.chdir(dest.parent):
            command = [wget, "--no-verbose"]
            if headers:
                for key, value in headers.items():
                    command.append(f"--header={key}: {value}")
            command.append(url)
            ret = ctx.run(*command)
            if ret.returncode:
                ctx.error(f"Failed to download {url}")
                ctx.exit(1)
        return dest
    # NOTE the stream=True parameter below
    with ctx.web as web:
        if headers:
            web.headers.update(headers)
        with web.get(url, stream=True, auth=auth) as r:
            r.raise_for_status()
            with dest.open("wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
    return dest
