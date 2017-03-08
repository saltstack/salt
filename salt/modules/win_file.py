# -*- coding: utf-8 -*-
'''
Manage information about files on the minion, set/read user, group
data

:depends:   - win32api
            - win32file
            - win32security
'''
from __future__ import absolute_import

# Import python libs
import os
import stat
import os.path
import logging
import struct
# pylint: disable=W0611
import operator  # do not remove
from collections import Iterable, Mapping  # do not remove
import datetime  # do not remove.
import tempfile  # do not remove. Used in salt.modules.file.__clean_tmp
import itertools  # same as above, do not remove, it's used in __clean_tmp
import contextlib  # do not remove, used in imported file.py functions
import difflib  # do not remove, used in imported file.py functions
import hashlib  # do not remove, used in imported file.py functions
import errno  # do not remove, used in imported file.py functions
import shutil  # do not remove, used in imported file.py functions
import re  # do not remove, used in imported file.py functions
import string  # do not remove, used in imported file.py functions
import sys  # do not remove, used in imported file.py functions
import fileinput  # do not remove, used in imported file.py functions
import fnmatch  # do not remove, used in imported file.py functions
import mmap  # do not remove, used in imported file.py functions
import glob  # do not remove, used in imported file.py functions
# do not remove, used in imported file.py functions
import salt.ext.six as six  # pylint: disable=import-error,no-name-in-module
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse  # pylint: disable=import-error,no-name-in-module
import salt.utils.atomicfile  # do not remove, used in imported file.py functions
from salt.exceptions import CommandExecutionError, SaltInvocationError
# pylint: enable=W0611

# Import third party libs
try:
    import win32api
    import win32file
    import win32security
    import win32con
    from pywintypes import error as pywinerror
    HAS_WINDOWS_MODULES = True
except ImportError:
    HAS_WINDOWS_MODULES = False

# Import salt libs
import salt.utils
from salt.modules.file import (check_hash,  # pylint: disable=W0611
        directory_exists, get_managed, mkdir, makedirs_, makedirs_perms,
        check_managed, check_managed_changes, check_perms, source_list,
        touch, append, contains, contains_regex, get_source_sum,
        contains_glob, find, psed, get_sum, _get_bkroot, _mkstemp_copy,
        get_hash, manage_file, file_exists, get_diff, line, list_backups,
        __clean_tmp, check_file_meta, _binary_replace,
        _splitlines_preserving_trailing_newline, restore_backup,
        access, copy, readdir, rmdir, truncate, replace, delete_backup,
        search, _get_flags, extract_hash, _error, _sed_esc, _psed,
        RE_FLAG_TABLE, blockreplace, prepend, seek_read, seek_write, rename,
        lstat, path_exists_glob, write, pardir, join, HASHES, HASHES_REVMAP,
        comment, uncomment, _add_flags, comment_line, apply_template_on_contents)

from salt.utils import namespaced_function as _namespaced_function

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'file'


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows():
        if HAS_WINDOWS_MODULES:
            global check_perms, get_managed, makedirs_perms, manage_file
            global source_list, mkdir, __clean_tmp, makedirs_, file_exists
            global check_managed, check_managed_changes, check_file_meta
            global append, _error, directory_exists, touch, contains
            global contains_regex, contains_glob, get_source_sum
            global find, psed, get_sum, check_hash, get_hash, delete_backup
            global get_diff, _get_flags, extract_hash, comment_line
            global access, copy, readdir, rmdir, truncate, replace, search
            global _binary_replace, _get_bkroot, list_backups, restore_backup
            global blockreplace, prepend, seek_read, seek_write, rename, lstat
            global write, pardir, join, _add_flags, apply_template_on_contents
            global path_exists_glob, comment, uncomment, _mkstemp_copy

            replace = _namespaced_function(replace, globals())
            search = _namespaced_function(search, globals())
            _get_flags = _namespaced_function(_get_flags, globals())
            _binary_replace = _namespaced_function(_binary_replace, globals())
            _error = _namespaced_function(_error, globals())
            _get_bkroot = _namespaced_function(_get_bkroot, globals())
            list_backups = _namespaced_function(list_backups, globals())
            restore_backup = _namespaced_function(restore_backup, globals())
            delete_backup = _namespaced_function(delete_backup, globals())
            extract_hash = _namespaced_function(extract_hash, globals())
            append = _namespaced_function(append, globals())
            check_perms = _namespaced_function(check_perms, globals())
            get_managed = _namespaced_function(get_managed, globals())
            check_managed = _namespaced_function(check_managed, globals())
            check_managed_changes = _namespaced_function(check_managed_changes, globals())
            check_file_meta = _namespaced_function(check_file_meta, globals())
            makedirs_perms = _namespaced_function(makedirs_perms, globals())
            makedirs_ = _namespaced_function(makedirs_, globals())
            manage_file = _namespaced_function(manage_file, globals())
            source_list = _namespaced_function(source_list, globals())
            mkdir = _namespaced_function(mkdir, globals())
            file_exists = _namespaced_function(file_exists, globals())
            __clean_tmp = _namespaced_function(__clean_tmp, globals())
            directory_exists = _namespaced_function(directory_exists, globals())
            touch = _namespaced_function(touch, globals())
            contains = _namespaced_function(contains, globals())
            contains_regex = _namespaced_function(contains_regex, globals())
            contains_glob = _namespaced_function(contains_glob, globals())
            get_source_sum = _namespaced_function(get_source_sum, globals())
            find = _namespaced_function(find, globals())
            psed = _namespaced_function(psed, globals())
            get_sum = _namespaced_function(get_sum, globals())
            check_hash = _namespaced_function(check_hash, globals())
            get_hash = _namespaced_function(get_hash, globals())
            get_diff = _namespaced_function(get_diff, globals())
            access = _namespaced_function(access, globals())
            copy = _namespaced_function(copy, globals())
            readdir = _namespaced_function(readdir, globals())
            rmdir = _namespaced_function(rmdir, globals())
            truncate = _namespaced_function(truncate, globals())
            blockreplace = _namespaced_function(blockreplace, globals())
            prepend = _namespaced_function(prepend, globals())
            seek_read = _namespaced_function(seek_read, globals())
            seek_write = _namespaced_function(seek_write, globals())
            rename = _namespaced_function(rename, globals())
            lstat = _namespaced_function(lstat, globals())
            path_exists_glob = _namespaced_function(path_exists_glob, globals())
            write = _namespaced_function(write, globals())
            pardir = _namespaced_function(pardir, globals())
            join = _namespaced_function(join, globals())
            comment = _namespaced_function(comment, globals())
            uncomment = _namespaced_function(uncomment, globals())
            comment_line = _namespaced_function(comment_line, globals())
            _mkstemp_copy = _namespaced_function(_mkstemp_copy, globals())
            _add_flags = _namespaced_function(_add_flags, globals())
            apply_template_on_contents = _namespaced_function(apply_template_on_contents, globals())

            return __virtualname__
    return (False, "Module win_file: module only works on Windows systems")

