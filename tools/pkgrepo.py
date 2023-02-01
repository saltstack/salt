"""
These commands are used to build the pacakge repository files.
"""
# pylint: disable=resource-leakage,broad-except
from __future__ import annotations

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

    salt_archive_keyring_gpg_file = (
        pathlib.Path("~/salt-archive-keyring.gpg").expanduser().resolve()
    )
    if not salt_archive_keyring_gpg_file:
        ctx.error(f"The file '{salt_archive_keyring_gpg_file}' does not exist.")
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
    if nightly_build or rc_build:
        create_repo_path = repo_path / "salt"
    create_repo_path = create_repo_path / "py3" / distro / distro_version / distro_arch
    if nightly_build is False:
        create_repo_path = create_repo_path / "minor" / salt_version
    else:
        create_repo_path = create_repo_path / datetime.utcnow().strftime("%Y-%m-%d")
    create_repo_path.mkdir(exist_ok=True, parents=True)
    ftp_archive_config_file = create_repo_path / "apt-ftparchive.conf"
    ctx.info(f"Writing {ftp_archive_config_file} ...")
    ftp_archive_config_file.write_text(textwrap.dedent(ftp_archive_config))

    ctx.info(f"Copying {salt_archive_keyring_gpg_file} to {create_repo_path} ...")
    shutil.copyfile(
        salt_archive_keyring_gpg_file,
        create_repo_path / salt_archive_keyring_gpg_file.name,
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

    if key_id == "0E08A149DE57BFBE":
        saltstack_gpg_key_file = (
            pathlib.Path("~/SALTSTACK-GPG-KEY.pub").expanduser().resolve()
        )
    else:
        saltstack_gpg_key_file = (
            pathlib.Path("~/SALTSTACK-GPG-KEY2.pub").expanduser().resolve()
        )
    if not saltstack_gpg_key_file.exists():
        ctx.error(f"The file '{saltstack_gpg_key_file}' does not exist.")
        ctx.exit(1)

    ctx.info("Creating repository directory structure ...")
    if nightly_build or rc_build:
        create_repo_path = repo_path / "salt"
    create_repo_path = create_repo_path / "py3" / distro / distro_version / distro_arch
    if nightly_build is False:
        create_repo_path = create_repo_path / "minor" / salt_version
    else:
        create_repo_path = create_repo_path / datetime.utcnow().strftime("%Y-%m-%d")
    create_repo_path.joinpath("SRPMS").mkdir(exist_ok=True, parents=True)

    ctx.info(f"Copying {saltstack_gpg_key_file} to {create_repo_path} ...")
    shutil.copyfile(
        saltstack_gpg_key_file,
        create_repo_path / saltstack_gpg_key_file.name,
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
            ctx.run("rpmsign", "--key-id", key_id, "--addsign", str(dpath))

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
