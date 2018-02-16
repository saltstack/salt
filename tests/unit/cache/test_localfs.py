# -*- coding: utf-8 -*-
'''
unit tests for the localfs cache
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import shutil
import tempfile

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.paths import TMP
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

# Import Salt libs
import salt.payload
import salt.utils.files
import salt.cache.localfs as localfs
from salt.exceptions import SaltCacheError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LocalFSTest(TestCase, LoaderModuleMockMixin):
    '''
    Validate the functions in the localfs cache
    '''

    def setup_loader_modules(self):
        return {localfs: {}}

    def _create_tmp_cache_file(self, tmp_dir, serializer):
        '''
        Helper function that creates a temporary cache file using localfs.store. This
        is to used to create DRY unit tests for the localfs cache.
        '''
        self.addCleanup(shutil.rmtree, tmp_dir)
        with patch.dict(localfs.__opts__, {'cachedir': tmp_dir}):
            with patch.dict(localfs.__context__, {'serial': serializer}):
                localfs.store(bank='bank', key='key', data='payload data', cachedir=tmp_dir)

    # 'store' function tests: 4

    def test_store_no_base_cache_dir(self):
        '''
        Tests that a SaltCacheError is raised when the base directory doesn't exist and
        cannot be created.
        '''
        with patch('os.path.isdir', MagicMock(return_value=None)):
            with patch('os.makedirs', MagicMock(side_effect=OSError)):
                self.assertRaises(SaltCacheError, localfs.store, bank='', key='', data='', cachedir='')

    def test_store_close_mkstemp_file_handle(self):
        '''
        Tests that the file descriptor that is opened by os.open during the mkstemp call
        in localfs.store is closed before calling salt.utils.files.fopen on the filename.

        This test mocks the call to mkstemp, but forces an OSError to be raised when the
        close() function is called on a file descriptor that doesn't exist.
        '''
        with patch('os.path.isdir', MagicMock(return_value=True)):
            with patch('tempfile.mkstemp', MagicMock(return_value=(12345, 'foo'))):
                self.assertRaises(OSError, localfs.store, bank='', key='', data='', cachedir='')

    def test_store_error_writing_cache(self):
        '''
        Tests that a SaltCacheError is raised when there is a problem writing to the
        cache file.
        '''
        with patch('os.path.isdir', MagicMock(return_value=True)):
            with patch('tempfile.mkstemp', MagicMock(return_value=('one', 'two'))):
                with patch('os.close', MagicMock(return_value=None)):
                    with patch('salt.utils.files.fopen', MagicMock(side_effect=IOError)):
                        self.assertRaises(SaltCacheError, localfs.store, bank='', key='', data='', cachedir='')

    def test_store_success(self):
        '''
        Tests that the store function writes the data to the serializer for storage.
        '''
        # Create a temporary cache dir
        tmp_dir = tempfile.mkdtemp(dir=TMP)

        # Use the helper function to create the cache file using localfs.store()
        self._create_tmp_cache_file(tmp_dir, salt.payload.Serial(self))

        # Read in the contents of the key.p file and assert "payload data" was written
        with salt.utils.files.fopen(tmp_dir + '/bank/key.p', 'rb') as fh_:
            for line in fh_:
                self.assertIn(b'payload data', line)

    # 'fetch' function tests: 3

    def test_fetch_return_when_cache_file_does_not_exist(self):
        '''
        Tests that the fetch function returns an empty dic when the cache key file
        doesn't exist.
        '''
        with patch('os.path.isfile', MagicMock(return_value=False)):
            self.assertEqual(localfs.fetch(bank='', key='', cachedir=''), {})

    def test_fetch_error_reading_cache(self):
        '''
        Tests that a SaltCacheError is raised when there is a problem reading the cache
        file.
        '''
        with patch('os.path.isfile', MagicMock(return_value=True)):
            with patch('salt.utils.files.fopen', MagicMock(side_effect=IOError)):
                self.assertRaises(SaltCacheError, localfs.fetch, bank='', key='', cachedir='')

    def test_fetch_success(self):
        '''
        Tests that the fetch function is able to read the cache file and return its data.
        '''
        # Create a temporary cache dir
        tmp_dir = tempfile.mkdtemp(dir=TMP)

        # Create a new serializer object to use in function patches
        serializer = salt.payload.Serial(self)

        # Use the helper function to create the cache file using localfs.store()
        self._create_tmp_cache_file(tmp_dir, serializer)

        # Now fetch the data from the new cache key file
        with patch.dict(localfs.__opts__, {'cachedir': tmp_dir}):
            with patch.dict(localfs.__context__, {'serial': serializer}):
                self.assertIn('payload data', localfs.fetch(bank='bank', key='key', cachedir=tmp_dir))

    # 'updated' function tests: 3

    def test_updated_return_when_cache_file_does_not_exist(self):
        '''
        Tests that the updated function returns None when the cache key file doesn't
        exist.
        '''
        with patch('os.path.isfile', MagicMock(return_value=False)):
            self.assertIsNone(localfs.updated(bank='', key='', cachedir=''))

    def test_updated_error_when_reading_mtime(self):
        '''
        Tests that a SaltCacheError is raised when there is a problem reading the mtime
        of the cache file.
        '''
        with patch('os.path.isfile', MagicMock(return_value=True)):
            with patch('os.path.getmtime', MagicMock(side_effect=IOError)):
                self.assertRaises(SaltCacheError, localfs.updated, bank='', key='', cachedir='')

    def test_updated_success(self):
        '''
        Test that the updated function returns the modification time of the cache file
        '''
        # Create a temporary cache dir
        tmp_dir = tempfile.mkdtemp(dir=TMP)

        # Use the helper function to create the cache file using localfs.store()
        self._create_tmp_cache_file(tmp_dir, salt.payload.Serial(self))

        with patch('os.path.join', MagicMock(return_value=tmp_dir + '/bank/key.p')):
            self.assertIsInstance(localfs.updated(bank='bank', key='key', cachedir=tmp_dir), int)

    # 'flush' function tests: 4

    def test_flush_key_is_none_and_no_target_dir(self):
        '''
        Tests that the flush function returns False when no key is passed in and the
        target directory doesn't exist.
        '''
        with patch('os.path.isdir', MagicMock(return_value=False)):
            self.assertFalse(localfs.flush(bank='', key=None, cachedir=''))

    def test_flush_key_provided_and_no_key_file_false(self):
        '''
        Tests that the flush function returns False when a key file is provided but
        the target key file doesn't exist in the cache bank.
        '''
        with patch('os.path.isfile', MagicMock(return_value=False)):
            self.assertFalse(localfs.flush(bank='', key='key', cachedir=''))

    def test_flush_success(self):
        '''
        Tests that the flush function returns True when a key file is provided and
        the target key exists in the cache bank.
        '''
        with patch('os.path.isfile', MagicMock(return_value=True)):
            # Create a temporary cache dir
            tmp_dir = tempfile.mkdtemp(dir=TMP)

            # Use the helper function to create the cache file using localfs.store()
            self._create_tmp_cache_file(tmp_dir, salt.payload.Serial(self))

            # Now test the return of the flush function
            with patch.dict(localfs.__opts__, {'cachedir': tmp_dir}):
                self.assertTrue(localfs.flush(bank='bank', key='key', cachedir=tmp_dir))

    def test_flush_error_raised(self):
        '''
        Tests that a SaltCacheError is raised when there is a problem removing the
        key file from the cache bank
        '''
        with patch('os.path.isfile', MagicMock(return_value=True)):
            with patch('os.remove', MagicMock(side_effect=OSError)):
                self.assertRaises(SaltCacheError, localfs.flush, bank='', key='key', cachedir='/var/cache/salt')

    # 'list' function tests: 3

    def test_list_no_base_dir(self):
        '''
        Tests that the ls function returns an empty list if the bank directory
        doesn't exist.
        '''
        with patch('os.path.isdir', MagicMock(return_value=False)):
            self.assertEqual(localfs.list_(bank='', cachedir=''), [])

    def test_list_error_raised_no_bank_directory_access(self):
        '''
        Tests that a SaltCacheError is raised when there is a problem accessing the
        cache bank directory.
        '''
        with patch('os.path.isdir', MagicMock(return_value=True)):
            with patch('os.listdir', MagicMock(side_effect=OSError)):
                self.assertRaises(SaltCacheError, localfs.list_, bank='', cachedir='')

    def test_list_success(self):
        '''
        Tests the return of the ls function containing bank entries.
        '''
        # Create a temporary cache dir
        tmp_dir = tempfile.mkdtemp(dir=TMP)

        # Use the helper function to create the cache file using localfs.store()
        self._create_tmp_cache_file(tmp_dir, salt.payload.Serial(self))

        # Now test the return of the ls function
        with patch.dict(localfs.__opts__, {'cachedir': tmp_dir}):
            self.assertEqual(localfs.list_(bank='bank', cachedir=tmp_dir), ['key'])

    # 'contains' function tests: 1

    def test_contains(self):
        '''
        Test the return of the contains function when key=None and when a key
        is provided.
        '''
        # Create a temporary cache dir
        tmp_dir = tempfile.mkdtemp(dir=TMP)

        # Use the helper function to create the cache file using localfs.store()
        self._create_tmp_cache_file(tmp_dir, salt.payload.Serial(self))

        # Now test the return of the contains function when key=None
        with patch.dict(localfs.__opts__, {'cachedir': tmp_dir}):
            self.assertTrue(localfs.contains(bank='bank', key=None, cachedir=tmp_dir))

        # Now test the return of the contains function when key='key'
        with patch.dict(localfs.__opts__, {'cachedir': tmp_dir}):
            self.assertTrue(localfs.contains(bank='bank', key='key', cachedir=tmp_dir))
