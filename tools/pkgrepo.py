"""
These commands are used to build the pacakge repository files.
"""
# pylint: disable=resource-leakage,broad-except
from __future__ import annotations

import hashlib
import json
import logging
import os
import pathlib
import shutil
import sys
import textwrap
from datetime import datetime
from typing import TYPE_CHECKING, Any

import packaging.version
from ptscripts import Context, command_group

import tools.pkg
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
repo = command_group(
    name="repo",
    help="Packaging Repository Related Commands",
    description=__doc__,
    parent=tools.pkg.pkg,
)

create = command_group(
    name="create", help="Packaging Repository Creation Related Commands", parent=repo
)

publish = command_group(
    name="publish",
    help="Packaging Repository Publication Related Commands",
    parent=repo,
)


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
            "choices": ("debian", "ubuntu"),
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
        "nightly_build": {
            "help": "Developement repository target",
        },
        "rc_build": {
            "help": "Release Candidate repository target",
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
    nightly_build: bool = False,
    rc_build: bool = False,
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
    distro_info = {
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
            "18.04": {
                "label": "salt_ubuntu1804",
                "codename": "bionic",
            },
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
    display_name = f"{distro.capitalize()} {distro_version}"
    if distro_version not in distro_info[distro]:
        ctx.error(f"Support for {display_name} is missing.")
        ctx.exit(1)

    if distro_arch == "x86_64":
        ctx.info(f"The {distro_arch} arch is an alias for 'amd64'. Adjusting.")
        distro_arch = "amd64"

    if distro_arch == "aarch64":
        ctx.info(f"The {distro_arch} arch is an alias for 'arm64'. Adjusting.")
        distro_arch = "arm64"

    distro_details = distro_info[distro][distro_version]

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
    archive_description = f"SaltProject {display_name} Python 3{'' if nightly_build else ' development'} Salt package repo"
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
    create_repo_path = _create_repo_path(
        repo_path,
        salt_version,
        distro,
        distro_version=distro_version,
        distro_arch=distro_arch,
        rc_build=rc_build,
        nightly_build=nightly_build,
    )
    ftp_archive_config_file = create_repo_path / "apt-ftparchive.conf"
    ctx.info(f"Writing {ftp_archive_config_file} ...")
    ftp_archive_config_file.write_text(textwrap.dedent(ftp_archive_config))

    # Export the GPG key in use
    tools.utils.export_gpg_key(ctx, key_id, repo_path, create_repo_path)

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
    if nightly_build is False:
        ctx.info("Creating '<major-version>' and 'latest' symlinks ...")
        major_version = Version(salt_version).major
        major_link = create_repo_path.parent.parent / str(major_version)
        major_link.symlink_to(f"minor/{salt_version}")
        latest_link = create_repo_path.parent.parent / "latest"
        latest_link.symlink_to(f"minor/{salt_version}")
    else:
        ctx.info("Creating 'latest' symlink ...")
        latest_link = create_repo_path.parent / "latest"
        latest_link.symlink_to(create_repo_path.name)

    ctx.info("Done")


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
            "choices": ("amazon", "redhat"),
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
        "nightly_build": {
            "help": "Developement repository target",
        },
        "rc_build": {
            "help": "Release Candidate repository target",
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
    nightly_build: bool = False,
    rc_build: bool = False,
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
    distro_info = {
        "amazon": ["2"],
        "redhat": ["7", "8", "9"],
    }
    display_name = f"{distro.capitalize()} {distro_version}"
    if distro_version not in distro_info[distro]:
        ctx.error(f"Support for {display_name} is missing.")
        ctx.exit(1)

    if distro_arch == "aarch64":
        ctx.info(f"The {distro_arch} arch is an alias for 'arm64'. Adjusting.")
        distro_arch = "arm64"

    ctx.info("Creating repository directory structure ...")
    create_repo_path = _create_repo_path(
        repo_path,
        salt_version,
        distro,
        distro_version=distro_version,
        distro_arch=distro_arch,
        rc_build=rc_build,
        nightly_build=nightly_build,
    )

    # Export the GPG key in use
    tools.utils.export_gpg_key(ctx, key_id, repo_path, create_repo_path)

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

    def _create_repo_file(create_repo_path, url_suffix):
        ctx.info(f"Creating '{repo_file_path.relative_to(repo_path)}' file ...")
        if nightly_build:
            base_url = "salt-dev/py3/"
            repo_file_contents = "[salt-nightly-repo]"
        elif rc_build:
            base_url = "salt_rc/py3/"
            repo_file_contents = "[salt-rc-repo]"
        else:
            base_url = "py3/"
            repo_file_contents = "[salt-repo]"
        base_url += f"{distro}/{url_suffix}"
        if distro == "amazon":
            distro_name = "Amazon Linux"
        else:
            distro_name = "RHEL/CentOS"

        if int(distro_version) < 8:
            failovermethod = "\n        failovermethod=priority\n"
        else:
            failovermethod = ""

        repo_file_contents += f"""
        name=Salt repo for {distro_name} {distro_version} PY3
        baseurl=https://repo.saltproject.io/{base_url}
        skip_if_unavailable=True{failovermethod}
        priority=10
        enabled=1
        enabled_metadata=1
        gpgcheck=1
        gpgkey={base_url}/{tools.utils.GPG_KEY_FILENAME}.pub
        """

    if nightly_build:
        repo_file_path = create_repo_path.parent / "nightly.repo"
    elif rc_build:
        repo_file_path = create_repo_path.parent / "rc.repo"
    else:
        repo_file_path = create_repo_path.parent / f"{create_repo_path.name}.repo"

    _create_repo_file(repo_file_path, salt_version)

    if nightly_build is False and rc_build is False:
        ctx.info("Creating '<major-version>' and 'latest' symlinks ...")
        major_version = Version(salt_version).major
        major_link = create_repo_path.parent.parent / str(major_version)
        major_link.symlink_to(f"minor/{salt_version}")
        latest_link = create_repo_path.parent.parent / "latest"
        latest_link.symlink_to(f"minor/{salt_version}")
        for name in (major_version, "latest"):
            repo_file_path = create_repo_path.parent.parent / f"{name}.repo"
            _create_repo_file(repo_file_path, name)
    else:
        ctx.info("Creating 'latest' symlink and 'latest.repo' file ...")
        latest_link = create_repo_path.parent / "latest"
        latest_link.symlink_to(create_repo_path.name)
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
        "nightly_build": {
            "help": "Developement repository target",
        },
        "rc_build": {
            "help": "Release Candidate repository target",
        },
    },
)
def windows(
    ctx: Context,
    salt_version: str = None,
    incoming: pathlib.Path = None,
    repo_path: pathlib.Path = None,
    key_id: str = None,
    nightly_build: bool = False,
    rc_build: bool = False,
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
        nightly_build=nightly_build,
        rc_build=rc_build,
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
        "nightly_build": {
            "help": "Developement repository target",
        },
        "rc_build": {
            "help": "Release Candidate repository target",
        },
    },
)
def macos(
    ctx: Context,
    salt_version: str = None,
    incoming: pathlib.Path = None,
    repo_path: pathlib.Path = None,
    key_id: str = None,
    nightly_build: bool = False,
    rc_build: bool = False,
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
        nightly_build=nightly_build,
        rc_build=rc_build,
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
        "nightly_build": {
            "help": "Developement repository target",
        },
        "rc_build": {
            "help": "Release Candidate repository target",
        },
    },
)
def onedir(
    ctx: Context,
    salt_version: str = None,
    incoming: pathlib.Path = None,
    repo_path: pathlib.Path = None,
    key_id: str = None,
    nightly_build: bool = False,
    rc_build: bool = False,
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
        nightly_build=nightly_build,
        rc_build=rc_build,
        repo_path=repo_path,
        incoming=incoming,
        key_id=key_id,
        distro="onedir",
        pkg_suffixes=(".xz", ".zip"),
    )
    ctx.info("Done")


