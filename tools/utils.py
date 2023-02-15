# pylint: disable=resource-leakage,broad-except
from __future__ import annotations

import pathlib

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
NIGHTLY_BUCKET_NAME = "salt-project-prod-salt-artifacts-nightly"
STAGING_BUCKET_NAME = "salt-project-prod-salt-artifacts-staging"
RELEASE_BUCKET_NAME = "salt-project-prod-salt-artifacts-release"


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


def export_gpg_key(
    ctx: Context, key_id: str, repo_path: pathlib.Path, create_repo_path: pathlib.Path
):
    keyfile_gpg = create_repo_path.joinpath(GPG_KEY_FILENAME).with_suffix(".gpg")
    if keyfile_gpg.exists():
        keyfile_gpg.unlink()
    ctx.info(
        f"Exporting GnuPG Key '{key_id}' to {keyfile_gpg.relative_to(repo_path)} ..."
    )
    ctx.run("gpg", "--output", str(keyfile_gpg), "--export", key_id)
    keyfile_pub = create_repo_path.joinpath(GPG_KEY_FILENAME).with_suffix(".pub")
    if keyfile_pub.exists():
        keyfile_pub.unlink()
    ctx.info(
        f"Exporting GnuPG Key '{key_id}' to {keyfile_pub.relative_to(repo_path)} ..."
    )
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
