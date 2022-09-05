"""
Management of NTP servers
=========================

.. versionadded:: 2014.1.0

This state is used to manage NTP servers. Currently only Windows is supported.

.. code-block:: yaml

    win_ntp:
      ntp.managed:
        - servers:
          - pool.ntp.org
          - us.pool.ntp.org
"""

import logging

import salt.utils.platform

log = logging.getLogger(__name__)


def __virtual__():
    """
    This only supports Windows
    """
    if not salt.utils.platform.is_windows():
        return (False, "Only Windows supported")
    return "ntp"


def _check_servers(servers):
    if not isinstance(servers, list):
        return False
    for server in servers:
        if not isinstance(server, str):
            return False
    return True


def _get_servers():
    try:
        return set(__salt__["ntp.get_servers"]())
    except TypeError:
        return {False}


def managed(name, servers=None):
    """
    Manage NTP servers

    servers
        A list of NTP servers
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "NTP servers already configured as specified",
    }

    if not _check_servers(servers):
        ret["result"] = False
        ret["comment"] = "NTP servers must be a list of strings"

    before_servers = _get_servers()
    desired_servers = set(servers)

    if before_servers == desired_servers:
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "NTP servers will be updated to: {}".format(
            ", ".join(sorted(desired_servers))
        )
        return ret

    __salt__["ntp.set_servers"](*desired_servers)
    after_servers = _get_servers()

    if after_servers == desired_servers:
        ret["comment"] = "NTP servers updated"
        ret["changes"] = {"old": sorted(before_servers), "new": sorted(after_servers)}
    else:
        ret["result"] = False
        ret["comment"] = "Failed to update NTP servers"
        if before_servers != after_servers:
            ret["changes"] = {
                "old": sorted(before_servers),
                "new": sorted(after_servers),
            }

    return ret
