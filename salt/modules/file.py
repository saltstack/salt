'''
Manage information about files on the minion, set/read user, group, and mode
data
'''

# TODO: We should add the capability to do u+r type operations here
# some time in the future

# Import python libs
import contextlib  # For < 2.7 compat
import os
import re
import time
import shutil
import stat
import tempfile
import sys
import getpass
import hashlib
import difflib
import fnmatch
import errno
import logging
import itertools
try:
    import grp
    import pwd
except ImportError:
    pass

# Import salt libs
import salt.utils
import salt.utils.find
import salt.utils.filebuffer
from salt.exceptions import CommandExecutionError, SaltInvocationError
import salt._compat

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    # win_file takes care of windows
    if salt.utils.is_windows():
        return False
    return 'file'


def __clean_tmp(sfn):
    '''
    Clean out a template temp file
    '''
    if sfn.startswith(tempfile.gettempdir()):
        # Don't remove if it exists in file_roots (any env)
        all_roots = itertools.chain.from_iterable(__opts__['file_roots'].itervalues())
        in_roots = any(sfn.startswith(root) for root in all_roots)
        # Only clean up files that exist
        if os.path.exists(sfn) and not in_roots:
            os.remove(sfn)


def _error(ret, err_msg):
    ret['result'] = False
    ret['comment'] = err_msg
    return ret


def _binary_replace(old, new):
    '''
    This function does NOT do any diffing, it just checks the old and new files
    to see if either is binary, and provides an appropriate string noting the
    difference between the two files. If neither file is binary, an empty
    string is returned.

    This function should only be run AFTER it has been determined that the
    files differ.
    '''
    old_isbin = not salt.utils.istextfile(old)
    new_isbin = not salt.utils.istextfile(new)
    if any((old_isbin, new_isbin)):
        if all((old_isbin, new_isbin)):
            return 'Replace binary file'
        elif old_isbin:
            return 'Replace binary file with text file'
        elif new_isbin:
            return 'Replace text file with binary file'
    return ''


def gid_to_group(gid):
    '''
    Convert the group id to the group name on this system

    CLI Example::

        salt '*' file.gid_to_group 0
    '''
    try:
        gid = int(gid)
    except ValueError:
        # This is not an integer, maybe it's already the group name?
        gid = group_to_gid(gid)

    if gid == '':
        # Don't even bother to feed it to grp
        return ''

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
    if not group:
        return ''
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
    if not user:
        user = getpass.getuser()
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
        return ''
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
        with salt.utils.fopen(path, 'rb') as ifile:
            return getattr(hashlib, form)(ifile.read()).hexdigest()
    except (IOError, OSError) as err:
        return 'File Error: {0}'.format(err)
    except AttributeError:
        return 'Hash {0} not supported'.format(form)
    except NameError:
        return 'Hashlib unavailable - please fix your python install'
    except Exception as err:
        return str(err)


def get_hash(path, form='md5', chunk_size=4096):
    '''
    Get the hash sum of a file

    This is better than ``get_sum`` for the following reasons:
        - It does not read the entire file into memory.
        - It does not return a string on error. The returned value of
            ``get_sum`` cannot really be trusted since it is vulnerable to
            collisions: ``get_sum(..., 'xyz') == 'Hash xyz not supported'``

    CLI Example::

        salt '*' file.get_hash /etc/shadow
    '''
    return salt.utils.get_hash(path, form, chunk_size)


def check_hash(path, hash):
    '''
    Check if a file matches the given hash string

    Returns true if the hash matched, otherwise false. Raises ValueError if
    the hash was not formatted correctly.

    path
        A file path
    hash
        A string in the form <hash_type>=<hash_value>. For example:
        ``md5=e138491e9d5b97023cea823fe17bac22``

    CLI Example::

        salt '*' file.check_hash /etc/fstab md5=<md5sum>
    '''
    hash_parts = hash.split('=', 1)
    if len(hash_parts) != 2:
        raise ValueError('Bad hash format: {!r}'.format(hash))
    hash_form, hash_value = hash_parts
    return get_hash(path, hash_form) == hash_value


def find(path, **kwargs):
    '''
    Approximate the Unix find(1) command and return a list of paths that
    meet the specified criteria.

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

        salt '*' file.find / type=f name=\\*.bak size=+10m
        salt '*' file.find /var mtime=+30d size=+10m print=path,size,mtime
        salt '*' file.find /var/log name=\\*.[0-9] mtime=+30d size=+10m delete
    '''
    try:
        finder = salt.utils.find.Finder(kwargs)
    except ValueError as ex:
        return 'error: {0}'.format(ex)

    ret = [p for p in finder.find(path)]
    ret.sort()
    return ret


