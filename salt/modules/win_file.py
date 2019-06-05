# -*- coding: utf-8 -*-
'''
Manage information about files on the minion, set/read user, group
data, modify the ACL of files/directories

:depends:   - win32api
            - win32file
            - win32con
            - salt.utils.win_dacl
'''
from __future__ import absolute_import, unicode_literals, print_function

# Import python libs
import os
import stat
import os.path
import logging
# pylint: disable=W0611
import operator  # do not remove
from collections import Iterable, Mapping  # do not remove
from functools import reduce  # do not remove
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
import io  # do not remove, used in imported file.py functions
import fnmatch  # do not remove, used in imported file.py functions
import mmap  # do not remove, used in imported file.py functions
import glob  # do not remove, used in imported file.py functions
# do not remove, used in imported file.py functions
from salt.ext import six
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse  # pylint: disable=import-error,no-name-in-module
import salt.utils.atomicfile  # do not remove, used in imported file.py functions
from salt.exceptions import CommandExecutionError, SaltInvocationError
# pylint: enable=W0611

# Import salt libs
import salt.utils.path
import salt.utils.platform
import salt.utils.user
from salt.modules.file import (check_hash,  # pylint: disable=W0611
        directory_exists, get_managed,
        check_managed, check_managed_changes, source_list,
        touch, append, contains, contains_regex, get_source_sum,
        contains_glob, find, psed, get_sum, _get_bkroot, _mkstemp_copy,
        get_hash, manage_file, file_exists, get_diff, line, list_backups,
        __clean_tmp, check_file_meta, _binary_replace,
        _splitlines_preserving_trailing_newline, restore_backup,
        access, copy, readdir, read, rmdir, truncate, replace, delete_backup,
        search, _get_flags, extract_hash, _error, _sed_esc, _psed,
        RE_FLAG_TABLE, blockreplace, prepend, seek_read, seek_write, rename,
        lstat, path_exists_glob, write, pardir, join, HASHES, HASHES_REVMAP,
        comment, uncomment, _add_flags, comment_line, _regex_to_static,
        _set_line_indent, apply_template_on_contents, dirname, basename,
        list_backups_dir, _assert_occurrence, _starts_till, _set_line_eol, _get_eol,
        _insert_line_after, _insert_line_before)
from salt.modules.file import normpath as normpath_

from salt.utils.functools import namespaced_function as _namespaced_function

HAS_WINDOWS_MODULES = False
try:
    if salt.utils.platform.is_windows():
        import win32api
        import win32file
        import win32con
        from pywintypes import error as pywinerror
        HAS_WINDOWS_MODULES = True
except ImportError:
    HAS_WINDOWS_MODULES = False

# This is to fix the pylint error: E0602: Undefined variable "WindowsError"
try:
    from exceptions import WindowsError
except ImportError:
    class WindowsError(OSError):
        pass

HAS_WIN_DACL = False
try:
    if salt.utils.platform.is_windows():
        import salt.utils.win_dacl
        HAS_WIN_DACL = True
except ImportError:
    HAS_WIN_DACL = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'file'


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.platform.is_windows():
        if HAS_WINDOWS_MODULES:
            # Load functions from file.py
            global get_managed, manage_file
            global source_list, __clean_tmp, file_exists
            global check_managed, check_managed_changes, check_file_meta
            global append, _error, directory_exists, touch, contains
            global contains_regex, contains_glob, get_source_sum
            global find, psed, get_sum, check_hash, get_hash, delete_backup
            global get_diff, line, _get_flags, extract_hash, comment_line
            global access, copy, readdir, read, rmdir, truncate, replace, search
            global _binary_replace, _get_bkroot, list_backups, restore_backup
            global _splitlines_preserving_trailing_newline
            global blockreplace, prepend, seek_read, seek_write, rename, lstat
            global write, pardir, join, _add_flags, apply_template_on_contents
            global path_exists_glob, comment, uncomment, _mkstemp_copy
            global _regex_to_static, _set_line_indent, dirname, basename
            global list_backups_dir, normpath_, _assert_occurrence, _starts_till
            global _insert_line_before, _insert_line_after, _set_line_eol, _get_eol

            replace = _namespaced_function(replace, globals())
            search = _namespaced_function(search, globals())
            _get_flags = _namespaced_function(_get_flags, globals())
            _binary_replace = _namespaced_function(_binary_replace, globals())
            _splitlines_preserving_trailing_newline = _namespaced_function(
                _splitlines_preserving_trailing_newline, globals())
            _error = _namespaced_function(_error, globals())
            _get_bkroot = _namespaced_function(_get_bkroot, globals())
            list_backups = _namespaced_function(list_backups, globals())
            restore_backup = _namespaced_function(restore_backup, globals())
            delete_backup = _namespaced_function(delete_backup, globals())
            extract_hash = _namespaced_function(extract_hash, globals())
            append = _namespaced_function(append, globals())
            get_managed = _namespaced_function(get_managed, globals())
            check_managed = _namespaced_function(check_managed, globals())
            check_managed_changes = _namespaced_function(check_managed_changes, globals())
            check_file_meta = _namespaced_function(check_file_meta, globals())
            manage_file = _namespaced_function(manage_file, globals())
            source_list = _namespaced_function(source_list, globals())
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
            line = _namespaced_function(line, globals())
            access = _namespaced_function(access, globals())
            copy = _namespaced_function(copy, globals())
            readdir = _namespaced_function(readdir, globals())
            read = _namespaced_function(read, globals())
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
            _regex_to_static = _namespaced_function(_regex_to_static, globals())
            _set_line_indent = _namespaced_function(_set_line_indent, globals())
            _set_line_eol = _namespaced_function(_set_line_eol, globals())
            _get_eol = _namespaced_function(_get_eol, globals())
            _insert_line_after = _namespaced_function(_insert_line_after, globals())
            _insert_line_before = _namespaced_function(_insert_line_before, globals())
            _mkstemp_copy = _namespaced_function(_mkstemp_copy, globals())
            _add_flags = _namespaced_function(_add_flags, globals())
            apply_template_on_contents = _namespaced_function(apply_template_on_contents, globals())
            dirname = _namespaced_function(dirname, globals())
            basename = _namespaced_function(basename, globals())
            list_backups_dir = _namespaced_function(list_backups_dir, globals())
            normpath_ = _namespaced_function(normpath_, globals())
            _assert_occurrence = _namespaced_function(_assert_occurrence, globals())
            _starts_till = _namespaced_function(_starts_till, globals())

        else:
            return False, 'Module win_file: Missing Win32 modules'

    if not HAS_WIN_DACL:
        return False, 'Module win_file: Unable to load salt.utils.win_dacl'

    return __virtualname__


