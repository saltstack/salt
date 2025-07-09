"""
Execute an unmodified puppet_node_classifier and read the output as YAML. The YAML data is then directly overlaid onto the minion's Pillar data.
"""

import logging

import salt.utils.yaml

# Don't "fix" the above docstring to put it on two lines, as the sphinx
# autosummary pulls only the first line for its description.


# Set up logging
log = logging.getLogger(__name__)


def ext_pillar(minion_id, pillar, command):  # pylint: disable=W0613
    """
    Execute an unmodified puppet_node_classifier and read the output as YAML
    """
    try:
        data = salt.utils.yaml.safe_load(__salt__["cmd.run"](f"{command} {minion_id}"))
        return data["parameters"]
    except Exception:  # pylint: disable=broad-except
        log.critical("YAML data from %s failed to parse", command)
        return {}
