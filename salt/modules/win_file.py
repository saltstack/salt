# -*- coding: utf-8 -*-
'''
Manage information about files on the minion, set/read user, group
data

:depends:   - win32api
            - win32con
            - win32file
            - win32security
            - ntsecuritycon
'''

# Import python libs
import os
import stat
import os.path
import logging
# pylint: disable=W0611
import tempfile  # do not remove. Used in salt.modules.file.__clean_tmp
import itertools  # same as above, do not remove, it's used in __clean_tmp
import contextlib  # do not remove, used in imported file.py functions
import difflib  # do not remove, used in imported file.py functions
import errno  # do not remove, used in imported file.py functions
import shutil  # do not remove, used in imported file.py functions
import re  # do not remove, used in imported file.py functions
import sys  # do not remove, used in imported file.py functions
import fileinput  # do not remove, used in imported file.py functions
import salt.utils.atomicfile  # do not remove, used in imported file.py functions
import salt._compat  # do not remove, used in imported file.py functions
from salt.exceptions import CommandExecutionError, SaltInvocationError
# pylint: enable=W0611

# Import third party libs
try:
    import win32security
    import win32file
    from pywintypes import error as pywinerror
    HAS_WINDOWS_MODULES = True
except ImportError:
    HAS_WINDOWS_MODULES = False

# Import salt libs
import salt.utils
from salt.modules.file import (check_hash,  # pylint: disable=W0611
        directory_exists, get_managed, mkdir, makedirs_, makedirs_perms,
        check_managed, check_perms, patch, remove, source_list, sed_contains,
        touch, append, contains, contains_regex, contains_regex_multiline,
        contains_glob, uncomment, sed, find, psed, get_sum, _get_bkroot,
        get_hash, comment, manage_file, file_exists, get_diff, list_backups,
        __clean_tmp, check_file_meta, _binary_replace, restore_backup,
        access, copy, readdir, rmdir, truncate, replace, delete_backup,
        search, _get_flags, extract_hash, _error)

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
            global check_managed, check_file_meta, remove, append, _error
            global directory_exists, patch, sed_contains, touch, contains
            global contains_regex, contains_regex_multiline, contains_glob
            global sed, find, psed, get_sum, check_hash, get_hash, delete_backup
            global uncomment, comment, get_diff, _get_flags, extract_hash
            global access, copy, readdir, rmdir, truncate, replace, search
            global _binary_replace, _get_bkroot, list_backups, restore_backup

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
            remove = _namespaced_function(remove, globals())
            append = _namespaced_function(append, globals())
            check_perms = _namespaced_function(check_perms, globals())
            get_managed = _namespaced_function(get_managed, globals())
            check_managed = _namespaced_function(check_managed, globals())
            check_file_meta = _namespaced_function(check_file_meta, globals())
            makedirs_perms = _namespaced_function(makedirs_perms, globals())
            makedirs_ = _namespaced_function(makedirs_, globals())
            manage_file = _namespaced_function(manage_file, globals())
            source_list = _namespaced_function(source_list, globals())
            mkdir = _namespaced_function(mkdir, globals())
            file_exists = _namespaced_function(file_exists, globals())
            __clean_tmp = _namespaced_function(__clean_tmp, globals())
            directory_exists = _namespaced_function(directory_exists, globals())
            patch = _namespaced_function(patch, globals())
            sed_contains = _namespaced_function(sed_contains, globals())
            touch = _namespaced_function(touch, globals())
            contains = _namespaced_function(contains, globals())
            contains_regex = _namespaced_function(contains_regex, globals())
            contains_regex_multiline = _namespaced_function(contains_regex_multiline, globals())
            contains_glob = _namespaced_function(contains_glob, globals())
            sed = _namespaced_function(sed, globals())
            find = _namespaced_function(find, globals())
            psed = _namespaced_function(psed, globals())
            get_sum = _namespaced_function(get_sum, globals())
            check_hash = _namespaced_function(check_hash, globals())
            get_hash = _namespaced_function(get_hash, globals())
            uncomment = _namespaced_function(uncomment, globals())
            comment = _namespaced_function(comment, globals())
            get_diff = _namespaced_function(get_diff, globals())
            access = _namespaced_function(access, globals())
            copy = _namespaced_function(copy, globals())
            readdir = _namespaced_function(readdir, globals())
            rmdir = _namespaced_function(rmdir, globals())
            truncate = _namespaced_function(truncate, globals())

            return __virtualname__
    return False

__outputter__ = {
    'touch': 'txt',
    'append': 'txt',
}

__func_alias__ = {
    'makedirs_': 'makedirs'
}


def gid_to_group(gid):
    '''
    Convert the group id to the group name on this system

    CLI Example:

    .. code-block:: bash

        salt '*' file.gid_to_group S-1-5-21-626487655-2533044672-482107328-1010
    '''
    if not gid:
        return False
    sid = win32security.GetBinarySid(gid)
    name, domain, account_type = win32security.LookupAccountSid(None, sid)
    return name


def group_to_gid(group):
    '''
    Convert the group to the gid on this system

    CLI Example:

    .. code-block:: bash

        salt '*' file.group_to_gid administrators
    '''
    sid, domain, account_type = win32security.LookupAccountName(None, group)
    return win32security.ConvertSidToStringSid(sid)