@publish.command(
    arguments={
        "repo_path": {
            "help": "Local path for the repository that shall be published.",
        },
    }
)
def nightly(ctx: Context, repo_path: pathlib.Path):
    """
    Publish to the nightly bucket.
    """
    _publish_repo(ctx, repo_path=repo_path, nightly_build=True)


@publish.command(
    arguments={
        "repo_path": {
            "help": "Local path for the repository that shall be published.",
        },
        "rc_build": {
            "help": "Release Candidate repository target",
        },
    }
)
def staging(ctx: Context, repo_path: pathlib.Path, rc_build: bool = False):
    """
    Publish to the staging bucket.
    """
    _publish_repo(ctx, repo_path=repo_path, rc_build=rc_build, stage=True)


@publish.command(
    arguments={
        "repo_path": {
            "help": "Local path for the repository that shall be published.",
        },
        "rc_build": {
            "help": "Release Candidate repository target",
        },
    }
)
def release(ctx: Context, repo_path: pathlib.Path, rc_build: bool = False):
    """
    Publish to the release bucket.
    """


def _create_onedir_based_repo(
    ctx: Context,
    salt_version: str,
    nightly_build: bool,
    rc_build: bool,
    repo_path: pathlib.Path,
    incoming: pathlib.Path,
    key_id: str,
    distro: str,
    pkg_suffixes: tuple[str, ...],
):
    ctx.info("Creating repository directory structure ...")
    create_repo_path = _create_repo_path(
        repo_path, salt_version, distro, rc_build=rc_build, nightly_build=nightly_build
    )
    if nightly_build is False:
        repo_json_path = create_repo_path.parent.parent / "repo.json"
    else:
        repo_json_path = create_repo_path.parent / "repo.json"

    if nightly_build:
        bucket_name = tools.utils.NIGHTLY_BUCKET_NAME
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
        release_json[dpath.name] = {
            "name": dpath.name,
            "version": salt_version,
            "os": distro,
            "arch": arch,
        }
        for hash_name in ("blake2b", "sha512", "sha3_512"):
            ctx.info(f"   * Calculating {hash_name} ...")
            hexdigest = _get_file_checksum(fpath, hash_name)
            release_json[dpath.name][hash_name.upper()] = hexdigest
            with open(f"{hashes_base_path}_{hash_name.upper()}", "a+") as wfh:
                wfh.write(f"{hexdigest} {dpath.name}\n")

    for fpath in create_repo_path.iterdir():
        if fpath.suffix in pkg_suffixes:
            continue
        tools.utils.gpg_sign(ctx, key_id, fpath)

    # Export the GPG key in use
    tools.utils.export_gpg_key(ctx, key_id, repo_path, create_repo_path)

    repo_json = _get_repo_json_file_contents(
        ctx, bucket_name=bucket_name, repo_path=repo_path, repo_json_path=repo_json_path
    )
    if nightly_build is False:
        minor_repo_json_path = create_repo_path.parent / "repo.json"
        minor_repo_json = _get_repo_json_file_contents(
            ctx,
            bucket_name=bucket_name,
            repo_path=repo_path,
            repo_json_path=minor_repo_json_path,
        )
        minor_repo_json[salt_version] = release_json
        minor_latest_version = _get_latest_version(*list(minor_repo_json))
        if str(minor_latest_version) not in minor_repo_json:
            minor_latest_version = Version(salt_version)
        minor_repo_json["latest"] = minor_repo_json[str(minor_latest_version)]
        ctx.info(f"Writing {minor_repo_json_path} ...")
        minor_repo_json_path.write_text(json.dumps(minor_repo_json, sort_keys=True))

        if _get_latest_version(*list(repo_json)).major <= Version(salt_version).major:
            repo_json["latest"] = release_json
            ctx.info("Creating '<major-version>' and 'latest' symlinks ...")
            major_version = Version(salt_version).major
            repo_json[str(major_version)] = release_json
            major_link = create_repo_path.parent.parent / str(major_version)
            if major_link.exists():
                major_link.unlink()
            major_link.symlink_to(f"minor/{salt_version}")
            latest_link = create_repo_path.parent.parent / "latest"
            if latest_link.exists():
                latest_link.unlink()
            latest_link.symlink_to(f"minor/{salt_version}")
    else:
        ctx.info("Creating 'latest' symlink ...")
        latest_link = create_repo_path.parent / "latest"
        latest_link.symlink_to(create_repo_path.name)

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
        ctx.info(f"Downloading existing '{repo_json_path.relative_to(repo_path)}' file")
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
    nightly_build: bool = False,
    rc_build: bool = False,
    stage: bool = False,
):
    """
    Publish packaging repositories.
    """
    if nightly_build:
        bucket_name = tools.utils.NIGHTLY_BUCKET_NAME
    elif stage:
        bucket_name = tools.utils.STAGING_BUCKET_NAME
    else:
        bucket_name = tools.utils.RELEASE_BUCKET_NAME

    ctx.info("Preparing upload ...")
    s3 = boto3.client("s3")
    to_delete_paths: dict[pathlib.Path, list[dict[str, str]]] = {}
    to_upload_paths: list[pathlib.Path] = []
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
                )
    except KeyboardInterrupt:
        pass


