# -*- coding: utf-8 -*-
'''
Platform independent versions of some os/os.path functions. Gets around PY2's
lack of support for reading NTFS links.
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import collections
import errno
import logging
import os
import posixpath
import re
import string
import struct

# Import Salt libs
import salt.utils.args
import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import CommandNotFoundError
from salt.utils.decorators import memoize as real_memoize
from salt.utils.decorators.jinja import jinja_filter

# Import 3rd-party libs
from salt.ext import six

try:
    import win32file
    from pywintypes import error as pywinerror
    HAS_WIN32FILE = True
except ImportError:
    HAS_WIN32FILE = False

log = logging.getLogger(__name__)


def islink(path):
    '''
    Equivalent to os.path.islink()
    '''
    if six.PY3 or not salt.utils.platform.is_windows():
        return os.path.islink(path)

    if not HAS_WIN32FILE:
        log.error('Cannot check if %s is a link, missing required modules', path)

    if not _is_reparse_point(path):
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


def readlink(path):
    '''
    Equivalent to os.readlink()
    '''
    if six.PY3 or not salt.utils.platform.is_windows():
        return os.readlink(path)

    if not HAS_WIN32FILE:
        log.error('Cannot read %s, missing required modules', path)

    reparse_data = _get_reparse_data(path)

    if not reparse_data:
        # Reproduce *NIX behavior when os.readlink is performed on a path that
        # is not a symbolic link.
        raise OSError(errno.EINVAL, 'Invalid argument: \'{0}\''.format(path))

    # REPARSE_DATA_BUFFER structure - see
    # http://msdn.microsoft.com/en-us/library/ff552012.aspx

    # parse the structure header to work out which type of reparse point this is
    header_parser = struct.Struct('L')
    ReparseTag, = header_parser.unpack(reparse_data[:header_parser.size])
    # http://msdn.microsoft.com/en-us/library/windows/desktop/aa365511.aspx
    if not ReparseTag & 0xA000FFFF == 0xA000000C:
        raise OSError(
            errno.EINVAL,
            '{0} is not a symlink, but another type of reparse point '
            '(0x{0:X}).'.format(ReparseTag)
        )

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
        # If target is on a UNC share, the decoded target will be in the format
        # "UNC\hostanme\sharename\additional\subdirs\under\share". So, in
        # these cases, return the target path in the proper UNC path format.
        if target.startswith('UNC\\'):
            return re.sub(r'^UNC\\+', r'\\\\', target)
        # if file is not found (i.e. bad symlink), return it anyway like on *nix
        if exc.winerror == 2:
            return target
        raise

    return target


def _is_reparse_point(path):
    '''
    Returns True if path is a reparse point; False otherwise.
    '''
    result = win32file.GetFileAttributesW(path)

    if result == -1:
        return False

    return True if result & 0x400 else False


def _get_reparse_data(path):
    '''
    Retrieves the reparse point data structure for the given path.

    If the path is not a reparse point, None is returned.

    See http://msdn.microsoft.com/en-us/library/ff552012.aspx for details on the
    REPARSE_DATA_BUFFER structure returned.
    '''
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


@jinja_filter('which')
def which(exe=None):
    '''
    Python clone of /usr/bin/which
    '''
    def _is_executable_file_or_link(exe):
        # check for os.X_OK doesn't suffice because directory may executable
        return (os.access(exe, os.X_OK) and
                (os.path.isfile(exe) or os.path.islink(exe)))

    if exe:
        if _is_executable_file_or_link(exe):
            # executable in cwd or fullpath
            return exe

        ext_list = salt.utils.stringutils.to_str(
            os.environ.get('PATHEXT', str('.EXE'))
        ).split(str(';'))

        @real_memoize
        def _exe_has_ext():
            '''
            Do a case insensitive test if exe has a file extension match in
            PATHEXT
            '''
            for ext in ext_list:
                try:
                    pattern = r'.*\.{0}$'.format(
                        salt.utils.stringutils.to_unicode(ext).lstrip('.')
                    )
                    re.match(
                        pattern,
                        salt.utils.stringutils.to_unicode(exe),
                        re.I).groups()
                    return True
                except AttributeError:
                    continue
            return False

        # Enhance POSIX path for the reliability at some environments, when $PATH is changing
        # This also keeps order, where 'first came, first win' for cases to find optional alternatives
        system_path = salt.utils.stringutils.to_unicode(os.environ.get('PATH', ''))
        search_path = system_path.split(os.pathsep)
        if not salt.utils.platform.is_windows():
            search_path.extend([
                x for x in ('/bin', '/sbin', '/usr/bin',
                            '/usr/sbin', '/usr/local/bin')
                if x not in search_path
            ])

        for path in search_path:
            full_path = join(path, exe)
            if _is_executable_file_or_link(full_path):
                return full_path
            elif salt.utils.platform.is_windows() and not _exe_has_ext():
                # On Windows, check for any extensions in PATHEXT.
                # Allows both 'cmd' and 'cmd.exe' to be matched.
                for ext in ext_list:
                    # Windows filesystem is case insensitive so we
                    # safely rely on that behavior
                    if _is_executable_file_or_link(full_path + ext):
                        return full_path + ext
        log.trace(
            '\'%s\' could not be found in the following search path: \'%s\'',
            exe, search_path
        )
    else:
        log.error('No executable was passed to be searched by salt.utils.path.which()')

    return None


def which_bin(exes):
    '''
    Scan over some possible executables and return the first one that is found
    '''
    if not isinstance(exes, collections.Iterable):
        return None
    for exe in exes:
        path = which(exe)
        if not path:
            continue
        return path
    return None


@jinja_filter('path_join')
def join(*parts, **kwargs):
    '''
    This functions tries to solve some issues when joining multiple absolute
    paths on both *nix and windows platforms.

    See tests/unit/utils/path_join_test.py for some examples on what's being
    talked about here.

    The "use_posixpath" kwarg can be be used to force joining using poxixpath,
    which is useful for Salt fileserver paths on Windows masters.
    '''
    if six.PY3:
        new_parts = []
        for part in parts:
            new_parts.append(salt.utils.stringutils.to_str(part))
        parts = new_parts

    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    use_posixpath = kwargs.pop('use_posixpath', False)
    if kwargs:
        salt.utils.args.invalid_kwargs(kwargs)

    pathlib = posixpath if use_posixpath else os.path

    # Normalize path converting any os.sep as needed
    parts = [pathlib.normpath(p) for p in parts]

    try:
        root = parts.pop(0)
    except IndexError:
        # No args passed to func
        return ''

    root = salt.utils.stringutils.to_unicode(root)
    if not parts:
        ret = root
    else:
        stripped = [p.lstrip(os.sep) for p in parts]
        ret = pathlib.join(root, *salt.utils.data.decode(stripped))
    return pathlib.normpath(ret)


def check_or_die(command):
    '''
    Simple convenience function for modules to use for gracefully blowing up
    if a required tool is not available in the system path.

    Lazily import `salt.modules.cmdmod` to avoid any sort of circular
    dependencies.
    '''
    if command is None:
        raise CommandNotFoundError('\'None\' is not a valid command.')

    if not which(command):
        raise CommandNotFoundError('\'{0}\' is not in the path'.format(command))


def sanitize_win_path(winpath):
    '''
    Remove illegal path characters for windows
    '''
    intab = '<>:|?*'
    if isinstance(winpath, six.text_type):
        winpath = winpath.translate(dict((ord(c), '_') for c in intab))
    elif isinstance(winpath, six.string_types):
        outtab = '_' * len(intab)
        trantab = ''.maketrans(intab, outtab) if six.PY3 else string.maketrans(intab, outtab)  # pylint: disable=no-member
        winpath = winpath.translate(trantab)
    return winpath


def safe_path(path, allow_path=None):
    r'''
    .. versionadded:: 2017.7.3

    Checks that the path is safe for modification by Salt. For example, you
    wouldn't want to have salt delete the contents of ``C:\Windows``. The
    following directories are considered unsafe:

    - C:\, D:\, E:\, etc.
    - \
    - C:\Windows

    Args:

        path (str): The path to check

        allow_paths (str, list): A directory or list of directories inside of
            path that may be safe. For example: ``C:\Windows\TEMP``

    Returns:
        bool: True if safe, otherwise False
    '''
    # Create regex definitions for directories that may be unsafe to modify
    system_root = os.environ.get('SystemRoot', 'C:\\Windows')
    deny_paths = (
        r'[a-z]\:\\$',  # C:\, D:\, etc
        r'\\$',  # \
        re.escape(system_root)  # C:\Windows
    )

    # Make allow_path a list
    if allow_path and not isinstance(allow_path, list):
        allow_path = [allow_path]

    # Create regex definition for directories we may want to make exceptions for
    allow_paths = list()
    if allow_path:
        for item in allow_path:
            allow_paths.append(re.escape(item))

    # Check the path to make sure it's not one of the bad paths
    good_path = True
    for d_path in deny_paths:
        if re.match(d_path, path, flags=re.IGNORECASE) is not None:
            # Found deny path
            good_path = False

    # If local_dest is one of the bad paths, check for exceptions
    if not good_path:
        for a_path in allow_paths:
            if re.match(a_path, path, flags=re.IGNORECASE) is not None:
                # Found exception
                good_path = True

    return good_path


def os_walk(top, *args, **kwargs):
    '''
    This is a helper than ensures that all paths returned from os.walk are
    unicode.
    '''
    for item in os.walk(top, *args, **kwargs):
        yield salt.utils.data.decode(item, preserve_tuples=True)
