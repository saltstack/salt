# -*- coding: utf-8 -*-
'''
Manage information about regular files, directories,
and special files on the minion, set/read user,
group, mode, and data
'''

# TODO: We should add the capability to do u+r type operations here
# some time in the future

from __future__ import print_function

# Import python libs
import contextlib  # For < 2.7 compat
import datetime
import difflib
import errno
import fileinput
import fnmatch
import getpass
import hashlib
import itertools
import logging
import operator
import os
import re
import shutil
import stat
import sys
import tempfile
import time

try:
    import grp
    import pwd
except ImportError:
    pass

# Import salt libs
import salt.utils
import salt.utils.find
import salt.utils.filebuffer
import salt.utils.atomicfile
from salt.exceptions import CommandExecutionError, SaltInvocationError
import salt._compat

log = logging.getLogger(__name__)

HASHES = [
            ['sha512', 128],
            ['sha384', 96],
            ['sha256', 64],
            ['sha224', 56],
            ['sha1', 40],
            ['md5', 32],
         ]


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
        # Don't remove if it exists in file_roots (any saltenv)
        all_roots = itertools.chain.from_iterable(
                __opts__['file_roots'].itervalues())
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


def _get_bkroot():
    '''
    Get the location of the backup dir in the minion cache
    '''
    # Get the cachedir from the minion config
    return os.path.join(__salt__['config.get']('cachedir'), 'file_backup')


def gid_to_group(gid):
    '''
    Convert the group id to the group name on this system

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

        salt '*' file.group_to_gid root
    '''
    if not group:
        return ''
    try:
        return grp.getgrnam(group).gr_gid
    except KeyError:
        return ''


def get_gid(path, follow_symlinks=True):
    '''
    Return the id of the group that owns a given file

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_gid /etc/passwd

    .. versionchanged:: 0.16.4
        ``follow_symlinks`` option added
    '''
    if not os.path.exists(path):
        try:
            # Broken symlinks will return false, but still have a uid and gid
            return os.lstat(path).st_gid
        except OSError:
            pass
        return -1
    return os.stat(path).st_gid if follow_symlinks else os.lstat(path).st_gid


def get_group(path, follow_symlinks=True):
    '''
    Return the group that owns a given file

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_group /etc/passwd

    .. versionchanged:: 0.16.4
        ``follow_symlinks`` option added
    '''
    gid = get_gid(path, follow_symlinks)
    if gid == -1:
        return False
    return gid_to_group(gid)


def uid_to_user(uid):
    '''
    Convert a uid to a user name

    CLI Example:

    .. code-block:: bash

        salt '*' file.uid_to_user 0
    '''
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return ''


def user_to_uid(user):
    '''
    Convert user name to a uid

    CLI Example:

    .. code-block:: bash

        salt '*' file.user_to_uid root
    '''
    if not user:
        user = getpass.getuser()
    try:
        return pwd.getpwnam(user).pw_uid
    except KeyError:
        return ''


def get_uid(path, follow_symlinks=True):
    '''
    Return the id of the user that owns a given file

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_uid /etc/passwd

    .. versionchanged:: 0.16.4
        ``follow_symlinks`` option added
    '''
    if not os.path.exists(path):
        try:
            # Broken symlinks will return false, but still have a uid and gid
            return os.lstat(path).st_uid
        except OSError:
            pass
        return -1
    return os.stat(path).st_uid if follow_symlinks else os.lstat(path).st_uid


def get_user(path, follow_symlinks=True):
    '''
    Return the user that owns a given file

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_user /etc/passwd

    .. versionchanged:: 0.16.4
        ``follow_symlinks`` option added
    '''
    uid = get_uid(path, follow_symlinks)
    if uid == -1:
        return False
    return uid_to_user(uid)


def get_mode(path):
    '''
    Return the mode of a file

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

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
        try:
            # Broken symlinks will return false, but still need to be chowned
            return os.lchown(path, uid, gid)
        except OSError:
            pass
        err += 'File not found'
    if err:
        return err
    return os.chown(path, uid, gid)


def chgrp(path, group):
    '''
    Change the group of a file

    CLI Example:

    .. code-block:: bash

        salt '*' file.chgrp /etc/passwd root
    '''
    user = get_user(path)
    return chown(path, user, group)


def get_sum(path, form='md5'):
    '''
    Return the sum for the given file, default is md5, sha1, sha224, sha256,
    sha384, sha512 are supported

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

        salt '*' file.check_hash /etc/fstab md5=<md5sum>
    '''
    hash_parts = hash.split('=', 1)
    if len(hash_parts) != 2:
        raise ValueError('Bad hash format: {0!r}'.format(hash))
    hash_form, hash_value = hash_parts
    return get_hash(path, hash_form) == hash_value


def find(path, **kwargs):
    '''
    Approximate the Unix ``find(1)`` command and return a list of paths that
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

        [<num>w] [<num>d] [<num>h] [<num>m] [<num>s]

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

    CLI Examples:

    .. code-block:: bash

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


def sed(path,
        before,
        after,
        limit='',
        backup='.bak',
        options='-r -e',
        flags='g',
        escape_all=False,
        negate_match=False):
    '''
    .. deprecated:: 0.17.0
       Use :py:func:`~salt.modules.file.replace` instead.

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
    negate_match : False
        Negate the search command (``!``)

        .. versionadded:: 0.17.0

    Forward slashes and single quotes will be escaped automatically in the
    ``before`` and ``after`` patterns.

    CLI Example:

    .. code-block:: bash

        salt '*' file.sed /etc/httpd/httpd.conf 'LogLevel warn' 'LogLevel info'
    '''
    # Largely inspired by Fabric's contrib.files.sed()
    # XXX:dc: Do we really want to always force escaping?
    #

    if not os.path.exists(path):
        return False

    # Mandate that before and after are strings
    before = str(before)
    after = str(after)
    before = _sed_esc(before, escape_all)
    after = _sed_esc(after, escape_all)
    limit = _sed_esc(limit, escape_all)
    if sys.platform == 'darwin':
        options = options.replace('-r', '-E')

    cmd = (
        r'''sed {backup}{options} '{limit}{negate_match}s/{before}/{after}/{flags}' {path}'''
        .format(
            backup='-i{0} '.format(backup) if backup else '-i ',
            options=options,
            limit='/{0}/ '.format(limit) if limit else '',
            before=before,
            after=after,
            flags=flags,
            path=path,
            negate_match='!' if negate_match else '',
        )
    )

    return __salt__['cmd.run_all'](cmd)


