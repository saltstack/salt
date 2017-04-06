# -*- coding: utf-8 -*-
'''
Manage information about regular files, directories,
and special files on the minion, set/read user,
group, mode, and data
'''

# TODO: We should add the capability to do u+r type operations here
# some time in the future

from __future__ import absolute_import, print_function

# Import python libs
import datetime
import difflib
import errno
import fileinput
import fnmatch
import itertools
import logging
import operator
import os
import re
import shutil
import stat
import string
import sys
import tempfile
import time
import glob
import hashlib
import mmap
from functools import reduce  # pylint: disable=redefined-builtin
from collections import Iterable, Mapping

# pylint: disable=import-error,no-name-in-module,redefined-builtin
import salt.ext.six as six
from salt.ext.six.moves import range, zip
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse
# pylint: enable=import-error,no-name-in-module,redefined-builtin

try:
    import grp
    import pwd
except ImportError:
    pass

# Import salt libs
import salt.utils
import salt.utils.atomicfile
import salt.utils.find
import salt.utils.filebuffer
import salt.utils.files
import salt.utils.locales
import salt.utils.templates
import salt.utils.url
from salt.exceptions import CommandExecutionError, MinionError, SaltInvocationError, get_error_message as _get_error_message

log = logging.getLogger(__name__)

__func_alias__ = {
    'makedirs_': 'makedirs'
}

HASHES = {
    'sha512': 128,
    'sha384': 96,
    'sha256': 64,
    'sha224': 56,
    'sha1': 40,
    'md5': 32,
}
HASHES_REVMAP = dict([(y, x) for x, y in six.iteritems(HASHES)])


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    # win_file takes care of windows
    if salt.utils.is_windows():
        return (False, 'The file execution module cannot be loaded: only available on non-Windows systems - use win_file instead.')
    return True


def __clean_tmp(sfn):
    '''
    Clean out a template temp file
    '''
    if sfn.startswith(os.path.join(tempfile.gettempdir(),
                                   salt.utils.files.TEMPFILE_PREFIX)):
        # Don't remove if it exists in file_roots (any saltenv)
        all_roots = itertools.chain.from_iterable(
                six.itervalues(__opts__['file_roots']))
        in_roots = any(sfn.startswith(root) for root in all_roots)
        # Only clean up files that exist
        if os.path.exists(sfn) and not in_roots:
            os.remove(sfn)


def _error(ret, err_msg):
    '''
    Common function for setting error information for return dicts
    '''
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


def _splitlines_preserving_trailing_newline(str):
    '''
    Returns a list of the lines in the string, breaking at line boundaries and
    preserving a trailing newline (if present).

    Essentially, this works like ``str.striplines(False)`` but preserves an
    empty line at the end. This is equivalent to the following code:

    .. code-block:: python

        lines = str.splitlines()
        if str.endswith('\n') or str.endswith('\r'):
            lines.append('')
    '''
    lines = str.splitlines()
    if str.endswith('\n') or str.endswith('\r'):
        lines.append('')
    return lines


def gid_to_group(gid):
    '''
    Convert the group id to the group name on this system

    gid
        gid to convert to a group name

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
    except (KeyError, NameError):
        # If group is not present, fall back to the gid.
        return gid


def group_to_gid(group):
    '''
    Convert the group to the gid on this system

    group
        group to convert to its gid

    CLI Example:

    .. code-block:: bash

        salt '*' file.group_to_gid root
    '''
    if group is None:
        return ''
    try:
        if isinstance(group, int):
            return group
        return grp.getgrnam(group).gr_gid
    except KeyError:
        return ''


def get_gid(path, follow_symlinks=True):
    '''
    Return the id of the group that owns a given file

    path
        file or directory of which to get the gid

    follow_symlinks
        indicated if symlinks should be followed


    CLI Example:

    .. code-block:: bash

        salt '*' file.get_gid /etc/passwd

    .. versionchanged:: 0.16.4
        ``follow_symlinks`` option added
    '''
    return stats(os.path.expanduser(path), follow_symlinks=follow_symlinks).get('gid', -1)


def get_group(path, follow_symlinks=True):
    '''
    Return the group that owns a given file

    path
        file or directory of which to get the group

    follow_symlinks
        indicated if symlinks should be followed

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_group /etc/passwd

    .. versionchanged:: 0.16.4
        ``follow_symlinks`` option added
    '''
    return stats(os.path.expanduser(path), follow_symlinks=follow_symlinks).get('group', False)


def uid_to_user(uid):
    '''
    Convert a uid to a user name

    uid
        uid to convert to a username

    CLI Example:

    .. code-block:: bash

        salt '*' file.uid_to_user 0
    '''
    try:
        return pwd.getpwuid(uid).pw_name
    except (KeyError, NameError):
        # If user is not present, fall back to the uid.
        return uid


def user_to_uid(user):
    '''
    Convert user name to a uid

    user
        user name to convert to its uid

    CLI Example:

    .. code-block:: bash

        salt '*' file.user_to_uid root
    '''
    if user is None:
        user = salt.utils.get_user()
    try:
        if isinstance(user, int):
            return user
        return pwd.getpwnam(user).pw_uid
    except KeyError:
        return ''


def get_uid(path, follow_symlinks=True):
    '''
    Return the id of the user that owns a given file

    path
        file or directory of which to get the uid

    follow_symlinks
        indicated if symlinks should be followed

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_uid /etc/passwd

    .. versionchanged:: 0.16.4
        ``follow_symlinks`` option added
    '''
    return stats(os.path.expanduser(path), follow_symlinks=follow_symlinks).get('uid', -1)


def get_user(path, follow_symlinks=True):
    '''
    Return the user that owns a given file

    path
        file or directory of which to get the user

    follow_symlinks
        indicated if symlinks should be followed

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_user /etc/passwd

    .. versionchanged:: 0.16.4
        ``follow_symlinks`` option added
    '''
    return stats(os.path.expanduser(path), follow_symlinks=follow_symlinks).get('user', False)


def get_mode(path, follow_symlinks=True):
    '''
    Return the mode of a file

    path
        file or directory of which to get the mode

    follow_symlinks
        indicated if symlinks should be followed

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_mode /etc/passwd

    .. versionchanged:: 2014.1.0
        ``follow_symlinks`` option added
    '''
    return stats(os.path.expanduser(path), follow_symlinks=follow_symlinks).get('mode', '')


def set_mode(path, mode):
    '''
    Set the mode of a file

    path
        file or directory of which to set the mode

    mode
        mode to set the path to

    CLI Example:

    .. code-block:: bash

        salt '*' file.set_mode /etc/passwd 0644
    '''
    path = os.path.expanduser(path)

    mode = str(mode).lstrip('0Oo')
    if not mode:
        mode = '0'
    if not os.path.exists(path):
        raise CommandExecutionError('{0}: File not found'.format(path))
    try:
        os.chmod(path, int(mode, 8))
    except Exception:
        return 'Invalid Mode ' + mode
    return get_mode(path)


def lchown(path, user, group):
    '''
    Chown a file, pass the file the desired user and group without following
    symlinks.

    path
        path to the file or directory

    user
        user owner

    group
        group owner

    CLI Example:

    .. code-block:: bash

        salt '*' file.chown /etc/passwd root root
    '''
    path = os.path.expanduser(path)

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

    return os.lchown(path, uid, gid)


def chown(path, user, group):
    '''
    Chown a file, pass the file the desired user and group

    path
        path to the file or directory

    user
        user owner

    group
        group owner

    CLI Example:

    .. code-block:: bash

        salt '*' file.chown /etc/passwd root root
    '''
    path = os.path.expanduser(path)

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

    path
        path to the file or directory

    group
        group owner

    CLI Example:

    .. code-block:: bash

        salt '*' file.chgrp /etc/passwd root
    '''
    path = os.path.expanduser(path)

    user = get_user(path)
    return chown(path, user, group)


def get_sum(path, form='sha256'):
    '''
    Return the checksum for the given file. The following checksum algorithms
    are supported:

    * md5
    * sha1
    * sha224
    * sha256 **(default)**
    * sha384
    * sha512

    path
        path to the file or directory

    form
        desired sum format

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_sum /etc/passwd sha512
    '''
    path = os.path.expanduser(path)

    if not os.path.isfile(path):
        return 'File not found'
    return salt.utils.get_hash(path, form, 4096)


def get_hash(path, form='sha256', chunk_size=65536):
    '''
    Get the hash sum of a file

    This is better than ``get_sum`` for the following reasons:
        - It does not read the entire file into memory.
        - It does not return a string on error. The returned value of
            ``get_sum`` cannot really be trusted since it is vulnerable to
            collisions: ``get_sum(..., 'xyz') == 'Hash xyz not supported'``

    path
        path to the file or directory

    form
        desired sum format

    chunk_size
        amount to sum at once

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_hash /etc/shadow
    '''
    return salt.utils.get_hash(os.path.expanduser(path), form, chunk_size)


def get_source_sum(file_name='',
                   source='',
                   source_hash=None,
                   source_hash_name=None,
                   saltenv='base'):
    '''
    .. versionadded:: 2016.11.0

    Used by :py:func:`file.get_managed <salt.modules.file.get_managed>` to
    obtain the hash and hash type from the parameters specified below.

    file_name
        Optional file name being managed, for matching with
        :py:func:`file.extract_hash <salt.modules.file.extract_hash>`.

        .. versionadded:: 2016.11.0

    source
        Source file, as used in :py:mod:`file <salt.states.file>` and other
        states. If ``source_hash`` refers to a file containing hashes, then
        this filename will be used to match a filename in that file. If the
        ``source_hash`` is a hash expression, then this argument will be
        ignored.

    source_hash
        Hash file/expression, as used in :py:mod:`file <salt.states.file>` and
        other states. If this value refers to a remote URL or absolute path to
        a local file, it will be cached and :py:func:`file.extract_hash
        <salt.modules.file.extract_hash>` will be used to obtain a hash from
        it.

    source_hash_name
        Specific file name to look for when ``source_hash`` refers to a remote
        file, used to disambiguate ambiguous matches.

        .. versionadded:: 2016.11.0

    saltenv : base
        Salt fileserver environment from which to retrive the source_hash. This
        value will only be used when ``source_hash`` refers to a file on the
        Salt fileserver (i.e. one beginning with ``salt://``).

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_source_sum /tmp/foo.tar.gz source=http://mydomain.tld/foo.tar.gz source_hash=499ae16dcae71eeb7c3a30c75ea7a1a6
        salt '*' file.get_source_sum /tmp/foo.tar.gz source=http://mydomain.tld/foo.tar.gz source_hash=https://mydomain.tld/hashes.md5
        salt '*' file.get_source_sum /tmp/foo.tar.gz source=http://mydomain.tld/foo.tar.gz source_hash=https://mydomain.tld/hashes.md5 source_hash_name=./dir2/foo.tar.gz
    '''
    def _invalid_source_hash_format():
        '''
        DRY helper for reporting invalid source_hash input
        '''
        raise CommandExecutionError(
            'Source hash {0} format is invalid. The supported formats are: '
            '1) a hash, 2) an expression in the format <hash_type>=<hash>, or '
            '3) either a path to a local file containing hashes, or a URI of '
            'a remote hash file. Supported protocols for remote hash files '
            'are: {1}. The hash may also not be of a valid length, the '
            'following are supported hash types and lengths: {2}.'.format(
                source_hash,
                ', '.join(salt.utils.files.VALID_PROTOS),
                ', '.join(
                    ['{0} ({1})'.format(HASHES_REVMAP[x], x)
                     for x in sorted(HASHES_REVMAP)]
                ),
            )
        )

    hash_fn = None
    if os.path.isabs(source_hash):
        hash_fn = source_hash
    else:
        try:
            proto = _urlparse(source_hash).scheme
            if proto in salt.utils.files.VALID_PROTOS:
                hash_fn = __salt__['cp.cache_file'](source_hash, saltenv)
                if not hash_fn:
                    raise CommandExecutionError(
                        'Source hash file {0} not found'.format(source_hash)
                    )
            else:
                if proto != '':
                    # Some unsupported protocol (e.g. foo://) is being used.
                    # We'll get into this else block if a hash expression
                    # (like md5=<md5 checksum here>), but in those cases, the
                    # protocol will be an empty string, in which case we avoid
                    # this error condition.
                    _invalid_source_hash_format()
        except (AttributeError, TypeError):
            _invalid_source_hash_format()

    if hash_fn is not None:
        ret = extract_hash(hash_fn, '', file_name, source, source_hash_name)
        if ret is None:
            _invalid_source_hash_format()
        return ret
    else:
        # The source_hash is a hash expression
        ret = {}
        try:
            ret['hash_type'], ret['hsum'] = \
                [x.strip() for x in source_hash.split('=', 1)]
        except AttributeError:
            _invalid_source_hash_format()
        except ValueError:
            # No hash type, try to figure out by hash length
            if not re.match('^[{0}]+$'.format(string.hexdigits), source_hash):
                _invalid_source_hash_format()
            ret['hsum'] = source_hash
            source_hash_len = len(source_hash)
            if source_hash_len in HASHES_REVMAP:
                ret['hash_type'] = HASHES_REVMAP[source_hash_len]
            else:
                _invalid_source_hash_format()

        if ret['hash_type'] not in HASHES:
            raise CommandExecutionError(
                'Invalid hash type \'{0}\'. Supported hash types are: {1}. '
                'Either remove the hash type and simply use \'{2}\' as the '
                'source_hash, or change the hash type to a supported type.'
                .format(ret['hash_type'], ', '.join(HASHES), ret['hsum'])
            )
        else:
            hsum_len = len(ret['hsum'])
            if hsum_len not in HASHES_REVMAP:
                _invalid_source_hash_format()
            elif hsum_len != HASHES[ret['hash_type']]:
                raise CommandExecutionError(
                    'Invalid length ({0}) for hash type \'{1}\'. Either '
                    'remove the hash type and simply use \'{2}\' as the '
                    'source_hash, or change the hash type to \'{3}\''.format(
                        hsum_len,
                        ret['hash_type'],
                        ret['hsum'],
                        HASHES_REVMAP[hsum_len],
                    )
                )

        return ret


def check_hash(path, file_hash):
    '''
    Check if a file matches the given hash string

    Returns ``True`` if the hash matches, otherwise ``False``.

    path
        Path to a file local to the minion.

    hash
        The hash to check against the file specified in the ``path`` argument.
        For versions 2016.11.4 and newer, the hash can be specified without an
        accompanying hash type (e.g. ``e138491e9d5b97023cea823fe17bac22``),
        but for earlier releases it is necessary to also specify the hash type
        in the format ``<hash_type>:<hash_value>`` (e.g.
        ``md5:e138491e9d5b97023cea823fe17bac22``).

    CLI Example:

    .. code-block:: bash

        salt '*' file.check_hash /etc/fstab e138491e9d5b97023cea823fe17bac22
        salt '*' file.check_hash /etc/fstab md5:e138491e9d5b97023cea823fe17bac22
    '''
    path = os.path.expanduser(path)

    if not isinstance(file_hash, six.string_types):
        raise SaltInvocationError('hash must be a string')

    for sep in (':', '='):
        if sep in file_hash:
            hash_type, hash_value = file_hash.split(sep, 1)
            break
    else:
        hash_value = file_hash
        hash_len = len(file_hash)
        hash_type = HASHES_REVMAP.get(hash_len)
        if hash_type is None:
            raise SaltInvocationError(
                'Hash {0} (length: {1}) could not be matched to a supported '
                'hash type. The supported hash types and lengths are: '
                '{2}'.format(
                    file_hash,
                    hash_len,
                    ', '.join(
                        ['{0} ({1})'.format(HASHES_REVMAP[x], x)
                         for x in sorted(HASHES_REVMAP)]
                    ),
                )
            )

    return get_hash(path, hash_type) == hash_value


