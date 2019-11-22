# -*- coding: utf-8 -*-
'''
Manage information about directories, set/read user,
group, mode, and data.
'''

from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import datetime
import errno
import fnmatch
import io
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
from collections import Iterable, Mapping, namedtuple
from functools import reduce  # pylint: disable=redefined-builtin

# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext import six
from salt.ext.six.moves import range, zip
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse
# pylint: enable=import-error,no-name-in-module,redefined-builtin

try:
    import grp
    import pwd
except ImportError:
    pass

# Import salt libs
import salt.utils.args
import salt.utils.atomicfile
import salt.utils.data
import salt.utils.filebuffer
import salt.utils.files
import salt.utils.find
import salt.utils.functools
import salt.utils.hashutils
import salt.utils.itertools
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.templates
import salt.utils.url
import salt.utils.user
import salt.utils.data
import salt.utils.versions
from salt.exceptions import CommandExecutionError, MinionError, SaltInvocationError, get_error_message as _get_error_message
from salt.utils.files import HASHES, HASHES_REVMAP

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    # win_file takes care of windows
    if salt.utils.platform.is_windows():
        return (
            False,
            'The file execution module cannot be loaded: only available on '
            'non-Windows systems - use win_file instead.'
        )
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
    old_isbin = not __utils__['files.is_text'](old)
    new_isbin = not __utils__['files.is_text'](new)
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


def _chattr_version():
    '''
    Return the version of chattr installed
    '''
    # There's no really *good* way to get the version of chattr installed.
    # It's part of the e2fsprogs package - we could try to parse the version
    # from the package manager, but there's no guarantee that it was
    # installed that way.
    #
    # The most reliable approach is to just check tune2fs, since that should
    # be installed with chattr, at least if it was installed in a conventional
    # manner.
    #
    # See https://unix.stackexchange.com/a/520399/5788 for discussion.
    tune2fs = salt.utils.path.which('tune2fs')
    if not tune2fs or salt.utils.platform.is_aix():
        return None
    cmd = [tune2fs]
    result = __salt__['cmd.run'](cmd, ignore_retcode=True, python_shell=False)
    match = re.search(
        r'tune2fs (?P<version>[0-9\.]+)',
        salt.utils.stringutils.to_str(result),
    )
    if match is None:
        version = None
    else:
        version = match.group('version')

    return version


def _chattr_has_extended_attrs():
    '''
    Return ``True`` if chattr supports extended attributes, that is,
    the version is >1.41.22. Otherwise, ``False``
    '''
    ver = _chattr_version()
    if ver is None:
        return False

    needed_version = salt.utils.versions.LooseVersion('1.41.12')
    chattr_version = salt.utils.versions.LooseVersion(ver)
    return chattr_version > needed_version


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
        user = salt.utils.user.get_user()
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

    mode = six.text_type(mode).lstrip('0Oo')
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


def _cmp_attrs(path, attrs):
    '''
    .. versionadded:: 2018.3.0

    Compare attributes of a given file to given attributes.
    Returns a pair (list) where first item are attributes to
    add and second item are to be removed.

    Please take into account when using this function that some minions will
    not have lsattr installed.

    path
        path to file to compare attributes with.

    attrs
        string of attributes to compare against a given file
    '''
    # lsattr for AIX is not the same thing as lsattr for linux.
    if salt.utils.platform.is_aix():
        return None

    try:
        lattrs = lsattr(path).get(path, '')
    except AttributeError:
        # lsattr not installed
        return None

    new = set(attrs)
    old = set(lattrs)

    return AttrChanges(
        added=''.join(new-old) or None,
        removed=''.join(old-new) or None,
    )


def lsattr(path):
    '''
    .. versionadded:: 2018.3.0
    .. versionchanged:: 2018.3.1
        If ``lsattr`` is not installed on the system, ``None`` is returned.
    .. versionchanged:: 2018.3.4
        If on ``AIX``, ``None`` is returned even if in filesystem as lsattr on ``AIX``
        is not the same thing as the linux version.

    Obtain the modifiable attributes of the given file. If path
    is to a directory, an empty list is returned.

    path
        path to file to obtain attributes of. File/directory must exist.

    CLI Example:

    .. code-block:: bash

        salt '*' file.lsattr foo1.txt
    '''
    if not salt.utils.path.which('lsattr') or salt.utils.platform.is_aix():
        return None

    if not os.path.exists(path):
        raise SaltInvocationError("File or directory does not exist.")

    cmd = ['lsattr', path]
    result = __salt__['cmd.run'](cmd, ignore_retcode=True, python_shell=False)

    results = {}
    for line in result.splitlines():
        if not line.startswith('lsattr: '):
            attrs, file = line.split(None, 1)
            if _chattr_has_extended_attrs():
                pattern = r"[aAcCdDeijPsStTu]"
            else:
                pattern = r"[acdijstuADST]"
            results[file] = re.findall(pattern, attrs)

    return results


