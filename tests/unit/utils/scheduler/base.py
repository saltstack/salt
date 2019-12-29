# -*- coding: utf-8 -*-
'''
    tests.unit.utils.scheduler.base
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import
import copy
import logging
import os

# Import Salt Testing libs
from tests.support.case import TestCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.mock import MagicMock, patch
from tests.support.processes import terminate_process
from tests.support.runtests import RUNTIME_VARS

# Import Salt libs
import salt.utils.schedule
import salt.utils.platform
from salt.modules.test import ping
from salt.utils.process import SubprocessList
log = logging.getLogger(__name__)


class SchedulerTestsBase(TestCase, SaltReturnAssertsMixin):
    '''
    Validate the pkg module
    '''
    @classmethod
    def setUpClass(cls):
        root_dir = os.path.join(RUNTIME_VARS.TMP, 'schedule-unit-tests')
        sock_dir = os.path.join(root_dir, 'test-socks')

        default_config = salt.config.minion_config(None)
        default_config['conf_dir'] = root_dir
        default_config['root_dir'] = root_dir
        default_config['sock_dir'] = sock_dir
        default_config['pki_dir'] = os.path.join(root_dir, 'pki')
        default_config['cachedir'] = os.path.join(root_dir, 'cache')
        cls.default_config = default_config
        cls.subprocess_list = SubprocessList()

    @classmethod
    def tearDownClass(cls):
        del cls.default_config
        del cls.subprocess_list

    def setUp(self):
        with patch('salt.utils.schedule.clean_proc_dir', MagicMock(return_value=None)):
            functions = {'test.ping': ping}
            self.schedule = salt.utils.schedule.Schedule(
                copy.deepcopy(self.default_config),
                functions,
                returners={},
                new_instance=True
            )
        self.schedule._subprocess_list = self.subprocess_list

    def tearDown(self):
        subprocess_list = self.subprocess_list
        processes = subprocess_list.processes
        self.schedule.reset()
        del self.schedule
        for proc in processes:
            if proc.is_alive():
                terminate_process(proc.pid, kill_children=True, slow_stop=True)
        subprocess_list.cleanup()
        processes = subprocess_list.processes
        if processes:
            for proc in processes:
                if proc.is_alive():
                    terminate_process(proc.pid, kill_children=True, slow_stop=False)
            subprocess_list.cleanup()
        processes = subprocess_list.processes
        if processes:
            log.warning('Processes left running: %s', processes)
