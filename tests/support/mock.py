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


def mock_open(mock=None, read_data=''):
    '''
    A helper function to create a mock to replace the use of `open`. It works
    for "open" called directly or used as a context manager.

    The "mock" argument is the mock object to configure. If "None" (the
    default) then a "MagicMock" will be created for you, with the API limited
    to methods or attributes available on standard file handles.

    "read_data" is a string representing the contents of the file to be read.
    By default, this is an empty string.

    Optionally, `read_data` can be a dictionary mapping fnmatch.fnmatch()
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

    If the file path being opened does not match the glob expression, an
    IOError will be raised to simulate the file not existing.

    Glob expressions will be attempted in iteration order, so if a file path
    matches more than one glob expression it will match whichever is iterated
    first.

    Passing "read_data" as a string is equivalent to passing it with a glob
    expression of "*".
    '''
    # Normalize read_data, Python 2 filehandles should never produce unicode
    # types on read.
    if not isinstance(read_data, dict):
        read_data = {'*': read_data}

    if six.PY2:
        read_data = {x: salt.utils.stringutils.to_str(y)
                     for x, y in six.iteritems(read_data)}

    global file_spec
    if file_spec is None:
        if six.PY3:
            import _io
            file_spec = list(set(dir(_io.TextIOWrapper)).union(set(dir(_io.BytesIO))))
        else:
            file_spec = file  # pylint: disable=undefined-variable

    if mock is None:
        mock = MagicMock(name='open', spec=open)

    # We're using a dict here so that we can access both the mock object and
    # the generator from the closures below. This also allows us to replace the
    # genreator with an updated one after we've read from it, which allows
    # the mocked read funcs to more closely emulate an actual filehandle. The
    # .__class__() function is used to preserve the dict class, in case
    # read_data is an OrderedDict.
    data = {
        'filehandle': read_data.__class__(),
        'mock': mock,
    }

    def _filename(data):
        return data['mock'].call_args[0][0]

    def _match_glob(filename):
        for key in read_data:
            if key == '*':
                continue
            if fnmatch.fnmatch(filename, key):
                return key
        return '*'

    def _match_fn(data):
        filename = _filename(data)
        try:
            return data['glob_map'][filename]
        except KeyError:
            data.setdefault('glob_map', {})[filename] = _match_glob(filename)
            return data['glob_map'][filename]

    def _empty_string(data):
        filename = _filename(data)
        try:
            return data['empty_string'][filename]
        except KeyError:
            data.setdefault('empty_string', {})[filename] = (
                b'' if isinstance(read_data[_match_fn(data)], six.binary_type)
                else ''
            )
            return data['empty_string'][filename]

    def _readlines_side_effect(*args, **kwargs):
        filename = _filename(data)
        ret = list(data['filehandle'][filename])
        # We've read everything in the file. Clear its contents so that further
        # reads behave as expected.
        data['filehandle'][filename] = _iterate_read_data('')
        return ret

    def _read_side_effect(*args, **kwargs):
        filename = _filename(data)
        joined = _empty_string(data).join(data['filehandle'][filename])
        if not args:
            # read() called with no args, we want to return everything. If
            # anything was in the generator, clear it
            if joined:
                # If there were any contents, clear them
                data['filehandle'][filename] = _iterate_read_data('')
            return joined
        else:
            # read() called with an explicit size. Return a slice matching the
            # requested size, but before doing so, reset data to reflect what
            # we read.
            size = args[0]
            if not isinstance(size, six.integer_types):
                raise TypeError('an integer is required')
            data['filehandle'][filename] = _iterate_read_data(joined[size:])
            return joined[:size]

    def _readline_side_effect():
        filename = _filename(data)
        try:
            return next(data['filehandle'][filename])
        except StopIteration:
            return _empty_string(data)

    def _iter_side_effect():
        filename = _filename(data)
        while True:
            try:
                yield next(data['filehandle'][filename])
            except StopIteration:
                break

    def _fopen_side_effect(name, *args, **kwargs):
        key = _match_glob(name)
        try:
            data['filehandle'][name] = _iterate_read_data(read_data[key])
            return DEFAULT
        except KeyError:
            # No matching glob in read_data, treat this as a file that does
            # not exist and raise the appropriate exception.
            raise IOError(errno.ENOENT, 'No such file or directory', name)

    handle = MagicMock(spec=file_spec)
    handle.__enter__.return_value = handle

    handle.write.return_value = None
    handle.read.return_value = None
    handle.readline.return_value = None
    handle.readlines.return_value = None

    # Support iteration via for loop
    handle.__iter__ = lambda x: _iter_side_effect()

    # This is salt specific and not in the upstream mock
    handle.read.side_effect = _read_side_effect
    handle.readline.side_effect = _readline_side_effect
    handle.readlines.side_effect = _readlines_side_effect

    mock.side_effect = _fopen_side_effect

    mock.return_value = handle
    return mock
