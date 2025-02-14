"""
Use hiera data as a Pillar source
"""

import logging

import salt.utils.path
import salt.utils.yaml

# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    """
    Only return if hiera is installed
    """
    return "hiera" if salt.utils.path.which("hiera") else False


def ext_pillar(
    minion_id, pillar, conf  # pylint: disable=W0613  # pylint: disable=W0613
):
    """
    Execute hiera and return the data
    """
    cmd = f"hiera -c {conf}"
    for key, val in __grains__.items():
        if isinstance(val, str):
            cmd += f" {key}='{val}'"
    try:
        data = salt.utils.yaml.safe_load(__salt__["cmd.run"](cmd))
    except Exception:  # pylint: disable=broad-except
        log.critical("Hiera YAML data failed to parse from conf %s", conf)
        return {}
    return data
