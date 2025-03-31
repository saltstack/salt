"""
Tests for our mock_open helper
"""

import errno
import logging
import textwrap

import salt.utils.data
import salt.utils.files
import salt.utils.stringutils
from tests.support.mock import mock_open, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class MockOpenMixin:
    def _get_values(self, binary=False, multifile=False, split=False):
        if split:
            questions = (
                self.questions_bytes_lines if binary else self.questions_str_lines
            )
            answers = self.answers_bytes_lines if binary else self.answers_str_lines
        else:
            questions = self.questions_bytes if binary else self.questions_str
            answers = self.answers_bytes if binary else self.answers_str
        mode = "rb" if binary else "r"
        if multifile:
            read_data = self.contents_bytes if binary else self.contents
        else:
            read_data = self.questions_bytes if binary else self.questions
        return questions, answers, mode, read_data

    def _test_read(self, binary=False, multifile=False):
        questions, answers, mode, read_data = self._get_values(
            binary=binary, multifile=multifile
        )

        with patch("salt.utils.files.fopen", mock_open(read_data=read_data)):
            with salt.utils.files.fopen("foo.txt", mode) as self.fh:
                result = self.fh.read()
                assert result == questions, result

            if multifile:
                with salt.utils.files.fopen("bar.txt", mode) as self.fh2:
                    result = self.fh2.read()
                    assert result == answers, result

                with salt.utils.files.fopen("baz.txt", mode) as self.fh3:
                    result = self.fh3.read()
                    assert result == answers, result

                try:
                    with salt.utils.files.fopen("helloworld.txt"):
                        raise Exception("No patterns should have matched")
                except OSError:
                    # An IOError is expected here
                    pass

    def _test_read_explicit_size(self, binary=False, multifile=False):
        questions, answers, mode, read_data = self._get_values(
            binary=binary, multifile=multifile
        )

        with patch("salt.utils.files.fopen", mock_open(read_data=read_data)):
            with salt.utils.files.fopen("foo.txt", mode) as self.fh:
                # Read 10 bytes
                result = self.fh.read(10)
                assert result == questions[:10], result
                # Read another 10 bytes
                result = self.fh.read(10)
                assert result == questions[10:20], result
                # Read the rest
                result = self.fh.read()
                assert result == questions[20:], result

            if multifile:
                with salt.utils.files.fopen("bar.txt", mode) as self.fh2:
                    # Read 10 bytes
                    result = self.fh2.read(10)
                    assert result == answers[:10], result
                    # Read another 10 bytes
                    result = self.fh2.read(10)
                    assert result == answers[10:20], result
                    # Read the rest
                    result = self.fh2.read()
                    assert result == answers[20:], result

                with salt.utils.files.fopen("baz.txt", mode) as self.fh3:
                    # Read 10 bytes
                    result = self.fh3.read(10)
                    assert result == answers[:10], result
                    # Read another 10 bytes
                    result = self.fh3.read(10)
                    assert result == answers[10:20], result
                    # Read the rest
                    result = self.fh3.read()
                    assert result == answers[20:], result

                try:
                    with salt.utils.files.fopen("helloworld.txt"):
                        raise Exception("No globs should have matched")
                except OSError:
                    # An IOError is expected here
                    pass

    def _test_read_explicit_size_larger_than_file_size(
        self, binary=False, multifile=False
    ):
        questions, answers, mode, read_data = self._get_values(
            binary=binary, multifile=multifile
        )

        with patch("salt.utils.files.fopen", mock_open(read_data=read_data)):
            with salt.utils.files.fopen("foo.txt", mode) as self.fh:
                result = self.fh.read(999999)
                assert result == questions, result

            if multifile:
                with salt.utils.files.fopen("bar.txt", mode) as self.fh2:
                    result = self.fh2.read(999999)
                    assert result == answers, result

                with salt.utils.files.fopen("baz.txt", mode) as self.fh3:
                    result = self.fh3.read(999999)
                    assert result == answers, result

                try:
                    with salt.utils.files.fopen("helloworld.txt"):
                        raise Exception("No globs should have matched")
                except OSError:
                    # An IOError is expected here
                    pass

    def _test_read_for_loop(self, binary=False, multifile=False):
        questions, answers, mode, read_data = self._get_values(
            binary=binary, multifile=multifile, split=True
        )

        with patch("salt.utils.files.fopen", mock_open(read_data=read_data)):
            with salt.utils.files.fopen("foo.txt", mode) as self.fh:
                index = 0
                for line in self.fh:
                    assert line == questions[index], f"Line {index}: {line}"
                    index += 1

            if multifile:
                with salt.utils.files.fopen("bar.txt", mode) as self.fh2:
                    index = 0
                    for line in self.fh2:
                        assert line == answers[index], f"Line {index}: {line}"
                        index += 1

                with salt.utils.files.fopen("baz.txt", mode) as self.fh3:
                    index = 0
                    for line in self.fh3:
                        assert line == answers[index], f"Line {index}: {line}"
                        index += 1

                try:
                    with salt.utils.files.fopen("helloworld.txt"):
                        raise Exception("No globs should have matched")
                except OSError:
                    # An IOError is expected here
                    pass

    def _test_read_readline(self, binary=False, multifile=False):
        questions, answers, mode, read_data = self._get_values(
            binary=binary, multifile=multifile, split=True
        )

        with patch("salt.utils.files.fopen", mock_open(read_data=read_data)):
            with salt.utils.files.fopen("foo.txt", mode) as self.fh:
                size = 8
                result = self.fh.read(size)
                assert result == questions[0][:size], result
                # Use .readline() to read the remainder of the line
                result = self.fh.readline()
                assert result == questions[0][size:], result
                # Read and check the other two lines
                result = self.fh.readline()
                assert result == questions[1], result
                result = self.fh.readline()
                assert result == questions[2], result

            if multifile:
                with salt.utils.files.fopen("bar.txt", mode) as self.fh2:
                    size = 20
                    result = self.fh2.read(size)
                    assert result == answers[0][:size], result
                    # Use .readline() to read the remainder of the line
                    result = self.fh2.readline()
                    assert result == answers[0][size:], result
                    # Read and check the other two lines
                    result = self.fh2.readline()
                    assert result == answers[1], result
                    result = self.fh2.readline()
                    assert result == answers[2], result

                with salt.utils.files.fopen("baz.txt", mode) as self.fh3:
                    size = 20
                    result = self.fh3.read(size)
                    assert result == answers[0][:size], result
                    # Use .readline() to read the remainder of the line
                    result = self.fh3.readline()
                    assert result == answers[0][size:], result
                    # Read and check the other two lines
                    result = self.fh3.readline()
                    assert result == answers[1], result
                    result = self.fh3.readline()
                    assert result == answers[2], result

                try:
                    with salt.utils.files.fopen("helloworld.txt"):
                        raise Exception("No globs should have matched")
                except OSError:
                    # An IOError is expected here
                    pass

    def _test_readline_readlines(self, binary=False, multifile=False):
        questions, answers, mode, read_data = self._get_values(
            binary=binary, multifile=multifile, split=True
        )

        with patch("salt.utils.files.fopen", mock_open(read_data=read_data)):
            with salt.utils.files.fopen("foo.txt", mode) as self.fh:
                # Read the first line
                result = self.fh.readline()
                assert result == questions[0], result
                # Use .readlines() to read the remainder of the file
                result = self.fh.readlines()
                assert result == questions[1:], result

            if multifile:
                with salt.utils.files.fopen("bar.txt", mode) as self.fh2:
                    # Read the first line
                    result = self.fh2.readline()
                    assert result == answers[0], result
                    # Use .readlines() to read the remainder of the file
                    result = self.fh2.readlines()
                    assert result == answers[1:], result

                with salt.utils.files.fopen("baz.txt", mode) as self.fh3:
                    # Read the first line
                    result = self.fh3.readline()
                    assert result == answers[0], result
                    # Use .readlines() to read the remainder of the file
                    result = self.fh3.readlines()
                    assert result == answers[1:], result

                try:
                    with salt.utils.files.fopen("helloworld.txt"):
                        raise Exception("No globs should have matched")
                except OSError:
                    # An IOError is expected here
                    pass

    def _test_readlines_multifile(self, binary=False, multifile=False):
        questions, answers, mode, read_data = self._get_values(
            binary=binary, multifile=multifile, split=True
        )

        with patch("salt.utils.files.fopen", mock_open(read_data=read_data)):
            with salt.utils.files.fopen("foo.txt", mode) as self.fh:
                result = self.fh.readlines()
                assert result == questions, result

            if multifile:
                with salt.utils.files.fopen("bar.txt", mode) as self.fh2:
                    result = self.fh2.readlines()
                    assert result == answers, result

                with salt.utils.files.fopen("baz.txt", mode) as self.fh3:
                    result = self.fh3.readlines()
                    assert result == answers, result

                try:
                    with salt.utils.files.fopen("helloworld.txt"):
                        raise Exception("No globs should have matched")
                except OSError:
                    # An IOError is expected here
                    pass


