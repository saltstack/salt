'''
Manage information about files on the minion, set/read user, group
data

Required python modules: win32api, win32con, win32security, ntsecuritycon
'''

import os
import time
import os.path
import hashlib
import logging

try:
    import win32security
    import ntsecuritycon as con
    has_windows_modules = True
except ImportError:
    has_windows_modules = False

import salt.utils
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)

def __virtual__():
    '''
    Only works on Windows systems
    '''
    if __grains__['os'] == 'Windows':
        if has_windows_modules:
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
    name, domain, type = win32security.LookupAccountSid (None, sid)
    return name


def group_to_gid(group):
    '''
    Convert the group to the gid on this system

    CLI Example::

        salt '*' file.group_to_gid administrators
    '''
    sid, domain, type = win32security.LookupAccountName (None, group)
    return win32security.ConvertSidToStringSid(sid)


def get_gid(path):
    '''
    Return the id of the group that owns a given file

    CLI Example::

        salt '*' file.get_gid c:\\temp\\test.txt
    '''
    if not os.path.exists(path):
        return False
    secdesc = win32security.GetFileSecurity (path, win32security.OWNER_SECURITY_INFORMATION)
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
    secdesc = win32security.GetFileSecurity (path, win32security.OWNER_SECURITY_INFORMATION)
    owner_sid = secdesc.GetSecurityDescriptorOwner()
    name, domain, type = win32security.LookupAccountSid (None, owner_sid)
    return name


def uid_to_user(uid):
    '''
    Convert a uid to a user name

    CLI Example::

        salt '*' file.uid_to_user S-1-5-21-626487655-2533044672-482107328-1010
    '''
    sid = win32security.GetBinarySid(uid)
    name, domain, type = win32security.LookupAccountSid (None, sid)
    return name


def user_to_uid(user):
    '''
    Convert user name to a uid

    CLI Example::

        salt '*' file.user_to_uid myusername
    '''
    sid, domain, type = win32security.LookupAccountName (None, user)
    return win32security.ConvertSidToStringSid(sid)


def get_uid(path):
    '''
    Return the id of the user that owns a given file

    CLI Example::

        salt '*' file.get_uid c:\\temp\\test.txt
    '''
    if not os.path.exists(path):
        return False
    secdesc = win32security.GetFileSecurity (path, win32security.OWNER_SECURITY_INFORMATION)
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
    secdesc = win32security.GetFileSecurity (path, win32security.OWNER_SECURITY_INFORMATION)
    owner_sid = secdesc.GetSecurityDescriptorOwner()
    name, domain, type = win32security.LookupAccountSid (None, owner_sid)
    return name


def chown(path, user, group):
    '''
    Chown a file, pass the file the desired user and group

    CLI Example::

        salt '*' file.chown c:\\temp\\test.txt myusername administrators
    '''
    # I think this function isn't working correctly yet
    sd = win32security.GetFileSecurity (path, win32security.DACL_SECURITY_INFORMATION)
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

    dacl = win32security.ACL ()
    dacl.AddAccessAllowedAce (win32security.ACL_REVISION, con.FILE_ALL_ACCESS, win32security.GetBinarySid(uid))
    dacl.AddAccessAllowedAce (win32security.ACL_REVISION, con.FILE_ALL_ACCESS, win32security.GetBinarySid(gid))
    sd.SetSecurityDescriptorDacl (1, dacl, 0)
    return win32security.SetFileSecurity (path, win32security.DACL_SECURITY_INFORMATION, sd)


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


def get_sum(path, form='md5'):
    '''
    Return the sum for the given file, default is md5, sha1, sha224, sha256,
    sha384, sha512 are supported

    CLI Example::

        salt '*' file.get_sum /etc/passwd sha512
    '''
    if not os.path.isfile(path):
        return 'File not found'
    try:
        return getattr(hashlib, form)(open(path, 'rb').read()).hexdigest()
    except (IOError, OSError) as e:
        return 'File Error: %s' % (str(e))
    except AttributeError as e:
        return 'Hash ' + form + ' not supported'
    except NameError as e:
        return 'Hashlib unavailable - please fix your python install'
    except Exception as e:
        return str(e)


