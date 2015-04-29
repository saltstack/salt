# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import monit


# Globals
monit.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MonitTestCase(TestCase):
    '''
    Test cases for salt.modules.aptpkg
    '''
    def test_start(self):
        '''
        Test for start
        '''
        with patch.dict(monit.__salt__,
                        {'cmd.retcode': MagicMock(return_value=False)}):
            self.assertTrue(monit.start('name'))

    def test_stop(self):
        '''
        Test for Stops service via monit
        '''
        with patch.dict(monit.__salt__,
                        {'cmd.retcode': MagicMock(return_value=False)}):
            self.assertTrue(monit.stop('name'))

    def test_restart(self):
        '''
        Test for Restart service via monit
        '''
        with patch.dict(monit.__salt__,
                        {'cmd.retcode': MagicMock(return_value=False)}):
            self.assertTrue(monit.restart('name'))

    def test_unmonitor(self):
        '''
        Test for Unmonitor service via monit
        '''
        with patch.dict(monit.__salt__,
                        {'cmd.retcode': MagicMock(return_value=False)}):
            self.assertTrue(monit.unmonitor('name'))

    def test_monitor(self):
        '''
        Test for monitor service via monit
        '''
        with patch.dict(monit.__salt__,
                        {'cmd.retcode': MagicMock(return_value=False)}):
            self.assertTrue(monit.monitor('name'))

    def test_summary(self):
        '''
        Test for Display a summary from monit
        '''
        mock = MagicMock(side_effect=['daemon is not running',
                                      'A\nB\nC\nD\nE'])
        with patch.dict(monit.__salt__, {'cmd.run': mock}):
            self.assertEqual(monit.summary(),
                             {'monit': 'daemon is not running',
                              'result': False})

            self.assertEqual(monit.summary(), {})

    def test_status(self):
        '''
        Test for Display a process status from monit
        '''
        with patch.dict(monit.__salt__,
                        {'cmd.run':
                         MagicMock(return_value='Process')}):
            self.assertEqual(monit.status('service'), 'No such service')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MonitTestCase, needs_daemon=False)
