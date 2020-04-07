# -*- coding: utf-8 -*-
"""
This module allows you to manage assistive access on macOS minions with 10.9+

.. versionadded:: 2016.3.0

.. code-block:: bash

    salt '*' assistive.install /usr/bin/osascript
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import re

# Import salt libs
import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError
from salt.utils.versions import LooseVersion as _LooseVersion

log = logging.getLogger(__name__)

__virtualname__ = "assistive"


def __virtual__():
    """
    Only work on Mac OS
    """
    if not salt.utils.platform.is_darwin():
        return False, "Must be run on macOS"
    if _LooseVersion(__grains__["osrelease"]) < salt.utils.stringutils.to_str("10.9"):
        return False, "Must be run on macOS 10.9 or newer"
    return __virtualname__


def install(app_id, enable=True):
    """
    Install a bundle ID or command as being allowed to use
    assistive access.

    app_id
        The bundle ID or command to install for assistive access.

    enabled
        Sets enabled or disabled status. Default is ``True``.

    CLI Example:

    .. code-block:: bash

        salt '*' assistive.install /usr/bin/osascript
        salt '*' assistive.install com.smileonmymac.textexpander
    """
    ge_el_capitan = (
        True
        if _LooseVersion(__grains__["osrelease"])
        >= salt.utils.stringutils.to_str("10.11")
        else False
    )
    ge_mojave = (
        True
        if _LooseVersion(__grains__["osrelease"])
        >= salt.utils.stringutils.to_str("10.14")
        else False
    )
    client_type = _client_type(app_id)
    enable_str = "1" if enable else "0"
    cmd = (
        'sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db" '
        "\"INSERT or REPLACE INTO access VALUES('kTCCServiceAccessibility','{0}',{1},{2},1,NULL{3}{4})\"".format(
            app_id,
            client_type,
            enable_str,
            ",NULL" if ge_el_capitan else "",
            ",NULL,NULL,NULL,NULL,''" if ge_mojave else "",
        )
    )

    call = __salt__["cmd.run_all"](cmd, output_loglevel="debug", python_shell=False)
    if call["retcode"] != 0:
        comment = ""
        if "stderr" in call:
            comment += call["stderr"]
        if "stdout" in call:
            comment += call["stdout"]

        raise CommandExecutionError("Error installing app: {0}".format(comment))

    return True


def installed(app_id):
    """
    Check if a bundle ID or command is listed in assistive access.
    This will not check to see if it's enabled.

    app_id
        The bundle ID or command to check installed status.

    CLI Example:

    .. code-block:: bash

        salt '*' assistive.installed /usr/bin/osascript
        salt '*' assistive.installed com.smileonmymac.textexpander
    """
    for a in _get_assistive_access():
        if app_id == a[0]:
            return True

    return False


def enable(app_id, enabled=True):
    """
    Enable or disable an existing assistive access application.

    app_id
        The bundle ID or command to set assistive access status.

    enabled
        Sets enabled or disabled status. Default is ``True``.

    CLI Example:

    .. code-block:: bash

        salt '*' assistive.enable /usr/bin/osascript
        salt '*' assistive.enable com.smileonmymac.textexpander enabled=False
    """
    enable_str = "1" if enabled else "0"
    for a in _get_assistive_access():
        if app_id == a[0]:
            cmd = (
                'sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db" '
                "\"UPDATE access SET allowed='{0}' WHERE client='{1}'\"".format(
                    enable_str, app_id
                )
            )

            call = __salt__["cmd.run_all"](
                cmd, output_loglevel="debug", python_shell=False
            )

            if call["retcode"] != 0:
                comment = ""
                if "stderr" in call:
                    comment += call["stderr"]
                if "stdout" in call:
                    comment += call["stdout"]

                raise CommandExecutionError("Error enabling app: {0}".format(comment))

            return True

    return False


def enabled(app_id):
    """
    Check if a bundle ID or command is listed in assistive access and
    enabled.

    app_id
        The bundle ID or command to retrieve assistive access status.

    CLI Example:

    .. code-block:: bash

        salt '*' assistive.enabled /usr/bin/osascript
        salt '*' assistive.enabled com.smileonmymac.textexpander
    """
    for a in _get_assistive_access():
        if app_id == a[0] and a[1] == "1":
            return True

    return False


def remove(app_id):
    """
    Remove a bundle ID or command as being allowed to use assistive access.

    app_id
        The bundle ID or command to remove from assistive access list.

    CLI Example:

    .. code-block:: bash

        salt '*' assistive.remove /usr/bin/osascript
        salt '*' assistive.remove com.smileonmymac.textexpander
    """
    cmd = (
        'sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db" '
        "\"DELETE from access where client='{0}'\"".format(app_id)
    )
    call = __salt__["cmd.run_all"](cmd, output_loglevel="debug", python_shell=False)

    if call["retcode"] != 0:
        comment = ""
        if "stderr" in call:
            comment += call["stderr"]
        if "stdout" in call:
            comment += call["stdout"]

        raise CommandExecutionError("Error removing app: {0}".format(comment))

    return True


def _client_type(app_id):
    """
    Determine whether the given ID is a bundle ID or a
    a path to a command
    """
    return "1" if app_id[0] == "/" else "0"


def _get_assistive_access():
    """
    Get a list of all of the assistive access applications installed,
    returns as a ternary showing whether each app is enabled or not.
    """
    cmd = 'sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db" "SELECT * FROM access"'
    call = __salt__["cmd.run_all"](cmd, output_loglevel="debug", python_shell=False)

    if call["retcode"] != 0:
        comment = ""
        if "stderr" in call:
            comment += call["stderr"]
        if "stdout" in call:
            comment += call["stdout"]

        raise CommandExecutionError("Error: {0}".format(comment))

    out = call["stdout"]
    return re.findall(
        r"kTCCServiceAccessibility\|(.*)\|[0-9]{1}\|([0-9]{1})\|[0-9]{1}\|",
        out,
        re.MULTILINE,
    )
