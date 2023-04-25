"""
These commands are used to build the pacakge repository files.
"""
# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import fnmatch
import hashlib
import json
import logging
import os
import pathlib
import re
import shutil
import sys
import tempfile
import textwrap
from datetime import datetime
from typing import TYPE_CHECKING, Any

import packaging.version
from ptscripts import Context, command_group

import tools.pkg
import tools.utils
from tools.utils import Version, get_salt_releases

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
repo = command_group(
    name="repo",
    help="Packaging Repository Related Commands",
    description=__doc__,
    parent="pkg",
)

create = command_group(
    name="create", help="Packaging Repository Creation Related Commands", parent=repo
)

publish = command_group(
    name="publish",
    help="Packaging Repository Publication Related Commands",
    parent=repo,
)


_deb_distro_info = {
    "debian": {
        "10": {
            "label": "deb10ary",
            "codename": "buster",
            "suitename": "oldstable",
        },
        "11": {
            "label": "deb11ary",
            "codename": "bullseye",
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
    ctx.info(distro_details)
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
    create_repo_path = _create_top_level_repo_path(
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

    create_repo_path = _create_repo_path(
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
    "amazon": ["2"],
    "redhat": ["7", "8", "9"],
    "fedora": ["36", "37", "38"],
    "photon": ["3", "4"],
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

    if distro_arch == "aarch64":
        ctx.info(f"The {distro_arch} arch is an alias for 'arm64'. Adjusting.")
        distro_arch = "arm64"

    ctx.info("Creating repository directory structure ...")
    create_repo_path = _create_top_level_repo_path(
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

    create_repo_path = _create_repo_path(
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
            base_url = f"salt-dev/{nightly_build_from}/"
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
    create_repo_path = _create_top_level_repo_path(
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
            with open(f"{hashes_base_path}_{hash_name.upper()}", "a+") as wfh:
                wfh.write(f"{hexdigest} {dpath.name}\n")
            with open(f"{dpath}.{hash_name}", "a+") as wfh:
                wfh.write(f"{hexdigest} {dpath.name}\n")

    for fpath in create_repo_path.iterdir():
        if fpath.suffix in (".pub", ".gpg"):
            continue
        tools.utils.gpg_sign(ctx, key_id, fpath)

    # Export the GPG key in use
    tools.utils.export_gpg_key(ctx, key_id, create_repo_path)
    ctx.info("Done")


@publish.command(
    arguments={
        "repo_path": {
            "help": "Local path for the repository that shall be published.",
        },
        "salt_version": {
            "help": "The salt version for which to build the repository",
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
            "help": "The salt version for which to build the repository",
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
            wfh.write(f"backup-complete=true\n")
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
    ]
    if src == tools.utils.RELEASE_BUCKET_NAME:
        cmdline.append("--s3-storage-class=INTELLIGENT_TIERING")
    cmdline.extend([f"s3://{src}", f"s3://{dst}"])
    ctx.info(f"Running: {' '.join(cmdline)}")
    ret = ctx.run(*cmdline, env=env, check=False)
    if ret.returncode:
        ctx.error(f"Failed to sync from s3://{src} to s3://{dst}")
        ctx.exit(1)


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
                log.exception(f"Error downloading {repo_release_files_path}: {exc}")
                ctx.exit(1)
            if exc.response["Error"]["Code"] == "404":
                ctx.error(f"Could not find {repo_release_files_path} in bucket.")
                ctx.exit(1)
            if exc.response["Error"]["Code"] == "400":
                ctx.error(
                    f"Could not download {repo_release_files_path} from bucket: {exc}"
                )
                ctx.exit(1)
            log.exception(f"Error downloading {repo_release_files_path}: {exc}")
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
                log.exception(f"Error downloading {repo_release_symlinks_path}: {exc}")
                ctx.exit(1)
            if exc.response["Error"]["Code"] == "404":
                ctx.error(f"Could not find {repo_release_symlinks_path} in bucket.")
                ctx.exit(1)
            if exc.response["Error"]["Code"] == "400":
                ctx.error(
                    f"Could not download {repo_release_symlinks_path} from bucket: {exc}"
                )
                ctx.exit(1)
            log.exception(f"Error downloading {repo_release_symlinks_path}: {exc}")
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
                log.exception(f"Failed to copy {fpath}")
            finally:
                progress.update(task, advance=1)

    # Now let's get the onedir based repositories where we need to update several repo.json
    major_version = packaging.version.parse(salt_version).major
    with tempfile.TemporaryDirectory(prefix=f"{salt_version}_release_") as tsd:
        repo_path = pathlib.Path(tsd)
        for distro in ("windows", "macos", "onedir"):

            create_repo_path = _create_repo_path(
                ctx,
                repo_path,
                salt_version,
                distro=distro,
            )
            repo_json_path = create_repo_path.parent.parent / "repo.json"

            release_repo_json = _get_repo_json_file_contents(
                ctx,
                bucket_name=tools.utils.RELEASE_BUCKET_NAME,
                repo_path=repo_path,
                repo_json_path=repo_json_path,
            )
            minor_repo_json_path = create_repo_path.parent / "repo.json"

            staging_minor_repo_json = _get_repo_json_file_contents(
                ctx,
                bucket_name=tools.utils.STAGING_BUCKET_NAME,
                repo_path=repo_path,
                repo_json_path=minor_repo_json_path,
            )
            release_minor_repo_json = _get_repo_json_file_contents(
                ctx,
                bucket_name=tools.utils.RELEASE_BUCKET_NAME,
                repo_path=repo_path,
                repo_json_path=minor_repo_json_path,
            )

            release_json = staging_minor_repo_json[salt_version]

            major_version = Version(salt_version).major
            versions = _parse_versions(*list(release_minor_repo_json))
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
                        Callback=tools.utils.UpdateProgress(progress, task),
                    )
                updated_contents = re.sub(
                    r"^(baseurl|gpgkey)=https://([^/]+)/(.*)$",
                    rf"\1=https://{release_domain}/\3",
                    repo_file_path.read_text(),
                    flags=re.MULTILINE,
                )
                ctx.info(f"Updated '{repo_file_path.relative_to(repo_path)}:")
                ctx.print(updated_contents)
                repo_file_path.write_text(updated_contents)
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
                        Callback=tools.utils.UpdateProgress(progress, task),
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
                Callback=tools.utils.UpdateProgress(progress, task),
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

    releases = get_salt_releases(ctx, repository)
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
                log.exception(f"Could not get information about {remote_path}: {exc}")
                ctx.exit(1)
            if exc.response["Error"]["Code"] == "404":
                ctx.error(f"Could not find {remote_path} in bucket.")
                ctx.exit(1)
            if exc.response["Error"]["Code"] == "400":
                ctx.error(f"Could get information about {remote_path}: {exc}")
                ctx.exit(1)
            log.exception(f"Error getting information about {remote_path}: {exc}")
            ctx.exit(1)
    ctx.info(f"Version {salt_version} has been staged for release")
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
    create_repo_path = _create_top_level_repo_path(
        ctx,
        repo_path,
        salt_version,
        distro,
        nightly_build_from=nightly_build_from,
    )
    # Export the GPG key in use
    tools.utils.export_gpg_key(ctx, key_id, create_repo_path)

    create_repo_path = _create_repo_path(
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
        else:
            ctx.error(
                f"Cannot pickup the right architecture from the filename '{dpath.name}'."
            )
            ctx.exit(1)
        if distro == "onedir":
            if "-onedir-linux-" in dpath.name.lower():
                release_os = "linux"
            elif "-onedir-darwin-" in dpath.name.lower():
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
            with open(f"{hashes_base_path}_{hash_name.upper()}", "a+") as wfh:
                wfh.write(f"{hexdigest} {dpath.name}\n")
            with open(f"{dpath}.{hash_name}", "a+") as wfh:
                wfh.write(f"{hexdigest} {dpath.name}\n")

    for fpath in create_repo_path.iterdir():
        if fpath.suffix in pkg_suffixes:
            continue
        tools.utils.gpg_sign(ctx, key_id, fpath)

    # Export the GPG key in use
    tools.utils.export_gpg_key(ctx, key_id, create_repo_path)

    repo_json = _get_repo_json_file_contents(
        ctx, bucket_name=bucket_name, repo_path=repo_path, repo_json_path=repo_json_path
    )
    if nightly_build_from:
        ctx.info(f"Writing {repo_json_path} ...")
        repo_json_path.write_text(json.dumps(repo_json, sort_keys=True))
        return

    major_version = Version(salt_version).major
    minor_repo_json_path = create_repo_path.parent / "repo.json"
    minor_repo_json = _get_repo_json_file_contents(
        ctx,
        bucket_name=bucket_name,
        repo_path=repo_path,
        repo_json_path=minor_repo_json_path,
    )
    minor_repo_json[salt_version] = release_json
    versions = _parse_versions(*list(minor_repo_json))
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


def _get_repo_json_file_contents(
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
                Callback=tools.utils.UpdateProgress(progress, task),
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
                log.exception(f"Failed to delete {bucket_uri}")
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
                    Callback=tools.utils.UpdateProgress(progress, task),
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


def _create_top_level_repo_path(
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


def _create_repo_path(
    ctx: Context,
    repo_path: pathlib.Path,
    salt_version: str,
    distro: str,
    distro_version: str | None = None,  # pylint: disable=bad-whitespace
    distro_arch: str | None = None,  # pylint: disable=bad-whitespace
    nightly_build_from: str | None = None,  # pylint: disable=bad-whitespace
):
    create_repo_path = _create_top_level_repo_path(
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


def _parse_versions(*versions: str) -> list[Version]:
    _versions = []
    for version in set(versions):
        if version == "latest":
            continue
        _versions.append(Version(version))
    if _versions:
        _versions.sort(reverse=True)
    return _versions
