# -*- coding: utf-8 -*-
'''
Functions for working with Symlinks on Windows

:requires: pywin32
'''
from __future__ import absolute_import
import os
import struct
import sys

# Import Salt Libs
import salt.utils
from salt.exceptions import SaltInvocationError

if salt.utils.is_windows():
    import win32file
    from pywintypes import error as pywinerror
    HAS_WIN32 = True
else:
    HAS_WIN32 = False



# Although utils are often directly imported, it is also possible to use the
# loader.
def __virtual__():
    '''
    Only load if Win32 Libraries are installed
    '''
    if not salt.utils.is_windows():
        return False, 'This Salt util only runs on Windows'

    if not HAS_WIN32:
        return False, 'This Salt util requires pywin32'

    return 'win_symlink'


def _is_reparse_point(path):
    '''
    Returns True if path is a reparse point; False otherwise.
    '''
    if sys.getwindowsversion().major < 6:
        raise SaltInvocationError(
            'Symlinks are only supported on Windows Vista or later.')

    result = win32file.GetFileAttributesW(path)

    if result == -1:
        raise SaltInvocationError('Invalid path: {0}'.format(path))

    if result & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
        return True
    else:
        return False


def _get_reparse_data(path):
    '''
    Retrieves the reparse point data structure for the given path.

    If the path is not a reparse point, None is returned.

    See http://msdn.microsoft.com/en-us/library/ff552012.aspx for details on the
    REPARSE_DATA_BUFFER structure returned.
    '''
    if sys.getwindowsversion().major < 6:
        raise SaltInvocationError(
            'Symlinks are only supported on Windows Vista or later.')

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


def is_link(path):
    '''
    Check if the path is a symlink

    This is only supported on Windows Vista or later.

    Inline with Unix behavior, this function will raise an error if the path
    is not a symlink, however, the error raised will be a SaltInvocationError,
    not an OSError.

    CLI Example:

    .. code-block:: bash

       salt '*' file.is_link /path/to/link
    '''
    try:
        if not _is_reparse_point(path):
            return False
    except SaltInvocationError:
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


def read_link(path):
    '''
    Return the path that a symlink points to

    This is only supported on Windows Vista or later.

    Inline with Unix behavior, this function will raise an error if the path is
    not a symlink, however, the error raised will be a SaltInvocationError, not
    an OSError.

    CLI Example:

    .. code-block:: bash

        salt '*' file.readlink /path/to/link
    '''
    if sys.getwindowsversion().major < 6:
        raise SaltInvocationError(
            'Symlinks are only supported on Windows Vista or later.')

    if not os.path.isabs(path):
        raise SaltInvocationError('Path to link must be absolute.')

    reparse_data = _get_reparse_data(path)

    if not reparse_data:
        raise SaltInvocationError(
            'The path specified is not a reparse point (symlinks are a type of '
            'reparse point).')

    # REPARSE_DATA_BUFFER structure - see
    # http://msdn.microsoft.com/en-us/library/ff552012.aspx

    # parse the structure header to work out which type of reparse point this is
    header_parser = struct.Struct('L')
    ReparseTag, = header_parser.unpack(reparse_data[:header_parser.size])
    # http://msdn.microsoft.com/en-us/library/windows/desktop/aa365511.aspx
    if not ReparseTag & 0xA000FFFF == 0xA000000C:
        raise SaltInvocationError(
            'The path specified is not a symlink, but another type of reparse '
            'point (0x{0:X}).'.format(ReparseTag))

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
        # if file is not found (i.e. bad symlink), return it anyway like on *nix
        if exc.winerror == 2:
            return target
        raise

    return target
