"""
Execute a command and read the output as YAMLEX.

The YAMLEX data is then directly overlaid onto the minion's Pillar data
"""


import logging

from salt.serializers.yamlex import deserialize

# Set up logging
log = logging.getLogger(__name__)


def ext_pillar(
    minion_id, pillar, command  # pylint: disable=W0613  # pylint: disable=W0613
):
    """
    Execute a command and read the output as YAMLEX
    """
    try:
        command = command.replace("%s", minion_id)
        return deserialize(__salt__["cmd.run"](command))
    except Exception:  # pylint: disable=broad-except
        log.critical("YAML data from %s failed to parse", command)
        return {}