def sed_contains(path,
                 text,
                 limit='',
                 flags='g'):
    '''
    .. deprecated:: 0.17.0
       Use :func:`search` instead.

    Return True if the file at ``path`` contains ``text``. Utilizes sed to
    perform the search (line-wise search).

    Note: the ``p`` flag will be added to any flags you pass in.

    CLI Example:

    .. code-block:: bash

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


def psed(path,
         before,
         after,
         limit='',
         backup='.bak',
         flags='gMS',
         escape_all=False,
         multi=False):
    '''
    .. deprecated:: 0.17.0
       Use :py:func:`~salt.modules.file.replace` instead.

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
        Flags to modify the search. Valid values are:
          - ``g``: Replace all occurrences of the pattern, not just the first.
          - ``I``: Ignore case.
          - ``L``: Make ``\\w``, ``\\W``, ``\\b``, ``\\B``, ``\\s`` and ``\\S``
            dependent on the locale.
          - ``M``: Treat multiple lines as a single line.
          - ``S``: Make `.` match all characters, including newlines.
          - ``U``: Make ``\\w``, ``\\W``, ``\\b``, ``\\B``, ``\\d``, ``\\D``,
            ``\\s`` and ``\\S`` dependent on Unicode.
          - ``X``: Verbose (whitespace is ignored).
    multi: ``False``
        If True, treat the entire file as a single line

    Forward slashes and single quotes will be escaped automatically in the
    ``before`` and ``after`` patterns.

    CLI Example:

    .. code-block:: bash

        salt '*' file.sed /etc/httpd/httpd.conf 'LogLevel warn' 'LogLevel info'
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


def _psed(text,
          before,
          after,
          limit,
          flags):
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


def uncomment(path,
              regex,
              char='#',
              backup='.bak'):
    '''
    .. deprecated:: 0.17.0
       Use :py:func:`~salt.modules.file.replace` instead.

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

    CLI Example:

    .. code-block:: bash

        salt '*' file.uncomment /etc/hosts.deny 'ALL: PARANOID'
    '''
    # Largely inspired by Fabric's contrib.files.uncomment()

    return sed(path,
               before=r'^([[:space:]]*){0}'.format(char),
               after=r'\1',
               limit=regex.lstrip('^'),
               backup=backup)


