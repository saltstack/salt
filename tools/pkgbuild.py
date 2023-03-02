"""
These commands are used to build the salt onedir and system packages.
"""
# pylint: disable=resource-leakage,broad-except
from __future__ import annotations

import logging
import os
import pathlib
import shutil
import tarfile
import zipfile
from typing import TYPE_CHECKING

from ptscripts import Context, command_group

import tools.pkg
import tools.utils

log = logging.getLogger(__name__)

# Define the command group
build = command_group(
    name="build",
    help="Packaging Repository Related Commands",
    description=__doc__,
    parent=tools.pkg.pkg,
)


@build.command(
    name="deb",
    arguments={
        "salt_version": {
            "help": (
                "The salt version for which to build the repository configuration files. "
                "If not passed, it will be discovered by running 'python3 salt/version.py'."
            ),
            "required": True,
        },
        "arch": {
            "help": "The architecture to build the package for",
            "choices": ("x86_64", "aarch64"),
            "required": True,
        },
        "checkout_root": {
            "help": "The root of the salt checkout",
            "required": True,
        },
        "use_existing_onedir": {
            "help": "Overwrite 'salt/_version.txt' if it already exists",
        },
    },
)
def debian(
    ctx: Context,
    salt_version: str = None,
    arch: str = None,
    checkout_root: str = None,
    use_existing_onedir: bool = True,
):
    """
    Build the deb package.
    """
    if TYPE_CHECKING:
        assert salt_version is not None
        assert arch is not None
        assert checkout_root is not None

    checkout = pathlib.Path(checkout_root)
    onedir_artifact = (
        checkout / "artifacts" / f"salt-{salt_version}-onedir-linux-{arch}.tar.xz"
    )
    patch = checkout / f"salt-{salt_version }.patch"
    kwargs = {} if not use_existing_onedir else {"onedir_artifact": onedir_artifact}
    _check_pkg_build_files_exist(ctx, checkout=checkout, patch=patch, **kwargs)

    _configure_git(ctx, checkout)
    with ctx.chdir(checkout):
        _apply_release_patch(ctx, patch)
        _set_onedir_location_in_environment(ctx, onedir_artifact, use_existing_onedir)

        ctx.run("ln", "-sf", "pkg/debian/", ".")
        ctx.run("debuild", "-e", "SALT_ONEDIR_ARCHIVE", "-uc", "-us")

    ctx.info("Done")


@build.command(
    name="rpm",
    arguments={
        "salt_version": {
            "help": (
                "The salt version for which to build the repository configuration files. "
                "If not passed, it will be discovered by running 'python3 salt/version.py'."
            ),
            "required": True,
        },
        "arch": {
            "help": "The architecture to build the package for",
            "choices": ("x86_64", "aarch64"),
            "required": True,
        },
        "checkout_root": {
            "help": "The root of the salt checkout",
            "required": True,
        },
        "use_existing_onedir": {
            "help": "Overwrite 'salt/_version.txt' if it already exists",
        },
    },
)
def rpm(
    ctx: Context,
    salt_version: str = None,
    arch: str = None,
    checkout_root: str = None,
    use_existing_onedir: bool = True,
):
    """
    Build the RPM package.
    """
    if TYPE_CHECKING:
        assert salt_version is not None
        assert arch is not None
        assert checkout_root is not None

    checkout = pathlib.Path(checkout_root)
    onedir_artifact = (
        checkout / "artifacts" / f"salt-{salt_version}-onedir-linux-{arch}.tar.xz"
    )
    patch = checkout / f"salt-{salt_version }.patch"
    kwargs = {} if not use_existing_onedir else {"onedir_artifact": onedir_artifact}
    _check_pkg_build_files_exist(ctx, checkout=checkout, patch=patch, **kwargs)

    _configure_git(ctx, checkout)
    with ctx.chdir(checkout):
        _apply_release_patch(ctx, patch)
        _set_onedir_location_in_environment(ctx, onedir_artifact, use_existing_onedir)

        spec_file = checkout / "pkg" / "rpm" / "salt.spec"
        ctx.run("rpmbuild", "-bb", f"--define=_salt_src {checkout}", str(spec_file))

    ctx.info("Done")