__outputter__ = {
    'touch': 'txt',
    'append': 'txt',
}

__func_alias__ = {
    'makedirs_': 'makedirs',
    'normpath_': 'normpath',
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


def gid_to_group(gid):
    '''
    Convert the group id to the group name on this system

    Under Windows, because groups are just another ACL entity, this function
    behaves the same as uid_to_user.

    For maintaining Windows systems, this function is superfluous and only
    exists for API compatibility with Unix. Use the uid_to_user function
    instead; an info level log entry will be generated if this function is used
    directly.

    Args:
        gid (str): The gid of the group

    Returns:
        str: The name of the group

    CLI Example:

    .. code-block:: bash

        salt '*' file.gid_to_group S-1-5-21-626487655-2533044672-482107328-1010
    '''
    func_name = '{0}.gid_to_group'.format(__virtualname__)
    if __opts__.get('fun', '') == func_name:
        log.info('The function %s should not be used on Windows systems; '
                 'see function docs for details.', func_name)

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

    Args:
        group (str): The name of the group

    Returns:
        str: The gid of the group

    CLI Example:

    .. code-block:: bash

        salt '*' file.group_to_gid administrators
    '''
    func_name = '{0}.group_to_gid'.format(__virtualname__)
    if __opts__.get('fun', '') == func_name:
        log.info('The function %s should not be used on Windows systems; '
                 'see function docs for details.', func_name)

    if group is None:
        return ''

    return salt.utils.win_dacl.get_sid_string(group)


def get_pgid(path, follow_symlinks=True):
    '''
    Return the id of the primary group that owns a given file (Windows only)

    This function will return the rarely used primary group of a file. This
    generally has no bearing on permissions unless intentionally configured
    and is most commonly used to provide Unix compatibility (e.g. Services
    For Unix, NFS services).

    Ensure you know what you are doing before using this function.

    Args:
        path (str): The path to the file or directory

        follow_symlinks (bool):
            If the object specified by ``path`` is a symlink, get attributes of
            the linked file instead of the symlink itself. Default is True

    Returns:
        str: The gid of the primary group

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_pgid c:\\temp\\test.txt
    '''
    if not os.path.exists(path):
        raise CommandExecutionError('Path not found: {0}'.format(path))

    # Under Windows, if the path is a symlink, the user that owns the symlink is
    # returned, not the user that owns the file/directory the symlink is
    # pointing to. This behavior is *different* to *nix, therefore the symlink
    # is first resolved manually if necessary. Remember symlinks are only
    # supported on Windows Vista or later.
    if follow_symlinks and sys.getwindowsversion().major >= 6:
        path = _resolve_symlink(path)

    group_name = salt.utils.win_dacl.get_primary_group(path)
    return salt.utils.win_dacl.get_sid_string(group_name)


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

    Args:
        path (str): The path to the file or directory

        follow_symlinks (bool):
            If the object specified by ``path`` is a symlink, get attributes of
            the linked file instead of the symlink itself. Default is True

    Returns:
        str: The name of the primary group

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

    Args:
        path (str): The path to the file or directory

        follow_symlinks (bool):
            If the object specified by ``path`` is a symlink, get attributes of
            the linked file instead of the symlink itself. Default is True

    Returns:
        str: The gid of the owner

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_gid c:\\temp\\test.txt
    '''
    func_name = '{0}.get_gid'.format(__virtualname__)
    if __opts__.get('fun', '') == func_name:
        log.info('The function %s should not be used on Windows systems; '
                 'see function docs for details. The value returned is the '
                 'uid.', func_name)

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

    Args:
        path (str): The path to the file or directory

        follow_symlinks (bool):
            If the object specified by ``path`` is a symlink, get attributes of
            the linked file instead of the symlink itself. Default is True

    Returns:
        str: The name of the owner

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_group c:\\temp\\test.txt
    '''
    func_name = '{0}.get_group'.format(__virtualname__)
    if __opts__.get('fun', '') == func_name:
        log.info('The function %s should not be used on Windows systems; '
                 'see function docs for details. The value returned is the '
                 'user (owner).', func_name)

    return get_user(path, follow_symlinks)


def uid_to_user(uid):
    '''
    Convert a uid to a user name

    Args:
        uid (str): The user id to lookup

    Returns:
        str: The name of the user

    CLI Example:

    .. code-block:: bash

        salt '*' file.uid_to_user S-1-5-21-626487655-2533044672-482107328-1010
    '''
    if uid is None or uid == '':
        return ''

    return salt.utils.win_dacl.get_name(uid)


def user_to_uid(user):
    '''
    Convert user name to a uid

    Args:
        user (str): The user to lookup

    Returns:
        str: The user id of the user

    CLI Example:

    .. code-block:: bash

        salt '*' file.user_to_uid myusername
    '''
    if user is None:
        user = salt.utils.user.get_user()

    return salt.utils.win_dacl.get_sid_string(user)


def get_uid(path, follow_symlinks=True):
    '''
    Return the id of the user that owns a given file

    Symlinks are followed by default to mimic Unix behavior. Specify
    `follow_symlinks=False` to turn off this behavior.

    Args:
        path (str): The path to the file or directory

        follow_symlinks (bool):
            If the object specified by ``path`` is a symlink, get attributes of
            the linked file instead of the symlink itself. Default is True

    Returns:
        str: The uid of the owner


    CLI Example:

    .. code-block:: bash

        salt '*' file.get_uid c:\\temp\\test.txt
        salt '*' file.get_uid c:\\temp\\test.txt follow_symlinks=False
    '''
    if not os.path.exists(path):
        raise CommandExecutionError('Path not found: {0}'.format(path))

    # Under Windows, if the path is a symlink, the user that owns the symlink is
    # returned, not the user that owns the file/directory the symlink is
    # pointing to. This behavior is *different* to *nix, therefore the symlink
    # is first resolved manually if necessary. Remember symlinks are only
    # supported on Windows Vista or later.
    if follow_symlinks and sys.getwindowsversion().major >= 6:
        path = _resolve_symlink(path)

    owner_sid = salt.utils.win_dacl.get_owner(path)
    return salt.utils.win_dacl.get_sid_string(owner_sid)


def get_user(path, follow_symlinks=True):
    '''
    Return the user that owns a given file

    Symlinks are followed by default to mimic Unix behavior. Specify
    `follow_symlinks=False` to turn off this behavior.

    Args:
        path (str): The path to the file or directory

        follow_symlinks (bool):
            If the object specified by ``path`` is a symlink, get attributes of
            the linked file instead of the symlink itself. Default is True

    Returns:
        str: The name of the owner


    CLI Example:

    .. code-block:: bash

        salt '*' file.get_user c:\\temp\\test.txt
        salt '*' file.get_user c:\\temp\\test.txt follow_symlinks=False
    '''
    if not os.path.exists(path):
        raise CommandExecutionError('Path not found: {0}'.format(path))

    # Under Windows, if the path is a symlink, the user that owns the symlink is
    # returned, not the user that owns the file/directory the symlink is
    # pointing to. This behavior is *different* to *nix, therefore the symlink
    # is first resolved manually if necessary. Remember symlinks are only
    # supported on Windows Vista or later.
    if follow_symlinks and sys.getwindowsversion().major >= 6:
        path = _resolve_symlink(path)

    return salt.utils.win_dacl.get_owner(path)


def get_mode(path):
    '''
    Return the mode of a file

    Right now we're just returning None because Windows' doesn't have a mode
    like Linux

    Args:
        path (str): The path to the file or directory

    Returns:
        None

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_mode /etc/passwd
    '''
    if not os.path.exists(path):
        raise CommandExecutionError('Path not found: {0}'.format(path))

    func_name = '{0}.get_mode'.format(__virtualname__)
    if __opts__.get('fun', '') == func_name:
        log.info('The function %s should not be used on Windows systems; '
                 'see function docs for details. The value returned is '
                 'always None.', func_name)

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

    Args:
        path (str): The path to the file or directory
        user (str): The name of the user to own the file
        group (str): The group (not used)
        pgroup (str): The primary group to assign

    Returns:
        bool: True if successful, otherwise error

    CLI Example:

    .. code-block:: bash

        salt '*' file.lchown c:\\temp\\test.txt myusername
        salt '*' file.lchown c:\\temp\\test.txt myusername pgroup=Administrators
        salt '*' file.lchown c:\\temp\\test.txt myusername "pgroup='None'"
    '''
    if group:
        func_name = '{0}.lchown'.format(__virtualname__)
        if __opts__.get('fun', '') == func_name:
            log.info('The group parameter has no effect when using %s on '
                     'Windows systems; see function docs for details.',
                     func_name)
        log.debug('win_file.py %s Ignoring the group parameter for %s',
                  func_name, path)
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

    Args:
        path (str): The path to the file or directory
        user (str): The name of the user to own the file
        group (str): The group (not used)
        pgroup (str): The primary group to assign
        follow_symlinks (bool):
            If the object specified by ``path`` is a symlink, get attributes of
            the linked file instead of the symlink itself. Default is True

    Returns:
        bool: True if successful, otherwise error

    CLI Example:

    .. code-block:: bash

        salt '*' file.chown c:\\temp\\test.txt myusername
        salt '*' file.chown c:\\temp\\test.txt myusername pgroup=Administrators
        salt '*' file.chown c:\\temp\\test.txt myusername "pgroup='None'"
    '''
    # the group parameter is not used; only provided for API compatibility
    if group is not None:
        func_name = '{0}.chown'.format(__virtualname__)
        if __opts__.get('fun', '') == func_name:
            log.info('The group parameter has no effect when using %s on '
                     'Windows systems; see function docs for details.',
                     func_name)
        log.debug('win_file.py %s Ignoring the group parameter for %s',
                  func_name, path)

    if follow_symlinks and sys.getwindowsversion().major >= 6:
        path = _resolve_symlink(path)

    if not os.path.exists(path):
        raise CommandExecutionError('Path not found: {0}'.format(path))

    salt.utils.win_dacl.set_owner(path, user)
    if pgroup:
        salt.utils.win_dacl.set_primary_group(path, pgroup)

    return True


def chpgrp(path, group):
    '''
    Change the group of a file

    Under Windows, this will set the rarely used primary group of a file.
    This generally has no bearing on permissions unless intentionally
    configured and is most commonly used to provide Unix compatibility (e.g.
    Services For Unix, NFS services).

    Ensure you know what you are doing before using this function.

    Args:
        path (str): The path to the file or directory
        pgroup (str): The primary group to assign

    Returns:
        bool: True if successful, otherwise error

    CLI Example:

    .. code-block:: bash

        salt '*' file.chpgrp c:\\temp\\test.txt Administrators
        salt '*' file.chpgrp c:\\temp\\test.txt "'None'"
    '''
    return salt.utils.win_dacl.set_primary_group(path, group)


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

    If you do actually want to set the 'primary group' of a file, use ``file
    .chpgrp``.

    To set group permissions use ``file.set_perms``

    Args:
        path (str): The path to the file or directory
        group (str): The group (unused)

    Returns:
        None

    CLI Example:

    .. code-block:: bash

        salt '*' file.chpgrp c:\\temp\\test.txt administrators
    '''
    func_name = '{0}.chgrp'.format(__virtualname__)
    if __opts__.get('fun', '') == func_name:
        log.info('The function %s should not be used on Windows systems; see '
                 'function docs for details.', func_name)
    log.debug('win_file.py %s Doing nothing for %s', func_name, path)

    return None


def stats(path, hash_type='sha256', follow_symlinks=True):
    '''
    Return a dict containing the stats about a given file

    Under Windows, `gid` will equal `uid` and `group` will equal `user`.

    While a file in Windows does have a 'primary group', this rarely used
    attribute generally has no bearing on permissions unless intentionally
    configured and is only used to support Unix compatibility features (e.g.
    Services For Unix, NFS services).

    Salt, therefore, remaps these properties to keep some kind of
    compatibility with Unix behavior. If the 'primary group' is required, it
    can be accessed in the `pgroup` and `pgid` properties.

    Args:
        path (str): The path to the file or directory
        hash_type (str): The type of hash to return
        follow_symlinks (bool):
            If the object specified by ``path`` is a symlink, get attributes of
            the linked file instead of the symlink itself. Default is True

    Returns:
        dict: A dictionary of file/directory stats

    CLI Example:

    .. code-block:: bash

        salt '*' file.stats /etc/passwd
    '''
    # This is to mirror the behavior of file.py. `check_file_meta` expects an
    # empty dictionary when the file does not exist
    if not os.path.exists(path):
        raise CommandExecutionError('Path not found: {0}'.format(path))

    if follow_symlinks and sys.getwindowsversion().major >= 6:
        path = _resolve_symlink(path)

    pstat = os.stat(path)

    ret = {}
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
    ret['mode'] = salt.utils.files.normalize_mode(oct(stat.S_IMODE(pstat.st_mode)))
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

    Args:
        path (str): The path to the file or directory

    Returns:
        dict: A dictionary of file attributes

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_attributes c:\\temp\\a.txt
    '''
    if not os.path.exists(path):
        raise CommandExecutionError('Path not found: {0}'.format(path))

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

    Args:
        path (str): The path to the file or directory
        archive (bool): Sets the archive attribute. Default is None
        hidden (bool): Sets the hidden attribute. Default is None
        normal (bool):
            Resets the file attributes. Cannot be used in conjunction with any
            other attribute. Default is None
        notIndexed (bool): Sets the indexed attribute. Default is None
        readonly (bool): Sets the readonly attribute. Default is None
        system (bool): Sets the system attribute. Default is None
        temporary (bool): Sets the temporary attribute. Default is None

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' file.set_attributes c:\\temp\\a.txt normal=True
        salt '*' file.set_attributes c:\\temp\\a.txt readonly=True hidden=True
    '''
    if not os.path.exists(path):
        raise CommandExecutionError('Path not found: {0}'.format(path))

    if normal:
        if archive or hidden or notIndexed or readonly or system or temporary:
            raise CommandExecutionError(
                'Normal attribute may not be used with any other attributes')
        ret = win32file.SetFileAttributes(path, 128)
        return True if ret is None else False

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

    ret = win32file.SetFileAttributes(path, intAttributes)
    return True if ret is None else False


def set_mode(path, mode):
    '''
    Set the mode of a file

    This just calls get_mode, which returns None because we don't use mode on
    Windows

    Args:
        path: The path to the file or directory
        mode: The mode (not used)

    Returns:
        None

    CLI Example:

    .. code-block:: bash

        salt '*' file.set_mode /etc/passwd 0644
    '''
    func_name = '{0}.set_mode'.format(__virtualname__)
    if __opts__.get('fun', '') == func_name:
        log.info('The function %s should not be used on Windows systems; '
                 'see function docs for details. The value returned is '
                 'always None. Use set_perms instead.', func_name)

    return get_mode(path)


def remove(path, force=False):
    '''
    Remove the named file or directory

    Args:
        path (str): The path to the file or directory to remove.
        force (bool): Remove even if marked Read-Only. Default is False

    Returns:
        bool: True if successful, False if unsuccessful

    CLI Example:

    .. code-block:: bash

        salt '*' file.remove C:\\Temp
    '''
    # This must be a recursive function in windows to properly deal with
    # Symlinks. The shutil.rmtree function will remove the contents of
    # the Symlink source in windows.

    path = os.path.expanduser(path)

    if not os.path.isabs(path):
        raise SaltInvocationError('File path must be absolute: {0}'.format(path))

    # Does the file/folder exists
    if not os.path.exists(path) and not is_link(path):
        raise CommandExecutionError('Path not found: {0}'.format(path))

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

    Args:
        src (str): The path to a file or directory
        link (str): The path to the link

    Returns:
        bool: True if successful, otherwise False

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


def is_link(path):
    '''
    Check if the path is a symlink

    This is only supported on Windows Vista or later.

    Inline with Unix behavior, this function will raise an error if the path
    is not a symlink, however, the error raised will be a SaltInvocationError,
    not an OSError.

    Args:
        path (str): The path to a file or directory

    Returns:
        bool: True if path is a symlink, otherwise False

    CLI Example:

    .. code-block:: bash

       salt '*' file.is_link /path/to/link
    '''
    if sys.getwindowsversion().major < 6:
        raise SaltInvocationError('Symlinks are only supported on Windows Vista or later.')

    try:
        return salt.utils.path.islink(path)
    except Exception as exc:
        raise CommandExecutionError(exc)


def readlink(path):
    '''
    Return the path that a symlink points to

    This is only supported on Windows Vista or later.

    Inline with Unix behavior, this function will raise an error if the path is
    not a symlink, however, the error raised will be a SaltInvocationError, not
    an OSError.

    Args:
        path (str): The path to the symlink

    Returns:
        str: The path that the symlink points to

    CLI Example:

    .. code-block:: bash

        salt '*' file.readlink /path/to/link
    '''
    if sys.getwindowsversion().major < 6:
        raise SaltInvocationError('Symlinks are only supported on Windows Vista or later.')

    try:
        return salt.utils.path.readlink(path)
    except OSError as exc:
        if exc.errno == errno.EINVAL:
            raise CommandExecutionError('{0} is not a symbolic link'.format(path))
        raise CommandExecutionError(exc.__str__())
    except Exception as exc:
        raise CommandExecutionError(exc)


def mkdir(path,
          owner=None,
          grant_perms=None,
          deny_perms=None,
          inheritance=True,
          reset=False):
    '''
    Ensure that the directory is available and permissions are set.

    Args:

        path (str):
            The full path to the directory.

        owner (str):
            The owner of the directory. If not passed, it will be the account
            that created the directory, likely SYSTEM

        grant_perms (dict):
            A dictionary containing the user/group and the basic permissions to
            grant, ie: ``{'user': {'perms': 'basic_permission'}}``. You can also
            set the ``applies_to`` setting here. The default is
            ``this_folder_subfolders_files``. Specify another ``applies_to``
            setting like this:

            .. code-block:: yaml

                {'user': {'perms': 'full_control', 'applies_to': 'this_folder'}}

            To set advanced permissions use a list for the ``perms`` parameter,
            ie:

            .. code-block:: yaml

                {'user': {'perms': ['read_attributes', 'read_ea'], 'applies_to': 'this_folder'}}

        deny_perms (dict):
            A dictionary containing the user/group and permissions to deny along
            with the ``applies_to`` setting. Use the same format used for the
            ``grant_perms`` parameter. Remember, deny permissions supersede
            grant permissions.

        inheritance (bool):
            If True the object will inherit permissions from the parent, if
            ``False``, inheritance will be disabled. Inheritance setting will
            not apply to parent directories if they must be created.

        reset (bool):
            If ``True`` the existing DACL will be cleared and replaced with the
            settings defined in this function. If ``False``, new entries will be
            appended to the existing DACL. Default is ``False``.

            .. versionadded:: 2018.3.0

    Returns:
        bool: True if successful

    Raises:
        CommandExecutionError: If unsuccessful

    CLI Example:

    .. code-block:: bash

        # To grant the 'Users' group 'read & execute' permissions.
        salt '*' file.mkdir C:\\Temp\\ Administrators "{'Users': {'perms': 'read_execute'}}"

        # Locally using salt call
        salt-call file.mkdir C:\\Temp\\ Administrators "{'Users': {'perms': 'read_execute', 'applies_to': 'this_folder_only'}}"

        # Specify advanced attributes with a list
        salt '*' file.mkdir C:\\Temp\\ Administrators "{'jsnuffy': {'perms': ['read_attributes', 'read_ea'], 'applies_to': 'this_folder_only'}}"
    '''
    # Make sure the drive is valid
    drive = os.path.splitdrive(path)[0]
    if not os.path.isdir(drive):
        raise CommandExecutionError('Drive {0} is not mapped'.format(drive))

    path = os.path.expanduser(path)
    path = os.path.expandvars(path)

    if not os.path.isdir(path):

        try:
            # Make the directory
            os.mkdir(path)

            # Set owner
            if owner:
                salt.utils.win_dacl.set_owner(obj_name=path, principal=owner)

            # Set permissions
            set_perms(
                path=path,
                grant_perms=grant_perms,
                deny_perms=deny_perms,
                inheritance=inheritance,
                reset=reset)

        except WindowsError as exc:
            raise CommandExecutionError(exc)

    return True


def makedirs_(path,
              owner=None,
              grant_perms=None,
              deny_perms=None,
              inheritance=True,
              reset=False):
    '''
    Ensure that the parent directory containing this path is available.

    Args:

        path (str):
            The full path to the directory.

            .. note::

                The path must end with a trailing slash otherwise the
                directory(s) will be created up to the parent directory. For
                example if path is ``C:\\temp\\test``, then it would be treated
                as ``C:\\temp\\`` but if the path ends with a trailing slash
                like ``C:\\temp\\test\\``, then it would be treated as
                ``C:\\temp\\test\\``.

        owner (str):
            The owner of the directory. If not passed, it will be the account
            that created the directory, likely SYSTEM.

        grant_perms (dict):
            A dictionary containing the user/group and the basic permissions to
            grant, ie: ``{'user': {'perms': 'basic_permission'}}``. You can also
            set the ``applies_to`` setting here. The default is
            ``this_folder_subfolders_files``. Specify another ``applies_to``
            setting like this:

            .. code-block:: yaml

                {'user': {'perms': 'full_control', 'applies_to': 'this_folder'}}

            To set advanced permissions use a list for the ``perms`` parameter, ie:

            .. code-block:: yaml

                {'user': {'perms': ['read_attributes', 'read_ea'], 'applies_to': 'this_folder'}}

        deny_perms (dict):
            A dictionary containing the user/group and permissions to deny along
            with the ``applies_to`` setting. Use the same format used for the
            ``grant_perms`` parameter. Remember, deny permissions supersede
            grant permissions.

        inheritance (bool):
            If True the object will inherit permissions from the parent, if
            False, inheritance will be disabled. Inheritance setting will not
            apply to parent directories if they must be created.

        reset (bool):
            If ``True`` the existing DACL will be cleared and replaced with the
            settings defined in this function. If ``False``, new entries will be
            appended to the existing DACL. Default is ``False``.

            .. versionadded:: 2018.3.0

    Returns:
        bool: True if successful

    Raises:
        CommandExecutionError: If unsuccessful

    CLI Example:

    .. code-block:: bash

        # To grant the 'Users' group 'read & execute' permissions.
        salt '*' file.makedirs C:\\Temp\\ Administrators "{'Users': {'perms': 'read_execute'}}"

        # Locally using salt call
        salt-call file.makedirs C:\\Temp\\ Administrators "{'Users': {'perms': 'read_execute', 'applies_to': 'this_folder_only'}}"

        # Specify advanced attributes with a list
        salt '*' file.makedirs C:\\Temp\\ Administrators "{'jsnuffy': {'perms': ['read_attributes', 'read_ea'], 'applies_to': 'this_folder_only'}}"
    '''
    path = os.path.expanduser(path)

    # walk up the directory structure until we find the first existing
    # directory
    dirname = os.path.normpath(os.path.dirname(path))

    if os.path.isdir(dirname):
        # There's nothing for us to do
        msg = 'Directory \'{0}\' already exists'.format(dirname)
        log.debug(msg)
        return msg

    if os.path.exists(dirname):
        msg = 'The path \'{0}\' already exists and is not a directory'.format(
            dirname
        )
        log.debug(msg)
        return msg

    directories_to_create = []
    while True:
        if os.path.isdir(dirname):
            break

        directories_to_create.append(dirname)
        current_dirname = dirname
        dirname = os.path.dirname(dirname)

        if current_dirname == dirname:
            raise SaltInvocationError(
                'Recursive creation for path \'{0}\' would result in an '
                'infinite loop. Please use an absolute path.'.format(dirname)
            )

    # create parent directories from the topmost to the most deeply nested one
    directories_to_create.reverse()
    for directory_to_create in directories_to_create:
        # all directories have the user, group and mode set!!
        log.debug('Creating directory: %s', directory_to_create)
        mkdir(
            path=directory_to_create,
            owner=owner,
            grant_perms=grant_perms,
            deny_perms=deny_perms,
            inheritance=inheritance,
            reset=reset)

    return True


def makedirs_perms(path,
                   owner=None,
                   grant_perms=None,
                   deny_perms=None,
                   inheritance=True,
                   reset=True):
    '''
    Set owner and permissions for each directory created.

    Args:

        path (str):
            The full path to the directory.

        owner (str):
            The owner of the directory. If not passed, it will be the account
            that created the directory, likely SYSTEM.

        grant_perms (dict):
            A dictionary containing the user/group and the basic permissions to
            grant, ie: ``{'user': {'perms': 'basic_permission'}}``. You can also
            set the ``applies_to`` setting here. The default is
            ``this_folder_subfolders_files``. Specify another ``applies_to``
            setting like this:

            .. code-block:: yaml

                {'user': {'perms': 'full_control', 'applies_to': 'this_folder'}}

            To set advanced permissions use a list for the ``perms`` parameter, ie:

            .. code-block:: yaml

                {'user': {'perms': ['read_attributes', 'read_ea'], 'applies_to': 'this_folder'}}

        deny_perms (dict):
            A dictionary containing the user/group and permissions to deny along
            with the ``applies_to`` setting. Use the same format used for the
            ``grant_perms`` parameter. Remember, deny permissions supersede
            grant permissions.

        inheritance (bool):
            If ``True`` the object will inherit permissions from the parent, if
            ``False``, inheritance will be disabled. Inheritance setting will
            not apply to parent directories if they must be created

        reset (bool):
            If ``True`` the existing DACL will be cleared and replaced with the
            settings defined in this function. If ``False``, new entries will be
            appended to the existing DACL. Default is ``False``.

            .. versionadded:: 2018.3.0

    Returns:
        bool: True if successful, otherwise raises an error

    CLI Example:

    .. code-block:: bash

        # To grant the 'Users' group 'read & execute' permissions.
        salt '*' file.makedirs_perms C:\\Temp\\ Administrators "{'Users': {'perms': 'read_execute'}}"

        # Locally using salt call
        salt-call file.makedirs_perms C:\\Temp\\ Administrators "{'Users': {'perms': 'read_execute', 'applies_to': 'this_folder_only'}}"

        # Specify advanced attributes with a list
        salt '*' file.makedirs_perms C:\\Temp\\ Administrators "{'jsnuffy': {'perms': ['read_attributes', 'read_ea'], 'applies_to': 'this_folder_files'}}"
    '''
    # Expand any environment variables
    path = os.path.expanduser(path)
    path = os.path.expandvars(path)

    # Get parent directory (head)
    head, tail = os.path.split(path)

    # If tail is empty, split head
    if not tail:
        head, tail = os.path.split(head)

    # If head and tail are defined and head is not there, recurse
    if head and tail and not os.path.exists(head):
        try:
            # Create the directory here, set inherited True because this is a
            # parent directory, the inheritance setting will only apply to the
            # target directory. Reset will be False as we only want to reset
            # the permissions on the target directory
            makedirs_perms(
                path=head,
                owner=owner,
                grant_perms=grant_perms,
                deny_perms=deny_perms,
                inheritance=True,
                reset=False)
        except OSError as exc:
            # be happy if someone already created the path
            if exc.errno != errno.EEXIST:
                raise
        if tail == os.curdir:  # xxx/newdir/. exists if xxx/newdir exists
            return {}

    # Make the directory
    mkdir(
        path=path,
        owner=owner,
        grant_perms=grant_perms,
        deny_perms=deny_perms,
        inheritance=inheritance,
        reset=reset)

    return True


def check_perms(path,
                ret=None,
                owner=None,
                grant_perms=None,
                deny_perms=None,
                inheritance=True,
                reset=False):
    '''
    Check owner and permissions for the passed directory. This function checks
    the permissions and sets them, returning the changes made. Used by the file
    state to populate the return dict

    Args:

        path (str):
            The full path to the directory.

        ret (dict):
            A dictionary to append changes to and return. If not passed, will
            create a new dictionary to return.

        owner (str):
            The owner to set for the directory.

        grant_perms (dict):
            A dictionary containing the user/group and the basic permissions to
            check/grant, ie: ``{'user': {'perms': 'basic_permission'}}``.
            Default is ``None``.

        deny_perms (dict):
            A dictionary containing the user/group and permissions to
            check/deny. Default is ``None``.

        inheritance (bool):
            ``True will check if inheritance is enabled and enable it. ``False``
            will check if inheritance is disabled and disable it. Default is
            ``True``.

        reset (bool):
            ``True`` will show what permissions will be removed by resetting the
            DACL. ``False`` will do nothing. Default is ``False``.

    Returns:
        dict: A dictionary of changes that have been made

    CLI Example:

    .. code-block:: bash

        # To see changes to ``C:\\Temp`` if the 'Users' group is given 'read & execute' permissions.
        salt '*' file.check_perms C:\\Temp\\ {} Administrators "{'Users': {'perms': 'read_execute'}}"

        # Locally using salt call
        salt-call file.check_perms C:\\Temp\\ {} Administrators "{'Users': {'perms': 'read_execute', 'applies_to': 'this_folder_only'}}"

        # Specify advanced attributes with a list
        salt '*' file.check_perms C:\\Temp\\ {} Administrators "{'jsnuffy': {'perms': ['read_attributes', 'read_ea'], 'applies_to': 'files_only'}}"
    '''
    if not os.path.exists(path):
        raise CommandExecutionError('Path not found: {0}'.format(path))

    path = os.path.expanduser(path)

    return __utils__['dacl.check_perms'](obj_name=path,
                                         obj_type='file',
                                         ret=ret,
                                         owner=owner,
                                         grant_perms=grant_perms,
                                         deny_perms=deny_perms,
                                         inheritance=inheritance,
                                         reset=reset)


def set_perms(path,
              grant_perms=None,
              deny_perms=None,
              inheritance=True,
              reset=False):
    '''
    Set permissions for the given path

    Args:

        path (str):
            The full path to the directory.

        grant_perms (dict):
            A dictionary containing the user/group and the basic permissions to
            grant, ie: ``{'user': {'perms': 'basic_permission'}}``. You can also
            set the ``applies_to`` setting here. The default for ``applise_to``
            is ``this_folder_subfolders_files``. Specify another ``applies_to``
            setting like this:

            .. code-block:: yaml

                {'user': {'perms': 'full_control', 'applies_to': 'this_folder'}}

            To set advanced permissions use a list for the ``perms`` parameter,
            ie:

            .. code-block:: yaml

                {'user': {'perms': ['read_attributes', 'read_ea'], 'applies_to': 'this_folder'}}

            To see a list of available attributes and applies to settings see
            the documentation for salt.utils.win_dacl.

            A value of ``None`` will make no changes to the ``grant`` portion of
            the DACL. Default is ``None``.

        deny_perms (dict):
            A dictionary containing the user/group and permissions to deny along
            with the ``applies_to`` setting. Use the same format used for the
            ``grant_perms`` parameter. Remember, deny permissions supersede
            grant permissions.

            A value of ``None`` will make no changes to the ``deny`` portion of
            the DACL. Default is ``None``.

        inheritance (bool):
            If ``True`` the object will inherit permissions from the parent, if
            ``False``, inheritance will be disabled. Inheritance setting will
            not apply to parent directories if they must be created. Default is
            ``False``.

        reset (bool):
            If ``True`` the existing DCL will be cleared and replaced with the
            settings defined in this function. If ``False``, new entries will be
            appended to the existing DACL. Default is ``False``.

            .. versionadded:: 2018.3.0

    Returns:
        bool: True if successful

    Raises:
        CommandExecutionError: If unsuccessful

    CLI Example:

    .. code-block:: bash

        # To grant the 'Users' group 'read & execute' permissions.
        salt '*' file.set_perms C:\\Temp\\ "{'Users': {'perms': 'read_execute'}}"

        # Locally using salt call
        salt-call file.set_perms C:\\Temp\\ "{'Users': {'perms': 'read_execute', 'applies_to': 'this_folder_only'}}"

        # Specify advanced attributes with a list
        salt '*' file.set_perms C:\\Temp\\ "{'jsnuffy': {'perms': ['read_attributes', 'read_ea'], 'applies_to': 'this_folder_only'}}"
    '''
    return __utils__['dacl.set_perms'](obj_name=path,
                                       obj_type='file',
                                       grant_perms=grant_perms,
                                       deny_perms=deny_perms,
                                       inheritance=inheritance,
                                       reset=reset)
