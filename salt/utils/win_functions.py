# -*- coding: utf-8 -*-
'''
Various functions to be used by windows during start up and to monkey patch
missing functions in other modules
'''
from __future__ import absolute_import
from salt.exceptions import CommandExecutionError

# Import 3rd Party Libs
try:
    import psutil
    import pywintypes
    import win32api
    import win32net
    import win32security
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


# Although utils are often directly imported, it is also possible to use the
# loader.
def __virtual__():
    '''
    Only load if Win32 Libraries are installed
    '''
    if not HAS_WIN32:
        return False, 'This utility requires pywin32'

    return 'win_functions'


def get_parent_pid():
    '''
    This is a monkey patch for os.getppid. Used in:
    - salt.utils.parsers

    Returns:
        int: The parent process id
    '''
    return psutil.Process().ppid()


def is_admin(name):
    '''
    Is the passed user a member of the Administrators group

    Args:
        name (str): The name to check

    Returns:
        bool: True if user is a member of the Administrators group, False
        otherwise
    '''
    groups = get_user_groups(name, True)

    for group in groups:
        if group in ('S-1-5-32-544', 'S-1-5-18'):
            return True

    return False


def get_user_groups(name, sid=False):
    '''
    Get the groups to which a user belongs

    Args:
        name (str): The user name to query
        sid (bool): True will return a list of SIDs, False will return a list of
        group names

    Returns:
        list: A list of group names or sids
    '''
    if name == 'SYSTEM':
        # 'win32net.NetUserGetLocalGroups' will fail if you pass in 'SYSTEM'.
        groups = [name]
    else:
        groups = win32net.NetUserGetLocalGroups(None, name)

    if not sid:
        return groups

    ret_groups = set()
    for group in groups:
        ret_groups.add(get_sid_from_name(group))

    return ret_groups


def get_sid_from_name(name):
    '''
    This is a tool for getting a sid from a name. The name can be any object.
    Usually a user or a group

    Args:
        name (str): The name of the user or group for which to get the sid

    Returns:
        str: The corresponding SID
    '''
    try:
        sid = win32security.LookupAccountName(None, name)[0]
    except pywintypes.error as exc:
        raise CommandExecutionError(
            'User {0} found: {1}'.format(name, exc.strerror))

    return win32security.ConvertSidToStringSid(sid)


def get_current_user():
    '''
    Gets the user executing the process

    Returns:
        str: The user name
    '''
    try:
        user_name = win32api.GetUserNameEx(win32api.NameSamCompatible)
        if user_name[-1] == '$':
            # Make the system account easier to identify.
            # Fetch sid so as to handle other language than english
            test_user = win32api.GetUserName()
            if test_user == 'SYSTEM':
                user_name = 'SYSTEM'
            elif get_sid_from_name(test_user) == 'S-1-5-18':
                user_name = 'SYSTEM'
    except pywintypes.error as exc:
        raise CommandExecutionError(
            'Failed to get current user: {0}'.format(exc.strerror))

    if not user_name:
        return False

    return user_name
