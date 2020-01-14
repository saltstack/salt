# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import random

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf

# Import Salt libs
from salt.ext import six
import salt.utils.platform

import pytest


@pytest.mark.windows_whitelisted
class StatusModuleTest(ModuleCase):
    '''
    Test the status module
    '''
    @skipIf(salt.utils.platform.is_windows(), 'minion is windows')
    @pytest.mark.flaky(max_runs=4)
    def test_status_pid(self):
        '''
        status.pid
        '''
        status_pid = self.run_function('status.pid', ['salt'])
        grab_pids = status_pid.split()[:10]
        random_pid = random.choice(grab_pids)
        grep_salt = self.run_function('cmd.run', ['pgrep -f salt'])
        assert random_pid in grep_salt

    @skipIf(not salt.utils.platform.is_windows(), 'windows only test')
    def test_status_cpuload(self):
        '''
        status.cpuload
        '''
        ret = self.run_function('status.cpuload')
        assert isinstance(ret, float)

    @skipIf(not salt.utils.platform.is_windows(), 'windows only test')
    def test_status_saltmem(self):
        '''
        status.saltmem
        '''
        ret = self.run_function('status.saltmem')
        assert isinstance(ret, int)

    def test_status_diskusage(self):
        '''
        status.diskusage
        '''
        ret = self.run_function('status.diskusage')
        if salt.utils.platform.is_darwin():
            assert 'not yet supported on this platform' in ret
        elif salt.utils.platform.is_windows():
            assert isinstance(ret['percent'], float)
        else:
            assert 'total' in str(ret)
            assert 'available' in str(ret)

    def test_status_procs(self):
        '''
        status.procs
        '''
        ret = self.run_function('status.procs')
        for x, y in six.iteritems(ret):
            assert 'cmd' in y

    def test_status_uptime(self):
        '''
        status.uptime
        '''
        ret = self.run_function('status.uptime')

        if salt.utils.platform.is_windows():
            assert isinstance(ret, float)
        else:
            assert isinstance(ret['days'], int)
