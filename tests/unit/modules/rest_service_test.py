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
from salt.modules import rest_service

# Globals
rest_service.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RestSvcTestCase(TestCase):
    '''
    Test cases for salt.modules.rest_service
    '''
    def test_start(self):
        '''
        Test to start the specified service
        '''
        with patch.dict(rest_service.__opts__, {'proxyobject': MagicMock()}):
            with patch.object(rest_service.__opts__['proxyobject'],
                              'service_start', MagicMock(return_value=True)):
                self.assertTrue(rest_service.start('name'))

    def test_stop(self):
        '''
        Test to stop the specified service
        '''
        with patch.dict(rest_service.__opts__, {'proxyobject': MagicMock()}):
            with patch.object(rest_service.__opts__['proxyobject'],
                              'service_stop', MagicMock(return_value=True)):
                self.assertTrue(rest_service.stop('name'))

    def test_restart(self):
        '''
        Test to restart the named service
        '''
        with patch.dict(rest_service.__opts__, {'proxyobject': MagicMock()}):
            with patch.object(rest_service.__opts__['proxyobject'],
                              'service_restart', MagicMock(return_value=True)):
                self.assertTrue(rest_service.restart('name'))

    def test_status(self):
        '''
        Test to return the status for a service, returns a bool whether
        the service is running.
        '''
        with patch.dict(rest_service.__opts__, {'proxyobject': MagicMock()}):
            with patch.object(rest_service.__opts__['proxyobject'],
                              'service_status', MagicMock(return_value=True)):
                self.assertTrue(rest_service.status('name'))

    def test_list_(self):
        '''
        Test for list services.
        '''
        with patch.dict(rest_service.__opts__, {'proxyobject': MagicMock()}):
            with patch.object(rest_service.__opts__['proxyobject'],
                              'service_list_', MagicMock(return_value=True)):
                self.assertTrue(rest_service.list_())


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RestSvcTestCase, needs_daemon=False)
