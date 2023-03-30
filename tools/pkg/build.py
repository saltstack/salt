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

import yaml
from ptscripts import Context, command_group

import tools.utils

log = logging.getLogger(__name__)

# Define the command group
build = command_group(
    name="build",
    help="Package build related commands.",
    description=__doc__,
    parent="pkg",
)


def _get_shared_constants():
    shared_constants = tools.utils.REPO_ROOT / "cicd" / "shared-context.yml"
    return yaml.safe_load(shared_constants.read_text())


@build.command(
    name="deb",
    arguments={
        "onedir": {
            "help": "The path to the onedir artifact",
        },
        "relenv_version": {
            "help": "The version of relenv to use",
        },
        "python_version": {
            "help": "The version of python to build with using relenv",
        },
        "arch": {
            "help": "The arch to build for",
        },
        "package_name": {
            "help": "The name of the relenv environment to create",
        },
    },
)
def debian(
    ctx: Context,
    onedir: str = None,  # pylint: disable=bad-whitespace
    relenv_version: str = None,
    python_version: str = None,
    arch: str = None,
    package_name: str = None,
):
    """
    Build the deb package.
    """
    checkout = pathlib.Path.cwd()
    env_args = ["-e", "SALT_ONEDIR_ARCHIVE"]
    if onedir:
        onedir_artifact = checkout / "artifacts" / onedir
        _check_pkg_build_files_exist(ctx, onedir_artifact=onedir_artifact)
        ctx.info(
            f"Building the package using the onedir artifact {str(onedir_artifact)}"
        )
        os.environ["SALT_ONEDIR_ARCHIVE"] = str(onedir_artifact)
    else:
        if arch is None:
            ctx.error(
                "Building the package from the source files but the arch to build for has not been given"
            )
            ctx.exit(1)
        if package_name is None:
            package_name = "build/onedir/salt"
            ctx.debug(
                f"Building the package in {str(package_name)} since package_name has not been given"
            )
        ctx.info(f"Building the package from the source files")
        shared_constants = _get_shared_constants()
        new_env = {
            "SALT_RELENV_VERSION": relenv_version or shared_constants["relenv_version"],
            "SALT_PYTHON_VERSION": python_version
            or shared_constants["python_version_linux"],
            "SALT_PACKAGE_NAME": str(package_name),
            "SALT_PACKAGE_ARCH": str(arch),
        }
        for key, value in new_env.items():
            os.environ[key] = value
            env_args.extend(["-e", key])

    ctx.run("ln", "-sf", "pkg/debian/", ".")
    ctx.run("debuild", *env_args, "-uc", "-us")

    ctx.info("Done")