def _sed_esc(string, escape_all=False):
    '''
    Escape single quotes and forward slashes
    '''
    special_chars = "^.[$()|*+?{"
    string = string.replace("'", "'\"'\"'").replace("/", "\\/")
    if escape_all is True:
        for char in special_chars:
            string = string.replace(char, "\\" + char)
    return string


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
    limit = _sed_esc(limit, escape_all)
    if sys.platform == 'darwin':
        options = options.replace('-r', '-E')

    cmd = (
        r'''sed {backup}{options} '{limit}s/{before}/{after}/{flags}' {path}'''
        .format(
            backup='-i{0} '.format(backup) if backup else '-i ',
            options=options,
            limit='/{0}/ '.format(limit) if limit else '',
            before=before,
            after=after,
            flags=flags,
            path=path
        )
    )

    return __salt__['cmd.run_all'](cmd)


def sed_contains(path, text, limit='', flags='g'):
    '''
    Return True if the file at ``path`` contains ``text``. Utilizes sed to
    perform the search (line-wise search).

    Note: the ``p`` flag will be added to any flags you pass in.

    CLI Example::

        salt '*' file.contains /etc/crontab 'mymaintenance.sh'
    '''
    # Largely inspired by Fabric's contrib.files.contains()

    if not os.path.exists(path):
        return False

    before = _sed_esc(str(text), False)
    limit = _sed_esc(str(limit), False)
    options = '-n -r -e'
    if sys.platform == 'darwin':
        options = options.replace('-r', '-E')

    cmd = r"sed {options} '{limit}s/{before}/$/{flags}' {path}".format(
        options=options,
        limit='/{0}/ '.format(limit) if limit else '',
        before=before,
        flags='p{0}'.format(flags),
        path=path)

    result = __salt__['cmd.run'](cmd)

    return bool(result)