def find(path, **kwargs):
    '''
    Approximate the Unix find(1) command and return a list of paths that
    meet the specified critera.

    The options include match criteria::

        name    = path-glob                 # case sensitive
        iname   = path-glob                 # case insensitive
        regex   = path-regex                # case sensitive
        iregex  = path-regex                # case insensitive
        type    = file-types                # match any listed type
        user    = users                     # match any listed user
        group   = groups                    # match any listed group
        size    = [+-]number[size-unit]     # default unit = byte
        mtime   = interval                  # modified since date
        grep    = regex                     # search file contents

    and/or actions::

        delete [= file-types]               # default type = 'f'
        exec    = command [arg ...]         # where {} is replaced by pathname
        print  [= print-opts]

    The default action is 'print=path'.

    file-glob::

        *                = match zero or more chars
        ?                = match any char
        [abc]            = match a, b, or c
        [!abc] or [^abc] = match anything except a, b, and c
        [x-y]            = match chars x through y
        [!x-y] or [^x-y] = match anything except chars x through y
        {a,b,c}          = match a or b or c

    path-regex: a Python re (regular expression) pattern to match pathnames

    file-types: a string of one or more of the following::

        a: all file types
        b: block device
        c: character device
        d: directory
        p: FIFO (named pipe)
        f: plain file
        l: symlink
        s: socket

    users: a space and/or comma separated list of user names and/or uids

    groups: a space and/or comma separated list of group names and/or gids

    size-unit::

        b: bytes
        k: kilobytes
        m: megabytes
        g: gigabytes
        t: terabytes

    interval::

        [<num>w] [<num>[d]] [<num>h] [<num>m] [<num>s]

        where:
            w: week
            d: day
            h: hour
            m: minute
            s: second

    print-opts: a comma and/or space separated list of one or more of the
    following::

        group: group name
        md5:   MD5 digest of file contents
        mode:  file permissions (as integer)
        mtime: last modification time (as time_t)
        name:  file basename
        path:  file absolute path
        size:  file size in bytes
        type:  file type
        user:  user name

    CLI Examples::

        salt '*' file.find / type=f name=\*.bak size=+10m
        salt '*' file.find /var mtime=+30d size=+10m print=path,size,mtime
        salt '*' file.find /var/log name=\*.[0-9] mtime=+30d size=+10m delete
    '''
    try:
        f = salt.utils.find.Finder(kwargs)
    except ValueError as ex:
        return 'error: {0}'.format(ex)

    ret = [p for p in f.find(path)]
    ret.sort()
    return ret

def _sed_esc(s):
    '''
    Escape single quotes and forward slashes
    '''
    return '{0}'.format(s).replace("'", "'\"'\"'").replace("/", "\/")

def sed(path, before, after, limit='', backup='.bak', options='-r -e',
        flags='g'):
    '''
    Make a simple edit to a file

    Equivalent to::

        sed <backup> <options> "/<limit>/ s/<before>/<after>/<flags> <file>"

    path
        The full path to the file to be edited
    before
        A pattern to find in order to replace with ``after``
    after
        Text that will replace ``before``
    limit : ``''``
        An initial pattern to search for before searching for ``before``
    backup : ``.bak``
        The file will be backed up before edit with this file extension;
        **WARNING:** each time ``sed``/``comment``/``uncomment`` is called will
        overwrite this backup
    options : ``-r -e``
        Options to pass to sed
    flags : ``g``
        Flags to modify the sed search; e.g., ``i`` for case-insensitve pattern
        matching

    Forward slashes and single quotes will be escaped automatically in the
    ``before`` and ``after`` patterns.

    CLI Example::

        salt '*' file.sed /etc/httpd/httpd.conf 'LogLevel warn' 'LogLevel info'

    .. versionadded:: 0.9.5
    '''
    # Largely inspired by Fabric's contrib.files.sed()

    before = _sed_esc(before)
    after = _sed_esc(after)

    cmd = r"sed {backup}{options} '{limit}s/{before}/{after}/{flags}' {path}".format(
            backup = '-i{0} '.format(backup) if backup else '',
            options = options,
            limit = '/{0}/ '.format(limit) if limit else '',
            before = before,
            after = after,
            flags = flags,
            path = path)

    return __salt__['cmd.run'](cmd)