def comment(path,
            regex,
            char='#',
            backup='.bak'):
    '''
    .. deprecated:: 0.17.0
       Use :py:func:`~salt.modules.file.replace` instead.

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

    CLI Example:

    .. code-block:: bash

        salt '*' file.comment /etc/modules pcspkr
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


def _get_flags(flags):
    '''
    Return an integer appropriate for use as a flag for the re module from a
    list of human-readable strings

    >>> _get_flags(['MULTILINE', 'IGNORECASE'])
    10
    '''
    if isinstance(flags, list):
        _flags_acc = []
        for flag in flags:
            _flag = getattr(re, flag.upper())

            if not isinstance(_flag, int):
                raise SaltInvocationError(
                    'Invalid re flag given: {0}'.format(flag)
                )

            _flags_acc.append(_flag)

        return reduce(operator.__or__, _flags_acc)

    return flags


def replace(path,
            pattern,
            repl,
            count=0,
            flags=0,
            bufsize=1,
            backup='.bak',
            dry_run=False,
            search_only=False,
            show_changes=True,
        ):
    '''
    Replace occurances of a pattern in a file

    .. versionadded:: 0.17.0

    This is a pure Python implementation that wraps Python's :py:func:`~re.sub`.

    :param path: Filesystem path to the file to be edited
    :param pattern: The PCRE search
    :param repl: The replacement text
    :param count: Maximum number of pattern occurrences to be replaced
    :param flags: A list of flags defined in the :ref:`re module documentation
        <contents-of-module-re>`. Each list item should be a string that will
        correlate to the human-friendly flag name. E.g., ``['IGNORECASE',
        'MULTILINE']``. Note: multiline searches must specify ``file`` as the
        ``bufsize`` argument below.

    :type flags: list or int
    :param bufsize: How much of the file to buffer into memory at once. The
        default value ``1`` processes one line at a time. The special value
        ``file`` may be specified which will read the entire file into memory
        before processing. Note: multiline searches must specify ``file``
        buffering.
    :type bufsize: int or str
    :param backup: The file extension to use for a backup of the file before
        editing. Set to ``False`` to skip making a backup.
    :param dry_run: Don't make any edits to the file
    :param search_only: Just search for the pattern; ignore the replacement;
        stop on the first match
    :param show_changes: Output a unified diff of the old file and the new
        file. If ``False`` return a boolean if any changes were made.
        Note: using this option will store two copies of the file in-memory
        (the original version and the edited version) in order to generate the
        diff.

    :rtype: bool or str

    CLI Example:

    .. code-block:: bash

        salt '*' file.replace /etc/httpd/httpd.conf 'LogLevel warn' 'LogLevel info'
        salt '*' file.replace /some/file 'before' 'after' flags='[MULTILINE, IGNORECASE]'
    '''
    if not os.path.exists(path):
        raise SaltInvocationError('File not found: {0}'.format(path))

    if not salt.utils.istextfile(path):
        raise SaltInvocationError(
            'Cannot perform string replacements on a binary file: {0}'
            .format(path)
        )

    flags_num = _get_flags(flags)
    cpattern = re.compile(pattern, flags_num)
    if bufsize == 'file':
        bufsize = os.path.getsize(path)

    # Search the file; track if any changes have been made for the return val
    has_changes = False
    orig_file = []  # used if show_changes
    new_file = []  # used if show_changes
    if not salt.utils.is_windows():
        pre_user = get_user(path)
        pre_group = get_group(path)
        pre_mode = __salt__['config.manage_mode'](get_mode(path))

    # Avoid TypeErrors by forcing repl to be a string
    repl = str(repl)
    for line in fileinput.input(path,
                                inplace=not dry_run,
                                backup=False if dry_run else backup,
                                bufsize=bufsize,
                                mode='rb'):

        if search_only:
            # Just search; bail as early as a match is found
            result = re.search(cpattern, line)

            if result:
                return True
        else:
            result = re.sub(cpattern, repl, line, count)

            # Identity check each potential change until one change is made
            if has_changes is False and not result is line:
                has_changes = True

            if show_changes:
                orig_file.append(line)
                new_file.append(result)

            if not dry_run:
                print(result, end='', file=sys.stdout)

    if not dry_run and not salt.utils.is_windows():
        check_perms(path, None, pre_user, pre_group, pre_mode)

    if show_changes:
        return ''.join(difflib.unified_diff(orig_file, new_file))

    return has_changes


def blockreplace(path,
        marker_start='#-- start managed zone --',
        marker_end='#-- end managed zone --',
        content='',
        append_if_not_found=False,
        prepend_if_not_found=False,
        backup='.bak',
        dry_run=False,
        show_changes=True,
        ):
    '''
    Replace content of a text block in a file, delimited by line markers

    .. versionadded:: Hydrogen

    A block of content delimited by comments can help you manage several lines
    entries without worrying about old entries removal.

    .. note::

        This function will store two copies of the file in-memory (the original
        version and the edited version) in order to detect changes and only
        edit the targeted file if necessary.

    path
        Filesystem path to the file to be edited

    marker_start
        The line content identifying a line as the start of the content block.
        Note that the whole line containing this marker will be considered, so
        whitespaces or extra content before or after the marker is included in
        final output

    marker_end
        The line content identifying a line as the end of the content block.
        Note that the whole line containing this marker will be considered, so
        whitespaces or extra content before or after the marker is included in
        final output

    content
        The content to be used between the two lines identified by marker_start
        and marker_stop.

    append_if_not_found : False
        If markers are not found and set to ``True`` then, the markers and
        content will be appended to the file.

    prepend_if_not_found : False
        If markers are not found and set to ``True`` then, the markers and
        content will be prepended to the file.


    backup
        The file extension to use for a backup of the file if any edit is made.
        Set to ``False`` to skip making a backup.

    dry_run
        Don't make any edits to the file.

    show_changes
        Output a unified diff of the old file and the new file. If ``False``,
        return a boolean if any changes were made.

    CLI Example:

    .. code-block:: bash

        salt '*' file.blockreplace /etc/hosts '#-- start managed zone foobar : DO NOT EDIT --' \\
        '#-- end managed zone foobar --' $'10.0.1.1 foo.foobar\\n10.0.1.2 bar.foobar' True

    '''
    if not os.path.exists(path):
        raise SaltInvocationError('File not found: {0}'.format(path))

    if append_if_not_found and prepend_if_not_found:
        raise SaltInvocationError('Choose between append or prepend_if_not_found')

    if not salt.utils.istextfile(path):
        raise SaltInvocationError(
            'Cannot perform string replacements on a binary file: {0}'
            .format(path)
        )

    # Search the file; track if any changes have been made for the return val
    has_changes = False
    orig_file = []
    new_file = []
    in_block = False
    old_content = ''
    done = False
    # we do not use in_place editing to avoid file attrs modifications when
    # no changes are required and to avoid any file access on a partially
    # written file.
    # we could also use salt.utils.filebuffer.BufferedReader
    for line in fileinput.input(path,
            inplace=False, backup=False,
            bufsize=1, mode='rb'):

        result = line

        if marker_start in line:
            # managed block start found, start recording
            in_block = True

        else:
            if in_block:
                if marker_end in line:
                    # end of block detected
                    in_block = False

                    # push new block content in file
                    for cline in content.split("\n"):
                        new_file.append(cline + "\n")

                    done = True

                else:
                    # remove old content, but keep a trace
                    old_content += line
                    result = None
        # else: we are not in the marked block, keep saving things

        orig_file.append(line)
        if result is not None:
            new_file.append(result)
    # end for. If we are here without block managment we maybe have some problems,
    # or we need to initialise the marked block

    if in_block:
        # unterminated block => bad, always fail
        raise CommandExecutionError(
            'Unterminated marked block. End of file reached before marker_end.'
        )

    if not done:
        if prepend_if_not_found:
            # add the markers and content at the beginning of file
            new_file.insert(0, marker_end + '\n')
            new_file.insert(0, content + '\n')
            new_file.insert(0, marker_start + '\n')
            done = True
        elif append_if_not_found:
            # add the markers and content at the end of file
            new_file.append(marker_start + '\n')
            new_file.append(content + '\n')
            new_file.append(marker_end + '\n')
            done = True
        else:
            raise CommandExecutionError(
                'Cannot edit marked block. Markers were not found in file.'
            )

    if done:
        diff = ''.join(difflib.unified_diff(orig_file, new_file))
        has_changes = diff is not ''
        if has_changes and not dry_run:
            # changes detected
            # backup old content
            if backup is not False:
                shutil.copy2(path, '{0}{1}'.format(path, backup))

            # backup file attrs
            perms = {}
            perms['user'] = get_user(path)
            perms['group'] = get_group(path)
            perms['mode'] = __salt__['config.manage_mode'](get_mode(path))

            # write new content in the file while avoiding partial reads
            f = salt.utils.atomicfile.atomic_open(path, 'wb')
            for line in new_file:
                f.write(line)
            f.close()

            # this may have overwritten file attrs
            check_perms(path,
                    None,
                    perms['user'],
                    perms['group'],
                    perms['mode'])

        if show_changes:
            return diff

    return has_changes


def search(path,
        pattern,
        flags=0,
        bufsize=1,
        ):
    '''
    Search for occurances of a pattern in a file

    .. versionadded:: 0.17.0

    Params are identical to :py:func:`~salt.modules.file.replace`.

    CLI Example:

    .. code-block:: bash

        salt '*' file.search /etc/crontab 'mymaintenance.sh'
    '''
    # This function wraps file.replace on purpose in order to enforce
    # consistent usage, compatible regex's, expected behavior, *and* bugs. :)
    # Any enhancements or fixes to one should affect the other.
    return replace(path,
            pattern,
            '',
            flags=flags,
            bufsize=bufsize,
            dry_run=True,
            search_only=True,
            show_changes=False)


def patch(originalfile, patchfile, options='', dry_run=False):
    '''
    .. versionadded:: 0.10.4

    Apply a patch to a file

    Equivalent to::

        patch <options> <originalfile> <patchfile>

    originalfile
        The full path to the file or directory to be patched
    patchfile
        A patch file to apply to ``originalfile``
    options
        Options to pass to patch.

    CLI Example:

    .. code-block:: bash

        salt '*' file.patch /opt/file.txt /tmp/file.txt.patch
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
    .. deprecated:: 0.17.0
       Use :func:`search` instead.

    Return ``True`` if the file at ``path`` contains ``text``

    CLI Example:

    .. code-block:: bash

        salt '*' file.contains /etc/crontab 'mymaintenance.sh'
    '''
    if not os.path.exists(path):
        return False

    stripped_text = str(text).strip()
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
    .. deprecated:: 0.17.0
       Use :func:`search` instead.

    Return True if the given regular expression matches on any line in the text
    of a given file.

    If the lchar argument (leading char) is specified, it
    will strip `lchar` from the left side of each line before trying to match

    CLI Example:

    .. code-block:: bash

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
    .. deprecated:: 0.17.0
       Use :func:`search` instead.

    Return True if the given regular expression matches anything in the text
    of a given file

    Traverses multiple lines at a time, via the salt BufferedReader (reads in
    chunks)

    CLI Example:

    .. code-block:: bash

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
    .. deprecated:: 0.17.0
       Use :func:`search` instead.

    Return True if the given glob matches a string in the named file

    CLI Example:

    .. code-block:: bash

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
    .. versionadded:: 0.9.5

    Append text to the end of a file

    CLI Example:

    .. code-block:: bash

        salt '*' file.append /etc/motd \\
                "With all thine offerings thou shalt offer salt." \\
                "Salt is what makes things taste bad when it isn't in them."
    '''
    # Largely inspired by Fabric's contrib.files.append()

    with salt.utils.fopen(path, "r+") as ofile:
        # Make sure we have a newline at the end of the file
        try:
            ofile.seek(-1, os.SEEK_END)
        except IOError as exc:
            if exc.errno == errno.EINVAL:
                # Empty file, simply append lines at the beginning of the file
                pass
            else:
                raise
        else:
            if ofile.read(1) != '\n':
                ofile.seek(0, os.SEEK_END)
                ofile.write('\n')
            else:
                ofile.seek(0, os.SEEK_END)
        # Append lines
        for line in args:
            ofile.write('{0}\n'.format(line))

    return 'Wrote {0} lines to "{1}"'.format(len(args), path)


