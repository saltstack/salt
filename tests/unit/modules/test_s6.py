# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Marek Skrobacki <skrobul@skrobul.com>`
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.s6 as s6


@skipIf(NO_MOCK, NO_MOCK_REASON)
class S6TestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.s6
    '''
    def setup_loader_modules(self):
        return {s6: {'SERVICE_DIR': '/etc/service'}}

    # 'start' function tests: 1

    def test_start(self):
        '''
        Test if it starts service via s6-svc.
        '''
        mock_ret = MagicMock(return_value=False)
        with patch.dict(s6.__salt__, {'cmd.retcode': mock_ret}):
            self.assertTrue(s6.start('ssh'))

    # 'stop' function tests: 1

    def test_stop(self):
        '''
        Test if it stops service via s6.
        '''
        mock_ret = MagicMock(return_value=False)
        with patch.dict(s6.__salt__, {'cmd.retcode': mock_ret}):
            self.assertTrue(s6.stop('ssh'))

    # 'term' function tests: 1

    def test_term(self):
        '''
        Test if it send a TERM to service via s6.
        '''
        mock_ret = MagicMock(return_value=False)
        with patch.dict(s6.__salt__, {'cmd.retcode': mock_ret}):
            self.assertTrue(s6.term('ssh'))

    # 'reload_' function tests: 1

    def test_reload(self):
        '''
        Test if it send a HUP to service via s6.
        '''
        mock_ret = MagicMock(return_value=False)
        with patch.dict(s6.__salt__, {'cmd.retcode': mock_ret}):
            self.assertTrue(s6.reload_('ssh'))

    # 'restart' function tests: 1

    def test_restart(self):
        '''
        Test if it restart service via s6. This will stop/start service.
        '''
        mock_ret = MagicMock(return_value=False)
        with patch.dict(s6.__salt__, {'cmd.retcode': mock_ret}):
            self.assertTrue(s6.restart('ssh'))

    # 'full_restart' function tests: 1

    def test_full_restart(self):
        '''
        Test if it calls s6.restart() function.
        '''
        mock_ret = MagicMock(return_value=False)
        with patch.dict(s6.__salt__, {'cmd.retcode': mock_ret}):
            self.assertIsNone(s6.full_restart('ssh'))

    # 'status' function tests: 1

    def test_status(self):
        '''
        Test if it return the status for a service via s6,
        return pid if running.
        '''
        mock_run = MagicMock(return_value='salt')
        with patch.dict(s6.__salt__, {'cmd.run_stdout': mock_run}):
            self.assertEqual(s6.status('ssh'), '')

    # 'available' function tests: 1

    def test_available(self):
        '''
        Test if it returns ``True`` if the specified service is available,
        otherwise returns ``False``.
        '''
        with patch.object(os, 'listdir',
                          MagicMock(return_value=['/etc/service'])):
            self.assertTrue(s6.available('/etc/service'))

    # 'missing' function tests: 1

    def test_missing(self):
        '''
        Test if it returns ``True`` if the specified service is not available,
        otherwise returns ``False``.
        '''
        with patch.object(os, 'listdir',
                          MagicMock(return_value=['/etc/service'])):
            self.assertTrue(s6.missing('foo'))

    # 'get_all' function tests: 1

    def test_get_all(self):
        '''
        Test if it return a list of all available services.
        '''
        with patch.object(os, 'listdir',
                          MagicMock(return_value=['/etc/service'])):
            self.assertListEqual(s6.get_all(), ['/etc/service'])