__outputter__ = {
    'touch': 'txt',
    'append': 'txt',
}

__func_alias__ = {
    'makedirs_': 'makedirs'
}


def _resolve_symlink(path, max_depth=64):
    '''
    Resolves the given symlink path to its real path, up to a maximum of the
    `max_depth` parameter which defaults to 64.

    If the path is not a symlink path, it is simply returned.
    '''
    if sys.getwindowsversion().major < 6:
        raise SaltInvocationError('Symlinks are only supported on Windows Vista or later.')

    # make sure we don't get stuck in a symlink loop!
    paths_seen = set((path, ))
    cur_depth = 0
    while is_link(path):
        path = readlink(path)
        if path in paths_seen:
            raise CommandExecutionError('The given path is involved in a symlink loop.')
        paths_seen.add(path)
        cur_depth += 1
        if cur_depth > max_depth:
            raise CommandExecutionError('Too many levels of symbolic links.')

    return path


def _change_privilege_state(privilege_name, enable):
    '''
    Change the state, either enable or disable, of the named privilege for this
    process.

    If the change fails, an exception will be raised. If successful, it returns
    True.
    '''
    log.debug(
        '{0} the privilege {1} for this process.'.format(
            'Enabling' if enable else 'Disabling',
            privilege_name
        )
    )
    # this is a pseudo-handle that doesn't need to be closed
    hProc = win32api.GetCurrentProcess()
    hToken = None
    try:
        hToken = win32security.OpenProcessToken(
            hProc,
            win32security.TOKEN_QUERY | win32security.TOKEN_ADJUST_PRIVILEGES
        )
        privilege = win32security.LookupPrivilegeValue(None, privilege_name)
        if enable:
            privilege_attrs = win32security.SE_PRIVILEGE_ENABLED
        else:
            # a value of 0 disables a privilege (there's no constant for it)
            privilege_attrs = 0

        # check that the handle has the requested privilege
        token_privileges = dict(win32security.GetTokenInformation(
            hToken, win32security.TokenPrivileges))
        if privilege not in token_privileges:
            if enable:
                raise SaltInvocationError(
                    'The requested privilege {0} is not available for this '
                    'process (check Salt user privileges).'.format(privilege_name))
            else:  # disable a privilege this process does not have
                log.debug(
                    'Cannot disable privilege {0} because this process '
                    'does not have that privilege.'.format(privilege_name)
                )
                return True
        else:
            # check if the privilege is already in the requested state
            if token_privileges[privilege] == privilege_attrs:
                log.debug(
                    'The requested privilege {0} is already in the '
                    'requested state.'.format(privilege_name)
                )
                return True

        changes = win32security.AdjustTokenPrivileges(
            hToken,
            False,
            [(privilege, privilege_attrs)]
        )
    finally:
        if hToken:
            win32api.CloseHandle(hToken)

    if not bool(changes):
        raise SaltInvocationError(
            'Could not {0} the {1} privilege for this process'.format(
                'enable' if enable else 'remove',
                privilege_name
            )
        )
    else:
        return True


def _enable_privilege(privilege_name):
    '''
    Enables the named privilege for this process.
    '''
    return _change_privilege_state(privilege_name, True)


def _disable_privilege(privilege_name):
    '''
    Disables the named privilege for this process.
    '''
    return _change_privilege_state(privilege_name, False)


