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
    help="Package build related commands.",
    description=__doc__,
    parent=tools.pkg.pkg,
)


@build.command(
    name="deb",
    arguments={
        "onedir": {
            "help": "The name of the onedir artifact, if given it should be under artifacts/",
        },
        "use_existing_onedir": {
            "help": "Whether to build using the existing onedir or not",
        },
    },
)
def debian(
    ctx: Context,
    onedir: str = None,  # pylint: disable=bad-whitespace
    use_existing_onedir: bool = True,
):
    """
    Build the deb package.
    """
    checkout = pathlib.Path.cwd()
    if use_existing_onedir:
        assert onedir is not None
        onedir_artifact = checkout / "artifacts" / onedir
        _check_pkg_build_files_exist(ctx, onedir_artifact=onedir_artifact)
        ctx.info(
            f"Building the package using the onedir artifact {str(onedir_artifact)}"
        )
        os.environ["SALT_ONEDIR_ARCHIVE"] = str(onedir_artifact)
    else:
        ctx.info(f"Building the package from the source files")

    ctx.run("ln", "-sf", "pkg/debian/", ".")
    ctx.run("debuild", "-e", "SALT_ONEDIR_ARCHIVE", "-uc", "-us")

    ctx.info("Done")


@build.command(
    name="rpm",
    arguments={
        "onedir": {
            "help": "The name of the onedir artifact, if given it should be under artifacts/",
        },
        "use_existing_onedir": {
            "help": "Whether to build using the existing onedir or not",
        },
    },
)
def rpm(
    ctx: Context,
    onedir: str = None,  # pylint: disable=bad-whitespace
    use_existing_onedir: bool = True,
):
    """
    Build the RPM package.
    """
    checkout = pathlib.Path.cwd()
    if use_existing_onedir:
        assert onedir is not None
        onedir_artifact = checkout / "artifacts" / onedir
        _check_pkg_build_files_exist(ctx, onedir_artifact=onedir_artifact)
        ctx.info(
            f"Building the package using the onedir artifact {str(onedir_artifact)}"
        )
        os.environ["SALT_ONEDIR_ARCHIVE"] = str(onedir_artifact)
    else:
        ctx.info(f"Building the package from the source files")

    spec_file = checkout / "pkg" / "rpm" / "salt.spec"
    ctx.run("rpmbuild", "-bb", f"--define=_salt_src {checkout}", str(spec_file))

    ctx.info("Done")


@build.command(
    name="macos",
    arguments={
        "onedir": {
            "help": "The name of the onedir artifact, if given it should be under artifacts/",
            "required": True,
        },
        "salt_version": {
            "help": (
                "The salt version for which to build the repository configuration files. "
                "If not passed, it will be discovered by running 'python3 salt/version.py'."
            ),
            "required": True,
        },
    },
)
def macos(ctx: Context, onedir: str = None, salt_version: str = None):
    """
    Build the macOS package.
    """
    if TYPE_CHECKING:
        assert onedir is not None
        assert salt_version is not None

    checkout = pathlib.Path.cwd()
    onedir_artifact = checkout / "artifacts" / onedir
    _check_pkg_build_files_exist(ctx, onedir_artifact=onedir_artifact)

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
        "onedir": {
            "help": "The name of the onedir artifact, if given it should be under artifacts/",
            "required": True,
        },
        "salt_version": {
            "help": (
                "The salt version for which to build the repository configuration files. "
                "If not passed, it will be discovered by running 'python3 salt/version.py'."
            ),
            "required": True,
        },
        "arch": {
            "help": "The architecture to build the package for",
            "choices": ("x86", "amd64"),
            "required": True,
        },
    },
)
def windows(
    ctx: Context,
    onedir: str = None,
    salt_version: str = None,
    arch: str = None,
):
    """
    Build the Windows package.
    """
    if TYPE_CHECKING:
        assert onedir is not None
        assert salt_version is not None
        assert arch is not None

    checkout = pathlib.Path.cwd()
    onedir_artifact = checkout / "artifacts" / onedir
    _check_pkg_build_files_exist(ctx, onedir_artifact=onedir_artifact)

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


@build.command(
    name="onedir-dependencies",
    arguments={
        "arch": {
            "help": "The architecture to build the package for",
            "choices": ("x86_64", "aarch64"),
            "required": True,
        },
        "python_version": {
            "help": "The version of python to create an environment for using relenv",
            "required": True,
        },
        "package_name": {
            "help": "The name of the relenv environment to be created under artifacts/",
            "required": True,
        },
        "platform": {
            "help": "The platform the relenv environment is being created on",
            "required": True,
        },
    },
)
def onedir_dependencies(
    ctx: Context,
    arch: str = None,
    python_version: str = None,
    package_name: str = None,
    platform: str = None,
):
    """
    Create a relenv environment with the onedir dependencies installed.

    NOTE: relenv needs to be installed into your environment and builds and toolchains (linux) fetched.
    """
    if TYPE_CHECKING:
        assert arch is not None
        assert python_version is not None
        assert package_name is not None

    # We import relenv here because it is not a hard requirement for the rest of the tools commands
    try:
        from relenv.create import create
    except ImportError:
        ctx.exit(1, "Relenv not installed in the current environment.")

    artifacts_dir = pathlib.Path("artifacts").resolve()
    artifacts_dir.mkdir(exist_ok=True)
    dest = artifacts_dir / package_name

    create(dest, arch=arch, version=python_version)

    if platform == "windows":
        python_bin = dest / "Scripts" / "python"
        pip_bin = dest / "Scripts" / "pip"
        no_binary = []
    else:
        python_bin = dest / "bin" / "python3"
        pip_bin = dest / "bin" / "pip3"
        no_binary = ["--no-binary=':all:'"]

    version_info = ctx.run(
        str(python_bin),
        "-c",
        "import sys; print('{}.{}'.format(*sys.version_info))",
        capture=True,
    )
    requirements_version = version_info.stdout.strip().decode()
    requirements_file = pathlib.Path(
        "requirements", "static", "pkg", f"py{requirements_version}", f"{platform}.txt"
    )

    ctx.run(str(pip_bin), "install", "-U", "wheel")
    ctx.run(str(pip_bin), "install", "-U", "pip>=22.3.1,<23.0")
    ctx.run(str(pip_bin), "install", "-U", "setuptools>=65.6.3,<66")
    ctx.run(str(pip_bin), "install", "-r", str(requirements_file), *no_binary)


def _check_pkg_build_files_exist(ctx: Context, **kwargs):
    for name, path in kwargs.items():
        if not path.exists():
            ctx.error(f"The path {path} does not exist, {name} is not valid... exiting")
            ctx.exit(1)