def find(path, *args, **kwargs):
    '''
    Approximate the Unix ``find(1)`` command and return a list of paths that
    meet the specified criteria.

    The options include match criteria:

    .. code-block:: text

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

    and/or actions:

    .. code-block:: text

        delete [= file-types]               # default type = 'f'
        exec    = command [arg ...]         # where {} is replaced by pathname
        print  [= print-opts]

    and/or depth criteria:

    .. code-block:: text

        maxdepth = maximum depth to transverse in path
        mindepth = minimum depth to transverse before checking files or directories

    The default action is ``print=path``

    ``path-glob``:

    .. code-block:: text

        *                = match zero or more chars
        ?                = match any char
        [abc]            = match a, b, or c
        [!abc] or [^abc] = match anything except a, b, and c
        [x-y]            = match chars x through y
        [!x-y] or [^x-y] = match anything except chars x through y
        {a,b,c}          = match a or b or c

    ``path-regex``: a Python Regex (regular expression) pattern to match pathnames

    ``file-types``: a string of one or more of the following:

    .. code-block:: text

        a: all file types
        b: block device
        c: character device
        d: directory
        p: FIFO (named pipe)
        f: plain file
        l: symlink
        s: socket

    ``users``: a space and/or comma separated list of user names and/or uids

    ``groups``: a space and/or comma separated list of group names and/or gids

    ``size-unit``:

    .. code-block:: text

        b: bytes
        k: kilobytes
        m: megabytes
        g: gigabytes
        t: terabytes

    interval:

    .. code-block:: text

        [<num>w] [<num>d] [<num>h] [<num>m] [<num>s]

        where:
            w: week
            d: day
            h: hour
            m: minute
            s: second

    print-opts: a comma and/or space separated list of one or more of the
    following:

    .. code-block:: text

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
    if 'delete' in args:
        kwargs['delete'] = 'f'
    elif 'print' in args:
        kwargs['print'] = 'path'

    try:
        finder = salt.utils.find.Finder(kwargs)
    except ValueError as ex:
        return 'error: {0}'.format(ex)

    ret = [item for i in [finder.find(p) for p in glob.glob(os.path.expanduser(path))] for item in i]
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

    Equivalent to:

    .. code-block:: bash

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
        Flags to modify the sed search; e.g., ``i`` for case-insensitive pattern
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
    path = os.path.expanduser(path)

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

    cmd = ['sed']
    cmd.append('-i{0}'.format(backup) if backup else '-i')
    cmd.extend(salt.utils.shlex_split(options))
    cmd.append(
        r'{limit}{negate_match}s/{before}/{after}/{flags}'.format(
            limit='/{0}/ '.format(limit) if limit else '',
            negate_match='!' if negate_match else '',
            before=before,
            after=after,
            flags=flags
        )
    )
    cmd.append(path)

    return __salt__['cmd.run_all'](cmd, python_shell=False)


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
    path = os.path.expanduser(path)

    if not os.path.exists(path):
        return False

    before = _sed_esc(str(text), False)
    limit = _sed_esc(str(limit), False)
    options = '-n -r -e'
    if sys.platform == 'darwin':
        options = options.replace('-r', '-E')

    cmd = ['sed']
    cmd.extend(salt.utils.shlex_split(options))
    cmd.append(
        r'{limit}s/{before}/$/{flags}'.format(
            limit='/{0}/ '.format(limit) if limit else '',
            before=before,
            flags='p{0}'.format(flags)
        )
    )
    cmd.append(path)

    result = __salt__['cmd.run'](cmd, python_shell=False)

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

    Equivalent to:

    .. code-block:: bash

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
    path = os.path.expanduser(path)

    multi = bool(multi)

    before = str(before)
    after = str(after)
    before = _sed_esc(before, escape_all)
    # The pattern to replace with does not need to be escaped!!!
    #after = _sed_esc(after, escape_all)
    limit = _sed_esc(limit, escape_all)

    shutil.copy2(path, '{0}{1}'.format(path, backup))

    with salt.utils.fopen(path, 'w') as ofile:
        with salt.utils.fopen('{0}{1}'.format(path, backup), 'r') as ifile:
            if multi is True:
                for line in ifile.readline():
                    ofile.write(_psed(line, before, after, limit, flags))
            else:
                ofile.write(_psed(ifile.read(), before, after, limit, flags))


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
    return comment_line(path=path,
                        regex=regex,
                        char=char,
                        cmnt=False,
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
    return comment_line(path=path,
                        regex=regex,
                        char=char,
                        cmnt=True,
                        backup=backup)


def comment_line(path,
                 regex,
                 char='#',
                 cmnt=True,
                 backup='.bak'):
    r'''
    Comment or Uncomment a line in a text file.

    :param path: string
        The full path to the text file.

    :param regex: string
        A regex expression that begins with ``^`` that will find the line you wish
        to comment. Can be as simple as ``^color =``

    :param char: string
        The character used to comment a line in the type of file you're referencing.
        Default is ``#``

    :param cmnt: boolean
        True to comment the line. False to uncomment the line. Default is True.

    :param backup: string
        The file extension to give the backup file. Default is ``.bak``
        Set to False/None to not keep a backup.

    :return: boolean
        Returns True if successful, False if not

    CLI Example:

    The following example will comment out the ``pcspkr`` line in the
    ``/etc/modules`` file using the default ``#`` character and create a backup
    file named ``modules.bak``

    .. code-block:: bash

        salt '*' file.comment_line '/etc/modules' '^pcspkr'


    CLI Example:

    The following example will uncomment the ``log_level`` setting in ``minion``
    config file if it is set to either ``warning``, ``info``, or ``debug`` using
    the ``#`` character and create a backup file named ``minion.bk``

    .. code-block:: bash

        salt '*' file.comment_line 'C:\salt\conf\minion' '^log_level: (warning|info|debug)' '#' False '.bk'
    '''
    # Get the regex for comment or uncomment
    if cmnt:
        regex = '{0}({1}){2}'.format(
                '^' if regex.startswith('^') else '',
                regex.lstrip('^').rstrip('$'),
                '$' if regex.endswith('$') else '')
    else:
        regex = r'^{0}\s*({1}){2}'.format(
                char,
                regex.lstrip('^').rstrip('$'),
                '$' if regex.endswith('$') else '')

    # Load the real path to the file
    path = os.path.realpath(os.path.expanduser(path))

    # Make sure the file exists
    if not os.path.isfile(path):
        raise SaltInvocationError('File not found: {0}'.format(path))

    # Make sure it is a text file
    if not salt.utils.istextfile(path):
        raise SaltInvocationError(
            'Cannot perform string replacements on a binary file: {0}'.format(path))

    # First check the whole file, determine whether to make the replacement
    # Searching first avoids modifying the time stamp if there are no changes
    found = False
    # Dictionaries for comparing changes
    orig_file = []
    new_file = []
    # Buffer size for fopen
    bufsize = os.path.getsize(path)
    try:
        # Use a read-only handle to open the file
        with salt.utils.fopen(path,
                              mode='rb',
                              buffering=bufsize) as r_file:
            # Loop through each line of the file and look for a match
            for line in r_file:
                # Is it in this line
                if re.match(regex, line):
                    # Load lines into dictionaries, set found to True
                    orig_file.append(line)
                    if cmnt:
                        new_file.append('{0}{1}'.format(char, line))
                    else:
                        new_file.append(line.lstrip(char))
                    found = True
    except (OSError, IOError) as exc:
        raise CommandExecutionError(
            "Unable to open file '{0}'. "
            "Exception: {1}".format(path, exc)
        )

    # We've searched the whole file. If we didn't find anything, return False
    if not found:
        return False

    if not salt.utils.is_windows():
        pre_user = get_user(path)
        pre_group = get_group(path)
        pre_mode = salt.utils.normalize_mode(get_mode(path))

    # Create a copy to read from and to use as a backup later
    try:
        temp_file = _mkstemp_copy(path=path, preserve_inode=False)
    except (OSError, IOError) as exc:
        raise CommandExecutionError("Exception: {0}".format(exc))

    try:
        # Open the file in write mode
        with salt.utils.fopen(path,
                              mode='wb',
                              buffering=bufsize) as w_file:
            try:
                # Open the temp file in read mode
                with salt.utils.fopen(temp_file,
                                      mode='rb',
                                      buffering=bufsize) as r_file:
                    # Loop through each line of the file and look for a match
                    for line in r_file:
                        try:
                            # Is it in this line
                            if re.match(regex, line):
                                # Write the new line
                                if cmnt:
                                    w_file.write('{0}{1}'.format(char, line))
                                else:
                                    w_file.write(line.lstrip(char))
                            else:
                                # Write the existing line (no change)
                                w_file.write(line)
                        except (OSError, IOError) as exc:
                            raise CommandExecutionError(
                                "Unable to write file '{0}'. Contents may "
                                "be truncated. Temporary file contains copy "
                                "at '{1}'. "
                                "Exception: {2}".format(path, temp_file, exc)
                            )
            except (OSError, IOError) as exc:
                raise CommandExecutionError("Exception: {0}".format(exc))
    except (OSError, IOError) as exc:
        raise CommandExecutionError("Exception: {0}".format(exc))

    if backup:
        # Move the backup file to the original directory
        backup_name = '{0}{1}'.format(path, backup)
        try:
            shutil.move(temp_file, backup_name)
        except (OSError, IOError) as exc:
            raise CommandExecutionError(
                "Unable to move the temp file '{0}' to the "
                "backup file '{1}'. "
                "Exception: {2}".format(path, temp_file, exc)
            )
    else:
        os.remove(temp_file)

    if not salt.utils.is_windows():
        check_perms(path, None, pre_user, pre_group, pre_mode)

    # Return a diff using the two dictionaries
    return ''.join(difflib.unified_diff(orig_file, new_file))


def _get_flags(flags):
    '''
    Return an integer appropriate for use as a flag for the re module from a
    list of human-readable strings

    .. code-block:: python

        >>> _get_flags(['MULTILINE', 'IGNORECASE'])
        10
        >>> _get_flags('MULTILINE')
        8
        >>> _get_flags(2)
        2
    '''
    if isinstance(flags, six.string_types):
        flags = [flags]

    if isinstance(flags, Iterable) and not isinstance(flags, Mapping):
        _flags_acc = []
        for flag in flags:
            _flag = getattr(re, str(flag).upper())

            if not isinstance(_flag, six.integer_types):
                raise SaltInvocationError(
                    'Invalid re flag given: {0}'.format(flag)
                )

            _flags_acc.append(_flag)

        return reduce(operator.__or__, _flags_acc)
    elif isinstance(flags, six.integer_types):
        return flags
    else:
        raise SaltInvocationError(
            'Invalid re flags: "{0}", must be given either as a single flag '
            'string, a list of strings, or as an integer'.format(flags)
        )


def _add_flags(flags, new_flags):
    '''
    Combine ``flags`` and ``new_flags``
    '''
    flags = _get_flags(flags)
    new_flags = _get_flags(new_flags)
    return flags | new_flags


def _mkstemp_copy(path,
                  preserve_inode=True):
    '''
    Create a temp file and move/copy the contents of ``path`` to the temp file.
    Return the path to the temp file.

    path
        The full path to the file whose contents will be moved/copied to a temp file.
        Whether it's moved or copied depends on the value of ``preserve_inode``.
    preserve_inode
        Preserve the inode of the file, so that any hard links continue to share the
        inode with the original filename. This works by *copying* the file, reading
        from the copy, and writing to the file at the original inode. If ``False``, the
        file will be *moved* rather than copied, and a new file will be written to a
        new inode, but using the original filename. Hard links will then share an inode
        with the backup, instead (if using ``backup`` to create a backup copy).
        Default is ``True``.
    '''
    temp_file = None
    # Create the temp file
    try:
        temp_file = salt.utils.mkstemp(prefix=salt.utils.files.TEMPFILE_PREFIX)
    except (OSError, IOError) as exc:
        raise CommandExecutionError(
            "Unable to create temp file. "
            "Exception: {0}".format(exc)
            )
    # use `copy` to preserve the inode of the
    # original file, and thus preserve hardlinks
    # to the inode. otherwise, use `move` to
    # preserve prior behavior, which results in
    # writing the file to a new inode.
    if preserve_inode:
        try:
            shutil.copy2(path, temp_file)
        except (OSError, IOError) as exc:
            raise CommandExecutionError(
                "Unable to copy file '{0}' to the "
                "temp file '{1}'. "
                "Exception: {2}".format(path, temp_file, exc)
                )
    else:
        try:
            shutil.move(path, temp_file)
        except (OSError, IOError) as exc:
            raise CommandExecutionError(
                "Unable to move file '{0}' to the "
                "temp file '{1}'. "
                "Exception: {2}".format(path, temp_file, exc)
                )

    return temp_file


def _starts_till(src, probe, strip_comments=True):
    '''
    Returns True if src and probe at least begins till some point.
    '''
    def _strip_comments(txt):
        '''
        Strip possible comments.
        Usually commends are one or two symbols
        '''
        buff = txt.split(" ", 1)
        return len(buff) == 2 and len(buff[0]) < 2 and buff[1] or txt

    def _to_words(txt):
        '''
        Split by words
        '''
        return txt and [w for w in txt.strip().split(" ") if w.strip()] or txt

    no_match = -1
    equal = 0
    if not src or not probe:
        return no_match

    if src == probe:
        return equal

    src = _to_words(strip_comments and _strip_comments(src) or src)
    probe = _to_words(strip_comments and _strip_comments(probe) or probe)

    a_buff, b_buff = len(src) < len(probe) and (src, probe) or (probe, src)
    b_buff = ' '.join(b_buff)
    for idx in range(len(a_buff)):
        prb = ' '.join(a_buff[:-(idx + 1)])
        if prb and b_buff.startswith(prb):
            return idx

    return no_match


def _regex_to_static(src, regex):
    '''
    Expand regular expression to static match.
    '''
    if not src or not regex:
        return None

    try:
        src = re.search(regex, src)
    except Exception as ex:
        raise CommandExecutionError("{0}: '{1}'".format(_get_error_message(ex), regex))

    return src and src.group() or regex


def _assert_occurrence(src, probe, target, amount=1):
    '''
    Raise an exception, if there are different amount of specified occurrences in src.
    '''
    occ = src.count(probe)
    if occ > amount:
        msg = 'more than'
    elif occ < amount:
        msg = 'less than'
    elif not occ:
        msg = 'no'
    else:
        msg = None

    if msg:
        raise CommandExecutionError('Found {0} expected occurrences in "{1}" expression'.format(msg, target))


def _get_line_indent(src, line, indent):
    '''
    Indent the line with the source line.
    '''
    if not indent:
        return line

    idt = []
    for c in src:
        if c not in ['\t', ' ']:
            break
        idt.append(c)

    return ''.join(idt) + line.strip()


def line(path, content, match=None, mode=None, location=None,
         before=None, after=None, show_changes=True, backup=False,
         quiet=False, indent=True):
    '''
    .. versionadded:: 2015.8.0

    Edit a line in the configuration file. The ``path`` and ``content``
    arguments are required, as well as passing in one of the ``mode``
    options.

    path
        Filesystem path to the file to be edited.

    content
        Content of the line.

    match
        Match the target line for an action by
        a fragment of a string or regular expression.

        If neither ``before`` nor ``after`` are provided, and ``match``
        is also ``None``, match becomes the ``content`` value.

    mode
        Defines how to edit a line. One of the following options is
        required:

        - ensure
            If line does not exist, it will be added. This is based on the
            ``content`` argument.
        - replace
            If line already exists, it will be replaced.
        - delete
            Delete the line, once found.
        - insert
            Insert a line.

        .. note::

            If ``mode=insert`` is used, at least one of the following
            options must also be defined: ``location``, ``before``, or
            ``after``. If ``location`` is used, it takes precedence
            over the other two options.

    location
        Defines where to place content in the line. Note this option is only
        used when ``mode=insert`` is specified. If a location is passed in, it
        takes precedence over both the ``before`` and ``after`` kwargs. Valid
        locations are:

        - start
            Place the content at the beginning of the file.
        - end
            Place the content at the end of the file.

    before
        Regular expression or an exact case-sensitive fragment of the string.
        This option is only used when either the ``ensure`` or ``insert`` mode
        is defined.

    after
        Regular expression or an exact case-sensitive fragment of the string.
        This option is only used when either the ``ensure`` or ``insert`` mode
        is defined.

    show_changes
        Output a unified diff of the old file and the new file.
        If ``False`` return a boolean if any changes were made.
        Default is ``True``

        .. note::
            Using this option will store two copies of the file in-memory
            (the original version and the edited version) in order to generate the diff.

    backup
        Create a backup of the original file with the extension:
        "Year-Month-Day-Hour-Minutes-Seconds".

    quiet
        Do not raise any exceptions. E.g. ignore the fact that the file that is
        tried to be edited does not exist and nothing really happened.

    indent
        Keep indentation with the previous line. This option is not considered when
        the ``delete`` mode is specified.

    CLI Example:

    .. code-block:: bash

        salt '*' file.line /etc/nsswitch.conf "networks:\tfiles dns" after="hosts:.*?" mode='ensure'

    .. note::

        If an equal sign (``=``) appears in an argument to a Salt command, it is
        interpreted as a keyword argument in the format of ``key=val``. That
        processing can be bypassed in order to pass an equal sign through to the
        remote shell command by manually specifying the kwarg:

        .. code-block:: bash

            salt '*' file.line /path/to/file content="CREATEMAIL_SPOOL=no" match="CREATE_MAIL_SPOOL=yes" mode="replace"
    '''
    path = os.path.realpath(os.path.expanduser(path))
    if not os.path.isfile(path):
        if not quiet:
            raise CommandExecutionError('File "{0}" does not exists or is not a file.'.format(path))
        return False  # No changes had happened

    mode = mode and mode.lower() or mode
    if mode not in ['insert', 'ensure', 'delete', 'replace']:
        if mode is None:
            raise CommandExecutionError('Mode was not defined. How to process the file?')
        else:
            raise CommandExecutionError('Unknown mode: "{0}"'.format(mode))

    # Before/after has privilege. If nothing defined, match is used by content.
    if before is None and after is None and not match:
        match = content

    with salt.utils.fopen(path, mode='r') as fp_:
        body = fp_.read()
    body_before = hashlib.sha256(salt.utils.to_bytes(body)).hexdigest()
    after = _regex_to_static(body, after)
    before = _regex_to_static(body, before)
    match = _regex_to_static(body, match)

    if os.stat(path).st_size == 0 and mode in ('delete', 'replace'):
        log.warning('Cannot find text to {0}. File \'{1}\' is empty.'.format(mode, path))
        body = ''
    elif mode == 'delete':
        body = os.linesep.join([line for line in body.split(os.linesep) if line.find(match) < 0])
    elif mode == 'replace':
        body = os.linesep.join([(_get_line_indent(file_line, content, indent)
                                if (file_line.find(match) > -1 and not file_line == content) else file_line)
                                for file_line in body.split(os.linesep)])
    elif mode == 'insert':
        if not location and not before and not after:
            raise CommandExecutionError('On insert must be defined either "location" or "before/after" conditions.')

        if not location:
            if before and after:
                _assert_occurrence(body, before, 'before')
                _assert_occurrence(body, after, 'after')
                out = []
                lines = body.split(os.linesep)
                for idx in range(len(lines)):
                    _line = lines[idx]
                    if _line.find(before) > -1 and idx <= len(lines) and lines[idx - 1].find(after) > -1:
                        out.append(_get_line_indent(_line, content, indent))
                        out.append(_line)
                    else:
                        out.append(_line)
                body = os.linesep.join(out)

            if before and not after:
                _assert_occurrence(body, before, 'before')
                out = []
                lines = body.split(os.linesep)
                for idx in range(len(lines)):
                    _line = lines[idx]
                    if _line.find(before) > -1:
                        cnd = _get_line_indent(_line, content, indent)
                        if not idx or (idx and _starts_till(lines[idx - 1], cnd) < 0):  # Job for replace instead
                            out.append(cnd)
                    out.append(_line)
                body = os.linesep.join(out)

            elif after and not before:
                _assert_occurrence(body, after, 'after')
                out = []
                lines = body.split(os.linesep)
                for idx in range(len(lines)):
                    _line = lines[idx]
                    out.append(_line)
                    cnd = _get_line_indent(_line, content, indent)
                    if _line.find(after) > -1:
                        # No dupes or append, if "after" is the last line
                        if (idx < len(lines) and _starts_till(lines[idx + 1], cnd) < 0) or idx + 1 == len(lines):
                            out.append(cnd)
                body = os.linesep.join(out)

        else:
            if location == 'start':
                body = ''.join([content, body])
            elif location == 'end':
                body = ''.join([body, _get_line_indent(body[-1], content, indent) if body else content])

    elif mode == 'ensure':
        after = after and after.strip()
        before = before and before.strip()

        if before and after:
            _assert_occurrence(body, before, 'before')
            _assert_occurrence(body, after, 'after')

            a_idx = b_idx = -1
            idx = 0
            body = body.split(os.linesep)
            for _line in body:
                idx += 1
                if _line.find(before) > -1 and b_idx < 0:
                    b_idx = idx
                if _line.find(after) > -1 and a_idx < 0:
                    a_idx = idx

            # Add
            if not b_idx - a_idx - 1:
                body = body[:a_idx] + [content] + body[b_idx - 1:]
            elif b_idx - a_idx - 1 == 1:
                if _starts_till(body[a_idx:b_idx - 1][0], content) > -1:
                    body[a_idx] = _get_line_indent(body[a_idx - 1], content, indent)
            else:
                raise CommandExecutionError('Found more than one line between boundaries "before" and "after".')
            body = os.linesep.join(body)

        elif before and not after:
            _assert_occurrence(body, before, 'before')
            body = body.split(os.linesep)
            out = []
            for idx in range(len(body)):
                if body[idx].find(before) > -1:
                    prev = (idx > 0 and idx or 1) - 1
                    out.append(_get_line_indent(body[prev], content, indent))
                    if _starts_till(out[prev], content) > -1:
                        del out[prev]
                out.append(body[idx])
            body = os.linesep.join(out)

        elif not before and after:
            _assert_occurrence(body, after, 'after')
            body = body.split(os.linesep)
            skip = None
            out = []
            for idx in range(len(body)):
                if skip != body[idx]:
                    out.append(body[idx])

                if body[idx].find(after) > -1:
                    next_line = idx + 1 < len(body) and body[idx + 1] or None
                    if next_line is not None and _starts_till(next_line, content) > -1:
                        skip = next_line
                    out.append(_get_line_indent(body[idx], content, indent))
            body = os.linesep.join(out)

        else:
            raise CommandExecutionError("Wrong conditions? "
                                        "Unable to ensure line without knowing "
                                        "where to put it before and/or after.")

    changed = body_before != hashlib.sha256(salt.utils.to_bytes(body)).hexdigest()

    if backup and changed and __opts__['test'] is False:
        try:
            temp_file = _mkstemp_copy(path=path, preserve_inode=True)
            shutil.move(temp_file, '{0}.{1}'.format(path, time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime())))
        except (OSError, IOError) as exc:
            raise CommandExecutionError("Unable to create the backup file of {0}. Exception: {1}".format(path, exc))

    changes_diff = None

    if changed:
        if show_changes:
            with salt.utils.fopen(path, 'r') as fp_:
                path_content = _splitlines_preserving_trailing_newline(
                    fp_.read())
            changes_diff = ''.join(difflib.unified_diff(
                path_content, _splitlines_preserving_trailing_newline(body)))
        if __opts__['test'] is False:
            fh_ = None
            try:
                fh_ = salt.utils.atomicfile.atomic_open(path, 'w')
                fh_.write(body)
            finally:
                if fh_:
                    fh_.close()

    return show_changes and changes_diff or changed


def replace(path,
            pattern,
            repl,
            count=0,
            flags=8,
            bufsize=1,
            append_if_not_found=False,
            prepend_if_not_found=False,
            not_found_content=None,
            backup='.bak',
            dry_run=False,
            search_only=False,
            show_changes=True,
            ignore_if_missing=False,
            preserve_inode=True,
        ):
    '''
    .. versionadded:: 0.17.0

    Replace occurrences of a pattern in a file. If ``show_changes`` is
    ``True``, then a diff of what changed will be returned, otherwise a
    ``True`` will be returned when changes are made, and ``False`` when
    no changes are made.

    This is a pure Python implementation that wraps Python's :py:func:`~re.sub`.

    path
        Filesystem path to the file to be edited. If a symlink is specified, it
        will be resolved to its target.

    pattern
        A regular expression, to be matched using Python's
        :py:func:`~re.search`.

    repl
        The replacement text

    count : 0
        Maximum number of pattern occurrences to be replaced. If count is a
        positive integer ``n``, only ``n`` occurrences will be replaced,
        otherwise all occurrences will be replaced.

    flags (list or int)
        A list of flags defined in the :ref:`re module documentation
        <contents-of-module-re>`. Each list item should be a string that will
        correlate to the human-friendly flag name. E.g., ``['IGNORECASE',
        'MULTILINE']``. Optionally, ``flags`` may be an int, with a value
        corresponding to the XOR (``|``) of all the desired flags. Defaults to
        8 (which supports 'MULTILINE').

    bufsize (int or str)
        How much of the file to buffer into memory at once. The
        default value ``1`` processes one line at a time. The special value
        ``file`` may be specified which will read the entire file into memory
        before processing.

    append_if_not_found : False
        .. versionadded:: 2014.7.0

        If set to ``True``, and pattern is not found, then the content will be
        appended to the file.

    prepend_if_not_found : False
        .. versionadded:: 2014.7.0

        If set to ``True`` and pattern is not found, then the content will be
        prepended to the file.

    not_found_content
        .. versionadded:: 2014.7.0

        Content to use for append/prepend if not found. If None (default), uses
        ``repl``. Useful when ``repl`` uses references to group in pattern.

    backup : .bak
        The file extension to use for a backup of the file before editing. Set
        to ``False`` to skip making a backup.

    dry_run : False
        If set to ``True``, no changes will be made to the file, the function
        will just return the changes that would have been made (or a
        ``True``/``False`` value if ``show_changes`` is set to ``False``).

    search_only : False
        If set to true, this no changes will be performed on the file, and this
        function will simply return ``True`` if the pattern was matched, and
        ``False`` if not.

    show_changes : True
        If ``True``, return a diff of changes made. Otherwise, return ``True``
        if changes were made, and ``False`` if not.

        .. note::
            Using this option will store two copies of the file in memory (the
            original version and the edited version) in order to generate the
            diff. This may not normally be a concern, but could impact
            performance if used with large files.

    ignore_if_missing : False
        .. versionadded:: 2015.8.0

        If set to ``True``, this function will simply return ``False``
        if the file doesn't exist. Otherwise, an error will be thrown.

    preserve_inode : True
        .. versionadded:: 2015.8.0

        Preserve the inode of the file, so that any hard links continue to
        share the inode with the original filename. This works by *copying* the
        file, reading from the copy, and writing to the file at the original
        inode. If ``False``, the file will be *moved* rather than copied, and a
        new file will be written to a new inode, but using the original
        filename. Hard links will then share an inode with the backup, instead
        (if using ``backup`` to create a backup copy).

    If an equal sign (``=``) appears in an argument to a Salt command it is
    interpreted as a keyword argument in the format ``key=val``. That
    processing can be bypassed in order to pass an equal sign through to the
    remote shell command by manually specifying the kwarg:

    .. code-block:: bash

        salt '*' file.replace /path/to/file pattern='=' repl=':'
        salt '*' file.replace /path/to/file pattern="bind-address\\s*=" repl='bind-address:'

    CLI Examples:

    .. code-block:: bash

        salt '*' file.replace /etc/httpd/httpd.conf pattern='LogLevel warn' repl='LogLevel info'
        salt '*' file.replace /some/file pattern='before' repl='after' flags='[MULTILINE, IGNORECASE]'
    '''
    symlink = False
    if is_link(path):
        symlink = True
        target_path = os.readlink(path)
        given_path = os.path.expanduser(path)

    path = os.path.realpath(os.path.expanduser(path))

    if not os.path.exists(path):
        if ignore_if_missing:
            return False
        else:
            raise SaltInvocationError('File not found: {0}'.format(path))

    if not salt.utils.istextfile(path):
        raise SaltInvocationError(
            'Cannot perform string replacements on a binary file: {0}'
            .format(path)
        )

    if search_only and (append_if_not_found or prepend_if_not_found):
        raise SaltInvocationError(
            'search_only cannot be used with append/prepend_if_not_found'
        )

    if append_if_not_found and prepend_if_not_found:
        raise SaltInvocationError(
            'Only one of append and prepend_if_not_found is permitted'
        )

    flags_num = _get_flags(flags)
    cpattern = re.compile(salt.utils.to_bytes(pattern), flags_num)
    filesize = os.path.getsize(path)
    if bufsize == 'file':
        bufsize = filesize

    # Search the file; track if any changes have been made for the return val
    has_changes = False
    orig_file = []  # used if show_changes
    new_file = []  # used if show_changes
    if not salt.utils.is_windows():
        pre_user = get_user(path)
        pre_group = get_group(path)
        pre_mode = salt.utils.normalize_mode(get_mode(path))

    # Avoid TypeErrors by forcing repl to be bytearray related to mmap
    # Replacement text may contains integer: 123 for example
    repl = salt.utils.to_bytes(str(repl))
    if not_found_content:
        not_found_content = salt.utils.to_bytes(not_found_content)

    found = False
    temp_file = None
    content = salt.utils.to_str(not_found_content) if not_found_content and \
                                       (prepend_if_not_found or
                                        append_if_not_found) \
                                     else salt.utils.to_str(repl)

    try:
        # First check the whole file, determine whether to make the replacement
        # Searching first avoids modifying the time stamp if there are no changes
        r_data = None
        # Use a read-only handle to open the file
        with salt.utils.fopen(path,
                              mode='rb',
                              buffering=bufsize) as r_file:
            try:
                # mmap throws a ValueError if the file is empty.
                r_data = mmap.mmap(r_file.fileno(),
                                   0,
                                   access=mmap.ACCESS_READ)
            except (ValueError, mmap.error):
                # size of file in /proc is 0, but contains data
                r_data = salt.utils.to_bytes("".join(r_file))
            if search_only:
                # Just search; bail as early as a match is found
                if re.search(cpattern, r_data):
                    return True  # `with` block handles file closure
            else:
                result, nrepl = re.subn(cpattern, repl, r_data, count)

                # found anything? (even if no change)
                if nrepl > 0:
                    found = True
                    # Identity check the potential change
                    has_changes = True if pattern != repl else has_changes

                if prepend_if_not_found or append_if_not_found:
                    # Search for content, to avoid pre/appending the
                    # content if it was pre/appended in a previous run.
                    if re.search(salt.utils.to_bytes('^{0}$'.format(re.escape(content))),
                                 r_data,
                                 flags=flags_num):
                        # Content was found, so set found.
                        found = True

                # Keep track of show_changes here, in case the file isn't
                # modified
                if show_changes or append_if_not_found or \
                   prepend_if_not_found:
                    orig_file = r_data.read(filesize).splitlines(True) \
                        if isinstance(r_data, mmap.mmap) \
                        else r_data.splitlines(True)
                    new_file = result.splitlines(True)

    except (OSError, IOError) as exc:
        raise CommandExecutionError(
            "Unable to open file '{0}'. "
            "Exception: {1}".format(path, exc)
            )
    finally:
        if r_data and isinstance(r_data, mmap.mmap):
            r_data.close()

    if has_changes and not dry_run:
        # Write the replacement text in this block.
        try:
            # Create a copy to read from and to use as a backup later
            temp_file = _mkstemp_copy(path=path,
                                      preserve_inode=preserve_inode)
        except (OSError, IOError) as exc:
            raise CommandExecutionError("Exception: {0}".format(exc))

        r_data = None
        try:
            # Open the file in write mode
            with salt.utils.fopen(path,
                        mode='w',
                        buffering=bufsize) as w_file:
                try:
                    # Open the temp file in read mode
                    with salt.utils.fopen(temp_file,
                                          mode='r',
                                          buffering=bufsize) as r_file:
                        r_data = mmap.mmap(r_file.fileno(),
                                           0,
                                           access=mmap.ACCESS_READ)
                        result, nrepl = re.subn(cpattern, repl,
                                                r_data, count)
                        try:
                            w_file.write(salt.utils.to_str(result))
                        except (OSError, IOError) as exc:
                            raise CommandExecutionError(
                                "Unable to write file '{0}'. Contents may "
                                "be truncated. Temporary file contains copy "
                                "at '{1}'. "
                                "Exception: {2}".format(path, temp_file, exc)
                                )
                except (OSError, IOError) as exc:
                    raise CommandExecutionError("Exception: {0}".format(exc))
                finally:
                    if r_data and isinstance(r_data, mmap.mmap):
                        r_data.close()
        except (OSError, IOError) as exc:
            raise CommandExecutionError("Exception: {0}".format(exc))

    if not found and (append_if_not_found or prepend_if_not_found):
        if not_found_content is None:
            not_found_content = repl
        if prepend_if_not_found:
            new_file.insert(0, not_found_content + b'\n')
        else:
            # append_if_not_found
            # Make sure we have a newline at the end of the file
            if 0 != len(new_file):
                if not new_file[-1].endswith(b'\n'):
                    new_file[-1] += b'\n'
            new_file.append(not_found_content + b'\n')
        has_changes = True
        if not dry_run:
            try:
                # Create a copy to read from and for later use as a backup
                temp_file = _mkstemp_copy(path=path,
                                          preserve_inode=preserve_inode)
            except (OSError, IOError) as exc:
                raise CommandExecutionError("Exception: {0}".format(exc))
            # write new content in the file while avoiding partial reads
            try:
                fh_ = salt.utils.atomicfile.atomic_open(path, 'w')
                for line in new_file:
                    fh_.write(salt.utils.to_str(line))
            finally:
                fh_.close()

    if backup and has_changes and not dry_run:
        # keep the backup only if it was requested
        # and only if there were any changes
        backup_name = '{0}{1}'.format(path, backup)
        try:
            shutil.move(temp_file, backup_name)
        except (OSError, IOError) as exc:
            raise CommandExecutionError(
                "Unable to move the temp file '{0}' to the "
                "backup file '{1}'. "
                "Exception: {2}".format(path, temp_file, exc)
                )
        if symlink:
            symlink_backup = '{0}{1}'.format(given_path, backup)
            target_backup = '{0}{1}'.format(target_path, backup)
            # Always clobber any existing symlink backup
            # to match the behaviour of the 'backup' option
            try:
                os.symlink(target_backup, symlink_backup)
            except OSError:
                os.remove(symlink_backup)
                os.symlink(target_backup, symlink_backup)
            except:
                raise CommandExecutionError(
                    "Unable create backup symlink '{0}'. "
                    "Target was '{1}'. "
                    "Exception: {2}".format(symlink_backup, target_backup,
                                            exc)
                    )
    elif temp_file:
        try:
            os.remove(temp_file)
        except (OSError, IOError) as exc:
            raise CommandExecutionError(
                "Unable to delete temp file '{0}'. "
                "Exception: {1}".format(temp_file, exc)
                )

    if not dry_run and not salt.utils.is_windows():
        check_perms(path, None, pre_user, pre_group, pre_mode)

    if show_changes:
        orig_file_as_str = ''.join([salt.utils.to_str(x) for x in orig_file])
        new_file_as_str = ''.join([salt.utils.to_str(x) for x in new_file])
        return ''.join(difflib.unified_diff(orig_file_as_str, new_file_as_str))

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
        append_newline=False,
        ):
    '''
    .. versionadded:: 2014.1.0

    Replace content of a text block in a file, delimited by line markers

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
        whitespace or extra content before or after the marker is included in
        final output

    marker_end
        The line content identifying a line as the end of the content block.
        Note that the whole line containing this marker will be considered, so
        whitespace or extra content before or after the marker is included in
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

    append_newline:
        Append a newline to the content block. For more information see:
        https://github.com/saltstack/salt/issues/33686

        .. versionadded:: 2016.3.4

    CLI Example:

    .. code-block:: bash

        salt '*' file.blockreplace /etc/hosts '#-- start managed zone foobar : DO NOT EDIT --' \\
        '#-- end managed zone foobar --' $'10.0.1.1 foo.foobar\\n10.0.1.2 bar.foobar' True

    '''
    path = os.path.expanduser(path)

    if not os.path.exists(path):
        raise SaltInvocationError('File not found: {0}'.format(path))

    if append_if_not_found and prepend_if_not_found:
        raise SaltInvocationError(
            'Only one of append and prepend_if_not_found is permitted'
        )

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
    # written file.
    # we could also use salt.utils.filebuffer.BufferedReader
    try:
        fi_file = fileinput.input(path,
                    inplace=False, backup=False,
                    bufsize=1, mode='r')
        for line in fi_file:

            result = line

            if marker_start in line:
                # managed block start found, start recording
                in_block = True

            else:
                if in_block:
                    if marker_end in line:
                        # end of block detected
                        in_block = False

                        # Check for multi-line '\n' terminated content as split will
                        # introduce an unwanted additional new line.
                        if content and content[-1] == '\n':
                            content = content[:-1]

                        # push new block content in file
                        for cline in content.split('\n'):
                            new_file.append(cline + '\n')

                        done = True

                    else:
                        # remove old content, but keep a trace
                        old_content += line
                        result = None
            # else: we are not in the marked block, keep saving things

            orig_file.append(line)
            if result is not None:
                new_file.append(result)
        # end for. If we are here without block management we maybe have some problems,
        # or we need to initialise the marked block

    finally:
        fi_file.close()

    if in_block:
        # unterminated block => bad, always fail
        raise CommandExecutionError(
            'Unterminated marked block. End of file reached before marker_end.'
        )

    if not done:
        if prepend_if_not_found:
            # add the markers and content at the beginning of file
            new_file.insert(0, marker_end + '\n')
            if append_newline is True:
                new_file.insert(0, content + '\n')
            else:
                new_file.insert(0, content)
            new_file.insert(0, marker_start + '\n')
            done = True
        elif append_if_not_found:
            # Make sure we have a newline at the end of the file
            if 0 != len(new_file):
                if not new_file[-1].endswith('\n'):
                    new_file[-1] += '\n'
            # add the markers and content at the end of file
            new_file.append(marker_start + '\n')
            if append_newline is True:
                new_file.append(content + '\n')
            else:
                new_file.append(content)
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
            # backup file attrs
            perms = {}
            perms['user'] = get_user(path)
            perms['group'] = get_group(path)
            perms['mode'] = salt.utils.normalize_mode(get_mode(path))

            # backup old content
            if backup is not False:
                backup_path = '{0}{1}'.format(path, backup)
                shutil.copy2(path, backup_path)
                # copy2 does not preserve ownership
                check_perms(backup_path,
                        None,
                        perms['user'],
                        perms['group'],
                        perms['mode'])

            # write new content in the file while avoiding partial reads
            try:
                fh_ = salt.utils.atomicfile.atomic_open(path, 'w')
                for line in new_file:
                    fh_.write(line)
            finally:
                fh_.close()

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
        flags=8,
        bufsize=1,
        ignore_if_missing=False,
        multiline=False
        ):
    '''
    .. versionadded:: 0.17.0

    Search for occurrences of a pattern in a file

    Except for multiline, params are identical to
    :py:func:`~salt.modules.file.replace`.

    multiline
        If true, inserts 'MULTILINE' into ``flags`` and sets ``bufsize`` to
        'file'.

        .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' file.search /etc/crontab 'mymaintenance.sh'
    '''
    if multiline:
        flags = _add_flags(flags, 'MULTILINE')
        bufsize = 'file'

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
            show_changes=False,
            ignore_if_missing=ignore_if_missing)


def patch(originalfile, patchfile, options='', dry_run=False):
    '''
    .. versionadded:: 0.10.4

    Apply a patch to a file or directory.

    Equivalent to:

    .. code-block:: bash

        patch <options> -i <patchfile> <originalfile>

    Or, when a directory is patched:

    .. code-block:: bash

        patch <options> -i <patchfile> -d <originalfile> -p0

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
    patchpath = salt.utils.which('patch')
    if not patchpath:
        raise CommandExecutionError(
            'patch executable not found. Is the distribution\'s patch '
            'package installed?'
        )

    cmd = [patchpath]
    cmd.extend(salt.utils.shlex_split(options))
    if dry_run:
        if __grains__['kernel'] in ('FreeBSD', 'OpenBSD'):
            cmd.append('-C')
        else:
            cmd.append('--dry-run')

    # this argument prevents interactive prompts when the patch fails to apply.
    # the exit code will still be greater than 0 if that is the case.
    if '-N' not in cmd and '--forward' not in cmd:
        cmd.append('--forward')

    has_rejectfile_option = False
    for option in cmd:
        if option == '-r' or option.startswith('-r ') \
                or option.startswith('--reject-file'):
            has_rejectfile_option = True
            break

    # by default, patch will write rejected patch files to <filename>.rej.
    # this option prevents that.
    if not has_rejectfile_option:
        cmd.append('--reject-file=-')

    cmd.extend(['-i', patchfile])

    if os.path.isdir(originalfile):
        cmd.extend(['-d', originalfile])

        has_strip_option = False
        for option in cmd:
            if option.startswith('-p') or option.startswith('--strip='):
                has_strip_option = True
                break

        if not has_strip_option:
            cmd.append('--strip=0')
    else:
        cmd.append(originalfile)

    return __salt__['cmd.run_all'](cmd, python_shell=False)


