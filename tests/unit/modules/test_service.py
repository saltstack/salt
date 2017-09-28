# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.modules.service as service


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ServiceTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.service
    '''
    def setup_loader_modules(self):
        return {service: {}}

    def test_start(self):
        '''
        Test to start the specified service
        '''
        with patch.object(os.path, 'join', return_value='A'):
            with patch.dict(service.__salt__, {'service.run':
                                               MagicMock(return_value=True)}):
                self.assertTrue(service.start('name'))

    def test_stop(self):
        '''
        Test to stop the specified service
        '''
        with patch.object(os.path, 'join', return_value='A'):
            with patch.dict(service.__salt__, {'service.run':
                                               MagicMock(return_value=True)}):
                self.assertTrue(service.stop('name'))

    def test_restart(self):
        '''
        Test to restart the specified service
        '''
        with patch.object(os.path, 'join', return_value='A'):
            with patch.dict(service.__salt__, {'service.run':
                                               MagicMock(return_value=True)}):
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
            with patch.dict(service.__salt__, {'service.run':
                                               MagicMock(return_value=True)}):
                self.assertTrue(service.reload_('name'))

    def test_run(self):
        '''
        Test to run the specified service
        '''
        with patch.object(os.path, 'join', return_value='A'):
            with patch.dict(service.__salt__, {'cmd.retcode':
                                               MagicMock(return_value=False)}):
                self.assertTrue(service.run('name', 'action'))

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
