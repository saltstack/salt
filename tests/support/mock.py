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


class MockFH(object):
    def __init__(self, filename, read_data):
        self.filename = filename
        self.empty_string = b'' if isinstance(read_data, six.binary_type) else ''
        self.read_data = self._iterate_read_data(read_data)
        self.read = Mock(side_effect=self._read)
        self.readlines = Mock(side_effect=self._readlines)
        self.readline = Mock(side_effect=self._readline)
        self.close = Mock()
        self.write = Mock()
        self.writelines = Mock()

    def _iterate_read_data(self, read_data):
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

    @property
    def write_calls(self):
        '''
        Return a list of all calls to the .write() mock
        '''
        return [x[1][0] for x in self.write.mock_calls]

    @property
    def writelines_calls(self):
        '''
        Return a list of all calls to the .writelines() mock
        '''
        return [x[1][0] for x in self.writelines.mock_calls]

    def _read(self, size=0):
        if not isinstance(size, six.integer_types) or size < 0:
            raise TypeError('a positive integer is required')

        joined = self.empty_string.join(self.read_data)
        if not size:
            # read() called with no args, return everything
            return joined
        else:
            # read() called with an explicit size. Return a slice matching the
            # requested size, but before doing so, reset read_data to reflect
            # what we read.
            self.read_data = self._iterate_read_data(joined[size:])
            return joined[:size]

    def _readlines(self, size=None):  # pylint: disable=unused-argument
        # TODO: Implement "size" argument
        return list(self.read_data)

    def _readline(self, size=None):  # pylint: disable=unused-argument
        # TODO: Implement "size" argument
        try:
            return next(self.read_data)
        except StopIteration:
            return self.empty_string

    def __iter__(self):
        while True:
            try:
                yield next(self.read_data)
            except StopIteration:
                break

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # pylint: disable=unused-argument
        pass


# reimplement mock_open to support multiple filehandles
def mock_open(read_data=''):
    '''
    A helper function to create a mock to replace the use of `open`. It works
    for "open" called directly or used as a context manager.

    The "mock" argument is the mock object to configure. If "None" (the
    default) then a "MagicMock" will be created for you, with the API limited
    to methods or attributes available on standard file handles.

    "read_data" is a string representing the contents of the file to be read.
    By default, this is an empty string.

    Optionally, "read_data" can be a dictionary mapping fnmatch.fnmatch()
    patterns to strings. This allows the mocked filehandle to serve content for
    more than one file path.

    .. code-block:: python

        data = {
            '/etc/foo.conf': textwrap.dedent("""\
                Foo
                Bar
                Baz
                """),
            '/etc/bar.conf': textwrap.dedent("""\
                A
                B
                C
                """),
        }
        with patch('salt.utils.files.fopen', mock_open(read_data=data):
            do stuff

    If the file path being opened does not match any of the glob expressions,
    an IOError will be raised to simulate the file not existing.

    Glob expressions will be attempted in iteration order, so if a file path
    matches more than one glob expression it will match whichever is iterated
    first. If a specifc iteration order is desired (and you are not running
    Python >= 3.6), consider passing "read_data" as an OrderedDict.

    Passing "read_data" as a string is equivalent to passing it with a glob
    expression of "*".
    '''
    # Normalize read_data, Python 2 filehandles should never produce unicode
    # types on read.
    if not isinstance(read_data, dict):
        read_data = {'*': read_data}

    if six.PY2:
        # .__class__() used here to preserve the dict class in the event that
        # an OrderedDict was used.
        new_read_data = read_data.__class__()
        for key, val in six.iteritems(read_data):
            try:
                val = salt.utils.stringutils.to_str(val)
            except TypeError:
                if not isinstance(val, BaseException):
                    raise
            new_read_data[key] = val

        read_data = new_read_data
        del new_read_data

    mock = MagicMock(name='open', spec=open)
    mock.handles = {}

    def _fopen_side_effect(name, *args, **kwargs):
        for pat in read_data:
            if pat == '*':
                continue
            if fnmatch.fnmatch(name, pat):
                matched_pattern = pat
                break
        else:
            # No non-glob match in read_data, fall back to '*'
            matched_pattern = '*'
        try:
            file_contents = read_data[matched_pattern]
            try:
                # Raise the exception if the matched file contents are an
                # instance of an exception class.
                raise file_contents
            except TypeError:
                # Contents were not an exception, so proceed with creating the
                # mocked filehandle.
                pass
            ret = MockFH(name, file_contents)
            mock.handles.setdefault(name, []).append(ret)
            return ret
        except KeyError:
            # No matching glob in read_data, treat this as a file that does
            # not exist and raise the appropriate exception.
            raise IOError(errno.ENOENT, 'No such file or directory', name)

    mock.side_effect = _fopen_side_effect
    return mock