def gid_to_group(gid):
    '''
    Convert the group id to the group name on this system

    Under Windows, because groups are just another ACL entity, this function
    behaves the same as uid_to_user.

    For maintaining Windows systems, this function is superfluous and only
    exists for API compatibility with Unix. Use the uid_to_user function
    instead; an info level log entry will be generated if this function is used
    directly.

    CLI Example:

    .. code-block:: bash

        salt '*' file.gid_to_group S-1-5-21-626487655-2533044672-482107328-1010
    '''
    func_name = '{0}.gid_to_group'.format(__virtualname__)
    if __opts__.get('fun', '') == func_name:
        log.info('The function {0} should not be used on Windows systems; '
                 'see function docs for details.'.format(func_name))

    return uid_to_user(gid)


def group_to_gid(group):
    '''
    Convert the group to the gid on this system

    Under Windows, because groups are just another ACL entity, this function
    behaves the same as user_to_uid, except if None is given, '' is returned.

    For maintaining Windows systems, this function is superfluous and only
    exists for API compatibility with Unix. Use the user_to_uid function
    instead; an info level log entry will be generated if this function is used
    directly.

    CLI Example:

    .. code-block:: bash

        salt '*' file.group_to_gid administrators
    '''
    func_name = '{0}.group_to_gid'.format(__virtualname__)
    if __opts__.get('fun', '') == func_name:
        log.info('The function {0} should not be used on Windows systems; '
                 'see function docs for details.'.format(func_name))

    return _user_to_uid(group)


def get_pgid(path, follow_symlinks=True):
    '''
    Return the id of the primary group that owns a given file (Windows only)

    This function will return the rarely used primary group of a file. This
    generally has no bearing on permissions unless intentionally configured
    and is most commonly used to provide Unix compatibility (e.g. Services
    For Unix, NFS services).

    Ensure you know what you are doing before using this function.

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_pgid c:\\temp\\test.txt
    '''
    if not os.path.exists(path):
        return False

    # Under Windows, if the path is a symlink, the user that owns the symlink is
    # returned, not the user that owns the file/directory the symlink is
    # pointing to. This behavior is *different* to *nix, therefore the symlink
    # is first resolved manually if necessary. Remember symlinks are only
    # supported on Windows Vista or later.
    if follow_symlinks and sys.getwindowsversion().major >= 6:
        path = _resolve_symlink(path)

    try:
        secdesc = win32security.GetFileSecurity(
            path, win32security.GROUP_SECURITY_INFORMATION
        )
    # Not all filesystems mountable within windows
    # have SecurityDescriptor's.  For instance, some mounted
    # SAMBA shares, or VirtualBox's shared folders.  If we
    # can't load a file descriptor for the file, we default
    # to "Everyone" - http://support.microsoft.com/kb/243330
    except MemoryError:
        # generic memory error (win2k3+)
        return 'S-1-1-0'
    except pywinerror as exc:
        # Incorrect function error (win2k8+)
        if exc.winerror == 1 or exc.winerror == 50:
            return 'S-1-1-0'
        raise
    group_sid = secdesc.GetSecurityDescriptorGroup()
    return win32security.ConvertSidToStringSid(group_sid)


def get_pgroup(path, follow_symlinks=True):
    '''
    Return the name of the primary group that owns a given file (Windows only)

    This function will return the rarely used primary group of a file. This
    generally has no bearing on permissions unless intentionally configured
    and is most commonly used to provide Unix compatibility (e.g. Services
    For Unix, NFS services).

    Ensure you know what you are doing before using this function.

    The return value may be 'None', e.g. if the user is not on a domain. This is
    a valid group - do not confuse this with the Salt/Python value of None which
    means no value was returned. To be certain, use the `get_pgid` function
    which will return the SID, including for the system 'None' group.

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_pgroup c:\\temp\\test.txt
    '''
    return uid_to_user(get_pgid(path, follow_symlinks))


def get_gid(path, follow_symlinks=True):
    '''
    Return the id of the group that owns a given file

    Under Windows, this will return the uid of the file.

    While a file in Windows does have a 'primary group', this rarely used
    attribute generally has no bearing on permissions unless intentionally
    configured and is only used to support Unix compatibility features (e.g.
    Services For Unix, NFS services).

    Salt, therefore, remaps this function to provide functionality that
    somewhat resembles Unix behavior for API compatibility reasons. When
    managing Windows systems, this function is superfluous and will generate
    an info level log entry if used directly.

    If you do actually want to access the 'primary group' of a file, use
    `file.get_pgid`.

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_gid c:\\temp\\test.txt
    '''
    func_name = '{0}.get_gid'.format(__virtualname__)
    if __opts__.get('fun', '') == func_name:
        log.info('The function {0} should not be used on Windows systems; '
                 'see function docs for details. The value returned is the '
                 'uid.'.format(func_name))

    return get_uid(path, follow_symlinks)


