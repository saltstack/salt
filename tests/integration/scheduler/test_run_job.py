# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import copy
import logging
import os

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin

# Import Salt Testing Libs
from tests.support.mock import MagicMock, patch
import tests.integration as integration

# Import Salt libs
import salt.utils.schedule
import salt.utils.platform

from salt.modules.test import ping as ping

try:
    import croniter  # pylint: disable=W0611
    HAS_CRONITER = True
except ImportError:
    HAS_CRONITER = False

log = logging.getLogger(__name__)
ROOT_DIR = os.path.join(integration.TMP, 'schedule-unit-tests')
SOCK_DIR = os.path.join(ROOT_DIR, 'test-socks')

DEFAULT_CONFIG = salt.config.minion_config(None)
DEFAULT_CONFIG['conf_dir'] = ROOT_DIR
DEFAULT_CONFIG['root_dir'] = ROOT_DIR
DEFAULT_CONFIG['sock_dir'] = SOCK_DIR
DEFAULT_CONFIG['pki_dir'] = os.path.join(ROOT_DIR, 'pki')
DEFAULT_CONFIG['cachedir'] = os.path.join(ROOT_DIR, 'cache')


class SchedulerRunJobTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the pkg module
    '''
    def setUp(self):
        with patch('salt.utils.schedule.clean_proc_dir', MagicMock(return_value=None)):
            functions = {'test.ping': ping}
            self.schedule = salt.utils.schedule.Schedule(copy.deepcopy(DEFAULT_CONFIG), functions, returners={})
        self.schedule.opts['loop_interval'] = 1

    def tearDown(self):
        self.schedule.reset()

    def test_run_job(self):
        '''
        verify that scheduled job runs
        '''
        job_name = 'test_run_job'
        job = {
          'schedule': {
            job_name: {
              'function': 'test.ping',
            }
          }
        }
        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # Run job
        self.schedule.run_job(job_name)
        ret = self.schedule.job_status(job_name)
        expected = {'function': 'test.ping', 'run': True, 'name': 'test_run_job'}
        self.assertEqual(ret, expected)
