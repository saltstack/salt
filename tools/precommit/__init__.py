"""
These commands, and sub-commands, are used by pre-commit.
"""

from ptscripts import command_group

import tools.utils

# Define the command group
cgroup = command_group(
    name="pre-commit", help="Pre-Commit Related Commands", description=__doc__
)

SALT_BASE_PATH = tools.utils.REPO_ROOT / "salt"

SALT_INTERNAL_LOADERS_PATHS = (
    # This is a 1:1 copy of SALT_INTERNAL_LOADERS_PATHS found in salt/loader/__init__.py
    str(SALT_BASE_PATH / "auth"),
    str(SALT_BASE_PATH / "beacons"),
    str(SALT_BASE_PATH / "cache"),
    str(SALT_BASE_PATH / "client" / "ssh" / "wrapper"),
    str(SALT_BASE_PATH / "cloud" / "clouds"),
    str(SALT_BASE_PATH / "engines"),
    str(SALT_BASE_PATH / "executors"),
    str(SALT_BASE_PATH / "fileserver"),
    str(SALT_BASE_PATH / "grains"),
    str(SALT_BASE_PATH / "log_handlers"),
    str(SALT_BASE_PATH / "matchers"),
    str(SALT_BASE_PATH / "metaproxy"),
    str(SALT_BASE_PATH / "modules"),
    str(SALT_BASE_PATH / "netapi"),
    str(SALT_BASE_PATH / "output"),
    str(SALT_BASE_PATH / "pillar"),
    str(SALT_BASE_PATH / "proxy"),
    str(SALT_BASE_PATH / "queues"),
    str(SALT_BASE_PATH / "renderers"),
    str(SALT_BASE_PATH / "returners"),
    str(SALT_BASE_PATH / "roster"),
    str(SALT_BASE_PATH / "runners"),
    str(SALT_BASE_PATH / "sdb"),
    str(SALT_BASE_PATH / "serializers"),
    str(SALT_BASE_PATH / "spm" / "pkgdb"),
    str(SALT_BASE_PATH / "spm" / "pkgfiles"),
    str(SALT_BASE_PATH / "states"),
    str(SALT_BASE_PATH / "thorium"),
    str(SALT_BASE_PATH / "tokens"),
    str(SALT_BASE_PATH / "tops"),
    str(SALT_BASE_PATH / "utils"),
    str(SALT_BASE_PATH / "wheel"),
)