def uncomment(path, regex, char='#', backup='.bak'):
    '''
    Uncomment specified commented lines in a file

    path
        The full path to the file to be edited
    regex
        A regular expression used to find the lines that are to be uncommented.
        This regex should not include the comment character. A leading ``^``
        character will be stripped for convenience (for easily switching
        between comment() and uncomment()).
    char : ``#``
        The character to remove in order to uncomment a line; if a single
        whitespace character follows the comment it will also be removed
    backup : ``.bak``
        The file will be backed up before edit with this file extension;
        **WARNING:** each time ``sed``/``comment``/``uncomment`` is called will
        overwrite this backup

    CLI Example::

        salt '*' file.uncomment /etc/hosts.deny 'ALL: PARANOID'

    .. versionadded:: 0.9.5
    '''
    # Largely inspired by Fabric's contrib.files.uncomment()

    return __salt__['file.sed'](path,
        before=r'^([[:space:]]*){0}[[:space:]]?'.format(char),
        after=r'\1',
        limit=regex.lstrip('^'),
        backup=backup)

def comment(path, regex, char='#', backup='.bak'):
    '''
    Comment out specified lines in a file

    path
        The full path to the file to be edited
    regex
        A regular expression used to find the lines that are to be commented;
        this pattern will be wrapped in parenthesis and will move any
        preceding/trailing ``^`` or ``$`` characters outside the parenthesis
        (e.g., the pattern ``^foo$`` will be rewritten as ``^(foo)$``)
    char : ``#``
        The character to be inserted at the beginning of a line in order to
        comment it out
    backup : ``.bak``
        The file will be backed up before edit with this file extension

        .. warning::

            This backup will be overwritten each time ``sed`` / ``comment`` /
            ``uncomment`` is called. Meaning the backup will only be useful
            after the first invocation.

    CLI Example::

        salt '*' file.comment /etc/modules pcspkr

    .. versionadded:: 0.9.5
    '''
    # Largely inspired by Fabric's contrib.files.comment()

    regex = "{0}({1}){2}".format(
            '^' if regex.startswith('^') else '',
            regex.lstrip('^').rstrip('$'),
            '$' if regex.endswith('$') else '')

    return __salt__['file.sed'](
        path,
        before=regex,
        after=r'{0}\1'.format(char),
        backup=backup)

def contains(path, text, limit=''):
    '''
    Return True if the file at ``path`` contains ``text``

    CLI Example::

        salt '*' file.contains /etc/crontab 'mymaintenance.sh'

    .. versionadded:: 0.9.5
    '''
    # Largely inspired by Fabric's contrib.files.contains()

    if not os.path.exists(path):
        return False

    result = __salt__['file.sed'](path, text, '&', limit=limit, backup='',
            options='-n -r -e', flags='gp')

    return bool(result)

def append(path, *args):
    '''
    Append text to the end of a file

    CLI Example::

        salt '*' file.append /etc/motd \\
                "With all thine offerings thou shalt offer salt."\\
                "Salt is what makes things taste bad when it isn't in them."

    .. versionadded:: 0.9.5
    '''
    # Largely inspired by Fabric's contrib.files.append()

    with open(path, "a") as f:
        for line in args:
            f.write('{0}\n'.format(line))

    return "Wrote {0} lines to '{1}'".format(len(args), path)

def touch(name, atime=None, mtime=None):
    '''
    Just like 'nix's "touch" command, create a file if it
    doesn't exist or simply update the atime and mtime if
    it already does.

    atime:
        Access time in Unix epoch time
    mtime:
        Last modification in Unix epoch time

    CLI Example::

        salt '*' file.touch /var/log/emptyfile

    .. versionadded:: 0.9.5
    '''
    if atime and atime.isdigit():
        atime = int(atime)
    if mtime and mtime.isdigit():
        mtime = int(mtime)
    try:
        with open(name, "a"):
            if not atime and not mtime:
                times = None
            elif not mtime and atime:
                times = (atime, time.time())
            elif not atime and mtime:
                times = (time.time(), mtime)
            else:
                times = (atime, mtime)
            os.utime(name, times)
    except TypeError as exc:
        msg = "atime and mtime must be integers"
        raise SaltInvocationError(msg)
    except (IOError, OSError) as exc:
        return False

    return os.path.exists(name)
