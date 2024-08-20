"""
Execute a command and read the output as YAML. The YAML data is then directly overlaid onto the minion's Pillar data
"""

import logging

import salt.utils.yaml

# Don't "fix" the above docstring to put it on two lines, as the sphinx
# autosummary pulls only the first line for its description.


# Set up logging
log = logging.getLogger(__name__)


def ext_pillar(
    minion_id, pillar, command  # pylint: disable=W0613  # pylint: disable=W0613
):
    """
    Execute a command and read the output as YAML
    """
    try:
        command = command.replace("%s", minion_id)
        output = __salt__["cmd.run_stdout"](command, python_shell=True)
        return salt.utils.yaml.safe_load(output)
    except Exception:  # pylint: disable=broad-except
        log.critical(
            "YAML data from '%s' failed to parse. Command output:\n%s", command, output
        )
        return {}
