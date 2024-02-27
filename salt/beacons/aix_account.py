"""
Beacon to fire event when we notice a AIX user is locked due to many failed login attempts.

.. versionadded:: 2018.3.0

:depends: none
"""

import logging

log = logging.getLogger(__name__)

__virtualname__ = "aix_account"


def __virtual__():
    """
    Only load if kernel is AIX
    """
    if __grains__["kernel"] == "AIX":
        return __virtualname__

    err_msg = "Only available on AIX systems."
    log.error("Unable to load %s beacon: %s", __virtualname__, err_msg)
    return False, err_msg


def validate(config):
    """
    Validate the beacon configuration
    """
    # Configuration for aix_account beacon should be a dictionary
    if not isinstance(config, dict):
        return False, "Configuration for aix_account beacon must be a dict."
    if "user" not in config:
        return (
            False,
            "Configuration for aix_account beacon must include a user or ALL for all users.",
        )
    return True, "Valid beacon configuration"


def beacon(config):
    """
    Checks for locked accounts due to too many invalid login attempts, 3 or higher.

    .. code-block:: yaml

        beacons:
          aix_account:
            user: ALL
            interval: 120

    """

    ret = []

    user = config["user"]

    locked_accounts = __salt__["shadow.login_failures"](user)
    ret.append({"accounts": locked_accounts})

    return ret
