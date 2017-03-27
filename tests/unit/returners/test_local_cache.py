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
import logging
import tempfile

# Import Salt Testing libs
from tests.integration import AdaptedConfigurationTestCaseMixIn
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
import salt.utils.jid
import salt.returners.local_cache as local_cache
import salt.ext.six as six

log = logging.getLogger(__name__)

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


class Local_CacheTest(TestCase, AdaptedConfigurationTestCaseMixIn, LoaderModuleMockMixin):
    '''
    Test the local cache returner
    '''
    def setup_loader_modules(self):
        return {
            local_cache: {
                '__opts__': {
                    'cachedir': self.TMP_CACHE_DIR,
                    'keep_jobs': self.KEEP_JOBS
                }
            }
        }

    @classmethod
    def setUpClass(cls):
        cls.TMP_CACHE_DIR = os.path.join(TMP, 'rootdir', 'cache')
        cls.JOBS_DIR = os.path.join(cls.TMP_CACHE_DIR, 'jobs')
        cls.JID_DIR = os.path.join(cls.JOBS_DIR, '31', 'c56eed380a4e899ae12bc42563cfdfc53066fb4a6b53e2378a08ac49064539')
        cls.JID_FILE = os.path.join(cls.JID_DIR, 'jid')
        cls.JID_MINION_DIR = os.path.join(cls.JID_DIR, 'minion', 'return.p')
        cls.JOB_CACHE_DIR_FILES = [cls.JID_FILE, cls.JID_MINION_DIR]
        cls.KEEP_JOBS = 0.0000000010
        cls.EMPTY_JID_DIR = []

    @classmethod
    def tearDownClass(cls):
        for attrname in ('TMP_CACHE_DIR', 'JOBS_DIR', 'JID_DIR', 'JID_FILE', 'JID_MINION_DIR',
                         'JOB_CACHE_DIR_FILES', 'KEEP_JOBS', 'EMPTY_JID_DIR'):
            try:
                attr_instance = getattr(cls, attrname)
                if isinstance(attr_instance, six.string_types):
                    if os.path.isdir(attr_instance):
                        shutil.rmtree(attr_instance)
                    elif os.path.isfile(attr_instance):
                        os.unlink(attr_instance)
                delattr(cls, attrname)
            except AttributeError:
                continue

    def _check_dir_files(self, msg, contents, status='None'):
        '''
        helper method to ensure files or dirs
        are either present or removed
        '''
        for content in contents:
            log.debug('CONTENT {0}'.format(content))
            if status == 'present':
                check_job_dir = os.path.exists(content)
            elif status == 'removed':
                if os.path.exists(content):
                    check_job_dir = False
                else:
                    check_job_dir = True
            self.assertTrue(check_job_dir, msg=msg + content)

    def _add_job(self):
        '''
        helper method to add job.
        '''
        # add the job.
        opts = {}
        opts.update(self.get_config('master'))
        opts['cachedir'] = self.TMP_CACHE_DIR
        load = {'fun_args': [], 'jid': '20160603132323715452',
                'return': True, 'retcode': 0, 'success': True,
                'cmd': '_return', 'fun': 'test.ping', 'id': 'minion'}

        add_job = salt.utils.job.store_job(opts, load)
        self.assertEqual(add_job, None)
        self._check_dir_files('Dir/file does not exist: ',
                              self.JOB_CACHE_DIR_FILES,
                              status='present')

    def test_clean_old_jobs(self):
        '''
        test to ensure jobs are removed from job cache
        '''
        self._add_job()

        # remove job
        self.assertEqual(local_cache.clean_old_jobs(), None)

        self._check_dir_files('job cache was not removed: ',
                              self.JOB_CACHE_DIR_FILES,
                              status='removed')

    def test_not_clean_new_jobs(self):
        '''
        test to ensure jobs are not removed when
        jobs dir is new
        '''
        self._add_job()

        with patch.dict(local_cache.__opts__, {'keep_jobs': 24}):
            self.assertEqual(local_cache.clean_old_jobs(), None)

            self._check_dir_files('job cache was removed: ',
                                  self.JOB_CACHE_DIR_FILES,
                                  status='present')

    def test_empty_jid_dir(self):
        '''
        test to ensure removal of empty jid dir
        '''
        # add empty jid dir
        new_jid_dir = os.path.join(self.JOBS_DIR, 'z0')
        self.EMPTY_JID_DIR.append(new_jid_dir)
        os.makedirs(new_jid_dir)

        # This needed due to a race condition in Windows
        # `os.makedirs` hasn't released the handle before
        # `local_cache.clean_old_jobs` tries to delete the new_jid_dir
        if salt.utils.is_windows():
            import time
            lock_dir = new_jid_dir + '.lckchk'
            tries = 0
            while True:
                tries += 1
                if tries > 10:
                    break
                # Rename the directory and name it back
                # If it fails, the directory handle is not released, try again
                # If it succeeds, break and continue test
                try:
                    os.rename(new_jid_dir, lock_dir)
                    time.sleep(1)
                    os.rename(lock_dir, new_jid_dir)
                    break
                except WindowsError:  # pylint: disable=E0602
                    continue

        # check dir exists
        self._check_dir_files('new_jid_dir was not created',
                              self.EMPTY_JID_DIR,
                              status='present')

        # remove job
        self.assertEqual(local_cache.clean_old_jobs(), None)

        # check jid dir is removed
        self._check_dir_files('new_jid_dir was not removed',
                              self.EMPTY_JID_DIR,
                              status='removed')