def chattr(*files, **kwargs):
    '''
    .. versionadded:: 2018.3.0

    Change the attributes of files. This function accepts one or more files and
    the following options:

    operator
        Can be wither ``add`` or ``remove``. Determines whether attributes
        should be added or removed from files

    attributes
        One or more of the following characters: ``aAcCdDeijPsStTu``,
        representing attributes to add to/remove from files

    version
        a version number to assign to the file(s)

    flags
        One or more of the following characters: ``RVf``, representing
        flags to assign to chattr (recurse, verbose, suppress most errors)

    CLI Example:

    .. code-block:: bash

        salt '*' file.chattr foo1.txt foo2.txt operator=add attributes=ai
        salt '*' file.chattr foo3.txt operator=remove attributes=i version=2
    '''
    operator = kwargs.pop('operator', None)
    attributes = kwargs.pop('attributes', None)
    flags = kwargs.pop('flags', None)
    version = kwargs.pop('version', None)

    if (operator is None) or (operator not in ('add', 'remove')):
        raise SaltInvocationError(
            "Need an operator: 'add' or 'remove' to modify attributes.")
    if attributes is None:
        raise SaltInvocationError("Need attributes: [aAcCdDeijPsStTu]")

    cmd = ['chattr']

    if operator == "add":
        attrs = '+{0}'.format(attributes)
    elif operator == "remove":
        attrs = '-{0}'.format(attributes)

    cmd.append(attrs)

    if flags is not None:
        cmd.append('-{0}'.format(flags))

    if version is not None:
        cmd.extend(['-v', version])

    cmd.extend(files)

    result = __salt__['cmd.run'](cmd, python_shell=False)

    if bool(result):
        return False

    return True


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
    return salt.utils.hashutils.get_hash(path, form, 4096)


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
    return salt.utils.hashutils.get_hash(path, form)


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

    saltenv : base
        Salt fileserver environment from which to retrieve the source_hash. This
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
        ret['hsum'] = ret['hsum'].lower()
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

        ret['hsum'] = ret['hsum'].lower()
        return ret


