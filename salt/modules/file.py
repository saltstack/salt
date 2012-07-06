'''
Manage information about files on the minion, set/read user, group, and mode
data
'''

# TODO: We should add the capability to do u+r type operations here
# some time in the future

# Import python libs
import os
import re
import time
import hashlib
import shutil
import stat
import sys
import fnmatch
try:
    import grp
    import pwd
except ImportError:
    pass

# Import salt libs
import salt.utils.find
from salt.exceptions import CommandExecutionError, SaltInvocationError

def __virtual__():
    '''
    Only work on posix-like systems
    '''
    # win_file takes care of windows
    if __grains__['os'] == 'Windows':
        return False
    return 'file'


__outputter__ = {
    'touch':  'txt',
    'append': 'txt',
}


def gid_to_group(gid):
    '''
    Convert the group id to the group name on this system

    CLI Example::

        salt '*' file.gid_to_group 0
    '''
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        return ''


def group_to_gid(group):
    '''
    Convert the group to the gid on this system

    CLI Example::

        salt '*' file.group_to_gid root
    '''
    try:
        return grp.getgrnam(group).gr_gid
    except KeyError:
        return ''


def get_gid(path):
    '''
    Return the id of the group that owns a given file

    CLI Example::

        salt '*' file.get_gid /etc/passwd
    '''
    if not os.path.exists(path):
        return -1
    return os.stat(path).st_gid


def get_group(path):
    '''
    Return the group that owns a given file

    CLI Example::

        salt '*' file.get_group /etc/passwd
    '''
    gid = get_gid(path)
    if gid == -1:
        return False
    return gid_to_group(gid)


def uid_to_user(uid):
    '''
    Convert a uid to a user name

    CLI Example::

        salt '*' file.uid_to_user 0
    '''
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return ''


def user_to_uid(user):
    '''
    Convert user name to a uid

    CLI Example::

        salt '*' file.user_to_uid root
    '''
    try:
        return pwd.getpwnam(user).pw_uid
    except KeyError:
        return ''


def get_uid(path):
    '''
    Return the id of the user that owns a given file

    CLI Example::

        salt '*' file.get_uid /etc/passwd
    '''
    if not os.path.exists(path):
        return False
    return os.stat(path).st_uid


def get_user(path):
    '''
    Return the user that owns a given file

    CLI Example::

        salt '*' file.get_user /etc/passwd
    '''
    uid = get_uid(path)
    if uid == -1:
        return False
    return uid_to_user(uid)


def get_mode(path):
    '''
    Return the mode of a file

    CLI Example::

        salt '*' file.get_mode /etc/passwd
    '''
    if not os.path.exists(path):
        return -1
    mode = str(oct(os.stat(path).st_mode)[-4:])
    if mode.startswith('0'):
        return mode[1:]
    return mode


def set_mode(path, mode):
    '''
    Set the mode of a file

    CLI Example::

        salt '*' file.set_mode /etc/passwd 0644
    '''
    mode = str(mode).lstrip('0')
    if not mode:
        mode = '0'
    if not os.path.exists(path):
        return 'File not found'
    try:
        os.chmod(path, int(mode, 8))
    except Exception:
        return 'Invalid Mode ' + mode
    return get_mode(path)


def chown(path, user, group):
    '''
    Chown a file, pass the file the desired user and group

    CLI Example::

        salt '*' file.chown /etc/passwd root root
    '''
    uid = user_to_uid(user)
    gid = group_to_gid(group)
    err = ''
    if uid == '':
        if user:
            err += 'User does not exist\n'
        else:
            uid = -1
    if gid == '':
        if group:
            err += 'Group does not exist\n'
        else:
            gid = -1
    if not os.path.exists(path):
        err += 'File not found'
    if err:
        return err
    return os.chown(path, uid, gid)


def chgrp(path, group):
    '''
    Change the group of a file

    CLI Example::

        salt '*' file.chgrp /etc/passwd root
    '''
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
        with open(path, 'rb') as f:
            return getattr(hashlib, form)(f.read()).hexdigest()
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

def _sed_esc(s, escape_all=False):
    '''
    Escape single quotes and forward slashes
    '''
    special_chars = "^.[$()|*+?{"
    s = s.replace("'", "'\"'\"'").replace("/", "\/")
    if escape_all:
        for ch in special_chars:
            s = s.replace(ch, "\\" + ch)
    return s

def sed(path, before, after, limit='', backup='.bak', options='-r -e',
        flags='g', escape_all=False):
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
    # XXX:dc: Do we really want to always force escaping?
    #
    # Mandate that before and after are strings
    before = str(before)
    after = str(after)
    before = _sed_esc(before, escape_all)
    after = _sed_esc(after, escape_all)
    if sys.platform == 'darwin':
        options = options.replace('-r', '-E')

    cmd = r"sed {backup}{options} '{limit}s/{before}/{after}/{flags}' {path}".format(
            backup = '-i{0} '.format(backup) if backup else '-i ',
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

    regex = '{0}({1}){2}'.format(
            '^' if regex.startswith('^') else '',
            regex.lstrip('^').rstrip('$'),
            '$' if regex.endswith('$') else '')

    return __salt__['file.sed'](
        path,
        before=regex,
        after=r'{0}\1'.format(char),
        backup=backup)


def contains(path, text):
    '''
    Return True if the file at ``path`` contains ``text``

    CLI Example::

        salt '*' file.contains /etc/crontab 'mymaintenance.sh'

    .. versionadded:: 0.9.5
    '''
    if not os.path.exists(path):
        return False

    try:
        with open(path, 'r') as fp_:
            for line in fp_:
                if text.strip() == line.strip():
                    return True
        return False
    except (IOError, OSError):
        return False


def contains_regex(path, regex, lchar=''):
    '''
    Return True if the given regular expression matches anything in the text
    of a given file

    CLI Example::

        salt '*' /etc/crontab '^maint'
    '''
    if not os.path.exists(path):
        return False

    try:
        with open(path, 'r') as fp_:
            for line in  fp_:
                if re.search(regex, line.lstrip(lchar)):
                    return True
            return False
    except (IOError, OSError):
        return False


def contains_glob(path, glob):
    '''
    Return True if the given glob matches a string in the named file

    CLI Example::

        salt '*' /etc/foobar '*cheese*'
    '''
    if not os.path.exists(path):
        return False

    try:
        with open(path, 'r') as fp_:
            data = fp_.read()
            if fnmatch.fnmatch(data, glob):
                return True
            else:
                return False
    except (IOError, OSError):
        return False


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

    return 'Wrote {0} lines to "{1}"'.format(len(args), path)


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
        with open(name, 'a'):
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
        msg = 'atime and mtime must be integers'
        raise SaltInvocationError(msg)
    except (IOError, OSError) as exc:
        return False

    return os.path.exists(name)


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
    ret['group'] = gid_to_group(pstat.st_gid)
    ret['user'] = uid_to_user(pstat.st_uid)
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


def remove(path):
    if not os.path.isabs(path):
        raise SaltInvocationError('File path must be absolute.')

    if os.path.exists(path):
        try:
            if os.path.isfile(path):
                os.remove(path)
                return True
            elif os.path.isdir(path):
                shutil.rmtree(path)
                return True
        except (OSError, IOError):
            raise CommandExecutionError('Could not remove "{0}"'.format(path))
    return False
