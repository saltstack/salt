# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import copy
import logging
import os

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS

# Import Salt libs
import salt.utils.schedule
import salt.utils.platform

from salt.modules.test import ping as ping

log = logging.getLogger(__name__)
ROOT_DIR = os.path.join(RUNTIME_VARS.TMP, 'schedule-unit-tests')
SOCK_DIR = os.path.join(ROOT_DIR, 'test-socks')

DEFAULT_CONFIG = salt.config.minion_config(None)
DEFAULT_CONFIG['conf_dir'] = ROOT_DIR
DEFAULT_CONFIG['root_dir'] = ROOT_DIR
DEFAULT_CONFIG['sock_dir'] = SOCK_DIR
DEFAULT_CONFIG['pki_dir'] = os.path.join(ROOT_DIR, 'pki')
DEFAULT_CONFIG['cachedir'] = os.path.join(ROOT_DIR, 'cache')


class SchedulerHelpersTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Test scheduler helper functions
    '''
    def setUp(self):
        with patch('salt.utils.schedule.clean_proc_dir', MagicMock(return_value=None)):
            functions = {'test.ping': ping}
            self.schedule = salt.utils.schedule.Schedule(copy.deepcopy(DEFAULT_CONFIG), functions, returners={})
        self.schedule.opts['loop_interval'] = 1

    def tearDown(self):
        self.schedule.reset()

    def test_get_schedule(self):
        '''
        verify that the _get_schedule function works
        when remove_hidden is True and schedule data
        contains enabled key
        '''
        job_name = 'test_get_schedule'
        job = {
          'schedule': {
            'enabled': True,
            job_name: {
              'function': 'test.ping',
              'seconds': 60
            }
          }
        }
        # Add the job to the scheduler
        self.schedule.opts.update(job)

        ret = self.schedule._get_schedule(remove_hidden=True)
        self.assertEqual(job['schedule'], ret)