def touch(name, atime=None, mtime=None):
    '''
    .. versionadded:: 0.9.5

    Just like the ``touch`` command, create a file if it doesn't exist or
    simply update the atime and mtime if it already does.

    atime:
        Access time in Unix epoch time
    mtime:
        Last modification in Unix epoch time

    CLI Example:

    .. code-block:: bash

        salt '*' file.touch /var/log/emptyfile
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


def seek_read(path, size, offset):
    '''
    Seek to a position on a file and write to it

    .. versionadded:: Hydrogen

    CLI Example:

    .. code-block:: bash

        salt '*' file.seek_read /path/to/file 4096 0
    '''
    seek_fh = os.open(path, os.O_RDONLY)
    os.lseek(seek_fh, int(offset), 0)
    data = os.read(seek_fh, int(size))
    os.close(seek_fh)
    return data


def seek_write(path, data, offset):
    '''
    Seek to a position on a file and write to it

    .. versionadded:: Hydrogen

    CLI Example:

    .. code-block:: bash

        salt '*' file.seek_write /path/to/file 'some data' 4096
    '''
    seek_fh = os.open(path, os.O_WRONLY)
    os.lseek(seek_fh, int(offset), 0)
    ret = os.write(seek_fh, data)
    os.fsync(seek_fh)
    os.close(seek_fh)
    return ret


def truncate(path, length):
    '''
    Seek to a position on a file and write to it

    .. versionadded:: Hydrogen

    CLI Example:

    .. code-block:: bash

        salt '*' file.truncate /path/to/file 512
    '''
    seek_fh = open(path, 'r+')
    seek_fh.truncate(int(length))
    seek_fh.close()


def link(src, link):
    '''
    Create a hard link to a file

    .. versionadded:: Hydrogen

    CLI Example:

    .. code-block:: bash

        salt '*' file.link /path/to/file /path/to/link
    '''
    if not os.path.isabs(src):
        raise SaltInvocationError('File path must be absolute.')

    try:
        os.link(src, link)
        return True
    except (OSError, IOError):
        raise CommandExecutionError('Could not create {0!r}'.format(link))
    return False


def symlink(src, link):
    '''
    Create a symbolic link to a file

    CLI Example:

    .. code-block:: bash

        salt '*' file.symlink /path/to/file /path/to/link
    '''
    if not os.path.isabs(src):
        raise SaltInvocationError('File path must be absolute.')

    try:
        os.symlink(src, link)
        return True
    except (OSError, IOError):
        raise CommandExecutionError('Could not create {0!r}'.format(link))
    return False


def rename(src, dst):
    '''
    Rename a file or directory

    CLI Example:

    .. code-block:: bash

        salt '*' file.rename /path/to/src /path/to/dst
    '''
    if not os.path.isabs(src):
        raise SaltInvocationError('File path must be absolute.')

    try:
        os.rename(src, dst)
        return True
    except OSError:
        raise CommandExecutionError(
            'Could not rename {0!r} to {1!r}'.format(src, dst)
        )
    return False


def copy(src, dst):
    '''
    Copy a file or directory

    CLI Example:

    .. code-block:: bash

        salt '*' file.copy /path/to/src /path/to/dst
    '''
    if not os.path.isabs(src):
        raise SaltInvocationError('File path must be absolute.')

    if not salt.utils.is_windows():
        pre_user = get_user(src)
        pre_group = get_group(src)
        pre_mode = __salt__['config.manage_mode'](get_mode(src))

    try:
        shutil.copyfile(src, dst)
    except OSError:
        raise CommandExecutionError(
            'Could not copy {0!r} to {1!r}'.format(src, dst)
        )

    if not salt.utils.is_windows():
        check_perms(dst, None, pre_user, pre_group, pre_mode)
    return True


def lstat(path):
    '''
    Returns the lstat attributes for the given file or dir. Does not support
    symbolic links.

    CLI Example:

    .. versionadded:: Hydrogen

    .. code-block:: bash

        salt '*' file.lstat /path/to/file
    '''
    if not os.path.isabs(path):
        raise SaltInvocationError('Path to file must be absolute.')

    try:
        lst = os.lstat(path)
        return dict((key, getattr(lst, key)) for key in ('st_atime', 'st_ctime',
            'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))
    except Exception:
        return {}


def access(path, mode):
    '''
    Test whether the Salt process has the specified access to the file. One of
    the following modes must be specified:

        f: Test the existence of the path
        r: Test the readability of the path
        w: Test the writability of the path
        x: Test whether the path can be executed

    .. versionadded:: Hydrogen

    CLI Example:

    .. code-block:: bash

        salt '*' file.access /path/to/file f
        salt '*' file.access /path/to/file x
    '''
    if not os.path.isabs(path):
        raise SaltInvocationError('Path to link must be absolute.')

    modes = {'f': os.F_OK,
             'r': os.R_OK,
             'w': os.W_OK,
             'x': os.X_OK}

    if mode in modes:
        return os.access(path, modes[mode])
    elif mode in modes.values():
        return os.access(path, mode)
    else:
        raise SaltInvocationError('Invalid mode specified.')


def readlink(path):
    '''
    Return the path that a symlink points to

    .. versionadded:: Hydrogen

    CLI Example:

    .. code-block:: bash

        salt '*' file.readlink /path/to/link
    '''
    if not os.path.isabs(path):
        raise SaltInvocationError('Path to link must be absolute.')

    if not os.path.islink(path):
        raise SaltInvocationError('A valid link was not specified.')

    return os.readlink(path)


def readdir(path):
    '''
    Return a list containing the contents of a directory

    .. versionadded:: Hydrogen

    CLI Example:

    .. code-block:: bash

        salt '*' file.readdir /path/to/dir/
    '''
    if not os.path.isabs(path):
        raise SaltInvocationError('Dir path must be absolute.')

    if not os.path.isdir(path):
        raise SaltInvocationError('A valid directory was not specified.')

    dirents = ['.', '..']
    dirents.extend(os.listdir(path))
    return dirents


def statvfs(path):
    '''
    Perform a statvfs call against the filesystem that the file resides on

    .. versionadded:: Hydrogen

    CLI Example:

    .. code-block:: bash

        salt '*' file.statvfs /path/to/file
    '''
    if not os.path.isabs(path):
        raise SaltInvocationError('File path must be absolute.')

    try:
        stv = os.statvfs(path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))
    except (OSError, IOError):
        raise CommandExecutionError('Could not create {0!r}'.format(link))
    return False


def stats(path, hash_type='md5', follow_symlink=False):
    '''
    Return a dict containing the stats for a given file

    CLI Example:

    .. code-block:: bash

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


