# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.modules import status

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Globals
status.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class StatusTestCase(TestCase):
    '''
    test modules.status functions
    '''
    def test_uptime(self):
        '''
        test modules.status.uptime function
        '''
        mock_uptime = 'very often'
        mock_run = MagicMock(return_value=mock_uptime)
        with patch.dict(status.__salt__, {'cmd.run': mock_run}):
            self.assertEqual(status.uptime(), mock_uptime)

        mock_uptime = 'very idle'
        mock_run = MagicMock(return_value=mock_uptime)
        with patch.dict(status.__salt__, {'cmd.run': mock_run}):
            with patch('os.path.exists', MagicMock(return_value=True)):
                self.assertEqual(status.uptime(human_readable=False), mock_uptime.split()[0])

        mock_uptime = ''
        mock_return = 'unexpected format in /proc/uptime'
        mock_run = MagicMock(return_value=mock_uptime)
        with patch.dict(status.__salt__, {'cmd.run': mock_run}):
            with patch('os.path.exists', MagicMock(return_value=True)):
                self.assertEqual(status.uptime(human_readable=False), mock_return)

        mock_return = 'cannot find /proc/uptime'
        with patch('os.path.exists', MagicMock(return_value=False)):
            self.assertEqual(status.uptime(human_readable=False), mock_return)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(StatusTestCase, needs_daemon=False)
