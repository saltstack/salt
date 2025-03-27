"""
Module for listing programs that automatically run on startup
(very alpha...not tested on anything but my Win 7x64)
"""

import os

import salt.utils.platform

# Define a function alias in order not to shadow built-in's
__func_alias__ = {"list_": "list"}

# Define the module's virtual name
__virtualname__ = "autoruns"


def __virtual__():
    """
    Only works on Windows systems
    """

    if salt.utils.platform.is_windows():
        return __virtualname__
    return (False, "Module win_autoruns: module only works on Windows systems")


def _get_dirs(user_dir, startup_dir):
    """
    Return a list of startup dirs
    """
    try:
        users = os.listdir(user_dir)
    except OSError:  # pylint: disable=E0602
        users = []

    full_dirs = []
    for user in users:
        full_dir = os.path.join(user_dir, user, startup_dir)
        if os.path.exists(full_dir):
            full_dirs.append(full_dir)
    return full_dirs


def list_():
    """
    Get a list of automatically running programs

    CLI Example:

    .. code-block:: bash

        salt '*' autoruns.list
    """
    autoruns = {}

    # Find autoruns in registry
    keys = [
        "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
        "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /reg:64",
        "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
    ]
    for key in keys:
        autoruns[key] = []
        cmd = ["reg", "query", key]
        for line in __salt__["cmd.run"](cmd, python_shell=False).splitlines():
            if (
                line and line[0:4] != "HKEY" and line[0:5] != "ERROR"
            ):  # Remove junk lines
                autoruns[key].append(line)

    # Find autoruns in user's startup folder
    user_dir = "C:\\Documents and Settings\\"
    startup_dir = "\\Start Menu\\Programs\\Startup"
    full_dirs = _get_dirs(user_dir, startup_dir)
    if not full_dirs:
        user_dir = "C:\\Users\\"
        startup_dir = (
            "\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup"
        )
        full_dirs = _get_dirs(user_dir, startup_dir)

    for full_dir in full_dirs:
        files = os.listdir(full_dir)
        autoruns[full_dir] = []
        for single_file in files:
            autoruns[full_dir].append(single_file)

    return autoruns
