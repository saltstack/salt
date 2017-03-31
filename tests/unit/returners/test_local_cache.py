# -*- coding: utf-8 -*-
'''
tests.unit.returners.local_cache_test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the Default Job Cache (local_cache).
'''

# Import Python libs
from __future__ import absolute_import
import os
import shutil
import tempfile

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.paths import TMP
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

# Import Salt libs
import salt.utils
import salt.returners.local_cache as local_cache

TMP_CACHE_DIR = os.path.join(TMP, 'salt_test_job_cache')
TMP_JID_DIR = os.path.join(TMP_CACHE_DIR, 'jobs')


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LocalCacheCleanOldJobsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Tests for the local_cache.clean_old_jobs function.
    '''
    def setup_loader_modules(self):
        return {local_cache: {'__opts__': {'cachedir': TMP_CACHE_DIR, 'keep_jobs': 1}}}

    def tearDown(self):
        '''
        Clean up after tests.

        Note that a setUp function is not used in this TestCase because the
        _make_tmp_jid_dirs replaces it.
        '''
        if os.path.exists(TMP_CACHE_DIR):
            shutil.rmtree(TMP_CACHE_DIR)

    @patch('os.path.exists', MagicMock(return_value=False))
    def test_clean_old_jobs_no_jid_root(self):
        '''
        Tests that the function returns None when no jid_root is found.
        '''
        self.assertEqual(local_cache.clean_old_jobs(), None)

    def test_clean_old_jobs_empty_jid_dir_removed(self):
        '''
        Tests that an empty JID dir is removed when it is old enough to be deleted.
        '''
        # Create temp job cache dir without files in it.
        jid_dir, jid_file = self._make_tmp_jid_dirs(create_files=False)

        # Make sure there are no files in the directory before continuing
        self.assertEqual(jid_file, None)

        # Call clean_old_jobs function, patching the keep_jobs value with a
        # very small value to force the call to clean the job.
        with patch.dict(local_cache.__opts__, {'keep_jobs': 0.00000001}):
            local_cache.clean_old_jobs()

        # Assert that the JID dir was removed
        self.assertEqual([], os.listdir(TMP_JID_DIR))

    def test_clean_old_jobs_empty_jid_dir_remains(self):
        '''
        Tests that an empty JID dir is NOT removed because it was created within
        the keep_jobs time frame.
        '''
        # Create temp job cache dir without files in it.
        jid_dir, jid_file = self._make_tmp_jid_dirs(create_files=False)

        # Make sure there are no files in the directory
        self.assertEqual(jid_file, None)

        # Call clean_old_jobs function
        local_cache.clean_old_jobs()

        # Get the name of the JID directory that was created to test against
        jid_dir_name = jid_dir.rpartition('/')[2]

        # Assert the JID directory is still present to be cleaned after keep_jobs interval
        self.assertEqual([jid_dir_name], os.listdir(TMP_JID_DIR))

    def test_clean_old_jobs_jid_file_corrupted(self):
        '''
        Tests that the entire JID dir is removed when the jid_file is not a file.
        This scenario indicates a corrupted cache entry, so the entire dir is scrubbed.
        '''
        # Create temp job cache dir and jid file
        jid_dir, jid_file = self._make_tmp_jid_dirs()

        # Make sure there is a jid file in a new job cache director
        jid_dir_name = jid_file.rpartition('/')[2]
        self.assertEqual(jid_dir_name, 'jid')

        # Even though we created a valid jid file in the _make_tmp_jid_dirs call to get
        # into the correct loop, we need to mock the 'os.path.isfile' check to force the
        # "corrupted file" check in the clean_old_jobs call.
        with patch('os.path.isfile', MagicMock(return_value=False)) as mock:
            local_cache.clean_old_jobs()

        # Assert that the JID dir was removed
        self.assertEqual([], os.listdir(TMP_JID_DIR))

    def test_clean_old_jobs_jid_file_is_cleaned(self):
        '''
        Test that the entire JID dir is removed when a job is old enough to be removed.
        '''
        # Create temp job cache dir and jid file
        jid_dir, jid_file = self._make_tmp_jid_dirs()

        # Make sure there is a jid directory
        jid_dir_name = jid_file.rpartition('/')[2]
        self.assertEqual(jid_dir_name, 'jid')

        # Call clean_old_jobs function, patching the keep_jobs value with a
        # very small value to force the call to clean the job.
        with patch.dict(local_cache.__opts__, {'keep_jobs': 0.00000001}):
            local_cache.clean_old_jobs()

        # Assert that the JID dir was removed
        self.assertEqual([], os.listdir(TMP_JID_DIR))

    def _make_tmp_jid_dirs(self, create_files=True):
        '''
        Helper function to set up temporary directories and files used for
        testing the clean_old_jobs function.

        Returns a temp_dir name and a jid_file_path. If create_files is False,
        the jid_file_path will be None.
        '''
        # First, create the /tmp/salt_test_job_cache/jobs/ directory to hold jid dirs
        if not os.path.exists(TMP_JID_DIR):
            os.makedirs(TMP_JID_DIR)

        # Then create a JID temp file in "/tmp/salt_test_job_cache/"
        temp_dir = tempfile.mkdtemp(dir=TMP_JID_DIR)

        jid_file_path = None
        if create_files:
            dir_name = '/'.join([temp_dir, 'jid'])
            os.mkdir(dir_name)
            jid_file_path = '/'.join([dir_name, 'jid'])
            with salt.utils.fopen(jid_file_path, 'w') as jid_file:
                jid_file.write('this is a jid file')

        return temp_dir, jid_file_path
