# -*- coding: utf-8 -*-
'''
Module for gathering disk information on Windows

:depends:   - win32api Python module
'''

# Import python libs
import ctypes
import string

# Import salt libs
import salt.utils

try:
    import win32api
except ImportError:
    pass

# Define the module's virtual name
__virtualname__ = 'disk'

# Don't shadow built-in's.
__func_alias__ = {
    'help_': 'help'
}


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows():
        return __virtualname__
    return False


def usage():
    '''
    Return usage information for volumes mounted on this minion

    CLI Example:

    .. code-block:: bash

        salt '*' disk.usage
    '''
    drives = []
    ret = {}
    drive_bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for letter in string.uppercase:
        if drive_bitmask & 1:
            drives.append(letter)
        drive_bitmask >>= 1
    for drive in drives:
        try:
            (sectorspercluster,
             bytespersector,
             freeclusters,
             totalclusters) = win32api.GetDiskFreeSpace(
                 '{0}:\\'.format(drive)
             )
            totalsize = sectorspercluster * bytespersector * totalclusters
            available_space = (
                sectorspercluster * bytespersector * freeclusters
            )
            used = totalsize - available_space
            capacity = int(used / float(totalsize) * 100)
            ret['{0}:\\'.format(drive)] = {
                'filesystem': '{0}:\\'.format(drive),
                '1K-blocks': totalsize,
                'used': used,
                'available': available_space,
                'capacity': '{0}%'.format(capacity),
            }
        except Exception:
            ret['{0}:\\'.format(drive)] = {
                'filesystem': '{0}:\\'.format(drive),
                '1K-blocks': None,
                'used': None,
                'available': None,
                'capacity': None,
            }
    return ret


def help_(cmd=None):
    '''
    Display help for module

    CLI Example:

    .. code-block:: bash

        salt '*' disk.help

        salt '*' disk.help usage
    '''
    if '__virtualname__' in globals():
        module_name = __virtualname__
    else:
        module_name = __name__.split('.')[-1]

    if cmd is None:
        return __salt__['sys.doc']('{0}' . format(module_name))
    else:
        return __salt__['sys.doc']('{0}.{1}' . format(module_name, cmd))
