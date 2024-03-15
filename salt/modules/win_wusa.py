"""
Microsoft Update files management via wusa.exe

:maintainer:    Thomas Lemarchand
:platform:      Windows
:depends:       PowerShell

.. versionadded:: 2018.3.4
"""

import logging
import os

import salt.utils.platform
import salt.utils.win_pwsh
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "wusa"
__func_alias__ = {"list_": "list"}


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
            cmd=f"Get-HotFix -Id {name}",
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
        2359302: f"{file_name} is already installed",
        3010: (
            f"{file_name} correctly installed but server reboot is needed to "
            f"complete installation"
        ),
        87: "Unknown error",
    }
    if ret_code in errors:
        raise CommandExecutionError(errors[ret_code], ret_code)
    elif ret_code:
        raise CommandExecutionError(f"Unknown error: {ret_code}")

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
        cmd.append("/kb:{}".format(kb[2:] if kb.lower().startswith("kb") else kb))
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
        -2145116156: f"{kb} does not support uninstall",
        2359303: f"{kb} not installed",
        87: "Unknown error. Try specifying an .msu file",
    }
    if ret_code in errors:
        raise CommandExecutionError(errors[ret_code], ret_code)
    elif ret_code:
        raise CommandExecutionError(f"Unknown error: {ret_code}")

    return True


def list_():
    """
    Get a list of updates installed on the machine

    Returns:
        list: A list of installed updates

    CLI Example:

    .. code-block:: bash

        salt '*' wusa.list
    """
    kbs = []
    ret = salt.utils.win_pwsh.run_dict("Get-HotFix | Select HotFixID")
    for item in ret:
        kbs.append(item["HotFixID"])
    return kbs