def rmdir(path):
    '''
    Remove the specified directory. Fails if a directory is not empty.

    .. versionadded:: Hydrogen

    CLI Example:

    .. code-block:: bash

        salt '*' file.rmdir /tmp/foo/
    '''
    if not os.path.isabs(path):
        raise SaltInvocationError('File path must be absolute.')

    if not os.path.isdir(path):
        raise SaltInvocationError('A valid directory was not specified.')

    try:
        os.rmdir(path)
        return True
    except OSError as exc:
        return exc.strerror


def remove(path):
    '''
    Remove the named file

    CLI Example:

    .. code-block:: bash

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
    except (OSError, IOError) as exc:
        raise CommandExecutionError(
            'Could not remove {0!r}: {1}'.format(path, exc)
        )
    return False


def directory_exists(path):
    '''
    Tests to see if path is a valid directory.  Returns True/False.

    CLI Example:

    .. code-block:: bash

        salt '*' file.directory_exists /etc

    '''
    return os.path.isdir(path)


def file_exists(path):
    '''
    Tests to see if path is a valid file.  Returns True/False.

    CLI Example:

    .. code-block:: bash

        salt '*' file.file_exists /etc/passwd

    '''
    return os.path.isfile(path)


def restorecon(path, recursive=False):
    '''
    Reset the SELinux context on a given path

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_selinux_context /etc/hosts
    '''
    out = __salt__['cmd.run']('ls -Z {0}'.format(path))
    return out.split(' ')[4]


def set_selinux_context(path,
                        user=None,
                        role=None,
                        type=None,
                        range=None):
    '''
    Set a specific SELinux label on a given path

    CLI Example:

    .. code-block:: bash

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


def source_list(source, source_hash, saltenv):
    '''
    Check the source list and return the source to use

    CLI Example:

    .. code-block:: bash

        salt '*' file.source_list salt://http/httpd.conf '{hash_type: 'md5', 'hsum': <md5sum>}' base
    '''
    # get the master file list
    if isinstance(source, list):
        mfiles = __salt__['cp.list_master'](saltenv)
        mdirs = __salt__['cp.list_master_dirs'](saltenv)
        for single in source:
            if isinstance(single, dict):
                single = next(iter(single))

            env_splitter = '?saltenv='
            if '?env=' in single:
                salt.utils.warn_until(
                    'Boron',
                    'Passing a salt environment should be done using '
                    '\'saltenv\' not \'env\'. This functionality will be '
                    'removed in Salt Boron.'
                )
                env_splitter = '?env='
            try:
                sname, senv = single.split(env_splitter)
            except ValueError:
                continue
            else:
                mfiles += ['{0}?saltenv={1}'.format(f, senv)
                           for f in __salt__['cp.list_master'](senv)]
                mdirs += ['{0}?saltenv={1}'.format(d, senv)
                          for d in __salt__['cp.list_master_dirs'](senv)]

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
                    if single_src[7:] in mfiles or single_src[7:] in mdirs:
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
        saltenv,
        context,
        defaults,
        **kwargs):
    '''
    Return the managed file data for file.managed

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_managed /etc/httpd/conf.d/httpd.conf jinja salt://http/httpd.conf '{hash_type: 'md5', 'hsum': <md5sum>}' root root '755' base None None
    '''
    # If the file is a template and the contents is managed
    # then make sure to copy it down and templatize  things.
    sfn = ''
    source_sum = {}
    if template and source:
        sfn = __salt__['cp.cache_file'](source, saltenv)
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
                saltenv=saltenv,
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
                source_sum = __salt__['cp.hash_file'](source, saltenv)
                if not source_sum:
                    return '', {}, 'Source file {0} not found'.format(source)
            elif source_hash:
                protos = ['salt', 'http', 'https', 'ftp']
                if salt._compat.urlparse(source_hash).scheme in protos:
                    # The source_hash is a file on a server
                    hash_fn = __salt__['cp.cache_file'](source_hash, saltenv)
                    if not hash_fn:
                        return '', {}, 'Source hash file {0} not found'.format(
                            source_hash)
                    source_sum = extract_hash(hash_fn, '', name)
                    if source_sum is None:
                        return '', {}, ('Source hash file {0} contains an invalid '
                            'hash format, it must be in the format <hash type>=<hash>.'
                            ).format(source_hash)

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


