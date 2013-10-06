# -*- coding: utf-8 -*-
'''
Module for listing programs that automatically run on startup
(very alpha...not tested on anything but my Win 7x64)
'''

# Import python libs
import os

# Import salt libs
import salt.utils


# Define a function alias in order not to shadow built-in's
__func_alias__ = {
    'list_': 'list'
}


def __virtual__():
    '''
    Only works on Windows systems
    '''

    if salt.utils.is_windows():
        return 'autoruns'
    return False


def list_():
    '''
    Get a list of automatically running programs

    CLI Example:

    .. code-block:: bash

        salt '*' autoruns.list
    '''
    autoruns = {}

    # Find autoruns in registry
    keys = ['HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run',
        'HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /reg:64',
        'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run'
    ]
    winver = __grains__['osfullname']
    for key in keys:
        autoruns[key] = []
        cmd = 'reg query ' + key
        print cmd
        for line in __salt__['cmd.run'](cmd).splitlines():
            if line and line[0:4] != "HKEY" and line[0:5] != "ERROR":   # Remove junk lines
                autoruns[key].append(line)

    # Find autoruns in user's startup folder
    if '7' in winver:
        user_dir = 'C:\\Users\\'
        startup_dir = '\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup'
    else:
        user_dir = 'C:\\Documents and Settings\\'
        startup_dir = '\\Start Menu\\Programs\\Startup'

    for user in os.listdir(user_dir):
        try:
            full_dir = user_dir + user + startup_dir
            files = os.listdir(full_dir)
            autoruns[full_dir] = []
            for afile in files:
                autoruns[full_dir].append(afile)
        except Exception:
            pass

    return autoruns
