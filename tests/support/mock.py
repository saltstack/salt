# -*- coding: utf-8 -*-
"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)

    tests.support.mock
    ~~~~~~~~~~~~~~~~~~

    Helper module that wraps `mock` and provides some fake objects in order to
    properly set the function/class decorators and yet skip the test case's
    execution.

    Note: mock >= 2.0.0 required since unittest.mock does not have
    MagicMock.assert_called in Python < 3.6.
"""
# pylint: disable=unused-import,function-redefined,blacklisted-module,blacklisted-external-module

from __future__ import absolute_import

import collections
import copy
import errno
import fnmatch
import sys

# By these days, we should blowup if mock is not available
import mock  # pylint: disable=blacklisted-external-import
import salt.utils.stringutils

# pylint: disable=no-name-in-module,no-member
from mock import (
    ANY,
    DEFAULT,
    FILTER_DIR,
    MagicMock,
    Mock,
    NonCallableMagicMock,
    NonCallableMock,
    PropertyMock,
    __version__,
    call,
    create_autospec,
    patch,
    sentinel,
)

# Import salt libs
from salt.ext import six

# pylint: disable=no-name-in-module,no-member


__mock_version = tuple(
    [int(part) for part in mock.__version__.split(".") if part.isdigit()]
)  # pylint: disable=no-member
if sys.version_info < (3, 6) and __mock_version < (2,):
    # We need mock >= 2.0.0 before Py3.6
    raise ImportError("Please install mock>=2.0.0")


class MockFH(object):
    def __init__(self, filename, read_data, *args, **kwargs):
        self.filename = filename
        self.read_data = read_data
        try:
            self.mode = args[0]
        except IndexError:
            self.mode = kwargs.get("mode", "r")
        self.binary_mode = "b" in self.mode
        self.read_mode = any(x in self.mode for x in ("r", "+"))
        self.write_mode = any(x in self.mode for x in ("w", "a", "+"))
        self.empty_string = b"" if self.binary_mode else ""
        self.call = MockCall(filename, *args, **kwargs)
        self.read_data_iter = self._iterate_read_data(read_data)
        self.read = Mock(side_effect=self._read)
        self.readlines = Mock(side_effect=self._readlines)
        self.readline = Mock(side_effect=self._readline)
        self.write = Mock(side_effect=self._write)
        self.writelines = Mock(side_effect=self._writelines)
        self.close = Mock()
        self.seek = Mock()
        self.__loc = 0
        self.__read_data_ok = False

    def _iterate_read_data(self, read_data):
        """
        Helper for mock_open:
        Retrieve lines from read_data via a generator so that separate calls to
        readline, read, and readlines are properly interleaved
        """
        # Newline will always be a bytestring on PY2 because mock_open will have
        # normalized it to one.
        newline = b"\n" if isinstance(read_data, six.binary_type) else "\n"

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
        """
        Return a list of all calls to the .write() mock
        """
        return [x[1][0] for x in self.write.mock_calls]

    @property
    def writelines_calls(self):
        """
        Return a list of all calls to the .writelines() mock
        """
        return [x[1][0] for x in self.writelines.mock_calls]

    def tell(self):
        return self.__loc

    def __check_read_data(self):
        if not self.__read_data_ok:
            if self.binary_mode:
                if not isinstance(self.read_data, six.binary_type):
                    raise TypeError(
                        "{0} opened in binary mode, expected read_data to be "
                        "bytes, not {1}".format(
                            self.filename, type(self.read_data).__name__
                        )
                    )
            else:
                if not isinstance(self.read_data, str):
                    raise TypeError(
                        "{0} opened in non-binary mode, expected read_data to "
                        "be str, not {1}".format(
                            self.filename, type(self.read_data).__name__
                        )
                    )
            # No need to repeat this the next time we check
            self.__read_data_ok = True

    def _read(self, size=0):
        self.__check_read_data()
        if not self.read_mode:
            raise IOError("File not open for reading")
        if not isinstance(size, six.integer_types) or size < 0:
            raise TypeError("a positive integer is required")

        joined = self.empty_string.join(self.read_data_iter)
        if not size:
            # read() called with no args, return everything
            self.__loc += len(joined)
            return joined
        else:
            # read() called with an explicit size. Return a slice matching the
            # requested size, but before doing so, reset read_data to reflect
            # what we read.
            self.read_data_iter = self._iterate_read_data(joined[size:])
            ret = joined[:size]
            self.__loc += len(ret)
            return ret

    def _readlines(self, size=None):  # pylint: disable=unused-argument
        # TODO: Implement "size" argument
        self.__check_read_data()
        if not self.read_mode:
            raise IOError("File not open for reading")
        ret = list(self.read_data_iter)
        self.__loc += sum(len(x) for x in ret)
        return ret

    def _readline(self, size=None):  # pylint: disable=unused-argument
        # TODO: Implement "size" argument
        self.__check_read_data()
        if not self.read_mode:
            raise IOError("File not open for reading")
        try:
            ret = next(self.read_data_iter)
            self.__loc += len(ret)
            return ret
        except StopIteration:
            return self.empty_string

    def __iter__(self):
        self.__check_read_data()
        if not self.read_mode:
            raise IOError("File not open for reading")
        while True:
            try:
                ret = next(self.read_data_iter)
                self.__loc += len(ret)
                yield ret
            except StopIteration:
                break

    def _write(self, content):
        if not self.write_mode:
            raise IOError("File not open for writing")
        if six.PY2:
            if isinstance(content, six.text_type):
                # encoding intentionally not specified to force a
                # UnicodeEncodeError when non-ascii unicode type is passed
                content.encode()
        else:
            content_type = type(content)
            if self.binary_mode and content_type is not bytes:
                raise TypeError(
                    "a bytes-like object is required, not '{0}'".format(
                        content_type.__name__
                    )
                )
            elif not self.binary_mode and content_type is not str:
                raise TypeError(
                    "write() argument must be str, not {0}".format(
                        content_type.__name__
                    )
                )

    def _writelines(self, lines):
        if not self.write_mode:
            raise IOError("File not open for writing")
        for line in lines:
            self._write(line)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # pylint: disable=unused-argument
        pass


class MockCall(object):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __repr__(self):
        # future lint: disable=blacklisted-function
        ret = str("MockCall(")
        for arg in self.args:
            ret += repr(arg) + str(", ")
        if not self.kwargs:
            if self.args:
                # Remove trailing ', '
                ret = ret[:-2]
        else:
            for key, val in six.iteritems(self.kwargs):
                ret += str("{0}={1}").format(
                    salt.utils.stringutils.to_str(key), repr(val)
                )
        ret += str(")")
        return ret
        # future lint: enable=blacklisted-function

    def __str__(self):
        return self.__repr__()

    def __eq__(self, other):
        return self.args == other.args and self.kwargs == other.kwargs


class MockOpen(object):
    r'''
    This class can be used to mock the use of ``open()``.

    ``read_data`` is a string representing the contents of the file to be read.
    By default, this is an empty string.

    Optionally, ``read_data`` can be a dictionary mapping ``fnmatch.fnmatch()``
    patterns to strings (or optionally, exceptions). This allows the mocked
    filehandle to serve content for more than one file path.

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

    Passing ``read_data`` as a string is equivalent to passing it with a glob
    expression of "*". That is to say, the below two invocations are
    equivalent:

    .. code-block:: python

        mock_open(read_data='foo\n')
        mock_open(read_data={'*': 'foo\n'})

    Instead of a string representing file contents, ``read_data`` can map to an
    exception, and that exception will be raised if a file matching that
    pattern is opened:

    .. code-block:: python

        data = {
            '/etc/*': IOError(errno.EACCES, 'Permission denied'),
            '*': 'Hello world!\n',
        }
        with patch('salt.utils.files.fopen', mock_open(read_data=data)):
            do stuff

    The above would raise an exception if any files within /etc are opened, but
    would produce a mocked filehandle if any other file is opened.

    To simulate file contents changing upon subsequent opens, the file contents
    can be a list of strings/exceptions. For example:

    .. code-block:: python

        data = {
            '/etc/foo.conf': [
                'before\n',
                'after\n',
            ],
            '/etc/bar.conf': [
                IOError(errno.ENOENT, 'No such file or directory', '/etc/bar.conf'),
                'Hey, the file exists now!',
            ],
        }
        with patch('salt.utils.files.fopen', mock_open(read_data=data):
            do stuff

    The first open of ``/etc/foo.conf`` would return "before\n" when read,
    while the second would return "after\n" when read. For ``/etc/bar.conf``,
    the first read would raise an exception, while the second would open
    successfully and read the specified string.

    Expressions will be attempted in dictionary iteration order (the exception
    being ``*`` which is tried last), so if a file path matches more than one
    fnmatch expression then the first match "wins". If your use case calls for
    overlapping expressions, then an OrderedDict can be used to ensure that the
    desired matching behavior occurs:

    .. code-block:: python

        data = OrderedDict()
        data['/etc/foo.conf'] = 'Permission granted!'
        data['/etc/*'] = IOError(errno.EACCES, 'Permission denied')
        data['*'] = '*': 'Hello world!\n'
        with patch('salt.utils.files.fopen', mock_open(read_data=data):
            do stuff

    The following attributes are tracked for the life of a mock object:

    * call_count - Tracks how many fopen calls were attempted
    * filehandles - This is a dictionary mapping filenames to lists of MockFH
      objects, representing the individual times that a given file was opened.
    '''

    def __init__(self, read_data=""):
        # If the read_data contains lists, we will be popping it. So, don't
        # modify the original value passed.
        read_data = copy.copy(read_data)

        # Normalize read_data, Python 2 filehandles should never produce unicode
        # types on read.
        if not isinstance(read_data, dict):
            read_data = {"*": read_data}

        if six.PY2:
            # .__class__() used here to preserve the dict class in the event that
            # an OrderedDict was used.
            new_read_data = read_data.__class__()
            for key, val in six.iteritems(read_data):
                try:
                    val = salt.utils.data.decode(val, to_str=True)
                except TypeError:
                    if not isinstance(val, BaseException):
                        raise
                new_read_data[key] = val

            read_data = new_read_data
            del new_read_data

        self.read_data = read_data
        self.filehandles = {}
        self.calls = []
        self.call_count = 0

    def __call__(self, name, *args, **kwargs):
        """
        Match the file being opened to the patterns in the read_data and spawn
        a mocked filehandle with the corresponding file contents.
        """
        call = MockCall(name, *args, **kwargs)
        self.calls.append(call)
        self.call_count += 1
        for pat in self.read_data:
            if pat == "*":
                continue
            if fnmatch.fnmatch(name, pat):
                matched_pattern = pat
                break
        else:
            # No non-glob match in read_data, fall back to '*'
            matched_pattern = "*"
        try:
            matched_contents = self.read_data[matched_pattern]
            try:
                # Assuming that the value for the matching expression is a
                # list, pop the first element off of it.
                file_contents = matched_contents.pop(0)
            except AttributeError:
                # The value for the matching expression is a string (or exception)
                file_contents = matched_contents
            except IndexError:
                # We've run out of file contents, abort!
                raise RuntimeError(
                    "File matching expression '{0}' opened more times than "
                    "expected".format(matched_pattern)
                )

            try:
                # Raise the exception if the matched file contents are an
                # instance of an exception class.
                raise file_contents
            except TypeError:
                # Contents were not an exception, so proceed with creating the
                # mocked filehandle.
                pass

            ret = MockFH(name, file_contents, *args, **kwargs)
            self.filehandles.setdefault(name, []).append(ret)
            return ret
        except KeyError:
            # No matching glob in read_data, treat this as a file that does
            # not exist and raise the appropriate exception.
            raise IOError(errno.ENOENT, "No such file or directory", name)

    def write_calls(self, path=None):
        """
        Returns the contents passed to all .write() calls. Use `path` to narrow
        the results to files matching a given pattern.
        """
        ret = []
        for filename, handles in six.iteritems(self.filehandles):
            if path is None or fnmatch.fnmatch(filename, path):
                for fh_ in handles:
                    ret.extend(fh_.write_calls)
        return ret

    def writelines_calls(self, path=None):
        """
        Returns the contents passed to all .writelines() calls. Use `path` to
        narrow the results to files matching a given pattern.
        """
        ret = []
        for filename, handles in six.iteritems(self.filehandles):
            if path is None or fnmatch.fnmatch(filename, path):
                for fh_ in handles:
                    ret.extend(fh_.writelines_calls)
        return ret


# reimplement mock_open to support multiple filehandles
mock_open = MockOpen