def contains(path, text):
    '''
    .. deprecated:: 0.17.0
       Use :func:`search` instead.

    Return ``True`` if the file at ``path`` contains ``text``

    CLI Example:

    .. code-block:: bash

        salt '*' file.contains /etc/crontab 'mymaintenance.sh'
    '''
    path = os.path.expanduser(path)

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
    path = os.path.expanduser(path)

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


def contains_glob(path, glob_expr):
    '''
    .. deprecated:: 0.17.0
       Use :func:`search` instead.

    Return ``True`` if the given glob matches a string in the named file

    CLI Example:

    .. code-block:: bash

        salt '*' file.contains_glob /etc/foobar '*cheese*'
    '''
    path = os.path.expanduser(path)

    if not os.path.exists(path):
        return False

    try:
        with salt.utils.filebuffer.BufferedReader(path) as breader:
            for chunk in breader:
                if fnmatch.fnmatch(chunk, glob_expr):
                    return True
            return False
    except (IOError, OSError):
        return False


def append(path, *args, **kwargs):
    '''
    .. versionadded:: 0.9.5

    Append text to the end of a file

    path
        path to file

    `*args`
        strings to append to file

    CLI Example:

    .. code-block:: bash

        salt '*' file.append /etc/motd \\
                "With all thine offerings thou shalt offer salt." \\
                "Salt is what makes things taste bad when it isn't in them."

    .. admonition:: Attention

        If you need to pass a string to append and that string contains
        an equal sign, you **must** include the argument name, args.
        For example:

        .. code-block:: bash

            salt '*' file.append /etc/motd args='cheese=spam'

            salt '*' file.append /etc/motd args="['cheese=spam','spam=cheese']"

    '''
    path = os.path.expanduser(path)

    # Largely inspired by Fabric's contrib.files.append()

    if 'args' in kwargs:
        if isinstance(kwargs['args'], list):
            args = kwargs['args']
        else:
            args = [kwargs['args']]

    # Make sure we have a newline at the end of the file. Do this in binary
    # mode so SEEK_END with nonzero offset will work.
    with salt.utils.fopen(path, 'rb+') as ofile:
        linesep = salt.utils.to_bytes(os.linesep)
        try:
            ofile.seek(-len(linesep), os.SEEK_END)
        except IOError as exc:
            if exc.errno in (errno.EINVAL, errno.ESPIPE):
                # Empty file, simply append lines at the beginning of the file
                pass
            else:
                raise
        else:
            if ofile.read(len(linesep)) != linesep:
                ofile.seek(0, os.SEEK_END)
                ofile.write(linesep)

    # Append lines in text mode
    with salt.utils.fopen(path, 'a') as ofile:
        for new_line in args:
            ofile.write('{0}{1}'.format(new_line, os.linesep))

    return 'Wrote {0} lines to "{1}"'.format(len(args), path)


