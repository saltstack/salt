"""
These commands are used to build the package repository files.
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import hashlib
import json
import logging
import os
import pathlib
import shutil
import textwrap
from datetime import datetime
from typing import TYPE_CHECKING

import boto3
from ptscripts import Context, command_group

import tools.pkg
import tools.utils
from tools.utils import Version, parse_versions
from tools.utils.repo import (
    create_full_repo_path,
    create_top_level_repo_path,
    get_repo_json_file_contents,
)

log = logging.getLogger(__name__)

create = command_group(
    name="create",
    help="Packaging Repository Creation Related Commands",
    parent=["pkg", "repo"],
)


_deb_distro_info = {
    "debian": {
        "10": {
            "label": "deb10ary",
            "codename": "buster",
            "suitename": "oldoldstable",
        },
        "11": {
            "label": "deb11ary",
            "codename": "bullseye",
            "suitename": "oldstable",
        },
        "12": {
            "label": "deb12ary",
            "codename": "bookworm",
            "suitename": "stable",
        },
    },
    "ubuntu": {
        "20.04": {
            "label": "salt_ubuntu2004",
            "codename": "focal",
        },
        "22.04": {
            "label": "salt_ubuntu2204",
            "codename": "jammy",
        },
        "23.04": {
            "label": "salt_ubuntu2304",
            "codename": "lunar",
        },
    },
}


@create.command(
    name="deb",
    arguments={
        "salt_version": {
            "help": (
                "The salt version for which to build the repository configuration files. "
                "If not passed, it will be discovered by running 'python3 salt/version.py'."
            ),
            "required": True,
        },
        "distro": {
            "help": "The debian based distribution to build the repository for",
            "choices": list(_deb_distro_info),
            "required": True,
        },
        "distro_version": {
            "help": "The distro version.",
            "required": True,
        },
        "distro_arch": {
            "help": "The distribution architecture",
            "choices": ("x86_64", "amd64", "aarch64", "arm64"),
        },
        "repo_path": {
            "help": "Path where the repository shall be created.",
            "required": True,
        },
        "key_id": {
            "help": "The GnuPG key ID used to sign.",
            "required": True,
        },
        "incoming": {
            "help": (
                "The path to the directory containing the files that should added to "
                "the repository."
            ),
            "required": True,
        },
        "nightly_build_from": {
            "help": "Developement repository target",
        },
    },
)
def debian(
    ctx: Context,
    salt_version: str = None,
    distro: str = None,
    distro_version: str = None,
    incoming: pathlib.Path = None,
    repo_path: pathlib.Path = None,
    key_id: str = None,
    distro_arch: str = "amd64",
    nightly_build_from: str = None,
):
    """
    Create the debian repository.
    """
    if TYPE_CHECKING:
        assert salt_version is not None
        assert distro is not None
        assert distro_version is not None
        assert incoming is not None
        assert repo_path is not None
        assert key_id is not None
    display_name = f"{distro.capitalize()} {distro_version}"
    if distro_version not in _deb_distro_info[distro]:
        ctx.error(f"Support for {display_name} is missing.")
        ctx.exit(1)

    if distro_arch == "x86_64":
        ctx.info(f"The {distro_arch} arch is an alias for 'amd64'. Adjusting.")
        distro_arch = "amd64"

    if distro_arch == "aarch64":
        ctx.info(f"The {distro_arch} arch is an alias for 'arm64'. Adjusting.")
        distro_arch = "arm64"

    distro_details = _deb_distro_info[distro][distro_version]

    ctx.info("Distribution Details:")
    ctx.print(distro_details, soft_wrap=True)
    if TYPE_CHECKING:
        assert isinstance(distro_details["label"], str)
        assert isinstance(distro_details["codename"], str)
        assert isinstance(distro_details["suitename"], str)
    label: str = distro_details["label"]
    codename: str = distro_details["codename"]

    ftp_archive_config_suite = ""
    if distro == "debian":
        suitename: str = distro_details["suitename"]
        ftp_archive_config_suite = (
            f"""\n    APT::FTPArchive::Release::Suite "{suitename}";\n"""
        )
    archive_description = f"SaltProject {display_name} Python 3{'' if not nightly_build_from else ' development'} Salt package repo"
    ftp_archive_config = f"""\
    APT::FTPArchive::Release::Origin "SaltProject";
    APT::FTPArchive::Release::Label "{label}";{ftp_archive_config_suite}
    APT::FTPArchive::Release::Codename "{codename}";
    APT::FTPArchive::Release::Architectures "{distro_arch}";
    APT::FTPArchive::Release::Components "main";
    APT::FTPArchive::Release::Description "{archive_description}";
    APT::FTPArchive::Release::Acquire-By-Hash "yes";
    Dir {{
        ArchiveDir ".";
    }};
    BinDirectory "pool" {{
        Packages "dists/{codename}/main/binary-{distro_arch}/Packages";
        Sources "dists/{codename}/main/source/Sources";
        Contents "dists/{codename}/main/Contents-{distro_arch}";
    }}
    """
    ctx.info("Creating repository directory structure ...")
    create_repo_path = create_top_level_repo_path(
        ctx,
        repo_path,
        salt_version,
        distro,
        distro_version=distro_version,
        distro_arch=distro_arch,
        nightly_build_from=nightly_build_from,
    )
    # Export the GPG key in use
    tools.utils.export_gpg_key(ctx, key_id, create_repo_path)

    create_repo_path = create_full_repo_path(
        ctx,
        repo_path,
        salt_version,
        distro,
        distro_version=distro_version,
        distro_arch=distro_arch,
        nightly_build_from=nightly_build_from,
    )
    ftp_archive_config_file = create_repo_path / "apt-ftparchive.conf"
    ctx.info(f"Writing {ftp_archive_config_file} ...")
    ftp_archive_config_file.write_text(textwrap.dedent(ftp_archive_config))

    # Export the GPG key in use
    tools.utils.export_gpg_key(ctx, key_id, create_repo_path)

    pool_path = create_repo_path / "pool"
    pool_path.mkdir(exist_ok=True)
    for fpath in incoming.iterdir():
        dpath = pool_path / fpath.name
        ctx.info(f"Copying {fpath} to {dpath} ...")
        shutil.copyfile(fpath, dpath)
        if fpath.suffix == ".dsc":
            ctx.info(f"Running 'debsign' on {dpath} ...")
            ctx.run("debsign", "--re-sign", "-k", key_id, str(dpath), interactive=True)

    dists_path = create_repo_path / "dists"
    symlink_parent_path = dists_path / codename / "main"
    symlink_paths = (
        symlink_parent_path / "by-hash" / "SHA256",
        symlink_parent_path / "source" / "by-hash" / "SHA256",
        symlink_parent_path / f"binary-{distro_arch}" / "by-hash" / "SHA256",
    )

    for path in symlink_paths:
        path.mkdir(exist_ok=True, parents=True)

    cmdline = ["apt-ftparchive", "generate", "apt-ftparchive.conf"]
    ctx.info(f"Running '{' '.join(cmdline)}' ...")
    ctx.run(*cmdline, cwd=create_repo_path)

    ctx.info("Creating by-hash symlinks ...")
    for path in symlink_paths:
        for fpath in path.parent.parent.iterdir():
            if not fpath.is_file():
                continue
            sha256sum = ctx.run("sha256sum", str(fpath), capture=True)
            link = path / sha256sum.stdout.decode().split()[0]
            link.symlink_to(f"../../{fpath.name}")

    cmdline = [
        "apt-ftparchive",
        "--no-md5",
        "--no-sha1",
        "--no-sha512",
        "release",
        "-c",
        "apt-ftparchive.conf",
        f"dists/{codename}/",
    ]
    ctx.info(f"Running '{' '.join(cmdline)}' ...")
    ret = ctx.run(*cmdline, capture=True, cwd=create_repo_path)
    release_file = dists_path / codename / "Release"
    ctx.info(f"Writing {release_file}  with the output of the previous command...")
    release_file.write_bytes(ret.stdout)

    cmdline = [
        "gpg",
        "-u",
        key_id,
        "-o",
        f"dists/{codename}/InRelease",
        "-a",
        "-s",
        "--clearsign",
        f"dists/{codename}/Release",
    ]
    ctx.info(f"Running '{' '.join(cmdline)}' ...")
    ctx.run(*cmdline, cwd=create_repo_path)

    cmdline = [
        "gpg",
        "-u",
        key_id,
        "-o",
        f"dists/{codename}/Release.gpg",
        "-a",
        "-b",
        "-s",
        f"dists/{codename}/Release",
    ]

    ctx.info(f"Running '{' '.join(cmdline)}' ...")
    ctx.run(*cmdline, cwd=create_repo_path)
    if not nightly_build_from:
        remote_versions = _get_remote_versions(
            tools.utils.STAGING_BUCKET_NAME,
            create_repo_path.parent.relative_to(repo_path),
        )
        major_version = Version(salt_version).major
        matching_major = None
        for version in remote_versions:
            if version.major == major_version:
                matching_major = version
                break
        if not matching_major or matching_major <= salt_version:
            major_link = create_repo_path.parent.parent / str(major_version)
            ctx.info(f"Creating '{major_link.relative_to(repo_path)}' symlink ...")
            major_link.symlink_to(f"minor/{salt_version}")
        if not remote_versions or remote_versions[0] <= salt_version:
            latest_link = create_repo_path.parent.parent / "latest"
            ctx.info(f"Creating '{latest_link.relative_to(repo_path)}' symlink ...")
            latest_link.symlink_to(f"minor/{salt_version}")

    ctx.info("Done")


_rpm_distro_info = {
    "amazon": ["2", "2023"],
    "redhat": ["7", "8", "9"],
    "fedora": ["36", "37", "38"],
    "photon": ["3", "4", "5"],
}


@create.command(
    name="rpm",
    arguments={
        "salt_version": {
            "help": (
                "The salt version for which to build the repository configuration files. "
                "If not passed, it will be discovered by running 'python3 salt/version.py'."
            ),
            "required": True,
        },
        "distro": {
            "help": "The debian based distribution to build the repository for",
            "choices": list(_rpm_distro_info),
            "required": True,
        },
        "distro_version": {
            "help": "The distro version.",
            "required": True,
        },
        "distro_arch": {
            "help": "The distribution architecture",
            "choices": ("x86_64", "aarch64", "arm64"),
        },
        "repo_path": {
            "help": "Path where the repository shall be created.",
            "required": True,
        },
        "key_id": {
            "help": "The GnuPG key ID used to sign.",
            "required": True,
        },
        "incoming": {
            "help": (
                "The path to the directory containing the files that should added to "
                "the repository."
            ),
            "required": True,
        },
        "nightly_build_from": {
            "help": "Developement repository target",
        },
    },
)
def rpm(
    ctx: Context,
    salt_version: str = None,
    distro: str = None,
    distro_version: str = None,
    incoming: pathlib.Path = None,
    repo_path: pathlib.Path = None,
    key_id: str = None,
    distro_arch: str = "amd64",
    nightly_build_from: str = None,
):
    """
    Create the redhat repository.
    """
    if TYPE_CHECKING:
        assert salt_version is not None
        assert distro is not None
        assert distro_version is not None
        assert incoming is not None
        assert repo_path is not None
        assert key_id is not None

    display_name = f"{distro.capitalize()} {distro_version}"
    if distro_version not in _rpm_distro_info[distro]:
        ctx.error(f"Support for {display_name} is missing.")
        ctx.exit(1)

    if distro == "photon":
        distro_version = f"{distro_version}.0"

    ctx.info("Creating repository directory structure ...")
    create_repo_path = create_top_level_repo_path(
        ctx,
        repo_path,
        salt_version,
        distro,
        distro_version=distro_version,
        distro_arch=distro_arch,
        nightly_build_from=nightly_build_from,
    )
    # Export the GPG key in use
    tools.utils.export_gpg_key(ctx, key_id, create_repo_path)

    create_repo_path = create_full_repo_path(
        ctx,
        repo_path,
        salt_version,
        distro,
        distro_version=distro_version,
        distro_arch=distro_arch,
        nightly_build_from=nightly_build_from,
    )

    # Export the GPG key in use
    tools.utils.export_gpg_key(ctx, key_id, create_repo_path)

    for fpath in incoming.iterdir():
        if ".src" in fpath.suffixes:
            dpath = create_repo_path / "SRPMS" / fpath.name
        else:
            dpath = create_repo_path / fpath.name
        ctx.info(f"Copying {fpath} to {dpath} ...")
        shutil.copyfile(fpath, dpath)
        if fpath.suffix == ".rpm":
            ctx.info(f"Running 'rpmsign' on {dpath} ...")
            ctx.run(
                "rpmsign",
                "--key-id",
                key_id,
                "--addsign",
                "--digest-algo=sha256",
                str(dpath),
            )

    createrepo = shutil.which("createrepo")
    if createrepo is None:
        container = "ghcr.io/saltstack/salt-ci-containers/packaging:centosstream-9"
        ctx.info(f"Using docker container '{container}' to call 'createrepo'...")
        uid = ctx.run("id", "-u", capture=True).stdout.strip().decode()
        gid = ctx.run("id", "-g", capture=True).stdout.strip().decode()
        ctx.run(
            "docker",
            "run",
            "--rm",
            "-v",
            f"{create_repo_path.resolve()}:/code",
            "-u",
            f"{uid}:{gid}",
            "-w",
            "/code",
            container,
            "createrepo",
            ".",
        )
    else:
        ctx.run("createrepo", ".", cwd=create_repo_path)

    if nightly_build_from:
        repo_domain = os.environ.get("SALT_REPO_DOMAIN_RELEASE", "repo.saltproject.io")
    else:
        repo_domain = os.environ.get(
            "SALT_REPO_DOMAIN_STAGING", "staging.repo.saltproject.io"
        )

    salt_repo_user = os.environ.get("SALT_REPO_USER")
    if salt_repo_user:
        log.info(
            "SALT_REPO_USER: %s",
            salt_repo_user[0] + "*" * (len(salt_repo_user) - 2) + salt_repo_user[-1],
        )
    salt_repo_pass = os.environ.get("SALT_REPO_PASS")
    if salt_repo_pass:
        log.info(
            "SALT_REPO_PASS: %s",
            salt_repo_pass[0] + "*" * (len(salt_repo_pass) - 2) + salt_repo_pass[-1],
        )
    if salt_repo_user and salt_repo_pass:
        repo_domain = f"{salt_repo_user}:{salt_repo_pass}@{repo_domain}"

    def _create_repo_file(create_repo_path, url_suffix):
        ctx.info(f"Creating '{repo_file_path.relative_to(repo_path)}' file ...")
        if nightly_build_from:
            base_url = f"salt-dev/{nightly_build_from}/{datetime.utcnow().strftime('%Y-%m-%d')}/"
            repo_file_contents = "[salt-nightly-repo]"
        elif "rc" in salt_version:
            base_url = "salt_rc/"
            repo_file_contents = "[salt-rc-repo]"
        else:
            base_url = ""
            repo_file_contents = "[salt-repo]"
        base_url += f"salt/py3/{distro}/{distro_version}/{distro_arch}/{url_suffix}"
        if distro == "amazon":
            distro_name = "Amazon Linux"
        elif distro == "redhat":
            distro_name = "RHEL/CentOS"
        else:
            distro_name = distro.capitalize()

        if distro != "photon" and int(distro_version) < 8:
            failovermethod = "\n            failovermethod=priority"
        else:
            failovermethod = ""

        repo_file_contents += textwrap.dedent(
            f"""
            name=Salt repo for {distro_name} {distro_version} PY3
            baseurl=https://{repo_domain}/{base_url}
            skip_if_unavailable=True{failovermethod}
            priority=10
            enabled=1
            enabled_metadata=1
            gpgcheck=1
            gpgkey=https://{repo_domain}/{base_url}/{tools.utils.GPG_KEY_FILENAME}.pub
            """
        )
        create_repo_path.write_text(repo_file_contents)

    if nightly_build_from:
        repo_file_path = create_repo_path.parent / "nightly.repo"
    else:
        repo_file_path = create_repo_path.parent / f"{create_repo_path.name}.repo"

    _create_repo_file(repo_file_path, f"minor/{salt_version}")

    if not nightly_build_from:
        remote_versions = _get_remote_versions(
            tools.utils.STAGING_BUCKET_NAME,
            create_repo_path.parent.relative_to(repo_path),
        )
        major_version = Version(salt_version).major
        matching_major = None
        for version in remote_versions:
            if version.major == major_version:
                matching_major = version
                break
        if not matching_major or matching_major <= salt_version:
            major_link = create_repo_path.parent.parent / str(major_version)
            ctx.info(f"Creating '{major_link.relative_to(repo_path)}' symlink ...")
            major_link.symlink_to(f"minor/{salt_version}")
            repo_file_path = create_repo_path.parent.parent / f"{major_version}.repo"
            _create_repo_file(repo_file_path, str(major_version))
        if not remote_versions or remote_versions[0] <= salt_version:
            latest_link = create_repo_path.parent.parent / "latest"
            ctx.info(f"Creating '{latest_link.relative_to(repo_path)}' symlink ...")
            latest_link.symlink_to(f"minor/{salt_version}")
            repo_file_path = create_repo_path.parent.parent / "latest.repo"
            _create_repo_file(repo_file_path, "latest")

    ctx.info("Done")


@create.command(
    name="windows",
    arguments={
        "salt_version": {
            "help": "The salt version for which to build the repository",
            "required": True,
        },
        "repo_path": {
            "help": "Path where the repository shall be created.",
            "required": True,
        },
        "key_id": {
            "help": "The GnuPG key ID used to sign.",
            "required": True,
        },
        "incoming": {
            "help": (
                "The path to the directory containing the files that should added to "
                "the repository."
            ),
            "required": True,
        },
        "nightly_build_from": {
            "help": "Developement repository target",
        },
    },
)
def windows(
    ctx: Context,
    salt_version: str = None,
    incoming: pathlib.Path = None,
    repo_path: pathlib.Path = None,
    key_id: str = None,
    nightly_build_from: str = None,
):
    """
    Create the windows repository.
    """
    if TYPE_CHECKING:
        assert salt_version is not None
        assert incoming is not None
        assert repo_path is not None
        assert key_id is not None
    _create_onedir_based_repo(
        ctx,
        salt_version=salt_version,
        nightly_build_from=nightly_build_from,
        repo_path=repo_path,
        incoming=incoming,
        key_id=key_id,
        distro="windows",
        pkg_suffixes=(".msi", ".exe"),
    )
    ctx.info("Done")


@create.command(
    name="macos",
    arguments={
        "salt_version": {
            "help": "The salt version for which to build the repository",
            "required": True,
        },
        "repo_path": {
            "help": "Path where the repository shall be created.",
            "required": True,
        },
        "key_id": {
            "help": "The GnuPG key ID used to sign.",
            "required": True,
        },
        "incoming": {
            "help": (
                "The path to the directory containing the files that should added to "
                "the repository."
            ),
            "required": True,
        },
        "nightly_build_from": {
            "help": "Developement repository target",
        },
    },
)
def macos(
    ctx: Context,
    salt_version: str = None,
    incoming: pathlib.Path = None,
    repo_path: pathlib.Path = None,
    key_id: str = None,
    nightly_build_from: str = None,
):
    """
    Create the windows repository.
    """
    if TYPE_CHECKING:
        assert salt_version is not None
        assert incoming is not None
        assert repo_path is not None
        assert key_id is not None
    _create_onedir_based_repo(
        ctx,
        salt_version=salt_version,
        nightly_build_from=nightly_build_from,
        repo_path=repo_path,
        incoming=incoming,
        key_id=key_id,
        distro="macos",
        pkg_suffixes=(".pkg",),
    )
    ctx.info("Done")


@create.command(
    name="onedir",
    arguments={
        "salt_version": {
            "help": "The salt version for which to build the repository",
            "required": True,
        },
        "repo_path": {
            "help": "Path where the repository shall be created.",
            "required": True,
        },
        "key_id": {
            "help": "The GnuPG key ID used to sign.",
            "required": True,
        },
        "incoming": {
            "help": (
                "The path to the directory containing the files that should added to "
                "the repository."
            ),
            "required": True,
        },
        "nightly_build_from": {
            "help": "Developement repository target",
        },
    },
)
def onedir(
    ctx: Context,
    salt_version: str = None,
    incoming: pathlib.Path = None,
    repo_path: pathlib.Path = None,
    key_id: str = None,
    nightly_build_from: str = None,
):
    """
    Create the onedir repository.
    """
    if TYPE_CHECKING:
        assert salt_version is not None
        assert incoming is not None
        assert repo_path is not None
        assert key_id is not None
    _create_onedir_based_repo(
        ctx,
        salt_version=salt_version,
        nightly_build_from=nightly_build_from,
        repo_path=repo_path,
        incoming=incoming,
        key_id=key_id,
        distro="onedir",
        pkg_suffixes=(".xz", ".zip"),
    )
    ctx.info("Done")


@create.command(
    name="src",
    arguments={
        "salt_version": {
            "help": "The salt version for which to build the repository",
            "required": True,
        },
        "repo_path": {
            "help": "Path where the repository shall be created.",
            "required": True,
        },
        "key_id": {
            "help": "The GnuPG key ID used to sign.",
            "required": True,
        },
        "incoming": {
            "help": (
                "The path to the directory containing the files that should added to "
                "the repository."
            ),
            "required": True,
        },
        "nightly_build_from": {
            "help": "Developement repository target",
        },
    },
)
def src(
    ctx: Context,
    salt_version: str = None,
    incoming: pathlib.Path = None,
    repo_path: pathlib.Path = None,
    key_id: str = None,
    nightly_build_from: str = None,
):
    """
    Create the onedir repository.
    """
    if TYPE_CHECKING:
        assert salt_version is not None
        assert incoming is not None
        assert repo_path is not None
        assert key_id is not None

    ctx.info("Creating repository directory structure ...")
    create_repo_path = create_top_level_repo_path(
        ctx,
        repo_path,
        salt_version,
        distro="src",
        nightly_build_from=nightly_build_from,
    )
    # Export the GPG key in use
    tools.utils.export_gpg_key(ctx, key_id, create_repo_path)
    create_repo_path = create_repo_path / salt_version
    create_repo_path.mkdir(exist_ok=True, parents=True)
    hashes_base_path = create_repo_path / f"salt-{salt_version}"
    for fpath in incoming.iterdir():
        if fpath.suffix not in (".gz",):
            continue
        ctx.info(f"* Processing {fpath} ...")
        dpath = create_repo_path / fpath.name
        ctx.info(f"Copying {fpath} to {dpath} ...")
        shutil.copyfile(fpath, dpath)
        for hash_name in ("blake2b", "sha512", "sha3_512"):
            ctx.info(f"   * Calculating {hash_name} ...")
            hexdigest = _get_file_checksum(fpath, hash_name)
            with open(
                f"{hashes_base_path}_{hash_name.upper()}", "a+", encoding="utf-8"
            ) as wfh:
                wfh.write(f"{hexdigest} {dpath.name}\n")
            with open(f"{dpath}.{hash_name}", "a+", encoding="utf-8") as wfh:
                wfh.write(f"{hexdigest} {dpath.name}\n")

    for fpath in create_repo_path.iterdir():
        if fpath.suffix in (".pub", ".gpg"):
            continue
        tools.utils.gpg_sign(ctx, key_id, fpath)

    # Export the GPG key in use
    tools.utils.export_gpg_key(ctx, key_id, create_repo_path)
    ctx.info("Done")


def _get_remote_versions(bucket_name: str, remote_path: str):
    log.info(
        "Getting remote versions from bucket %r under path: %s",
        bucket_name,
        remote_path,
    )
    remote_path = str(remote_path)
    if not remote_path.endswith("/"):
        remote_path += "/"

    s3 = boto3.client("s3")
    ret = s3.list_objects(
        Bucket=bucket_name,
        Delimiter="/",
        Prefix=remote_path,
    )
    if "CommonPrefixes" not in ret:
        return []
    versions = []
    for entry in ret["CommonPrefixes"]:
        _, version = entry["Prefix"].rstrip("/").rsplit("/", 1)
        if version == "latest":
            continue
        versions.append(Version(version))
    versions.sort(reverse=True)
    log.info("Remote versions collected: %s", versions)
    return versions


def _create_onedir_based_repo(
    ctx: Context,
    salt_version: str,
    nightly_build_from: str | None,
    repo_path: pathlib.Path,
    incoming: pathlib.Path,
    key_id: str,
    distro: str,
    pkg_suffixes: tuple[str, ...],
):
    ctx.info("Creating repository directory structure ...")
    create_repo_path = create_top_level_repo_path(
        ctx,
        repo_path,
        salt_version,
        distro,
        nightly_build_from=nightly_build_from,
    )
    # Export the GPG key in use
    tools.utils.export_gpg_key(ctx, key_id, create_repo_path)

    create_repo_path = create_full_repo_path(
        ctx,
        repo_path,
        salt_version,
        distro,
        nightly_build_from=nightly_build_from,
    )
    if not nightly_build_from:
        repo_json_path = create_repo_path.parent.parent / "repo.json"
    else:
        repo_json_path = create_repo_path.parent / "repo.json"

    if nightly_build_from:
        bucket_name = tools.utils.RELEASE_BUCKET_NAME
    else:
        bucket_name = tools.utils.STAGING_BUCKET_NAME

    release_json = {}

    copy_exclusions = (
        ".blake2b",
        ".sha512",
        ".sha3_512",
        ".BLAKE2B",
        ".SHA512",
        ".SHA3_512",
        ".json",
    )
    hashes_base_path = create_repo_path / f"salt-{salt_version}"
    for fpath in incoming.iterdir():
        if fpath.suffix in copy_exclusions:
            continue
        ctx.info(f"* Processing {fpath} ...")
        dpath = create_repo_path / fpath.name
        ctx.info(f"Copying {fpath} to {dpath} ...")
        shutil.copyfile(fpath, dpath)
        if "-amd64" in dpath.name.lower():
            arch = "amd64"
        elif "-x86_64" in dpath.name.lower():
            arch = "x86_64"
        elif "-x86" in dpath.name.lower():
            arch = "x86"
        elif "-aarch64" in dpath.name.lower():
            arch = "aarch64"
        elif "-arm64" in dpath.name.lower():
            arch = "arm64"
        else:
            ctx.error(
                f"Cannot pickup the right architecture from the filename '{dpath.name}'."
            )
            ctx.exit(1)
        if distro == "onedir":
            if "-onedir-linux-" in dpath.name.lower():
                release_os = "linux"
            elif "-onedir-macos-" in dpath.name.lower():
                release_os = "macos"
            elif "-onedir-windows-" in dpath.name.lower():
                release_os = "windows"
            else:
                ctx.error(
                    f"Cannot pickup the right OS from the filename '{dpath.name}'."
                )
                ctx.exit(1)
        else:
            release_os = distro
        release_json[dpath.name] = {
            "name": dpath.name,
            "version": salt_version,
            "os": release_os,
            "arch": arch,
        }
        for hash_name in ("blake2b", "sha512", "sha3_512"):
            ctx.info(f"   * Calculating {hash_name} ...")
            hexdigest = _get_file_checksum(fpath, hash_name)
            release_json[dpath.name][hash_name.upper()] = hexdigest
            with open(
                f"{hashes_base_path}_{hash_name.upper()}", "a+", encoding="utf-8"
            ) as wfh:
                wfh.write(f"{hexdigest} {dpath.name}\n")
            with open(f"{dpath}.{hash_name}", "a+", encoding="utf-8") as wfh:
                wfh.write(f"{hexdigest} {dpath.name}\n")

    for fpath in create_repo_path.iterdir():
        if fpath.suffix in pkg_suffixes:
            continue
        tools.utils.gpg_sign(ctx, key_id, fpath)

    # Export the GPG key in use
    tools.utils.export_gpg_key(ctx, key_id, create_repo_path)

    repo_json = get_repo_json_file_contents(
        ctx, bucket_name=bucket_name, repo_path=repo_path, repo_json_path=repo_json_path
    )
    if nightly_build_from:
        ctx.info(f"Writing {repo_json_path} ...")
        repo_json_path.write_text(json.dumps(repo_json, sort_keys=True))
        return

    major_version = Version(salt_version).major
    minor_repo_json_path = create_repo_path.parent / "repo.json"
    minor_repo_json = get_repo_json_file_contents(
        ctx,
        bucket_name=bucket_name,
        repo_path=repo_path,
        repo_json_path=minor_repo_json_path,
    )
    minor_repo_json[salt_version] = release_json
    versions = parse_versions(*list(minor_repo_json))
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

    latest_link = create_repo_path.parent.parent / "latest"
    if latest_version <= salt_version:
        repo_json["latest"] = release_json
        ctx.info(f"Creating '{latest_link.relative_to(repo_path)}' symlink ...")
        if latest_link.exists():
            latest_link.unlink()
        latest_link.symlink_to(f"minor/{salt_version}")
    else:
        ctx.info(
            f"Not creating the '{latest_link.relative_to(repo_path)}' symlink "
            f"since {latest_version} > {salt_version}"
        )

    major_link = create_repo_path.parent.parent / str(major_version)
    if latest_minor_version <= salt_version:
        minor_repo_json["latest"] = release_json
        # This is the latest minor, update the major in the top level repo.json
        # to this version
        repo_json[str(major_version)] = release_json
        ctx.info(f"Creating '{major_link.relative_to(repo_path)}' symlink ...")
        if major_link.exists():
            major_link.unlink()
        major_link.symlink_to(f"minor/{salt_version}")
    else:
        ctx.info(
            f"Not creating the '{major_link.relative_to(repo_path)}' symlink "
            f"since {latest_minor_version} > {salt_version}"
        )

    ctx.info(f"Writing {minor_repo_json_path} ...")
    minor_repo_json_path.write_text(json.dumps(minor_repo_json, sort_keys=True))

    ctx.info(f"Writing {repo_json_path} ...")
    repo_json_path.write_text(json.dumps(repo_json, sort_keys=True))


def _get_file_checksum(fpath: pathlib.Path, hash_name: str) -> str:

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
