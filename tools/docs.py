"""
These commands are used to generate Salt's manpages.
"""
# pylint: disable=resource-leakage,broad-except
from __future__ import annotations

import logging
import os
import pathlib
import shutil
import sys

from ptscripts import Context, command_group

log = logging.getLogger(__name__)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Define the command group
docs = command_group(
    name="docs",
    help="Manpages tools",
    description=__doc__,
    venv_config={
        "requirements_files": [
            REPO_ROOT
            / "requirements"
            / "static"
            / "ci"
            / "py{}.{}".format(*sys.version_info)
            / "docs.txt"
        ],
    },
)


@docs.command(
    name="man",
)
def man(ctx: Context):
    ctx.run("make", "clean", cwd="doc/", check=True)
    ctx.run("make", "man", "SHPINXOPTS=-W", cwd="doc/", check=True)
    for root, dirs, files in os.walk("doc/_build/man"):
        for file in files:
            shutil.copy(os.path.join(root, file), os.path.join("doc/man", file))


@docs.command(
    name="html",
)
def html(ctx: Context):
    ctx.run("make", "clean", cwd="doc/", check=True)
    ctx.run("make", "html", "SHPINXOPTS=-W", cwd="doc/", check=True)


@docs.command(
    name="epub",
)
def epub(ctx: Context):
    ctx.run("make", "clean", cwd="doc/", check=True)
    ctx.run("make", "epub", "SHPINXOPTS=-W", cwd="doc/", check=True)


@docs.command(
    name="pdf",
)
def pdf(ctx: Context):
    if not shutil.which("inkscape"):
        ctx.warn("No inkscape binary found")
        ctx.exit(1)
    ctx.run("make", "clean", cwd="doc/", check=True)
    ctx.run("make", "pdf", "SHPINXOPTS=-W", cwd="doc/", check=True)
