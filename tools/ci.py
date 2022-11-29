"""
These commands are used in the CI pipeline.
"""
from __future__ import annotations

import json
import logging
import pathlib

from ptscripts import Context, command_group

log = logging.getLogger(__name__)

REPO_ROOT = pathlib.Path(__file__).parent.parent

# Define the command group
ci = command_group(name="ci", help="CI Related Commands", description=__doc__)


@ci.command(
    arguments={
        "distro_slug": {
            "help": "The distribution slug to generate the matrix for",
        },
    },
)
def matrix(ctx: Context, distro_slug: str):
    """
    Generate the test matrix.
    """
    _matrix = []
    for transport in ("zeromq", "tcp"):
        if transport == "tcp":
            if distro_slug not in ("centosstream-9", "ubuntu-22.04-arm64"):
                # Only run TCP transport tests on these distributions
                continue
        for chunk in ("unit", "functional", "integration", "scenarios"):
            if transport == "tcp" and chunk in ("unit", "functional"):
                # Only integration and scenarios shall be tested under TCP,
                # the rest would be repeating tests
                continue
            if "macos" in distro_slug and chunk == "scenarios":
                continue
            _matrix.append({"transport": transport, "tests-chunk": chunk})
    print(json.dumps(_matrix))
    ctx.exit(0)


@ci.command(
    name="transport-matrix",
    arguments={
        "distro_slug": {
            "help": "The distribution slug to generate the matrix for",
        },
    },
)
def transport_matrix(ctx: Context, distro_slug: str):
    """
    Generate the test matrix.
    """
    _matrix = []
    for transport in ("zeromq", "tcp"):
        if transport == "tcp":
            if distro_slug not in ("centosstream-9", "ubuntu-22.04-arm64"):
                # Only run TCP transport tests on these distributions
                continue
        _matrix.append({"transport": transport})
    print(json.dumps(_matrix))
    ctx.exit(0)
