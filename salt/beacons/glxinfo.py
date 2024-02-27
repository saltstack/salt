"""
Beacon to emit when a display is available to a linux machine

.. versionadded:: 2016.3.0
"""

import logging

import salt.utils.beacons
import salt.utils.path

log = logging.getLogger(__name__)

__virtualname__ = "glxinfo"

last_state = {}


def __virtual__():

    which_result = salt.utils.path.which("glxinfo")
    if which_result is None:
        err_msg = "glxinfo is missing."
        log.error("Unable to load %s beacon: %s", __virtualname__, err_msg)
        return False, err_msg
    else:
        return __virtualname__


def validate(config):
    """
    Validate the beacon configuration
    """
    # Configuration for glxinfo beacon should be a dictionary
    if not isinstance(config, list):
        return False, "Configuration for glxinfo beacon must be a list."

    config = salt.utils.beacons.list_to_dict(config)

    if "user" not in config:
        return (
            False,
            "Configuration for glxinfo beacon must include a user as glxinfo is not available to root.",
        )
    return True, "Valid beacon configuration"


def beacon(config):
    """
    Emit the status of a connected display to the minion

    Mainly this is used to detect when the display fails to connect
    for whatever reason.

    .. code-block:: yaml

        beacons:
          glxinfo:
            - user: frank
            - screen_event: True

    """

    log.trace("glxinfo beacon starting")
    ret = []

    config = salt.utils.beacons.list_to_dict(config)

    retcode = __salt__["cmd.retcode"](
        "DISPLAY=:0 glxinfo", runas=config["user"], python_shell=True
    )

    if "screen_event" in config and config["screen_event"]:
        last_value = last_state.get("screen_available", False)
        screen_available = retcode == 0
        if last_value != screen_available or "screen_available" not in last_state:
            ret.append({"tag": "screen_event", "screen_available": screen_available})

        last_state["screen_available"] = screen_available

    return ret