def extract_hash(hash_fn, hash_type='md5', file_name=''):
    '''
    This routine is called from the :mod:`file.managed
    <salt.states.file.managed>` state to pull a hash from a remote file.
    Regular expressions are used line by line on the ``source_hash`` file, to
    find a potential candidate of the indicated hash type.  This avoids many
    problems of arbitrary file lay out rules. It specifically permits pulling
    hash codes from debian ``*.dsc`` files.

    For example:

    .. code-block:: yaml

        openerp_7.0-latest-1.tar.gz:
          file.managed:
            - name: /tmp/openerp_7.0-20121227-075624-1_all.deb
            - source: http://nightly.openerp.com/7.0/nightly/deb/openerp_7.0-20121227-075624-1.tar.gz
            - source_hash: http://nightly.openerp.com/7.0/nightly/deb/openerp_7.0-20121227-075624-1.dsc

    CLI Example:

    .. code-block:: bash

        salt '*' file.extract_hash /etc/foo sha512 /path/to/hash/file
    '''
    source_sum = None
    partial_id = False
    name_sought = re.findall(r'^(.+)/([^/]+)$', '/x' + file_name)[0][1]
    log.debug('modules.file.py - extract_hash(): Extracting hash for file named: {}'.format(name_sought))
    hash_fn_fopen = salt.utils.fopen(hash_fn, 'r')
    for hash_variant in HASHES:
        if hash_type == '' or hash_type == hash_variant[0]:
            log.debug('modules.file.py - extract_hash(): Will use regex to get'
                ' a purely hexadecimal number of length ({0}), presumably hash'
                ' type : {1}'.format(hash_variant[1], hash_variant[0]))
            hash_fn_fopen.seek(0)
            for line in hash_fn_fopen.read().splitlines():
                hash_array = re.findall(r'(?i)(?<![a-z0-9])[a-f0-9]{' + str(hash_variant[1]) + '}(?![a-z0-9])', line)
                log.debug('modules.file.py - extract_hash(): '
                    'From "line": {} got : {}'.format(line, hash_array))
                if hash_array:
                    if not partial_id:
                        source_sum = {'hsum': hash_array[0], 'hash_type': hash_variant[0]}
                        partial_id = True

                    log.debug('modules.file.py - extract_hash(): Found : {} -- {}'.format(
                                            source_sum['hash_type'], source_sum['hsum']))

                    if re.search(name_sought, line):
                        source_sum = {'hsum': hash_array[0], 'hash_type': hash_variant[0]}
                        log.debug('modules.file.py - extract_hash: '
                        'For {} -- returning the {} hash "{}".'.format(
                                 name_sought, source_sum['hash_type'], source_sum['hsum']))
                        return source_sum

    if partial_id:
        log.debug('modules.file.py - extract_hash: '
                'Returning the partially identified {} hash "{}".'.format(
                       source_sum['hash_type'], source_sum['hsum']))
    else:
        log.debug('modules.file.py - extract_hash: Returning None.')
    return source_sum


def check_perms(name, ret, user, group, mode):
    '''
    Check the permissions on files and chown if needed

    CLI Example:

    .. code-block:: bash

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
        saltenv,
        contents=None,
        **kwargs):
    '''
    Check to see what changes need to be made for a file

    CLI Example:

    .. code-block:: bash

        salt '*' file.check_managed /etc/httpd/conf.d/httpd.conf salt://http/httpd.conf '{hash_type: 'md5', 'hsum': <md5sum>}' root, root, '755' jinja True None None base
    '''
    # If the source is a list then find which file exists
    source, source_hash = source_list(source, source_hash, saltenv)

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
            saltenv,
            context,
            defaults,
            **kwargs)
        if comments:
            __clean_tmp(sfn)
            return False, comments
    changes = check_file_meta(name, sfn, source, source_sum, user,
                              group, mode, saltenv, template, contents)
    __clean_tmp(sfn)
    if changes:
        log.info(changes)
        comments = ['The following values are set to be changed:\n']
        comments.extend('{0}: {1}\n'.format(key, val)
                        for key, val in changes.iteritems())
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
        saltenv,
        template=None,
        contents=None):
    '''
    Check for the changes in the file metadata.

    CLI Example:

    .. code-block:: bash

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
                sfn = __salt__['cp.cache_file'](source, saltenv)
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
        env=None,
        saltenv='base'):
    '''
    Return unified diff of file compared to file on master

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_diff /home/fred/.vimrc salt://users/fred/.vimrc
    '''
    ret = ''

    if isinstance(env, salt._compat.string_types):
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' not '
            '\'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    if not os.path.exists(minionfile):
        ret = 'File {0} does not exist on the minion'.format(minionfile)
        return ret

    sfn = __salt__['cp.cache_file'](masterfile, saltenv)
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
                saltenv,
                backup,
                template=None,
                show_diff=True,
                contents=None,
                dir_mode=None):
    '''
    Checks the destination against what was retrieved with get_managed and
    makes the appropriate modifications (if necessary).

    CLI Example:

    .. code-block:: bash

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
                sfn = __salt__['cp.cache_file'](source, saltenv)
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
                sfn = __salt__['cp.cache_file'](source, saltenv)
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
                    if dir_mode is None:
                        # Add execute bit to each nonzero digit in the mode, if
                        # dir_mode was not specified. Otherwise, any
                        # directories created with makedirs() below can't be
                        # listed via a shell.
                        mode_list = [x for x in str(mode)][-3:]
                        for idx in xrange(len(mode_list)):
                            if mode_list[idx] != '0':
                                mode_list[idx] = str(int(mode_list[idx]) | 1)
                        dir_mode = ''.join(mode_list)
                    makedirs(name, user=user, group=group, mode=dir_mode)
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
                current_umask = os.umask(077)

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

        # This is a new file, if no mode specified, use the umask to figure
        # out what mode to use for the new file.
        if mode is None:
            # Get current umask
            mask = os.umask(0)
            os.umask(mask)
            # Calculate the mode value that results from the umask
            mode = oct((0777 ^ mask) & 0666)
        ret, perms = check_perms(name, ret, user, group, mode)

        if not ret['comment']:
            ret['comment'] = 'File ' + name + ' updated'

        if __opts__['test']:
            ret['comment'] = 'File ' + name + ' not updated'
        elif not ret['changes'] and ret['result']:
            ret['comment'] = 'File ' + name + ' is in the correct state'
        __clean_tmp(sfn)
        return ret


def mkdir(dir_path,
          user=None,
          group=None,
          mode=None):
    '''
    Ensure that a directory is available.

    CLI Example:

    .. code-block:: bash

        salt '*' file.mkdir /opt/jetty/context
    '''
    directory = os.path.normpath(dir_path)

    if not os.path.isdir(directory):
        # If a caller such as managed() is invoked  with makedirs=True, make
        # sure that any created dirs are created with the same user and group
        # to follow the principal of least surprise method.
        makedirs_perms(directory, user, group, mode)


def makedirs(path,
             user=None,
             group=None,
             mode=None):
    '''
    Ensure that the directory containing this path is available.

    CLI Example:

    .. code-block:: bash

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


