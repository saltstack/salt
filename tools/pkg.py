"""
These commands are used to build Salt packages.
"""
# pylint: disable=resource-leakage,broad-except
from __future__ import annotations

import fnmatch
import logging
import os
import pathlib
import shutil
import sys

import yaml
from ptscripts import Context, command_group

log = logging.getLogger(__name__)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Define the command group
pkg = command_group(name="pkg", help="Packaging Related Commands", description=__doc__)


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
    },
)
def set_salt_version(ctx: Context, salt_version: str, overwrite: bool = False):
    """
    Write the Salt version to 'salt/_version.txt'
    """
    salt_version_file = REPO_ROOT / "salt" / "_version.txt"
    if salt_version_file.exists():
        if not overwrite:
            ctx.error("The 'salt/_version.txt' file already exists")
            ctx.exit(1)
        salt_version_file.unlink()
    if salt_version is None:
        if not REPO_ROOT.joinpath(".git").exists():
            ctx.error(
                "Apparently not running from a Salt repository checkout. "
                "Unable to discover the Salt version."
            )
            ctx.exit(1)
            ctx.info("Discovering the Salt version...")
        ret = ctx.run(shutil.which("python3"), "salt/version.py", capture=True)
        salt_version = ret.stdout.strip().decode()
        ctx.info(f"Discovered Salt version: {salt_version!r}")

    if not REPO_ROOT.joinpath("salt").is_dir():
        ctx.error(
            "The path 'salt/' is not a directory. Unable to write 'salt/_version.txt'"
        )
        ctx.exit(1)

    try:
        REPO_ROOT.joinpath("salt/_version.txt").write_text(salt_version)
    except Exception as exc:
        ctx.error(f"Unable to write 'salt/_version.txt': {exc}")
        ctx.exit(1)

    ctx.info(f"Successfuly wrote {salt_version!r} to 'salt/_version.txt'")

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
    Clean the provided path of paths that shouyld not be included in the archive.

    For example:

        * `__pycache__` directories
        * `*.pyc` files
        * `*.pyo` files

    When running on Windows and macOS, some additional cleanup is also done.
    """
    with open(str(REPO_ROOT / "cicd" / "env-cleanup-files.yml")) as rfh:
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

    dir_patterns = set()
    for pattern in patterns["dir_patterns"]:
        if isinstance(pattern, list):
            dir_patterns.update(set(pattern))
            continue
        dir_patterns.add(pattern)

    file_patterns = set()
    for pattern in patterns["file_patterns"]:
        if isinstance(pattern, list):
            file_patterns.update(set(pattern))
            continue
        file_patterns.add(pattern)

    for root, dirs, files in os.walk(cleanup_path, topdown=True, followlinks=False):
        for dirname in dirs:
            path = pathlib.Path(root, dirname).resolve()
            if not path.exists():
                continue
            match_path = path.as_posix()
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
