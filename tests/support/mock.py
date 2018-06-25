# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)

    tests.support.mock
    ~~~~~~~~~~~~~~~~~~

    Helper module that wraps `mock` and provides some fake objects in order to
    properly set the function/class decorators and yet skip the test case's
    execution.

    Note: mock >= 2.0.0 required since unittest.mock does not have
    MagicMock.assert_called in Python < 3.6.
'''
# pylint: disable=unused-import,function-redefined,blacklisted-module,blacklisted-external-module

from __future__ import absolute_import
import errno
import fnmatch
import sys

# Import salt libs
from salt.ext import six
import salt.utils.stringutils

try:
    from mock import (
        Mock,
        MagicMock,
        patch,
        sentinel,
        DEFAULT,
        # ANY and call will be imported further down
        create_autospec,
        FILTER_DIR,
        NonCallableMock,
        NonCallableMagicMock,
        PropertyMock,
        __version__
    )
    NO_MOCK = False
    NO_MOCK_REASON = ''
    mock_version = []
    for __part in __version__.split('.'):
        try:
            mock_version.append(int(__part))
        except ValueError:
            # Non-integer value (ex. '1a')
            mock_version.append(__part)
    mock_version = tuple(mock_version)
except ImportError as exc:
    NO_MOCK = True
    NO_MOCK_REASON = 'mock python module is unavailable'
    mock_version = (0, 0, 0)

    # Let's not fail on imports by providing fake objects and classes

    class MagicMock(object):

        # __name__ can't be assigned a unicode
        __name__ = str('{0}.fakemock').format(__name__)  # future lint: disable=blacklisted-function

        def __init__(self, *args, **kwargs):
            pass

        def dict(self, *args, **kwargs):
            return self

        def multiple(self, *args, **kwargs):
            return self

        def __call__(self, *args, **kwargs):
            return self

    Mock = MagicMock
    patch = MagicMock()
    sentinel = object()
    DEFAULT = object()
    create_autospec = MagicMock()
    FILTER_DIR = True
    NonCallableMock = MagicMock()
    NonCallableMagicMock = MagicMock()
    mock_open = object()
    PropertyMock = object()
    call = tuple
    ANY = object()


if NO_MOCK is False:
    try:
        from mock import call, ANY
    except ImportError:
        NO_MOCK = True
        NO_MOCK_REASON = 'you need to upgrade your mock version to >= 0.8.0'


# backport mock_open from the python 3 unittest.mock library so that we can
# mock read, readline, readlines, and file iteration properly

file_spec = None


def _iterate_read_data(read_data):
    '''
    Helper for mock_open:
    Retrieve lines from read_data via a generator so that separate calls to
    readline, read, and readlines are properly interleaved
    '''
    # Newline will always be a bytestring on PY2 because mock_open will have
    # normalized it to one.
    newline = b'\n' if isinstance(read_data, six.binary_type) else '\n'

    read_data = [line + newline for line in read_data.split(newline)]

    if read_data[-1] == newline:
        # If the last line ended in a newline, the list comprehension will have an
        # extra entry that's just a newline. Remove this.
        read_data = read_data[:-1]
    else:
        # If there wasn't an extra newline by itself, then the file being
        # emulated doesn't have a newline to end the last line, so remove the
        # newline that we added in the list comprehension.
        read_data[-1] = read_data[-1][:-1]

    for line in read_data:
        yield line


def mock_open(mock=None, read_data='', match=None):
    '''
    A helper function to create a mock to replace the use of `open`. It works
    for `open` called directly or used as a context manager.

    The `mock` argument is the mock object to configure. If `None` (the
    default) then a `MagicMock` will be created for you, with the API limited
    to methods or attributes available on standard file handles.

    `read_data` is a string for the `read` methoddline`, and `readlines` of the
    file handle to return.  This is an empty string by default.

    If passed, `match` can be either a string or an iterable containing
    patterns to attempt to match using fnmatch.fnmatch(). A side_effect will be
    added to the mock object returned, which will cause an IOError(2, 'No such
    file or directory') to be raised when the file path is not a match. This
    allows you to make your mocked filehandle only work for certain file paths.
    '''
    # Normalize read_data, Python 2 filehandles should never produce unicode
    # types on read.
    if six.PY2:
        read_data = salt.utils.stringutils.to_str(read_data)

    def _readlines_side_effect(*args, **kwargs):
        if handle.readlines.return_value is not None:
            return handle.readlines.return_value
        return list(_data)

    def _read_side_effect(*args, **kwargs):
        if handle.read.return_value is not None:
            return handle.read.return_value
        joiner = b'' if isinstance(read_data, six.binary_type) else ''
        return joiner.join(_data)

    def _readline_side_effect():
        if handle.readline.return_value is not None:
            while True:
                yield handle.readline.return_value
        for line in _data:
            yield line

    global file_spec
    if file_spec is None:
        if six.PY3:
            import _io
            file_spec = list(set(dir(_io.TextIOWrapper)).union(set(dir(_io.BytesIO))))
        else:
            file_spec = file  # pylint: disable=undefined-variable

    if mock is None:
        mock = MagicMock(name='open', spec=open)

    handle = MagicMock(spec=file_spec)
    handle.__enter__.return_value = handle

    _data = _iterate_read_data(read_data)

    handle.write.return_value = None
    handle.read.return_value = None
    handle.readline.return_value = None
    handle.readlines.return_value = None

    # Support iteration via for loop
    handle.__iter__ = lambda x: _readline_side_effect()

    # This is salt specific and not in the upstream mock
    handle.read.side_effect = _read_side_effect
    handle.readline.side_effect = _readline_side_effect()
    handle.readlines.side_effect = _readlines_side_effect

    if match is not None:
        if isinstance(match, six.string_types):
            match = [match]

        def fopen_side_effect(name, *args, **kwargs):
            for pat in match:
                if fnmatch.fnmatch(name, pat):
                    return DEFAULT
            raise IOError(errno.ENOENT, 'No such file or directory', name)

        mock.side_effect = fopen_side_effect

    mock.return_value = handle
    return mock