def get_group(path, follow_symlinks=True):
    '''
    Return the group that owns a given file

    Under Windows, this will return the user (owner) of the file.

    While a file in Windows does have a 'primary group', this rarely used
    attribute generally has no bearing on permissions unless intentionally
    configured and is only used to support Unix compatibility features (e.g.
    Services For Unix, NFS services).

    Salt, therefore, remaps this function to provide functionality that
    somewhat resembles Unix behavior for API compatibility reasons. When
    managing Windows systems, this function is superfluous and will generate
    an info level log entry if used directly.

    If you do actually want to access the 'primary group' of a file, use
    `file.get_pgroup`.

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_group c:\\temp\\test.txt
    '''
    func_name = '{0}.get_group'.format(__virtualname__)
    if __opts__.get('fun', '') == func_name:
        log.info('The function {0} should not be used on Windows systems; '
                 'see function docs for details. The value returned is the '
                 'user (owner).'.format(func_name))

    return get_user(path, follow_symlinks)


def uid_to_user(uid):
    '''
    Convert a uid to a user name

    CLI Example:

    .. code-block:: bash

        salt '*' file.uid_to_user S-1-5-21-626487655-2533044672-482107328-1010
    '''
    if uid is None or uid == '':
        return ''

    sid = win32security.GetBinarySid(uid)
    try:
        name, domain, account_type = win32security.LookupAccountSid(None, sid)
        return name
    except pywinerror as exc:
        # if user does not exist...
        # 1332 = No mapping between account names and security IDs was carried
        # out.
        if exc.winerror == 1332:
            return ''
        else:
            raise


def user_to_uid(user):
    '''
    Convert user name to a uid

    CLI Example:

    .. code-block:: bash

        salt '*' file.user_to_uid myusername
    '''
    if user is None:
        user = salt.utils.get_user()
    return _user_to_uid(user)


def _user_to_uid(user):
    '''
    Convert user name to a uid
    '''
    if user is None or user == '':
        return ''

    try:
        sid, domain, account_type = win32security.LookupAccountName(None, user)
    except pywinerror as exc:
        # if user does not exist...
        # 1332 = No mapping between account names and security IDs was carried
        # out.
        if exc.winerror == 1332:
            return ''
        else:
            raise

    return win32security.ConvertSidToStringSid(sid)


def get_uid(path, follow_symlinks=True):
    '''
    Return the id of the user that owns a given file

    Symlinks are followed by default to mimic Unix behavior. Specify
    `follow_symlinks=False` to turn off this behavior.

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_uid c:\\temp\\test.txt
        salt '*' file.get_uid c:\\temp\\test.txt follow_symlinks=False
    '''
    if not os.path.exists(path):
        return False

    # Under Windows, if the path is a symlink, the user that owns the symlink is
    # returned, not the user that owns the file/directory the symlink is
    # pointing to. This behavior is *different* to *nix, therefore the symlink
    # is first resolved manually if necessary. Remember symlinks are only
    # supported on Windows Vista or later.
    if follow_symlinks and sys.getwindowsversion().major >= 6:
        path = _resolve_symlink(path)
    try:
        secdesc = win32security.GetFileSecurity(
            path, win32security.OWNER_SECURITY_INFORMATION
        )
    except MemoryError:
        # generic memory error (win2k3+)
        return 'S-1-1-0'
    except pywinerror as exc:
        # Incorrect function error (win2k8+)
        if exc.winerror == 1 or exc.winerror == 50:
            return 'S-1-1-0'
        raise
    owner_sid = secdesc.GetSecurityDescriptorOwner()
    return win32security.ConvertSidToStringSid(owner_sid)


def get_user(path, follow_symlinks=True):
    '''
    Return the user that owns a given file

    Symlinks are followed by default to mimic Unix behavior. Specify
    `follow_symlinks=False` to turn off this behavior.

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_user c:\\temp\\test.txt
        salt '*' file.get_user c:\\temp\\test.txt follow_symlinks=False
    '''
    return uid_to_user(get_uid(path, follow_symlinks))


def get_mode(path):
    '''
    Return the mode of a file

    Right now we're just returning None because Windows' doesn't have a mode
    like Linux

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_mode /etc/passwd
    '''
    if not os.path.exists(path):
        return ''

    func_name = '{0}.get_mode'.format(__virtualname__)
    if __opts__.get('fun', '') == func_name:
        log.info('The function {0} should not be used on Windows systems; '
                 'see function docs for details. The value returned is '
                 'always None.'.format(func_name))

    return None


def lchown(path, user, group=None, pgroup=None):
    '''
    Chown a file, pass the file the desired user and group without following any
    symlinks.

    Under Windows, the group parameter will be ignored.

    This is because while files in Windows do have a 'primary group'
    property, this is rarely used.  It generally has no bearing on
    permissions unless intentionally configured and is most commonly used to
    provide Unix compatibility (e.g. Services For Unix, NFS services).

    If you do want to change the 'primary group' property and understand the
    implications, pass the Windows only parameter, pgroup, instead.

    To set the primary group to 'None', it must be specified in quotes.
    Otherwise Salt will interpret it as the Python value of None and no primary
    group changes will occur. See the example below.

    CLI Example:

    .. code-block:: bash

        salt '*' file.lchown c:\\temp\\test.txt myusername
        salt '*' file.lchown c:\\temp\\test.txt myusername pgroup=Administrators
        salt '*' file.lchown c:\\temp\\test.txt myusername "pgroup='None'"
    '''
    if group:
        func_name = '{0}.lchown'.format(__virtualname__)
        if __opts__.get('fun', '') == func_name:
            log.info('The group parameter has no effect when using {0} on Windows '
                     'systems; see function docs for details.'.format(func_name))
        log.debug(
            'win_file.py {0} Ignoring the group parameter for {1}'.format(
                func_name, path
            )
        )
        group = None

    return chown(path, user, group, pgroup, follow_symlinks=False)