def check_hash(path, file_hash):
    '''
    Check if a file matches the given hash string

    Returns ``True`` if the hash matches, otherwise ``False``.

    path
        Path to a file local to the minion.

    hash
        The hash to check against the file specified in the ``path`` argument.

        .. versionchanged:: 2016.11.4

        For this and newer versions the hash can be specified without an
        accompanying hash type (e.g. ``e138491e9d5b97023cea823fe17bac22``),
        but for earlier releases it is necessary to also specify the hash type
        in the format ``<hash_type>=<hash_value>`` (e.g.
        ``md5=e138491e9d5b97023cea823fe17bac22``).

    CLI Example:

    .. code-block:: bash

        salt '*' file.check_hash /etc/fstab e138491e9d5b97023cea823fe17bac22
        salt '*' file.check_hash /etc/fstab md5=e138491e9d5b97023cea823fe17bac22
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
    before = six.text_type(before)
    after = six.text_type(after)
    before = _sed_esc(before, escape_all)
    after = _sed_esc(after, escape_all)
    limit = _sed_esc(limit, escape_all)
    if sys.platform == 'darwin':
        options = options.replace('-r', '-E')

    cmd = ['sed']
    cmd.append('-i{0}'.format(backup) if backup else '-i')
    cmd.extend(salt.utils.args.shlex_split(options))
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

    before = _sed_esc(six.text_type(text), False)
    limit = _sed_esc(six.text_type(limit), False)
    options = '-n -r -e'
    if sys.platform == 'darwin':
        options = options.replace('-r', '-E')

    cmd = ['sed']
    cmd.extend(salt.utils.args.shlex_split(options))
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

    before = six.text_type(before)
    after = six.text_type(after)
    before = _sed_esc(before, escape_all)
    # The pattern to replace with does not need to be escaped!!!
    #after = _sed_esc(after, escape_all)
    limit = _sed_esc(limit, escape_all)

    shutil.copy2(path, '{0}{1}'.format(path, backup))

    with salt.utils.files.fopen(path, 'w') as ofile:
        with salt.utils.files.fopen('{0}{1}'.format(path, backup), 'r') as ifile:
            if multi is True:
                for line in ifile.readline():
                    ofile.write(
                        salt.utils.stringutils.to_str(
                            _psed(
                                salt.utils.stringutils.to_unicode(line),
                                before,
                                after,
                                limit,
                                flags
                            )
                        )
                    )
            else:
                ofile.write(
                    salt.utils.stringutils.to_str(
                        _psed(
                            salt.utils.stringutils.to_unicode(ifile.read()),
                            before,
                            after,
                            limit,
                            flags
                        )
                    )
                )


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
    if not __utils__['files.is_text'](path):
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
        with salt.utils.files.fopen(path,
                              mode='rb',
                              buffering=bufsize) as r_file:
            # Loop through each line of the file and look for a match
            for line in r_file:
                # Is it in this line
                line = salt.utils.stringutils.to_unicode(line)
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

    if not salt.utils.platform.is_windows():
        pre_user = get_user(path)
        pre_group = get_group(path)
        pre_mode = salt.utils.files.normalize_mode(get_mode(path))

    # Create a copy to read from and to use as a backup later
    try:
        temp_file = _mkstemp_copy(path=path, preserve_inode=False)
    except (OSError, IOError) as exc:
        raise CommandExecutionError("Exception: {0}".format(exc))

    try:
        # Open the file in write mode
        mode = 'wb' if six.PY2 and salt.utils.platform.is_windows() else 'w'
        with salt.utils.files.fopen(path,
                              mode=mode,
                              buffering=bufsize) as w_file:
            try:
                # Open the temp file in read mode
                with salt.utils.files.fopen(temp_file,
                                      mode='rb',
                                      buffering=bufsize) as r_file:
                    # Loop through each line of the file and look for a match
                    for line in r_file:
                        line = salt.utils.stringutils.to_unicode(line)
                        try:
                            # Is it in this line
                            if re.match(regex, line):
                                # Write the new line
                                if cmnt:
                                    wline = '{0}{1}'.format(char, line)
                                else:
                                    wline = line.lstrip(char)
                            else:
                                # Write the existing line (no change)
                                wline = line
                            wline = salt.utils.stringutils.to_bytes(wline) \
                                if six.PY2 and salt.utils.platform.is_windows() \
                                else salt.utils.stringutils.to_str(wline)
                            w_file.write(wline)
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

    if not salt.utils.platform.is_windows():
        check_perms(path, None, pre_user, pre_group, pre_mode)

    # Return a diff using the two dictionaries
    return __utils__['stringutils.get_diff'](orig_file, new_file)


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
            _flag = getattr(re, six.text_type(flag).upper())

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
        temp_file = salt.utils.files.mkstemp(prefix=salt.utils.files.TEMPFILE_PREFIX)
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
    Returns True if src and probe at least matches at the beginning till some point.
    '''
    def _strip_comments(txt):
        '''
        Strip possible comments.
        Usually comments are one or two symbols at the beginning of the line, separated with space
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

    src = src.rstrip('\n\r')
    probe = probe.rstrip('\n\r')
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
        compiled = re.compile(regex, re.DOTALL)
        src = [line for line in src if compiled.search(line) or line.count(regex)]
    except Exception as ex:
        raise CommandExecutionError("{0}: '{1}'".format(_get_error_message(ex), regex))

    return src and src or []


def _assert_occurrence(probe, target, amount=1):
    '''
    Raise an exception, if there are different amount of specified occurrences in src.
    '''
    occ = len(probe)
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

    return occ


def _set_line_indent(src, line, indent):
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

    return ''.join(idt) + line.lstrip()


def _get_eol(line):
    match = re.search('((?<!\r)\n|\r(?!\n)|\r\n)$', line)
    return match and match.group() or ''


def _set_line_eol(src, line):
    '''
    Add line ending
    '''
    line_ending = _get_eol(src) or os.linesep
    return line.rstrip() + line_ending


def _insert_line_before(idx, body, content, indent):
    if not idx or (idx and _starts_till(body[idx - 1], content) < 0):
        cnd = _set_line_indent(body[idx], content, indent)
        body.insert(idx, cnd)
    return body


def _insert_line_after(idx, body, content, indent):
    # No duplicates or append, if "after" is the last line
    next_line = idx + 1 < len(body) and body[idx + 1] or None
    if next_line is None or _starts_till(next_line, content) < 0:
        cnd = _set_line_indent(body[idx], content, indent)
        body.insert(idx + 1, cnd)
    return body


def line(path, content=None, match=None, mode=None, location=None,
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
        Content of the line. Allowed to be empty if mode=delete.

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

    # We've set the content to be empty in the function params but we want to make sure
    # it gets passed when needed. Feature #37092
    empty_content_modes = ['delete']
    if mode not in empty_content_modes and content is None:
        raise CommandExecutionError('Content can only be empty if mode is "{0}"'.format(', '.join(empty_content_modes)))
    del empty_content_modes

    # Before/after has privilege. If nothing defined, match is used by content.
    if before is None and after is None and not match:
        match = content

    with salt.utils.files.fopen(path, mode='r') as fp_:
        body = salt.utils.data.decode_list(fp_.readlines())
    body_before = hashlib.sha256(salt.utils.stringutils.to_bytes(''.join(body))).hexdigest()
    # Add empty line at the end if last line ends with eol.
    # Allows simpler code
    if body and _get_eol(body[-1]):
        body.append('')

    after = _regex_to_static(body, after)
    before = _regex_to_static(body, before)
    match = _regex_to_static(body, match)

    if os.stat(path).st_size == 0 and mode in ('delete', 'replace'):
        log.warning('Cannot find text to {0}. File \'{1}\' is empty.'.format(mode, path))
        body = []
    elif mode == 'delete' and match:
        body = [line for line in body if line != match[0]]
    elif mode == 'replace' and match:
        idx = body.index(match[0])
        file_line = body.pop(idx)
        body.insert(idx, _set_line_indent(file_line, content, indent))
    elif mode == 'insert':
        if not location and not before and not after:
            raise CommandExecutionError('On insert must be defined either "location" or "before/after" conditions.')

        if not location:
            if before and after:
                _assert_occurrence(before, 'before')
                _assert_occurrence(after, 'after')

                out = []
                in_range = False
                for line in body:
                    if line == after[0]:
                        in_range = True
                    elif line == before[0] and in_range:
                        cnd = _set_line_indent(line, content, indent)
                        out.append(cnd)
                    out.append(line)
                body = out

            if before and not after:
                _assert_occurrence(before, 'before')

                idx = body.index(before[0])
                body = _insert_line_before(idx, body, content, indent)

            elif after and not before:
                _assert_occurrence(after, 'after')

                idx = body.index(after[0])
                body = _insert_line_after(idx, body, content, indent)

        else:
            if location == 'start':
                if body:
                    body.insert(0, _set_line_eol(body[0], content))
                else:
                    body.append(content + os.linesep)
            elif location == 'end':
                body.append(_set_line_indent(body[-1], content, indent) if body else content)

    elif mode == 'ensure':

        if before and after:
            _assert_occurrence(before, 'before')
            _assert_occurrence(after, 'after')

            is_there = bool([l for l in body if l.count(content)])
            if not is_there:
                idx = body.index(after[0])
                if idx < (len(body) - 1) and body[idx + 1] == before[0]:
                    cnd = _set_line_indent(body[idx], content, indent)
                    body.insert(idx + 1, cnd)
                else:
                    raise CommandExecutionError('Found more than one line between '
                                                'boundaries "before" and "after".')

        elif before and not after:
            _assert_occurrence(before, 'before')

            idx = body.index(before[0])
            body = _insert_line_before(idx, body, content, indent)

        elif not before and after:
            _assert_occurrence(after, 'after')

            idx = body.index(after[0])
            body = _insert_line_after(idx, body, content, indent)

        else:
            raise CommandExecutionError("Wrong conditions? "
                                        "Unable to ensure line without knowing "
                                        "where to put it before and/or after.")

    if body:
        for idx, line in enumerate(body):
            if not _get_eol(line) and idx+1 < len(body):
                prev = idx and idx-1 or 1
                body[idx] = _set_line_eol(body[prev], line)
        # We do not need empty line at the end anymore
        if '' == body[-1]:
            body.pop()

    changed = body_before != hashlib.sha256(salt.utils.stringutils.to_bytes(''.join(body))).hexdigest()

    if backup and changed and __opts__['test'] is False:
        try:
            temp_file = _mkstemp_copy(path=path, preserve_inode=True)
            shutil.move(temp_file, '{0}.{1}'.format(path, time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime())))
        except (OSError, IOError) as exc:
            raise CommandExecutionError("Unable to create the backup file of {0}. Exception: {1}".format(path, exc))

    changes_diff = None

    if changed:
        if show_changes:
            with salt.utils.files.fopen(path, 'r') as fp_:
                path_content = salt.utils.data.decode_list(fp_.read().splitlines(True))
            changes_diff = __utils__['stringutils.get_diff'](path_content, body)
        if __opts__['test'] is False:
            fh_ = None
            try:
                # Make sure we match the file mode from salt.utils.files.fopen
                if six.PY2 and salt.utils.platform.is_windows():
                    mode = 'wb'
                    body = salt.utils.data.encode_list(body)
                else:
                    mode = 'w'
                    body = salt.utils.data.decode_list(body, to_str=True)
                fh_ = salt.utils.atomicfile.atomic_open(path, mode)
                fh_.writelines(body)
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
            backslash_literal=False,
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
        A list of flags defined in the ``re`` module documentation from the
        Python standard library. Each list item should be a string that will
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

    backslash_literal : False
        .. versionadded:: 2016.11.7

        Interpret backslashes as literal backslashes for the repl and not
        escape characters.  This will help when using append/prepend so that
        the backslashes are not interpreted for the repl on the second run of
        the state.

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

    if not __utils__['files.is_text'](path):
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
    cpattern = re.compile(salt.utils.stringutils.to_bytes(pattern), flags_num)
    filesize = os.path.getsize(path)
    if bufsize == 'file':
        bufsize = filesize

    # Search the file; track if any changes have been made for the return val
    has_changes = False
    orig_file = []  # used for show_changes and change detection
    new_file = []  # used for show_changes and change detection
    if not salt.utils.platform.is_windows():
        pre_user = get_user(path)
        pre_group = get_group(path)
        pre_mode = salt.utils.files.normalize_mode(get_mode(path))

    # Avoid TypeErrors by forcing repl to be bytearray related to mmap
    # Replacement text may contains integer: 123 for example
    repl = salt.utils.stringutils.to_bytes(six.text_type(repl))
    if not_found_content:
        not_found_content = salt.utils.stringutils.to_bytes(not_found_content)

    found = False
    temp_file = None
    content = salt.utils.stringutils.to_unicode(not_found_content) \
        if not_found_content and (prepend_if_not_found or append_if_not_found) \
        else salt.utils.stringutils.to_unicode(repl)

    try:
        # First check the whole file, determine whether to make the replacement
        # Searching first avoids modifying the time stamp if there are no changes
        r_data = None
        # Use a read-only handle to open the file
        with salt.utils.files.fopen(path,
                              mode='rb',
                              buffering=bufsize) as r_file:
            try:
                # mmap throws a ValueError if the file is empty.
                r_data = mmap.mmap(r_file.fileno(),
                                   0,
                                   access=mmap.ACCESS_READ)
            except (ValueError, mmap.error):
                # size of file in /proc is 0, but contains data
                r_data = salt.utils.stringutils.to_bytes("".join(r_file))
            if search_only:
                # Just search; bail as early as a match is found
                if re.search(cpattern, r_data):
                    return True  # `with` block handles file closure
                else:
                    return False
            else:
                result, nrepl = re.subn(cpattern,
                                        repl.replace('\\', '\\\\') if backslash_literal else repl,
                                        r_data,
                                        count)

                # found anything? (even if no change)
                if nrepl > 0:
                    found = True
                    # Identity check the potential change
                    has_changes = True if pattern != repl else has_changes

                if prepend_if_not_found or append_if_not_found:
                    # Search for content, to avoid pre/appending the
                    # content if it was pre/appended in a previous run.
                    if re.search(salt.utils.stringutils.to_bytes('^{0}($|(?=\r\n))'.format(re.escape(content))),
                                 r_data,
                                 flags=flags_num):
                        # Content was found, so set found.
                        found = True

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
            with salt.utils.files.fopen(path,
                        mode='w',
                        buffering=bufsize) as w_file:
                try:
                    # Open the temp file in read mode
                    with salt.utils.files.fopen(temp_file,
                                          mode='r',
                                          buffering=bufsize) as r_file:
                        r_data = mmap.mmap(r_file.fileno(),
                                           0,
                                           access=mmap.ACCESS_READ)
                        result, nrepl = re.subn(cpattern,
                                                repl.replace('\\', '\\\\') if backslash_literal else repl,
                                                r_data,
                                                count)
                        try:
                            w_file.write(salt.utils.stringutils.to_str(result))
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
            new_file.insert(0, not_found_content + salt.utils.stringutils.to_bytes(os.linesep))
        else:
            # append_if_not_found
            # Make sure we have a newline at the end of the file
            if 0 != len(new_file):
                if not new_file[-1].endswith(salt.utils.stringutils.to_bytes(os.linesep)):
                    new_file[-1] += salt.utils.stringutils.to_bytes(os.linesep)
            new_file.append(not_found_content + salt.utils.stringutils.to_bytes(os.linesep))
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
                fh_ = salt.utils.atomicfile.atomic_open(path, 'wb')
                for line in new_file:
                    fh_.write(salt.utils.stringutils.to_bytes(line))
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
            except Exception:
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

    if not dry_run and not salt.utils.platform.is_windows():
        check_perms(path, None, pre_user, pre_group, pre_mode)

    differences = __utils__['stringutils.get_diff'](orig_file, new_file)

    if show_changes:
        return differences

    # We may have found a regex line match but don't need to change the line
    # (for situations where the pattern also matches the repl). Revert the
    # has_changes flag to False if the final result is unchanged.
    if not differences:
        has_changes = False

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
        append_newline=False):
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
        The line content identifying the end of the content block. As of
        versions 2017.7.5 and 2018.3.1, everything up to the text matching the
        marker will be replaced, so it's important to ensure that your marker
        includes the beginning of the text you wish to replace.

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

    dry_run : False
        If ``True``, do not make any edits to the file and simply return the
        changes that *would* be made.

    show_changes : True
        Controls how changes are presented. If ``True``, this function will
        return a unified diff of the changes made. If False, then it will
        return a boolean (``True`` if any changes were made, otherwise
        ``False``).

    append_newline : False
        Controls whether or not a newline is appended to the content block. If
        the value of this argument is ``True`` then a newline will be added to
        the content block. If it is ``False``, then a newline will *not* be
        added to the content block. If it is ``None`` then a newline will only
        be added to the content block if it does not already end in a newline.

        .. versionadded:: 2016.3.4
        .. versionchanged:: 2017.7.5,2018.3.1
            New behavior added when value is ``None``.
        .. versionchanged:: 2019.2.0
            The default value of this argument will change to ``None`` to match
            the behavior of the :py:func:`file.blockreplace state
            <salt.states.file.blockreplace>`

    CLI Example:

    .. code-block:: bash

        salt '*' file.blockreplace /etc/hosts '#-- start managed zone foobar : DO NOT EDIT --' \\
        '#-- end managed zone foobar --' $'10.0.1.1 foo.foobar\\n10.0.1.2 bar.foobar' True

    '''
    if append_if_not_found and prepend_if_not_found:
        raise SaltInvocationError(
            'Only one of append and prepend_if_not_found is permitted'
        )

    path = os.path.expanduser(path)

    if not os.path.exists(path):
        raise SaltInvocationError('File not found: {0}'.format(path))

    try:
        file_encoding = __utils__['files.get_encoding'](path)
    except CommandExecutionError:
        file_encoding = None

    if __utils__['files.is_binary'](path):
        if not file_encoding:
            raise SaltInvocationError(
                'Cannot perform string replacements on a binary file: {0}'
                .format(path)
        )

    if append_newline is None and not content.endswith((os.linesep, '\n')):
        append_newline = True

    # Split the content into a list of lines, removing newline characters. To
    # ensure that we handle both Windows and POSIX newlines, first split on
    # Windows newlines, and then split on POSIX newlines.
    split_content = []
    for win_line in content.split('\r\n'):
        for content_line in win_line.split('\n'):
            split_content.append(content_line)

    line_count = len(split_content)

    has_changes = False
    orig_file = []
    new_file = []
    in_block = False
    block_found = False
    linesep = None

    def _add_content(linesep, lines=None, include_marker_start=True,
                     end_line=None):
        if lines is None:
            lines = []
            include_marker_start = True

        if end_line is None:
            end_line = marker_end
        end_line = end_line.rstrip('\r\n') + linesep

        if include_marker_start:
            lines.append(marker_start + linesep)

        if split_content:
            for index, content_line in enumerate(split_content, 1):
                if index != line_count:
                    lines.append(content_line + linesep)
                else:
                    # We're on the last line of the content block
                    if append_newline:
                        lines.append(content_line + linesep)
                        lines.append(end_line)
                    else:
                        lines.append(content_line + end_line)
        else:
            lines.append(end_line)

        return lines

    # We do not use in-place editing to avoid file attrs modifications when
    # no changes are required and to avoid any file access on a partially
    # written file.
    try:
        fi_file = io.open(path, mode='r', encoding=file_encoding, newline='')
        for line in fi_file:
            write_line_to_new_file = True

            if linesep is None:
                # Auto-detect line separator
                if line.endswith('\r\n'):
                    linesep = '\r\n'
                elif line.endswith('\n'):
                    linesep = '\n'
                else:
                    # No newline(s) in file, fall back to system's linesep
                    linesep = os.linesep

            if marker_start in line:
                # We've entered the content block
                in_block = True
            else:
                if in_block:
                    # We're not going to write the lines from the old file to
                    # the new file until we have exited the block.
                    write_line_to_new_file = False

                    marker_end_pos = line.find(marker_end)
                    if marker_end_pos != -1:
                        # End of block detected
                        in_block = False
                        # We've found and exited the block
                        block_found = True

                        _add_content(linesep, lines=new_file,
                                     include_marker_start=False,
                                     end_line=line[marker_end_pos:])

            # Save the line from the original file
            orig_file.append(line)
            if write_line_to_new_file:
                new_file.append(line)

    except (IOError, OSError) as exc:
        raise CommandExecutionError(
            'Failed to read from {0}: {1}'.format(path, exc)
        )
    finally:
        if linesep is None:
            # If the file was empty, we will not have set linesep yet. Assume
            # the system's line separator. This is needed for when we
            # prepend/append later on.
            linesep = os.linesep
        try:
            fi_file.close()
        except Exception:
            pass

    if in_block:
        # unterminated block => bad, always fail
        raise CommandExecutionError(
            'Unterminated marked block. End of file reached before marker_end.'
        )

    if not block_found:
        if prepend_if_not_found:
            # add the markers and content at the beginning of file
            prepended_content = _add_content(linesep)
            prepended_content.extend(new_file)
            new_file = prepended_content
            block_found = True
        elif append_if_not_found:
            # Make sure we have a newline at the end of the file
            if 0 != len(new_file):
                if not new_file[-1].endswith(linesep):
                    new_file[-1] += linesep
            # add the markers and content at the end of file
            _add_content(linesep, lines=new_file)
            block_found = True
        else:
            raise CommandExecutionError(
                'Cannot edit marked block. Markers were not found in file.'
            )

    if block_found:
        diff = __utils__['stringutils.get_diff'](orig_file, new_file)
        has_changes = diff is not ''
        if has_changes and not dry_run:
            # changes detected
            # backup file attrs
            perms = {}
            perms['user'] = get_user(path)
            perms['group'] = get_group(path)
            perms['mode'] = salt.utils.files.normalize_mode(get_mode(path))

            # backup old content
            if backup is not False:
                backup_path = '{0}{1}'.format(path, backup)
                shutil.copy2(path, backup_path)
                # copy2 does not preserve ownership
                if salt.utils.platform.is_windows():
                    # This function resides in win_file.py and will be available
                    # on Windows. The local function will be overridden
                    # pylint: disable=E1120,E1123
                    check_perms(path=backup_path,
                                ret=None,
                                owner=perms['user'])
                    # pylint: enable=E1120,E1123
                else:
                    check_perms(name=backup_path,
                                ret=None,
                                user=perms['user'],
                                group=perms['group'],
                                mode=perms['mode'])

            # write new content in the file while avoiding partial reads
            try:
                fh_ = salt.utils.atomicfile.atomic_open(path, 'wb')
                for line in new_file:
                    fh_.write(salt.utils.stringutils.to_bytes(line, encoding=file_encoding))
            finally:
                fh_.close()

            # this may have overwritten file attrs
            if salt.utils.platform.is_windows():
                # This function resides in win_file.py and will be available
                # on Windows. The local function will be overridden
                # pylint: disable=E1120,E1123
                check_perms(path=path,
                            ret=None,
                            owner=perms['user'])
                # pylint: enable=E1120,E1123
            else:
                check_perms(path,
                            ret=None,
                            user=perms['user'],
                            group=perms['group'],
                            mode=perms['mode'])

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
    patchpath = salt.utils.path.which('patch')
    if not patchpath:
        raise CommandExecutionError(
            'patch executable not found. Is the distribution\'s patch '
            'package installed?'
        )

    cmd = [patchpath]
    cmd.extend(salt.utils.args.shlex_split(options))
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

    stripped_text = six.text_type(text).strip()
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
        with salt.utils.files.fopen(path, 'r') as target:
            for line in target:
                line = salt.utils.stringutils.to_unicode(line)
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
    with salt.utils.files.fopen(path, 'rb+') as ofile:
        linesep = salt.utils.stringutils.to_bytes(os.linesep)
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
    with salt.utils.files.fopen(path, 'a') as ofile:
        for new_line in args:
            ofile.write(
                salt.utils.stringutils.to_str(
                    '{0}{1}'.format(new_line, os.linesep)
                )
            )

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
        with salt.utils.files.fopen(path) as fhr:
            contents = [salt.utils.stringutils.to_unicode(line)
                        for line in fhr.readlines()]
    except IOError:
        contents = []

    preface = []
    for line in args:
        preface.append('{0}\n'.format(line))

    with salt.utils.files.fopen(path, 'w') as ofile:
        contents = preface + contents
        ofile.write(salt.utils.stringutils.to_str(''.join(contents)))
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
    with salt.utils.files.fopen(path, "w") as ofile:
        ofile.write(salt.utils.stringutils.to_str(''.join(contents)))
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
            with salt.utils.files.fopen(name, 'a'):
                pass

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
    seek_fh = os.open(path, os.O_RDONLY)
    try:
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
    seek_fh = os.open(path, os.O_WRONLY)
    try:
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
    with salt.utils.files.fopen(path, 'rb+') as seek_fh:
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


