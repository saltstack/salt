# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.modules import status
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
)

ensure_in_syspath('../../')

# Globals
status.__salt__ = {}
status.__grains__ = {}


class StatusTestCase(TestCase):
    '''
    test modules.status functions
    '''

    def test_uptime(self):
        '''
        Test modules.status.uptime function, new version
        :return:
        '''
        class ProcUptime(object):
            def __init__(self, *args, **kwargs):
                self.data = "773865.18 1003405.46"

            def read(self):
                return self.data

        with patch.dict(status.__salt__, {'cmd.run': MagicMock(return_value="1\n2\n3")}):
            with patch('os.path.exists', MagicMock(return_value=True)):
                with patch('time.time', MagicMock(return_value=1458821523.72)):
                    status.open = ProcUptime
                    u_time = status.uptime()
                    self.assertEqual(u_time['users'], 3)
                    self.assertEqual(u_time['seconds'], 773865)
                    self.assertEqual(u_time['days'], 8)
                    self.assertEqual(u_time['time'], '22:57')

    def test_uptime_failure(self):
        '''
        Test modules.status.uptime function should raise an exception if /proc/uptime does not exists.
        :return:
        '''
        with patch('os.path.exists', MagicMock(return_value=False)):
            with patch.dict(status.__grains__, {'kernel': 'Linux'}):
                with self.assertRaises(CommandExecutionError):
                    status.uptime()


if __name__ == '__main__':
    from integration import run_tests
    run_tests(StatusTestCase, needs_daemon=False)
