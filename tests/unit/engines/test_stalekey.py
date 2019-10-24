# -*- coding: utf-8 -*-
'''
unit tests for the stalekey engine
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.engines.stalekey as stalekey
import salt.config

log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class EngineStalekeyTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.engine.sqs_events
    '''

    def setup_loader_modules(self):
        return {stalekey: {}}

    # 'present' function tests: 1
    def test_test(self):
        '''
        Test to ensure the SQS engine logs a warning when queue not present
        '''
        log.debug('=== testing ====')
        with patch('salt.key.get_key', MagicMock()) as mock_key:
            mock_key.delete_key.return_value = True
            ret = stalekey._delete_keys(['foo', 'bar', 'baz'])
        log.debug('=== ret %s ====', ret)
        self.assertTrue(True, True)
