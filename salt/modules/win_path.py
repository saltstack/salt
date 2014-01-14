# -*- coding: utf-8 -*-
'''
Manage the Windows System PATH

Note that not all Windows applications will rehash the PATH environment variable,
Only the ones that listen to the WM_SETTINGCHANGE message
http://support.microsoft.com/kb/104011
'''

# Python Libs
import logging
import re

# Third party libs
try:
    import win32gui
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

# Import salt libs
import salt.utils

# Settings
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Load only on Windows
    '''
    if salt.utils.is_windows() and HAS_WIN32:
        return 'win_path'
    return False


def _normalize_dir(string):
    '''
    Normalize the directory to make comparison possible
    '''
    return re.sub(r'\\$', '', string.lower())


def rehash():
    '''
    Send a WM_SETTINGCHANGE Broadcast to Windows to rehash the Environment variables
    '''
    return win32gui.SendMessageTimeout(win32con.HWND_BROADCAST, win32con.WM_SETTINGCHANGE, 0, 'Environment', 0, 10000)[0] == 1


def get_path():
    '''
    Returns the system path
    '''
    ret = __salt__['reg.read_key']('HKEY_LOCAL_MACHINE', 'SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment', 'PATH').split(';')

    # Trim ending backslash
    return map(_normalize_dir, ret)


def exists(path):
    '''
    Check if the directory is configured in the SYSTEM path
    Case-insensitive and ignores trailing backslash

    CLI Example:

    .. code-block:: bash

        salt '*' win_path.exists 'c:\\python27'
        salt '*' win_path.exists 'c:\\python27\\'
        salt '*' win_path.exists 'C:\\pyThon27'
    '''
    path = _normalize_dir(path)
    sysPath = get_path()

    return path in sysPath


def add(path, index=0):
    '''
    Add the directory to the SYSTEM path in the index location

    CLI Example:

    .. code-block:: bash

        # Will add to the beginning of the path
        salt '*' win_path.add 'c:\\python27' 0

        # Will add to the end of the path
        salt '*' win_path.add 'c:\\python27' index='-1'
    '''
    currIndex = -1
    sysPath = get_path()
    path = _normalize_dir(path)
    index = int(index)

    # validate index boundaries
    if index < 0:
        index = len(sysPath) + index + 1
    if index > len(sysPath):
        index = len(sysPath)

    # Check if we are in the system path at the right location
    try:
        currIndex = sysPath.index(path)
        if currIndex != index:
            sysPath.pop(currIndex)
        else:
            return True
    except ValueError:
        pass

    # Add it to the Path
    sysPath.insert(index, path)
    regedit = __salt__['reg.set_key'](
        'HKEY_LOCAL_MACHINE',
        'SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment',
        'PATH',
        ';'.join(sysPath),
        'REG_EXPAND_SZ'
        )

    # Broadcast WM_SETTINGCHANGE to Windows
    if regedit:
        return rehash()
    else:
        return False


def remove(path):
    '''
    Remove the directory from the SYSTEM path
    '''
    path = _normalize_dir(path)
    sysPath = get_path()
    try:
        sysPath.remove(path)
    except ValueError:
        return True

    regedit = __salt__['reg.set_key'](
        'HKEY_LOCAL_MACHINE',
        'SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment',
        'PATH',
        ';'.join(sysPath),
        'REG_EXPAND_SZ'
    )
    if regedit:
        return rehash()
    else:
        return False
