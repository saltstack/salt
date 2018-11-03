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
            out.msg(msg, title='Here')
            assert saltsupport.LogCollector.INFO in out.messages
            assert type(out.messages[saltsupport.LogCollector.INFO]) == saltsupport.LogCollector.MessagesList
            assert out.messages[saltsupport.LogCollector.INFO] == ['00:00:00.000 - {0}: {1}'.format('Here', msg)]

    def test_info_message(self):
        '''
        Test set info message to the log collector.

        :return:
        '''
        utcmock = MagicMock()
        utcmock.utcnow = MagicMock(return_value=datetime.datetime.utcfromtimestamp(0))
        with patch('datetime.datetime', utcmock):
            msg = 'SIMM crosstalk during tectonic stress'
            out = saltsupport.LogCollector()
            out.info(msg)
            assert saltsupport.LogCollector.INFO in out.messages
            assert type(out.messages[saltsupport.LogCollector.INFO]) == saltsupport.LogCollector.MessagesList
            assert out.messages[saltsupport.LogCollector.INFO] == ['00:00:00.000 - {}'.format(msg)]

    def test_warning_message(self):
        '''
        Test set warning message to the log collector.

        :return:
        '''
        utcmock = MagicMock()
        utcmock.utcnow = MagicMock(return_value=datetime.datetime.utcfromtimestamp(0))
        with patch('datetime.datetime', utcmock):
            msg = 'Your e-mail is now being delivered by USPS'
            out = saltsupport.LogCollector()
            out.warning(msg)
            assert saltsupport.LogCollector.WARNING in out.messages
            assert type(out.messages[saltsupport.LogCollector.WARNING]) == saltsupport.LogCollector.MessagesList
            assert out.messages[saltsupport.LogCollector.WARNING] == ['00:00:00.000 - {}'.format(msg)]

    def test_error_message(self):
        '''
        Test set error message to the log collector.

        :return:
        '''
        utcmock = MagicMock()
        utcmock.utcnow = MagicMock(return_value=datetime.datetime.utcfromtimestamp(0))
        with patch('datetime.datetime', utcmock):
            msg = 'Learning curve appears to be fractal'
            out = saltsupport.LogCollector()
            out.error(msg)
            assert saltsupport.LogCollector.ERROR in out.messages
            assert type(out.messages[saltsupport.LogCollector.ERROR]) == saltsupport.LogCollector.MessagesList
            assert out.messages[saltsupport.LogCollector.ERROR] == ['00:00:00.000 - {}'.format(msg)]

    def test_hl_message(self):
        '''
        Test highlighter message to the log collector.

        :return:
        '''
        utcmock = MagicMock()
        utcmock.utcnow = MagicMock(return_value=datetime.datetime.utcfromtimestamp(0))
        with patch('datetime.datetime', utcmock):
            out = saltsupport.LogCollector()
            out.highlight('The {} TTYs became {} TTYs and vice versa', 'real', 'pseudo')
            assert saltsupport.LogCollector.INFO in out.messages
            assert type(out.messages[saltsupport.LogCollector.INFO]) == saltsupport.LogCollector.MessagesList
            assert out.messages[saltsupport.LogCollector.INFO] == ['00:00:00.000 - The real TTYs became '
                                                                   'pseudo TTYs and vice versa']
