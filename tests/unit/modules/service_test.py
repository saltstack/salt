# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import service
import os

# Globals
service.__grains__ = {}
service.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ServiceTestCase(TestCase):
    '''
    Test cases for salt.modules.service
    '''
    def test_start(self):
        '''
        Test to start the specified service
        '''
        with patch.object(os.path, 'join', return_value='A'):
            with patch.dict(service.__salt__, {'cmd.retcode':
                                               MagicMock(return_value=False)}):
                self.assertTrue(service.start('name'))

    def test_stop(self):
        '''
        Test to stop the specified service
        '''
        with patch.object(os.path, 'join', return_value='A'):
            with patch.dict(service.__salt__, {'cmd.retcode':
                                               MagicMock(return_value=False)}):
                self.assertTrue(service.stop('name'))

    def test_restart(self):
        '''
        Test to restart the specified service
        '''
        with patch.object(os.path, 'join', return_value='A'):
            with patch.dict(service.__salt__, {'cmd.retcode':
                                               MagicMock(return_value=False)}):
                self.assertTrue(service.restart('name'))

    def test_status(self):
        '''
        Test to return the status for a service, returns the PID or an empty
        string if the service is running or not, pass a signature to use to
        find the service via ps
        '''
        with patch.dict(service.__salt__,
                        {'status.pid': MagicMock(return_value=True)}):
            self.assertTrue(service.status('name'))

    def test_reload_(self):
        '''
        Test to restart the specified service
        '''
        with patch.object(os.path, 'join', return_value='A'):
            with patch.dict(service.__salt__, {'cmd.retcode':
                                               MagicMock(return_value=False)}):
                self.assertTrue(service.reload_('name'))

    def test_available(self):
        '''
        Test to returns ``True`` if the specified service is available,
        otherwise returns ``False``.
        '''
        with patch.object(service, 'get_all', return_value=['name', 'A']):
            self.assertTrue(service.available('name'))

    def test_missing(self):
        '''
        Test to inverse of service.available.
        '''
        with patch.object(service, 'get_all', return_value=['name1', 'A']):
            self.assertTrue(service.missing('name'))

    def test_get_all(self):
        '''
        Test to return a list of all available services
        '''
        with patch.object(os.path, 'isdir', side_effect=[False, True]):

            self.assertEqual(service.get_all(), [])

            with patch.object(os, 'listdir', return_value=['A', 'B']):
                self.assertListEqual(service.get_all(), ['A', 'B'])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ServiceTestCase, needs_daemon=False)
