# -*- coding: utf-8 -*-
'''
A module written originally by Armin Ronacher to manage file transfers in an
atomic way
'''

# Import python libs
from __future__ import absolute_import
import os
import tempfile
import sys
import errno
import time
import random
import shutil
import salt.ext.six as six


CAN_RENAME_OPEN_FILE = False
if os.name == 'nt':  # pragma: no cover
    _rename = lambda src, dst: False            # pylint: disable=C0103
    _rename_atomic = lambda src, dst: False     # pylint: disable=C0103

    try:
        import ctypes

        _MOVEFILE_REPLACE_EXISTING = 0x1
        _MOVEFILE_WRITE_THROUGH = 0x8
        _MoveFileEx = ctypes.windll.kernel32.MoveFileExW  # pylint: disable=C0103

        def _rename(src, dst):  # pylint: disable=E0102
            if not isinstance(src, six.text_type):
                src = six.text_type(src, sys.getfilesystemencoding())
            if not isinstance(dst, six.text_type):
                dst = six.text_type(dst, sys.getfilesystemencoding())
            if _rename_atomic(src, dst):
                return True
            retry = 0
            rval = False
            while not rval and retry < 100:
                rval = _MoveFileEx(src, dst, _MOVEFILE_REPLACE_EXISTING |
                                             _MOVEFILE_WRITE_THROUGH)
                if not rval:
                    time.sleep(0.001)
                    retry += 1
            return rval

        # new in Vista and Windows Server 2008
        # pylint: disable=C0103
        _CreateTransaction = ctypes.windll.ktmw32.CreateTransaction
        _CommitTransaction = ctypes.windll.ktmw32.CommitTransaction
        _MoveFileTransacted = ctypes.windll.kernel32.MoveFileTransactedW
        _CloseHandle = ctypes.windll.kernel32.CloseHandle
        # pylint: enable=C0103
        CAN_RENAME_OPEN_FILE = True

        def _rename_atomic(src, dst):  # pylint: disable=E0102
            tra = _CreateTransaction(None, 0, 0, 0, 0, 1000, 'Atomic rename')
            if tra == -1:
                return False
            try:
                retry = 0
                rval = False
                while not rval and retry < 100:
                    rval = _MoveFileTransacted(src, dst, None, None,
                                               _MOVEFILE_REPLACE_EXISTING |
                                               _MOVEFILE_WRITE_THROUGH, tra)
                    if rval:
                        rval = _CommitTransaction(tra)
                        break
                    else:
                        time.sleep(0.001)
                        retry += 1
                return rval
            finally:
                _CloseHandle(tra)
    except Exception:
        pass

    def atomic_rename(src, dst):
        # Try atomic or pseudo-atomic rename
        if _rename(src, dst):
            return
        # Fall back to "move away and replace"
        try:
            os.rename(src, dst)
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise
            old = '{0}-{1:08x}'.format(dst, random.randint(0, sys.maxint))
            os.rename(dst, old)
            os.rename(src, dst)
            try:
                os.unlink(old)
            except Exception:
                pass
else:
    atomic_rename = os.rename  # pylint: disable=C0103
    CAN_RENAME_OPEN_FILE = True


class _AtomicWFile(object):
    '''
    Helper class for :func:`atomic_open`.
    '''
    def __init__(self, fhanle, tmp_filename, filename):
        self._fh = fhanle
        self._tmp_filename = tmp_filename
        self._filename = filename

    def __getattr__(self, attr):
        return getattr(self._fh, attr)

    def __enter__(self):
        return self

    def close(self):
        if self._fh.closed:
            return
        self._fh.close()
        if os.path.isfile(self._filename):
            shutil.copymode(self._filename, self._tmp_filename)
        atomic_rename(self._tmp_filename, self._filename)

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.close()
        else:
            self._fh.close()
            try:
                os.remove(self._tmp_filename)
            except OSError:
                pass

    def __repr__(self):
        return '<{0} {1}{2}, mode {3}>'.format(
            self.__class__.__name__,
            self._fh.closed and 'closed ' or '',
            self._filename,
            self._fh.mode
        )


def atomic_open(filename, mode='w'):
    '''
    Works like a regular `open()` but writes updates into a temporary
    file instead of the given file and moves it over when the file is
    closed.  The file returned behaves as if it was a regular Python
    '''
    if mode in ('r', 'rb', 'r+', 'rb+', 'a', 'ab'):
        raise TypeError('Read or append modes don\'t work with atomic_open')
    ntf = tempfile.NamedTemporaryFile(mode, prefix='.___atomic_write',
                                      dir=os.path.dirname(filename),
                                      delete=False)
    return _AtomicWFile(ntf, ntf.name, filename)
