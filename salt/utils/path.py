# -*- coding: utf-8 -*-
"""
Platform independent versions of some os/os.path functions. Gets around PY2's
lack of support for reading NTFS links.
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

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

# Import 3rd-party libs
from salt.ext import six
from salt.utils.decorators.jinja import jinja_filter

try:
    from collections.abc import Iterable
except ImportError:
    # pylint: disable=no-name-in-module
    from collections import Iterable

    # pylint: enable=no-name-in-module


try:
    import win32file
    from pywintypes import error as pywinerror

    HAS_WIN32FILE = True
except ImportError:
    HAS_WIN32FILE = False

log = logging.getLogger(__name__)


def islink(path):
    """
    Equivalent to os.path.islink()
    """
    if six.PY3 or not salt.utils.platform.is_windows():
        return os.path.islink(path)

    if not HAS_WIN32FILE:
        log.error("Cannot check if %s is a link, missing required modules", path)

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
    header_parser = struct.Struct("L")
    (ReparseTag,) = header_parser.unpack(reparse_data[: header_parser.size])
    # http://msdn.microsoft.com/en-us/library/windows/desktop/aa365511.aspx
    if not ReparseTag & 0xA000FFFF == 0xA000000C:
        return False
    else:
        return True


def readlink(path):
    """
    Equivalent to os.readlink()
    """
    if six.PY3 or not salt.utils.platform.is_windows():
        return os.readlink(path)

    if not HAS_WIN32FILE:
        log.error("Cannot read %s, missing required modules", path)

    reparse_data = _get_reparse_data(path)

    if not reparse_data:
        # Reproduce *NIX behavior when os.readlink is performed on a path that
        # is not a symbolic link.
        raise OSError(errno.EINVAL, "Invalid argument: '{0}'".format(path))

    # REPARSE_DATA_BUFFER structure - see
    # http://msdn.microsoft.com/en-us/library/ff552012.aspx

    # parse the structure header to work out which type of reparse point this is
    header_parser = struct.Struct("L")
    (ReparseTag,) = header_parser.unpack(reparse_data[: header_parser.size])
    # http://msdn.microsoft.com/en-us/library/windows/desktop/aa365511.aspx
    if not ReparseTag & 0xA000FFFF == 0xA000000C:
        raise OSError(
            errno.EINVAL,
            "{0} is not a symlink, but another type of reparse point "
            "(0x{0:X}).".format(ReparseTag),
        )

    # parse as a symlink reparse point structure (the structure for other
    # reparse points is different)
    data_parser = struct.Struct("LHHHHHHL")
    (
        ReparseTag,
        ReparseDataLength,
        Reserved,
        SubstituteNameOffset,
        SubstituteNameLength,
        PrintNameOffset,
        PrintNameLength,
        Flags,
    ) = data_parser.unpack(reparse_data[: data_parser.size])

    path_buffer_offset = data_parser.size
    absolute_substitute_name_offset = path_buffer_offset + SubstituteNameOffset
    target_bytes = reparse_data[
        absolute_substitute_name_offset : absolute_substitute_name_offset
        + SubstituteNameLength
    ]
    target = target_bytes.decode("UTF-16")

    if target.startswith("\\??\\"):
        target = target[4:]

    try:
        # comes out in 8.3 form; convert it to LFN to make it look nicer
        target = win32file.GetLongPathName(target)
    except pywinerror as exc:
        # If target is on a UNC share, the decoded target will be in the format
        # "UNC\hostanme\sharename\additional\subdirs\under\share". So, in
        # these cases, return the target path in the proper UNC path format.
        if target.startswith("UNC\\"):
            return re.sub(r"^UNC\\+", r"\\\\", target)
        # if file is not found (i.e. bad symlink), return it anyway like on *nix
        if exc.winerror == 2:
            return target
        raise

    return target


def _is_reparse_point(path):
    """
    Returns True if path is a reparse point; False otherwise.
    """
    result = win32file.GetFileAttributesW(path)

    if result == -1:
        return False

    return True if result & 0x400 else False


def _get_reparse_data(path):
    """
    Retrieves the reparse point data structure for the given path.

    If the path is not a reparse point, None is returned.

    See http://msdn.microsoft.com/en-us/library/ff552012.aspx for details on the
    REPARSE_DATA_BUFFER structure returned.
    """
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
            0x00200000
            | 0x02000000,  # FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS
        )

        reparseData = win32file.DeviceIoControl(
            fileHandle,
            0x900A8,  # FSCTL_GET_REPARSE_POINT
            None,  # in buffer
            16384,  # out buffer size (MAXIMUM_REPARSE_DATA_BUFFER_SIZE)
        )

    finally:
        if fileHandle:
            win32file.CloseHandle(fileHandle)

    return reparseData


@jinja_filter("which")
def which(exe=None):
    """
    Python clone of /usr/bin/which
    """

    if not exe:
        log.error("No executable was passed to be searched by salt.utils.path.which()")
        return None

    ## define some utilities (we use closures here because our predecessor used them)
    def is_executable_common(path):
        """
        This returns truth if posixy semantics (which python simulates on
        windows) states that this is executable.
        """
        return os.path.isfile(path) and os.access(path, os.X_OK)

    def resolve(path):
        """
        This will take a path and recursively follow the link until we get to a
        real file.
        """
        while os.path.islink(path):
            res = os.readlink(path)

            # if the link points to a relative target, then convert it to an
            # absolute path relative to the original path
            if not os.path.isabs(res):
                directory, _ = os.path.split(path)
                res = join(directory, res)
            path = res
        return path

    # windows-only
    def has_executable_ext(path, ext_membership):
        """
        Extract the extension from the specified path, lowercase it so we
        can be insensitive, and then check it against the available exts.
        """
        p, ext = os.path.splitext(path)
        return ext.lower() in ext_membership

    ## prepare related variables from the environment
    res = salt.utils.stringutils.to_unicode(os.environ.get("PATH", ""))
    system_path = res.split(os.pathsep)

    # add some reasonable defaults in case someone's PATH is busted
    if not salt.utils.platform.is_windows():
        res = set(system_path)
        extended_path = [
            "/sbin",
            "/bin",
            "/usr/sbin",
            "/usr/bin",
            "/usr/local/sbin",
            "/usr/local/bin",
        ]
        system_path.extend([p for p in extended_path if p not in res])

    ## now to define the semantics of what's considered executable on a given platform
    if salt.utils.platform.is_windows():
        # executable semantics on windows requires us to search PATHEXT
        res = salt.utils.stringutils.to_str(os.environ.get("PATHEXT", str(".EXE")))

        # generate two variables, one of them for O(n) searches (but ordered)
        # and another for O(1) searches. the previous guy was trying to use
        # memoization with a function that has no arguments, this provides
        # the exact same benefit
        pathext = res.split(os.pathsep)
        res = {ext.lower() for ext in pathext}

        # check if our caller already specified a valid extension as then we don't need to match it
        _, ext = os.path.splitext(exe)
        if ext.lower() in res:
            pathext = [""]

            is_executable = is_executable_common

        # The specified extension isn't valid, so we just assume it's part of the
        # filename and proceed to walk the pathext list
        else:
            is_executable = lambda path, membership=res: is_executable_common(
                path
            ) and has_executable_ext(path, membership)

    else:
        # in posix, there's no such thing as file extensions..only zuul
        pathext = [""]

        # executable semantics are pretty simple on reasonable platforms...
        is_executable = is_executable_common

    ## search for the executable

    # check to see if the full path was specified as then we don't need
    # to actually walk the system_path for any reason
    if is_executable(exe):
        return exe

    # now to search through our system_path
    for path in system_path:
        p = join(path, exe)

        # iterate through all extensions to see which one is executable
        for ext in pathext:
            pext = p + ext
            rp = resolve(pext)
            if is_executable(rp):
                return p + ext
            continue
        continue

    ## if something was executable, we should've found it already...
    log.trace(
        "'%s' could not be found in the following search path: '%s'", exe, system_path
    )
    return None


def which_bin(exes):
    """
    Scan over some possible executables and return the first one that is found
    """
    if not isinstance(exes, Iterable):
        return None
    for exe in exes:
        path = which(exe)
        if not path:
            continue
        return path
    return None


@jinja_filter("path_join")
def join(*parts, **kwargs):
    """
    This functions tries to solve some issues when joining multiple absolute
    paths on both *nix and windows platforms.

    See tests/unit/utils/path_join_test.py for some examples on what's being
    talked about here.

    The "use_posixpath" kwarg can be be used to force joining using poxixpath,
    which is useful for Salt fileserver paths on Windows masters.
    """
    if six.PY3:
        new_parts = []
        for part in parts:
            new_parts.append(salt.utils.stringutils.to_str(part))
        parts = new_parts

    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    use_posixpath = kwargs.pop("use_posixpath", False)
    if kwargs:
        salt.utils.args.invalid_kwargs(kwargs)

    pathlib = posixpath if use_posixpath else os.path

    # Normalize path converting any os.sep as needed
    parts = [pathlib.normpath(p) for p in parts]

    try:
        root = parts.pop(0)
    except IndexError:
        # No args passed to func
        return ""

    root = salt.utils.stringutils.to_unicode(root)
    if not parts:
        ret = root
    else:
        stripped = [p.lstrip(os.sep) for p in parts]
        ret = pathlib.join(root, *salt.utils.data.decode(stripped))
    return pathlib.normpath(ret)


def check_or_die(command):
    """
    Simple convenience function for modules to use for gracefully blowing up
    if a required tool is not available in the system path.

    Lazily import `salt.modules.cmdmod` to avoid any sort of circular
    dependencies.
    """
    if command is None:
        raise CommandNotFoundError("'None' is not a valid command.")

    if not which(command):
        raise CommandNotFoundError("'{0}' is not in the path".format(command))


def sanitize_win_path(winpath):
    """
    Remove illegal path characters for windows
    """
    intab = "<>:|?*"
    if isinstance(winpath, six.text_type):
        winpath = winpath.translate(dict((ord(c), "_") for c in intab))
    elif isinstance(winpath, six.string_types):
        outtab = "_" * len(intab)
        trantab = (
            "".maketrans(intab, outtab) if six.PY3 else string.maketrans(intab, outtab)
        )  # pylint: disable=no-member
        winpath = winpath.translate(trantab)
    return winpath


def safe_path(path, allow_path=None):
    r"""
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
    """
    # Create regex definitions for directories that may be unsafe to modify
    system_root = os.environ.get("SystemRoot", "C:\\Windows")
    deny_paths = (
        r"[a-z]\:\\$",  # C:\, D:\, etc
        r"\\$",  # \
        re.escape(system_root),  # C:\Windows
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
    """
    This is a helper than ensures that all paths returned from os.walk are
    unicode.
    """
    if six.PY2 and salt.utils.platform.is_windows():
        top_query = top
    else:
        top_query = salt.utils.stringutils.to_str(top)
    for item in os.walk(top_query, *args, **kwargs):
        yield salt.utils.data.decode(item, preserve_tuples=True)