class MockOpenTestCase(TestCase, MockOpenMixin):
    """
    Tests for our mock_open helper to ensure that it behaves as closely as
    possible to a real filehandle.
    """

    # Cyrllic characters used to test unicode handling
    questions = textwrap.dedent(
        """\
        Шнат is your name?
        Шнат is your quest?
        Шнат is the airspeed velocity of an unladen swallow?
        """
    )

    answers = textwrap.dedent(
        """\
        It is Аятнця, King of the Britons.
        To seek тне Holy Grail.
        Шнат do you mean? An African or European swallow?
        """
    )

    @classmethod
    def setUpClass(cls):
        cls.questions_lines = cls.questions.splitlines(True)
        cls.answers_lines = cls.answers.splitlines(True)

        cls.questions_str = salt.utils.stringutils.to_str(cls.questions)
        cls.answers_str = salt.utils.stringutils.to_str(cls.answers)
        cls.questions_str_lines = cls.questions_str.splitlines(True)
        cls.answers_str_lines = cls.answers_str.splitlines(True)

        cls.questions_bytes = salt.utils.stringutils.to_bytes(cls.questions)
        cls.answers_bytes = salt.utils.stringutils.to_bytes(cls.answers)
        cls.questions_bytes_lines = cls.questions_bytes.splitlines(True)
        cls.answers_bytes_lines = cls.answers_bytes.splitlines(True)

        # When this is used as the read_data, Python 2 should normalize
        # cls.questions and cls.answers to str types.
        cls.contents = {"foo.txt": cls.questions, "b*.txt": cls.answers}
        cls.contents_bytes = {
            "foo.txt": cls.questions_bytes,
            "b*.txt": cls.answers_bytes,
        }

        cls.read_data_as_list = [
            "foo",
            "bar",
            "спам",
            IOError(errno.EACCES, "Permission denied"),
        ]
        cls.normalized_read_data_as_list = salt.utils.data.decode(
            cls.read_data_as_list, to_str=True
        )
        cls.read_data_as_list_bytes = salt.utils.data.encode(cls.read_data_as_list)

    def tearDown(self):
        """
        Each test should read the entire contents of the mocked filehandle(s).
        This confirms that the other read functions return empty strings/lists,
        to simulate being at EOF.
        """
        for handle_name in ("fh", "fh2", "fh3"):
            try:
                fh = getattr(self, handle_name)
            except AttributeError:
                continue
            log.debug("Running tearDown tests for self.%s", handle_name)
            try:
                result = fh.read(5)
                assert not result, result
                result = fh.read()
                assert not result, result
                result = fh.readline()
                assert not result, result
                result = fh.readlines()
                assert not result, result
                # Last but not least, try to read using a for loop. This should not
                # read anything as we should hit EOF immediately, before the generator
                # in the mocked filehandle has a chance to yield anything. So the
                # exception will only be raised if we aren't at EOF already.
                for line in fh:
                    raise Exception(
                        "Instead of EOF, read the following from {}: {}".format(
                            handle_name, line
                        )
                    )
            except OSError as exc:
                if str(exc) != "File not open for reading":
                    raise
            del fh

    def test_read(self):
        """
        Test reading the entire file
        """
        self._test_read(binary=False, multifile=False)
        self._test_read(binary=True, multifile=False)
        self._test_read(binary=False, multifile=True)
        self._test_read(binary=True, multifile=True)

    def test_read_explicit_size(self):
        """
        Test reading with explicit sizes
        """
        self._test_read_explicit_size(binary=False, multifile=False)
        self._test_read_explicit_size(binary=True, multifile=False)
        self._test_read_explicit_size(binary=False, multifile=True)
        self._test_read_explicit_size(binary=True, multifile=True)

    def test_read_explicit_size_larger_than_file_size(self):
        """
        Test reading with an explicit size larger than the size of read_data.
        This ensures that we just return the contents up until EOF and that we
        don't raise any errors due to the desired size being larger than the
        mocked file's size.
        """
        self._test_read_explicit_size_larger_than_file_size(
            binary=False, multifile=False
        )
        self._test_read_explicit_size_larger_than_file_size(
            binary=True, multifile=False
        )
        self._test_read_explicit_size_larger_than_file_size(
            binary=False, multifile=True
        )
        self._test_read_explicit_size_larger_than_file_size(binary=True, multifile=True)

    def test_read_for_loop(self):
        """
        Test reading the contents of the file line by line in a for loop
        """
        self._test_read_for_loop(binary=False, multifile=False)
        self._test_read_for_loop(binary=True, multifile=False)
        self._test_read_for_loop(binary=False, multifile=True)
        self._test_read_for_loop(binary=True, multifile=True)

    def test_read_readline(self):
        """
        Test reading part of a line using .read(), then reading the rest of the
        line (and subsequent lines) using .readline().
        """
        self._test_read_readline(binary=False, multifile=False)
        self._test_read_readline(binary=True, multifile=False)
        self._test_read_readline(binary=False, multifile=True)
        self._test_read_readline(binary=True, multifile=True)

    def test_readline_readlines(self):
        """
        Test reading the first line using .readline(), then reading the rest of
        the file using .readlines().
        """
        self._test_readline_readlines(binary=False, multifile=False)
        self._test_readline_readlines(binary=True, multifile=False)
        self._test_readline_readlines(binary=False, multifile=True)
        self._test_readline_readlines(binary=True, multifile=True)

    def test_readlines(self):
        """
        Test reading the entire file using .readlines
        """
        self._test_readlines_multifile(binary=False, multifile=False)
        self._test_readlines_multifile(binary=True, multifile=False)
        self._test_readlines_multifile(binary=False, multifile=True)
        self._test_readlines_multifile(binary=True, multifile=True)

    def test_read_data_converted_to_dict(self):
        """
        Test that a non-dict value for read_data is converted to a dict mapping
        '*' to that value.
        """
        contents = "спам"
        normalized = salt.utils.stringutils.to_str(contents)
        with patch("salt.utils.files.fopen", mock_open(read_data=contents)) as m_open:
            assert m_open.read_data == {"*": normalized}, m_open.read_data

        with patch(
            "salt.utils.files.fopen", mock_open(read_data=self.read_data_as_list)
        ) as m_open:
            assert m_open.read_data == {
                "*": self.normalized_read_data_as_list,
            }, m_open.read_data

    def test_read_data_list(self):
        """
        Test read_data when it is a list
        """
        with patch(
            "salt.utils.files.fopen", mock_open(read_data=self.read_data_as_list)
        ):
            for value in self.normalized_read_data_as_list:
                try:
                    with salt.utils.files.fopen("foo.txt") as self.fh:
                        result = self.fh.read()
                        assert result == value, result
                except OSError:
                    # Only raise the caught exception if it wasn't expected
                    # (i.e. if value is not an exception)
                    if not isinstance(value, IOError):
                        raise

    def test_read_data_list_bytes(self):
        """
        Test read_data when it is a list and the value is a bytestring
        """
        with patch(
            "salt.utils.files.fopen", mock_open(read_data=self.read_data_as_list_bytes)
        ):
            for value in self.read_data_as_list_bytes:
                try:
                    with salt.utils.files.fopen("foo.txt", "rb") as self.fh:
                        result = self.fh.read()
                        assert result == value, result
                except OSError:
                    # Only raise the caught exception if it wasn't expected
                    # (i.e. if value is not an exception)
                    if not isinstance(value, IOError):
                        raise

    def test_tell(self):
        """
        Test the implementation of tell
        """
        with patch("salt.utils.files.fopen", mock_open(read_data=self.contents)):
            # Try with reading explicit sizes and then reading the rest of the
            # file.
            with salt.utils.files.fopen("foo.txt") as self.fh:
                self.fh.read(5)
                loc = self.fh.tell()
                assert loc == 5, loc
                self.fh.read(12)
                loc = self.fh.tell()
                assert loc == 17, loc
                self.fh.read()
                loc = self.fh.tell()
                assert loc == len(self.questions_str), loc

            # Try reading way more content then actually exists in the file,
            # tell() should return a value equal to the length of the content
            with salt.utils.files.fopen("foo.txt") as self.fh:
                self.fh.read(999999)
                loc = self.fh.tell()
                assert loc == len(self.questions_str), loc

            # Try reading a few bytes using .read(), then the rest of the line
            # using .readline(), then the rest of the file using .readlines(),
            # and check the location after each read.
            with salt.utils.files.fopen("foo.txt") as self.fh:
                # Read a few bytes
                self.fh.read(5)
                loc = self.fh.tell()
                assert loc == 5, loc
                # Read the rest of the line. Location should then be at the end
                # of the first line.
                self.fh.readline()
                loc = self.fh.tell()
                assert loc == len(self.questions_str_lines[0]), loc
                # Read the rest of the file using .readlines()
                self.fh.readlines()
                loc = self.fh.tell()
                assert loc == len(self.questions_str), loc

            # Check location while iterating through the filehandle
            with salt.utils.files.fopen("foo.txt") as self.fh:
                index = 0
                for _ in self.fh:
                    index += 1
                    loc = self.fh.tell()
                    assert loc == sum(
                        len(x) for x in self.questions_str_lines[:index]
                    ), loc

    def test_write(self):
        """
        Test writing to a filehandle using .write()
        """
        # Test opening for non-binary writing
        with patch("salt.utils.files.fopen", mock_open()):
            with salt.utils.files.fopen("foo.txt", "w") as self.fh:
                for line in self.questions_str_lines:
                    self.fh.write(line)
                assert (
                    self.fh.write_calls == self.questions_str_lines
                ), self.fh.write_calls

        # Test opening for binary writing using "wb"
        with patch("salt.utils.files.fopen", mock_open(read_data=b"")):
            with salt.utils.files.fopen("foo.txt", "wb") as self.fh:
                for line in self.questions_bytes_lines:
                    self.fh.write(line)
                assert (
                    self.fh.write_calls == self.questions_bytes_lines
                ), self.fh.write_calls

        # Test opening for binary writing using "ab"
        with patch("salt.utils.files.fopen", mock_open(read_data=b"")):
            with salt.utils.files.fopen("foo.txt", "ab") as self.fh:
                for line in self.questions_bytes_lines:
                    self.fh.write(line)
                assert (
                    self.fh.write_calls == self.questions_bytes_lines
                ), self.fh.write_calls

        # Test opening for read-and-write using "r+b"
        with patch("salt.utils.files.fopen", mock_open(read_data=b"")):
            with salt.utils.files.fopen("foo.txt", "r+b") as self.fh:
                for line in self.questions_bytes_lines:
                    self.fh.write(line)
                assert (
                    self.fh.write_calls == self.questions_bytes_lines
                ), self.fh.write_calls

        # Test trying to write str types to a binary filehandle
        with patch("salt.utils.files.fopen", mock_open(read_data=b"")):
            with salt.utils.files.fopen("foo.txt", "wb") as self.fh:
                try:
                    self.fh.write("foo\n")
                except TypeError:
                    # This exception is expected on Python 3
                    pass
                else:
                    # This write should work fine on Python 2
                    raise Exception(
                        "Should not have been able to write a str to a "
                        "binary filehandle"
                    )

        # Test trying to write bytestrings to a non-binary filehandle
        with patch("salt.utils.files.fopen", mock_open()):
            with salt.utils.files.fopen("foo.txt", "w") as self.fh:
                try:
                    self.fh.write(b"foo\n")
                except TypeError:
                    # This exception is expected on Python 3
                    pass
                else:
                    # This write should work fine on Python 2
                    raise Exception(
                        "Should not have been able to write a bytestring "
                        "to a non-binary filehandle"
                    )

    def test_writelines(self):
        """
        Test writing to a filehandle using .writelines()
        """
        # Test opening for non-binary writing
        with patch("salt.utils.files.fopen", mock_open()):
            with salt.utils.files.fopen("foo.txt", "w") as self.fh:
                self.fh.writelines(self.questions_str_lines)
                assert self.fh.writelines_calls == [
                    self.questions_str_lines
                ], self.fh.writelines_calls

        # Test opening for binary writing using "wb"
        with patch("salt.utils.files.fopen", mock_open(read_data=b"")):
            with salt.utils.files.fopen("foo.txt", "wb") as self.fh:
                self.fh.writelines(self.questions_bytes_lines)
                assert self.fh.writelines_calls == [
                    self.questions_bytes_lines
                ], self.fh.writelines_calls

        # Test opening for binary writing using "ab"
        with patch("salt.utils.files.fopen", mock_open(read_data=b"")):
            with salt.utils.files.fopen("foo.txt", "ab") as self.fh:
                self.fh.writelines(self.questions_bytes_lines)
                assert self.fh.writelines_calls == [
                    self.questions_bytes_lines
                ], self.fh.writelines_calls

        # Test opening for read-and-write using "r+b"
        with patch("salt.utils.files.fopen", mock_open(read_data=b"")):
            with salt.utils.files.fopen("foo.txt", "r+b") as self.fh:
                self.fh.writelines(self.questions_bytes_lines)
                assert self.fh.writelines_calls == [
                    self.questions_bytes_lines
                ], self.fh.writelines_calls

        # Test trying to write str types to a binary filehandle
        with patch("salt.utils.files.fopen", mock_open(read_data=b"")):
            with salt.utils.files.fopen("foo.txt", "wb") as self.fh:
                try:
                    self.fh.writelines(["foo\n"])
                except TypeError:
                    # This exception is expected on Python 3
                    pass
                else:
                    # This write should work fine on Python 2
                    raise Exception(
                        "Should not have been able to write a str to a "
                        "binary filehandle"
                    )

        # Test trying to write bytestrings to a non-binary filehandle
        with patch("salt.utils.files.fopen", mock_open()):
            with salt.utils.files.fopen("foo.txt", "w") as self.fh:
                try:
                    self.fh.write([b"foo\n"])
                except TypeError:
                    # This exception is expected on Python 3
                    pass
                else:
                    # This write should work fine on Python 2
                    raise Exception(
                        "Should not have been able to write a bytestring "
                        "to a non-binary filehandle"
                    )

    def test_open(self):
        """
        Test that opening a file for binary reading with string read_data
        fails, and that the same thing happens for non-binary filehandles and
        bytestring read_data.

        NOTE: This test should always pass on PY2 since MockOpen will normalize
        unicode types to str types.
        """
        try:
            with patch("salt.utils.files.fopen", mock_open()):
                try:
                    with salt.utils.files.fopen("foo.txt", "rb") as self.fh:
                        self.fh.read()
                except TypeError:
                    pass
                else:
                    raise Exception(
                        "Should not have been able open for binary read with "
                        "non-bytestring read_data"
                    )

            with patch("salt.utils.files.fopen", mock_open(read_data=b"")):
                try:
                    with salt.utils.files.fopen("foo.txt", "r") as self.fh2:
                        self.fh2.read()
                except TypeError:
                    pass
                else:
                    raise Exception(
                        "Should not have been able open for non-binary read "
                        "with bytestring read_data"
                    )
        finally:
            # Make sure we destroy the filehandles before the teardown, as they
            # will also try to read and this will generate another exception
            delattr(self, "fh")
            delattr(self, "fh2")
