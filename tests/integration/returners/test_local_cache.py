# -*- coding: utf-8 -*-
'''
Tests for the local_cache returner
'''
# Import Python libs
from __future__ import absolute_import
import logging
import os

# Import Salt Testing libs
import tests.integration as integration

# Import salt libs
import salt.utils.job
from salt.returners import local_cache

log = logging.getLogger(__name__)

# JOBS DIR and FILES
TMP_CACHE_DIR = os.path.join(integration.TMP, 'rootdir', 'cache')
JOBS_DIR = os.path.join(TMP_CACHE_DIR, 'jobs')
JID_DIR = os.path.join(JOBS_DIR, '31', 'c56eed380a4e899ae12bc42563cfdfc53066fb4a6b53e2378a08ac49064539')
JID_FILE = os.path.join(JID_DIR, 'jid')
JID_MINION_DIR = os.path.join(JID_DIR, 'minion', 'return.p')
JOB_CACHE_DIR_FILES = [JID_FILE, JID_MINION_DIR]
KEEP_JOBS = 0.0000000010
EMPTY_JID_DIR = []

local_cache.__opts__ = {'cachedir': TMP_CACHE_DIR,
                        'keep_jobs': KEEP_JOBS}


class Local_CacheTest(integration.ShellCase):
    '''
    Test the local cache returner
    '''
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
            self.assertTrue(check_job_dir,
                            msg=msg + content)

    def _add_job(self):
        '''
        helper method to add job.
        '''
        # add the job.
        opts = {}
        opts.update(self.get_config('master'))
        load = {'fun_args': [], 'jid': '20160603132323715452',
                'return': True, 'retcode': 0, 'success': True,
                'cmd': '_return', 'fun': 'test.ping', 'id': 'minion'}

        add_job = salt.utils.job.store_job(opts, load)
        self.assertEqual(add_job, None)
        self._check_dir_files('Dir/file does not exist: ',
                              JOB_CACHE_DIR_FILES,
                              status='present')

    def test_clean_old_jobs(self):
        '''
        test to ensure jobs are removed from job cache
        '''
        self._add_job()

        # remove job
        self.assertEqual(local_cache.clean_old_jobs(), None)

        self._check_dir_files('job cache was not removed: ',
                              JOB_CACHE_DIR_FILES,
                              status='removed')

    def test_not_clean_new_jobs(self):
        '''
        test to ensure jobs are not removed when
        jobs dir is new
        '''
        self._add_job()

        local_cache.__opts__['keep_jobs'] = 24
        self.assertEqual(local_cache.clean_old_jobs(), None)

        self._check_dir_files('job cache was removed: ',
                              JOB_CACHE_DIR_FILES,
                              status='present')

        # need to set back to initial KEEP_JOBS
        local_cache.__opts__['keep_jobs'] = KEEP_JOBS

    def test_empty_jid_dir(self):
        '''
        test to ensure removal of empty jid dir
        '''
        # add empty jid dir
        new_jid_dir = os.path.join(JOBS_DIR, 'z0')
        EMPTY_JID_DIR.append(new_jid_dir)
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
                              EMPTY_JID_DIR,
                              status='present')

        # remove job
        self.assertEqual(local_cache.clean_old_jobs(), None)

        # check jid dir is removed
        self._check_dir_files('new_jid_dir was not removed',
                              EMPTY_JID_DIR,
                              status='removed')