def get_gid(path):
    '''
    Return the id of the group that owns a given file

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_gid c:\\temp\\test.txt
    '''
    if not os.path.exists(path):
        return False
    secdesc = win32security.GetFileSecurity(
        path, win32security.OWNER_SECURITY_INFORMATION
    )
    owner_sid = secdesc.GetSecurityDescriptorOwner()
    return win32security.ConvertSidToStringSid(owner_sid)


def get_group(path):
    '''
    Return the group that owns a given file

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_group c:\\temp\\test.txt
    '''
    if not os.path.exists(path):
        return False
    secdesc = win32security.GetFileSecurity(
        path, win32security.OWNER_SECURITY_INFORMATION
    )
    owner_sid = secdesc.GetSecurityDescriptorOwner()
    name, domain, account_type = win32security.LookupAccountSid(None, owner_sid)
    return name


def uid_to_user(uid):
    '''
    Convert a uid to a user name

    CLI Example:

    .. code-block:: bash

        salt '*' file.uid_to_user S-1-5-21-626487655-2533044672-482107328-1010
    '''
    sid = win32security.GetBinarySid(uid)
    name, domain, account_type = win32security.LookupAccountSid(None, sid)
    return name


def user_to_uid(user):
    '''
    Convert user name to a uid

    CLI Example:

    .. code-block:: bash

        salt '*' file.user_to_uid myusername
    '''
    sid, domain, account_type = win32security.LookupAccountName(None, user)
    return win32security.ConvertSidToStringSid(sid)


def get_uid(path):
    '''
    Return the id of the user that owns a given file

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_uid c:\\temp\\test.txt
    '''
    if not os.path.exists(path):
        return False
    secdesc = win32security.GetFileSecurity(
        path, win32security.OWNER_SECURITY_INFORMATION
    )
    owner_sid = secdesc.GetSecurityDescriptorOwner()
    return win32security.ConvertSidToStringSid(owner_sid)


def get_mode(path):
    '''
    Return the mode of a file

    Right now we're just returning None
    because Windows' doesn't have a mode
    like Linux

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_mode /etc/passwd
    '''
    if not os.path.exists(path):
        return -1
    return None


def get_user(path):
    '''
    Return the user that owns a given file

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_user c:\\temp\\test.txt
    '''
    secdesc = win32security.GetFileSecurity(
        path, win32security.OWNER_SECURITY_INFORMATION
    )
    owner_sid = secdesc.GetSecurityDescriptorOwner()
    name, domain, account_type = win32security.LookupAccountSid(None, owner_sid)
    return name


def chown(path, user, group):
    '''
    Chown a file, pass the file the desired user and group

    CLI Example:

    .. code-block:: bash

        salt '*' file.chown c:\\temp\\test.txt myusername administrators
    '''
    err = ''
    # get SID object for user
    try:
        userSID, domainName, objectType = win32security.LookupAccountName(None, user)
    except pywinerror:
        err += 'User does not exist\n'

    # get SID object for group
    try:
        groupSID, domainName, objectType = win32security.LookupAccountName(None, group)
    except pywinerror:
        err += 'Group does not exist\n'

    if not os.path.exists(path):
        err += 'File not found\n'
    if err:
        return err

    # set owner and group
    securityInfo = win32security.OWNER_SECURITY_INFORMATION + win32security.GROUP_SECURITY_INFORMATION
    win32security.SetNamedSecurityInfo(path, win32security.SE_FILE_OBJECT, securityInfo, userSID, groupSID, None, None)
    return None


def chgrp(path, group):
    '''
    Change the group of a file

    CLI Example:

    .. code-block:: bash

        salt '*' file.chgrp c:\\temp\\test.txt administrators
    '''
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
    securityInfo = win32security.GROUP_SECURITY_INFORMATION
    win32security.SetNamedSecurityInfo(path, win32security.SE_FILE_OBJECT, securityInfo, None, groupSID, None, None)
    return None


def stats(path, hash_type='md5', follow_symlinks=False):
    '''
    Return a dict containing the stats for a given file

    CLI Example:

    .. code-block:: bash

        salt '*' file.stats /etc/passwd
    '''
    ret = {}
    if not os.path.exists(path):
        return ret
    if follow_symlinks:
        pstat = os.stat(path)
    else:
        pstat = os.lstat(path)
    ret['inode'] = pstat.st_ino
    ret['uid'] = pstat.st_uid
    ret['gid'] = pstat.st_gid
    ret['group'] = 0
    ret['user'] = 0
    ret['atime'] = pstat.st_atime
    ret['mtime'] = pstat.st_mtime
    ret['ctime'] = pstat.st_ctime
    ret['size'] = pstat.st_size
    ret['mode'] = str(oct(stat.S_IMODE(pstat.st_mode)))
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
        findDataTuple = fileIterator.next()
        if findDataTuple[6] == 0xA0000003:
            attributes['mountedVolume'] = True
    # check if it's a soft (symbolic) link

    # Note:  os.path.islink() does not work in
    #   Python 2.7 for the Windows NTFS file system.
    #   The following code does, however, work (tested in Windows 8)

    attributes['symbolicLink'] = False
    if attributes['reparsePoint'] is True:
        fileIterator = win32file.FindFilesIterator(path)
        findDataTuple = fileIterator.next()
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
    return get_mode(path)
