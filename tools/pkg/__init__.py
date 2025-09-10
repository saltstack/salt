"""
These commands are used to build Salt packages.
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import fnmatch
import gzip
import hashlib
import json
import logging
import os
import pathlib
import shutil
import sys
import tarfile
import tempfile

import yaml
from ptscripts import Context, command_group
from ptscripts.models import VirtualEnvPipConfig

import tools.utils

log = logging.getLogger(__name__)

# Define the command group
pkg = command_group(name="pkg", help="Packaging Related Commands", description=__doc__)


class Recompress:
    """
    Helper class to re-compress a ``.tag.gz`` file to make it reproducible.
    """

    def __init__(self, mtime):
        self.mtime = int(mtime)

    def tar_reset(self, tarinfo):
        """
        Reset user, group, mtime, and mode to create reproducible tar.
        """
        tarinfo.uid = tarinfo.gid = 0
        tarinfo.uname = tarinfo.gname = "root"
        tarinfo.mtime = self.mtime
        if tarinfo.type == tarfile.DIRTYPE:
            tarinfo.mode = 0o755
        else:
            tarinfo.mode = 0o644
        if tarinfo.pax_headers:
            raise ValueError(tarinfo.name, tarinfo.pax_headers)
        return tarinfo

    def recompress(self, targz):
        """
        Re-compress the passed path.
        """
        tempd = pathlib.Path(tempfile.mkdtemp()).resolve()
        d_src = tempd.joinpath("src")
        d_src.mkdir()
        d_tar = tempd.joinpath(targz.stem)
        d_targz = tempd.joinpath(targz.name)
        with tarfile.open(d_tar, "w|") as wfile:
            with tarfile.open(targz, "r:gz") as rfile:
                rfile.extractall(d_src)  # nosec
                extracted_dir = next(pathlib.Path(d_src).iterdir())
                for name in sorted(extracted_dir.rglob("*")):
                    wfile.add(
                        str(name),
                        filter=self.tar_reset,
                        recursive=False,
                        arcname=str(name.relative_to(d_src)),
                    )

        with open(d_tar, "rb") as rfh:
            with gzip.GzipFile(
                fileobj=open(d_targz, "wb"), mode="wb", filename="", mtime=self.mtime
            ) as gz:  # pylint: disable=invalid-name
                while True:
                    chunk = rfh.read(1024)
                    if not chunk:
                        break
                    gz.write(chunk)
        targz.unlink()
        shutil.move(str(d_targz), str(targz))


@pkg.command(
    name="set-salt-version",
    arguments={
        "salt_version": {
            "help": (
                "The salt version to write to 'salt/_version.txt'. If not passed "
                "it will be discovered by running 'python3 salt/version.py'."
            ),
            "nargs": "?",
            "default": None,
        },
        "overwrite": {
            "help": "Overwrite 'salt/_version.txt' if it already exists",
        },
        "validate_version": {
            "help": "Validate, and normalize, the passed Salt Version",
        },
        "release": {
            "help": "When true, also update salt/versions.py to set the version as released",
        },
    },
)
def set_salt_version(
    ctx: Context,
    salt_version: str,
    overwrite: bool = False,
    validate_version: bool = False,
    release: bool = False,
):
    """
    Write the Salt version to 'salt/_version.txt'
    """
    salt_version_file = tools.utils.REPO_ROOT / "salt" / "_version.txt"
    if salt_version_file.exists():
        if not overwrite:
            ctx.error("The 'salt/_version.txt' file already exists")
            ctx.exit(1)
        salt_version_file.unlink()
    if salt_version is None:
        if not tools.utils.REPO_ROOT.joinpath(".git").exists():
            ctx.error(
                "Apparently not running from a Salt repository checkout. "
                "Unable to discover the Salt version."
            )
            ctx.exit(1)
            ctx.info("Discovering the Salt version...")
        ret = ctx.run(shutil.which("python3"), "salt/version.py", capture=True)
        salt_version = ret.stdout.strip().decode()
        ctx.info(f"Discovered Salt version: {salt_version!r}")
    elif validate_version:
        ctx.info(f"Validating and normalizing the salt version {salt_version!r}...")
        with ctx.virtualenv(
            name="set-salt-version",
            config=VirtualEnvPipConfig(
                requirements_files=[
                    tools.utils.REPO_ROOT / "requirements" / "base.txt",
                ]
            ),
        ) as venv:
            code = f"""
            import sys
            import salt.version
            parsed_version = salt.version.SaltStackVersion.parse("{salt_version}")
            if parsed_version.name is None:
                # When we run out of names, or we stop supporting version names
                # we'll need to remove this version check.
                print("'{{}}' is not a valid Salt Version.".format(parsed_version), file=sys.stderr, flush=True)
                sys.exit(1)
            sys.stdout.write(str(parsed_version))
            sys.stdout.flush()
            """
            ret = venv.run_code(code, capture=True, check=False)
            if ret.returncode:
                ctx.error(ret.stderr.decode())
                ctx.exit(ret.returncode)
            salt_version = ret.stdout.strip().decode()

    if not tools.utils.REPO_ROOT.joinpath("salt").is_dir():
        ctx.error(
            "The path 'salt/' is not a directory. Unable to write 'salt/_version.txt'"
        )
        ctx.exit(1)

    try:
        tools.utils.REPO_ROOT.joinpath("salt/_version.txt").write_text(
            salt_version, encoding="utf-8"
        )
    except Exception as exc:
        ctx.error(f"Unable to write 'salt/_version.txt': {exc}")
        ctx.exit(1)

    ctx.info(f"Successfuly wrote {salt_version!r} to 'salt/_version.txt'")

    version_instance = tools.utils.Version(salt_version)
    if release and not version_instance.is_prerelease:
        with open(
            tools.utils.REPO_ROOT / "salt" / "version.py", "r+", encoding="utf-8"
        ) as rwfh:
            contents = rwfh.read()
            match = f"info=({version_instance.major}, {version_instance.minor}))"
            if match in contents:
                contents = contents.replace(
                    match,
                    f"info=({version_instance.major}, {version_instance.minor}),  released=True)",
                )
                rwfh.seek(0)
                rwfh.write(contents)
                rwfh.truncate()

                ctx.info(
                    f"Successfuly marked {salt_version!r} as released in 'salt/version.py'"
                )

    gh_env_file = os.environ.get("GITHUB_ENV", None)
    if gh_env_file is not None:
        variable_text = f"SALT_VERSION={salt_version}"
        ctx.info(f"Writing '{variable_text}' to '$GITHUB_ENV' file:", gh_env_file)
        with open(gh_env_file, "w", encoding="utf-8") as wfh:
            wfh.write(f"{variable_text}\n")

    gh_output_file = os.environ.get("GITHUB_OUTPUT", None)
    if gh_output_file is not None:
        variable_text = f"salt-version={salt_version}"
        ctx.info(f"Writing '{variable_text}' to '$GITHUB_OUTPUT' file:", gh_output_file)
        with open(gh_output_file, "w", encoding="utf-8") as wfh:
            wfh.write(f"{variable_text}\n")

    ctx.exit(0)


@pkg.command(
    name="pre-archive-cleanup",
    arguments={
        "cleanup_path": {
            "help": (
                "The salt version to write to 'salt/_version.txt'. If not passed "
                "it will be discovered by running 'python3 salt/version.py'."
            ),
            "metavar": "PATH_TO_CLEANUP",
        },
        "pkg": {
            "help": "Perform extended, pre-packaging cleanup routines",
        },
    },
)
def pre_archive_cleanup(ctx: Context, cleanup_path: str, pkg: bool = False):
    """
    Clean the provided path of paths that should not be included in the archive.

    For example:

        * `__pycache__` directories
        * `*.pyc` files
        * `*.pyo` files

    When running on Windows and macOS, some additional cleanup is also done.
    """
    with open(
        str(tools.utils.REPO_ROOT / "pkg" / "common" / "env-cleanup-rules.yml"),
        encoding="utf-8",
    ) as rfh:
        patterns = yaml.safe_load(rfh.read())

    if pkg:
        patterns = patterns["pkg"]
    else:
        patterns = patterns["ci"]

    if sys.platform.lower().startswith("win"):
        patterns = patterns["windows"]
    elif sys.platform.lower().startswith("darwin"):
        patterns = patterns["darwin"]
    else:
        patterns = patterns["linux"]

    def unnest_lists(patterns):
        if isinstance(patterns, list):
            for pattern in patterns:
                yield from unnest_lists(pattern)
        else:
            yield patterns

    exclude_patterns = set()
    for pattern in unnest_lists(patterns["exclude_patterns"]):
        exclude_patterns.add(pattern)

    dir_patterns = set()
    for pattern in unnest_lists(patterns["dir_patterns"]):
        dir_patterns.add(pattern)

    file_patterns = set()
    for pattern in unnest_lists(patterns["file_patterns"]):
        file_patterns.add(pattern)

    for root, dirs, files in os.walk(cleanup_path, topdown=True, followlinks=False):
        for dirname in dirs:
            path = pathlib.Path(root, dirname).resolve()
            if not path.exists():
                continue
            match_path = path.as_posix()
            skip_match = False
            for pattern in exclude_patterns:
                if fnmatch.fnmatch(str(match_path), pattern):
                    ctx.info(
                        f"Excluded file: {match_path}; Matching pattern: {pattern!r}"
                    )
                    skip_match = True
                    break
            if skip_match:
                continue
            for pattern in dir_patterns:
                if fnmatch.fnmatch(str(match_path), pattern):
                    ctx.info(
                        f"Deleting directory: {match_path}; Matching pattern: {pattern!r}"
                    )
                    shutil.rmtree(str(path))
                    break
        for filename in files:
            path = pathlib.Path(root, filename).resolve()
            if not path.exists():
                continue
            match_path = path.as_posix()
            skip_match = False
            for pattern in exclude_patterns:
                if fnmatch.fnmatch(str(match_path), pattern):
                    ctx.info(
                        f"Excluded file: {match_path}; Matching pattern: {pattern!r}"
                    )
                    skip_match = True
                    break
            if skip_match:
                continue
            for pattern in file_patterns:
                if fnmatch.fnmatch(str(match_path), pattern):
                    ctx.info(
                        f"Deleting file: {match_path}; Matching pattern: {pattern!r}"
                    )
                    try:
                        os.remove(str(path))
                    except FileNotFoundError:
                        pass
                    break


@pkg.command(
    name="generate-hashes",
    arguments={
        "files": {
            "help": "The files to generate the hashes for.",
            "nargs": "*",
        },
    },
)
def generate_hashes(ctx: Context, files: list[pathlib.Path]):
    """
    Generate "blake2b", "sha512" and "sha3_512" hashes for the passed files.
    """
    for fpath in files:
        ctx.info(f"* Processing {fpath} ...")
        hashes = {}
        for hash_name in ("blake2b", "sha512", "sha3_512"):
            ctx.info(f"   * Calculating {hash_name} ...")
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
            digest_file_path = fpath.parent / f"{fpath.name}.{hash_name.upper()}"
            hexdigest = digest.hexdigest()
            ctx.info(f"   * Writing {digest_file_path} ...")
            digest_file_path.write_text(digest.hexdigest())
            hashes[hash_name] = hexdigest
        hashes_json_path = fpath.parent / f"{fpath.name}.json"
        ctx.info(f"   * Writing {hashes_json_path} ...")
        hashes_json_path.write_text(json.dumps(hashes))
    ctx.info("Done")


@pkg.command(
    name="source-tarball",
    venv_config=VirtualEnvPipConfig(
        requirements_files=[
            tools.utils.REPO_ROOT / "requirements" / "build.txt",
        ],
    ),
)
def source_tarball(ctx: Context):
    shutil.rmtree("dist/", ignore_errors=True)
    timestamp = ctx.run(
        "git",
        "show",
        "-s",
        "--format=%at",
        "HEAD",
        capture=True,
    ).stdout.strip()
    env = {
        **os.environ,
        **{
            "SOURCE_DATE_EPOCH": str(timestamp),
        },
    }
    ctx.run(
        "python3",
        "-m",
        "build",
        "--sdist",
        str(tools.utils.REPO_ROOT),
        env=env,
        check=True,
    )
    # Recreate sdist to be reproducible
    recompress = Recompress(timestamp)
    for targz in tools.utils.REPO_ROOT.joinpath("dist").glob("*.tar.gz"):
        ctx.info(f"Re-compressing {targz.relative_to(tools.utils.REPO_ROOT)} ...")
        recompress.recompress(targz)
    sha256sum = shutil.which("sha256sum")
    if sha256sum:
        packages = [
            str(pkg.relative_to(tools.utils.REPO_ROOT))
            for pkg in tools.utils.REPO_ROOT.joinpath("dist").iterdir()
        ]
        ctx.run("sha256sum", *packages)
    ctx.run("python3", "-m", "twine", "check", "dist/*", check=True)


@pkg.command(
    name="pypi-upload",
    venv_config=VirtualEnvPipConfig(
        requirements_files=[
            tools.utils.REPO_ROOT / "requirements" / "build.txt",
        ],
    ),
    arguments={
        "files": {
            "help": "Files to upload to PyPi",
            "nargs": "*",
        },
        "test": {
            "help": "When true, upload to test.pypi.org instead",
        },
    },
)
def pypi_upload(ctx: Context, files: list[pathlib.Path], test: bool = False):
    ctx.run(
        "python3", "-m", "twine", "check", *[str(fpath) for fpath in files], check=True
    )
    if test is True:
        repository_url = "https://test.pypi.org/legacy/"
    else:
        repository_url = "https://upload.pypi.org/legacy/"
    if "TWINE_USERNAME" not in os.environ:
        os.environ["TWINE_USERNAME"] = "__token__"
    if "TWINE_PASSWORD" not in os.environ:
        ctx.error("The 'TWINE_PASSWORD' variable is not set. Cannot upload.")
        ctx.exit(1)
    cmdline = [
        "twine",
        "upload",
        f"--repository-url={repository_url}",
        "--username=__token__",
    ]
    if test is True:
        cmdline.append("--skip-existing")
    cmdline.extend([str(fpath) for fpath in files])
    ctx.info(f"Running '{' '.join(cmdline)}' ...")
    ret = ctx.run(*cmdline, check=False)
    if ret.returncode:
        ctx.error(ret.stderr.strip().decode())
    ctx.exit(ret.returncode)


@pkg.command(
    name="configure-git",
    arguments={
        "user": {
            "help": "The git global username",
            "required": False,
        },
        "email": {
            "help": "The git global email",
            "required": False,
        },
    },
)
def configure_git(
    ctx: Context,
    user: str = "Salt Project Packaging",
    email: str = "saltproject-packaging@vmware.com",
):
    cwd = pathlib.Path.cwd()
    ctx.info("Setting name and email in git global config")
    ctx.run("git", "config", "--global", "user.name", f"'{user}'")
    ctx.run("git", "config", "--global", "user.email", f"{email}")
    ctx.info(f"Adding {str(cwd)} as a safe directory")
    ctx.run("git", "config", "--global", "--add", "safe.directory", str(cwd))


@pkg.command(
    name="apply-release-patch",
    arguments={
        "patch": {"help": "The git global username"},
        "delete": {
            "help": "Whether to delete the patch after applying",
            "required": False,
        },
    },
)
def apply_release_patch(ctx: Context, patch: pathlib.Path, delete: bool = False):
    patch = patch.resolve()
    ctx.info("Applying the release patch")
    ctx.run("git", "am", "--committer-date-is-author-date", patch.name)
    if delete:
        ctx.info("Deleting the release patch because --delete was passed")
        patch.unlink()