def chown(path, user, group=None, pgroup=None, follow_symlinks=True):
    '''
    Chown a file, pass the file the desired user and group

    Under Windows, the group parameter will be ignored.

    This is because while files in Windows do have a 'primary group'
    property, this is rarely used.  It generally has no bearing on
    permissions unless intentionally configured and is most commonly used to
    provide Unix compatibility (e.g. Services For Unix, NFS services).

    If you do want to change the 'primary group' property and understand the
    implications, pass the Windows only parameter, pgroup, instead.

    To set the primary group to 'None', it must be specified in quotes.
    Otherwise Salt will interpret it as the Python value of None and no primary
    group changes will occur. See the example below.

    CLI Example:

    .. code-block:: bash

        salt '*' file.chown c:\\temp\\test.txt myusername
        salt '*' file.chown c:\\temp\\test.txt myusername pgroup=Administrators
        salt '*' file.chown c:\\temp\\test.txt myusername "pgroup='None'"
    '''
    # the group parameter is not used; only provided for API compatibility
    if group:
        func_name = '{0}.chown'.format(__virtualname__)
        if __opts__.get('fun', '') == func_name:
            log.info('The group parameter has no effect when using {0} on Windows '
                     'systems; see function docs for details.'.format(func_name))
        log.debug(
            'win_file.py {0} Ignoring the group parameter for {1}'.format(
                func_name, path
            )
        )
        group = None

    err = ''
    # get SID object for user
    try:
        userSID, domainName, objectType = win32security.LookupAccountName(None, user)
    except pywinerror:
        err += 'User does not exist\n'

    if pgroup:
        # get SID object for group
        try:
            groupSID, domainName, objectType = win32security.LookupAccountName(None, pgroup)
        except pywinerror:
            err += 'Group does not exist\n'
    else:
        groupSID = None

    if not os.path.exists(path):
        err += 'File not found'
    if err:
        return err

    if follow_symlinks and sys.getwindowsversion().major >= 6:
        path = _resolve_symlink(path)

    privilege_enabled = False
    try:
        privilege_enabled = _enable_privilege(win32security.SE_RESTORE_NAME)
        if pgroup:
            # set owner and group
            win32security.SetNamedSecurityInfo(
                path,
                win32security.SE_FILE_OBJECT,
                win32security.OWNER_SECURITY_INFORMATION + win32security.GROUP_SECURITY_INFORMATION,
                userSID,
                groupSID,
                None,
                None
            )
        else:
            # set owner only
            win32security.SetNamedSecurityInfo(
                path,
                win32security.SE_FILE_OBJECT,
                win32security.OWNER_SECURITY_INFORMATION,
                userSID,
                None,
                None,
                None
            )
    finally:
        if privilege_enabled:
            _disable_privilege(win32security.SE_RESTORE_NAME)

    return None


def chpgrp(path, group):
    '''
    Change the group of a file

    Under Windows, this will set the rarely used primary group of a file.
    This generally has no bearing on permissions unless intentionally
    configured and is most commonly used to provide Unix compatibility (e.g.
    Services For Unix, NFS services).

    Ensure you know what you are doing before using this function.

    To set the primary group to 'None', it must be specified in quotes.
    Otherwise Salt will interpret it as the Python value of None and no primary
    group changes will occur. See the example below.

    CLI Example:

    .. code-block:: bash

        salt '*' file.chpgrp c:\\temp\\test.txt Administrators
        salt '*' file.chpgrp c:\\temp\\test.txt "'None'"
    '''
    if group is None:
        raise SaltInvocationError("The group value was specified as None and "
                                  "is invalid. If you mean the built-in None "
                                  "group, specify the group in lowercase, e.g. "
                                  "'none'.")

    err = ''
    # get SID object for group
    try:
        groupSID, domainName, objectType = win32security.LookupAccountName(None, group)
    except pywinerror:
        err += 'Group does not exist\n'

    if not os.path.exists(path):
        err += 'File not found\n'
    if err:
        return err

    # set group
    privilege_enabled = False
    try:
        privilege_enabled = _enable_privilege(win32security.SE_RESTORE_NAME)
        win32security.SetNamedSecurityInfo(
            path,
            win32security.SE_FILE_OBJECT,
            win32security.GROUP_SECURITY_INFORMATION,
            None,
            groupSID,
            None,
            None
        )
    finally:
        if privilege_enabled:
            _disable_privilege(win32security.SE_RESTORE_NAME)

    return None


