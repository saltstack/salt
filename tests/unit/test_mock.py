# -*- coding: utf-8 -*-
'''
Tests for our mock_open helper
'''
# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function
import errno
import logging

# Import Salt libs
import salt.utils.data
import salt.utils.files

# Import Salt Testing Libs
from tests.support.mock import patch, mock_open, NO_MOCK, NO_MOCK_REASON
from tests.support.unit import TestCase, skipIf

QUESTIONS = '''\
What is your name?
What is your quest?
What is the airspeed velocity of an unladen swallow?
'''

ANSWERS = '''\
It is Arthur, King of the Britons.
To seek the Holy Grail.
What do you mean? An African or European swallow?
'''

log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MockOpenTestCase(TestCase):
    '''
    Tests for our mock_open helper to ensure that it behaves as closely as
    possible to a real filehandle.
    '''
    @classmethod
    def setUpClass(cls):
        cls.contents = {'foo.txt': QUESTIONS, 'b*.txt': ANSWERS}
        cls.read_data_as_list = [
            'foo', 'bar', 'спам',
            IOError(errno.EACCES, 'Permission denied')
        ]
        cls.normalized_read_data_as_list = salt.utils.data.decode(
            cls.read_data_as_list,
            to_str=True
        )
        cls.read_data_as_list_bytes = salt.utils.data.encode(cls.read_data_as_list)

    def tearDown(self):
        '''
        Each test should read the entire contents of the mocked filehandle(s).
        This confirms that the other read functions return empty strings/lists,
        to simulate being at EOF.
        '''
        for handle_name in ('fh', 'fh2', 'fh3'):
            try:
                fh = getattr(self, handle_name)
            except AttributeError:
                continue
            log.debug('Running tearDown tests for self.%s', handle_name)
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
                    'Instead of EOF, read the following from {0}: {1}'.format(
                        handle_name,
                        line
                    )
                )
            del fh

    def test_read(self):
        '''
        Test reading the entire file
        '''
        with patch('salt.utils.files.fopen', mock_open(read_data=QUESTIONS)):
            with salt.utils.files.fopen('foo.txt') as self.fh:
                result = self.fh.read()
                assert result == QUESTIONS, result

    def test_read_multifile(self):
        '''
        Same as test_read, but using multifile support
        '''
        with patch('salt.utils.files.fopen', mock_open(read_data=self.contents)):
            with salt.utils.files.fopen('foo.txt') as self.fh:
                result = self.fh.read()
                assert result == QUESTIONS, result

            with salt.utils.files.fopen('bar.txt') as self.fh2:
                result = self.fh2.read()
                assert result == ANSWERS, result

            with salt.utils.files.fopen('baz.txt') as self.fh3:
                result = self.fh3.read()
                assert result == ANSWERS, result

            try:
                with salt.utils.files.fopen('helloworld.txt'):
                    raise Exception('No globs should have matched')
            except IOError:
                # An IOError is expected here
                pass

    def test_read_explicit_size(self):
        '''
        Test reading with explicit sizes
        '''
        with patch('salt.utils.files.fopen', mock_open(read_data=QUESTIONS)):
            with salt.utils.files.fopen('foo.txt') as self.fh:
                # Read 10 bytes
                result = self.fh.read(10)
                assert result == QUESTIONS[:10], result
                # Read another 10 bytes
                result = self.fh.read(10)
                assert result == QUESTIONS[10:20], result
                # Read the rest
                result = self.fh.read()
                assert result == QUESTIONS[20:], result

    def test_read_explicit_size_multifile(self):
        '''
        Same as test_read_explicit_size, but using multifile support
        '''
        with patch('salt.utils.files.fopen', mock_open(read_data=self.contents)):
            with salt.utils.files.fopen('foo.txt') as self.fh:
                # Read 10 bytes
                result = self.fh.read(10)
                assert result == QUESTIONS[:10], result
                # Read another 10 bytes
                result = self.fh.read(10)
                assert result == QUESTIONS[10:20], result
                # Read the rest
                result = self.fh.read()
                assert result == QUESTIONS[20:], result

            with salt.utils.files.fopen('bar.txt') as self.fh2:
                # Read 10 bytes
                result = self.fh2.read(10)
                assert result == ANSWERS[:10], result
                # Read another 10 bytes
                result = self.fh2.read(10)
                assert result == ANSWERS[10:20], result
                # Read the rest
                result = self.fh2.read()
                assert result == ANSWERS[20:], result

            with salt.utils.files.fopen('baz.txt') as self.fh3:
                # Read 10 bytes
                result = self.fh3.read(10)
                assert result == ANSWERS[:10], result
                # Read another 10 bytes
                result = self.fh3.read(10)
                assert result == ANSWERS[10:20], result
                # Read the rest
                result = self.fh3.read()
                assert result == ANSWERS[20:], result

            try:
                with salt.utils.files.fopen('helloworld.txt'):
                    raise Exception('No globs should have matched')
            except IOError:
                # An IOError is expected here
                pass

    def test_read_explicit_size_larger_than_file_size(self):
        '''
        Test reading with an explicit size larger than the size of read_data.
        This ensures that we just return the contents up until EOF and that we
        don't raise any errors due to the desired size being larger than the
        mocked file's size.
        '''
        with patch('salt.utils.files.fopen', mock_open(read_data=QUESTIONS)):
            with salt.utils.files.fopen('foo.txt') as self.fh:
                result = self.fh.read(999999)
                assert result == QUESTIONS, result

    def test_read_explicit_size_larger_than_file_size_multifile(self):
        '''
        Same as test_read_explicit_size_larger_than_file_size, but using
        multifile support
        '''
        with patch('salt.utils.files.fopen', mock_open(read_data=self.contents)):
            with salt.utils.files.fopen('foo.txt') as self.fh:
                result = self.fh.read(999999)
                assert result == QUESTIONS, result

            with salt.utils.files.fopen('bar.txt') as self.fh2:
                result = self.fh2.read(999999)
                assert result == ANSWERS, result

            with salt.utils.files.fopen('baz.txt') as self.fh3:
                result = self.fh3.read(999999)
                assert result == ANSWERS, result

            try:
                with salt.utils.files.fopen('helloworld.txt'):
                    raise Exception('No globs should have matched')
            except IOError:
                # An IOError is expected here
                pass

    def test_read_for_loop(self):
        '''
        Test reading the contents of the file line by line in a for loop
        '''
        with patch('salt.utils.files.fopen', mock_open(read_data=QUESTIONS)):
            lines = QUESTIONS.splitlines(True)
            with salt.utils.files.fopen('foo.txt') as self.fh:
                index = 0
                for line in self.fh:
                    assert line == lines[index], 'Line {0}: {1}'.format(index, line)
                    index += 1

    def test_read_for_loop_multifile(self):
        '''
        Same as test_read_for_loop, but using multifile support
        '''
        with patch('salt.utils.files.fopen', mock_open(read_data=self.contents)):
            lines = QUESTIONS.splitlines(True)
            with salt.utils.files.fopen('foo.txt') as self.fh:
                index = 0
                for line in self.fh:
                    assert line == lines[index], 'Line {0}: {1}'.format(index, line)
                    index += 1

            lines = ANSWERS.splitlines(True)
            with salt.utils.files.fopen('bar.txt') as self.fh2:
                index = 0
                for line in self.fh2:
                    assert line == lines[index], 'Line {0}: {1}'.format(index, line)
                    index += 1

            with salt.utils.files.fopen('baz.txt') as self.fh3:
                index = 0
                for line in self.fh3:
                    assert line == lines[index], 'Line {0}: {1}'.format(index, line)
                    index += 1

            try:
                with salt.utils.files.fopen('helloworld.txt'):
                    raise Exception('No globs should have matched')
            except IOError:
                # An IOError is expected here
                pass

    def test_read_readline(self):
        '''
        Test reading part of a line using .read(), then reading the rest of the
        line (and subsequent lines) using .readline().
        '''
        with patch('salt.utils.files.fopen', mock_open(read_data=QUESTIONS)):
            with salt.utils.files.fopen('foo.txt') as self.fh:
                # Read the first 4 chars of line 1
                result = self.fh.read(4)
                assert result == 'What', result
                # Use .readline() to read the remainder of the line
                result = self.fh.readline()
                assert result == ' is your name?\n', result
                # Read and check the other two lines
                result = self.fh.readline()
                assert result == 'What is your quest?\n', result
                result = self.fh.readline()
                assert result == 'What is the airspeed velocity of an unladen swallow?\n', result

    def test_read_readline_multifile(self):
        '''
        Same as test_read_readline, but using multifile support
        '''
        with patch('salt.utils.files.fopen', mock_open(read_data=self.contents)):
            with salt.utils.files.fopen('foo.txt') as self.fh:
                # Read the first 4 chars of line 1
                result = self.fh.read(4)
                assert result == 'What', result
                # Use .readline() to read the remainder of the line
                result = self.fh.readline()
                assert result == ' is your name?\n', result
                # Read and check the other two lines
                result = self.fh.readline()
                assert result == 'What is your quest?\n', result
                result = self.fh.readline()
                assert result == 'What is the airspeed velocity of an unladen swallow?\n', result

            with salt.utils.files.fopen('bar.txt') as self.fh2:
                # Read the first 4 chars of line 1
                result = self.fh2.read(14)
                assert result == 'It is Arthur, ', result
                # Use .readline() to read the remainder of the line
                result = self.fh2.readline()
                assert result == 'King of the Britons.\n', result
                # Read and check the other two lines
                result = self.fh2.readline()
                assert result == 'To seek the Holy Grail.\n', result
                result = self.fh2.readline()
                assert result == 'What do you mean? An African or European swallow?\n', result

            with salt.utils.files.fopen('baz.txt') as self.fh3:
                # Read the first 4 chars of line 1
                result = self.fh3.read(14)
                assert result == 'It is Arthur, ', result
                # Use .readline() to read the remainder of the line
                result = self.fh3.readline()
                assert result == 'King of the Britons.\n', result
                # Read and check the other two lines
                result = self.fh3.readline()
                assert result == 'To seek the Holy Grail.\n', result
                result = self.fh3.readline()
                assert result == 'What do you mean? An African or European swallow?\n', result

            try:
                with salt.utils.files.fopen('helloworld.txt'):
                    raise Exception('No globs should have matched')
            except IOError:
                # An IOError is expected here
                pass

    def test_readline_readlines(self):
        '''
        Test reading the first line using .readline(), then reading the rest of
        the file using .readlines().
        '''
        with patch('salt.utils.files.fopen', mock_open(read_data=QUESTIONS)):
            with salt.utils.files.fopen('foo.txt') as self.fh:
                # Read the first line
                result = self.fh.readline()
                assert result == 'What is your name?\n', result
                # Use .readlines() to read the remainder of the file
                result = self.fh.readlines()
                assert result == [
                    'What is your quest?\n',
                    'What is the airspeed velocity of an unladen swallow?\n'
                ], result

    def test_readline_readlines_multifile(self):
        '''
        Same as test_readline_readlines, but using multifile support
        '''
        with patch('salt.utils.files.fopen', mock_open(read_data=self.contents)):
            with salt.utils.files.fopen('foo.txt') as self.fh:
                # Read the first line
                result = self.fh.readline()
                assert result == 'What is your name?\n', result
                # Use .readlines() to read the remainder of the file
                result = self.fh.readlines()
                assert result == [
                    'What is your quest?\n',
                    'What is the airspeed velocity of an unladen swallow?\n'
                ], result

            with salt.utils.files.fopen('bar.txt') as self.fh2:
                # Read the first line
                result = self.fh2.readline()
                assert result == 'It is Arthur, King of the Britons.\n', result
                # Use .readlines() to read the remainder of the file
                result = self.fh2.readlines()
                assert result == [
                    'To seek the Holy Grail.\n',
                    'What do you mean? An African or European swallow?\n'
                ], result

            with salt.utils.files.fopen('baz.txt') as self.fh3:
                # Read the first line
                result = self.fh3.readline()
                assert result == 'It is Arthur, King of the Britons.\n', result
                # Use .readlines() to read the remainder of the file
                result = self.fh3.readlines()
                assert result == [
                    'To seek the Holy Grail.\n',
                    'What do you mean? An African or European swallow?\n'
                ], result

            try:
                with salt.utils.files.fopen('helloworld.txt'):
                    raise Exception('No globs should have matched')
            except IOError:
                # An IOError is expected here
                pass

    def test_readlines(self):
        '''
        Test reading the entire file using .readlines
        '''
        with patch('salt.utils.files.fopen', mock_open(read_data=QUESTIONS)):
            with salt.utils.files.fopen('foo.txt') as self.fh:
                result = self.fh.readlines()
                assert result == QUESTIONS.splitlines(True), result

    def test_readlines_multifile(self):
        '''
        Same as test_readlines, but using multifile support
        '''
        with patch('salt.utils.files.fopen', mock_open(read_data=self.contents)):
            with salt.utils.files.fopen('foo.txt') as self.fh:
                result = self.fh.readlines()
                assert result == QUESTIONS.splitlines(True), result

            with salt.utils.files.fopen('bar.txt') as self.fh2:
                result = self.fh2.readlines()
                assert result == ANSWERS.splitlines(True), result

            with salt.utils.files.fopen('baz.txt') as self.fh3:
                result = self.fh3.readlines()
                assert result == ANSWERS.splitlines(True), result

            try:
                with salt.utils.files.fopen('helloworld.txt'):
                    raise Exception('No globs should have matched')
            except IOError:
                # An IOError is expected here
                pass

    def test_read_data_converted_to_dict(self):
        '''
        Test that a non-dict value for read_data is converted to a dict mapping
        '*' to that value.
        '''
        contents = 'спам'
        normalized = salt.utils.stringutils.to_str(contents)
        with patch('salt.utils.files.fopen',
                   mock_open(read_data=contents)) as m_open:
            assert m_open.read_data == {'*': normalized}, m_open.read_data

        with patch('salt.utils.files.fopen',
                   mock_open(read_data=self.read_data_as_list)) as m_open:
            assert m_open.read_data == {
                '*': self.normalized_read_data_as_list,
            }, m_open.read_data

    def test_read_data_list(self):
        '''
        Test read_data when it is a list
        '''
        with patch('salt.utils.files.fopen',
                   mock_open(read_data=self.read_data_as_list)):
            for value in self.normalized_read_data_as_list:
                try:
                    with salt.utils.files.fopen('foo.txt') as self.fh:
                        result = self.fh.read()
                        assert result == value, result
                except IOError:
                    # Don't raise the exception if it was expected
                    if not isinstance(value, IOError):
                        raise

    def test_read_data_list_bytes(self):
        '''
        Test read_data when it is a list and the value is a bytestring
        '''
        with patch('salt.utils.files.fopen',
                   mock_open(read_data=self.read_data_as_list_bytes)):
            for value in self.read_data_as_list_bytes:
                try:
                    with salt.utils.files.fopen('foo.txt') as self.fh:
                        result = self.fh.read()
                        assert result == value, result
                except IOError:
                    # Don't raise the exception if it was expected
                    if not isinstance(value, IOError):
                        raise

    def test_tell(self):
        '''
        Test the implementation of tell
        '''
        lines = QUESTIONS.splitlines(True)
        with patch('salt.utils.files.fopen',
                   mock_open(read_data=self.contents)):
            # Try with reading explicit sizes and then reading the rest of the
            # file.
            with salt.utils.files.fopen('foo.txt') as self.fh:
                self.fh.read(5)
                loc = self.fh.tell()
                assert loc == 5, loc
                self.fh.read(12)
                loc = self.fh.tell()
                assert loc == 17, loc
                self.fh.read()
                loc = self.fh.tell()
                assert loc == len(QUESTIONS), loc

            # Try reading way more content then actually exists in the file,
            # tell() should return a value equal to the length of the content
            with salt.utils.files.fopen('foo.txt') as self.fh:
                self.fh.read(999999)
                loc = self.fh.tell()
                assert loc == len(QUESTIONS), loc

            # Try reading a few bytes using .read(), then the rest of the line
            # using .readline(), then the rest of the file using .readlines(),
            # and check the location after each read.
            with salt.utils.files.fopen('foo.txt') as self.fh:
                # Read a few bytes
                self.fh.read(5)
                loc = self.fh.tell()
                assert loc == 5, loc
                # Read the rest of the line. Location should then be at the end
                # of the first line.
                self.fh.readline()
                loc = self.fh.tell()
                assert loc == len(lines[0]), loc
                # Read the rest of the file using .readlines()
                self.fh.readlines()
                loc = self.fh.tell()
                assert loc == len(QUESTIONS), loc

            # Check location while iterating through the filehandle
            with salt.utils.files.fopen('foo.txt') as self.fh:
                index = 0
                for _ in self.fh:
                    index += 1
                    loc = self.fh.tell()
                    assert loc == sum(len(x) for x in lines[:index]), loc