def prepend(path, *args, **kwargs):
    '''
    .. versionadded:: 2014.7.0

    Prepend text to the beginning of a file

    path
        path to file

    `*args`
        strings to prepend to the file

    CLI Example:

    .. code-block:: bash

        salt '*' file.prepend /etc/motd \\
                "With all thine offerings thou shalt offer salt." \\
                "Salt is what makes things taste bad when it isn't in them."

    .. admonition:: Attention

        If you need to pass a string to append and that string contains
        an equal sign, you **must** include the argument name, args.
        For example:

        .. code-block:: bash

            salt '*' file.prepend /etc/motd args='cheese=spam'

            salt '*' file.prepend /etc/motd args="['cheese=spam','spam=cheese']"

    '''
    path = os.path.expanduser(path)

    if 'args' in kwargs:
        if isinstance(kwargs['args'], list):
            args = kwargs['args']
        else:
            args = [kwargs['args']]

    try:
        with salt.utils.fopen(path) as fhr:
            contents = fhr.readlines()
    except IOError:
        contents = []

    preface = []
    for line in args:
        preface.append('{0}\n'.format(line))

    with salt.utils.fopen(path, "w") as ofile:
        contents = preface + contents
        ofile.write(''.join(contents))
    return 'Prepended {0} lines to "{1}"'.format(len(args), path)


def write(path, *args, **kwargs):
    '''
    .. versionadded:: 2014.7.0

    Write text to a file, overwriting any existing contents.

    path
        path to file

    `*args`
        strings to write to the file

    CLI Example:

    .. code-block:: bash

        salt '*' file.write /etc/motd \\
                "With all thine offerings thou shalt offer salt."

    .. admonition:: Attention

        If you need to pass a string to append and that string contains
        an equal sign, you **must** include the argument name, args.
        For example:

        .. code-block:: bash

            salt '*' file.write /etc/motd args='cheese=spam'

            salt '*' file.write /etc/motd args="['cheese=spam','spam=cheese']"

    '''
    path = os.path.expanduser(path)

    if 'args' in kwargs:
        if isinstance(kwargs['args'], list):
            args = kwargs['args']
        else:
            args = [kwargs['args']]

    contents = []
    for line in args:
        contents.append('{0}\n'.format(line))
    with salt.utils.fopen(path, "w") as ofile:
        ofile.write(''.join(contents))
    return 'Wrote {0} lines to "{1}"'.format(len(contents), path)


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
    name = os.path.expanduser(name)

    if atime and atime.isdigit():
        atime = int(atime)
    if mtime and mtime.isdigit():
        mtime = int(mtime)
    try:
        if not os.path.exists(name):
            with salt.utils.fopen(name, 'a') as fhw:
                fhw.write('')

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
    .. versionadded:: 2014.1.0

    Seek to a position on a file and read it

    path
        path to file

    seek
        amount to read at once

    offset
        offset to start into the file

    CLI Example:

    .. code-block:: bash

        salt '*' file.seek_read /path/to/file 4096 0
    '''
    path = os.path.expanduser(path)
    try:
        seek_fh = os.open(path, os.O_RDONLY)
        os.lseek(seek_fh, int(offset), 0)
        data = os.read(seek_fh, int(size))
    finally:
        os.close(seek_fh)
    return data


def seek_write(path, data, offset):
    '''
    .. versionadded:: 2014.1.0

    Seek to a position on a file and write to it

    path
        path to file

    data
        data to write to file

    offset
        position in file to start writing

    CLI Example:

    .. code-block:: bash

        salt '*' file.seek_write /path/to/file 'some data' 4096
    '''
    path = os.path.expanduser(path)
    try:
        seek_fh = os.open(path, os.O_WRONLY)
        os.lseek(seek_fh, int(offset), 0)
        ret = os.write(seek_fh, data)
        os.fsync(seek_fh)
    finally:
        os.close(seek_fh)
    return ret


def truncate(path, length):
    '''
    .. versionadded:: 2014.1.0

    Seek to a position on a file and delete everything after that point

    path
        path to file

    length
        offset into file to truncate

    CLI Example:

    .. code-block:: bash

        salt '*' file.truncate /path/to/file 512
    '''
    path = os.path.expanduser(path)
    with salt.utils.fopen(path, 'rb+') as seek_fh:
        seek_fh.truncate(int(length))


def link(src, path):
    '''
    .. versionadded:: 2014.1.0

    Create a hard link to a file

    CLI Example:

    .. code-block:: bash

        salt '*' file.link /path/to/file /path/to/link
    '''
    src = os.path.expanduser(src)

    if not os.path.isabs(src):
        raise SaltInvocationError('File path must be absolute.')

    try:
        os.link(src, path)
        return True
    except (OSError, IOError):
        raise CommandExecutionError('Could not create \'{0}\''.format(path))
    return False


def is_link(path):
    '''
    Check if the path is a symbolic link

    CLI Example:

    .. code-block:: bash

       salt '*' file.is_link /path/to/link
    '''
    # This function exists because os.path.islink does not support Windows,
    # therefore a custom function will need to be called. This function
    # therefore helps API consistency by providing a single function to call for
    # both operating systems.

    return os.path.islink(os.path.expanduser(path))


def symlink(src, path):
    '''
    Create a symbolic link (symlink, soft link) to a file

    CLI Example:

    .. code-block:: bash

        salt '*' file.symlink /path/to/file /path/to/link
    '''
    path = os.path.expanduser(path)

    if not os.path.isabs(path):
        raise SaltInvocationError('File path must be absolute.')

    try:
        os.symlink(src, path)
        return True
    except (OSError, IOError):
        raise CommandExecutionError('Could not create \'{0}\''.format(path))
    return False


def rename(src, dst):
    '''
    Rename a file or directory

    CLI Example:

    .. code-block:: bash

        salt '*' file.rename /path/to/src /path/to/dst
    '''
    src = os.path.expanduser(src)
    dst = os.path.expanduser(dst)

    if not os.path.isabs(src):
        raise SaltInvocationError('File path must be absolute.')

    try:
        os.rename(src, dst)
        return True
    except OSError:
        raise CommandExecutionError(
            'Could not rename \'{0}\' to \'{1}\''.format(src, dst)
        )
    return False


def copy(src, dst, recurse=False, remove_existing=False):
    '''
    Copy a file or directory from source to dst

    In order to copy a directory, the recurse flag is required, and
    will by default overwrite files in the destination with the same path,
    and retain all other existing files. (similar to cp -r on unix)

    remove_existing will remove all files in the target directory,
    and then copy files from the source.

    .. note::
        The copy function accepts paths that are local to the Salt minion.
        This function does not support salt://, http://, or the other
        additional file paths that are supported by :mod:`states.file.managed
        <salt.states.file.managed>` and :mod:`states.file.recurse
        <salt.states.file.recurse>`.

    CLI Example:

    .. code-block:: bash

        salt '*' file.copy /path/to/src /path/to/dst
        salt '*' file.copy /path/to/src_dir /path/to/dst_dir recurse=True
        salt '*' file.copy /path/to/src_dir /path/to/dst_dir recurse=True remove_existing=True

    '''
    src = os.path.expanduser(src)
    dst = os.path.expanduser(dst)

    if not os.path.isabs(src):
        raise SaltInvocationError('File path must be absolute.')

    if not os.path.exists(src):
        raise CommandExecutionError('No such file or directory \'{0}\''.format(src))

    if not salt.utils.is_windows():
        pre_user = get_user(src)
        pre_group = get_group(src)
        pre_mode = salt.utils.normalize_mode(get_mode(src))

    try:
        if (os.path.exists(dst) and os.path.isdir(dst)) or os.path.isdir(src):
            if not recurse:
                raise SaltInvocationError(
                    "Cannot copy overwriting a directory without recurse flag set to true!")
            if remove_existing:
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                salt.utils.files.recursive_copy(src, dst)
        else:
            shutil.copyfile(src, dst)
    except OSError:
        raise CommandExecutionError(
            'Could not copy \'{0}\' to \'{1}\''.format(src, dst)
        )

    if not salt.utils.is_windows():
        check_perms(dst, None, pre_user, pre_group, pre_mode)
    return True


def lstat(path):
    '''
    .. versionadded:: 2014.1.0

    Returns the lstat attributes for the given file or dir. Does not support
    symbolic links.

    CLI Example:

    .. code-block:: bash

        salt '*' file.lstat /path/to/file
    '''
    path = os.path.expanduser(path)

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
    .. versionadded:: 2014.1.0

    Test whether the Salt process has the specified access to the file. One of
    the following modes must be specified:

    .. code-block::text

        f: Test the existence of the path
        r: Test the readability of the path
        w: Test the writability of the path
        x: Test whether the path can be executed

    CLI Example:

    .. code-block:: bash

        salt '*' file.access /path/to/file f
        salt '*' file.access /path/to/file x
    '''
    path = os.path.expanduser(path)

    if not os.path.isabs(path):
        raise SaltInvocationError('Path to link must be absolute.')

    modes = {'f': os.F_OK,
             'r': os.R_OK,
             'w': os.W_OK,
             'x': os.X_OK}

    if mode in modes:
        return os.access(path, modes[mode])
    elif mode in six.itervalues(modes):
        return os.access(path, mode)
    else:
        raise SaltInvocationError('Invalid mode specified.')


