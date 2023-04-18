# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import os
import pathlib

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

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
GPG_KEY_FILENAME = "SALT-PROJECT-GPG-PUBKEY-2023"
SPB_ENVIRONMENT = os.environ.get("SPB_ENVIRONMENT") or "prod"
NIGHTLY_BUCKET_NAME = f"salt-project-{SPB_ENVIRONMENT}-salt-artifacts-nightly"
STAGING_BUCKET_NAME = f"salt-project-{SPB_ENVIRONMENT}-salt-artifacts-staging"
RELEASE_BUCKET_NAME = f"salt-project-{SPB_ENVIRONMENT}-salt-artifacts-release"
BACKUP_BUCKET_NAME = f"salt-project-{SPB_ENVIRONMENT}-salt-artifacts-backup"


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

    def __hash__(self):
        return hash(str(self))
