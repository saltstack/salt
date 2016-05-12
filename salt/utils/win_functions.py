# -*- coding: utf-8 -*-
'''
Various functions to be used by windows during start up and to monkey patch
missing functions in other modules
'''
from salt.exceptions import CommandExecutionError

# Import Salt Libs
import salt.utils

# Import 3rd Party Libs
try:
    import ntsecuritycon
    import psutil
    import pywintypes
    import win32api
    import win32net
    import win32security
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


def __virtual__():
    '''
    Load only on Windows with necessary modules
    '''
    if not salt.utils.is_windows():
        return False, 'This utility only works on Windows'
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
        if group == 'S-1-5-32-544':
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
            'User {0} found: {1}'.format(name, exc[2]))

    return win32security.ConvertSidToStringSid(sid)


def get_name_from_sid(sid):
    '''
    This gets the name from the specified SID. Opposite of get_sid_from_name

    Args:
        sid (str): The SID for which to find the name

    Returns:
        str: The name that corresponds to the passed SID
    '''
    try:
        sid_obj = win32security.ConvertStringSidToSid(sid)
        name = win32security.LookupAccountSid(None, sid_obj)[0]
    except pywintypes.error as exc:
        raise CommandExecutionError(
            'User {0} found: {1}'.format(sid, exc[2]))

    return name


def get_current_user():
    '''
    Gets the user executing the process

    Returns:
        str: The user name
    '''
    try:
        user_name = win32api.GetUserNameEx(win32api.NameSamCompatible)
    except pywintypes.error as exc:
        raise CommandExecutionError(
            'Failed to get current user: {0}'.format(exc[2]))

    if not user_name:
        return False

    return user_name


def get_path_owner(path):
    '''
    Gets the owner of the file or directory passed

    Args:
        path (str): The path for which to obtain owner information

    Returns:
        str: The owner (group or user)
    '''
    # Return owner
    security_descriptor = win32security.GetFileSecurity(
        path, win32security.OWNER_SECURITY_INFORMATION)
    owner_sid = security_descriptor.GetSecurityDescriptorOwner()

    return get_name_from_sid(win32security.ConvertSidToStringSid(owner_sid))


def set_path_owner(path):
    '''
    Sets the owner of a file or directory to be Administrator

    Args:
        path (str): The path to the file or directory

    Returns:
        bool: True if successful, Otherwise CommandExecutionError
    '''
    # Must use the SID here to be locale agnostic
    admins = win32security.ConvertStringSidToSid('S-1-5-32-544')
    try:
        win32security.SetNamedSecurityInfo(
            path,
            win32security.SE_FILE_OBJECT,
            win32security.OWNER_SECURITY_INFORMATION |
            win32security.PROTECTED_DACL_SECURITY_INFORMATION,
            admins,
            None, None, None)
    except pywintypes.error as exc:
        raise CommandExecutionError(
            'Failed to set owner: {0}'.format(exc[2]))

    return True


def set_path_permissions(path):
    '''
    Gives Administrators, System, and Owner full control over the specified
    directory

    Args:
        path (str): The path to the file or directory

    Returns:
        bool: True if successful, Otherwise CommandExecutionError
    '''
    # TODO: Need to make this more generic, maybe a win_dacl utility
    admins = win32security.ConvertStringSidToSid('S-1-5-32-544')
    user = win32security.ConvertStringSidToSid('S-1-5-32-545')
    system = win32security.ConvertStringSidToSid('S-1-5-18')
    owner = win32security.ConvertStringSidToSid('S-1-3-4')

    dacl = win32security.ACL()

    revision = win32security.ACL_REVISION_DS
    inheritance = win32security.CONTAINER_INHERIT_ACE |\
        win32security.OBJECT_INHERIT_ACE
    full_access = ntsecuritycon.GENERIC_ALL
    user_access = ntsecuritycon.GENERIC_READ | \
        ntsecuritycon.GENERIC_EXECUTE

    dacl.AddAccessAllowedAceEx(revision, inheritance, full_access, admins)
    dacl.AddAccessAllowedAceEx(revision, inheritance, full_access, system)
    dacl.AddAccessAllowedAceEx(revision, inheritance, full_access, owner)
    if 'pki' not in path:
        dacl.AddAccessAllowedAceEx(revision, inheritance, user_access, user)

    try:
        win32security.SetNamedSecurityInfo(
            path,
            win32security.SE_FILE_OBJECT,
            win32security.DACL_SECURITY_INFORMATION |
            win32security.PROTECTED_DACL_SECURITY_INFORMATION,
            None, None, dacl, None)
    except pywintypes.error as exc:
        raise CommandExecutionError(
            'Failed to set permissions: {0}'.format(exc[2]))

    return True