def makedirs_perms(name,
                   user=None,
                   group=None,
                   mode='0755'):
    '''
    Taken and modified from os.makedirs to set user, group and mode for each
    directory created.

    CLI Example:

    .. code-block:: bash

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


def get_devmm(name):
    '''
    Get major/minor info from a device

    CLI Example:

    .. code-block:: bash

       salt '*' file.get_devmm /dev/chr
    '''
    if is_chrdev(name) or is_blkdev(name):
        stat_structure = os.stat(name)
        return (
                os.major(stat_structure.st_rdev),
                os.minor(stat_structure.st_rdev))
    else:
        return (0, 0)


def is_chrdev(name):
    '''
    Check if a file exists and is a character device.

    CLI Example:

    .. code-block:: bash

       salt '*' file.is_chrdev /dev/chr
    '''
    stat_structure = None
    try:
        stat_structure = os.stat(name)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            #If the character device does not exist in the first place
            return False
        else:
            raise
    return stat.S_ISCHR(stat_structure.st_mode)


def mknod_chrdev(name,
                 major,
                 minor,
                 user=None,
                 group=None,
                 mode='0660'):
    '''
    Create a character device.

    CLI Example:

    .. code-block:: bash

       salt '*' file.mknod_chrdev /dev/chr 180 31
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': False}
    log.debug("Creating character device name:{0} major:{1} minor:{2} mode:{3}".format(name,
                                                                                       major,
                                                                                       minor,
                                                                                       mode))
    try:
        if __opts__['test']:
            ret['changes'] = {'new': 'Character device {0} created.'.format(name)}
            ret['result'] = None
        else:
            if os.mknod(name,
                        int(str(mode).lstrip('0'), 8) | stat.S_IFCHR,
                        os.makedev(major, minor)) is None:
                ret['changes'] = {'new': 'Character device {0} created.'.format(name)}
                ret['result'] = True
    except OSError as exc:
        # be happy it is already there....however, if you are trying to change the
        # major/minor, you will need to unlink it first as os.mknod will not overwrite
        if exc.errno != errno.EEXIST:
            raise
        else:
            ret['comment'] = 'File {0} exists and cannot be overwritten'.format(name)
    #quick pass at verifying the permissions of the newly created character device
    check_perms(name,
                None,
                user,
                group,
                int('{0}'.format(mode)) if mode else None)
    return ret


def is_blkdev(name):
    '''
    Check if a file exists and is a block device.

    CLI Example:

    .. code-block:: bash

       salt '*' file.is_blkdev /dev/blk
    '''
    stat_structure = None
    try:
        stat_structure = os.stat(name)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            #If the block device does not exist in the first place
            return False
        else:
            raise
    return stat.S_ISBLK(stat_structure.st_mode)


def mknod_blkdev(name,
                 major,
                 minor,
                 user=None,
                 group=None,
                 mode='0660'):
    '''
    Create a block device.

    CLI Example:

    .. code-block:: bash

       salt '*' file.mknod_blkdev /dev/blk 8 999
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': False}
    log.debug("Creating block device name:{0} major:{1} minor:{2} mode:{3}".format(name,
                                                                                   major,
                                                                                   minor,
                                                                                   mode))
    try:
        if __opts__['test']:
            ret['changes'] = {'new': 'Block device {0} created.'.format(name)}
            ret['result'] = None
        else:
            if os.mknod(name,
                        int(str(mode).lstrip('0'), 8) | stat.S_IFBLK,
                        os.makedev(major, minor)) is None:
                ret['changes'] = {'new': 'Block device {0} created.'.format(name)}
                ret['result'] = True
    except OSError as exc:
        # be happy it is already there....however, if you are trying to change the
        # major/minor, you will need to unlink it first as os.mknod will not overwrite
        if exc.errno != errno.EEXIST:
            raise
        else:
            ret['comment'] = 'File {0} exists and cannot be overwritten'.format(name)
    #quick pass at verifying the permissions of the newly created block device
    check_perms(name,
                None,
                user,
                group,
                int('{0}'.format(mode)) if mode else None)
    return ret


def is_fifo(name):
    '''
    Check if a file exists and is a FIFO.

    CLI Example:

    .. code-block:: bash

       salt '*' file.is_fifo /dev/fifo
    '''
    stat_structure = None
    try:
        stat_structure = os.stat(name)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            #If the fifo does not exist in the first place
            return False
        else:
            raise
    return stat.S_ISFIFO(stat_structure.st_mode)


def mknod_fifo(name,
               user=None,
               group=None,
               mode='0660'):
    '''
    Create a FIFO pipe.

    CLI Example:

    .. code-block:: bash

       salt '*' file.mknod_fifo /dev/fifo
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': False}
    log.debug("Creating FIFO name:{0}".format(name))
    try:
        if __opts__['test']:
            ret['changes'] = {'new': 'Fifo pipe {0} created.'.format(name)}
            ret['result'] = None
        else:
            if os.mkfifo(name, int(str(mode).lstrip('0'), 8)) is None:
                ret['changes'] = {'new': 'Fifo pipe {0} created.'.format(name)}
                ret['result'] = True
    except OSError as exc:
        #be happy it is already there
        if exc.errno != errno.EEXIST:
            raise
        else:
            ret['comment'] = 'File {0} exists and cannot be overwritten'.format(name)
    #quick pass at verifying the permissions of the newly created fifo
    check_perms(name,
                None,
                user,
                group,
                int('{0}'.format(mode)) if mode else None)
    return ret


