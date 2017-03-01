# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`

    tests.support.mock
    ~~~~~~~~~~~~~~~~~~

    Helper module that wraps :mod:`mock <python3:unittest.mock>` and provides
    some fake objects in order to properly set the function/class decorators
    and yet skip the test cases execution.
'''
# pylint: disable=unused-import,function-redefined

from __future__ import absolute_import
import sys

try:
    if sys.version_info >= (3,):
        # Python 3
        from unittest.mock import (
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
            __version__ as __mock_version
        )
    else:
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
            __version__ as __mock_version
        )
    NO_MOCK = False
    NO_MOCK_REASON = ''
    mock_version = []
    for __part in __mock_version.split('.'):
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

        __name__ = '{0}.fakemock'.format(__name__)

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
        if sys.version_info >= (3,):
            # Python 3
            from unittest.mock import call, ANY
        else:
            from mock import call, ANY
    except ImportError:
        NO_MOCK = True
        NO_MOCK_REASON = 'you need to upgrade your mock version to >= 0.8.0'


if sys.version_info >= (3,):
    from mock import mock_open
else:
    # backport mock_open from the python 3 unittest.mock library so that we can
    # mock read, readline, readlines, and file iteration properly

    file_spec = None

    def _iterate_read_data(read_data):
        # Helper for mock_open:
        # Retrieve lines from read_data via a generator so that separate calls to
        # readline, read, and readlines are properly interleaved
        data_as_list = ['{0}\n'.format(l) for l in read_data.split('\n')]

        if data_as_list[-1] == '\n':
            # If the last line ended in a newline, the list comprehension will have an
            # extra entry that's just a newline.  Remove this.
            data_as_list = data_as_list[:-1]
        else:
            # If there wasn't an extra newline by itself, then the file being
            # emulated doesn't have a newline to end the last line  remove the
            # newline that our naive format() added
            data_as_list[-1] = data_as_list[-1][:-1]

        for line in data_as_list:
            yield line

    def mock_open(mock=None, read_data=''):
        """
        A helper function to create a mock to replace the use of `open`. It works
        for `open` called directly or used as a context manager.

        The `mock` argument is the mock object to configure. If `None` (the
        default) then a `MagicMock` will be created for you, with the API limited
        to methods or attributes available on standard file handles.

        `read_data` is a string for the `read` methoddline`, and `readlines` of the
        file handle to return.  This is an empty string by default.
        """
        def _readlines_side_effect(*args, **kwargs):
            if handle.readlines.return_value is not None:
                return handle.readlines.return_value
            return list(_data)

        def _read_side_effect(*args, **kwargs):
            if handle.read.return_value is not None:
                return handle.read.return_value
            return ''.join(_data)

        def _readline_side_effect():
            if handle.readline.return_value is not None:
                while True:
                    yield handle.readline.return_value
            for line in _data:
                yield line

        global file_spec
        if file_spec is None:
            file_spec = file

        if mock is None:
            mock = MagicMock(name='open', spec=open)

        handle = MagicMock(spec=file_spec)
        handle.__enter__.return_value = handle

        _data = _iterate_read_data(read_data)

        handle.write.return_value = None
        handle.read.return_value = None
        handle.readline.return_value = None
        handle.readlines.return_value = None

        handle.read.side_effect = _read_side_effect
        handle.readline.side_effect = _readline_side_effect()
        handle.readlines.side_effect = _readlines_side_effect

        mock.return_value = handle
        return mock