def readlink(path, canonicalize=False):
    '''
    .. versionadded:: 2014.1.0

    Return the path that a symlink points to
    If canonicalize is set to True, then it return the final target

    CLI Example:

    .. code-block:: bash

        salt '*' file.readlink /path/to/link
    '''
    path = os.path.expanduser(path)

    if not os.path.isabs(path):
        raise SaltInvocationError('Path to link must be absolute.')

    if not os.path.islink(path):
        raise SaltInvocationError('A valid link was not specified.')

    if canonicalize:
        return os.path.realpath(path)
    else:
        return os.readlink(path)


def readdir(path):
    '''
    .. versionadded:: 2014.1.0

    Return a list containing the contents of a directory

    CLI Example:

    .. code-block:: bash

        salt '*' file.readdir /path/to/dir/
    '''
    path = os.path.expanduser(path)

    if not os.path.isabs(path):
        raise SaltInvocationError('Dir path must be absolute.')

    if not os.path.isdir(path):
        raise SaltInvocationError('A valid directory was not specified.')

    dirents = ['.', '..']
    dirents.extend(os.listdir(path))
    return dirents


def statvfs(path):
    '''
    .. versionadded:: 2014.1.0

    Perform a statvfs call against the filesystem that the file resides on

    CLI Example:

    .. code-block:: bash

        salt '*' file.statvfs /path/to/file
    '''
    path = os.path.expanduser(path)

    if not os.path.isabs(path):
        raise SaltInvocationError('File path must be absolute.')

    try:
        stv = os.statvfs(path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))
    except (OSError, IOError):
        raise CommandExecutionError('Could not statvfs \'{0}\''.format(path))
    return False


def stats(path, hash_type=None, follow_symlinks=True):
    '''
    Return a dict containing the stats for a given file

    CLI Example:

    .. code-block:: bash

        salt '*' file.stats /etc/passwd
    '''
    path = os.path.expanduser(path)

    ret = {}
    if not os.path.exists(path):
        try:
            # Broken symlinks will return False for os.path.exists(), but still
            # have a uid and gid
            pstat = os.lstat(path)
        except OSError:
            # Not a broken symlink, just a nonexistent path
            return ret
    else:
        if follow_symlinks:
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
    if hash_type:
        ret['sum'] = get_hash(path, hash_type)
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
    .. versionadded:: 2014.1.0

    Remove the specified directory. Fails if a directory is not empty.

    CLI Example:

    .. code-block:: bash

        salt '*' file.rmdir /tmp/foo/
    '''
    path = os.path.expanduser(path)

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
    Remove the named file. If a directory is supplied, it will be recursively
    deleted.

    CLI Example:

    .. code-block:: bash

        salt '*' file.remove /tmp/foo
    '''
    path = os.path.expanduser(path)

    if not os.path.isabs(path):
        raise SaltInvocationError('File path must be absolute: {0}'.format(path))

    try:
        if os.path.isfile(path) or os.path.islink(path):
            os.remove(path)
            return True
        elif os.path.isdir(path):
            shutil.rmtree(path)
            return True
    except (OSError, IOError) as exc:
        raise CommandExecutionError(
            'Could not remove \'{0}\': {1}'.format(path, exc)
        )
    return False


def directory_exists(path):
    '''
    Tests to see if path is a valid directory.  Returns True/False.

    CLI Example:

    .. code-block:: bash

        salt '*' file.directory_exists /etc

    '''
    return os.path.isdir(os.path.expanduser(path))


def file_exists(path):
    '''
    Tests to see if path is a valid file.  Returns True/False.

    CLI Example:

    .. code-block:: bash

        salt '*' file.file_exists /etc/passwd

    '''
    return os.path.isfile(os.path.expanduser(path))


def path_exists_glob(path):
    '''
    Tests to see if path after expansion is a valid path (file or directory).
    Expansion allows usage of ? * and character ranges []. Tilde expansion
    is not supported. Returns True/False.

    .. versionadded:: Hellium

    CLI Example:

    .. code-block:: bash

        salt '*' file.path_exists_glob /etc/pam*/pass*

    '''
    return True if glob.glob(os.path.expanduser(path)) else False


def restorecon(path, recursive=False):
    '''
    Reset the SELinux context on a given path

    CLI Example:

    .. code-block:: bash

         salt '*' file.restorecon /home/user/.ssh/authorized_keys
    '''
    if recursive:
        cmd = ['restorecon', '-FR', path]
    else:
        cmd = ['restorecon', '-F', path]
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def get_selinux_context(path):
    '''
    Get an SELinux context from a given path

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_selinux_context /etc/hosts
    '''
    out = __salt__['cmd.run'](['ls', '-Z', path], python_shell=False)

    try:
        ret = re.search(r'\w+:\w+:\w+:\w+', out).group(0)
    except AttributeError:
        ret = (
            'No selinux context information is available for {0}'.format(path)
        )

    return ret


def set_selinux_context(path,
                        user=None,
                        role=None,
                        type=None,    # pylint: disable=W0622
                        range=None):  # pylint: disable=W0622
    '''
    Set a specific SELinux label on a given path

    CLI Example:

    .. code-block:: bash

        salt '*' file.set_selinux_context path <role> <type> <range>
    '''
    if not any((user, role, type, range)):
        return False

    cmd = ['chcon']
    if user:
        cmd.extend(['-u', user])
    if role:
        cmd.extend(['-r', role])
    if type:
        cmd.extend(['-t', type])
    if range:
        cmd.extend(['-l', range])
    cmd.append(path)

    ret = not __salt__['cmd.retcode'](cmd, python_shell=False)
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
    contextkey = '{0}_|-{1}_|-{2}'.format(source, source_hash, saltenv)
    if contextkey in __context__:
        return __context__[contextkey]

    # get the master file list
    if isinstance(source, list):
        mfiles = [(f, saltenv) for f in __salt__['cp.list_master'](saltenv)]
        mdirs = [(d, saltenv) for d in __salt__['cp.list_master_dirs'](saltenv)]
        for single in source:
            if isinstance(single, dict):
                single = next(iter(single))

            path, senv = salt.utils.url.parse(single)
            if senv:
                mfiles += [(f, senv) for f in __salt__['cp.list_master'](senv)]
                mdirs += [(d, senv) for d in __salt__['cp.list_master_dirs'](senv)]

        ret = None
        for single in source:
            if isinstance(single, dict):
                # check the proto, if it is http or ftp then download the file
                # to check, if it is salt then check the master list
                # if it is a local file, check if the file exists
                if len(single) != 1:
                    continue
                single_src = next(iter(single))
                single_hash = single[single_src] if single[single_src] else source_hash
                urlparsed_single_src = _urlparse(single_src)
                proto = urlparsed_single_src.scheme
                if proto == 'salt':
                    path, senv = salt.utils.url.parse(single_src)
                    if not senv:
                        senv = saltenv
                    if (path, saltenv) in mfiles or (path, saltenv) in mdirs:
                        ret = (single_src, single_hash)
                        break
                elif proto.startswith('http') or proto == 'ftp':
                    try:
                        if __salt__['cp.cache_file'](single_src):
                            ret = (single_src, single_hash)
                            break
                    except MinionError as exc:
                        # Error downloading file. Log the caught exception and
                        # continue on to the next source.
                        log.exception(exc)
                elif proto == 'file' and os.path.exists(urlparsed_single_src.path):
                    ret = (single_src, single_hash)
                    break
                elif single_src.startswith('/') and os.path.exists(single_src):
                    ret = (single_src, single_hash)
                    break
            elif isinstance(single, six.string_types):
                path, senv = salt.utils.url.parse(single)
                if not senv:
                    senv = saltenv
                if (path, senv) in mfiles or (path, senv) in mdirs:
                    ret = (single, source_hash)
                    break
                urlparsed_src = _urlparse(single)
                proto = urlparsed_src.scheme
                if proto == 'file' and os.path.exists(urlparsed_src.path):
                    ret = (single, source_hash)
                    break
                elif proto.startswith('http') or proto == 'ftp':
                    if __salt__['cp.cache_file'](single):
                        ret = (single, source_hash)
                        break
                elif single.startswith('/') and os.path.exists(single):
                    ret = (single, source_hash)
                    break
        if ret is None:
            # None of the list items matched
            raise CommandExecutionError(
                'none of the specified sources were found'
            )
    else:
        ret = (source, source_hash)

    __context__[contextkey] = ret
    return ret


def apply_template_on_contents(
        contents,
        template,
        context,
        defaults,
        saltenv):
    '''
    Return the contents after applying the templating engine

    contents
        template string

    template
        template format

    context
        Overrides default context variables passed to the template.

    defaults
        Default context passed to the template.

    CLI Example:

    .. code-block:: bash

        salt '*' file.apply_template_on_contents \\
            contents='This is a {{ template }} string.' \\
            template=jinja \\
            "context={}" "defaults={'template': 'cool'}" \\
            saltenv=base
    '''
    if template in salt.utils.templates.TEMPLATE_REGISTRY:
        context_dict = defaults if defaults else {}
        if context:
            context_dict.update(context)
        # Apply templating
        contents = salt.utils.templates.TEMPLATE_REGISTRY[template](
            contents,
            from_str=True,
            to_str=True,
            context=context_dict,
            saltenv=saltenv,
            grains=__opts__['grains'],
            pillar=__pillar__,
            salt=__salt__,
            opts=__opts__)['data']
        if six.PY2:
            contents = contents.encode('utf-8')
    else:
        ret = {}
        ret['result'] = False
        ret['comment'] = ('Specified template format {0} is not supported'
                          ).format(template)
        return ret
    return contents


def get_managed(
        name,
        template,
        source,
        source_hash,
        source_hash_name,
        user,
        group,
        mode,
        saltenv,
        context,
        defaults,
        skip_verify=False,
        **kwargs):
    '''
    Return the managed file data for file.managed

    name
        location where the file lives on the server

    template
        template format

    source
        managed source file

    source_hash
        hash of the source file

    source_hash_name
        When ``source_hash`` refers to a remote file, this specifies the
        filename to look for in that file.

        .. versionadded:: 2016.3.5

    user
        Owner of file

    group
        Group owner of file

    mode
        Permissions of file

    context
        Variables to add to the template context

    defaults
        Default values of for context_dict

    skip_verify
        If ``True``, hash verification of remote file sources (``http://``,
        ``https://``, ``ftp://``) will be skipped, and the ``source_hash``
        argument will be ignored.

        .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_managed /etc/httpd/conf.d/httpd.conf jinja salt://http/httpd.conf '{hash_type: 'md5', 'hsum': <md5sum>}' None root root '755' base None None
    '''
    # Copy the file to the minion and templatize it
    sfn = ''
    source_sum = {}

    def _get_local_file_source_sum(path):
        '''
        DRY helper for getting the source_sum value from a locally cached
        path.
        '''
        return {'hsum': get_hash(path, form='sha256'), 'hash_type': 'sha256'}

    # If we have a source defined, let's figure out what the hash is
    if source:
        urlparsed_source = _urlparse(source)
        parsed_scheme = urlparsed_source.scheme
        parsed_path = os.path.join(
                urlparsed_source.netloc, urlparsed_source.path).rstrip(os.sep)

        if parsed_scheme and parsed_scheme.lower() in 'abcdefghijklmnopqrstuvwxyz':
            parsed_path = ':'.join([parsed_scheme, parsed_path])
            parsed_scheme = 'file'

        if parsed_scheme == 'salt':
            source_sum = __salt__['cp.hash_file'](source, saltenv)
            if not source_sum:
                return '', {}, 'Source file {0} not found'.format(source)
        elif not source_hash and parsed_scheme == 'file':
            source_sum = _get_local_file_source_sum(parsed_path)
        elif not source_hash and source.startswith(os.sep):
            source_sum = _get_local_file_source_sum(source)
        else:
            if not skip_verify:
                if source_hash:
                    try:
                        source_sum = get_source_sum(name,
                                                    source,
                                                    source_hash,
                                                    source_hash_name,
                                                    saltenv)
                    except CommandExecutionError as exc:
                        return '', {}, exc.strerror
                else:
                    msg = (
                        'Unable to verify upstream hash of source file {0}, '
                        'please set source_hash or set skip_verify to True'
                        .format(source)
                    )
                    return '', {}, msg

    if source and (template or parsed_scheme in salt.utils.files.REMOTE_PROTOS):
        # Check if we have the template or remote file cached
        cache_refetch = False
        cached_dest = __salt__['cp.is_cached'](source, saltenv)
        if cached_dest and (source_hash or skip_verify):
            htype = source_sum.get('hash_type', 'sha256')
            cached_sum = get_hash(cached_dest, form=htype)
            if skip_verify:
                # prev: if skip_verify or cached_sum == source_sum['hsum']:
                # but `cached_sum == source_sum['hsum']` is elliptical as prev if
                sfn = cached_dest
                source_sum = {'hsum': cached_sum, 'hash_type': htype}
            elif cached_sum != source_sum['hsum']:
                cache_refetch = True

        # If we didn't have the template or remote file, let's get it
        # Similarly when the file has been updated and the cache has to be refreshed
        if not sfn or cache_refetch:
            try:
                sfn = __salt__['cp.cache_file'](source, saltenv)
            except Exception as exc:
                # A 404 or other error code may raise an exception, catch it
                # and return a comment that will fail the calling state.
                return '', {}, 'Failed to cache {0}: {1}'.format(source, exc)

        # If cache failed, sfn will be False, so do a truth check on sfn first
        # as invoking os.path.exists() on a bool raises a TypeError.
        if not sfn or not os.path.exists(sfn):
            return sfn, {}, 'Source file \'{0}\' not found'.format(source)
        if sfn == name:
            raise SaltInvocationError(
                'Source file cannot be the same as destination'
            )

        if template:
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
                    grains=__opts__['grains'],
                    opts=__opts__,
                    **kwargs)
            else:
                return sfn, {}, ('Specified template format {0} is not supported'
                                 ).format(template)

            if data['result']:
                sfn = data['data']
                hsum = get_hash(sfn, form='sha256')
                source_sum = {'hash_type': 'sha256',
                              'hsum': hsum}
            else:
                __clean_tmp(sfn)
                return sfn, {}, data['data']

    return sfn, source_sum, ''


