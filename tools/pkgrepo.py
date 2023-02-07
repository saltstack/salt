"""
These commands are used to build the pacakge repository files.
"""
# pylint: disable=resource-leakage,broad-except
from __future__ import annotations

import hashlib
import json
import logging
import pathlib
import shutil
import textwrap
from datetime import datetime
from typing import TYPE_CHECKING

import packaging.version
from ptscripts import Context, command_group

log = logging.getLogger(__name__)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Define the command group
pkg = command_group(
    name="pkg-repo", help="Packaging Repository Related Commands", description=__doc__
)


@pkg.command(
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

    salt_project_gpg_pub_key_file = (
        pathlib.Path("~/SALT-PROJECT-GPG-PUBKEY-2023.gpg").expanduser().resolve()
    )
    if not salt_project_gpg_pub_key_file:
        ctx.error(f"The file '{salt_project_gpg_pub_key_file}' does not exist.")
        ctx.exit(1)

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
    create_repo_path = repo_path
    if nightly_build or rc_build:
        create_repo_path = create_repo_path / "salt"
    create_repo_path = create_repo_path / "py3" / distro / distro_version / distro_arch
    if nightly_build is False:
        create_repo_path = create_repo_path / "minor" / salt_version
    else:
        create_repo_path = create_repo_path / datetime.utcnow().strftime("%Y-%m-%d")
    create_repo_path.mkdir(exist_ok=True, parents=True)
    ftp_archive_config_file = create_repo_path / "apt-ftparchive.conf"
    ctx.info(f"Writing {ftp_archive_config_file} ...")
    ftp_archive_config_file.write_text(textwrap.dedent(ftp_archive_config))

    ctx.info(f"Copying {salt_project_gpg_pub_key_file} to {create_repo_path} ...")
    shutil.copyfile(
        salt_project_gpg_pub_key_file,
        create_repo_path / salt_project_gpg_pub_key_file.name,
    )

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
        major_version = packaging.version.parse(salt_version).major
        major_link = create_repo_path.parent.parent / str(major_version)
        major_link.symlink_to(f"minor/{salt_version}")
        latest_link = create_repo_path.parent.parent / "latest"
        latest_link.symlink_to(f"minor/{salt_version}")
    else:
        ctx.info("Creating 'latest' symlink ...")
        latest_link = create_repo_path.parent / "latest"
        latest_link.symlink_to(create_repo_path.name)

    ctx.info("Done")


@pkg.command(
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

    salt_project_gpg_pub_key_file = (
        pathlib.Path("~/SALT-PROJECT-GPG-PUBKEY-2023.gpg").expanduser().resolve()
    )

    if not salt_project_gpg_pub_key_file.exists():
        ctx.error(f"The file '{salt_project_gpg_pub_key_file}' does not exist.")
        ctx.exit(1)

    ctx.info("Creating repository directory structure ...")
    create_repo_path = repo_path
    if nightly_build or rc_build:
        create_repo_path = create_repo_path / "salt"
    create_repo_path = create_repo_path / "py3" / distro / distro_version / distro_arch
    if nightly_build is False:
        create_repo_path = create_repo_path / "minor" / salt_version
    else:
        create_repo_path = create_repo_path / datetime.utcnow().strftime("%Y-%m-%d")
    create_repo_path.joinpath("SRPMS").mkdir(exist_ok=True, parents=True)

    ctx.info(f"Copying {salt_project_gpg_pub_key_file} to {create_repo_path} ...")
    shutil.copyfile(
        salt_project_gpg_pub_key_file,
        create_repo_path / salt_project_gpg_pub_key_file.name,
    )

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
        if distro_version == "9":
            gpg_key = f"{base_url}/SALTSTACK-GPG-KEY2.pub"
        else:
            gpg_key = f"{base_url}/SALTSTACK-GPG-KEY.pub"
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
        gpgkey={gpg_key}
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
        major_version = packaging.version.parse(salt_version).major
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


@pkg.command(
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
        os="windows",
        pkg_suffixes=(".msi", ".exe"),
    )
    ctx.info("Done")


@pkg.command(
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
        os="macos",
        pkg_suffixes=(".pkg",),
    )
    ctx.info("Done")


@pkg.command(
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
        os="onedir",
        pkg_suffixes=(".xz", ".zip"),
    )
    ctx.info("Done")


def _create_onedir_based_repo(
    ctx: Context,
    salt_version: str,
    nightly_build: bool,
    rc_build: bool,
    repo_path: pathlib.Path,
    incoming: pathlib.Path,
    key_id: str,
    os: str,
    pkg_suffixes: tuple[str, ...],
):
    salt_project_gpg_pub_key_file = (
        pathlib.Path("~/SALT-PROJECT-GPG-PUBKEY-2023.gpg").expanduser().resolve()
    )
    if not salt_project_gpg_pub_key_file:
        ctx.error(f"The file '{salt_project_gpg_pub_key_file}' does not exist.")
        ctx.exit(1)

    ctx.info("Creating repository directory structure ...")
    create_repo_path = repo_path
    if nightly_build or rc_build:
        create_repo_path = create_repo_path / "salt"
    create_repo_path = create_repo_path / "py3" / os
    repo_json_path = create_repo_path / "repo.json"
    if nightly_build is False:
        create_repo_path = create_repo_path / "minor" / salt_version
    else:
        create_repo_path = create_repo_path / datetime.utcnow().strftime("%Y-%m-%d")
    create_repo_path.mkdir(parents=True, exist_ok=True)

    ctx.info("Downloading any pre-existing 'repo.json' file")
    if nightly_build:
        bucket_name = "salt-project-prod-salt-artifacts-nightly"
    else:
        bucket_name = "salt-project-prod-salt-artifacts-staging"

    bucket_url = (
        f"s3://{bucket_name}/{create_repo_path.relative_to(repo_path)}/repo.json"
    )
    ret = ctx.run("aws", "s3", "cp", bucket_url, create_repo_path, check=False)
    if ret.returncode:
        repo_json = {}
    else:
        repo_json = json.loads(str(repo_json_path))

    if salt_version not in repo_json:
        repo_json[salt_version] = {}

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
        repo_json[salt_version][dpath.name] = {
            "name": dpath.name,
            "version": salt_version,
            "os": os,
            "arch": arch,
        }
        for hash_name in ("blake2b", "sha512", "sha3_512"):
            ctx.info(f"   * Calculating {hash_name} ...")
            hexdigest = _get_file_checksum(fpath, hash_name)
            repo_json[salt_version][dpath.name][hash_name.upper()] = hexdigest
            with open(f"{hashes_base_path}_{hash_name.upper()}", "a+") as wfh:
                wfh.write(f"{hexdigest} {dpath.name}\n")

    for fpath in create_repo_path.iterdir():
        if fpath.suffix in pkg_suffixes:
            continue
        ctx.info(f"GPG Signing '{fpath.relative_to(repo_path)}' ...")
        ctx.run("gpg", "-u", key_id, "-o" f"{fpath}.asc", "-a", "-b", "-s", str(fpath))

    ctx.info(f"Copying {salt_project_gpg_pub_key_file} to {create_repo_path} ...")
    shutil.copyfile(
        salt_project_gpg_pub_key_file,
        create_repo_path / salt_project_gpg_pub_key_file.name,
    )

    if nightly_build is False:
        versions_in_repo_json = {}
        for version in repo_json:
            if version == "latest":
                continue
            versions_in_repo_json[packaging.version.parse(version)] = version
        latest_version = versions_in_repo_json[
            sorted(versions_in_repo_json, reverse=True)[0]
        ]
        if salt_version == latest_version:
            repo_json["latest"] = repo_json[salt_version]
            ctx.info("Creating '<major-version>' and 'latest' symlinks ...")
            major_version = packaging.version.parse(salt_version).major
            repo_json[str(major_version)] = repo_json[salt_version]
            major_link = create_repo_path.parent.parent / str(major_version)
            major_link.symlink_to(f"minor/{salt_version}")
            latest_link = create_repo_path.parent.parent / "latest"
            latest_link.symlink_to(f"minor/{salt_version}")

        ctx.info("Downloading any pre-existing 'minor/repo.json' file")
        minor_repo_json_path = create_repo_path.parent / "repo.json"
        bucket_url = f"s3://{bucket_name}/{minor_repo_json_path.relative_to(repo_path)}"
        ret = ctx.run(
            "aws", "s3", "cp", bucket_url, minor_repo_json_path.parent, check=False
        )
        if ret.returncode:
            minor_repo_json = {}
        else:
            minor_repo_json = json.loads(str(minor_repo_json_path))

        minor_repo_json[salt_version] = repo_json[salt_version]
        minor_repo_json_path.write_text(json.dumps(minor_repo_json))
    else:
        ctx.info("Creating 'latest' symlink ...")
        latest_link = create_repo_path.parent / "latest"
        latest_link.symlink_to(create_repo_path.name)

    repo_json_path.write_text(json.dumps(repo_json))


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