def mknod(name,
          ntype,
          major=0,
          minor=0,
          user=None,
          group=None,
          mode='0600'):
    '''
    Create a block device, character device, or fifo pipe.
    Identical to the gnu mknod.

    CLI Examples:

   .. code-block:: bash

      salt '*' file.mknod /dev/chr c 180 31
      salt '*' file.mknod /dev/blk b 8 999
      salt '*' file.nknod /dev/fifo p
    '''
    ret = False
    makedirs(name,
             user,
             group)
    if ntype == 'c':
        ret = mknod_chrdev(name,
                           major,
                           minor,
                           user,
                           group,
                           mode)
    elif ntype == 'b':
        ret = mknod_blkdev(name,
                            major,
                            minor,
                            user,
                            group,
                            mode)
    elif ntype == 'p':
        ret = mknod_fifo(name,
                          user,
                          group,
                          mode)
    else:
        raise Exception("Node type unavailable: '{0}'. Available node types are character ('c'), block ('b'), and pipe ('p').".format(ntype))
    return ret


def list_backups(path, limit=None):
    '''
    Lists the previous versions of a file backed up using Salt's :doc:`file
    state backup </ref/states/backup_mode>` system.

    .. versionadded:: 0.17.0

    path
        The path on the minion to check for backups
    limit
        Limit the number of results to the most recent N backups

    CLI Example:

    .. code-block:: bash

        salt '*' file.list_backups /foo/bar/baz.txt
    '''
    try:
        limit = int(limit)
    except TypeError:
        pass
    except ValueError:
        log.error('file.list_backups: \'limit\' value must be numeric')
        limit = None

    bkroot = _get_bkroot()
    parent_dir, basename = os.path.split(path)
    # Figure out full path of location of backup file in minion cache
    bkdir = os.path.join(bkroot, parent_dir[1:])

    files = {}
    for fn in [x for x in os.listdir(bkdir)
               if os.path.isfile(os.path.join(bkdir, x))]:
        strpfmt = '{0}_%a_%b_%d_%H:%M:%S_%f_%Y'.format(basename)
        try:
            timestamp = datetime.datetime.strptime(fn, strpfmt)
        except ValueError:
            # File didn't match the strp format string, so it's not a backup
            # for this file. Move on to the next one.
            continue
        files.setdefault(timestamp, {})['Backup Time'] = \
            timestamp.strftime('%a %b %d %Y %H:%M:%S.%f')
        location = os.path.join(bkdir, fn)
        files[timestamp]['Size'] = os.stat(location).st_size
        files[timestamp]['Location'] = location

    return dict(zip(
        range(len(files)),
        [files[x] for x in sorted(files, reverse=True)[:limit]]
    ))

list_backup = list_backups


def restore_backup(path, backup_id):
    '''
    Restore a previous version of a file that was backed up using Salt's
    :doc:`file state backup </ref/states/backup_mode>` system.

    .. versionadded:: 0.17.0

    path
        The path on the minion to check for backups
    backup_id
        The numeric id for the backup you wish to restore, as found using
        :mod:`file.list_backups <salt.modules.file.list_backups>`

    CLI Example:

    .. code-block:: bash

        salt '*' file.restore_backup /foo/bar/baz.txt 0
    '''
    # Note: This only supports minion backups, so this function will need to be
    # modified if/when master backups are implemented.
    ret = {'result': False,
           'comment': 'Invalid backup_id \'{0}\''.format(backup_id)}
    try:
        if len(str(backup_id)) == len(str(int(backup_id))):
            backup = list_backups(path)[int(backup_id)]
        else:
            return ret
    except ValueError:
        return ret
    except KeyError:
        ret['comment'] = 'backup_id \'{0}\' does not exist for ' \
                         '{1}'.format(backup_id, path)
        return ret

    salt.utils.backup_minion(path, _get_bkroot())
    try:
        shutil.copyfile(backup['Location'], path)
    except IOError as exc:
        ret['comment'] = \
            'Unable to restore {0} to {1}: ' \
            '{2}'.format(backup['Location'], path, exc)
        return ret
    else:
        ret['result'] = True
        ret['comment'] = 'Successfully restored {0} to ' \
                         '{1}'.format(backup['Location'], path)

    # Try to set proper ownership
    try:
        fstat = os.stat(path)
    except (OSError, IOError):
        ret['comment'] += ', but was unable to set ownership'
    else:
        os.chown(path, fstat.st_uid, fstat.st_gid)

    return ret


def delete_backup(path, backup_id):
    '''
    Restore a previous version of a file that was backed up using Salt's
    :doc:`file state backup </ref/states/backup_mode>` system.

    .. versionadded:: 0.17.0

    path
        The path on the minion to check for backups
    backup_id
        The numeric id for the backup you wish to delete, as found using
        :mod:`file.list_backups <salt.modules.file.list_backups>`

    CLI Example:

    .. code-block:: bash

        salt '*' file.restore_backup /foo/bar/baz.txt 0
    '''
    ret = {'result': False,
           'comment': 'Invalid backup_id \'{0}\''.format(backup_id)}
    try:
        if len(str(backup_id)) == len(str(int(backup_id))):
            backup = list_backups(path)[int(backup_id)]
        else:
            return ret
    except ValueError:
        return ret
    except KeyError:
        ret['comment'] = 'backup_id \'{0}\' does not exist for ' \
                         '{1}'.format(backup_id, path)
        return ret

    try:
        os.remove(backup['Location'])
    except IOError as exc:
        ret['comment'] = 'Unable to remove {0}: {1}'.format(backup['Location'],
                                                            exc)
    else:
        ret['result'] = True
        ret['comment'] = 'Successfully removed {0}'.format(backup['Location'])

    return ret

remove_backup = delete_backup


def grep(path,
         pattern,
         *args):
    '''
    Grep for a string in the specified file

    .. note::
        This function's return value is slated for refinement in future
        versions of Salt

    path
        A file path
    pattern
        A string. For example:
        ``test``
        ``a[0-5]``
    args
        grep options. For example:
        ``" -v"``
        ``" -i -B2"``

    CLI Example:

    .. code-block:: bash

        salt '*' file.grep /etc/passwd nobody
        salt '*' file.grep /etc/sysconfig/network-scripts/ifcfg-eth0 ipaddr " -i"
        salt '*' file.grep /etc/sysconfig/network-scripts/ifcfg-eth0 ipaddr " -i -B2"
        salt '*' file.grep "/etc/sysconfig/network-scripts/*" ipaddr " -i -l"
    '''
    if args:
        options = ' '.join(args)
    else:
        options = ''
    cmd = (
        r'''grep  {options} {pattern} {path}'''
        .format(
            options=options,
            pattern=pattern,
            path=path,
        )
    )

    try:
        ret = __salt__['cmd.run_all'](cmd)
    except (IOError, OSError) as exc:
        raise CommandExecutionError(exc.strerror)

    return ret
