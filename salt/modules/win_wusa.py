# -*- coding: utf-8 -*-
"""
Microsoft Update files management via wusa.exe

:maintainer:    Thomas Lemarchand
:platform:      Windows
:depends:       PowerShell

.. versionadded:: 2018.3.4
"""

# Import python libs
from __future__ import absolute_import, unicode_literals

import logging
import os

# Import salt libs
import salt.utils.platform
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "wusa"


def __virtual__():
    """
    Load only on Windows
    """
    if not salt.utils.platform.is_windows():
        return False, "Only available on Windows systems"

    powershell_info = __salt__["cmd.shell_info"](shell="powershell", list_modules=False)
    if not powershell_info["installed"]:
        return False, "PowerShell not available"

    return __virtualname__


def _pshell_json(cmd, cwd=None):
    """
    Execute the desired powershell command and ensure that it returns data
    in JSON format and load that into python
    """
    if "convertto-json" not in cmd.lower():
        cmd = "{0} | ConvertTo-Json".format(cmd)
    log.debug("PowerShell: %s", cmd)
    ret = __salt__["cmd.run_all"](cmd, shell="powershell", cwd=cwd)

    if "pid" in ret:
        del ret["pid"]

    if ret.get("stderr", ""):
        error = ret["stderr"].splitlines()[0]
        raise CommandExecutionError(error, info=ret)

    if "retcode" not in ret or ret["retcode"] != 0:
        # run_all logs an error to log.error, fail hard back to the user
        raise CommandExecutionError(
            "Issue executing PowerShell {0}".format(cmd), info=ret
        )

    # Sometimes Powershell returns an empty string, which isn't valid JSON
    if ret["stdout"] == "":
        ret["stdout"] = "{}"

    try:
        ret = salt.utils.json.loads(ret["stdout"], strict=False)
    except ValueError:
        raise CommandExecutionError("No JSON results from PowerShell", info=ret)

    return ret


def is_installed(name):
    """
    Check if a specific KB is installed.

    Args:

        name (str):
            The name of the KB to check

    Returns:
        bool: ``True`` if installed, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' wusa.is_installed KB123456
    """
    return (
        __salt__["cmd.retcode"](
            cmd="Get-HotFix -Id {0}".format(name),
            shell="powershell",
            ignore_retcode=True,
        )
        == 0
    )


def install(path, restart=False):
    """
    Install a KB from a .msu file.

    Args:

        path (str):
            The full path to the msu file to install

        restart (bool):
            ``True`` to force a restart if required by the installation. Adds
            the ``/forcerestart`` switch to the ``wusa.exe`` command. ``False``
            will add the ``/norestart`` switch instead. Default is ``False``

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    Raise:
        CommandExecutionError: If the package is already installed or an error
            is encountered

    CLI Example:

    .. code-block:: bash

        salt '*' wusa.install C:/temp/KB123456.msu
    """
    # Build the command
    cmd = ["wusa.exe", path, "/quiet"]
    if restart:
        cmd.append("/forcerestart")
    else:
        cmd.append("/norestart")

    # Run the command
    ret_code = __salt__["cmd.retcode"](cmd, ignore_retcode=True)

    # Check the ret_code
    file_name = os.path.basename(path)
    errors = {
        2359302: "{0} is already installed".format(file_name),
        3010: "{0} correctly installed but server reboot is needed to complete installation".format(
            file_name
        ),
        87: "Unknown error",
    }
    if ret_code in errors:
        raise CommandExecutionError(errors[ret_code], ret_code)
    elif ret_code:
        raise CommandExecutionError("Unknown error: {0}".format(ret_code))

    return True


def uninstall(path, restart=False):
    """
    Uninstall a specific KB.

    Args:

        path (str):
            The full path to the msu file to uninstall. This can also be just
            the name of the KB to uninstall

        restart (bool):
            ``True`` to force a restart if required by the installation. Adds
            the ``/forcerestart`` switch to the ``wusa.exe`` command. ``False``
            will add the ``/norestart`` switch instead. Default is ``False``

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    Raises:
        CommandExecutionError: If an error is encountered

    CLI Example:

    .. code-block:: bash

        salt '*' wusa.uninstall KB123456

        # or

        salt '*' wusa.uninstall C:/temp/KB123456.msu
    """
    # Build the command
    cmd = ["wusa.exe", "/uninstall", "/quiet"]
    kb = os.path.splitext(os.path.basename(path))[0]
    if os.path.exists(path):
        cmd.append(path)
    else:
        cmd.append("/kb:{0}".format(kb[2:] if kb.lower().startswith("kb") else kb))
    if restart:
        cmd.append("/forcerestart")
    else:
        cmd.append("/norestart")

    # Run the command
    ret_code = __salt__["cmd.retcode"](cmd, ignore_retcode=True)

    # Check the ret_code
    # If you pass /quiet and specify /kb, you'll always get retcode 87 if there
    # is an error. Use the actual file to get a more descriptive error
    errors = {
        -2145116156: "{0} does not support uninstall".format(kb),
        2359303: "{0} not installed".format(kb),
        87: "Unknown error. Try specifying an .msu file",
    }
    if ret_code in errors:
        raise CommandExecutionError(errors[ret_code], ret_code)
    elif ret_code:
        raise CommandExecutionError("Unknown error: {0}".format(ret_code))

    return True


def list():
    """
    Get a list of updates installed on the machine

    Returns:
        list: A list of installed updates

    CLI Example:

    .. code-block:: bash

        salt '*' wusa.list
    """
    kbs = []
    ret = _pshell_json("Get-HotFix | Select HotFixID")
    for item in ret:
        kbs.append(item["HotFixID"])
    return kbs
