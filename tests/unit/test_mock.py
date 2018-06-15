# -*- coding: utf-8 -*-
'''
Tests for our mock_open helper
'''
# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function
import textwrap

# Import Salt libs
import salt.utils.files

# Import Salt Testing Libs
from tests.support.mock import patch, mock_open, NO_MOCK, NO_MOCK_REASON
from tests.support.unit import TestCase, skipIf

QUESTIONS = '''\
What is your name?
What is your quest?
What is the airspeed velocity of an unladen swallow?
'''


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MockOpenTestCase(TestCase):
    '''
    Tests for our mock_open helper to ensure that it behaves as closely as
    possible to a real filehandle.
    '''
    def tearDown(self):
        '''
        Each test should read the entire contents of the mocked filehandle.
        This confirms that the other read functions return empty strings/lists,
        to simulate being at EOF.
        '''
        result = self.fh.read(5)
        assert not result, result
        result = self.fh.read()
        assert not result, result
        result = self.fh.readline()
        assert not result, result
        result = self.fh.readlines()
        assert not result, result
        # Last but not least, try to read using a for loop. This should not
        # read anything as we should hit EOF immediately, before the generator
        # in the mocked filehandle has a chance to yield anything. So the
        # exception will only be raised if we aren't at EOF already.
        for line in self.fh:
            raise Exception(
                'Instead of EOF, read the following: {0}'.format(line)
            )

    def test_read(self):
        '''
        Test reading the entire file
        '''
        with patch('salt.utils.files.fopen', mock_open(read_data=QUESTIONS)):
            with salt.utils.files.fopen('foo.txt') as self.fh:
                result = self.fh.read(999999)
                assert result == QUESTIONS, result

    def test_read_explicit_size(self):
        '''
        Test reading with explicit sizes
        '''
        with patch('salt.utils.files.fopen', mock_open(read_data='foobarbaz!')):
            with salt.utils.files.fopen('foo.txt') as self.fh:
                # Read 3 bytes
                result = self.fh.read(3)
                assert result == 'foo', result
                # Read another 3 bytes
                result = self.fh.read(3)
                assert result == 'bar', result
                # Read the rest
                result = self.fh.read()
                assert result == 'baz!', result

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

    def test_read_for_loop(self):
        '''
        Test reading the contents of the file line by line in a for loop
        '''
        lines = QUESTIONS.splitlines(True)
        with patch('salt.utils.files.fopen', mock_open(read_data=QUESTIONS)):
            with salt.utils.files.fopen('foo.txt') as self.fh:
                index = 0
                for line in self.fh:
                    assert line == lines[index], 'Line {0}: {1}'.format(index, line)
                    index += 1

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

    def test_readlines(self):
        '''
        Test reading the entire file using .readlines
        '''
        with patch('salt.utils.files.fopen', mock_open(read_data=QUESTIONS)):
            with salt.utils.files.fopen('foo.txt') as self.fh:
                result = self.fh.readlines()
                assert result == QUESTIONS.splitlines(True), result