def symlink(src, path):
    '''
    Create a symbolic link (symlink, soft link) to a file

    CLI Example:

    .. code-block:: bash

        salt '*' file.symlink /path/to/file /path/to/link
    '''
    path = os.path.expanduser(path)

    try:
        if os.path.normpath(os.readlink(path)) == os.path.normpath(src):
            log.debug('link already in correct state: %s -> %s', path, src)
            return True
    except OSError:
        pass

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

    if not salt.utils.platform.is_windows():
        pre_user = get_user(src)
        pre_group = get_group(src)
        pre_mode = salt.utils.files.normalize_mode(get_mode(src))

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

    if not salt.utils.platform.is_windows():
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


def read(path, binary=False):
    '''
    .. versionadded:: 2017.7.0

    Return the content of the file.

    CLI Example:

    .. code-block:: bash

        salt '*' file.read /path/to/file
    '''
    access_mode = 'r'
    if binary is True:
        access_mode += 'b'
    with salt.utils.files.fopen(path, access_mode) as file_obj:
        return salt.utils.stringutils.to_unicode(file_obj.read())


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


def get_absolute(path, resolve=False, follow_symlinks=False):
    return salt.utils.path.get_absolute(path, resolve, follow_symlinks)


def set_link(src, path, hard=False, resolve=True):
    return salt.utils.path.set_link(src, path, hard, resolve)


def get_link(path, resolve=True):
    return salt.utils.path.get_link(path, resolve)


def dir_to_list(path, recursive=False, follow_symlinks=False):
    return salt.utils.path.dir_to_list(path, recursive, follow_symlinks)


def dir_to_dict(path, recursive=False, follow_symlinks=False):
    return salt.utils.path.dir_to_dict(path, recursive, follow_symlinks)


def dir_is_absent(path):
    return salt.utils.path.dir_is_absent(path)


def file_is_absent(path):
    return salt.utils.path.file_is_absent(path)


def remove(path, recursive=False, follow_symlinks=False):
    return salt.utils.path.remove(path, recursive, follow_symlinks)



def dir_is_empty(path):
    return salt.utils.path.dir_is_empty(path)


def is_symlink(path):
    return salt.utils.path.is_symlink(path)