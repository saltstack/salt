"""
Module for gathering disk information on Windows

:depends:   - win32api Python module
"""

import ctypes
import string

import salt.utils.platform

try:
    import win32api
except ImportError:
    pass

# Define the module's virtual name
__virtualname__ = "disk"


UPPERCASE = string.ascii_uppercase


def __virtual__():
    """
    Only works on Windows systems
    """
    if salt.utils.platform.is_windows():
        return __virtualname__
    return (False, "Module win_disk: module only works on Windows systems")


def usage():
    """
    Return usage information for volumes mounted on this minion

    CLI Example:

    .. code-block:: bash

        salt '*' disk.usage
    """
    drives = []
    ret = {}
    drive_bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for letter in UPPERCASE:
        if drive_bitmask & 1:
            drives.append(letter)
        drive_bitmask >>= 1
    for drive in drives:
        try:
            (
                available_bytes,
                total_bytes,
                total_free_bytes,
            ) = win32api.GetDiskFreeSpaceEx(f"{drive}:\\")
            used = total_bytes - total_free_bytes
            capacity = used / float(total_bytes) * 100
            ret[f"{drive}:\\"] = {
                "filesystem": f"{drive}:\\",
                "1K-blocks": total_bytes / 1024,
                "used": used / 1024,
                "available": total_free_bytes / 1024,
                "capacity": f"{capacity:.0f}%",
            }
        except Exception:  # pylint: disable=broad-except
            ret[f"{drive}:\\"] = {
                "filesystem": f"{drive}:\\",
                "1K-blocks": None,
                "used": None,
                "available": None,
                "capacity": None,
            }
    return ret