def _create_repo_path(
    repo_path: pathlib.Path,
    salt_version: str,
    distro: str,
    distro_version: str | None = None,  # pylint: disable=bad-whitespace
    distro_arch: str | None = None,  # pylint: disable=bad-whitespace
    rc_build: bool = False,
    nightly_build: bool = False,
):
    create_repo_path = repo_path
    if nightly_build:
        create_repo_path = create_repo_path / "salt-dev"
    elif nightly_build:
        create_repo_path = create_repo_path / "salt_rc"
    create_repo_path = create_repo_path / "salt" / "py3" / distro
    if distro_version:
        create_repo_path = create_repo_path / distro_version
    if distro_arch:
        create_repo_path = create_repo_path / distro_arch
    if nightly_build is False:
        create_repo_path = create_repo_path / "minor" / salt_version
    else:
        create_repo_path = create_repo_path / datetime.utcnow().strftime("%Y-%m-%d")
    create_repo_path.mkdir(exist_ok=True, parents=True)
    return create_repo_path


def _get_latest_version(*versions: str) -> Version:
    _versions = []
    for version in set(versions):
        if version == "latest":
            continue
        _versions.append(Version(version))
    if _versions:
        _versions.sort(reverse=True)
        return _versions[0]
    return Version("0.0.0")


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
