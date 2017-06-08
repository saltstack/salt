# -*- coding: utf-8 -*-
'''
Manage the Windows System PATH

Note that not all Windows applications will rehash the PATH environment variable,
Only the ones that listen to the WM_SETTINGCHANGE message
http://support.microsoft.com/kb/104011
'''
from __future__ import absolute_import

# Python Libs
import logging
import re
import os
from salt.ext.six.moves import map

# Third party libs
try:
    from win32con import HWND_BROADCAST, WM_SETTINGCHANGE
    from win32api import SendMessage
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
    return (False, "Module win_path: module only works on Windows systems")


def _normalize_dir(string):
    '''
    Normalize the directory to make comparison possible
    '''
    return re.sub(r'\\$', '', string.lower())


def rehash():
    '''
    Send a WM_SETTINGCHANGE Broadcast to Windows to refresh the Environment variables

    CLI Example:

    ... code-block:: bash

        salt '*' win_path.rehash
    '''
    return bool(SendMessage(HWND_BROADCAST, WM_SETTINGCHANGE, 0, 'Environment'))


def get_path():
    '''
    Returns a list of items in the SYSTEM path

    CLI Example:

    .. code-block:: bash

        salt '*' win_path.get_path
    '''
    ret = __salt__['reg.read_value']('HKEY_LOCAL_MACHINE',
                                   'SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment',
                                   'PATH')['vdata'].split(';')

    # Trim ending backslash
    return list(map(_normalize_dir, ret))


def exists(path):
    '''
    Check if the directory is configured in the SYSTEM path
    Case-insensitive and ignores trailing backslash

    Returns:
        boolean True if path exists, False if not

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

    Returns:
        boolean True if successful, False if unsuccessful

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

    localPath = os.environ["PATH"].split(os.pathsep)
    if path not in localPath:
        localPath.append(path)
        os.environ["PATH"] = os.pathsep.join(localPath)

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
    regedit = __salt__['reg.set_value'](
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
    r'''
    Remove the directory from the SYSTEM path

    Returns:
        boolean True if successful, False if unsuccessful

    CLI Example:

    .. code-block:: bash

        # Will remove C:\Python27 from the path
        salt '*' win_path.remove 'c:\\python27'
    '''
    path = _normalize_dir(path)
    sysPath = get_path()

    localPath = os.environ["PATH"].split(os.pathsep)
    if path in localPath:
        localPath.remove(path)
        os.environ["PATH"] = os.pathsep.join(localPath)

    try:
        sysPath.remove(path)
    except ValueError:
        return True

    regedit = __salt__['reg.set_value'](
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