def chgrp(path, group):
    '''
    Change the group of a file

    Under Windows, this will do nothing.

    While a file in Windows does have a 'primary group', this rarely used
    attribute generally has no bearing on permissions unless intentionally
    configured and is only used to support Unix compatibility features (e.g.
    Services For Unix, NFS services).

    Salt, therefore, remaps this function to do nothing while still being
    compatible with Unix behavior. When managing Windows systems,
    this function is superfluous and will generate an info level log entry if
    used directly.

    If you do actually want to set the 'primary group' of a file, use `file
    .chpgrp`.

    CLI Example:

    .. code-block:: bash

        salt '*' file.chpgrp c:\\temp\\test.txt administrators
    '''
    func_name = '{0}.chgrp'.format(__virtualname__)
    if __opts__.get('fun', '') == func_name:
        log.info('The function {0} should not be used on Windows systems; see '
                 'function docs for details.'.format(func_name))
    log.debug('win_file.py {0} Doing nothing for {1}'.format(func_name, path))

    return None


def stats(path, hash_type='sha256', follow_symlinks=True):
    '''
    Return a dict containing the stats for a given file

    Under Windows, `gid` will equal `uid` and `group` will equal `user`.

    While a file in Windows does have a 'primary group', this rarely used
    attribute generally has no bearing on permissions unless intentionally
    configured and is only used to support Unix compatibility features (e.g.
    Services For Unix, NFS services).

    Salt, therefore, remaps these properties to keep some kind of
    compatibility with Unix behavior. If the 'primary group' is required, it
    can be accessed in the `pgroup` and `pgid` properties.

    CLI Example:

    .. code-block:: bash

        salt '*' file.stats /etc/passwd
    '''
    ret = {}
    if not os.path.exists(path):
        return ret
    if follow_symlinks and sys.getwindowsversion().major >= 6:
        path = _resolve_symlink(path)
    pstat = os.stat(path)
    ret['inode'] = pstat.st_ino
    # don't need to resolve symlinks again because we've already done that
    ret['uid'] = get_uid(path, follow_symlinks=False)
    # maintain the illusion that group is the same as user as states need this
    ret['gid'] = ret['uid']
    ret['user'] = uid_to_user(ret['uid'])
    ret['group'] = ret['user']
    ret['pgid'] = get_pgid(path, follow_symlinks)
    ret['pgroup'] = gid_to_group(ret['pgid'])
    ret['atime'] = pstat.st_atime
    ret['mtime'] = pstat.st_mtime
    ret['ctime'] = pstat.st_ctime
    ret['size'] = pstat.st_size
    ret['mode'] = str(oct(stat.S_IMODE(pstat.st_mode)))
    if hash_type:
        ret['sum'] = get_sum(path, hash_type)
    ret['type'] = 'file'
    if stat.S_ISDIR(pstat.st_mode):
        ret['type'] = 'dir'
    if stat.S_ISCHR(pstat.st_mode):
        ret['type'] = 'char'
    if stat.S_ISBLK(pstat.st_mode):
        ret['type'] = 'block'
    if stat.S_ISREG(pstat.st_mode):
        ret['type'] = 'file'
    if stat.S_ISLNK(pstat.st_mode):
        ret['type'] = 'link'
    if stat.S_ISFIFO(pstat.st_mode):
        ret['type'] = 'pipe'
    if stat.S_ISSOCK(pstat.st_mode):
        ret['type'] = 'socket'
    ret['target'] = os.path.realpath(path)
    return ret


def get_attributes(path):
    '''
    Return a dictionary object with the Windows
    file attributes for a file.

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_attributes c:\\temp\\a.txt
    '''
    err = ''
    if not os.path.exists(path):
        err += 'File not found\n'
    if err:
        return err

    # set up dictionary for attribute values
    attributes = {}

    # Get cumulative int value of attributes
    intAttributes = win32file.GetFileAttributes(path)

    # Assign individual attributes
    attributes['archive'] = (intAttributes & 32) == 32
    attributes['reparsePoint'] = (intAttributes & 1024) == 1024
    attributes['compressed'] = (intAttributes & 2048) == 2048
    attributes['directory'] = (intAttributes & 16) == 16
    attributes['encrypted'] = (intAttributes & 16384) == 16384
    attributes['hidden'] = (intAttributes & 2) == 2
    attributes['normal'] = (intAttributes & 128) == 128
    attributes['notIndexed'] = (intAttributes & 8192) == 8192
    attributes['offline'] = (intAttributes & 4096) == 4096
    attributes['readonly'] = (intAttributes & 1) == 1
    attributes['system'] = (intAttributes & 4) == 4
    attributes['temporary'] = (intAttributes & 256) == 256

    # check if it's a Mounted Volume
    attributes['mountedVolume'] = False
    if attributes['reparsePoint'] is True and attributes['directory'] is True:
        fileIterator = win32file.FindFilesIterator(path)
        findDataTuple = next(fileIterator)
        if findDataTuple[6] == 0xA0000003:
            attributes['mountedVolume'] = True
    # check if it's a soft (symbolic) link

    # Note:  os.path.islink() does not work in
    #   Python 2.7 for the Windows NTFS file system.
    #   The following code does, however, work (tested in Windows 8)

    attributes['symbolicLink'] = False
    if attributes['reparsePoint'] is True:
        fileIterator = win32file.FindFilesIterator(path)
        findDataTuple = next(fileIterator)
        if findDataTuple[6] == 0xA000000C:
            attributes['symbolicLink'] = True

    return attributes


