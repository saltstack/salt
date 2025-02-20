"""
These commands are used to generate Salt's manpages.
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import logging
import os
import pathlib
import shutil
import sys

from ptscripts import Context, command_group
from ptscripts.models import VirtualEnvPipConfig

import tools.utils

log = logging.getLogger(__name__)

# Define the command group
docs = command_group(
    name="docs",
    help="Manpages tools",
    description=__doc__,
    venv_config=VirtualEnvPipConfig(
        requirements_files=[
            tools.utils.REPO_ROOT / "requirements" / "base.txt",
            tools.utils.REPO_ROOT / "requirements" / "zeromq.txt",
            tools.utils.REPO_ROOT
            / "requirements"
            / "static"
            / "ci"
            / "py{}.{}".format(*sys.version_info)
            / "docs.txt",
        ],
        install_args=[
            "--constraint",
            str(
                tools.utils.REPO_ROOT
                / "requirements"
                / "static"
                / "pkg"
                / "py{}.{}".format(*sys.version_info)
                / "linux.txt"
            ),
        ],
    ),
)


@docs.command(
    name="man",
    arguments={
        "no_clean": {
            "help": "Don't cleanup prior to building",
        },
        "no_color": {
            "help": "Disable colored output.",
        },
    },
)
def man(ctx: Context, no_clean: bool = False, no_color: bool = False):
    if no_clean is False:
        ctx.run("make", "clean", cwd="doc/", check=True)
    opts = [
        "-W",
        "-j",
        "auto",
        "--keep-going",
    ]
    if no_color is False:
        opts.append("--color")
    ctx.run(
        "make",
        "man",
        f"SPHINXOPTS={' '.join(opts)}",
        cwd="doc/",
        check=True,
    )
    for root, dirs, files in os.walk("doc/_build/man"):
        for file in files:
            shutil.copy(os.path.join(root, file), os.path.join("doc/man", file))


@docs.command(
    name="html",
    arguments={
        "no_clean": {
            "help": "Don't cleanup prior to building",
        },
        "no_color": {
            "help": "Disable colored output.",
        },
        "archive": {
            "help": "Compress the generated documentation into the provided archive.",
        },
    },
)
def html(
    ctx: Context,
    no_clean: bool = False,
    no_color: bool = False,
    archive: pathlib.Path = os.environ.get("ARCHIVE_FILENAME"),  # type: ignore[assignment]
):
    if no_clean is False:
        ctx.run("make", "clean", cwd="doc/", check=True)
    opts = [
        "-W",
        "-j",
        "auto",
        "--keep-going",
    ]
    if no_color is False:
        opts.append("--color")
    ctx.run(
        "make",
        "html",
        f"SPHINXOPTS={' '.join(opts)}",
        cwd="doc/",
        check=True,
    )
    github_output = os.environ.get("GITHUB_OUTPUT")
    if archive is not None:
        ctx.info(f"Compressing the generated documentation to '{archive}'...")
        ctx.run("tar", "caf", str(archive.resolve()), ".", cwd="doc/_build/html")

        if github_output is not None:
            with open(github_output, "a", encoding="utf-8") as wfh:
                wfh.write(
                    "has-artifacts=true\n"
                    f"artifact-name={archive.resolve().name}\n"
                    f"artifact-path={archive.resolve()}\n"
                )
    elif github_output is not None:
        artifact = tools.utils.REPO_ROOT / "doc" / "_build" / "html"
        if "LATEST_RELEASE" in os.environ:
            artifact_name = f"salt-{os.environ['LATEST_RELEASE']}-docs-html"
        else:
            artifact_name = "salt-docs-html"
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(
                "has-artifacts=true\n"
                f"artifact-name={artifact_name}\n"
                f"artifact-path={artifact.resolve()}\n"
            )


@docs.command(
    name="pdf",
    arguments={
        "no_clean": {
            "help": "Don't cleanup prior to building",
        },
        "no_color": {
            "help": "Disable colored output.",
        },
    },
)
def pdf(ctx: Context, no_clean: bool = False, no_color: bool = False):
    if not shutil.which("inkscape"):
        ctx.warn("No inkscape binary found")
        ctx.exit(1)
    if no_clean is False:
        ctx.run("make", "clean", cwd="doc/", check=True)
    opts = [
        "-W",
        "-j",
        "auto",
        "--keep-going",
    ]
    if no_color is False:
        opts.append("--color")
    ctx.run(
        "make",
        "pdf",
        f"SPHINXOPTS={' '.join(opts)}",
        cwd="doc/",
        check=True,
    )

    artifact = tools.utils.REPO_ROOT / "doc" / "_build" / "latex" / "Salt.pdf"
    if "LATEST_RELEASE" in os.environ:
        shutil.move(
            artifact, artifact.parent / f"Salt-{os.environ['LATEST_RELEASE']}.pdf"
        )
        artifact = artifact.parent / f"Salt-{os.environ['LATEST_RELEASE']}.pdf"
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is not None:
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write(
                "has-artifacts=true\n"
                f"artifact-name={artifact.resolve().name}\n"
                f"artifact-path={artifact.resolve()}\n"
            )


@docs.command(
    name="linkcheck",
    arguments={
        "no_clean": {
            "help": "Don't cleanup prior to building",
        },
        "no_color": {
            "help": "Disable colored output.",
        },
    },
)
def linkcheck(ctx: Context, no_clean: bool = False, no_color: bool = False):
    if no_clean is False:
        ctx.run("make", "clean", cwd="doc/", check=True)
    opts = [
        "-W",
        "-j",
        "auto",
        "--keep-going",
    ]
    if no_color is False:
        opts.append("--color")
    ctx.run(
        "make",
        "linkcheck",
        f"SPHINXOPTS={' '.join(opts)}",
        cwd="doc/",
        check=True,
    )
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is not None:
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write("has-artifacts=false\n")


@docs.command(
    name="spellcheck",
    arguments={
        "no_clean": {
            "help": "Don't cleanup prior to building",
        },
        "no_color": {
            "help": "Disable colored output.",
        },
    },
)
def spellcheck(ctx: Context, no_clean: bool = False, no_color: bool = False):
    if no_clean is False:
        ctx.run("make", "clean", cwd="doc/", check=True)
    opts = [
        "-W",
        "-j",
        "auto",
        "--keep-going",
    ]
    if no_color is False:
        opts.append("--color")
    ctx.run(
        "make",
        "spelling",
        f"SPHINXOPTS={' '.join(opts)}",
        cwd="doc/",
        check=True,
    )
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is not None:
        with open(github_output, "a", encoding="utf-8") as wfh:
            wfh.write("has-artifacts=false\n")