@build.command(
    name="rpm",
    arguments={
        "onedir": {
            "help": "The path to the onedir artifact",
        },
        "relenv_version": {
            "help": "The version of relenv to use",
        },
        "python_version": {
            "help": "The version of python to build with using relenv",
        },
        "arch": {
            "help": "The arch to build for",
        },
        "package_name": {
            "help": "The name of the relenv environment to create",
        },
    },
)
def rpm(
    ctx: Context,
    onedir: str = None,  # pylint: disable=bad-whitespace
    relenv_version: str = None,
    python_version: str = None,
    arch: str = None,
    package_name: str = None,
):
    """
    Build the RPM package.
    """
    checkout = pathlib.Path.cwd()
    if onedir:
        onedir_artifact = checkout / "artifacts" / onedir
        _check_pkg_build_files_exist(ctx, onedir_artifact=onedir_artifact)
        ctx.info(
            f"Building the package using the onedir artifact {str(onedir_artifact)}"
        )
        os.environ["SALT_ONEDIR_ARCHIVE"] = str(onedir_artifact)
    else:
        ctx.info(f"Building the package from the source files")
        if arch is None:
            ctx.error(
                "Building the package from the source files but the arch to build for has not been given"
            )
            ctx.exit(1)
        if package_name is None:
            package_name = "build/salt"
            ctx.debug(
                f"Building the package in {str(package_name)} since package_name has not been given"
            )
        ctx.info(f"Building the package from the source files")
        shared_constants = _get_shared_constants()
        new_env = {
            "SALT_RELENV_VERSION": relenv_version or shared_constants["relenv_version"],
            "SALT_PYTHON_VERSION": python_version
            or shared_constants["python_version_linux"],
            "SALT_PACKAGE_NAME": str(package_name),
            "SALT_PACKAGE_ARCH": str(arch),
        }
        for key, value in new_env.items():
            os.environ[key] = value

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
            "choices": ("x86_64", "aarch64", "x86", "amd64"),
            "required": True,
        },
        "python_version": {
            "help": "The version of python to create an environment for using relenv",
            "required": True,
        },
        "package_name": {
            "help": "The name of the relenv environment to be created",
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
        assert platform is not None

    # We import relenv here because it is not a hard requirement for the rest of the tools commands
    try:
        from relenv.create import create
    except ImportError:
        ctx.exit(1, "Relenv not installed in the current environment.")

    dest = pathlib.Path(package_name).resolve()
    create(dest, arch=arch, version=python_version)

    install_args = ["-v"]
    if platform == "windows":
        python_bin = dest / "Scripts" / "python"
    else:
        python_bin = dest / "bin" / "python3"
        install_args.extend(
            [
                "--use-pep517",
                "--no-cache-dir",
                "--no-binary=:all:",
            ]
        )

    version_info = ctx.run(
        str(python_bin),
        "-c",
        "import sys; print('{}.{}'.format(*sys.version_info))",
        capture=True,
    )
    requirements_version = version_info.stdout.strip().decode()
    requirements_file = (
        tools.utils.REPO_ROOT
        / "requirements"
        / "static"
        / "pkg"
        / f"py{requirements_version}"
        / f"{platform}.txt"
    )
    _check_pkg_build_files_exist(ctx, requirements_file=requirements_file)

    ctx.run(str(python_bin), "-m", "pip", "install", "-U", "wheel")
    ctx.run(str(python_bin), "-m", "pip", "install", "-U", "pip>=22.3.1,<23.0")
    ctx.run(str(python_bin), "-m", "pip", "install", "-U", "setuptools>=65.6.3,<66")
    ctx.run(
        str(python_bin),
        "-m",
        "pip",
        "install",
        *install_args,
        "-r",
        str(requirements_file),
    )


@build.command(
    name="salt-onedir",
    arguments={
        "salt_name": {
            "help": "The path to the salt code to install, relative to the repo root",
        },
        "platform": {
            "help": "The platform that installed is being installed on",
            "required": True,
        },
        "package_name": {
            "help": "The name of the relenv environment to install salt into",
            "required": True,
        },
    },
)
def salt_onedir(
    ctx: Context,
    salt_name: str,
    platform: str = None,
    package_name: str = None,
):
    """
    Install salt into a relenv onedir environment.
    """
    if TYPE_CHECKING:
        assert platform is not None
        assert package_name is not None

    salt_archive = pathlib.Path(salt_name).resolve()
    onedir_env = pathlib.Path(package_name).resolve()
    _check_pkg_build_files_exist(ctx, onedir_env=onedir_env, salt_archive=salt_archive)

    os.environ["USE_STATIC_REQUIREMENTS"] = "1"
    if platform == "windows":
        ctx.run(
            "powershell.exe",
            r"pkg\windows\install_salt.cmd",
            "-BuildDir",
            str(onedir_env),
            "-CICD",
            "-SourceTarball",
            str(salt_archive),
        )
        ctx.run(
            "powershell.exe",
            r"pkg\windows\prep_salt.cmd",
            "-BuildDir",
            str(onedir_env),
            "-CICD",
        )
    else:
        os.environ["RELENV_PIP_DIR"] = "1"
        pip_bin = onedir_env / "bin" / "pip3"
        ctx.run(str(pip_bin), "install", str(salt_archive))
        if platform == "darwin":

            def errfn(fn, path, err):
                ctx.info(f"Removing {path} failed: {err}")

            shutil.rmtree(onedir_env / "opt", onerror=errfn)
            shutil.rmtree(onedir_env / "etc", onerror=errfn)
            shutil.rmtree(onedir_env / "Library", onerror=errfn)


def _check_pkg_build_files_exist(ctx: Context, **kwargs):
    for name, path in kwargs.items():
        if not path.exists():
            ctx.error(f"The path {path} does not exist, {name} is not valid... exiting")
            ctx.exit(1)