def set_attributes(path, archive=None, hidden=None, normal=None,
                   notIndexed=None, readonly=None, system=None, temporary=None):
    '''
    Set file attributes for a file.  Note that the normal attribute
    means that all others are false.  So setting it will clear all others.

    CLI Example:

    .. code-block:: bash

        salt '*' file.set_attributes c:\\temp\\a.txt normal=True
        salt '*' file.set_attributes c:\\temp\\a.txt readonly=True hidden=True
    '''
    err = ''
    if not os.path.exists(path):
        err += 'File not found\n'
    if normal:
        if archive or hidden or notIndexed or readonly or system or temporary:
            err += 'Normal attribute may not be used with any other attributes\n'
        else:
            return win32file.SetFileAttributes(path, 128)
    if err:
        return err
    # Get current attributes
    intAttributes = win32file.GetFileAttributes(path)
    # individually set or clear bits for appropriate attributes
    if archive is not None:
        if archive:
            intAttributes |= 0x20
        else:
            intAttributes &= 0xFFDF
    if hidden is not None:
        if hidden:
            intAttributes |= 0x2
        else:
            intAttributes &= 0xFFFD
    if notIndexed is not None:
        if notIndexed:
            intAttributes |= 0x2000
        else:
            intAttributes &= 0xDFFF
    if readonly is not None:
        if readonly:
            intAttributes |= 0x1
        else:
            intAttributes &= 0xFFFE
    if system is not None:
        if system:
            intAttributes |= 0x4
        else:
            intAttributes &= 0xFFFB
    if temporary is not None:
        if temporary:
            intAttributes |= 0x100
        else:
            intAttributes &= 0xFEFF
    return win32file.SetFileAttributes(path, intAttributes)


def set_mode(path, mode):
    '''
    Set the mode of a file

    This just calls get_mode, which returns None because we don't use mode on
    Windows

    CLI Example:

    .. code-block:: bash

        salt '*' file.set_mode /etc/passwd 0644
    '''
    func_name = '{0}.set_mode'.format(__virtualname__)
    if __opts__.get('fun', '') == func_name:
        log.info('The function {0} should not be used on Windows systems; '
                 'see function docs for details. The value returned is '
                 'always None.'.format(func_name))

    return get_mode(path)


def remove(path, force=False):
    '''
    Remove the named file or directory

    :param str path: The path to the file or directory to remove.

    :param bool force: Remove even if marked Read-Only

    :return: True if successful, False if unsuccessful
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' file.remove C:\\Temp
    '''
    # This must be a recursive function in windows to properly deal with
    # Symlinks. The shutil.rmtree function will remove the contents of
    # the Symlink source in windows.

    path = os.path.expanduser(path)

    # Does the file/folder exists
    if not os.path.exists(path):
        return 'File/Folder not found: {0}'.format(path)

    if not os.path.isabs(path):
        raise SaltInvocationError('File path must be absolute.')

    # Remove ReadOnly Attribute
    if force:
        # Get current file attributes
        file_attributes = win32api.GetFileAttributes(path)
        win32api.SetFileAttributes(path, win32con.FILE_ATTRIBUTE_NORMAL)

    try:
        if os.path.isfile(path):
            # A file and a symlinked file are removed the same way
            os.remove(path)
        elif is_link(path):
            # If it's a symlink directory, use the rmdir command
            os.rmdir(path)
        else:
            for name in os.listdir(path):
                item = '{0}\\{1}'.format(path, name)
                # If it's a normal directory, recurse to remove it's contents
                remove(item, force)

            # rmdir will work now because the directory is empty
            os.rmdir(path)
    except (OSError, IOError) as exc:
        if force:
            # Reset attributes to the original if delete fails.
            win32api.SetFileAttributes(path, file_attributes)
        raise CommandExecutionError(
            'Could not remove \'{0}\': {1}'.format(path, exc)
        )

    return True


def symlink(src, link):
    '''
    Create a symbolic link to a file

    This is only supported with Windows Vista or later and must be executed by
    a user with the SeCreateSymbolicLink privilege.

    The behavior of this function matches the Unix equivalent, with one
    exception - invalid symlinks cannot be created. The source path must exist.
    If it doesn't, an error will be raised.

    CLI Example:

    .. code-block:: bash

        salt '*' file.symlink /path/to/file /path/to/link
    '''
    # When Python 3.2 or later becomes the minimum version, this function can be
    # replaced with the built-in os.symlink function, which supports Windows.
    if sys.getwindowsversion().major < 6:
        raise SaltInvocationError('Symlinks are only supported on Windows Vista or later.')

    if not os.path.exists(src):
        raise SaltInvocationError('The given source path does not exist.')

    if not os.path.isabs(src):
        raise SaltInvocationError('File path must be absolute.')

    # ensure paths are using the right slashes
    src = os.path.normpath(src)
    link = os.path.normpath(link)

    is_dir = os.path.isdir(src)

    try:
        win32file.CreateSymbolicLink(link, src, int(is_dir))
        return True
    except pywinerror as exc:
        raise CommandExecutionError(
            'Could not create \'{0}\' - [{1}] {2}'.format(
                link,
                exc.winerror,
                exc.strerror
            )
        )