def psed(path, before, after, limit='', backup='.bak', flags='gMS',
         escape_all=False, multi=False):
    '''
    Make a simple edit to a file (pure Python version)

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
    flags : ``gMS``
        Flags to modify the search. Valid values are :
            ``g``: Replace all occurrences of the pattern, not just the first.
            ``I``: Ignore case.
            ``L``: Make ``\\w``, ``\\W``, ``\\b``, ``\\B``, ``\\s`` and ``\\S`` dependent on the locale.
            ``M``: Treat multiple lines as a single line.
            ``S``: Make `.` match all characters, including newlines.
            ``U``: Make ``\\w``, ``\\W``, ``\\b``, ``\\B``, ``\\d``, ``\\D``, ``\\s`` and ``\\S`` dependent on Unicode.
            ``X``: Verbose (whitespace is ignored).
    multi: ``False``
        If True, treat the entire file as a single line

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
    multi = bool(multi)

    before = str(before)
    after = str(after)
    before = _sed_esc(before, escape_all)
    # The pattern to replace with does not need to be escaped!!!
    #after = _sed_esc(after, escape_all)
    limit = _sed_esc(limit, escape_all)

    shutil.copy2(path, '{0}{1}'.format(path, backup))

    ofile = salt.utils.fopen(path, 'w')
    with salt.utils.fopen('{0}{1}'.format(path, backup), 'r') as ifile:
        if multi is True:
            for line in ifile.readline():
                ofile.write(_psed(line, before, after, limit, flags))
        else:
            ofile.write(_psed(ifile.read(), before, after, limit, flags))

    ofile.close()


RE_FLAG_TABLE = {'I': re.I,
                 'L': re.L,
                 'M': re.M,
                 'S': re.S,
                 'U': re.U,
                 'X': re.X}


def _psed(text, before, after, limit, flags):
    '''
    Does the actual work for file.psed, so that single lines can be passed in
    '''
    atext = text
    if limit:
        limit = re.compile(limit)
        comps = text.split(limit)
        atext = ''.join(comps[1:])

    count = 1
    if 'g' in flags:
        count = 0
        flags = flags.replace('g', '')

    aflags = 0
    for flag in flags:
        aflags |= RE_FLAG_TABLE[flag]

    before = re.compile(before, flags=aflags)
    text = re.sub(before, after, atext, count=count)

    return text


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
        The character to remove in order to uncomment a line
    backup : ``.bak``
        The file will be backed up before edit with this file extension;
        **WARNING:** each time ``sed``/``comment``/``uncomment`` is called will
        overwrite this backup

    CLI Example::

        salt '*' file.uncomment /etc/hosts.deny 'ALL: PARANOID'

    .. versionadded:: 0.9.5
    '''
    # Largely inspired by Fabric's contrib.files.uncomment()

    return sed(path,
               before=r'^([[:space:]]*){0}'.format(char),
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

    return sed(path,
               before=regex,
               after=r'{0}\1'.format(char),
               backup=backup)


def patch(originalfile, patchfile, options='', dry_run=False):
    '''
    Apply a patch to a file

    Equivalent to::

        patch <options> <originalfile> <patchfile>

    originalfile
        The full path to the file or directory to be patched
    patchfile
        A patch file to apply to ``originalfile``
    options
        Options to pass to patch.

    CLI Example::

        salt '*' file.patch /opt/file.txt /tmp/file.txt.patch

    .. versionadded:: 0.10.4
    '''
    if dry_run:
        if __grains__['kernel'] in ('FreeBSD', 'OpenBSD'):
            dry_run_opt = ' -C'
        else:
            dry_run_opt = ' --dry-run'
    else:
        dry_run_opt = ''
    cmd = 'patch {0}{1} {2} {3}'.format(
        options, dry_run_opt, originalfile, patchfile)
    return __salt__['cmd.run_all'](cmd)


def contains(path, text):
    '''
    Return True if the file at ``path`` contains ``text``

    CLI Example::

        salt '*' file.contains /etc/crontab 'mymaintenance.sh'

    .. versionadded:: 0.9.5
    '''
    if not os.path.exists(path):
        return False

    stripped_text = text.strip()
    try:
        with salt.utils.filebuffer.BufferedReader(path) as breader:
            for chunk in breader:
                if stripped_text in chunk:
                    return True
        return False
    except (IOError, OSError):
        return False


def contains_regex(path, regex, lchar=''):
    '''
    Return True if the given regular expression matches on any line in the text
    of a given file.

    If the lchar argument (leading char) is specified, it
    will strip `lchar` from the left side of each line before trying to match

    CLI Examples::

        salt '*' file.contains_regex /etc/crontab
    '''
    if not os.path.exists(path):
        return False

    try:
        with salt.utils.fopen(path, 'r') as target:
            for line in target:
                if lchar:
                    line = line.lstrip(lchar)
                if re.search(regex, line):
                    return True
            return False
    except (IOError, OSError):
        return False


def contains_regex_multiline(path, regex):
    '''
    Return True if the given regular expression matches anything in the text
    of a given file

    Traverses multiple lines at a time, via the salt BufferedReader (reads in
    chunks)

    CLI Example::

        salt '*' file.contains_regex_multiline /etc/crontab '^maint'
    '''
    if not os.path.exists(path):
        return False

    try:
        with salt.utils.filebuffer.BufferedReader(path) as breader:
            for chunk in breader:
                if re.search(regex, chunk, re.MULTILINE):
                    return True
            return False
    except (IOError, OSError):
        return False


def contains_glob(path, glob):
    '''
    Return True if the given glob matches a string in the named file

    CLI Example::

        salt '*' file.contains_glob /etc/foobar '*cheese*'
    '''
    if not os.path.exists(path):
        return False

    try:
        with salt.utils.filebuffer.BufferedReader(path) as breader:
            for chunk in breader:
                if fnmatch.fnmatch(chunk, glob):
                    return True
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

    with salt.utils.fopen(path, "a") as ofile:
        for line in args:
            ofile.write('{0}\n'.format(line))

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
        if not os.path.exists(name):
            salt.utils.fopen(name, 'a')

        if not atime and not mtime:
            times = None
        elif not mtime and atime:
            times = (atime, time.time())
        elif not atime and mtime:
            times = (time.time(), mtime)
        else:
            times = (atime, mtime)
        os.utime(name, times)

    except TypeError:
        raise SaltInvocationError('atime and mtime must be integers')
    except (IOError, OSError) as exc:
        raise CommandExecutionError(exc.strerror)

    return os.path.exists(name)


def symlink(src, link):
    '''
    Create a symbolic link to a file

    CLI Example::

        salt '*' file.symlink /path/to/file /path/to/link
    '''
    if not os.path.isabs(src):
        raise SaltInvocationError('File path must be absolute.')

    try:
        os.symlink(src, link)
        return True
    except (OSError, IOError):
        raise CommandExecutionError('Could not create "{0}"'.format(link))
    return False


def rename(src, dst):
    '''
    Rename a file or directory

    CLI Example::

        salt '*' file.rename /path/to/src /path/to/dst
    '''
    if not os.path.isabs(src):
        raise SaltInvocationError('File path must be absolute.')

    try:
        os.rename(src, dst)
        return True
    except OSError:
        raise CommandExecutionError('Could not rename "{0}" to "{1}"'.format(src, dst))
    return False


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
    '''
    Remove the named file

    CLI Example::

        salt '*' file.remove /tmp/foo
    '''
    if not os.path.isabs(path):
        raise SaltInvocationError('File path must be absolute.')

    try:
        if os.path.isfile(path) or os.path.islink(path):
            os.remove(path)
            return True
        elif os.path.isdir(path):
            shutil.rmtree(path)
            return True
    except (OSError, IOError):
        raise CommandExecutionError('Could not remove "{0}"'.format(path))
    return False


def directory_exists(path):
    '''
    Tests to see if path is a valid directory.  Returns True/False.

    CLI Example::

        salt '*' file.directory_exists /etc

    '''
    return os.path.isdir(path)


def file_exists(path):
    '''
    Tests to see if path is a valid file.  Returns True/False.

    CLI Example::

        salt '*' file.file_exists /etc/passwd

    '''
    return os.path.isfile(path)


def restorecon(path, recursive=False):
    '''
    Reset the SELinux context on a given path

    CLI Example::

         salt '*' file.restorecon /home/user/.ssh/authorized_keys
    '''
    if recursive:
        cmd = 'restorecon -FR {0}'.format(path)
    else:
        cmd = 'restorecon -F {0}'.format(path)
    return not __salt__['cmd.retcode'](cmd)


def get_selinux_context(path):
    '''
    Get an SELinux context from a given path

    CLI Example::

        salt '*' file.get_selinux_context /etc/hosts
    '''
    out = __salt__['cmd.run']('ls -Z {0}'.format(path))
    return out.split(' ')[4]


def set_selinux_context(path, user=None, role=None, type=None, range=None):
    '''
    Set a specific SELinux label on a given path

    CLI Example::

        salt '*' file.set_selinux_context path <role> <type> <range>
    '''
    if not any((user, role, type, range)):
        return False

    cmd = 'chcon '
    if user:
        cmd += '-u {0} '.format(user)
    if role:
        cmd += '-r {0} '.format(role)
    if type:
        cmd += '-t {0} '.format(type)
    if range:
        cmd += '-l {0} '.format(range)

    cmd += path
    ret = not __salt__['cmd.retcode'](cmd)
    if ret:
        return get_selinux_context(path)
    else:
        return ret


def source_list(source, source_hash, env):
    '''
    Check the source list and return the source to use

    CLI Example::
        salt '*' file.source_list salt://http/httpd.conf '{hash_type: 'md5', 'hsum': <md5sum>}' base
    '''
    if isinstance(source, list):
        # get the master file list
        mfiles = __salt__['cp.list_master'](env)
        mdirs = __salt__['cp.list_master_dirs'](env)
        for single in source:
            if isinstance(single, dict):
                # check the proto, if it is http or ftp then download the file
                # to check, if it is salt then check the master list
                if len(single) != 1:
                    continue
                single_src = next(iter(single))
                single_hash = single[single_src]
                proto = salt._compat.urlparse(single_src).scheme
                if proto == 'salt':
                    if single_src in mfiles:
                        source = single_src
                        break
                elif proto.startswith('http') or proto == 'ftp':
                    dest = salt.utils.mkstemp()
                    fn_ = __salt__['cp.get_url'](single_src, dest)
                    os.remove(fn_)
                    if fn_:
                        source = single_src
                        source_hash = single_hash
                        break
            elif isinstance(single, salt._compat.string_types):
                if single[7:] in mfiles or single[7:] in mdirs:
                    source = single
                    break
    return source, source_hash


def get_managed(
        name,
        template,
        source,
        source_hash,
        user,
        group,
        mode,
        env,
        context,
        defaults,
        **kwargs):
    '''
    Return the managed file data for file.managed

    CLI Example::

        salt '*' file.get_managed /etc/httpd/conf.d/httpd.conf jinja salt://http/httpd.conf '{hash_type: 'md5', 'hsum': <md5sum>}' root root '755' base None None
    '''
    # If the file is a template and the contents is managed
    # then make sure to copy it down and templatize  things.
    sfn = ''
    source_sum = {}
    if template and source:
        sfn = __salt__['cp.cache_file'](source, env)
        if not os.path.exists(sfn):
            return sfn, {}, 'Source file {0} not found'.format(source)
        if template in salt.utils.templates.TEMPLATE_REGISTRY:
            context_dict = defaults if defaults else {}
            if context:
                context_dict.update(context)
            data = salt.utils.templates.TEMPLATE_REGISTRY[template](
                sfn,
                name=name,
                source=source,
                user=user,
                group=group,
                mode=mode,
                env=env,
                context=context_dict,
                salt=__salt__,
                pillar=__pillar__,
                grains=__grains__,
                opts=__opts__,
                **kwargs)
        else:
            return sfn, {}, ('Specified template format {0} is not supported'
                             ).format(template)

        if data['result']:
            sfn = data['data']
            hsum = get_hash(sfn)
            source_sum = {'hash_type': 'md5',
                          'hsum': hsum}
        else:
            __clean_tmp(sfn)
            return sfn, {}, data['data']
    else:
        # Copy the file down if there is a source
        if source:
            if salt._compat.urlparse(source).scheme == 'salt':
                source_sum = __salt__['cp.hash_file'](source, env)
                if not source_sum:
                    return '', {}, 'Source file {0} not found'.format(source)
            elif source_hash:
                protos = ['salt', 'http', 'ftp']
                if salt._compat.urlparse(source_hash).scheme in protos:
                    # The source_hash is a file on a server
                    hash_fn = __salt__['cp.cache_file'](source_hash)
                    if not hash_fn:
                        return '', {}, 'Source hash file {0} not found'.format(
                            source_hash)
                    hash_fn_fopen = salt.utils.fopen(hash_fn, 'r')
                    for line in hash_fn_fopen.read().splitlines():
                        line = line.strip()
                        if ' ' not in line:
                            hashstr = line
                            break
                        elif line.startswith('{0} '.format(name)):
                            hashstr = line.split()[1]
                            break
                    else:
                        hashstr = ''  # NOT FOUND
                    comps = hashstr.split('=')
                    if len(comps) < 2:
                        return '', {}, ('Source hash file {0} contains an '
                                        'invalid hash format, it must be in '
                                        'the format <hash type>=<hash>'
                                        ).format(source_hash)
                    source_sum['hsum'] = comps[1].strip()
                    source_sum['hash_type'] = comps[0].strip()
                else:
                    # The source_hash is a hash string
                    comps = source_hash.split('=')
                    if len(comps) < 2:
                        return '', {}, ('Source hash file {0} contains an '
                                        'invalid hash format, it must be in '
                                        'the format <hash type>=<hash>'
                                        ).format(source_hash)
                    source_sum['hsum'] = comps[1].strip()
                    source_sum['hash_type'] = comps[0].strip()
            else:
                return '', {}, ('Unable to determine upstream hash of'
                                ' source file {0}').format(source)
    return sfn, source_sum, ''


def check_perms(name, ret, user, group, mode):
    '''
    Check the permissions on files and chown if needed

    CLI Example::

        salt '*' file.check_perms /etc/sudoers '{}' root root 400
    '''
    if not ret:
        ret = {'name': name,
               'changes': {},
               'comment': [],
               'result': True}
        orig_comment = ''
    else:
        orig_comment = ret['comment']
        ret['comment'] = []

    # Check permissions
    perms = {}
    perms['luser'] = get_user(name)
    perms['lgroup'] = get_group(name)
    perms['lmode'] = __salt__['config.manage_mode'](get_mode(name))

    # Mode changes if needed
    if mode is not None:
        mode = __salt__['config.manage_mode'](mode)
        if mode != perms['lmode']:
            if __opts__['test'] is True:
                ret['changes']['mode'] = mode
            else:
                set_mode(name, mode)
                if mode != __salt__['config.manage_mode'](get_mode(name)):
                    ret['result'] = False
                    ret['comment'].append(
                        'Failed to change mode to {0}'.format(mode)
                    )
                else:
                    ret['changes']['mode'] = mode
    # user/group changes if needed, then check if it worked
    if user:
        if user != perms['luser']:
            perms['cuser'] = user
    if group:
        if group != perms['lgroup']:
            perms['cgroup'] = group
    if 'cuser' in perms or 'cgroup' in perms:
        if not __opts__['test']:
            if user is None:
                user = perms['luser']
            if group is None:
                group = perms['lgroup']
            try:
                chown(name, user, group)
            except OSError:
                ret['result'] = False

    if user:
        if user != get_user(name):
            if __opts__['test'] is True:
                ret['changes']['user'] = user
            else:
                ret['result'] = False
                ret['comment'].append('Failed to change user to {0}'
                                      .format(user))
        elif 'cuser' in perms:
            ret['changes']['user'] = user
    if group:
        if group != get_group(name):
            if __opts__['test'] is True:
                ret['changes']['group'] = group
            else:
                ret['result'] = False
                ret['comment'].append('Failed to change group to {0}'
                                      .format(group))
        elif 'cgroup' in perms:
            ret['changes']['group'] = group

    if isinstance(orig_comment, basestring):
        if orig_comment:
            ret['comment'].insert(0, orig_comment)
        ret['comment'] = '; '.join(ret['comment'])
    if __opts__['test'] is True and ret['changes']:
        ret['result'] = None
    return ret, perms


def check_managed(
        name,
        source,
        source_hash,
        user,
        group,
        mode,
        template,
        makedirs,
        context,
        defaults,
        env,
        contents=None,
        **kwargs):
    '''
    Check to see what changes need to be made for a file

    CLI Example::

        salt '*' file.check_managed /etc/httpd/conf.d/httpd.conf salt://http/httpd.conf '{hash_type: 'md5', 'hsum': <md5sum>}' root, root, '755' jinja True None None base
    '''
    # If the source is a list then find which file exists
    source, source_hash = source_list(source, source_hash, env)

    sfn = ''
    source_sum = None

    if contents is None:
        # Gather the source file from the server
        sfn, source_sum, comments = get_managed(
            name,
            template,
            source,
            source_hash,
            user,
            group,
            mode,
            env,
            context,
            defaults,
            **kwargs)
        if comments:
            __clean_tmp(sfn)
            return False, comments
    changes = check_file_meta(name, sfn, source, source_sum, user,
                              group, mode, env, template, contents)
    __clean_tmp(sfn)
    if changes:
        log.info(changes)
        comments = ['The following values are set to be changed:\n']
        comments.extend('{0}: {1}\n'.format(key, val) for key, val in changes.iteritems())
        return None, ''.join(comments)
    return True, 'The file {0} is in the correct state'.format(name)


def check_file_meta(
        name,
        sfn,
        source,
        source_sum,
        user,
        group,
        mode,
        env,
        template=None,
        contents=None):
    '''
    Check for the changes in the file metadata.

    CLI Example::

        salt '*' file.check_file_meta /etc/httpd/conf.d/httpd.conf salt://http/httpd.conf '{hash_type: 'md5', 'hsum': <md5sum>}' root, root, '755' base
    '''
    changes = {}
    if not source_sum:
        source_sum = dict()
    lstats = stats(name, source_sum.get('hash_type'), 'md5')
    if not lstats:
        changes['newfile'] = name
        return changes
    if 'hsum' in source_sum:
        if source_sum['hsum'] != lstats['sum']:
            if not sfn and source:
                sfn = __salt__['cp.cache_file'](source, env)
            if sfn:
                if __salt__['config.option']('obfuscate_templates'):
                    changes['diff'] = '<Obfuscated Template>'
                else:
                    # Check to see if the files are bins
                    bdiff = _binary_replace(name, sfn)
                    if bdiff:
                        changes['diff'] = bdiff
                    else:
                        with contextlib.nested(
                                salt.utils.fopen(sfn, 'rb'),
                                salt.utils.fopen(name, 'rb')) as (src, name_):
                            slines = src.readlines()
                            nlines = name_.readlines()
                        changes['diff'] = \
                            ''.join(difflib.unified_diff(nlines, slines))
            else:
                changes['sum'] = 'Checksum differs'

    if contents is not None:
        # Write a tempfile with the static contents
        tmp = salt.utils.mkstemp(text=True)
        with salt.utils.fopen(tmp, 'w') as tmp_:
            tmp_.write(str(contents))
        # Compare the static contents with the named file
        with contextlib.nested(
                salt.utils.fopen(tmp, 'rb'),
                salt.utils.fopen(name, 'rb')) as (src, name_):
            slines = src.readlines()
            nlines = name_.readlines()
        if ''.join(nlines) != ''.join(slines):
            if __salt__['config.option']('obfuscate_templates'):
                changes['diff'] = '<Obfuscated Template>'
            else:
                if salt.utils.istextfile(name):
                    changes['diff'] = \
                        ''.join(difflib.unified_diff(nlines, slines))
                else:
                    changes['diff'] = 'Replace binary file with text file'

    if user is not None and user != lstats['user']:
        changes['user'] = user
    if group is not None and group != lstats['group']:
        changes['group'] = group
    # Normalize the file mode
    smode = __salt__['config.manage_mode'](lstats['mode'])
    mode = __salt__['config.manage_mode'](mode)
    if mode is not None and mode != smode:
        changes['mode'] = mode
    return changes


def get_diff(
        minionfile,
        masterfile,
        env='base'):
    '''
    Return unified diff of file compared to file on master

    CLI Example::

        salt '*' file.get_diff /home/fred/.vimrc salt://users/fred/.vimrc
    '''
    ret = ''

    if not os.path.exists(minionfile):
        ret = 'File {0} does not exist on the minion'.format(minionfile)
        return ret

    sfn = __salt__['cp.cache_file'](masterfile, env)
    if sfn:
        with contextlib.nested(salt.utils.fopen(sfn, 'r'),
                               salt.utils.fopen(minionfile, 'r')) \
                as (src, name_):
            slines = src.readlines()
            nlines = name_.readlines()
        if ''.join(nlines) != ''.join(slines):
            bdiff = _binary_replace(minionfile, sfn)
            if bdiff:
                ret += bdiff
            else:
                ret += ''.join(difflib.unified_diff(nlines, slines,
                                                    minionfile, masterfile))
    else:
        ret = 'Failed to copy file from master'

    return ret


def manage_file(name,
                sfn,
                ret,
                source,
                source_sum,
                user,
                group,
                mode,
                env,
                backup,
                template=None,
                show_diff=True,
                contents=None):
    '''
    Checks the destination against what was retrieved with get_managed and
    makes the appropriate modifications (if necessary).

    CLI Example::

        salt '*' file.manage_file /etc/httpd/conf.d/httpd.conf '{}' salt://http/httpd.conf '{hash_type: 'md5', 'hsum': <md5sum>}' root root '755' base ''
    '''
    if not ret:
        ret = {'name': name,
               'changes': {},
               'comment': '',
               'result': True}

    # Check changes if the target file exists
    if os.path.isfile(name):
        # Only test the checksums on files with managed contents
        if source:
            name_sum = get_hash(name, source_sum['hash_type'])

        # Check if file needs to be replaced
        if source and source_sum['hsum'] != name_sum:
            if not sfn:
                sfn = __salt__['cp.cache_file'](source, env)
            if not sfn:
                return _error(
                    ret, 'Source file {0} not found'.format(source))
            # If the downloaded file came from a non salt server source verify
            # that it matches the intended sum value
            if salt._compat.urlparse(source).scheme != 'salt':
                dl_sum = get_hash(sfn, source_sum['hash_type'])
                if dl_sum != source_sum['hsum']:
                    ret['comment'] = ('File sum set for file {0} of {1} does '
                                      'not match real sum of {2}'
                                      ).format(name,
                                               source_sum['hsum'],
                                               dl_sum)
                    ret['result'] = False
                    return ret

            # Print a diff equivalent to diff -u old new
            if __salt__['config.option']('obfuscate_templates'):
                ret['changes']['diff'] = '<Obfuscated Template>'
            elif not show_diff:
                ret['changes']['diff'] = '<show_diff=False>'
            else:
                # Check to see if the files are bins
                bdiff = _binary_replace(name, sfn)
                if bdiff:
                    ret['changes']['diff'] = bdiff
                else:
                    with contextlib.nested(
                            salt.utils.fopen(sfn, 'rb'),
                            salt.utils.fopen(name, 'rb')) as (src, name_):
                        slines = src.readlines()
                        nlines = name_.readlines()
                    ret['changes']['diff'] = \
                        ''.join(difflib.unified_diff(nlines, slines))

            # Pre requisites are met, and the file needs to be replaced, do it
            try:
                salt.utils.copyfile(sfn,
                                    name,
                                    __salt__['config.backup_mode'](backup),
                                    __opts__['cachedir'])
            except IOError:
                __clean_tmp(sfn)
                return _error(
                    ret, 'Failed to commit change, permission error')

        if contents is not None:
            # Write the static contents to a temporary file
            tmp = salt.utils.mkstemp(text=True)
            with salt.utils.fopen(tmp, 'w') as tmp_:
                tmp_.write(str(contents))

            # Compare contents of files to know if we need to replace
            with contextlib.nested(
                    salt.utils.fopen(tmp, 'rb'),
                    salt.utils.fopen(name, 'rb')) as (src, name_):
                slines = src.readlines()
                nlines = name_.readlines()
                different = ''.join(slines) != ''.join(nlines)

            if different:
                if __salt__['config.option']('obfuscate_templates'):
                    ret['changes']['diff'] = '<Obfuscated Template>'
                elif not show_diff:
                    ret['changes']['diff'] = '<show_diff=False>'
                else:
                    if salt.utils.istextfile(name):
                        ret['changes']['diff'] = \
                            ''.join(difflib.unified_diff(nlines, slines))
                    else:
                        ret['changes']['diff'] = \
                            'Replace binary file with text file'

                # Pre requisites are met, the file needs to be replaced, do it
                try:
                    salt.utils.copyfile(tmp,
                                        name,
                                        __salt__['config.backup_mode'](backup),
                                        __opts__['cachedir'])
                except IOError:
                    __clean_tmp(tmp)
                    return _error(
                        ret, 'Failed to commit change, permission error')
            __clean_tmp(tmp)

        ret, perms = check_perms(name, ret, user, group, mode)

        if ret['changes']:
            ret['comment'] = 'File {0} updated'.format(name)

        elif not ret['changes'] and ret['result']:
            ret['comment'] = 'File {0} is in the correct state'.format(name)
        __clean_tmp(sfn)
        return ret
    else:
        # Only set the diff if the file contents is managed
        if source:
            # It is a new file, set the diff accordingly
            ret['changes']['diff'] = 'New file'
            # Apply the new file
            if not sfn:
                sfn = __salt__['cp.cache_file'](source, env)
            if not sfn:
                return _error(
                    ret, 'Source file {0} not found'.format(source))
            # If the downloaded file came from a non salt server source verify
            # that it matches the intended sum value
            if salt._compat.urlparse(source).scheme != 'salt':
                dl_sum = get_hash(sfn, source_sum['hash_type'])
                if dl_sum != source_sum['hsum']:
                    ret['comment'] = ('File sum set for file {0} of {1} does '
                                      'not match real sum of {2}'
                                      ).format(name,
                                               source_sum['hsum'],
                                               dl_sum)
                    ret['result'] = False
                    return ret

            if not os.path.isdir(os.path.dirname(name)):
                if makedirs:
                    makedirs(name, user=user, group=group, mode=mode)
                else:
                    __clean_tmp(sfn)
                    return _error(ret, 'Parent directory not present')
        else:
            if not os.path.isdir(os.path.dirname(name)):
                if makedirs:
                    makedirs(name, user=user, group=group, mode=mode)
                else:
                    __clean_tmp(sfn)
                    return _error(ret, 'Parent directory not present')

            # Create the file, user rw-only if mode will be set to prevent
            # a small security race problem before the permissions are set
            if mode:
                current_umask = os.umask(63)

            # Create a new file when test is False and source is None
            if contents is None:
                if not __opts__['test']:
                    if touch(name):
                        ret['changes']['new'] = 'file {0} created'.format(name)
                        ret['comment'] = 'Empty file'
                    else:
                        return _error(
                            ret, 'Empty file {0} not created'.format(name)
                        )
            else:
                if not __opts__['test']:
                    if touch(name):
                        ret['changes']['diff'] = 'New file'
                    else:
                        return _error(
                            ret, 'File {0} not created'.format(name)
                        )

            if mode:
                os.umask(current_umask)

        if contents is not None:
            # Write the static contents to a temporary file
            tmp = salt.utils.mkstemp(text=True)
            with salt.utils.fopen(tmp, 'w') as tmp_:
                tmp_.write(str(contents))
            # Copy into place
            salt.utils.copyfile(tmp,
                                name,
                                __salt__['config.backup_mode'](backup),
                                __opts__['cachedir'])
            __clean_tmp(tmp)
        # Now copy the file contents if there is a source file
        elif sfn:
            salt.utils.copyfile(sfn,
                                name,
                                __salt__['config.backup_mode'](backup),
                                __opts__['cachedir'])
            __clean_tmp(sfn)

        # Check and set the permissions if necessary
        ret, perms = check_perms(name, ret, user, group, mode)

        if not ret['comment']:
            ret['comment'] = 'File ' + name + ' updated'

        if __opts__['test']:
            ret['comment'] = 'File ' + name + ' not updated'
        elif not ret['changes'] and ret['result']:
            ret['comment'] = 'File ' + name + ' is in the correct state'
        __clean_tmp(sfn)
        return ret


def mkdir(dir_path, user=None, group=None, mode=None):
    '''
    Ensure that a directory is available.

    CLI Example::

        salt '*' file.mkdir /opt/jetty/context
    '''
    directory = os.path.normpath(dir_path)

    if not os.path.isdir(directory):
        # If a caller such as managed() is invoked  with makedirs=True, make
        # sure that any created dirs are created with the same user and group
        # to follow the principal of least surprise method.
        makedirs_perms(directory, user, group, mode)


def makedirs(path, user=None, group=None, mode=None):
    '''
    Ensure that the directory containing this path is available.

    CLI Example::

        salt '*' file.makedirs /opt/code
    '''
    # walk up the directory structure until we find the first existing
    # directory
    dirname = os.path.normpath(os.path.dirname(path))

    if os.path.isdir(dirname):
        # There's nothing for us to do
        return 'Directory {0!r} already exists'.format(path)

    if os.path.exists(dirname):
        return 'The path {0!r} already exists and is not a directory'.format(
            path
        )

    directories_to_create = []
    while True:
        if os.path.isdir(dirname):
            break

        directories_to_create.append(dirname)
        dirname = os.path.dirname(dirname)

    # create parent directories from the topmost to the most deeply nested one
    directories_to_create.reverse()
    for directory_to_create in directories_to_create:
        # all directories have the user, group and mode set!!
        mkdir(directory_to_create, user=user, group=group, mode=mode)


def makedirs_perms(name, user=None, group=None, mode='0755'):
    '''
    Taken and modified from os.makedirs to set user, group and mode for each
    directory created.

    CLI Example::

        salt '*' file.makedirs_perms /opt/code
    '''
    path = os.path
    head, tail = path.split(name)
    if not tail:
        head, tail = path.split(head)
    if head and tail and not path.exists(head):
        try:
            makedirs_perms(head, user, group, mode)
        except OSError as exc:
            # be happy if someone already created the path
            if exc.errno != errno.EEXIST:
                raise
        if tail == os.curdir:  # xxx/newdir/. exists if xxx/newdir exists
            return
    os.mkdir(name)
    check_perms(name,
                None,
                user,
                group,
                int('{0}'.format(mode)) if mode else None)
