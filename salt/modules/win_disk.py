# -*- coding: utf-8 -*-
"""
Module for gathering disk information on Windows

:depends:   - win32api Python module
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import ctypes
import string

# Import Salt libs
import salt.utils.platform

# Import 3rd-party libs
from salt.ext import six

try:
    import win32api
except ImportError:
    pass

# Define the module's virtual name
__virtualname__ = "disk"


if six.PY3:
    UPPERCASE = string.ascii_uppercase
else:
    UPPERCASE = string.uppercase


def __virtual__():
    """
    Only works on Windows systems
    """
    if salt.utils.platform.is_windows():
        return __virtualname__
    return (False, "Module win_disk: module only works on Windows systems")


def letters():
    """
    Return a list of drive letters for volumes mounted on this minion

    CLI Example:

    .. code-block:: bash

        salt '*' disk.letters

    .. versionadded:: 3003
    """
    drives = []
    drive_bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for letter in UPPERCASE:
        if drive_bitmask & 1:
            drives.append(letter)
        drive_bitmask >>= 1
    return drives

def usage():
    """
    Return usage information for volumes mounted on this minion

    CLI Example:

    .. code-block:: bash

        salt '*' disk.usage
    """

    ret = {}
    for drive in letters():
        try:
            (
                available_bytes,
                total_bytes,
                total_free_bytes,
            ) = win32api.GetDiskFreeSpaceEx("{0}:\\".format(drive))
            used = total_bytes - total_free_bytes
            capacity = used / float(total_bytes) * 100
            ret["{0}:\\".format(drive)] = {
                "filesystem": "{0}:\\".format(drive),
                "1K-blocks": total_bytes / 1024,
                "used": used / 1024,
                "available": total_free_bytes / 1024,
                "capacity": "{0:.0f}%".format(capacity),
            }
        except Exception:  # pylint: disable=broad-except
            ret["{0}:\\".format(drive)] = {
                "filesystem": "{0}:\\".format(drive),
                "1K-blocks": None,
                "used": None,
                "available": None,
                "capacity": None,
            }
    return ret
