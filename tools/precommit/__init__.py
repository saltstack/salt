"""
These commands, and sub-commands, are used by pre-commit.
"""
from ptscripts import command_group

# Define the command group
cgroup = command_group(
    name="pre-commit", help="Pre-Commit Related Commands", description=__doc__
)
