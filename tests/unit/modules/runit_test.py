# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import os

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
from salt.modules import runit

# Globals
runit.__salt__ = {}
runit.SERVICE_DIR = '/etc/service'


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RunitTestCase(TestCase):
    '''
    Test cases for salt.modules.runit
    '''
    # 'start' function tests: 1

    def test_start(self):
        '''
        Test if it starts service via runit.
        '''
        mock_ret = MagicMock(return_value=False)
        with patch.dict(runit.__salt__, {'cmd.retcode': mock_ret}):
            self.assertTrue(runit.start('ssh'))

    # 'stop' function tests: 1

    def test_stop(self):
        '''
        Test if it stops service via runit.
        '''
        mock_ret = MagicMock(return_value=False)
        with patch.dict(runit.__salt__, {'cmd.retcode': mock_ret}):
            self.assertTrue(runit.stop('ssh'))

    # 'term' function tests: 1

    def test_term(self):
        '''
        Test if it send a TERM to service via runit.
        '''
        mock_ret = MagicMock(return_value=False)
        with patch.dict(runit.__salt__, {'cmd.retcode': mock_ret}):
            self.assertTrue(runit.term('ssh'))

    # 'reload_' function tests: 1

    def test_reload(self):
        '''
        Test if it send a HUP to service via runit.
        '''
        mock_ret = MagicMock(return_value=False)
        with patch.dict(runit.__salt__, {'cmd.retcode': mock_ret}):
            self.assertTrue(runit.reload_('ssh'))

    # 'restart' function tests: 1

    def test_restart(self):
        '''
        Test if it restart service via runit. This will stop/start service.
        '''
        mock_ret = MagicMock(return_value=False)
        with patch.dict(runit.__salt__, {'cmd.retcode': mock_ret}):
            self.assertTrue(runit.restart('ssh'))

    # 'full_restart' function tests: 1

    def test_full_restart(self):
        '''
        Test if it calls runit.restart() function.
        '''
        mock_ret = MagicMock(return_value=False)
        with patch.dict(runit.__salt__, {'cmd.retcode': mock_ret}):
            self.assertIsNone(runit.full_restart('ssh'))

    # 'status' function tests: 1

    def test_status(self):
        '''
        Test if it return the status for a service via runit,
        return pid if running.
        '''
        mock_run = MagicMock(return_value='salt')
        with patch.dict(runit.__salt__, {'cmd.run_stdout': mock_run}):
            self.assertEqual(runit.status('ssh'), '')

    # 'available' function tests: 1

    def test_available(self):
        '''
        Test if it returns ``True`` if the specified service is available,
        otherwise returns ``False``.
        '''
        with patch.object(os, 'listdir',
                          MagicMock(return_value=['/etc/service'])):
            self.assertTrue(runit.available('/etc/service'))

    # 'enabled' function tests: 1

    def test_enabled(self):
        '''
        Test if it returns ``True`` if the specified service is available,
        otherwise returns ``False``.
        '''
        with patch.object(os, 'listdir',
                          MagicMock(return_value=['run', 'supervise'])):
            mock_mode = MagicMock(return_value='0700')
            with patch.dict(runit.__salt__, {'file.get_mode': mock_mode}):
                with patch('salt.modules.runit.available', MagicMock(return_value=True)):
                    self.assertTrue(runit.enabled('foo'))

    # 'missing' function tests: 1

    def test_missing(self):
        '''
        Test if it returns ``True`` if the specified service is not available,
        otherwise returns ``False``.
        '''
        with patch.object(os, 'listdir',
                          MagicMock(return_value=['/etc/service'])):
            self.assertTrue(runit.missing('foo'))

    # 'get_all' function tests: 1

    def test_get_all(self):
        '''
        Test if it return a list of all available services.
        '''
        with patch.object(os, 'listdir',
                          MagicMock(return_value=['/etc/service'])):
            self.assertListEqual(runit.get_all(), ['/etc/service'])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RunitTestCase, needs_daemon=False)