def _is_reparse_point(path):
    '''
    Returns True if path is a reparse point; False otherwise.
    '''
    if sys.getwindowsversion().major < 6:
        raise SaltInvocationError('Symlinks are only supported on Windows Vista or later.')

    result = win32file.GetFileAttributesW(path)

    if result == -1:
        raise SaltInvocationError('The path given is not valid, symlink or not. (does it exist?)')

    if result & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
        return True
    else:
        return False


def is_link(path):
    '''
    Check if the path is a symlink

    This is only supported on Windows Vista or later.

    Inline with Unix behavior, this function will raise an error if the path
    is not a symlink, however, the error raised will be a SaltInvocationError,
    not an OSError.

    CLI Example:

    .. code-block:: bash

       salt '*' file.is_link /path/to/link
    '''
    if sys.getwindowsversion().major < 6:
        return False

    try:
        if not _is_reparse_point(path):
            return False
    except SaltInvocationError:
        return False

    # check that it is a symlink reparse point (in case it is something else,
    # like a mount point)
    reparse_data = _get_reparse_data(path)

    # sanity check - this should not happen
    if not reparse_data:
        # not a reparse point
        return False

    # REPARSE_DATA_BUFFER structure - see
    # http://msdn.microsoft.com/en-us/library/ff552012.aspx

    # parse the structure header to work out which type of reparse point this is
    header_parser = struct.Struct('L')
    ReparseTag, = header_parser.unpack(reparse_data[:header_parser.size])
    # http://msdn.microsoft.com/en-us/library/windows/desktop/aa365511.aspx
    if not ReparseTag & 0xA000FFFF == 0xA000000C:
        return False
    else:
        return True


def _get_reparse_data(path):
    '''
    Retrieves the reparse point data structure for the given path.

    If the path is not a reparse point, None is returned.

    See http://msdn.microsoft.com/en-us/library/ff552012.aspx for details on the
    REPARSE_DATA_BUFFER structure returned.
    '''
    if sys.getwindowsversion().major < 6:
        raise SaltInvocationError('Symlinks are only supported on Windows Vista or later.')

    # ensure paths are using the right slashes
    path = os.path.normpath(path)

    if not _is_reparse_point(path):
        return None

    fileHandle = None
    try:
        fileHandle = win32file.CreateFileW(
            path,
            0x80000000,  # GENERIC_READ
            1,  # share with other readers
            None,  # no inherit, default security descriptor
            3,  # OPEN_EXISTING
            0x00200000 | 0x02000000  # FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS
        )

        reparseData = win32file.DeviceIoControl(
            fileHandle,
            0x900a8,  # FSCTL_GET_REPARSE_POINT
            None,  # in buffer
            16384  # out buffer size (MAXIMUM_REPARSE_DATA_BUFFER_SIZE)
        )

    finally:
        if fileHandle:
            win32file.CloseHandle(fileHandle)

    return reparseData


def readlink(path):
    '''
    Return the path that a symlink points to

    This is only supported on Windows Vista or later.

    Inline with Unix behavior, this function will raise an error if the path is
    not a symlink, however, the error raised will be a SaltInvocationError, not
    an OSError.

    CLI Example:

    .. code-block:: bash

        salt '*' file.readlink /path/to/link
    '''
    if sys.getwindowsversion().major < 6:
        raise SaltInvocationError('Symlinks are only supported on Windows Vista or later.')

    if not os.path.isabs(path):
        raise SaltInvocationError('Path to link must be absolute.')

    reparse_data = _get_reparse_data(path)

    if not reparse_data:
        raise SaltInvocationError('The path specified is not a reparse point (symlinks are a type of reparse point).')

    # REPARSE_DATA_BUFFER structure - see
    # http://msdn.microsoft.com/en-us/library/ff552012.aspx

    # parse the structure header to work out which type of reparse point this is
    header_parser = struct.Struct('L')
    ReparseTag, = header_parser.unpack(reparse_data[:header_parser.size])
    # http://msdn.microsoft.com/en-us/library/windows/desktop/aa365511.aspx
    if not ReparseTag & 0xA000FFFF == 0xA000000C:
        raise SaltInvocationError('The path specified is not a symlink, but another type of reparse point (0x{0:X}).'.format(ReparseTag))

    # parse as a symlink reparse point structure (the structure for other
    # reparse points is different)
    data_parser = struct.Struct('LHHHHHHL')
    ReparseTag, ReparseDataLength, Reserved, SubstituteNameOffset, \
    SubstituteNameLength, PrintNameOffset, \
    PrintNameLength, Flags = data_parser.unpack(reparse_data[:data_parser.size])

    path_buffer_offset = data_parser.size
    absolute_substitute_name_offset = path_buffer_offset + SubstituteNameOffset
    target_bytes = reparse_data[absolute_substitute_name_offset:absolute_substitute_name_offset+SubstituteNameLength]
    target = target_bytes.decode('UTF-16')

    if target.startswith('\\??\\'):
        target = target[4:]

    try:
        # comes out in 8.3 form; convert it to LFN to make it look nicer
        target = win32file.GetLongPathName(target)
    except pywinerror as exc:
        # if file is not found (i.e. bad symlink), return it anyway like on *nix
        if exc.winerror == 2:
            return target
        raise

    return target