def extract_hash(hash_fn,
                 hash_type='sha256',
                 file_name='',
                 source='',
                 source_hash_name=None):
    '''
    .. versionchanged:: 2016.3.5
        Prior to this version, only the ``file_name`` argument was considered
        for filename matches in the hash file. This would be problematic for
        cases in which the user was relying on a remote checksum file that they
        do not control, and they wished to use a different name for that file
        on the minion from the filename on the remote server (and in the
        checksum file). For example, managing ``/tmp/myfile.tar.gz`` when the
        remote file was at ``https://mydomain.tld/different_name.tar.gz``. The
        :py:func:`file.managed <salt.states.file.managed>` state now also
        passes this function the source URI as well as the ``source_hash_name``
        (if specified). In cases where ``source_hash_name`` is specified, it
        takes precedence over both the ``file_name`` and ``source``. When it is
        not specified, ``file_name`` takes precedence over ``source``. This
        allows for better capability for matching hashes.
    .. versionchanged:: 2016.11.0
        File name and source URI matches are no longer disregarded when
        ``source_hash_name`` is specified. They will be used as fallback
        matches if there is no match to the ``source_hash_name`` value.

    This routine is called from the :mod:`file.managed
    <salt.states.file.managed>` state to pull a hash from a remote file.
    Regular expressions are used line by line on the ``source_hash`` file, to
    find a potential candidate of the indicated hash type. This avoids many
    problems of arbitrary file layout rules. It specifically permits pulling
    hash codes from debian ``*.dsc`` files.

    If no exact match of a hash and filename are found, then the first hash
    found (if any) will be returned. If no hashes at all are found, then
    ``None`` will be returned.

    For example:

    .. code-block:: yaml

        openerp_7.0-latest-1.tar.gz:
          file.managed:
            - name: /tmp/openerp_7.0-20121227-075624-1_all.deb
            - source: http://nightly.openerp.com/7.0/nightly/deb/openerp_7.0-20121227-075624-1.tar.gz
            - source_hash: http://nightly.openerp.com/7.0/nightly/deb/openerp_7.0-20121227-075624-1.dsc

    CLI Example:

    .. code-block:: bash

        salt '*' file.extract_hash /path/to/hash/file sha512 /etc/foo
    '''
    hash_len = HASHES.get(hash_type)
    if hash_len is None:
        if hash_type:
            log.warning(
                'file.extract_hash: Unsupported hash_type \'%s\', falling '
                'back to matching any supported hash_type', hash_type
            )
            hash_type = ''
        hash_len_expr = '{0},{1}'.format(min(HASHES_REVMAP), max(HASHES_REVMAP))
    else:
        hash_len_expr = str(hash_len)

    filename_separators = string.whitespace + r'\/'

    if source_hash_name:
        if not isinstance(source_hash_name, six.string_types):
            source_hash_name = str(source_hash_name)
        source_hash_name_idx = (len(source_hash_name) + 1) * -1
        log.debug(
            'file.extract_hash: Extracting %s hash for file matching '
            'source_hash_name \'%s\'',
            'any supported' if not hash_type else hash_type,
            source_hash_name
        )
    if file_name:
        if not isinstance(file_name, six.string_types):
            file_name = str(file_name)
        file_name_basename = os.path.basename(file_name)
        file_name_idx = (len(file_name_basename) + 1) * -1
    if source:
        if not isinstance(source, six.string_types):
            source = str(source)
        urlparsed_source = _urlparse(source)
        source_basename = os.path.basename(
            urlparsed_source.path or urlparsed_source.netloc
        )
        source_idx = (len(source_basename) + 1) * -1

    basename_searches = [x for x in (file_name, source) if x]
    if basename_searches:
        log.debug(
            'file.extract_hash: %s %s hash for file matching%s: %s',
            'If no source_hash_name match found, will extract'
                if source_hash_name
                else 'Extracting',
            'any supported' if not hash_type else hash_type,
            '' if len(basename_searches) == 1 else ' either of the following',
            ', '.join(basename_searches)
        )

    partial = None
    found = {}

    with salt.utils.fopen(hash_fn, 'r') as fp_:
        for line in fp_:
            line = line.strip()
            hash_re = r'(?i)(?<![a-z0-9])([a-f0-9]{' + hash_len_expr + '})(?![a-z0-9])'
            hash_match = re.search(hash_re, line)
            matched = None
            if hash_match:
                matched_hsum = hash_match.group(1)
                if matched_hsum is not None:
                    matched_type = HASHES_REVMAP.get(len(matched_hsum))
                    if matched_type is None:
                        # There was a match, but it's not of the correct length
                        # to match one of the supported hash types.
                        matched = None
                    else:
                        matched = {'hsum': matched_hsum,
                                   'hash_type': matched_type}

            if matched is None:
                log.debug(
                    'file.extract_hash: In line \'%s\', no %shash found',
                    line,
                    '' if not hash_type else hash_type + ' '
                )
                continue

            if partial is None:
                partial = matched

            def _add_to_matches(found, line, match_type, value, matched):
                log.debug(
                    'file.extract_hash: Line \'%s\' matches %s \'%s\'',
                    line, match_type, value
                )
                found.setdefault(match_type, []).append(matched)

            hash_matched = False
            if source_hash_name:
                if line.endswith(source_hash_name):
                    # Checking the character before where the basename
                    # should start for either whitespace or a path
                    # separator. We can't just rsplit on spaces/whitespace,
                    # because the filename may contain spaces.
                    try:
                        if line[source_hash_name_idx] in string.whitespace:
                            _add_to_matches(found, line, 'source_hash_name',
                                            source_hash_name, matched)
                            hash_matched = True
                    except IndexError:
                        pass
                elif re.match(source_hash_name.replace('.', r'\.') + r'\s+',
                              line):
                    _add_to_matches(found, line, 'source_hash_name',
                                    source_hash_name, matched)
                    hash_matched = True
            if file_name:
                if line.endswith(file_name_basename):
                    # Checking the character before where the basename
                    # should start for either whitespace or a path
                    # separator. We can't just rsplit on spaces/whitespace,
                    # because the filename may contain spaces.
                    try:
                        if line[file_name_idx] in filename_separators:
                            _add_to_matches(found, line, 'file_name',
                                            file_name, matched)
                            hash_matched = True
                    except IndexError:
                        pass
                elif re.match(file_name.replace('.', r'\.') + r'\s+', line):
                    _add_to_matches(found, line, 'file_name',
                                    file_name, matched)
                    hash_matched = True
            if source:
                if line.endswith(source_basename):
                    # Same as above, we can't just do an rsplit here.
                    try:
                        if line[source_idx] in filename_separators:
                            _add_to_matches(found, line, 'source',
                                            source, matched)
                            hash_matched = True
                    except IndexError:
                        pass
                elif re.match(source.replace('.', r'\.') + r'\s+', line):
                    _add_to_matches(found, line, 'source', source, matched)
                    hash_matched = True

            if not hash_matched:
                log.debug(
                    'file.extract_hash: Line \'%s\' contains %s hash '
                    '\'%s\', but line did not meet the search criteria',
                    line, matched['hash_type'], matched['hsum']
                )

    for found_type, found_str in (('source_hash_name', source_hash_name),
                                  ('file_name', file_name),
                                  ('source', source)):
        if found_type in found:
            if len(found[found_type]) > 1:
                log.debug(
                    'file.extract_hash: Multiple %s matches for %s: %s',
                    found_type,
                    found_str,
                    ', '.join(
                        ['{0} ({1})'.format(x['hsum'], x['hash_type'])
                         for x in found[found_type]]
                    )
                )
            ret = found[found_type][0]
            log.debug(
                'file.extract_hash: Returning %s hash \'%s\' as a match of %s',
                ret['hash_type'], ret['hsum'], found_str
            )
            return ret

    if partial:
        log.debug(
            'file.extract_hash: Returning the partially identified %s hash '
            '\'%s\'', partial['hash_type'], partial['hsum']
        )
        return partial

    log.debug('file.extract_hash: No matches, returning None')
    return None


def check_perms(name, ret, user, group, mode, follow_symlinks=False):
    '''
    Check the permissions on files and chown if needed

    CLI Example:

    .. code-block:: bash

        salt '*' file.check_perms /etc/sudoers '{}' root root 400

    .. versionchanged:: 2014.1.3
        ``follow_symlinks`` option added
    '''
    name = os.path.expanduser(name)

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
    cur = stats(name, follow_symlinks=follow_symlinks)
    if not cur:
        # NOTE: The file.directory state checks the content of the error
        # message in this exception. Any changes made to the message for this
        # exception will reflect the file.directory state as well, and will
        # likely require changes there.
        raise CommandExecutionError('{0} does not exist'.format(name))
    perms['luser'] = cur['user']
    perms['lgroup'] = cur['group']
    perms['lmode'] = salt.utils.normalize_mode(cur['mode'])

    # Mode changes if needed
    if mode is not None:
        # File is a symlink, ignore the mode setting
        # if follow_symlinks is False
        if os.path.islink(name) and not follow_symlinks:
            pass
        else:
            mode = salt.utils.normalize_mode(mode)
            if mode != perms['lmode']:
                if __opts__['test'] is True:
                    ret['changes']['mode'] = mode
                else:
                    set_mode(name, mode)
                    if mode != salt.utils.normalize_mode(get_mode(name)):
                        ret['result'] = False
                        ret['comment'].append(
                            'Failed to change mode to {0}'.format(mode)
                        )
                    else:
                        ret['changes']['mode'] = mode
    # user/group changes if needed, then check if it worked
    if user:
        if isinstance(user, int):
            user = uid_to_user(user)
        if (salt.utils.is_windows() and
                user_to_uid(user) != user_to_uid(perms['luser'])
            ) or (
            not salt.utils.is_windows() and user != perms['luser']
        ):
            perms['cuser'] = user

    if group:
        if isinstance(group, int):
            group = gid_to_group(group)
        if (salt.utils.is_windows() and
                group_to_gid(group) != group_to_gid(perms['lgroup'])
            ) or (
                not salt.utils.is_windows() and group != perms['lgroup']
        ):
            perms['cgroup'] = group

    if 'cuser' in perms or 'cgroup' in perms:
        if not __opts__['test']:
            if os.path.islink(name) and not follow_symlinks:
                chown_func = lchown
            else:
                chown_func = chown
            if user is None:
                user = perms['luser']
            if group is None:
                group = perms['lgroup']
            try:
                chown_func(name, user, group)
            except OSError:
                ret['result'] = False

    if user:
        if isinstance(user, int):
            user = uid_to_user(user)
        if (salt.utils.is_windows() and
                user_to_uid(user) != user_to_uid(
                    get_user(name, follow_symlinks=follow_symlinks)) and
                user != ''
            ) or (
            not salt.utils.is_windows() and
                user != get_user(name, follow_symlinks=follow_symlinks) and
                user != ''
        ):
            if __opts__['test'] is True:
                ret['changes']['user'] = user
            else:
                ret['result'] = False
                ret['comment'].append('Failed to change user to {0}'
                                          .format(user))
        elif 'cuser' in perms and user != '':
            ret['changes']['user'] = user
    if group:
        if isinstance(group, int):
            group = gid_to_group(group)
        if (salt.utils.is_windows() and
                group_to_gid(group) != group_to_gid(
                    get_group(name, follow_symlinks=follow_symlinks)) and
                user != '') or (
            not salt.utils.is_windows() and
                group != get_group(name, follow_symlinks=follow_symlinks) and
                user != ''
        ):
            if __opts__['test'] is True:
                ret['changes']['group'] = group
            else:
                ret['result'] = False
                ret['comment'].append('Failed to change group to {0}'
                                      .format(group))
        elif 'cgroup' in perms and user != '':
            ret['changes']['group'] = group

    if isinstance(orig_comment, six.string_types):
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
        source_hash_name,
        user,
        group,
        mode,
        template,
        context,
        defaults,
        saltenv,
        contents=None,
        skip_verify=False,
        **kwargs):
    '''
    Check to see what changes need to be made for a file

    CLI Example:

    .. code-block:: bash

        salt '*' file.check_managed /etc/httpd/conf.d/httpd.conf salt://http/httpd.conf '{hash_type: 'md5', 'hsum': <md5sum>}' root, root, '755' jinja True None None base
    '''
    # If the source is a list then find which file exists
    source, source_hash = source_list(source,           # pylint: disable=W0633
                                      source_hash,
                                      saltenv)

    sfn = ''
    source_sum = None

    if contents is None:
        # Gather the source file from the server
        sfn, source_sum, comments = get_managed(
            name,
            template,
            source,
            source_hash,
            source_hash_name,
            user,
            group,
            mode,
            saltenv,
            context,
            defaults,
            skip_verify,
            **kwargs)
        if comments:
            __clean_tmp(sfn)
            return False, comments
    changes = check_file_meta(name, sfn, source, source_sum, user,
                              group, mode, saltenv, contents)
    # Ignore permission for files written temporary directories
    # Files in any path will still be set correctly using get_managed()
    if name.startswith(tempfile.gettempdir()):
        for key in ['user', 'group', 'mode']:
            changes.pop(key, None)
    __clean_tmp(sfn)
    if changes:
        log.info(changes)
        comments = ['The following values are set to be changed:\n']
        comments.extend('{0}: {1}\n'.format(key, val)
                        for key, val in six.iteritems(changes))
        return None, ''.join(comments)
    return True, 'The file {0} is in the correct state'.format(name)


def check_managed_changes(
        name,
        source,
        source_hash,
        source_hash_name,
        user,
        group,
        mode,
        template,
        context,
        defaults,
        saltenv,
        contents=None,
        skip_verify=False,
        keep_mode=False,
        **kwargs):
    '''
    Return a dictionary of what changes need to be made for a file

    CLI Example:

    .. code-block:: bash

        salt '*' file.check_managed_changes /etc/httpd/conf.d/httpd.conf salt://http/httpd.conf '{hash_type: 'md5', 'hsum': <md5sum>}' root, root, '755' jinja True None None base
    '''
    # If the source is a list then find which file exists
    source, source_hash = source_list(source,           # pylint: disable=W0633
                                      source_hash,
                                      saltenv)

    sfn = ''
    source_sum = None

    if contents is None:
        # Gather the source file from the server
        sfn, source_sum, comments = get_managed(
            name,
            template,
            source,
            source_hash,
            source_hash_name,
            user,
            group,
            mode,
            saltenv,
            context,
            defaults,
            skip_verify,
            **kwargs)
        if comments:
            __clean_tmp(sfn)
            return False, comments
        if sfn and source and keep_mode:
            if _urlparse(source).scheme in ('salt', 'file') \
                    or source.startswith('/'):
                try:
                    mode = salt.utils.st_mode_to_octal(os.stat(sfn).st_mode)
                except Exception as exc:
                    log.warning('Unable to stat %s: %s', sfn, exc)
    changes = check_file_meta(name, sfn, source, source_sum, user,
                              group, mode, saltenv, contents)
    __clean_tmp(sfn)
    return changes