@build.command(
    name="macos",
    arguments={
        "salt_version": {
            "help": (
                "The salt version for which to build the repository configuration files. "
                "If not passed, it will be discovered by running 'python3 salt/version.py'."
            ),
            "required": True,
        },
        "arch": {
            "help": "The architecture to build the package for",
            "choices": ("x86_64", "aarch64"),
            "required": True,
        },
        "checkout_root": {
            "help": "The root of the salt checkout",
            "required": True,
        },
    },
)
def macos(
    ctx: Context,
    salt_version: str = None,
    arch: str = None,
    checkout_root: str = None,
):
    """
    Build the macOS package.
    """
    if TYPE_CHECKING:
        assert salt_version is not None
        assert arch is not None
        assert checkout_root is not None

    checkout = pathlib.Path(checkout_root)
    onedir_artifact = (
        checkout / "artifacts" / f"salt-{salt_version}-onedir-darwin-{arch}.tar.xz"
    )
    _check_pkg_build_files_exist(
        ctx, checkout=checkout, onedir_artifact=onedir_artifact
    )

    build_root = checkout / "pkg" / "macos" / "build" / "opt"
    build_root.mkdir(parents=True, exist_ok=True)
    ctx.info(f"Extracting the onedir artifact to {build_root}")
    with tarfile.open(str(onedir_artifact)) as tarball:
        with ctx.chdir(onedir_artifact.parent):
            tarball.extractall(path=build_root)

    ctx.info("Building the macos package")
    with ctx.chdir(checkout / "pkg" / "macos"):
        ctx.run("./prep_salt.sh")
        ctx.run("sudo", "./package.sh", "-n", salt_version)

    ctx.info("Done")


@build.command(
    name="windows",
    arguments={
        "salt_version": {
            "help": (
                "The salt version for which to build the repository configuration files. "
                "If not passed, it will be discovered by running 'python3 salt/version.py'."
            ),
            "required": True,
        },
        "arch": {
            "help": "The architecture to build the package for",
            "choices": ("x86_64", "aarch64"),
            "required": True,
        },
        "checkout_root": {
            "help": "The root of the salt checkout",
            "required": True,
        },
    },
)
def windows(
    ctx: Context,
    salt_version: str = None,
    arch: str = None,
    checkout_root: str = None,
):
    """
    Build the Windows package.
    """
    if TYPE_CHECKING:
        assert salt_version is not None
        assert arch is not None
        assert checkout_root is not None

    checkout = pathlib.Path(checkout_root)
    onedir_artifact = (
        checkout / "artifacts" / f"salt-{salt_version}-onedir-windows-{arch}.zip"
    )
    _check_pkg_build_files_exist(
        ctx, checkout=checkout, onedir_artifact=onedir_artifact
    )

    unzip_dir = checkout / "pkg" / "windows"
    ctx.info(f"Unzipping the onedir artifact to {unzip_dir}")
    with zipfile.ZipFile(onedir_artifact, mode="r") as archive:
        archive.extractall(unzip_dir)

    move_dir = unzip_dir / "salt"
    build_env = unzip_dir / "buildenv"
    _check_pkg_build_files_exist(ctx, move_dir=move_dir)

    ctx.info(f"Moving {move_dir} directory to the build environment in {build_env}")
    shutil.move(move_dir, build_env)

    ctx.info("Building the windows package")
    ctx.run(
        "powershell.exe",
        "&",
        "pkg/windows/build.cmd",
        "-Architecture",
        arch,
        "-Version",
        salt_version,
        "-CICD",
        "-SkipInstall",
    )

    ctx.info("Done")


def _check_pkg_build_files_exist(ctx: Context, **kwargs):
    for name, path in kwargs.items():
        if not path.exists():
            ctx.error(f"The path {path} does not exist, {name} is not valid... exiting")
            ctx.exit(1)


def _set_onedir_location_in_environment(
    ctx: Context, onedir_artifact: pathlib.Path, use_existing_onedir: bool
):
    if use_existing_onedir:
        ctx.info(
            f"Building the package using the onedir artifact {str(onedir_artifact)}"
        )
        os.environ["SALT_ONEDIR_ARCHIVE"] = str(onedir_artifact)
    else:
        ctx.info(f"Building the package from the source files")


def _apply_release_patch(ctx: Context, patch: pathlib.Path):
    ctx.info("Applying the release patch")
    ctx.run("git", "am", "--committer-date-is-author-date", patch.name)
    patch.unlink()


def _configure_git(ctx: Context, checkout: pathlib.Path):
    ctx.info("Setting name and email in git global config")
    ctx.run("git", "config", "--global", "user.name", "'Salt Project Packaging'")
    ctx.run(
        "git", "config", "--global", "user.email", "saltproject-packaging@vmware.com"
    )
    ctx.run("git", "config", "--global", "--add", "safe.directory", str(checkout))
