# -*- coding: utf-8 -*-
'''
    :codeauthor: Bo Maryniuk <bo@suse.de>
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, MagicMock, NO_MOCK, NO_MOCK_REASON
from salt.modules import saltsupport
import datetime

try:
    import pytest
except ImportError:
    pytest = None


@skipIf(not bool(pytest), 'Pytest required')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltSupportModuleTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.support::SaltSupportModule
    '''
    def setup_loader_modules(self):
        return {saltsupport: {}}


@skipIf(not bool(pytest), 'Pytest required')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class LogCollectorTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.support::LogCollector
    '''
    def setup_loader_modules(self):
        return {saltsupport: {}}

    def test_msg(self):
        '''
        Test set message to the log collector.

        :return:
        '''
        utcmock = MagicMock()
        utcmock.utcnow = MagicMock(return_value=datetime.datetime.utcfromtimestamp(0))
        with patch('datetime.datetime', utcmock):
            msg = 'Upgrading /dev/null device'
            out = saltsupport.LogCollector()
            out.msg(msg)
            assert 'info' in out.messages
            assert type(out.messages['info']) == saltsupport.LogCollector.MessagesList
            assert out.messages['info'] == ['00:00:00.000 - {}'.format(msg)]
