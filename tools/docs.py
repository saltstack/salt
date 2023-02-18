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

import tools.utils

log = logging.getLogger(__name__)

# Define the command group
docs = command_group(
    name="docs",
    help="Manpages tools",
    description=__doc__,
    venv_config={
        "requirements_files": [
            tools.utils.REPO_ROOT
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
    arguments={
        "no_clean": {
            "help": "Don't cleanup prior to building",
        }
    },
)
def man(ctx: Context, no_clean: bool = False):
    if no_clean is False:
        ctx.run("make", "clean", cwd="doc/", check=True)
    ctx.run("make", "man", "SPHINXOPTS=-W", cwd="doc/", check=True)
    for root, dirs, files in os.walk("doc/_build/man"):
        for file in files:
            shutil.copy(os.path.join(root, file), os.path.join("doc/man", file))


@docs.command(
    name="html",
    arguments={
        "no_clean": {
            "help": "Don't cleanup prior to building",
        },
        "archive": {
            "help": "Compress the generated documentation into the provided archive.",
        },
    },
)
def html(ctx: Context, no_clean: bool = False, archive: pathlib.Path = None):
    if no_clean is False:
        ctx.run("make", "clean", cwd="doc/", check=True)
    ctx.run("make", "html", "SPHINXOPTS=-W --keep-going", cwd="doc/", check=True)
    if archive is not None:
        ctx.info(f"Compressing the generated documentation to '{archive}'...")
        ctx.run("tar", "caf", str(archive.resolve()), ".", cwd="doc/_build/html")


@docs.command(
    name="epub",
    arguments={
        "no_clean": {
            "help": "Don't cleanup prior to building",
        },
    },
)
def epub(ctx: Context, no_clean: bool = False):
    if no_clean is False:
        ctx.run("make", "clean", cwd="doc/", check=True)
    ctx.run("make", "epub", cwd="doc/", check=True)


@docs.command(
    name="pdf",
    arguments={
        "no_clean": {
            "help": "Don't cleanup prior to building",
        }
    },
)
def pdf(ctx: Context, no_clean: bool = False):
    if not shutil.which("inkscape"):
        ctx.warn("No inkscape binary found")
        ctx.exit(1)
    if no_clean is False:
        ctx.run("make", "clean", cwd="doc/", check=True)
    ctx.run("make", "pdf", "SPHINXOPTS=-W", cwd="doc/", check=True)


@docs.command(
    name="linkcheck",
    arguments={
        "no_clean": {
            "help": "Don't cleanup prior to building",
        }
    },
)
def linkcheck(ctx: Context, no_clean: bool = False):
    if no_clean is False:
        ctx.run("make", "clean", cwd="doc/", check=True)
    ctx.run(
        "make",
        "linkcheck",
        "SPHINXOPTS=-W -j auto --keep-going --color",
        cwd="doc/",
        check=True,
    )


@docs.command(
    name="spellcheck",
    arguments={
        "no_clean": {
            "help": "Don't cleanup prior to building",
        }
    },
)
def spellcheck(ctx: Context, no_clean: bool = False):
    if no_clean is False:
        ctx.run("make", "clean", cwd="doc/", check=True)
    ctx.run(
        "make",
        "spelling",
        "SPHINXOPTS=-W -j auto --keep-going --color",
        cwd="doc/",
        check=True,
    )
