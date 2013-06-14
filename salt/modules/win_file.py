'''
Manage information about files on the minion, set/read user, group
data

:depends:   - win32api
            - win32con
            - win32security
            - ntsecuritycon
'''

# Import python libs
import os
import stat
import os.path
import logging
import contextlib
import difflib
import tempfile # do no remove. Used in import of salt.modules.file.__clean_tmp

# Import third party libs
try:
    import win32security
    import ntsecuritycon as con
    HAS_WINDOWS_MODULES = True
except ImportError:
    HAS_WINDOWS_MODULES = False

# Import salt libs
import salt.utils
from salt.modules.file import (check_hash, check_managed, check_perms, # pylint: disable=W0611
        directory_exists, get_managed, mkdir, makedirs, makedirs_perms,
        patch, remove, source_list, sed_contains, touch, append, contains,
        contains_regex, contains_regex_multiline, contains_glob, patch,
        uncomment, sed, find, psed, get_sum, check_hash, get_hash, comment,
        manage_file, file_exists, get_diff, get_managed, __clean_tmp,
        check_managed, check_file_meta, contains_regex)

from salt.utils import namespaced_function

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows():
        if HAS_WINDOWS_MODULES:
            global check_perms, get_managed, makedirs_perms, manage_file
            global source_list, mkdir, __clean_tmp, makedirs

            check_perms = namespaced_function(check_perms, globals())
            get_managed = namespaced_function(get_managed, globals())
            makedirs_perms = namespaced_function(makedirs_perms, globals())
            makedirs = namespaced_function(makedirs, globals())
            manage_file = namespaced_function(manage_file, globals())
            source_list = namespaced_function(source_list, globals())
            mkdir = namespaced_function(mkdir, globals())
            __clean_tmp = namespaced_function(__clean_tmp, globals())

            return 'file'
        log.warn(salt.utils.required_modules_error(__file__, __doc__))
    return False


__outputter__ = {
    'touch': 'txt',
    'append': 'txt',
}


def gid_to_group(gid):
    '''
    Convert the group id to the group name on this system

    CLI Example::

        salt '*' file.gid_to_group S-1-5-21-626487655-2533044672-482107328-1010
    '''
    sid = win32security.GetBinarySid(gid)
    name, domain, account_type = win32security.LookupAccountSid(None, sid)
    return name


def group_to_gid(group):
    '''
    Convert the group to the gid on this system

    CLI Example::

        salt '*' file.group_to_gid administrators
    '''
    sid, domain, account_type = win32security.LookupAccountName(None, group)
    return win32security.ConvertSidToStringSid(sid)


def get_gid(path):
    '''
    Return the id of the group that owns a given file

    CLI Example::

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

    CLI Example::

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

    CLI Example::

        salt '*' file.uid_to_user S-1-5-21-626487655-2533044672-482107328-1010
    '''
    sid = win32security.GetBinarySid(uid)
    name, domain, account_type = win32security.LookupAccountSid(None, sid)
    return name


def user_to_uid(user):
    '''
    Convert user name to a uid

    CLI Example::

        salt '*' file.user_to_uid myusername
    '''
    sid, domain, account_type = win32security.LookupAccountName(None, user)
    return win32security.ConvertSidToStringSid(sid)


def get_uid(path):
    '''
    Return the id of the user that owns a given file

    CLI Example::

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

    Right now we're just returning 777
    because Windows' doesn't have a mode
    like Linux

    CLI Example::

        salt '*' file.get_mode /etc/passwd
    '''
    if not os.path.exists(path):
        return -1
    mode = 777
    return mode


def get_user(path):
    '''
    Return the user that owns a given file

    CLI Example::

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

    CLI Example::

        salt '*' file.chown c:\\temp\\test.txt myusername administrators
    '''
    # I think this function isn't working correctly yet
    gsd = win32security.GetFileSecurity(
        path, win32security.DACL_SECURITY_INFORMATION
    )
    uid = user_to_uid(user)
    gid = group_to_gid(group)
    err = ''
    if uid == '':
        err += 'User does not exist\n'
    if gid == '':
        err += 'Group does not exist\n'
    if not os.path.exists(path):
        err += 'File not found'
    if err:
        return err

    dacl = win32security.ACL()
    dacl.AddAccessAllowedAce(
        win32security.ACL_REVISION, con.FILE_ALL_ACCESS,
        win32security.GetBinarySid(uid)
    )
    dacl.AddAccessAllowedAce(
        win32security.ACL_REVISION, con.FILE_ALL_ACCESS,
        win32security.GetBinarySid(gid)
    )
    gsd.SetSecurityDescriptorDacl(1, dacl, 0)
    return win32security.SetFileSecurity(
        path, win32security.DACL_SECURITY_INFORMATION, gsd
    )


def chgrp(path, group):
    '''
    Change the group of a file

    CLI Example::

        salt '*' file.chgrp c:\\temp\\test.txt administrators
    '''
    # I think this function isn't working correctly yet
    gid = group_to_gid(group)
    err = ''
    if gid == '':
        err += 'Group does not exist\n'
    if not os.path.exists(path):
        err += 'File not found'
    if err:
        return err
    user = get_user(path)
    return chown(path, user, group)


def stats(path, hash_type='md5', follow_symlink=False):
    '''
    Return a dict containing the stats for a given file

    CLI Example::

        salt '*' file.stats /etc/passwd
    '''
    ret = {}
    if not os.path.exists(path):
        return ret
    if follow_symlink:
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