def check_file_meta(
        name,
        sfn,
        source,
        source_sum,
        user,
        group,
        mode,
        saltenv,
        contents=None):
    '''
    Check for the changes in the file metadata.

    CLI Example:

    .. code-block:: bash

        salt '*' file.check_file_meta /etc/httpd/conf.d/httpd.conf salt://http/httpd.conf '{hash_type: 'md5', 'hsum': <md5sum>}' root, root, '755' base

    .. note::

        Supported hash types include sha512, sha384, sha256, sha224, sha1, and
        md5.

    name
        Path to file destination

    sfn
        Template-processed source file contents

    source
        URL to file source

    source_sum
        File checksum information as a dictionary

        .. code-block:: yaml

            {hash_type: md5, hsum: <md5sum>}

    user
        Destination file user owner

    group
        Destination file group owner

    mode
        Destination file permissions mode

    saltenv
        Salt environment used to resolve source files

    contents
        File contents
    '''
    changes = {}
    if not source_sum:
        source_sum = dict()
    lstats = stats(name, hash_type=source_sum.get('hash_type', None), follow_symlinks=False)
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
                        with salt.utils.fopen(sfn, 'r') as src:
                            slines = src.readlines()
                        with salt.utils.fopen(name, 'r') as name_:
                            nlines = name_.readlines()
                        changes['diff'] = \
                            ''.join(difflib.unified_diff(nlines, slines))
            else:
                changes['sum'] = 'Checksum differs'

    if contents is not None:
        # Write a tempfile with the static contents
        tmp = salt.utils.mkstemp(prefix=salt.utils.files.TEMPFILE_PREFIX,
                                 text=True)
        if salt.utils.is_windows():
            contents = os.linesep.join(
                _splitlines_preserving_trailing_newline(contents))
        with salt.utils.fopen(tmp, 'w') as tmp_:
            tmp_.write(str(contents))
        # Compare the static contents with the named file
        with salt.utils.fopen(tmp, 'r') as src:
            slines = src.readlines()
        with salt.utils.fopen(name, 'r') as name_:
            nlines = name_.readlines()
        __clean_tmp(tmp)
        if ''.join(nlines) != ''.join(slines):
            if __salt__['config.option']('obfuscate_templates'):
                changes['diff'] = '<Obfuscated Template>'
            else:
                if salt.utils.istextfile(name):
                    changes['diff'] = \
                        ''.join(difflib.unified_diff(nlines, slines))
                else:
                    changes['diff'] = 'Replace binary file with text file'

    if (user is not None
            and user != lstats['user']
            and user != lstats['uid']):
        changes['user'] = user
    if (group is not None
            and group != lstats['group']
            and group != lstats['gid']):
        changes['group'] = group
    # Normalize the file mode
    smode = salt.utils.normalize_mode(lstats['mode'])
    mode = salt.utils.normalize_mode(mode)
    if mode is not None and mode != smode:
        changes['mode'] = mode
    return changes


def get_diff(
        minionfile,
        masterfile,
        saltenv='base'):
    '''
    Return unified diff of file compared to file on master

    CLI Example:

    .. code-block:: bash

        salt '*' file.get_diff /home/fred/.vimrc salt://users/fred/.vimrc
    '''
    minionfile = os.path.expanduser(minionfile)

    ret = ''

    if not os.path.exists(minionfile):
        ret = 'File {0} does not exist on the minion'.format(minionfile)
        return ret

    sfn = __salt__['cp.cache_file'](masterfile, saltenv)
    if sfn:
        with salt.utils.fopen(sfn, 'r') as src:
            slines = src.readlines()
        with salt.utils.fopen(minionfile, 'r') as name_:
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
                makedirs=False,
                template=None,   # pylint: disable=W0613
                show_changes=True,
                contents=None,
                dir_mode=None,
                follow_symlinks=True,
                skip_verify=False,
                keep_mode=False,
                **kwargs):
    '''
    Checks the destination against what was retrieved with get_managed and
    makes the appropriate modifications (if necessary).

    name
        location to place the file

    sfn
        location of cached file on the minion

        This is the path to the file stored on the minion. This file is placed
        on the minion using cp.cache_file.  If the hash sum of that file
        matches the source_sum, we do not transfer the file to the minion
        again.

        This file is then grabbed and if it has template set, it renders the
        file to be placed into the correct place on the system using
        salt.files.utils.copyfile()

    ret
        The initial state return data structure. Pass in ``None`` to use the
        default structure.

    source
        file reference on the master

    source_hash
        sum hash for source

    user
        user owner

    group
        group owner

    backup
        backup_mode

    makedirs
        make directories if they do not exist

    template
        format of templating

    show_changes
        Include diff in state return

    contents:
        contents to be placed in the file

    dir_mode
        mode for directories created with makedirs

    skip_verify : False
        If ``True``, hash verification of remote file sources (``http://``,
        ``https://``, ``ftp://``) will be skipped, and the ``source_hash``
        argument will be ignored.

        .. versionadded:: 2016.3.0

    keep_mode : False
        If ``True``, and the ``source`` is a file from the Salt fileserver (or
        a local file on the minion), the mode of the destination file will be
        set to the mode of the source file.

    CLI Example:

    .. code-block:: bash

        salt '*' file.manage_file /etc/httpd/conf.d/httpd.conf '' '{}' salt://http/httpd.conf '{hash_type: 'md5', 'hsum': <md5sum>}' root root '755' base ''

    .. versionchanged:: 2014.7.0
        ``follow_symlinks`` option added

    '''
    name = os.path.expanduser(name)

    if not ret:
        ret = {'name': name,
               'changes': {},
               'comment': '',
               'result': True}

    if source and not sfn:
        # File is not present, cache it
        sfn = __salt__['cp.cache_file'](source, saltenv)
        if not sfn:
            return _error(
                ret, 'Source file \'{0}\' not found'.format(source))
        htype = source_sum.get('hash_type', __opts__.get('hash_type', 'md5'))
        # Recalculate source sum now that file has been cached
        source_sum = {
            'hash_type': htype,
            'hsum': get_hash(sfn, form=htype)
        }
        if keep_mode:
            if _urlparse(source).scheme in ('salt', 'file') \
                    or source.startswith('/'):
                try:
                    mode = salt.utils.st_mode_to_octal(os.stat(sfn).st_mode)
                except Exception as exc:
                    log.warning('Unable to stat %s: %s', sfn, exc)

    # Check changes if the target file exists
    if os.path.isfile(name) or os.path.islink(name):
        if os.path.islink(name) and follow_symlinks:
            real_name = os.path.realpath(name)
        else:
            real_name = name

        # Only test the checksums on files with managed contents
        if source and not (not follow_symlinks and os.path.islink(real_name)):
            name_sum = get_hash(real_name, source_sum.get('hash_type', __opts__.get('hash_type', 'md5')))
        else:
            name_sum = None

        # Check if file needs to be replaced
        if source and (name_sum is None or source_sum.get('hsum', __opts__.get('hash_type', 'md5')) != name_sum):
            if not sfn:
                sfn = __salt__['cp.cache_file'](source, saltenv)
            if not sfn:
                return _error(
                    ret, 'Source file \'{0}\' not found'.format(source))
            # If the downloaded file came from a non salt server or local
            # source, and we are not skipping checksum verification, then
            # verify that it matches the specified checksum.
            if not skip_verify \
                    and _urlparse(source).scheme not in ('salt', ''):
                dl_sum = get_hash(sfn, source_sum['hash_type'])
                if dl_sum != source_sum['hsum']:
                    ret['comment'] = (
                        'Specified {0} checksum for {1} ({2}) does not match '
                        'actual checksum ({3}). If the \'source_hash\' value '
                        'refers to a remote file with multiple possible '
                        'matches, then it may be necessary to set '
                        '\'source_hash_name\'.'.format(
                            source_sum['hash_type'],
                            source,
                            source_sum['hsum'],
                            dl_sum
                        )
                    )
                    ret['result'] = False
                    return ret

            # Print a diff equivalent to diff -u old new
            if __salt__['config.option']('obfuscate_templates'):
                ret['changes']['diff'] = '<Obfuscated Template>'
            elif not show_changes:
                ret['changes']['diff'] = '<show_changes=False>'
            else:
                # Check to see if the files are bins
                bdiff = _binary_replace(real_name, sfn)
                if bdiff:
                    ret['changes']['diff'] = bdiff
                else:
                    with salt.utils.fopen(sfn, 'r') as src:
                        slines = src.readlines()
                    with salt.utils.fopen(real_name, 'r') as name_:
                        nlines = name_.readlines()

                    sndiff = ''.join(difflib.unified_diff(nlines, slines))
                    if sndiff:
                        ret['changes']['diff'] = sndiff

            # Pre requisites are met, and the file needs to be replaced, do it
            try:
                salt.utils.files.copyfile(sfn,
                                    real_name,
                                    __salt__['config.backup_mode'](backup),
                                    __opts__['cachedir'])
            except IOError as io_error:
                __clean_tmp(sfn)
                return _error(
                    ret, 'Failed to commit change: {0}'.format(io_error))

        if contents is not None:
            # Write the static contents to a temporary file
            tmp = salt.utils.mkstemp(prefix=salt.utils.files.TEMPFILE_PREFIX,
                                     text=True)
            if salt.utils.is_windows():
                contents = os.linesep.join(
                    _splitlines_preserving_trailing_newline(contents))
            with salt.utils.fopen(tmp, 'w') as tmp_:
                tmp_.write(str(contents))

            # Compare contents of files to know if we need to replace
            with salt.utils.fopen(tmp, 'r') as src:
                slines = src.readlines()
            with salt.utils.fopen(real_name, 'r') as name_:
                nlines = name_.readlines()
                different = ''.join(slines) != ''.join(nlines)

            if different:
                if __salt__['config.option']('obfuscate_templates'):
                    ret['changes']['diff'] = '<Obfuscated Template>'
                elif not show_changes:
                    ret['changes']['diff'] = '<show_changes=False>'
                else:
                    if salt.utils.istextfile(real_name):
                        ret['changes']['diff'] = \
                            ''.join(difflib.unified_diff(nlines, slines))
                    else:
                        ret['changes']['diff'] = \
                            'Replace binary file with text file'

                # Pre requisites are met, the file needs to be replaced, do it
                try:
                    salt.utils.files.copyfile(tmp,
                                        real_name,
                                        __salt__['config.backup_mode'](backup),
                                        __opts__['cachedir'])
                except IOError as io_error:
                    __clean_tmp(tmp)
                    return _error(
                        ret, 'Failed to commit change: {0}'.format(io_error))
            __clean_tmp(tmp)

        # Check for changing symlink to regular file here
        if os.path.islink(name) and not follow_symlinks:
            if not sfn:
                sfn = __salt__['cp.cache_file'](source, saltenv)
            if not sfn:
                return _error(
                    ret, 'Source file \'{0}\' not found'.format(source))
            # If the downloaded file came from a non salt server source verify
            # that it matches the intended sum value
            if not skip_verify and _urlparse(source).scheme != 'salt':
                dl_sum = get_hash(sfn, source_sum['hash_type'])
                if dl_sum != source_sum['hsum']:
                    ret['comment'] = (
                        'Specified {0} checksum for {1} ({2}) does not match '
                        'actual checksum ({3})'.format(
                            source_sum['hash_type'],
                            name,
                            source_sum['hsum'],
                            dl_sum
                        )
                    )
                    ret['result'] = False
                    return ret

            try:
                salt.utils.files.copyfile(sfn,
                                    name,
                                    __salt__['config.backup_mode'](backup),
                                    __opts__['cachedir'])
            except IOError as io_error:
                __clean_tmp(sfn)
                return _error(
                    ret, 'Failed to commit change: {0}'.format(io_error))

            ret['changes']['diff'] = \
                'Replace symbolic link with regular file'

        ret, _ = check_perms(name, ret, user, group, mode, follow_symlinks)

        if ret['changes']:
            ret['comment'] = 'File {0} updated'.format(name)

        elif not ret['changes'] and ret['result']:
            ret['comment'] = u'File {0} is in the correct state'.format(
                salt.utils.locales.sdecode(name)
            )
        if sfn:
            __clean_tmp(sfn)
        return ret
    else:  # target file does not exist
        contain_dir = os.path.dirname(name)

        def _set_mode_and_make_dirs(name, dir_mode, mode, user, group):
            # check for existence of windows drive letter
            if salt.utils.is_windows():
                drive, _ = os.path.splitdrive(name)
                if drive and not os.path.exists(drive):
                    __clean_tmp(sfn)
                    return _error(ret,
                                  '{0} drive not present'.format(drive))
            if dir_mode is None and mode is not None:
                # Add execute bit to each nonzero digit in the mode, if
                # dir_mode was not specified. Otherwise, any
                # directories created with makedirs_() below can't be
                # listed via a shell.
                mode_list = [x for x in str(mode)][-3:]
                for idx in range(len(mode_list)):
                    if mode_list[idx] != '0':
                        mode_list[idx] = str(int(mode_list[idx]) | 1)
                dir_mode = ''.join(mode_list)
            makedirs_(name, user=user,
                      group=group, mode=dir_mode)

        if source:
            # It is a new file, set the diff accordingly
            ret['changes']['diff'] = 'New file'
            # Apply the new file
            if not sfn:
                sfn = __salt__['cp.cache_file'](source, saltenv)
            if not sfn:
                return _error(
                    ret, 'Source file \'{0}\' not found'.format(source))
            # If the downloaded file came from a non salt server source verify
            # that it matches the intended sum value
            if not skip_verify \
                    and _urlparse(source).scheme != 'salt':
                dl_sum = get_hash(sfn, source_sum['hash_type'])
                if dl_sum != source_sum['hsum']:
                    ret['comment'] = (
                        'Specified {0} checksum for {1} ({2}) does not match '
                        'actual checksum ({3})'.format(
                            source_sum['hash_type'],
                            name,
                            source_sum['hsum'],
                            dl_sum
                        )
                    )
                    ret['result'] = False
                    return ret
            if not os.path.isdir(contain_dir):
                if makedirs:
                    _set_mode_and_make_dirs(name, dir_mode, mode, user, group)
                else:
                    __clean_tmp(sfn)
                    # No changes actually made
                    ret['changes'].pop('diff', None)
                    return _error(ret, 'Parent directory not present')
        else:  # source != True
            if not os.path.isdir(contain_dir):
                if makedirs:
                    _set_mode_and_make_dirs(name, dir_mode, mode, user, group)
                else:
                    __clean_tmp(sfn)
                    # No changes actually made
                    ret['changes'].pop('diff', None)
                    return _error(ret, 'Parent directory not present')

            # Create the file, user rw-only if mode will be set to prevent
            # a small security race problem before the permissions are set
            if mode:
                current_umask = os.umask(0o77)

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
            tmp = salt.utils.mkstemp(prefix=salt.utils.files.TEMPFILE_PREFIX,
                                     text=True)
            if salt.utils.is_windows():
                contents = os.linesep.join(
                    _splitlines_preserving_trailing_newline(contents))
            with salt.utils.fopen(tmp, 'w') as tmp_:
                tmp_.write(str(contents))
            # Copy into place
            salt.utils.files.copyfile(tmp,
                                name,
                                __salt__['config.backup_mode'](backup),
                                __opts__['cachedir'])
            __clean_tmp(tmp)
        # Now copy the file contents if there is a source file
        elif sfn:
            salt.utils.files.copyfile(sfn,
                                name,
                                __salt__['config.backup_mode'](backup),
                                __opts__['cachedir'])
            __clean_tmp(sfn)

        # This is a new file, if no mode specified, use the umask to figure
        # out what mode to use for the new file.
        if mode is None and not salt.utils.is_windows():
            # Get current umask
            mask = os.umask(0)
            os.umask(mask)
            # Calculate the mode value that results from the umask
            mode = oct((0o777 ^ mask) & 0o666)
        ret, _ = check_perms(name, ret, user, group, mode)

        if not ret['comment']:
            ret['comment'] = 'File ' + name + ' updated'

        if __opts__['test']:
            ret['comment'] = 'File ' + name + ' not updated'
        elif not ret['changes'] and ret['result']:
            ret['comment'] = 'File ' + name + ' is in the correct state'
        if sfn:
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
    dir_path = os.path.expanduser(dir_path)

    directory = os.path.normpath(dir_path)

    if not os.path.isdir(directory):
        # If a caller such as managed() is invoked  with makedirs=True, make
        # sure that any created dirs are created with the same user and group
        # to follow the principal of least surprise method.
        makedirs_perms(directory, user, group, mode)

    return True


