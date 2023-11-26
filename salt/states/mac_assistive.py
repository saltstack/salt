"""
Allows you to manage assistive access on macOS minions with 10.9+
=================================================================

Install, enable and disable assistive access on macOS minions

.. code-block:: yaml

    /usr/bin/osacript:
      assistive.installed:
        - enabled: True
"""

import logging

import salt.utils.platform
from salt.utils.versions import Version

log = logging.getLogger(__name__)

__virtualname__ = "assistive"


def __virtual__():
    """
    Only work on Mac OS
    """
    if salt.utils.platform.is_darwin() and Version(__grains__["osrelease"]) >= Version(
        "10.9"
    ):
        return True
    return (False, "Only supported on Mac OS 10.9+")


def installed(name, enabled=True):
    """
    Make sure that we have the given bundle ID or path to command
    installed in the assistive access panel.

    name
        The bundle ID or path to command

    enable
        Should assistive access be enabled on this application?

    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    is_installed = __salt__["assistive.installed"](name)

    if is_installed:
        is_enabled = __salt__["assistive.enabled"](name)

        if enabled != is_enabled:
            __salt__["assistive.enable"](name, enabled)
            ret["comment"] = "Updated enable to {}".format(enabled)
        else:
            ret["comment"] = "Already in the correct state"

    else:
        __salt__["assistive.install"](name, enabled)
        ret["comment"] = "Installed {} into the assistive access panel".format(name)

    return ret
