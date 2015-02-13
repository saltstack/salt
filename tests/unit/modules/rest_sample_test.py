# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
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

# Import Salt Libs
from salt.modules import rest_sample

# Globals
rest_sample.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RestSampleTestCase(TestCase):
    '''
    Test cases for salt.modules.rest_sample
    '''
    # 'grains_refresh' function tests: 1

    def test_grains_refresh(self):
        '''
        Test if it refresh the cache.
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(rest_sample.__opts__, {'proxyobject': mock}):
            self.assertTrue(rest_sample.grains_refresh())

    # 'ping' function tests: 1

    def test_ping(self):
        '''
        Test if it ping
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(rest_sample.__opts__, {'proxyobject': mock}):
            self.assertIsNone(rest_sample.ping())


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RestSampleTestCase, needs_daemon=False)