def makedirs_(path,
              user=None,
              group=None,
              mode=None):
    '''
    Ensure that the directory containing this path is available.

    .. note::

        The path must end with a trailing slash otherwise the directory/directories
        will be created up to the parent directory. For example if path is
        ``/opt/code``, then it would be treated as ``/opt/`` but if the path
        ends with a trailing slash like ``/opt/code/``, then it would be
        treated as ``/opt/code/``.

    CLI Example:

    .. code-block:: bash

        salt '*' file.makedirs /opt/code/
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
    name = os.path.expanduser(name)

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
    name = os.path.expanduser(name)

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
    name = os.path.expanduser(name)

    stat_structure = None
    try:
        stat_structure = os.stat(name)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            # If the character device does not exist in the first place
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
    .. versionadded:: 0.17.0

    Create a character device.

    CLI Example:

    .. code-block:: bash

       salt '*' file.mknod_chrdev /dev/chr 180 31
    '''
    name = os.path.expanduser(name)

    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': False}
    log.debug('Creating character device name:{0} major:{1} minor:{2} mode:{3}'
              .format(name, major, minor, mode))
    try:
        if __opts__['test']:
            ret['changes'] = {'new': 'Character device {0} created.'.format(name)}
            ret['result'] = None
        else:
            if os.mknod(name,
                        int(str(mode).lstrip('0Oo'), 8) | stat.S_IFCHR,
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
    # quick pass at verifying the permissions of the newly created character device
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
    name = os.path.expanduser(name)

    stat_structure = None
    try:
        stat_structure = os.stat(name)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            # If the block device does not exist in the first place
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
    .. versionadded:: 0.17.0

    Create a block device.

    CLI Example:

    .. code-block:: bash

       salt '*' file.mknod_blkdev /dev/blk 8 999
    '''
    name = os.path.expanduser(name)

    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': False}
    log.debug('Creating block device name:{0} major:{1} minor:{2} mode:{3}'
              .format(name, major, minor, mode))
    try:
        if __opts__['test']:
            ret['changes'] = {'new': 'Block device {0} created.'.format(name)}
            ret['result'] = None
        else:
            if os.mknod(name,
                        int(str(mode).lstrip('0Oo'), 8) | stat.S_IFBLK,
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
    # quick pass at verifying the permissions of the newly created block device
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
    name = os.path.expanduser(name)

    stat_structure = None
    try:
        stat_structure = os.stat(name)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            # If the fifo does not exist in the first place
            return False
        else:
            raise
    return stat.S_ISFIFO(stat_structure.st_mode)


def mknod_fifo(name,
               user=None,
               group=None,
               mode='0660'):
    '''
    .. versionadded:: 0.17.0

    Create a FIFO pipe.

    CLI Example:

    .. code-block:: bash

       salt '*' file.mknod_fifo /dev/fifo
    '''
    name = os.path.expanduser(name)

    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': False}
    log.debug('Creating FIFO name: {0}'.format(name))
    try:
        if __opts__['test']:
            ret['changes'] = {'new': 'Fifo pipe {0} created.'.format(name)}
            ret['result'] = None
        else:
            if os.mkfifo(name, int(str(mode).lstrip('0Oo'), 8)) is None:
                ret['changes'] = {'new': 'Fifo pipe {0} created.'.format(name)}
                ret['result'] = True
    except OSError as exc:
        # be happy it is already there
        if exc.errno != errno.EEXIST:
            raise
        else:
            ret['comment'] = 'File {0} exists and cannot be overwritten'.format(name)
    # quick pass at verifying the permissions of the newly created fifo
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
    .. versionadded:: 0.17.0

    Create a block device, character device, or fifo pipe.
    Identical to the gnu mknod.

    CLI Examples:

    .. code-block:: bash

        salt '*' file.mknod /dev/chr c 180 31
        salt '*' file.mknod /dev/blk b 8 999
        salt '*' file.nknod /dev/fifo p
    '''
    ret = False
    makedirs_(name, user, group)
    if ntype == 'c':
        ret = mknod_chrdev(name, major, minor, user, group, mode)
    elif ntype == 'b':
        ret = mknod_blkdev(name, major, minor, user, group, mode)
    elif ntype == 'p':
        ret = mknod_fifo(name, user, group, mode)
    else:
        raise SaltInvocationError(
            'Node type unavailable: \'{0}\'. Available node types are '
            'character (\'c\'), block (\'b\'), and pipe (\'p\').'.format(ntype)
        )
    return ret


def list_backups(path, limit=None):
    '''
    .. versionadded:: 0.17.0

    Lists the previous versions of a file backed up using Salt's :ref:`file
    state backup <file-state-backups>` system.

    path
        The path on the minion to check for backups
    limit
        Limit the number of results to the most recent N backups

    CLI Example:

    .. code-block:: bash

        salt '*' file.list_backups /foo/bar/baz.txt
    '''
    path = os.path.expanduser(path)

    try:
        limit = int(limit)
    except TypeError:
        pass
    except ValueError:
        log.error('file.list_backups: \'limit\' value must be numeric')
        limit = None

    bkroot = _get_bkroot()
    parent_dir, basename = os.path.split(path)
    if salt.utils.is_windows():
        # ':' is an illegal filesystem path character on Windows
        src_dir = parent_dir.replace(':', '_')
    else:
        src_dir = parent_dir[1:]
    # Figure out full path of location of backup file in minion cache
    bkdir = os.path.join(bkroot, src_dir)

    if not os.path.isdir(bkdir):
        return {}

    files = {}
    for fname in [x for x in os.listdir(bkdir)
                  if os.path.isfile(os.path.join(bkdir, x))]:
        if salt.utils.is_windows():
            # ':' is an illegal filesystem path character on Windows
            strpfmt = '{0}_%a_%b_%d_%H-%M-%S_%f_%Y'.format(basename)
        else:
            strpfmt = '{0}_%a_%b_%d_%H:%M:%S_%f_%Y'.format(basename)
        try:
            timestamp = datetime.datetime.strptime(fname, strpfmt)
        except ValueError:
            # File didn't match the strp format string, so it's not a backup
            # for this file. Move on to the next one.
            continue
        if salt.utils.is_windows():
            str_format = '%a %b %d %Y %H-%M-%S.%f'
        else:
            str_format = '%a %b %d %Y %H:%M:%S.%f'
        files.setdefault(timestamp, {})['Backup Time'] = \
            timestamp.strftime(str_format)
        location = os.path.join(bkdir, fname)
        files[timestamp]['Size'] = os.stat(location).st_size
        files[timestamp]['Location'] = location

    return dict(list(zip(
        list(range(len(files))),
        [files[x] for x in sorted(files, reverse=True)[:limit]]
    )))

list_backup = salt.utils.alias_function(list_backups, 'list_backup')


def list_backups_dir(path, limit=None):
    '''
    Lists the previous versions of a directory backed up using Salt's :ref:`file
    state backup <file-state-backups>` system.

    path
        The directory on the minion to check for backups
    limit
        Limit the number of results to the most recent N backups

    CLI Example:

    .. code-block:: bash

        salt '*' file.list_backups_dir /foo/bar/baz/
    '''
    path = os.path.expanduser(path)

    try:
        limit = int(limit)
    except TypeError:
        pass
    except ValueError:
        log.error('file.list_backups_dir: \'limit\' value must be numeric')
        limit = None

    bkroot = _get_bkroot()
    parent_dir, basename = os.path.split(path)
    # Figure out full path of location of backup folder in minion cache
    bkdir = os.path.join(bkroot, parent_dir[1:])

    if not os.path.isdir(bkdir):
        return {}

    files = {}
    f = dict([(i, len(list(n))) for i, n in itertools.groupby([x.split("_")[0] for x in sorted(os.listdir(bkdir))])])
    ff = os.listdir(bkdir)
    for i, n in six.iteritems(f):
        ssfile = {}
        for x in sorted(ff):
            basename = x.split('_')[0]
            if i == basename:
                strpfmt = '{0}_%a_%b_%d_%H:%M:%S_%f_%Y'.format(basename)
                try:
                    timestamp = datetime.datetime.strptime(x, strpfmt)
                except ValueError:
                    # Folder didn't match the strp format string, so it's not a backup
                    # for this folder. Move on to the next one.
                    continue
                ssfile.setdefault(timestamp, {})['Backup Time'] = \
                    timestamp.strftime('%a %b %d %Y %H:%M:%S.%f')
                location = os.path.join(bkdir, x)
                ssfile[timestamp]['Size'] = os.stat(location).st_size
                ssfile[timestamp]['Location'] = location

        sfiles = dict(list(zip(list(range(n)), [ssfile[x] for x in sorted(ssfile, reverse=True)[:limit]])))
        sefiles = {i: sfiles}
        files.update(sefiles)
    return files


def restore_backup(path, backup_id):
    '''
    .. versionadded:: 0.17.0

    Restore a previous version of a file that was backed up using Salt's
    :ref:`file state backup <file-state-backups>` system.

    path
        The path on the minion to check for backups
    backup_id
        The numeric id for the backup you wish to restore, as found using
        :mod:`file.list_backups <salt.modules.file.list_backups>`

    CLI Example:

    .. code-block:: bash

        salt '*' file.restore_backup /foo/bar/baz.txt 0
    '''
    path = os.path.expanduser(path)

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
    if not salt.utils.is_windows():
        try:
            fstat = os.stat(path)
        except (OSError, IOError):
            ret['comment'] += ', but was unable to set ownership'
        else:
            os.chown(path, fstat.st_uid, fstat.st_gid)

    return ret


def delete_backup(path, backup_id):
    '''
    .. versionadded:: 0.17.0

    Delete a previous version of a file that was backed up using Salt's
    :ref:`file state backup <file-state-backups>` system.

    path
        The path on the minion to check for backups
    backup_id
        The numeric id for the backup you wish to delete, as found using
        :mod:`file.list_backups <salt.modules.file.list_backups>`

    CLI Example:

    .. code-block:: bash

        salt '*' file.delete_backup /var/cache/salt/minion/file_backup/home/foo/bar/baz.txt 0
    '''
    path = os.path.expanduser(path)

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

remove_backup = salt.utils.alias_function(delete_backup, 'remove_backup')


def grep(path,
         pattern,
         *opts):
    '''
    Grep for a string in the specified file

    .. note::
        This function's return value is slated for refinement in future
        versions of Salt

    path
        Path to the file to be searched

        .. note::
            Globbing is supported (i.e. ``/var/log/foo/*.log``, but if globbing
            is being used then the path should be quoted to keep the shell from
            attempting to expand the glob expression.

    pattern
        Pattern to match. For example: ``test``, or ``a[0-5]``

    opts
        Additional command-line flags to pass to the grep command. For example:
        ``-v``, or ``-i -B2``

        .. note::
            The options should come after a double-dash (as shown in the
            examples below) to keep Salt's own argument parser from
            interpreting them.

    CLI Example:

    .. code-block:: bash

        salt '*' file.grep /etc/passwd nobody
        salt '*' file.grep /etc/sysconfig/network-scripts/ifcfg-eth0 ipaddr -- -i
        salt '*' file.grep /etc/sysconfig/network-scripts/ifcfg-eth0 ipaddr -- -i -B2
        salt '*' file.grep "/etc/sysconfig/network-scripts/*" ipaddr -- -i -l
    '''
    path = os.path.expanduser(path)

    split_opts = []
    for opt in opts:
        try:
            split = salt.utils.shlex_split(opt)
        except AttributeError:
            split = salt.utils.shlex_split(str(opt))
        if len(split) > 1:
            raise SaltInvocationError(
                'Passing multiple command line arguments in a single string '
                'is not supported, please pass the following arguments '
                'separately: {0}'.format(opt)
            )
        split_opts.extend(split)

    cmd = ['grep'] + split_opts + [pattern, path]
    try:
        ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    except (IOError, OSError) as exc:
        raise CommandExecutionError(exc.strerror)

    return ret


def open_files(by_pid=False):
    '''
    Return a list of all physical open files on the system.

    CLI Examples:

    .. code-block:: bash

        salt '*' file.open_files
        salt '*' file.open_files by_pid=True
    '''
    # First we collect valid PIDs
    pids = {}
    procfs = os.listdir('/proc/')
    for pfile in procfs:
        try:
            pids[int(pfile)] = []
        except ValueError:
            # Not a valid PID, move on
            pass

    # Then we look at the open files for each PID
    files = {}
    for pid in pids:
        ppath = '/proc/{0}'.format(pid)
        try:
            tids = os.listdir('{0}/task'.format(ppath))
        except OSError:
            continue

        # Collect the names of all of the file descriptors
        fd_ = []

        #try:
        #    fd_.append(os.path.realpath('{0}/task/{1}exe'.format(ppath, tid)))
        #except:
        #    pass

        for fpath in os.listdir('{0}/fd'.format(ppath)):
            fd_.append('{0}/fd/{1}'.format(ppath, fpath))

        for tid in tids:
            try:
                fd_.append(
                    os.path.realpath('{0}/task/{1}/exe'.format(ppath, tid))
                )
            except OSError:
                continue

            for tpath in os.listdir('{0}/task/{1}/fd'.format(ppath, tid)):
                fd_.append('{0}/task/{1}/fd/{2}'.format(ppath, tid, tpath))

        fd_ = sorted(set(fd_))

        # Loop through file descriptors and return useful data for each file
        for fdpath in fd_:
            # Sometimes PIDs and TIDs disappear before we can query them
            try:
                name = os.path.realpath(fdpath)
                # Running stat on the file cuts out all of the sockets and
                # deleted files from the list
                os.stat(name)
            except OSError:
                continue

            if name not in files:
                files[name] = [pid]
            else:
                # We still want to know which PIDs are using each file
                files[name].append(pid)
                files[name] = sorted(set(files[name]))

            pids[pid].append(name)
            pids[pid] = sorted(set(pids[pid]))

    if by_pid:
        return pids
    return files


def pardir():
    '''
    Return the relative parent directory path symbol for underlying OS

    .. versionadded:: 2014.7.0

    This can be useful when constructing Salt Formulas.

    .. code-block:: jinja

        {% set pardir = salt['file.pardir']() %}
        {% set final_path = salt['file.join']('subdir', pardir, 'confdir') %}

    CLI Example:

    .. code-block:: bash

        salt '*' file.pardir
    '''
    return os.path.pardir


def normpath(path):
    '''
    Returns Normalize path, eliminating double slashes, etc.

    .. versionadded:: 2015.5.0

    This can be useful at the CLI but is frequently useful when scripting.

    .. code-block:: jinja

        {%- from salt['file.normpath'](tpldir + '/../vars.jinja') import parent_vars %}

    CLI Example:

    .. code-block:: bash

        salt '*' file.normpath 'a/b/c/..'
    '''
    return os.path.normpath(path)


def basename(path):
    '''
    Returns the final component of a pathname

    .. versionadded:: 2015.5.0

    This can be useful at the CLI but is frequently useful when scripting.

    .. code-block:: jinja

        {%- set filename = salt['file.basename'](source_file) %}

    CLI Example:

    .. code-block:: bash

        salt '*' file.basename 'test/test.config'
    '''
    return os.path.basename(path)


def dirname(path):
    '''
    Returns the directory component of a pathname

    .. versionadded:: 2015.5.0

    This can be useful at the CLI but is frequently useful when scripting.

    .. code-block:: jinja

        {%- from salt['file.dirname'](tpldir) + '/vars.jinja' import parent_vars %}

    CLI Example:

    .. code-block:: bash

        salt '*' file.dirname 'test/path/filename.config'
    '''
    return os.path.dirname(path)


def join(*args):
    '''
    Return a normalized file system path for the underlying OS

    .. versionadded:: 2014.7.0

    This can be useful at the CLI but is frequently useful when scripting
    combining path variables:

    .. code-block:: jinja

        {% set www_root = '/var' %}
        {% set app_dir = 'myapp' %}

        myapp_config:
          file:
            - managed
            - name: {{ salt['file.join'](www_root, app_dir, 'config.yaml') }}

    CLI Example:

    .. code-block:: bash

        salt '*' file.join '/' 'usr' 'local' 'bin'
    '''
    return os.path.join(*args)


def move(src, dst):
    '''
    Move a file or directory

    CLI Example:

    .. code-block:: bash

        salt '*' file.move /path/to/src /path/to/dst
    '''
    src = os.path.expanduser(src)
    dst = os.path.expanduser(dst)

    if not os.path.isabs(src):
        raise SaltInvocationError('Source path must be absolute.')

    if not os.path.isabs(dst):
        raise SaltInvocationError('Destination path must be absolute.')

    ret = {
        'result': True,
        'comment': "'{0}' moved to '{1}'".format(src, dst),
    }

    try:
        shutil.move(src, dst)
    except (OSError, IOError) as exc:
        raise CommandExecutionError(
            "Unable to move '{0}' to '{1}': {2}".format(src, dst, exc)
        )

    return ret


def diskusage(path):
    '''
    Recursively calculate disk usage of path and return it
    in bytes

    CLI Example:

    .. code-block:: bash

        salt '*' file.diskusage /path/to/check
    '''

    total_size = 0
    seen = set()
    if os.path.isfile(path):
        stat_structure = os.stat(path)
        ret = stat_structure.st_size
        return ret

    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)

            try:
                stat_structure = os.stat(fp)
            except OSError:
                continue

            if stat_structure.st_ino in seen:
                continue

            seen.add(stat_structure.st_ino)

            total_size += stat_structure.st_size

    ret = total_size
    return ret
