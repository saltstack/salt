"""
These commands are used to build the salt onedir and system packages.
"""

# pylint: disable=resource-leakage,broad-except
from __future__ import annotations

import json
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
    return yaml.safe_load(tools.utils.SHARED_WORKFLOW_CONTEXT_FILEPATH.read_text())


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
    },
)
def debian(
    ctx: Context,
    onedir: str = None,  # pylint: disable=bad-whitespace
    relenv_version: str = None,
    python_version: str = None,
    arch: str = None,
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
        ctx.info("Building the package from the source files")
        shared_constants = _get_shared_constants()
        if not python_version:
            python_version = shared_constants["python_version"]
        if not relenv_version:
            relenv_version = shared_constants["relenv_version"]
        if TYPE_CHECKING:
            assert python_version
            assert relenv_version
        new_env = {
            "SALT_RELENV_VERSION": relenv_version,
            "SALT_PYTHON_VERSION": python_version,
            "SALT_PACKAGE_ARCH": str(arch),
            "RELENV_FETCH_VERSION": relenv_version,
        }
        for key, value in new_env.items():
            os.environ[key] = value
            env_args.extend(["-e", key])

    env = os.environ.copy()
    env["PIP_CONSTRAINT"] = str(
        tools.utils.REPO_ROOT / "requirements" / "constraints.txt"
    )

    ctx.run("ln", "-sf", "pkg/debian/", ".")
    ctx.run("debuild", *env_args, "-uc", "-us", env=env)

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
    },
)
def rpm(
    ctx: Context,
    onedir: str = None,  # pylint: disable=bad-whitespace
    relenv_version: str = None,
    python_version: str = None,
    arch: str = None,
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
        ctx.info("Building the package from the source files")
        if arch is None:
            ctx.error(
                "Building the package from the source files but the arch to build for has not been given"
            )
            ctx.exit(1)
        ctx.info("Building the package from the source files")
        shared_constants = _get_shared_constants()
        if not python_version:
            python_version = shared_constants["python_version"]
        if not relenv_version:
            relenv_version = shared_constants["relenv_version"]
        if TYPE_CHECKING:
            assert python_version
            assert relenv_version
        new_env = {
            "SALT_RELENV_VERSION": relenv_version,
            "SALT_PYTHON_VERSION": python_version,
            "SALT_PACKAGE_ARCH": str(arch),
            "RELENV_FETCH_VERSION": relenv_version,
        }
        for key, value in new_env.items():
            os.environ[key] = value

    env = os.environ.copy()
    env["PIP_CONSTRAINT"] = str(
        tools.utils.REPO_ROOT / "requirements" / "constraints.txt"
    )
    spec_file = checkout / "pkg" / "rpm" / "salt.spec"
    ctx.run(
        "rpmbuild", "-bb", f"--define=_salt_src {checkout}", str(spec_file), env=env
    )

    ctx.info("Done")


@build.command(
    name="macos",
    arguments={
        "onedir": {
            "help": "The name of the onedir artifact, if given it should be under artifacts/",
        },
        "salt_version": {
            "help": (
                "The salt version for which to build the repository configuration files. "
                "If not passed, it will be discovered by running 'python3 salt/version.py'."
            ),
            "required": True,
        },
        "sign": {
            "help": "Sign and notorize built package",
        },
        "relenv_version": {
            "help": "The version of relenv to use",
        },
        "python_version": {
            "help": "The version of python to build with using relenv",
        },
    },
)
def macos(
    ctx: Context,
    onedir: str = None,
    salt_version: str = None,
    sign: bool = False,
    relenv_version: str = None,
    python_version: str = None,
):
    """
    Build the macOS package.
    """
    if TYPE_CHECKING:
        assert onedir is not None
        assert salt_version is not None

    checkout = pathlib.Path.cwd()
    if onedir:
        onedir_artifact = checkout / "artifacts" / onedir
        ctx.info(f"Building package from existing onedir: {str(onedir_artifact)}")
        _check_pkg_build_files_exist(ctx, onedir_artifact=onedir_artifact)

        build_root = checkout / "pkg" / "macos" / "build" / "opt"
        build_root.mkdir(parents=True, exist_ok=True)
        ctx.info(f"Extracting the onedir artifact to {build_root}")
        with tarfile.open(str(onedir_artifact)) as tarball:
            with ctx.chdir(onedir_artifact.parent):
                tarball.extractall(path=build_root)  # nosec
    else:
        ctx.info("Building package without an existing onedir")

    if not onedir:
        # Prep the salt onedir if not building from an existing one
        shared_constants = _get_shared_constants()
        if not python_version:
            python_version = shared_constants["python_version"]
        if not relenv_version:
            relenv_version = shared_constants["relenv_version"]
        if TYPE_CHECKING:
            assert python_version
            assert relenv_version
        os.environ["RELENV_FETCH_VERSION"] = relenv_version
        with ctx.chdir(checkout / "pkg" / "macos"):
            ctx.info("Fetching relenv python")
            ctx.run(
                "./build_python.sh",
                "--version",
                python_version,
                "--relenv-version",
                relenv_version,
            )

            ctx.info("Installing salt into the relenv python")
            ctx.run("./install_salt.sh")

    if sign:
        ctx.info("Signing binaries")
        with ctx.chdir(checkout / "pkg" / "macos"):
            ctx.run("./sign_binaries.sh")
    ctx.info("Building the macos package")
    with ctx.chdir(checkout / "pkg" / "macos"):
        ctx.run("./prep_salt.sh")
        if sign:
            package_args = ["--sign", salt_version]
        else:
            package_args = [salt_version]
        ctx.run("./package.sh", *package_args)
    if sign:
        ctx.info("Notarizing package")
        ret = ctx.run("uname", "-m", capture=True)
        cpu_arch = ret.stdout.strip().decode()
        with ctx.chdir(checkout / "pkg" / "macos"):
            ctx.run("./notarize.sh", f"salt-{salt_version}-py3-{cpu_arch}.pkg")

    ctx.info("Done")


@build.command(
    name="windows",
    arguments={
        "onedir": {
            "help": "The name of the onedir artifact, if given it should be under artifacts/",
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
        "sign": {
            "help": "Sign and notarize built package",
        },
        "relenv_version": {
            "help": "The version of relenv to use",
        },
        "python_version": {
            "help": "The version of python to build with using relenv",
        },
    },
)
def windows(
    ctx: Context,
    onedir: str = None,
    salt_version: str = None,
    arch: str = None,
    sign: bool = False,
    relenv_version: str = None,
    python_version: str = None,
):
    """
    Build the Windows package.
    """
    if TYPE_CHECKING:
        assert salt_version is not None
        assert arch is not None

    shared_constants = _get_shared_constants()
    if not python_version:
        python_version = shared_constants["python_version"]
    if not relenv_version:
        relenv_version = shared_constants["relenv_version"]
    if TYPE_CHECKING:
        assert python_version
        assert relenv_version
    os.environ["RELENV_FETCH_VERSION"] = relenv_version

    build_cmd = [
        "powershell.exe",
        "&",
        "pkg/windows/build.cmd",
        "-Architecture",
        arch,
        "-Version",
        salt_version,
        "-PythonVersion",
        python_version,
        "-RelenvVersion",
        relenv_version,
        "-CICD",
    ]

    checkout = pathlib.Path.cwd()
    if onedir:
        build_cmd.append("-SkipInstall")
        onedir_artifact = checkout / "artifacts" / onedir
        ctx.info(f"Building package from existing onedir: {str(onedir_artifact)}")
        _check_pkg_build_files_exist(ctx, onedir_artifact=onedir_artifact)

        unzip_dir = checkout / "pkg" / "windows"
        ctx.info(f"Unzipping the onedir artifact to {unzip_dir}")
        with zipfile.ZipFile(onedir_artifact, mode="r") as archive:
            archive.extractall(unzip_dir)  # nosec

        move_dir = unzip_dir / "salt"
        build_env = unzip_dir / "buildenv"
        _check_pkg_build_files_exist(ctx, move_dir=move_dir)

        ctx.info(f"Moving {move_dir} directory to the build environment in {build_env}")
        shutil.move(move_dir, build_env)
    else:
        build_cmd.append("-Build")
        ctx.info("Building package without an existing onedir")

    ctx.info(f"Running: {' '.join(build_cmd)} ...")
    ctx.run(*build_cmd)

    if sign:
        env = os.environ.copy()
        envpath = env.get("PATH")
        if envpath is None:
            path_parts = []
        else:
            path_parts = envpath.split(os.pathsep)
        path_parts.extend(
            [
                r"C:\Program Files (x86)\Windows Kits\10\App Certification Kit",
                r"C:\Program Files (x86)\Microsoft SDKs\Windows\v10.0A\bin\NETFX 4.8 Tools",
                r"C:\Program Files\DigiCert\DigiCert One Signing Manager Tools",
            ]
        )
        env["PATH"] = os.pathsep.join(path_parts)
        command = ["smksp_registrar.exe", "list"]
        ctx.info(f"Running: '{' '.join(command)}' ...")
        ctx.run(*command, env=env)
        command = ["smctl.exe", "keypair", "ls"]
        ctx.info(f"Running: '{' '.join(command)}' ...")
        ret = ctx.run(*command, env=env, check=False)
        if ret.returncode:
            ctx.error(f"Failed to run '{' '.join(command)}'")
        command = [
            r"C:\Windows\System32\certutil.exe",
            "-csp",
            "DigiCert Signing Manager KSP",
            "-key",
            "-user",
        ]
        ctx.info(f"Running: '{' '.join(command)}' ...")
        ret = ctx.run(*command, env=env, check=False)
        if ret.returncode:
            ctx.error(f"Failed to run '{' '.join(command)}'")

        command = ["smksp_cert_sync.exe"]
        ctx.info(f"Running: '{' '.join(command)}' ...")
        ret = ctx.run(*command, env=env, check=False)
        if ret.returncode:
            ctx.error(f"Failed to run '{' '.join(command)}'")

        for fname in (
            f"pkg/windows/build/Salt-Minion-{salt_version}-Py3-{arch}-Setup.exe",
            f"pkg/windows/build/Salt-Minion-{salt_version}-Py3-{arch}.msi",
        ):
            fpath = str(pathlib.Path(fname).resolve())
            ctx.info(f"Signing {fname} ...")
            ctx.run(
                "signtool.exe",
                "sign",
                "/sha1",
                os.environ["WIN_SIGN_CERT_SHA1_HASH"],
                "/tr",
                "http://timestamp.digicert.com",
                "/td",
                "SHA256",
                "/fd",
                "SHA256",
                fpath,
                env=env,
            )
            ctx.info(f"Verifying {fname} ...")
            ctx.run("signtool.exe", "verify", "/v", "/pa", fpath, env=env)

    ctx.info("Done")


@build.command(
    name="onedir-dependencies",
    arguments={
        "arch": {
            "help": "The architecture to build the package for",
            "choices": ("x86_64", "arm64", "x86", "amd64"),
            "required": True,
        },
        "python_version": {
            "help": "The version of python to create an environment for using relenv",
            "required": True,
        },
        "relenv_version": {
            "help": "The version of relenv to use",
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
    relenv_version: str = None,
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

    if platform == "darwin":
        platform = "macos"

    if platform != "macos" and arch == "arm64":
        arch = "aarch64"

    shared_constants = _get_shared_constants()
    if not python_version:
        python_version = shared_constants["python_version"]
    if not relenv_version:
        relenv_version = shared_constants["relenv_version"]
    if TYPE_CHECKING:
        assert python_version
        assert relenv_version
    os.environ["RELENV_FETCH_VERSION"] = relenv_version

    # We import relenv here because it is not a hard requirement for the rest of the tools commands
    try:
        import relenv.create
    except ImportError:
        ctx.exit(1, "Relenv not installed in the current environment.")

    dest = pathlib.Path(package_name).resolve()
    relenv.create.create(dest, arch=arch, version=python_version)

    # Validate that we're using the relenv version we really want to
    if platform == "windows":
        env_scripts_dir = dest / "Scripts"
    else:
        env_scripts_dir = dest / "bin"

    ret = ctx.run(
        str(env_scripts_dir / "relenv"), "--version", capture=True, check=False
    )
    if ret.returncode:
        ctx.error(f"Failed to get the relenv version: {ret}")
        ctx.exit(1)

    env_relenv_version = ret.stdout.strip().decode()
    if env_relenv_version != relenv_version:
        ctx.error(
            f"The onedir installed relenv version({env_relenv_version}) is not "
            f"the relenv version which should be used({relenv_version})."
        )
        ctx.exit(1)

    ctx.info(
        f"The relenv version installed in the onedir env({env_relenv_version}) "
        f"matches the version which must be used."
    )

    env = os.environ.copy()
    install_args = ["-v"]
    if platform == "windows":
        python_bin = env_scripts_dir / "python"
    else:
        env["RELENV_BUILDENV"] = "1"
        python_bin = env_scripts_dir / "python3"
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
        / f"{platform if platform != 'macos' else 'darwin'}.txt"
    )
    _check_pkg_build_files_exist(ctx, requirements_file=requirements_file)

    env["PIP_CONSTRAINT"] = str(
        tools.utils.REPO_ROOT / "requirements" / "constraints.txt"
    )
    ctx.run(
        str(python_bin),
        "-m",
        "pip",
        "install",
        "-U",
        "setuptools",
        "pip",
        "wheel",
        env=env,
    )
    ctx.run(
        str(python_bin),
        "-m",
        "pip",
        "install",
        *install_args,
        "-r",
        str(requirements_file),
        env=env,
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
        "relenv_version": {
            "help": "The version of relenv to use",
        },
    },
)
def salt_onedir(
    ctx: Context,
    salt_name: str,
    platform: str = None,
    package_name: str = None,
    relenv_version: str = None,
):
    """
    Install salt into a relenv onedir environment.
    """
    if TYPE_CHECKING:
        assert platform is not None
        assert package_name is not None

    if platform == "darwin":
        platform = "macos"

    shared_constants = _get_shared_constants()
    if not relenv_version:
        relenv_version = shared_constants["relenv_version"]
    if TYPE_CHECKING:
        assert relenv_version
    os.environ["RELENV_FETCH_VERSION"] = relenv_version

    salt_archive = pathlib.Path(salt_name).resolve()
    onedir_env = pathlib.Path(package_name).resolve()
    _check_pkg_build_files_exist(ctx, onedir_env=onedir_env, salt_archive=salt_archive)

    # Validate that we're using the relenv version we really want to
    if platform == "windows":
        env_scripts_dir = onedir_env / "Scripts"
    else:
        env_scripts_dir = onedir_env / "bin"

    ret = ctx.run(
        str(env_scripts_dir / "relenv"), "--version", capture=True, check=False
    )
    if ret.returncode:
        ctx.error(f"Failed to get the relenv version: {ret}")
        ctx.exit(1)

    env_relenv_version = ret.stdout.strip().decode()
    if env_relenv_version != relenv_version:
        ctx.error(
            f"The onedir installed relenv version({env_relenv_version}) is not "
            f"the relenv version which should be used({relenv_version})."
        )
        ctx.exit(1)

    ctx.info(
        f"The relenv version installed in the onedir env({env_relenv_version}) "
        f"matches the version which must be used."
    )

    env = os.environ.copy()
    env["USE_STATIC_REQUIREMENTS"] = "1"
    env["RELENV_BUILDENV"] = "1"
    if platform == "windows":
        ctx.run(
            "powershell.exe",
            r"pkg\windows\install_salt.cmd",
            "-BuildDir",
            str(onedir_env),
            "-CICD",
            "-SourceTarball",
            str(salt_archive),
            env=env,
        )
        ctx.run(
            "powershell.exe",
            r"pkg\windows\prep_salt.cmd",
            "-BuildDir",
            str(onedir_env),
            "-CICD",
            env=env,
        )
        python_executable = str(env_scripts_dir / "python.exe")
        ret = ctx.run(
            python_executable,
            "-c",
            "import json, sys, site, pathlib; sys.stdout.write(json.dumps([pathlib.Path(p).as_posix() for p in site.getsitepackages()]))",
            capture=True,
        )
        if ret.returncode:
            ctx.error(f"Failed to get the path to `site-packages`: {ret}")
            ctx.exit(1)
        site_packages_json = json.loads(ret.stdout.strip().decode())
        ctx.info(f"Discovered 'site-packages' paths: {site_packages_json}")
    else:
        env["RELENV_PIP_DIR"] = "1"
        pip_bin = env_scripts_dir / "pip3"
        ctx.run(
            str(pip_bin),
            "install",
            "--no-warn-script-location",
            str(salt_archive),
            env=env,
        )
        if platform == "macos":

            def errfn(fn, path, err):
                ctx.info(f"Removing {path} failed: {err}")

            for subdir in ("opt", "etc", "Library"):
                path = onedir_env / subdir
                if path.exists():
                    shutil.rmtree(path, onerror=errfn)

        python_executable = str(env_scripts_dir / "python3")
        ret = ctx.run(
            python_executable,
            "-c",
            "import json, sys, site, pathlib; sys.stdout.write(json.dumps(site.getsitepackages()))",
            capture=True,
        )
        if ret.returncode:
            ctx.error(f"Failed to get the path to `site-packages`: {ret}")
            ctx.exit(1)
        site_packages_json = json.loads(ret.stdout.strip().decode())
        ctx.info(f"Discovered 'site-packages' paths: {site_packages_json}")

    site_packages: str
    for site_packages_path in site_packages_json:
        if "site-packages" in site_packages_path:
            site_packages = site_packages_path
            break
    else:
        ctx.error("Cloud not find a site-packages path with 'site-packages' in it?!")
        ctx.exit(1)

    ret = ctx.run(
        str(python_executable),
        "-c",
        "import sys; print('{}.{}'.format(*sys.version_info))",
        capture=True,
    )
    python_version_info = ret.stdout.strip().decode()
    extras_dir = onedir_env / f"extras-{python_version_info}"
    ctx.info(f"Creating Salt's extras path: {extras_dir}")
    extras_dir.mkdir(exist_ok=True)

    for fname in ("_salt_onedir_extras.py", "_salt_onedir_extras.pth"):
        src = tools.utils.REPO_ROOT / "pkg" / "common" / "onedir" / fname
        dst = pathlib.Path(site_packages) / fname
        ctx.info(f"Copying '{src.relative_to(tools.utils.REPO_ROOT)}' to '{dst}' ...")
        shutil.copyfile(src, dst)

    # Add package type file for package grain
    with open(
        pathlib.Path(site_packages) / "salt" / "_pkg.txt", "w", encoding="utf-8"
    ) as fp:
        fp.write("onedir")


def _check_pkg_build_files_exist(ctx: Context, **kwargs):
    for name, path in kwargs.items():
        if not path.exists():
            ctx.error(f"The path {path} does not exist, {name} is not valid... exiting")
            ctx.exit(1)
