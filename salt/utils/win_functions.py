# -*- coding: utf-8 -*-
'''
Various functions to be used by windows during start up and to monkey patch
missing functions in other modules
'''
from __future__ import absolute_import
import platform
import re

# Import Salt Libs
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
    # If None is passed, use the Universal Well-known SID "Null SID"
    if name is None:
        name = 'NULL SID'

    try:
        sid = win32security.LookupAccountName(None, name)[0]
    except pywintypes.error as exc:
        raise CommandExecutionError(
            'User {0} not found: {1}'.format(name, exc.strerror))

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


def get_sam_name(username):
    r'''
    Gets the SAM name for a user. It basically prefixes a username without a
    backslash with the computer name. If the user does not exist, a SAM
    compatible name will be returned using the local hostname as the domain.

    i.e. salt.utils.get_same_name('Administrator') would return 'DOMAIN.COM\Administrator'

    .. note:: Long computer names are truncated to 15 characters
    '''
    try:
        sid_obj = win32security.LookupAccountName(None, username)[0]
    except pywintypes.error:
        return '\\'.join([platform.node()[:15].upper(), username])
    username, domain, _ = win32security.LookupAccountSid(None, sid_obj)
    return '\\'.join([domain, username])


def escape_argument(arg):
    '''
    Escape the argument for the cmd.exe shell.
    See http://blogs.msdn.com/b/twistylittlepassagesallalike/archive/2011/04/23/everyone-quotes-arguments-the-wrong-way.aspx

    First we escape the quote chars to produce a argument suitable for
    CommandLineToArgvW. We don't need to do this for simple arguments.

    Args:
        arg (str): a single command line argument to escape for the cmd.exe shell

    Returns:
        str: an escaped string suitable to be passed as a program argument to the cmd.exe shell
    '''
    if not arg or re.search(r'(["\s])', arg):
        arg = '"' + arg.replace('"', r'\"') + '"'

    return escape_for_cmd_exe(arg)


def escape_for_cmd_exe(arg):
    '''
    Escape an argument string to be suitable to be passed to
    cmd.exe on Windows

    This method takes an argument that is expected to already be properly
    escaped for the receiving program to be properly parsed. This argument
    will be further escaped to pass the interpolation performed by cmd.exe
    unchanged.

    Any meta-characters will be escaped, removing the ability to e.g. use
    redirects or variables.

    Args:
        arg (str): a single command line argument to escape for cmd.exe

    Returns:
        str: an escaped string suitable to be passed as a program argument to cmd.exe
    '''
    meta_chars = '()%!^"<>&|'
    meta_re = re.compile('(' + '|'.join(re.escape(char) for char in list(meta_chars)) + ')')
    meta_map = {char: "^{0}".format(char) for char in meta_chars}

    def escape_meta_chars(m):
        char = m.group(1)
        return meta_map[char]

    return meta_re.sub(escape_meta_chars, arg)
